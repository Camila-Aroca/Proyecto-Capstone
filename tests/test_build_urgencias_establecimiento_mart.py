"""Pruebas dirigidas para el mart mensual de Urgencias por establecimiento."""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_urgencias_establecimiento_mart import (
    build_establecimiento_monthly_mart,
    validate_mart,
    validate_reconciliation_with_comuna_monthly,
)


def _source_fixture() -> pd.DataFrame:
    rows: list[tuple[object, ...]] = []
    # Fechas ISO (YYYY-MM-DD) para evitar la ambigüedad DD/MM vs MM/DD de
    # `pd.to_datetime` sin `dayfirst` explícito: dos fechas en enero, una en
    # febrero.
    dates = ["2021-01-01", "2021-01-03", "2021-02-01"]
    # Establecimiento 10 (Santiago, Hospital) y 11 (Ñuñoa, SAPU); cada uno
    # reporta siempre la misma comuna/glosa/tipo (regla determinista).
    establishments = {
        10: {"comuna_codigo": "13101", "comuna_glosa": "Santiago", "glosa": "Hospital X", "tipo": "Hospital"},
        11: {"comuna_codigo": "13120", "comuna_glosa": "Ñuñoa", "glosa": "SAPU Y", "tipo": "SAPU"},
    }
    values = {
        1: {10: 10, 11: 5},
        35: {10: 0, 11: 1},
        36: {10: 2, 11: 0},
        37: {10: 0, 11: 0},
        38: {10: 1, 11: 0},
        39: {10: 1, 11: 0},
        40: {10: 0, 11: 0},
        41: {10: 0, 11: 0},
    }
    for date in dates:
        for cause, by_establishment in values.items():
            for establishment, total in by_establishment.items():
                meta = establishments[establishment]
                rows.append(
                    (
                        2021, date, meta["comuna_codigo"], meta["comuna_glosa"],
                        establishment, meta["glosa"], meta["tipo"], cause, total,
                    )
                )
    return pd.DataFrame(
        rows,
        columns=[
            "ano", "fecha", "comuna_codigo", "comuna_glosa",
            "establecimiento_codigo", "establecimiento_glosa",
            "tipo_establecimiento_urgencia", "id_causa", "total",
        ],
    )


def _comuna_monthly_reference(mart: pd.DataFrame) -> pd.DataFrame:
    from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS

    columns = list(COUNT_COLUMNS)
    return mart.groupby(["comuna_codigo", "fecha_mes"], as_index=False)[columns].sum(min_count=1)


def test_grain_is_establecimiento_by_month_and_carries_stable_attributes() -> None:
    mart = build_establecimiento_monthly_mart(_source_fixture())
    validate_mart(mart)

    assert len(mart) == 4  # 2 establecimientos x 2 meses
    assert not mart.duplicated(["establecimiento_codigo", "fecha_mes"]).any()
    hospital_jan = mart.loc[
        (mart["establecimiento_codigo"] == 10) & (mart["fecha_mes"] == "2021-01-01")
    ].iloc[0]
    assert hospital_jan["comuna_codigo"] == "13101"
    assert hospital_jan["establecimiento_glosa"] == "Hospital X"
    assert hospital_jan["tipo_establecimiento_urgencia"] == "Hospital"
    assert hospital_jan["atenciones_id1"] == 20
    assert hospital_jan["atenciones_id36"] == 4
    assert hospital_jan["proporcion_id38_sobre_id36"] == pytest.approx(1 / 2)


def test_mart_does_not_invent_population_or_reporter_columns() -> None:
    mart = build_establecimiento_monthly_mart(_source_fixture())
    forbidden = {
        "poblacion_anual", "tasa_atenciones_id1_por_10000",
        "n_establecimientos_reportantes_id1", "n_establecimientos_reportantes_id36",
    }
    assert forbidden.isdisjoint(mart.columns)


def test_validation_rejects_broken_id36_hierarchy() -> None:
    mart = build_establecimiento_monthly_mart(_source_fixture())
    mart.loc[mart.index[0], "atenciones_id41"] = 99
    with pytest.raises(ValueError, match="ID36 no reconcilia"):
        validate_mart(mart)


def test_validation_rejects_duplicated_grain() -> None:
    mart = build_establecimiento_monthly_mart(_source_fixture())
    duplicated = pd.concat([mart, mart.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="no único"):
        validate_mart(duplicated)


def test_reconciliation_passes_against_matching_comuna_monthly() -> None:
    mart = build_establecimiento_monthly_mart(_source_fixture())
    reference = _comuna_monthly_reference(mart)
    validate_reconciliation_with_comuna_monthly(mart, reference)


def test_reconciliation_rejects_mismatch_against_comuna_monthly() -> None:
    mart = build_establecimiento_monthly_mart(_source_fixture())
    reference = _comuna_monthly_reference(mart)
    reference.loc[reference.index[0], "atenciones_id1"] += 1
    with pytest.raises(ValueError, match="No reconcilia establecimiento→comuna"):
        validate_reconciliation_with_comuna_monthly(mart, reference)


def test_stage_is_registered_after_clean_urgencias_and_comuna_marts() -> None:
    assert pipeline.STAGES["build_urgencias_establecimiento_mart"]["depends_on"] == [
        "clean_urgencias", "build_urgencias_comuna_marts"
    ]
    assert "build_urgencias_establecimiento_mart" in pipeline.PIPELINE_ORDER
    assert (
        pipeline.PIPELINE_ORDER.index("build_urgencias_comuna_marts")
        < pipeline.PIPELINE_ORDER.index("build_urgencias_establecimiento_mart")
    )
