"""Pruebas dirigidas para el mart mensual comunal de Urgencias con desglose etario."""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_urgencias_comuna_etario_mart import (
    AGE_GROUPS,
    build_comuna_etario_monthly_mart,
    validate_mart,
    validate_reconciliation_with_comuna_monthly,
)


def _source_fixture() -> pd.DataFrame:
    # Valores por grupo etario en el orden de AGE_GROUPS:
    # (menores_1, de_1_a_4, de_5_a_14, de_15_a_64, de_65_y_mas)
    # Construidos para que, por fila, ID36 = ID37+ID38+ID39+ID40+ID41
    # exactamente por grupo etario (identidad DEIS verificada en el EDA real).
    # Fechas en formato ISO (YYYY-MM-DD) para evitar la ambigüedad DD/MM vs
    # MM/DD de `pd.to_datetime` sin `dayfirst` explícito.
    records = [
        # (fecha, id_causa, valores_por_grupo)
        ("2021-01-01", 1, (5, 5, 5, 15, 5)),
        ("2021-01-01", 35, (0, 0, 0, 1, 0)),
        ("2021-01-01", 36, (0, 1, 1, 2, 1)),
        ("2021-01-01", 37, (0, 0, 0, 1, 0)),
        ("2021-01-01", 38, (0, 1, 0, 0, 0)),
        ("2021-01-01", 39, (0, 0, 1, 0, 0)),
        ("2021-01-01", 40, (0, 0, 0, 1, 0)),
        ("2021-01-01", 41, (0, 0, 0, 0, 1)),
        ("2021-01-03", 1, (4, 4, 4, 10, 4)),
        ("2021-01-03", 35, (0, 0, 0, 0, 0)),
        ("2021-01-03", 36, (0, 0, 2, 2, 1)),
        ("2021-01-03", 37, (0, 0, 0, 2, 0)),
        ("2021-01-03", 38, (0, 0, 0, 0, 0)),
        ("2021-01-03", 39, (0, 0, 2, 0, 0)),
        ("2021-01-03", 40, (0, 0, 0, 0, 0)),
        ("2021-01-03", 41, (0, 0, 0, 0, 1)),
        ("2021-02-01", 1, (2, 2, 2, 8, 2)),
        ("2021-02-01", 35, (0, 0, 0, 0, 0)),
        ("2021-02-01", 36, (1, 0, 0, 3, 0)),
        ("2021-02-01", 37, (1, 0, 0, 0, 0)),
        ("2021-02-01", 38, (0, 0, 0, 0, 0)),
        ("2021-02-01", 39, (0, 0, 0, 0, 0)),
        ("2021-02-01", 40, (0, 0, 0, 3, 0)),
        ("2021-02-01", 41, (0, 0, 0, 0, 0)),
    ]
    rows = []
    for fecha, id_causa, values in records:
        rows.append((2021, fecha, "13101", "Santiago", id_causa, *values))
    return pd.DataFrame(
        rows,
        columns=["ano", "fecha", "comuna_codigo", "comuna_glosa", "id_causa", *AGE_GROUPS],
    )


def _comuna_monthly_reference(mart: pd.DataFrame) -> pd.DataFrame:
    from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS

    columns = list(COUNT_COLUMNS)
    return mart.groupby(["comuna_codigo", "fecha_mes"], as_index=False)[columns].sum(min_count=1)


def test_grain_is_comuna_by_month_by_age_group() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    validate_mart(mart)

    assert len(mart) == 2 * len(AGE_GROUPS)  # 2 meses x 5 grupos etarios
    assert not mart.duplicated(["comuna_codigo", "fecha_mes", "grupo_etario_urgencia"]).any()
    january_65 = mart.loc[
        (mart["fecha_mes"] == "2021-01-01") & (mart["grupo_etario_urgencia"] == "de_65_y_mas")
    ].iloc[0]
    assert january_65["atenciones_id1"] == 9  # 5 + 4
    assert january_65["atenciones_id36"] == 2  # 1 + 1
    assert january_65["atenciones_id41"] == 2  # 1 + 1

    january_64 = mart.loc[
        (mart["fecha_mes"] == "2021-01-01") & (mart["grupo_etario_urgencia"] == "de_15_a_64")
    ].iloc[0]
    assert january_64["atenciones_id36"] == 4  # 2 + 2
    assert january_64["atenciones_id37"] == 3  # 1 + 2
    assert january_64["atenciones_id40"] == 1  # 1 + 0


def test_mart_does_not_include_total_sexo_or_reporter_columns() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    forbidden = {
        "total", "sexo", "genero",
        "n_establecimientos_reportantes_id1", "n_establecimientos_reportantes_id36",
        "poblacion_anual",
    }
    assert forbidden.isdisjoint(mart.columns)


def test_validation_rejects_unexpected_age_group_value() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    mart.loc[mart.index[0], "grupo_etario_urgencia"] = "grupo_inventado"
    with pytest.raises(ValueError, match="fuera del contrato"):
        validate_mart(mart)


def test_validation_rejects_duplicated_grain() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    duplicated = pd.concat([mart, mart.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="no único"):
        validate_mart(duplicated)


def test_validation_rejects_broken_id36_hierarchy() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    mart.loc[mart.index[0], "atenciones_id41"] = 99
    with pytest.raises(ValueError, match="ID36 no reconcilia"):
        validate_mart(mart)


def test_age_groups_reconcile_with_comuna_monthly_totals() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    reference = _comuna_monthly_reference(mart)
    validate_reconciliation_with_comuna_monthly(mart, reference)


def test_reconciliation_rejects_mismatch_against_comuna_monthly() -> None:
    mart = build_comuna_etario_monthly_mart(_source_fixture())
    reference = _comuna_monthly_reference(mart)
    reference.loc[reference.index[0], "atenciones_id1"] += 1
    with pytest.raises(ValueError, match="No reconcilia etario→comuna"):
        validate_reconciliation_with_comuna_monthly(mart, reference)


def test_stage_is_registered_after_clean_urgencias_and_comuna_marts() -> None:
    assert pipeline.STAGES["build_urgencias_comuna_etario_mart"]["depends_on"] == [
        "clean_urgencias", "build_urgencias_comuna_marts"
    ]
    assert "build_urgencias_comuna_etario_mart" in pipeline.PIPELINE_ORDER
    assert (
        pipeline.PIPELINE_ORDER.index("build_urgencias_comuna_marts")
        < pipeline.PIPELINE_ORDER.index("build_urgencias_comuna_etario_mart")
    )
