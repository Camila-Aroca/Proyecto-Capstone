"""Pruebas dirigidas para el mart semanal de Urgencias por establecimiento."""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS
from src.data.build_urgencias_establecimiento_weekly_mart import (
    HOSPITALIZACION_COLUMN,
    WEEKLY_COUNT_COLUMNS,
    build_establecimiento_weekly_mart,
    validate_mart,
    validate_reconciliation_with_comuna_weekly,
)

ESTABLECIMIENTOS = {
    10: {"comuna_codigo": "13101", "comuna_glosa": "Santiago", "glosa": "Hospital X", "tipo": "Hospital"},
    11: {"comuna_codigo": "13101", "comuna_glosa": "Santiago", "glosa": "SAPU Y", "tipo": "SAPU"},
    12: {"comuna_codigo": "13120", "comuna_glosa": "Ñuñoa", "glosa": "SAR Z", "tipo": "SAR"},
}
# Valores diarios por causa y establecimiento; ID36 = ID37 + ... + ID41.
VALORES = {
    1: {10: 10, 11: 5, 12: 7},
    35: {10: 0, 11: 1, 12: 0},
    36: {10: 2, 11: 1, 12: 0},
    37: {10: 0, 11: 0, 12: 0},
    38: {10: 1, 11: 0, 12: 0},
    39: {10: 1, 11: 1, 12: 0},
    40: {10: 0, 11: 0, 12: 0},
    41: {10: 0, 11: 0, 12: 0},
    42: {10: 1, 11: 0, 12: 0},
}


def _origen(sin_reporte: tuple[int, int] | None = None) -> pd.DataFrame:
    """Dos semanas DEIS de 2021 con dos días cada una.

    `sin_reporte` = (establecimiento, semana) omite todas sus filas esa semana,
    como ocurre cuando un establecimiento no reporta.
    """
    filas = []
    for semana, fechas in ((1, ("2021-01-03", "2021-01-04")), (2, ("2021-01-10", "2021-01-11"))):
        for fecha in fechas:
            for causa, por_estab in VALORES.items():
                for estab, total in por_estab.items():
                    if sin_reporte == (estab, semana):
                        continue
                    meta = ESTABLECIMIENTOS[estab]
                    filas.append({
                        "ano": 2021, "semana": semana, "fecha": fecha,
                        "comuna_codigo": meta["comuna_codigo"], "comuna_glosa": meta["comuna_glosa"],
                        "establecimiento_codigo": estab, "establecimiento_glosa": meta["glosa"],
                        "tipo_establecimiento_urgencia": meta["tipo"],
                        "id_causa": causa, "total": total,
                    })
    return pd.DataFrame(filas)


def _comuna_semanal(mart: pd.DataFrame) -> pd.DataFrame:
    return mart.groupby(["comuna_codigo", "ano", "semana"], as_index=False)[list(COUNT_COLUMNS)].sum()


def test_agrega_a_establecimiento_por_semana_con_id42() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    assert len(mart) == 6  # 3 establecimientos x 2 semanas
    fila = mart[(mart["establecimiento_codigo"] == 10) & (mart["semana"] == 1)].iloc[0]
    assert fila["atenciones_id36"] == 4 and fila[HOSPITALIZACION_COLUMN] == 2
    assert fila["fecha_inicio_semana"] == "2021-01-03"
    assert set(WEEKLY_COUNT_COLUMNS) <= set(mart.columns)
    validate_mart(mart)


def test_un_cero_publicado_se_conserva_como_cero() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    sapu = mart[mart["establecimiento_codigo"] == 11]
    assert (sapu[HOSPITALIZACION_COLUMN] == 0).all()


def test_una_semana_sin_reporte_no_se_rellena() -> None:
    mart = build_establecimiento_weekly_mart(_origen(sin_reporte=(12, 2)))
    assert len(mart) == 5
    assert mart[(mart["establecimiento_codigo"] == 12) & (mart["semana"] == 2)].empty


def test_no_inventa_poblacion_ni_reportantes() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    assert "poblacion_anual" not in mart.columns
    assert not any(c.startswith("n_establecimientos_reportantes") for c in mart.columns)


def test_rechaza_causas_fuera_del_contrato() -> None:
    origen = _origen()
    origen.loc[0, "id_causa"] = 2
    with pytest.raises(ValueError, match="fuera del contrato"):
        build_establecimiento_weekly_mart(origen)


def test_valida_jerarquia_de_salud_mental() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    mart.loc[0, "atenciones_id36"] = 99
    with pytest.raises(ValueError):
        validate_mart(mart)


def test_rechaza_grano_duplicado() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    with pytest.raises(ValueError, match="no único"):
        validate_mart(pd.concat([mart, mart.iloc[[0]]], ignore_index=True))


def test_reconcilia_con_el_mart_comunal_semanal() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    validate_reconciliation_with_comuna_weekly(mart, _comuna_semanal(mart))


def test_detecta_diferencias_con_el_mart_comunal() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    referencia = _comuna_semanal(mart)
    referencia.loc[0, "atenciones_id36"] += 1
    with pytest.raises(ValueError, match="atenciones_id36"):
        validate_reconciliation_with_comuna_weekly(mart, referencia)


def test_detecta_universos_distintos() -> None:
    mart = build_establecimiento_weekly_mart(_origen())
    referencia = _comuna_semanal(mart).iloc[1:]
    with pytest.raises(ValueError, match="universo"):
        validate_reconciliation_with_comuna_weekly(mart, referencia)


def test_stage_registrado_despues_de_limpieza_y_mart_comunal() -> None:
    stage = pipeline.STAGES["build_urgencias_establecimiento_weekly_mart"]
    assert stage["depends_on"] == ["clean_urgencias", "build_urgencias_comuna_marts"]
    orden = pipeline.PIPELINE_ORDER
    posicion = orden.index("build_urgencias_establecimiento_weekly_mart")
    assert orden.index("build_urgencias_comuna_marts") < posicion
