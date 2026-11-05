"""Pruebas del panel por establecimiento y de su benchmark.

Usan un mart sintético: no dependen de `data/processed/` ni de los reports.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from scripts.run_benchmark_establecimientos import REFERENCIA, select_model
from src.models.backtesting import prepare_supervised
from src.models.establecimientos import (
    NIVEL_ESTABLECIMIENTO,
    OBJETIVOS,
    build_establishment_panel,
    fixed_universe,
    select_universe,
)
from src.models.features import RM_SERIES_ID, SEASONAL_PERIOD, build_supervised_frame, feature_columns
from src.models.hierarchy import reconcile_bottom_up, reconcile_top_down

ESTABLECIMIENTOS = {
    1: ("Hospital A", "Hospital", 20),
    2: ("Hospital B", "Hospital", 8),
    3: ("SAPU C", "SAPU", 6),
    4: ("SAR D", "SAR", 0),   # volumen nulo en salud mental
}


def _mart(anos=(2021, 2022, 2023), sin_reporte: tuple[int, int, int] | None = None) -> pd.DataFrame:
    """Mart semanal sintético. `sin_reporte` = (establecimiento, ano, semana) omite esa fila."""
    rng = np.random.RandomState(0)
    filas = []
    for codigo, (glosa, tipo, nivel) in ESTABLECIMIENTOS.items():
        for ano in anos:
            for semana in range(1, SEASONAL_PERIOD + 2):  # incluye la semana 53
                if sin_reporte == (codigo, ano, semana):
                    continue
                id36 = int(max(0, nivel + rng.normal(0, 1))) if nivel else 0
                filas.append({
                    "establecimiento_codigo": codigo, "ano": ano, "semana": semana,
                    "comuna_codigo": "13101", "comuna_glosa": "Santiago",
                    "establecimiento_glosa": glosa, "tipo_establecimiento_urgencia": tipo,
                    "atenciones_id1": id36 * 10 + 5, "atenciones_id36": id36,
                    "atenciones_id42": id36 // 4 if tipo == "Hospital" else 0,
                })
    return pd.DataFrame(filas)


class TestUniverso:
    def test_atenciones_excluye_por_volumen(self):
        universo = select_universe(_mart(), OBJETIVOS["atenciones_sm"], ano_inicio=2022)
        motivos = universo.set_index("establecimiento_codigo")["motivo_exclusion"]
        assert motivos[4].startswith("volumen medio menor")
        assert universo.set_index("establecimiento_codigo")["incluido"].loc[[1, 2, 3]].all()

    def test_hospitalizaciones_solo_hospitales(self):
        universo = select_universe(_mart(), OBJETIVOS["hospitalizaciones_sm"], ano_inicio=2022)
        fila = universo.set_index("establecimiento_codigo")
        assert fila.loc[3, "motivo_exclusion"] == "no es hospital"
        assert fila.loc[1, "incluido"]

    def test_una_semana_sin_reporte_excluye_sin_imputar(self):
        universo = select_universe(
            _mart(sin_reporte=(2, 2022, 10)), OBJETIVOS["atenciones_sm"], ano_inicio=2022
        )
        fila = universo.set_index("establecimiento_codigo").loc[2]
        assert fila["motivo_exclusion"] == "semanas sin reporte en la ventana"

    def test_una_ausencia_antes_de_la_ventana_no_excluye(self):
        universo = select_universe(
            _mart(sin_reporte=(2, 2021, 10)), OBJETIVOS["atenciones_sm"], ano_inicio=2022
        )
        assert universo.set_index("establecimiento_codigo").loc[2, "incluido"]

    def test_la_semana_53_no_cuenta_como_semana_de_la_ventana(self):
        universo = select_universe(_mart(), OBJETIVOS["atenciones_sm"], ano_inicio=2022)
        assert (universo["semanas_ventana"] == 2 * SEASONAL_PERIOD).all()


class TestPanel:
    def test_total_es_la_suma_de_los_establecimientos_incluidos(self):
        mart, objetivo = _mart(), OBJETIVOS["atenciones_sm"]
        panel = build_establishment_panel(mart, objetivo, select_universe(mart, objetivo, 2022), 2022)
        total = panel[panel["series_id"] == RM_SERIES_ID].set_index("t")["y"]
        hojas = panel[panel["nivel"] == NIVEL_ESTABLECIMIENTO].groupby("t")["y"].sum()
        pd.testing.assert_series_equal(total, hojas, check_names=False, check_dtype=False)
        assert set(panel["series_id"]) == {"1", "2", "3", RM_SERIES_ID}

    def test_grilla_regular_sin_semana_53(self):
        mart, objetivo = _mart(), OBJETIVOS["atenciones_sm"]
        panel = build_establishment_panel(mart, objetivo, select_universe(mart, objetivo, 2022), 2022)
        assert (panel["semana"] <= SEASONAL_PERIOD).all()
        assert panel.groupby("series_id")["t"].size().nunique() == 1

    def test_sin_establecimientos_falla(self):
        mart, objetivo = _mart(), OBJETIVOS["atenciones_sm"]
        universo = select_universe(mart, objetivo, 2022).assign(incluido=False)
        with pytest.raises(ValueError, match="Ningún establecimiento"):
            build_establishment_panel(mart, objetivo, universo, 2022)

    def test_las_covariables_solo_entran_rezagadas(self):
        mart, objetivo = _mart(), OBJETIVOS["hospitalizaciones_sm"]
        panel = build_establishment_panel(mart, objetivo, select_universe(mart, objetivo, 2022), 2022)
        frame = build_supervised_frame(panel, 4, exogenous=objetivo.exogenas)
        columnas = feature_columns(frame)
        assert "atenciones_id36_lag_4" in columnas and "atenciones_id36" not in frame.columns
        # Ni población (no existe para un establecimiento) ni atributos descriptivos.
        assert "log_poblacion" not in columnas
        assert not {"comuna_codigo", "establecimiento_glosa", "tipo_establecimiento_urgencia"} & set(columnas)
        serie = frame[frame["series_id"] == "1"].set_index("t")
        original = panel[panel["series_id"] == "1"].set_index("t")["atenciones_id36"]
        assert serie.loc[80, "atenciones_id36_lag_4"] == original[76]

    def test_prepare_supervised_acepta_otras_covariables(self):
        mart, objetivo = _mart(), OBJETIVOS["hospitalizaciones_sm"]
        panel = build_establishment_panel(mart, objetivo, select_universe(mart, objetivo, 2022), 2022)
        matrices = prepare_supervised(panel, (4,), exogenous=objetivo.exogenas)
        assert "atenciones_id36_lag_4" in matrices[4].columns


class TestJerarquiaConEstablecimientos:
    @staticmethod
    def _predicciones() -> pd.DataFrame:
        return pd.DataFrame({
            "series_id": [RM_SERIES_ID, "1", "2"],
            "nivel": ["region", NIVEL_ESTABLECIMIENTO, NIVEL_ESTABLECIMIENTO],
            "origen": [10] * 3, "horizonte": [4] * 3,
            "y_pred": [30.0, 10.0, 10.0], "y_inferior": [25.0, 8.0, 8.0], "y_superior": [35.0, 12.0, 12.0],
        })

    def test_bottom_up_suma_establecimientos(self):
        total = reconcile_bottom_up(self._predicciones()).set_index("series_id").loc[RM_SERIES_ID, "y_pred"]
        assert total == pytest.approx(20.0)

    def test_top_down_reparte_el_total(self):
        resultado = reconcile_top_down(self._predicciones()).set_index("series_id")["y_pred"]
        assert resultado["1"] == pytest.approx(15.0) and resultado["2"] == pytest.approx(15.0)


class TestSeleccion:
    @staticmethod
    def _tabla(filas):
        columnas = ["modelo", "mase_promedio", "calibrado_region", f"calibrado_{NIVEL_ESTABLECIMIENTO}"]
        return pd.DataFrame(filas, columns=columnas)

    def test_prefiere_el_calibrado_que_supera_al_baseline(self):
        tabla = self._tabla([
            (REFERENCIA, 0.9, True, True),
            ("preciso_no_calibrado", 0.6, False, True),
            ("calibrado", 0.7, True, True),
        ])
        assert select_model(tabla)[0] == "calibrado"

    def test_sin_calibrados_elige_el_mas_preciso_y_lo_declara(self):
        tabla = self._tabla([(REFERENCIA, 0.9, True, True), ("a", 0.6, False, False), ("b", 0.7, True, False)])
        elegido, criterio = select_model(tabla)
        assert elegido == "a" and "orientativos" in criterio

    def test_si_nadie_supera_al_baseline_queda_el_baseline(self):
        tabla = self._tabla([(REFERENCIA, 0.9, True, True), ("a", 1.1, True, True)])
        assert select_model(tabla)[0] == REFERENCIA


def test_stage_registrado_despues_del_mart_semanal():
    stage = pipeline.STAGES["benchmark_establecimientos_sm"]
    assert stage["depends_on"] == ["build_urgencias_establecimiento_weekly_mart"]
    orden = pipeline.PIPELINE_ORDER
    assert orden.index("build_urgencias_establecimiento_weekly_mart") < orden.index("benchmark_establecimientos_sm")


class TestUniversoFijo:
    """El año en curso restringe el universo; nunca rellena semanas faltantes."""

    @staticmethod
    def _actual(sin_semanas: dict[int, set[int]] | None = None) -> pd.DataFrame:
        filas = []
        for codigo, (glosa, tipo, nivel) in ESTABLECIMIENTOS.items():
            for semana in range(1, 11):
                if semana in (sin_semanas or {}).get(codigo, set()):
                    continue
                filas.append({
                    "establecimiento_codigo": codigo, "ano": 2024, "semana": semana,
                    "establecimiento_glosa": glosa, "tipo_establecimiento_urgencia": tipo,
                    "fecha_inicio_semana": f"2024-{semana:02d}", "atenciones_id36": nivel,
                    "atenciones_id42": nivel // 4,
                })
        return pd.DataFrame(filas)

    def test_quien_deja_de_reportar_sale_del_universo(self):
        universo = select_universe(_mart(), OBJETIVOS["atenciones_sm"], ano_inicio=2022)
        final, excluidos = fixed_universe(
            universo, self._actual({3: {9, 10}}), OBJETIVOS["atenciones_sm"], max_excluida_pct=100
        )
        assert excluidos["establecimiento_codigo"].tolist() == [3]
        assert excluidos.iloc[0]["semanas_reportadas"] == 8
        assert not final.set_index("establecimiento_codigo").loc[3, "incluido"]

    def test_falla_si_lo_excluido_pesa_demasiado(self):
        universo = select_universe(_mart(), OBJETIVOS["atenciones_sm"], ano_inicio=2022)
        with pytest.raises(ValueError, match="sobre el máximo"):
            fixed_universe(universo, self._actual({1: {10}}), OBJETIVOS["atenciones_sm"], max_excluida_pct=5)

    def test_sin_ausencias_el_universo_no_cambia(self):
        universo = select_universe(_mart(), OBJETIVOS["atenciones_sm"], ano_inicio=2022)
        final, excluidos = fixed_universe(universo, self._actual(), OBJETIVOS["atenciones_sm"])
        assert excluidos.empty
        pd.testing.assert_series_equal(final["incluido"], universo["incluido"])


def test_holdout_registrado_despues_del_benchmark():
    stage = pipeline.STAGES["evaluate_holdout_establecimientos_sm"]
    assert stage["depends_on"] == ["benchmark_establecimientos_sm", "clean_urgencias"]
    orden = pipeline.PIPELINE_ORDER
    assert orden.index("benchmark_establecimientos_sm") < orden.index("evaluate_holdout_establecimientos_sm")
