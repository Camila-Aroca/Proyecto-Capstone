"""Pruebas dirigidas para el paquete de modelos de demanda (`src/models`).

Usan paneles sinteticos deterministas: las pruebas no dependen de que
`data/processed/` este materializado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.models import RANDOM_SEED
from src.models.backtesting import (
    build_origins,
    empirical_interval,
    prepare_supervised,
    rolling_origin_backtest,
    split_train_target,
    summarize_backtest,
)
from src.models.baseline import SeasonalNaive
from src.models.features import (
    RM_SERIES_ID,
    SEASONAL_PERIOD,
    build_panel,
    build_supervised_frame,
    drop_incomplete_rows,
    feature_columns,
)
from src.models.gradient_boosting import LightGBMGlobal
from src.models.hybrid import HierarchicalHybrid
from src.models.linear_glm import PoissonGLMGlobal
from src.models.hierarchy import (
    coherence_gap,
    reconcile_bottom_up,
    reconcile_top_down,
)
from src.models.metrics import (
    evaluate_predictions,
    interval_coverage,
    mape,
    mase,
    seasonal_naive_scale,
)


def _weekly_fixture(n_anos: int = 4, comunas: tuple[str, ...] = ("13101", "13102")):
    """Mart semanal sintetico con estacionalidad y tendencia reproducibles."""
    rng = np.random.RandomState(RANDOM_SEED)
    filas = []
    for indice, comuna in enumerate(comunas):
        escala = 10 * (indice + 1)
        for ano in range(2021, 2021 + n_anos):
            for semana in range(1, SEASONAL_PERIOD + 1):
                estacional = 5 * np.sin(2 * np.pi * semana / SEASONAL_PERIOD)
                nivel = escala + estacional + (ano - 2021) * 2
                filas.append(
                    {
                        "comuna_codigo": comuna,
                        "comuna_glosa": f"Comuna {comuna}",
                        "ano": ano,
                        "semana": semana,
                        "atenciones_id36": max(0, int(nivel + rng.normal(0, 1))),
                        "poblacion_anual": 100_000 * (indice + 1),
                        "atenciones_id1": int(nivel * 10),
                        "n_establecimientos_reportantes_id36": 3,
                    }
                )
        # Fragmento de calendario que debe quedar fuera del panel.
        filas.append(
            {
                "comuna_codigo": comuna, "comuna_glosa": f"Comuna {comuna}",
                "ano": 2021, "semana": SEASONAL_PERIOD + 1,
                "atenciones_id36": 1, "poblacion_anual": 100_000 * (indice + 1),
                "atenciones_id1": 10, "n_establecimientos_reportantes_id36": 3,
            }
        )
    return pd.DataFrame(filas)


class TestPanel:
    def test_excluye_semana_53_y_agrega_serie_rm(self):
        panel = build_panel(_weekly_fixture())
        assert (panel["semana"] != SEASONAL_PERIOD + 1).all()
        assert RM_SERIES_ID in set(panel["series_id"])
        assert set(panel["nivel"]) == {"comuna", "region"}

    def test_indice_temporal_es_continuo_y_compartido(self):
        panel = build_panel(_weekly_fixture(n_anos=2))
        esperado = 2 * SEASONAL_PERIOD
        assert panel["t"].nunique() == esperado
        assert sorted(panel["t"].unique()) == list(range(esperado))
        # Todas las series comparten la misma grilla.
        longitudes = panel.groupby("series_id")["t"].size().unique()
        assert len(longitudes) == 1

    def test_serie_rm_es_la_suma_de_las_comunas(self):
        panel = build_panel(_weekly_fixture(n_anos=2))
        region = panel[panel["series_id"] == RM_SERIES_ID].set_index("t")["y"]
        comunas = panel[panel["series_id"] != RM_SERIES_ID].groupby("t")["y"].sum()
        pd.testing.assert_series_equal(
            region.sort_index(), comunas.sort_index(), check_names=False
        )

    def test_rechaza_panel_con_series_de_distinta_longitud(self):
        weekly = _weekly_fixture(n_anos=2)
        # Quitar una semana a una sola comuna rompe la regularidad de la grilla.
        mutilado = weekly.drop(
            weekly[(weekly["comuna_codigo"] == "13101") & (weekly["semana"] == 10)].index
        )
        with pytest.raises(ValueError, match="misma longitud"):
            build_panel(mutilado)


class TestAusenciaDeFugaTemporal:
    """La garantia mas importante del paquete: no mirar el futuro."""

    def test_features_no_cambian_al_alterar_el_futuro(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        horizonte = 4
        corte = 100

        original = build_supervised_frame(panel, horizon=horizonte)
        alterado_panel = panel.copy()
        # Se multiplica por 1000 todo lo posterior al corte.
        futuro = alterado_panel["t"] > corte
        alterado_panel.loc[futuro, "y"] = alterado_panel.loc[futuro, "y"] * 1000
        alterado = build_supervised_frame(alterado_panel, horizon=horizonte)

        columnas = feature_columns(original)
        # Las filas cuyo objetivo es anterior o igual al corte solo pueden usar
        # informacion hasta t-horizonte, de modo que no deben verse afectadas.
        antes = original[original["t"] <= corte][columnas].reset_index(drop=True)
        antes_alterado = alterado[alterado["t"] <= corte][columnas].reset_index(drop=True)
        pd.testing.assert_frame_equal(antes, antes_alterado)

    def test_rezagos_respetan_el_horizonte(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        for horizonte in (4, 8):
            frame = build_supervised_frame(panel, horizon=horizonte)
            rezagos = [
                int(c.split("_")[-1]) for c in frame.columns
                if c.startswith("y_lag_")
            ]
            # Ningun rezago del target puede ser menor que el horizonte: eso
            # significaria usar una observacion aun no disponible.
            assert min(rezagos) >= horizonte

    def test_lag_estacional_coincide_con_el_valor_del_anio_previo(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        una = frame[frame["series_id"] == "13101"].sort_values("t")
        y = una["y"].to_numpy()
        lag = una[f"y_lag_{SEASONAL_PERIOD}"].to_numpy()
        np.testing.assert_allclose(lag[SEASONAL_PERIOD:], y[:-SEASONAL_PERIOD])

    def test_no_mezcla_informacion_entre_series(self):
        panel = build_panel(_weekly_fixture(n_anos=2))
        frame = build_supervised_frame(panel, horizon=4)
        # El primer periodo de cada serie no tiene historia propia: su rezago
        # debe ser nulo, no el valor final de la serie anterior.
        primeros = frame.sort_values("t").groupby("series_id").head(4)
        assert primeros["y_lag_4"].isna().all()


class TestFeatures:
    def test_feature_columns_excluye_identificadores_y_target(self):
        panel = build_panel(_weekly_fixture(n_anos=2))
        frame = build_supervised_frame(panel, horizon=4)
        columnas = feature_columns(frame)
        for prohibida in ("y", "series_id", "t", "ano", "comuna_glosa", "nivel"):
            assert prohibida not in columnas
        assert "y_lag_4" in columnas

    def test_drop_incomplete_rows_elimina_filas_sin_historia(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        columnas = feature_columns(frame)
        limpio = drop_incomplete_rows(frame, columnas)
        assert not limpio[columnas].isna().any().any()
        assert len(limpio) < len(frame)

    def test_features_ciclicas_son_continuas_entre_semana_52_y_1(self):
        panel = build_panel(_weekly_fixture(n_anos=2))
        frame = build_supervised_frame(panel, horizon=4)
        s52 = frame[frame["semana"] == 52].iloc[0]
        s1 = frame[frame["semana"] == 1].iloc[0]
        # El salto entre el fin y el inicio del anio debe ser pequeno.
        assert abs(float(s52["cos_1"]) - float(s1["cos_1"])) < 0.05

    def test_horizonte_invalido_es_rechazado(self):
        panel = build_panel(_weekly_fixture(n_anos=2))
        with pytest.raises(ValueError, match="entero positivo"):
            build_supervised_frame(panel, horizon=0)


class TestMetricas:
    def test_mape_excluye_ceros(self):
        real = np.array([0.0, 10.0])
        pred = np.array([5.0, 11.0])
        assert mape(real, pred) == pytest.approx(10.0)

    def test_mape_sin_valores_positivos_es_nan(self):
        assert np.isnan(mape(np.zeros(3), np.ones(3)))

    def test_mase_menor_que_uno_si_supera_al_baseline(self):
        historia = np.array([1.0, 5.0] * 20)
        escala = seasonal_naive_scale(historia, period=1)
        real = np.array([1.0, 5.0])
        assert mase(real, real, escala) == 0.0
        assert mase(real, real + escala, escala) == pytest.approx(1.0)

    def test_escala_de_serie_constante_es_nan(self):
        assert np.isnan(seasonal_naive_scale(np.ones(30), period=4))

    def test_cobertura_cuenta_los_valores_dentro_del_intervalo(self):
        real = np.array([1.0, 5.0, 10.0])
        assert interval_coverage(real, np.zeros(3), np.array([2.0, 4.0, 20.0])) == pytest.approx(
            2 / 3
        )

    def test_evaluate_predictions_exige_columnas_minimas(self):
        with pytest.raises(ValueError, match="Faltan columnas"):
            evaluate_predictions(pd.DataFrame({"series_id": ["a"]}))


class TestBacktesting:
    def test_origenes_dejan_espacio_para_el_horizonte_maximo(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        horizontes = (4, 8)
        origenes = build_origins(panel, horizontes, n_origins=5, step=2)
        assert len(origenes) == 5
        assert max(origenes) + max(horizontes) <= int(panel["t"].max())

    def test_split_separa_entrenamiento_y_objetivo(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        train, objetivo, columnas = split_train_target(frame, origin=120, horizon=4)
        assert train["t"].max() <= 120
        assert set(objetivo["t"].unique()) == {124}
        assert columnas

    def test_intervalo_empirico_respeta_el_nivel(self):
        residuos = np.arange(-50.0, 51.0)
        inferior, superior = empirical_interval(residuos, nivel=0.80)
        assert inferior < 0 < superior
        assert interval_coverage(residuos, np.full(101, inferior), np.full(101, superior)) >= 0.79

    def test_intervalo_empirico_sin_residuos_es_nan(self):
        inferior, superior = empirical_interval(np.array([]), nivel=0.80)
        assert np.isnan(inferior) and np.isnan(superior)


class TestBaseline:
    def test_predice_el_mismo_periodo_del_anio_anterior(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        modelo = SeasonalNaive()
        prediccion = modelo.fit_predict(frame, origin=120, horizon=4)
        objetivo = frame[frame["t"] == 124].set_index("series_id")
        for _, fila in prediccion.iterrows():
            esperado = objetivo.loc[fila["series_id"], f"y_lag_{SEASONAL_PERIOD}"]
            assert fila["y_pred"] == pytest.approx(float(esperado))

    def test_intervalo_no_es_negativo_y_esta_ordenado(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        prediccion = SeasonalNaive().fit_predict(frame, origin=120, horizon=4)
        assert (prediccion["y_inferior"] >= 0).all()
        assert (prediccion["y_superior"] >= prediccion["y_inferior"]).all()

    def test_backtest_completo_produce_metricas(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        horizontes = (4,)
        predicciones = rolling_origin_backtest(
            panel, SeasonalNaive(), horizontes, n_origins=3, step=2
        )
        assert set(predicciones["modelo"]) == {"baseline_estacional"}
        assert predicciones["y_real"].notna().all()
        resumen = summarize_backtest(predicciones, panel, horizontes, 3, 2)
        assert {"mae", "rmse", "mase", "cobertura"} <= set(resumen.columns)


class TestLightGBMGlobal:
    def test_predicciones_no_negativas_con_intervalo_ordenado(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        modelo = LightGBMGlobal(params={"n_estimators": 30})
        prediccion = modelo.fit_predict(frame, origin=120, horizon=4)
        assert len(prediccion) == panel["series_id"].nunique()
        assert (prediccion["y_pred"] >= 0).all()
        assert (prediccion["y_inferior"] >= 0).all()
        assert (prediccion["y_superior"] >= prediccion["y_inferior"]).all()

    def test_es_reproducible_con_la_misma_semilla(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        parametros = {"n_estimators": 30}
        primera = LightGBMGlobal(seed=7, params=parametros).fit_predict(frame, 120, 4)
        segunda = LightGBMGlobal(seed=7, params=parametros).fit_predict(frame, 120, 4)
        pd.testing.assert_frame_equal(primera, segunda)

    def test_importancias_requieren_ajuste_previo(self):
        with pytest.raises(ValueError, match="no ha sido ajustado"):
            LightGBMGlobal().feature_importances()


class TestReconciliacion:
    def _predicciones_incoherentes(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "series_id": [RM_SERIES_ID, "13101", "13102"],
                "y_pred": [100.0, 40.0, 40.0],
                "y_inferior": [80.0, 30.0, 30.0],
                "y_superior": [120.0, 50.0, 50.0],
                "origen": [10, 10, 10],
                "horizonte": [4, 4, 4],
            }
        )

    def test_coherence_gap_detecta_la_diferencia(self):
        brecha = coherence_gap(self._predicciones_incoherentes())
        assert float(brecha.iloc[0]["brecha_absoluta"]) == pytest.approx(20.0)
        assert float(brecha.iloc[0]["brecha_relativa_pct"]) == pytest.approx(20.0)

    def test_bottom_up_hace_que_la_region_sea_la_suma(self):
        reconciliado = reconcile_bottom_up(self._predicciones_incoherentes())
        region = reconciliado[reconciliado["series_id"] == RM_SERIES_ID].iloc[0]
        assert float(region["y_pred"]) == pytest.approx(80.0)
        assert coherence_gap(reconciliado).iloc[0]["brecha_absoluta"] == pytest.approx(0.0)

    def test_bottom_up_no_altera_las_comunas(self):
        original = self._predicciones_incoherentes()
        reconciliado = reconcile_bottom_up(original)
        comunas = reconciliado[reconciliado["series_id"] != RM_SERIES_ID]
        assert sorted(comunas["y_pred"]) == [40.0, 40.0]

    def test_top_down_conserva_el_total_regional(self):
        reconciliado = reconcile_top_down(self._predicciones_incoherentes())
        region = reconciliado[reconciliado["series_id"] == RM_SERIES_ID].iloc[0]
        assert float(region["y_pred"]) == pytest.approx(100.0)
        comunas = reconciliado[reconciliado["series_id"] != RM_SERIES_ID]
        assert float(comunas["y_pred"].sum()) == pytest.approx(100.0)
        assert coherence_gap(reconciliado).iloc[0]["brecha_absoluta"] == pytest.approx(0.0)

    def test_top_down_con_suma_comunal_cero_no_divide_por_cero(self):
        predicciones = self._predicciones_incoherentes()
        predicciones.loc[predicciones["series_id"] != RM_SERIES_ID, "y_pred"] = 0.0
        reconciliado = reconcile_top_down(predicciones)
        comunas = reconciliado[reconciliado["series_id"] != RM_SERIES_ID]
        assert comunas["y_pred"].notna().all()
        assert float(comunas["y_pred"].sum()) == pytest.approx(0.0)


class TestRegistroEnPipeline:
    def test_stage_registrado_con_dependencia_correcta(self):
        stage = pipeline.STAGES["benchmark_demanda_sm"]
        assert stage["module"] == "scripts.run_demand_benchmark"
        # El maestro de establecimientos define la jerarquia por Servicio de Salud.
        assert stage["depends_on"] == [
            "build_urgencias_comuna_marts",
            "clean_establishments",
        ]
        assert stage["outputs"] == [
            "reports/modeling/benchmark_demanda_sm.md",
            "reports/modeling/benchmark_demanda_sm_resumen.csv",
            "reports/modeling/benchmark_demanda_sm_seleccion.json",
        ]

    def test_stage_corre_despues_de_su_upstream(self):
        orden = pipeline.PIPELINE_ORDER
        for upstream in ("build_urgencias_comuna_marts", "clean_establishments"):
            assert orden.index(upstream) < orden.index("benchmark_demanda_sm")


class TestPoissonGLMGlobal:
    def test_predicciones_no_negativas_con_intervalo_ordenado(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        modelo = PoissonGLMGlobal(max_iter=500)
        prediccion = modelo.fit_predict(frame, origin=120, horizon=4)
        assert len(prediccion) == panel["series_id"].nunique()
        assert (prediccion["y_pred"] >= 0).all()
        assert (prediccion["y_inferior"] >= 0).all()
        assert (prediccion["y_superior"] >= prediccion["y_inferior"]).all()

    def test_estima_dispersion_por_serie(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        modelo = PoissonGLMGlobal(max_iter=500)
        modelo.fit_predict(frame, origin=120, horizon=4)
        # Debe haber una dispersion propia por serie, no una sola agrupada.
        assert len(modelo.dispersion_por_serie) > 1
        # La sobredispersion nunca se reporta por debajo de Poisson puro.
        assert all(v >= 1.0 for v in modelo.dispersion_por_serie.values())
        assert modelo.dispersion_agrupada >= 1.0

    def test_expone_coeficientes_interpretables(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        modelo = PoissonGLMGlobal(max_iter=500)
        modelo.fit_predict(frame, origin=120, horizon=4)
        assert modelo.coeficientes is not None
        assert {"termino", "coeficiente"} == set(modelo.coeficientes.columns)
        # Un termino por feature mas uno por serie del dominio.
        assert len(modelo.coeficientes) > len(feature_columns(frame))

    def test_es_reproducible(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        primera = PoissonGLMGlobal(max_iter=500).fit_predict(frame, 120, 4)
        segunda = PoissonGLMGlobal(max_iter=500).fit_predict(frame, 120, 4)
        pd.testing.assert_frame_equal(primera, segunda)


class TestHierarchicalHybrid:
    def _hibrido(self, reconciliacion: str = "top_down") -> HierarchicalHybrid:
        return HierarchicalHybrid(
            region_model=PoissonGLMGlobal(max_iter=500),
            comuna_model=LightGBMGlobal(params={"n_estimators": 30}),
            reconciliacion=reconciliacion,
        )

    def test_rechaza_reconciliacion_no_soportada(self):
        with pytest.raises(ValueError, match="no soportada"):
            HierarchicalHybrid(SeasonalNaive(), SeasonalNaive(), reconciliacion="mint")

    def test_nombre_describe_la_composicion(self):
        hibrido = self._hibrido()
        assert "poisson_glm_global" in hibrido.name
        assert "lightgbm_global" in hibrido.name
        assert "top_down" in hibrido.name

    def test_resultado_es_coherente_entre_niveles(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        prediccion = self._hibrido().fit_predict(frame, origin=120, horizon=4)
        region = prediccion[prediccion["series_id"] == RM_SERIES_ID]["y_pred"].sum()
        comunas = prediccion[prediccion["series_id"] != RM_SERIES_ID]["y_pred"].sum()
        assert float(comunas) == pytest.approx(float(region), rel=1e-6)

    def test_conserva_el_total_del_modelo_regional(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        glm = PoissonGLMGlobal(max_iter=500)
        solo_glm = glm.fit_predict(frame, origin=120, horizon=4)
        esperado = float(
            solo_glm[solo_glm["series_id"] == RM_SERIES_ID]["y_pred"].iloc[0]
        )
        hibrido = self._hibrido().fit_predict(frame, origin=120, horizon=4)
        obtenido = float(
            hibrido[hibrido["series_id"] == RM_SERIES_ID]["y_pred"].iloc[0]
        )
        assert obtenido == pytest.approx(esperado, rel=1e-9)

    def test_no_devuelve_columnas_auxiliares_de_reconciliacion(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        frame = build_supervised_frame(panel, horizon=4)
        prediccion = self._hibrido().fit_predict(frame, origin=120, horizon=4)
        assert "origen" not in prediccion.columns
        assert "horizonte" not in prediccion.columns

    def test_funciona_en_el_motor_de_backtesting(self):
        panel = build_panel(_weekly_fixture(n_anos=3))
        predicciones = rolling_origin_backtest(
            panel, self._hibrido(), (4,), n_origins=2, step=2
        )
        assert predicciones["y_real"].notna().all()
        assert set(predicciones["modelo"]) == {self._hibrido().name}
