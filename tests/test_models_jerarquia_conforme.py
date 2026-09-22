"""Pruebas de la jerarquia por Servicio de Salud y de la prediccion conforme.

Usan datos sinteticos deterministas: no dependen de `data/processed/`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import RANDOM_SEED
from src.models.backtesting import (
    PointForecaster,
    rolling_origin_backtest,
    split_train_target,
)
from src.models.baseline import SeasonalNaive, SeasonalNaiveDrift
from src.models.conformal import ConformalWrapper, conformal_bounds
from src.models.features import (
    RM_SERIES_ID,
    SEASONAL_PERIOD,
    build_panel,
    build_supervised_frame,
    feature_columns,
    load_servicio_map,
)
from src.models.gradient_boosting import LightGBMGlobal
from src.models.hierarchy import (
    coherence_gap,
    reconcile_bottom_up,
    reconcile_middle_out,
    reconcile_top_down,
    reconcile_wls_structural,
)
from src.models.hybrid import HierarchicalHybrid, reconcile_combined_backtest
from src.models.linear_glm import PoissonGLMGlobal

COMUNAS = ("13101", "13102", "13103")
SERVICIO_MAP = pd.DataFrame(
    {
        "comuna_codigo": list(COMUNAS),
        "servicio_id": ["SS_NORTE", "SS_NORTE", "SS_SUR"],
        "servicio_glosa": [
            "Servicio de Salud Metropolitano Norte",
            "Servicio de Salud Metropolitano Norte",
            "Servicio de Salud Metropolitano Sur",
        ],
    }
)


def _weekly(n_anos: int = 3) -> pd.DataFrame:
    """Mart semanal sintetico con estacionalidad, tendencia y ruido reproducibles."""
    rng = np.random.RandomState(RANDOM_SEED)
    filas = []
    for indice, comuna in enumerate(COMUNAS):
        escala = 10 * (indice + 1)
        for ano in range(2021, 2021 + n_anos):
            for semana in range(1, SEASONAL_PERIOD + 1):
                nivel = escala + 5 * np.sin(2 * np.pi * semana / SEASONAL_PERIOD) + (ano - 2021)
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
    return pd.DataFrame(filas)


def _panel3() -> pd.DataFrame:
    return build_panel(_weekly(), servicio_map=SERVICIO_MAP)


def _predicciones3(valores: dict[str, float]) -> pd.DataFrame:
    """Un pronostico de 3 niveles con valores dados por serie."""
    estructura = {
        RM_SERIES_ID: ("region", None),
        "SS_NORTE": ("servicio", "SS_NORTE"),
        "SS_SUR": ("servicio", "SS_SUR"),
        "13101": ("comuna", "SS_NORTE"),
        "13102": ("comuna", "SS_NORTE"),
        "13103": ("comuna", "SS_SUR"),
    }
    filas = []
    for serie, (nivel, servicio) in estructura.items():
        valor = valores[serie]
        filas.append(
            {
                "series_id": serie,
                "nivel": nivel,
                "servicio_id": servicio,
                "y_pred": valor,
                "y_inferior": valor * 0.8,
                "y_superior": valor * 1.2,
                "origen": 10,
                "horizonte": 4,
            }
        )
    return pd.DataFrame(filas)


INCOHERENTE = {
    RM_SERIES_ID: 120.0, "SS_NORTE": 70.0, "SS_SUR": 40.0,
    "13101": 30.0, "13102": 30.0, "13103": 30.0,
}


def _valor(frame: pd.DataFrame, serie: str) -> float:
    return float(frame.loc[frame["series_id"] == serie, "y_pred"].iloc[0])


def _es_coherente(frame: pd.DataFrame) -> bool:
    comunas = {c: _valor(frame, c) for c in COMUNAS}
    norte = comunas["13101"] + comunas["13102"]
    sur = comunas["13103"]
    return (
        np.isclose(_valor(frame, "SS_NORTE"), norte)
        and np.isclose(_valor(frame, "SS_SUR"), sur)
        and np.isclose(_valor(frame, RM_SERIES_ID), norte + sur)
    )


class TestMapaServicio:
    def _escribir_maestro(self, tmp_path, filas):
        ruta = tmp_path / "maestro.parquet"
        pd.DataFrame(
            filas, columns=["comuna_codigo", "seremi_salud_glosa_servicio_de_salud_glosa"]
        ).to_parquet(ruta)
        return ruta

    def test_asigna_el_servicio_mayoritario(self, tmp_path):
        ruta = self._escribir_maestro(
            tmp_path,
            [
                ("13101", "Servicio de Salud Metropolitano Central"),
                ("13101", "Servicio de Salud Metropolitano Central"),
                ("13101", "Servicio de Salud Metropolitano Occidente"),
            ],
        )
        mapa = load_servicio_map(ruta)
        fila = mapa.iloc[0]
        assert fila["servicio_id"] == "SS_CENTRAL"
        assert fila["participacion"] == pytest.approx(2 / 3)
        assert fila["servicios_en_comuna"] == 2

    def test_excluye_categorias_que_no_son_servicios(self, tmp_path):
        # SEREMI y "No Aplica" no definen pertenencia aunque sean mayoria.
        ruta = self._escribir_maestro(
            tmp_path,
            [
                ("13101", "SEREMI de Salud Metropolitana de Santiago"),
                ("13101", "SEREMI de Salud Metropolitana de Santiago"),
                ("13101", "Servicio de Salud No Aplica"),
                ("13101", "Servicio de Salud Metropolitano Sur"),
                ("13101", None),
            ],
        )
        mapa = load_servicio_map(ruta)
        assert list(mapa["servicio_id"]) == ["SS_SUR"]

    def test_identificador_se_deriva_de_la_glosa(self, tmp_path):
        ruta = self._escribir_maestro(
            tmp_path, [("13201", "Servicio de Salud Metropolitano Sur Oriente")]
        )
        assert load_servicio_map(ruta).iloc[0]["servicio_id"] == "SS_SUR_ORIENTE"

    def test_empate_falla_en_vez_de_resolverse_en_silencio(self, tmp_path):
        ruta = self._escribir_maestro(
            tmp_path,
            [
                ("13101", "Servicio de Salud Metropolitano Norte"),
                ("13101", "Servicio de Salud Metropolitano Sur"),
            ],
        )
        with pytest.raises(ValueError, match="Empate"):
            load_servicio_map(ruta)


class TestPanelTresNiveles:
    def test_agrega_series_de_servicio(self):
        panel = _panel3()
        niveles = panel.drop_duplicates("series_id")["nivel"].value_counts()
        assert niveles["region"] == 1
        assert niveles["servicio"] == 2
        assert niveles["comuna"] == 3

    def test_servicio_es_la_suma_de_sus_comunas(self):
        panel = _panel3()
        norte = panel[panel["series_id"] == "SS_NORTE"].set_index("t")["y"]
        comunas_norte = (
            panel[panel["series_id"].isin(["13101", "13102"])].groupby("t")["y"].sum()
        )
        pd.testing.assert_series_equal(norte, comunas_norte, check_names=False)

    def test_region_es_la_suma_de_los_servicios(self):
        panel = _panel3()
        region = panel[panel["series_id"] == RM_SERIES_ID].set_index("t")["y"]
        servicios = panel[panel["nivel"] == "servicio"].groupby("t")["y"].sum()
        pd.testing.assert_series_equal(region, servicios, check_names=False)

    def test_sin_mapa_el_panel_no_cambia(self):
        panel = build_panel(_weekly())
        assert "servicio_id" not in panel.columns
        assert set(panel["nivel"]) == {"region", "comuna"}

    def test_comuna_sin_servicio_falla(self):
        incompleto = SERVICIO_MAP[SERVICIO_MAP["comuna_codigo"] != "13103"]
        with pytest.raises(ValueError, match="sin Servicio"):
            build_panel(_weekly(), servicio_map=incompleto)

    def test_servicio_id_no_es_predictor(self):
        frame = build_supervised_frame(_panel3(), horizon=4)
        assert "servicio_id" not in feature_columns(frame)

    def test_motor_adjunta_la_estructura_a_las_predicciones(self):
        panel = _panel3()
        pred = rolling_origin_backtest(panel, SeasonalNaive(), (4,), n_origins=2, step=2)
        assert {"nivel", "servicio_id"} <= set(pred.columns)
        assert set(pred["nivel"]) == {"region", "servicio", "comuna"}


class TestReconciliacionTresNiveles:
    def test_bottom_up_es_coherente_en_todos_los_niveles(self):
        rec = reconcile_bottom_up(_predicciones3(INCOHERENTE))
        assert _es_coherente(rec)
        assert _valor(rec, "13101") == 30.0

    def test_top_down_conserva_la_region_y_es_coherente(self):
        rec = reconcile_top_down(_predicciones3(INCOHERENTE))
        assert _valor(rec, RM_SERIES_ID) == pytest.approx(120.0)
        assert _es_coherente(rec)

    def test_middle_out_conserva_los_servicios(self):
        rec = reconcile_middle_out(_predicciones3(INCOHERENTE))
        assert _valor(rec, "SS_NORTE") == pytest.approx(70.0)
        assert _valor(rec, "SS_SUR") == pytest.approx(40.0)
        assert _valor(rec, RM_SERIES_ID) == pytest.approx(110.0)
        assert _es_coherente(rec)

    def test_middle_out_exige_nivel_servicio(self):
        dos_niveles = _predicciones3(INCOHERENTE)
        dos_niveles = dos_niveles[dos_niveles["nivel"] != "servicio"]
        with pytest.raises(ValueError, match="middle-out"):
            reconcile_middle_out(dos_niveles)

    def test_wls_es_coherente_y_usa_todos_los_niveles(self):
        rec = reconcile_wls_structural(_predicciones3(INCOHERENTE))
        assert _es_coherente(rec)
        # No descarta ningun nivel: el total no coincide con ninguno de los
        # candidatos puros (120 regional, 110 por servicios, 90 por comunas).
        total = _valor(rec, RM_SERIES_ID)
        assert 90.0 < total < 120.0

    def test_wls_deja_intacto_un_pronostico_ya_coherente(self):
        coherente = {
            RM_SERIES_ID: 90.0, "SS_NORTE": 60.0, "SS_SUR": 30.0,
            "13101": 30.0, "13102": 30.0, "13103": 30.0,
        }
        rec = reconcile_wls_structural(_predicciones3(coherente))
        for serie, valor in coherente.items():
            assert _valor(rec, serie) == pytest.approx(valor)

    def test_wls_no_produce_conteos_negativos(self):
        extremo = {
            RM_SERIES_ID: 1.0, "SS_NORTE": 1.0, "SS_SUR": 0.0,
            "13101": 50.0, "13102": 0.0, "13103": 0.0,
        }
        rec = reconcile_wls_structural(_predicciones3(extremo))
        assert (rec["y_pred"] >= 0).all()
        assert (rec["y_inferior"] >= 0).all()
        assert _es_coherente(rec)

    def test_wls_funciona_con_dos_niveles(self):
        dos = _predicciones3(INCOHERENTE)
        dos = dos[dos["nivel"] != "servicio"].drop(columns=["servicio_id"])
        rec = reconcile_wls_structural(dos)
        suma = rec[rec["nivel"] == "comuna"]["y_pred"].sum()
        assert _valor(rec, RM_SERIES_ID) == pytest.approx(suma)

    def test_wls_exige_todos_los_nodos(self):
        incompleto = _predicciones3(INCOHERENTE)
        incompleto = incompleto[incompleto["series_id"] != "13103"]
        # Sin la comuna 13103 el Servicio Sur queda sin miembros: la estructura
        # observada ya no corresponde a la jerarquia completa.
        with pytest.raises(ValueError, match="sin comunas"):
            reconcile_wls_structural(incompleto)

    def test_coherence_gap_ignora_el_nivel_servicio(self):
        brecha = coherence_gap(_predicciones3(INCOHERENTE))
        # 120 regional contra 90 de comunas; los Servicios no se suman.
        assert float(brecha.iloc[0]["brecha_absoluta"]) == pytest.approx(30.0)


class TestFitPoint:
    def test_modelos_cumplen_el_protocolo_puntual(self):
        for modelo in (SeasonalNaive(), PoissonGLMGlobal(), LightGBMGlobal()):
            assert isinstance(modelo, PointForecaster)
        assert not isinstance(SeasonalNaiveDrift(), PointForecaster)

    @pytest.mark.parametrize(
        "modelo",
        [
            PoissonGLMGlobal(max_iter=500),
            LightGBMGlobal(params={"n_estimators": 30}),
        ],
        ids=["glm", "lightgbm"],
    )
    def test_fit_point_coincide_con_fit_predict(self, modelo):
        frame = build_supervised_frame(_panel3(), horizon=4)
        train, objetivo, columnas = split_train_target(frame, origin=100, horizon=4)
        puntual = modelo.fit_point(train, objetivo, columnas)
        completo = modelo.fit_predict(frame, origin=100, horizon=4)
        np.testing.assert_allclose(puntual, completo["y_pred"].to_numpy())

    def test_hibrido_puntual_es_coherente_por_periodo(self):
        hibrido = HierarchicalHybrid(
            PoissonGLMGlobal(max_iter=500), LightGBMGlobal(params={"n_estimators": 30})
        )
        frame = build_supervised_frame(build_panel(_weekly()), horizon=4)
        train, _, columnas = split_train_target(frame, origin=100, horizon=4)
        ventana = frame[(frame["t"] > 80) & (frame["t"] <= 90)]
        pred = pd.Series(hibrido.fit_point(train[train["t"] <= 80], ventana, columnas))
        ventana = ventana.assign(pred=pred.to_numpy())
        for _, periodo in ventana.groupby("t"):
            region = periodo.loc[periodo["series_id"] == RM_SERIES_ID, "pred"].iloc[0]
            comunas = periodo.loc[periodo["series_id"] != RM_SERIES_ID, "pred"].sum()
            assert region == pytest.approx(comunas)


class TestConformal:
    def test_cotas_usan_correccion_de_muestra_finita(self):
        scores = np.arange(1.0, 27.0)  # n = 26
        inferior, superior, valida = conformal_bounds(scores, nivel=0.80)
        # floor(27 * 0.1) = 2 -> segundo menor; ceil(27 * 0.9) = 25 -> vigesimo quinto.
        assert inferior == 2.0
        assert superior == 25.0
        assert valida

    def test_pocos_residuos_invalidan_la_garantia(self):
        _, _, valida = conformal_bounds(np.arange(5.0), nivel=0.80)
        assert not valida

    def test_cobertura_empirica_cumple_el_nominal(self):
        # Bajo intercambiabilidad exacta la cobertura promedio debe ser al menos
        # el nominal y a lo mas nominal + 2/(n+1).
        rng = np.random.RandomState(RANDOM_SEED)
        n, repeticiones, nivel = 26, 3000, 0.80
        cubiertos = 0
        for _ in range(repeticiones):
            calibracion = rng.standard_t(df=4, size=n)
            prueba = rng.standard_t(df=4)
            inferior, superior, _ = conformal_bounds(calibracion, nivel)
            cubiertos += inferior <= prueba <= superior
        cobertura = cubiertos / repeticiones
        assert nivel - 0.02 <= cobertura <= nivel + 2 / (n + 1) + 0.02

    def test_rechaza_modelos_sin_fit_point(self):
        with pytest.raises(TypeError, match="fit_point"):
            ConformalWrapper(SeasonalNaiveDrift())

    def test_intervalo_ordenado_y_no_negativo(self):
        frame = build_supervised_frame(_panel3(), horizon=4)
        envuelto = ConformalWrapper(SeasonalNaive(), calibracion_periodos=20)
        pred = envuelto.fit_predict(frame, origin=130, horizon=4)
        assert (pred["y_inferior"] >= 0).all()
        assert (pred["y_superior"] >= pred["y_inferior"]).all()
        assert envuelto.name == "baseline_estacional_conformal"

    def test_calibra_cada_nivel_por_separado(self):
        frame = build_supervised_frame(_panel3(), horizon=4)
        envuelto = ConformalWrapper(SeasonalNaive(), calibracion_periodos=20)
        envuelto.fit_predict(frame, origin=130, horizon=4)
        calibracion = envuelto.ultima_calibracion
        assert set(calibracion["nivel"]) == {"region", "servicio", "comuna"}
        # 20 periodos x series del nivel.
        residuos = calibracion.set_index("nivel")["residuos"]
        assert residuos["region"] == 20
        assert residuos["servicio"] == 40
        assert residuos["comuna"] == 60

    def test_no_altera_el_pronostico_puntual_del_modelo_base(self):
        frame = build_supervised_frame(_panel3(), horizon=4)
        base = SeasonalNaive().fit_predict(frame, origin=130, horizon=4)
        conforme = ConformalWrapper(SeasonalNaive(), calibracion_periodos=20).fit_predict(
            frame, origin=130, horizon=4
        )
        np.testing.assert_allclose(base["y_pred"], conforme["y_pred"])

    def test_historia_insuficiente_falla_explicitamente(self):
        frame = build_supervised_frame(_panel3(), horizon=4)
        envuelto = ConformalWrapper(SeasonalNaive(), calibracion_periodos=200)
        with pytest.raises(ValueError, match="Historia insuficiente"):
            envuelto.fit_predict(frame, origin=130, horizon=4)


class TestHibridoCombinado:
    def test_combinar_backtests_equivale_al_hibrido(self):
        panel = build_panel(_weekly())
        horizontes = (4,)
        glm = PoissonGLMGlobal(max_iter=500)
        lgbm = LightGBMGlobal(params={"n_estimators": 30})
        pred_glm = rolling_origin_backtest(panel, glm, horizontes, 2, 2)
        pred_lgbm = rolling_origin_backtest(panel, lgbm, horizontes, 2, 2)
        combinado = reconcile_combined_backtest(pred_glm, pred_lgbm, "top_down", "h")

        hibrido = HierarchicalHybrid(
            PoissonGLMGlobal(max_iter=500), LightGBMGlobal(params={"n_estimators": 30})
        )
        directo = rolling_origin_backtest(panel, hibrido, horizontes, 2, 2)

        clave = ["origen", "series_id"]
        a = combinado.sort_values(clave)["y_pred"].to_numpy()
        b = directo.sort_values(clave)["y_pred"].to_numpy()
        np.testing.assert_allclose(a, b)


class TestPruebaPareada:
    def _pred(self, errores: list[float], serie: str = "13101") -> pd.DataFrame:
        return pd.DataFrame(
            {
                "origen": list(range(len(errores))),
                "horizonte": 4,
                "series_id": serie,
                "y_real": 10.0,
                "y_pred": [10.0 + e for e in errores],
            }
        )

    def test_detecta_una_mejora_consistente(self):
        from src.models.metrics import paired_comparison

        a = self._pred([3.0] * 40)
        b = self._pred([1.0] * 39 + [0.5])
        resultado = paired_comparison(a, b, {"13101": 1.0})
        assert resultado["cambio_pct"] < 0
        assert resultado["proporcion_b_mejor"] == 1.0
        assert resultado["p_valor"] < 0.05

    def test_modelos_identicos_dan_p_uno(self):
        from src.models.metrics import paired_comparison

        a = self._pred([2.0, 1.0, 3.0])
        resultado = paired_comparison(a, a.copy(), {"13101": 1.0})
        assert resultado["p_valor"] == 1.0
        assert resultado["cambio_pct"] == 0.0

    def test_media_y_proporcion_pueden_discrepar(self):
        # b es peor en la mayoria de los pronosticos pero corrige un error enorme:
        # su promedio mejora aunque gane en pocos casos.
        from src.models.metrics import paired_comparison

        a = self._pred([1.0] * 9 + [100.0])
        b = self._pred([2.0] * 9 + [1.0])
        resultado = paired_comparison(a, b, {"13101": 1.0})
        assert resultado["cambio_pct"] < 0
        assert resultado["proporcion_b_mejor"] == pytest.approx(0.1)

    def test_filtra_por_series(self):
        from src.models.metrics import paired_comparison

        a = pd.concat([self._pred([1.0] * 5, "13101"), self._pred([9.0] * 5, "13102")])
        b = pd.concat([self._pred([1.0] * 5, "13101"), self._pred([0.0] * 5, "13102")])
        solo_una = paired_comparison(a, b, {"13101": 1.0, "13102": 1.0}, ["13101"])
        assert solo_una["n"] == 5
        assert solo_una["cambio_pct"] == 0.0

    def test_tolerancia_de_cobertura_decrece_con_n(self):
        from src.models.metrics import coverage_tolerance

        assert coverage_tolerance(65, 0.8) == pytest.approx(0.0972, abs=1e-4)
        assert coverage_tolerance(3315, 0.8) < coverage_tolerance(65, 0.8)
        assert np.isnan(coverage_tolerance(0, 0.8))


class TestReglaDeSeleccion:
    """La regla de decision del benchmark: calibrado primero, precision despues."""

    def _tabla(self, filas):
        return pd.DataFrame(
            filas,
            columns=[
                "modelo", "mase_region", "mase_comuna", "mase_promedio",
                "cobertura_region", "cobertura_comuna",
                "calibrado_region", "calibrado_comuna",
            ],
        )

    def _predicciones(self, nombres, errores):
        """Predicciones sinteticas donde cada modelo tiene un error constante."""
        filas = []
        for nombre, error in zip(nombres, errores):
            for origen in range(30):
                for serie, nivel in ((RM_SERIES_ID, "region"), ("13101", "comuna")):
                    filas.append(
                        {
                            "origen": origen, "horizonte": 4, "series_id": serie,
                            "nivel": nivel, "y_real": 10.0,
                            "y_pred": 10.0 + error + 0.01 * (origen % 3),
                        }
                    )
            yield nombre, pd.DataFrame(filas)
            filas = []

    def test_prefiere_el_calibrado_aunque_otro_sea_mas_preciso(self):
        from scripts.run_demand_benchmark import select_model

        tabla = self._tabla(
            [
                ("preciso_mal_calibrado", 0.60, 0.60, 0.60, 0.95, 0.70, False, False),
                ("calibrado", 0.61, 0.61, 0.61, 0.80, 0.80, True, True),
                ("baseline_estacional", 0.90, 0.90, 0.90, 0.85, 0.80, True, True),
            ]
        )
        predicciones = dict(
            self._predicciones(["preciso_mal_calibrado", "calibrado"], [1.0, 1.0])
        )
        elegido, texto = select_model(
            tabla, predicciones, {RM_SERIES_ID: 1.0, "13101": 1.0}
        )
        assert elegido == "calibrado"
        assert "no es estadisticamente distinguible" in texto

    def test_declara_intercambio_si_la_ventaja_es_significativa(self):
        from scripts.run_demand_benchmark import select_model

        tabla = self._tabla(
            [
                ("preciso_mal_calibrado", 0.40, 0.40, 0.40, 0.95, 0.70, False, False),
                ("calibrado", 0.61, 0.61, 0.61, 0.80, 0.80, True, True),
                ("baseline_estacional", 0.90, 0.90, 0.90, 0.85, 0.80, True, True),
            ]
        )
        predicciones = dict(
            self._predicciones(["preciso_mal_calibrado", "calibrado"], [0.5, 3.0])
        )
        elegido, texto = select_model(
            tabla, predicciones, {RM_SERIES_ID: 1.0, "13101": 1.0}
        )
        assert elegido == "calibrado"
        assert "intercambio real" in texto

    def test_excluye_baselines_de_los_candidatos(self):
        from scripts.run_demand_benchmark import select_model

        tabla = self._tabla(
            [
                ("baseline_estacional_drift", 0.85, 0.85, 0.85, 0.80, 0.80, True, True),
                ("modelo", 0.70, 0.70, 0.70, 0.80, 0.80, True, True),
                ("baseline_estacional", 0.90, 0.90, 0.90, 0.80, 0.80, True, True),
            ]
        )
        elegido, _ = select_model(tabla, {}, {})
        assert elegido == "modelo"

    def test_sin_candidatos_recomienda_el_baseline(self):
        from scripts.run_demand_benchmark import select_model

        tabla = self._tabla(
            [
                ("peor", 0.95, 0.95, 0.95, 0.80, 0.80, True, True),
                ("baseline_estacional", 0.90, 0.90, 0.90, 0.80, 0.80, True, True),
            ]
        )
        elegido, texto = select_model(tabla, {}, {})
        assert elegido == "baseline_estacional"
        assert "ningun modelo supera" in texto
