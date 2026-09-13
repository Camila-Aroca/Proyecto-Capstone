"""Pruebas dirigidas para los marts comunales históricos de Urgencias."""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_urgencias_comuna_marts import (
    build_monthly_mart,
    build_weekly_mart,
    validate_mart,
    validate_reconciliation,
)


def _poblacion_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "comuna_codigo": ["13101", "13101"],
            "ano": [2021, 2022],
            "poblacion_anual": [500_000, 510_000],
        }
    )


def _source_fixture() -> pd.DataFrame:
    rows: list[tuple[object, ...]] = []
    dates = [("01/01/2021", 1), ("03/01/2021", 1), ("01/02/2021", 5)]
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
    for date, week in dates:
        for cause, by_establishment in values.items():
            for establishment, total in by_establishment.items():
                rows.append(
                    (2021, week, date, "13101", "Santiago", establishment, cause, total)
                )
    return pd.DataFrame(
        rows,
        columns=[
            "ano", "semana", "fecha", "comuna_codigo", "comuna_glosa",
            "establecimiento_codigo", "id_causa", "total",
        ],
    )


def test_weekly_grain_hierarchy_ratios_and_reporters() -> None:
    weekly = build_weekly_mart(_source_fixture(), _poblacion_fixture())
    validate_mart(weekly, "weekly")

    assert len(weekly) == 2
    assert not weekly.duplicated(["comuna_codigo", "fecha_inicio_semana"]).any()
    first = weekly.loc[weekly["semana"] == 1].iloc[0]
    assert first["fecha_inicio_semana"] == "2021-01-01"
    assert first["atenciones_id36"] == 4
    assert first["atenciones_id37"] + first["atenciones_id38"] + first["atenciones_id39"] + first["atenciones_id40"] + first["atenciones_id41"] == 4
    assert first["proporcion_id36_sobre_id1"] == pytest.approx(4 / 30)
    assert first["proporcion_id38_sobre_id36"] == pytest.approx(1 / 2)
    assert first["n_establecimientos_reportantes_id1"] == 2
    assert first["n_establecimientos_reportantes_id36"] == 2
    assert first["poblacion_anual"] == 500_000
    assert first["tasa_atenciones_id1_por_10000"] == pytest.approx(30 / 500_000 * 10_000)
    assert first["tasa_atenciones_id36_por_10000"] == pytest.approx(4 / 500_000 * 10_000)


def test_monthly_reconciles_exactly_with_weekly_counts() -> None:
    source = _source_fixture()
    poblacion = _poblacion_fixture()
    weekly = build_weekly_mart(source, poblacion)
    monthly = build_monthly_mart(source, poblacion)
    validate_mart(monthly, "monthly")
    validate_reconciliation(weekly, monthly)

    assert len(monthly) == 2
    january = monthly.loc[monthly["mes"] == 1].iloc[0]
    assert january["fecha_mes"] == "2021-01-01"
    assert january["atenciones_id1"] == 30
    assert january["atenciones_id36"] == 4
    assert january["poblacion_anual"] == 500_000


def test_monthly_reuses_same_annual_population_across_months() -> None:
    source = _source_fixture()
    monthly = build_monthly_mart(source, _poblacion_fixture())
    assert monthly["ano"].eq(2021).all()
    assert monthly["poblacion_anual"].nunique() == 1
    assert monthly["poblacion_anual"].iloc[0] == 500_000


def test_validation_rejects_broken_id36_hierarchy() -> None:
    weekly = build_weekly_mart(_source_fixture(), _poblacion_fixture())
    weekly.loc[weekly.index[0], "atenciones_id41"] = 99
    with pytest.raises(ValueError, match="ID36 no reconcilia"):
        validate_mart(weekly, "weekly")


def test_absent_cause_is_not_silently_imputed_as_zero() -> None:
    source = _source_fixture().query("id_causa != 35")
    weekly = build_weekly_mart(source, _poblacion_fixture())

    assert weekly["atenciones_id35"].isna().all()
    assert weekly["tasa_atenciones_id35_por_10000"].isna().all()


def test_missing_poblacion_denominator_is_rejected() -> None:
    source = _source_fixture()
    poblacion_incompleta = _poblacion_fixture().iloc[[1]]
    with pytest.raises(ValueError, match="Sin denominador poblacional"):
        build_weekly_mart(source, poblacion_incompleta)


def test_mart_stage_is_registered_after_clean_urgencias_and_poblacion() -> None:
    assert pipeline.STAGES["build_urgencias_comuna_marts"]["depends_on"] == [
        "clean_urgencias", "clean_poblacion_proyecciones"
    ]
    assert "build_urgencias_comuna_marts" in pipeline.PIPELINE_ORDER
