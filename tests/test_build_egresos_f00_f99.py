"""Pruebas dirigidas para el dataset canónico F00-F99 de Egresos Hospitalarios."""

from __future__ import annotations

import pyarrow as pa
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_egresos_f00_f99 import (
    DICCIONARIO_PATH,
    EXPECTED_F00_F99_SUBCATEGORIAS,
    RM_REGION_CODE,
    add_residente_rm_flag,
    build_dataset,
    filter_f00_f99,
    independent_total_count,
    load_catalog_f00_f99,
    validate_diag1_domain,
    validate_dias_estada,
    validate_grain,
    validate_no_pipeline_duplication,
    validate_whitelisted_domains,
    validate_years,
)

CATALOG_CODES = {"F200", "F329", "F411"}


def _table(rows: list[dict]) -> pa.Table:
    columns = {key: [row.get(key) for row in rows] for key in rows[0]}
    return pa.table(columns)


def _valid_rows() -> list[dict]:
    return [
        {
            "ano_egreso": 2021, "sexo": "1", "grupo_edad": "20 A 24 AÑOS",
            "region_residencia": 13, "comuna_residencia": 13101,
            "prevision": 1, "glosa_prevision": "FONASA",
            "pertenencia_establecimiento_salud": "Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS",
            "diag1": "F200", "diag2": "", "dias_estada": 5, "condicion_egreso": 1,
        },
        {
            "ano_egreso": 2021, "sexo": "2", "grupo_edad": "25 A 29 AÑOS",
            "region_residencia": 5, "comuna_residencia": 5101,
            "prevision": 2, "glosa_prevision": "ISAPRE",
            "pertenencia_establecimiento_salud": "No Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS",
            "diag1": "F329", "diag2": "", "dias_estada": 10, "condicion_egreso": 2,
        },
        {
            "ano_egreso": 2021, "sexo": "*", "grupo_edad": "*",
            "region_residencia": None, "comuna_residencia": None,
            "prevision": None, "glosa_prevision": "*",
            "pertenencia_establecimiento_salud": "*",
            "diag1": "F411", "diag2": "", "dias_estada": 1, "condicion_egreso": 1,
        },
    ]


def test_filter_keeps_only_catalog_codes() -> None:
    table = _table(_valid_rows() + [
        {"ano_egreso": 2021, "sexo": "1", "grupo_edad": "20 A 24 AÑOS", "region_residencia": 13,
         "comuna_residencia": 13101, "prevision": 1, "glosa_prevision": "FONASA",
         "pertenencia_establecimiento_salud": "Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS",
         "diag1": "I619", "diag2": "", "dias_estada": 3, "condicion_egreso": 1},
    ])
    filtered = filter_f00_f99(table, CATALOG_CODES)
    assert filtered.num_rows == 3
    assert set(filtered["diag1"].to_pylist()) == {"F200", "F329", "F411"}


def test_residente_rm_flag_is_nullable_and_correct() -> None:
    table = filter_f00_f99(_table(_valid_rows()), CATALOG_CODES)
    flagged = add_residente_rm_flag(table)
    flags = flagged["residente_rm"].to_pylist()
    assert flags == [True, False, None]


def test_validate_diag1_domain_rejects_code_outside_catalog() -> None:
    table = _table([_valid_rows()[0] | {"diag1": "Z999"}])
    with pytest.raises(ValueError, match="fuera del catálogo"):
        validate_diag1_domain(table, CATALOG_CODES)


def test_validate_years_rejects_year_outside_contract() -> None:
    table = _table([_valid_rows()[0] | {"ano_egreso": 2019}])
    with pytest.raises(ValueError, match="contrato"):
        validate_years(table, years=(2020, 2021))


def test_validate_no_pipeline_duplication_detects_mismatch() -> None:
    table = _table(_valid_rows())
    with pytest.raises(ValueError):
        validate_no_pipeline_duplication({2021: 3}, table, expected_total=2)


def test_validate_dias_estada_rejects_non_positive() -> None:
    table = _table([_valid_rows()[0] | {"dias_estada": 0}])
    with pytest.raises(ValueError, match="dias_estada"):
        validate_dias_estada(table)


def test_validate_whitelisted_domains_rejects_unknown_sexo_value() -> None:
    table = _table([_valid_rows()[0] | {"sexo": "OTRO_VALOR_NUEVO"}])
    with pytest.raises(ValueError, match="sexo"):
        validate_whitelisted_domains(table)


def test_validate_grain_rejects_empty_dataset() -> None:
    empty = _table(_valid_rows()).filter(pa.array([False, False, False]))
    with pytest.raises(ValueError, match="vacío"):
        validate_grain(empty)


def test_load_catalog_f00_f99_matches_official_diccionario() -> None:
    catalog = load_catalog_f00_f99(DICCIONARIO_PATH)
    assert len(catalog) == EXPECTED_F00_F99_SUBCATEGORIAS
    assert "F200" in set(catalog["CODIGO SUBCATEGORIA"])
    assert (catalog["CAPITULO"] == "F00-F99").all()


def test_build_dataset_reconciles_against_real_egresos_processed() -> None:
    combined, per_year_counts, catalog = build_dataset()
    catalog_codes = set(catalog["CODIGO SUBCATEGORIA"])
    expected_total = independent_total_count(catalog_codes)

    validate_diag1_domain(combined, catalog_codes)
    validate_years(combined)
    validate_no_pipeline_duplication(per_year_counts, combined, expected_total)
    validate_dias_estada(combined)
    validate_whitelisted_domains(combined)
    validate_grain(combined)

    assert combined.num_rows == expected_total
    assert set(per_year_counts) == set(range(2020, 2026))
    flags = combined["residente_rm"].to_pylist()
    assert sum(1 for f in flags if f is True) > 0
    assert sum(1 for f in flags if f is False) > 0
    assert sum(1 for f in flags if f is None) > 0


def test_stage_is_registered_after_clean_egresos() -> None:
    assert pipeline.STAGES["build_egresos_f00_f99"]["depends_on"] == ["clean_egresos"]
    assert "build_egresos_f00_f99" in pipeline.PIPELINE_ORDER
    assert (
        pipeline.PIPELINE_ORDER.index("clean_egresos")
        < pipeline.PIPELINE_ORDER.index("build_egresos_f00_f99")
    )
