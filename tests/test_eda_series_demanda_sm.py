"""Pruebas dirigidas para el EDA de series temporales de demanda de salud mental.

Usan fixtures sinteticas deterministas en vez del mart real: las pruebas deben
correr sin depender de que `data/processed/` este materializado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from scripts.eda_series_demanda_sm import (
    SEASONAL_PERIOD,
    TARGET,
    _tabla_md,
    audit_calendar,
    autocorrelation_profile,
    build_comuna_matrix,
    build_rm_series,
    comuna_heterogeneity,
    seasonal_naive_backtest,
    seasonal_naive_by_comuna,
    stationarity_tests,
)


def _weekly_fixture() -> pd.DataFrame:
    """Mart semanal sintetico: 2 comunas, 3 semanas regulares y una `semana 53`."""
    filas = [
        # (comuna_codigo, comuna_glosa, ano, semana, fecha, id1, id36, id37, reportantes)
        ("13101", "Comuna A", 2021, 1, "2021-01-04", 100, 10, 1, 5),
        ("13101", "Comuna A", 2021, 2, "2021-01-11", 110, 12, 1, 5),
        ("13101", "Comuna A", 2021, 3, "2021-01-18", 120, 14, 2, 5),
        ("13101", "Comuna A", 2021, 53, "2021-01-01", 20, 2, 0, 5),
        ("13102", "Comuna B", 2021, 1, "2021-01-04", 50, 0, 0, 2),
        ("13102", "Comuna B", 2021, 2, "2021-01-11", 60, 5, 0, 2),
        ("13102", "Comuna B", 2021, 3, "2021-01-18", 70, 6, 1, 2),
        ("13102", "Comuna B", 2021, 53, "2021-01-01", 10, 1, 0, 2),
    ]
    frame = pd.DataFrame(
        filas,
        columns=[
            "comuna_codigo", "comuna_glosa", "ano", "semana", "fecha_inicio_semana",
            "atenciones_id1", TARGET, "atenciones_id37",
            "n_establecimientos_reportantes_id36",
        ],
    )
    frame["fecha_inicio_semana"] = pd.to_datetime(frame["fecha_inicio_semana"])
    return frame


class TestCalendario:
    def test_audit_calendar_marca_semana_53(self):
        cal = audit_calendar(_weekly_fixture())
        fragmentos = cal[cal["es_semana_53"]]
        assert len(fragmentos) == 1
        assert int(fragmentos.iloc[0]["semana"]) == SEASONAL_PERIOD + 1
        # Agrega las dos comunas: 2 + 1 atenciones.
        assert int(fragmentos.iloc[0]["atenciones"]) == 3

    def test_build_rm_series_excluye_semana_53_por_defecto(self):
        serie = build_rm_series(_weekly_fixture())
        assert len(serie) == 3
        assert (SEASONAL_PERIOD + 1) not in [s for _, s in serie.index]
        # Semana 1: 10 (A) + 0 (B).
        assert serie.loc[(2021, 1)] == 10

    def test_build_rm_series_puede_conservar_semana_53(self):
        serie = build_rm_series(_weekly_fixture(), drop_week_53=False)
        assert len(serie) == 4

    def test_build_comuna_matrix_excluye_fragmentos(self):
        matriz = build_comuna_matrix(_weekly_fixture())
        assert matriz.shape == (2, 3)
        assert list(matriz.index) == ["13101", "13102"]


class TestDiagnosticos:
    def test_stationarity_tests_cubre_nivel_y_diferencia(self):
        rng = np.random.RandomState(42)
        serie = pd.Series(np.cumsum(rng.normal(size=120)))
        est = stationarity_tests(serie)
        assert list(est["serie"]) == ["nivel", "primera_diferencia"]
        # Una caminata aleatoria tiene raiz unitaria en nivel, no en su diferencia.
        assert not bool(est.loc[0, "adf_rechaza_raiz_unitaria"])
        assert bool(est.loc[1, "adf_rechaza_raiz_unitaria"])

    def test_stationarity_tests_declara_p_truncado(self):
        # Caminata aleatoria con deriva: el estadistico KPSS cae fuera de la
        # tabla de referencia, asi que el p-valor devuelto esta truncado y el
        # informe debe poder declararlo.
        rng = np.random.RandomState(1)
        est = stationarity_tests(pd.Series(np.cumsum(rng.normal(loc=1.0, size=150))))
        assert est["kpss_p_truncado_en_tabla"].dtype == bool
        assert bool(est.loc[0, "kpss_p_truncado_en_tabla"])

    def test_autocorrelation_profile_rezago_cero_es_uno(self):
        rng = np.random.RandomState(7)
        perfil = autocorrelation_profile(pd.Series(rng.normal(size=200)), nlags=10)
        assert perfil.loc[0, "acf"] == pytest.approx(1.0)
        assert len(perfil) == 11
        # Banda de Bartlett para n=200.
        assert perfil.loc[0, "banda_significancia"] == pytest.approx(
            1.96 / np.sqrt(200), abs=1e-4
        )


class TestBaseline:
    def test_naive_estacional_es_exacto_en_serie_periodica(self):
        # Serie perfectamente periodica: el baseline no debe cometer error.
        serie = pd.Series(list(range(1, 5)) * 10, dtype=float)
        resultado = seasonal_naive_backtest(serie, period=4, horizons=(1, 2))
        assert (resultado["mae"] == 0).all()
        assert (resultado["mape_pct"] == 0).all()

    def test_naive_estacional_no_usa_informacion_futura(self):
        # Alterar el ultimo valor no puede cambiar el pronostico de periodos previos.
        base = pd.Series(list(range(1, 5)) * 10, dtype=float)
        alterada = base.copy()
        alterada.iloc[-1] = 999.0
        r_base = seasonal_naive_backtest(base, period=4, horizons=(1,))
        r_alt = seasonal_naive_backtest(alterada, period=4, horizons=(1,))
        # Solo el ultimo punto evaluado cambia; el conteo de evaluaciones no.
        assert int(r_base.loc[0, "n_evaluaciones"]) == int(r_alt.loc[0, "n_evaluaciones"])
        assert r_alt.loc[0, "mae"] > r_base.loc[0, "mae"]

    def test_naive_por_comuna_excluye_ceros_del_mape(self):
        # Los ceros deben estar en el tramo evaluado (segunda mitad), que es
        # donde el MAPE quedaria indefinido.
        matriz = pd.DataFrame(
            [[2.0, 4.0, 2.0, 4.0, 0.0, 2.0, 0.0, 2.0]],
            index=["13101"],
        )
        resultado = seasonal_naive_by_comuna(matriz, period=4)
        assert int(resultado.loc[0, "puntos_excluidos_por_cero"]) == 2
        assert np.isfinite(resultado.loc[0, "mape_pct"])


class TestHeterogeneidad:
    def test_shares_suman_uno_y_cuenta_ceros(self):
        perfil = comuna_heterogeneity(_weekly_fixture())
        assert perfil["share_demanda_rm"].sum() == pytest.approx(1.0, abs=1e-3)
        # Comuna B tiene una semana regular con 0 atenciones ID36.
        fila_b = perfil[perfil["comuna_codigo"] == "13102"].iloc[0]
        assert int(fila_b["semanas_en_cero"]) == 1

    def test_ordena_por_volumen_descendente(self):
        perfil = comuna_heterogeneity(_weekly_fixture())
        assert perfil["total"].is_monotonic_decreasing


class TestRender:
    def test_tabla_md_genera_encabezado_y_filas(self):
        tabla = _tabla_md(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}))
        lineas = tabla.splitlines()
        assert lineas[0] == "| a | b |"
        assert lineas[1] == "|---|---|"
        assert len(lineas) == 4

    def test_tabla_md_representa_nulos_como_vacio(self):
        tabla = _tabla_md(pd.DataFrame({"a": [None]}))
        assert tabla.splitlines()[2] == "|  |"


class TestRegistroEnPipeline:
    def test_stage_registrado_con_dependencia_correcta(self):
        stage = pipeline.STAGES["eda_series_demanda_sm"]
        assert stage["module"] == "scripts.eda_series_demanda_sm"
        assert stage["depends_on"] == ["build_urgencias_comuna_marts"]
        assert stage["outputs"] == [
            "reports/eda/eda_series_demanda_sm.md",
            "reports/eda/eda_series_demanda_sm_resumen.csv",
        ]

    def test_stage_corre_despues_de_su_upstream(self):
        orden = pipeline.PIPELINE_ORDER
        assert "eda_series_demanda_sm" in orden
        assert orden.index("build_urgencias_comuna_marts") < orden.index(
            "eda_series_demanda_sm"
        )
