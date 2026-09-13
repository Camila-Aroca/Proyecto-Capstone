"""Pruebas dirigidas para la dimensión canónica de oferta de urgencia (RM)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_dim_oferta_urgencia_rm import (
    CRITERIO_CORE,
    CRITERIO_EXCEPCION_CEAR,
    build_dim_oferta_urgencia_rm,
    validate_dim_oferta,
)

MAESTRO_COLUMNS = [
    "establecimiento_codigo", "establecimiento_glosa", "comuna_codigo",
    "comuna_glosa", "tipo_establecimiento_glosa", "estado_funcionamiento",
    "latitud", "longitud",
]
URGENCIAS_COLUMNS = [
    "ano", "establecimiento_codigo", "id_causa", "total", "tipo_establecimiento_urgencia",
]


def _write_maestro(path: Path, rows: list[tuple]) -> None:
    frame = pd.DataFrame(rows, columns=MAESTRO_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def _write_urgencias_year(directory: Path, year: int, rows: list[tuple]) -> None:
    frame = pd.DataFrame(rows, columns=URGENCIAS_COLUMNS)
    directory.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False),
        directory / f"urgencias_rm_{year}.parquet",
    )


def _default_maestro_rows() -> list[tuple]:
    return [
        (100001, "Hospital Uno", "13101", "Santiago", "Hospital", "Vigente en Operación Habitual", -33.45, -70.65),
        (100002, "SAPU Dos", "13101", "Santiago", "Servicio de Atención Primaria de Urgencia (SAPU)", "vigente en operación habitual", -33.44, -70.64),
        (100003, "SAR Tres Cerrado", "13101", "Santiago", "Servicio de Atención Primaria de Urgencia de Alta Resolutividad (SAR)", "Cerrado", -33.46, -70.66),
        (100004, "SUR Cuatro Sin Coords", "13101", "Santiago", "Servicio de Urgencia Rural (SUR)", "Vigente en Operación Habitual", None, None),
        (100005, "COSAM Cinco", "13101", "Santiago", "Centro Comunitario de Salud Mental  (COSAM)", "Vigente en Operación Habitual", -33.47, -70.67),
        (100006, "CESFAM Seis Excepcion CEAR", "13101", "Santiago", "Centro de Salud Familiar (CESFAM)", "Vigente en Operación Habitual", -33.48, -70.68),
        (100007, "CESFAM Siete Sin Evidencia", "13101", "Santiago", "Centro de Salud Familiar (CESFAM)", "Vigente en Operación Habitual", -33.49, -70.69),
        (100008, "Clinica Ocho", "13101", "Santiago", "Clínica", "Vigente en Operación Habitual", -33.50, -70.70),
    ]


def _write_default_urgencias(directory: Path) -> None:
    # Solo se escriben (y solo se leen) los años del período canónico CERRADO
    # 2021-2025; 2020/2026 se cubren aparte en
    # test_2020_and_2026_are_excluded_from_evidence_window.
    for year in range(2021, 2026):
        _write_urgencias_year(directory, year, [])
    _write_urgencias_year(directory, 2021, [
        (2021, 100001, 1, 100, "Hospital"),
        (2021, 100001, 36, 10, "Hospital"),
        (2021, 100002, 1, 50, "SAPU"),
        (2021, 100002, 36, 0, "SAPU"),
    ])
    _write_urgencias_year(directory, 2023, [
        (2023, 100006, 1, 15, "CEAR"),
        (2023, 100006, 36, 8, "CEAR"),
    ])


@pytest.fixture
def fixture_paths(tmp_path: Path) -> tuple[Path, Path]:
    maestro_path = tmp_path / "establecimientos_rm_clean.parquet"
    urgencias_dir = tmp_path / "urgencias"
    _write_maestro(maestro_path, _default_maestro_rows())
    _write_default_urgencias(urgencias_dir)
    return maestro_path, urgencias_dir


def test_core_types_and_vigente_filter(fixture_paths: tuple[Path, Path]) -> None:
    maestro_path, urgencias_dir = fixture_paths
    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)

    codes = set(dim["establecimiento_codigo"])
    assert 100001 in codes  # Hospital vigente
    assert 100002 in codes  # SAPU vigente, estado en minúscula (normalización)
    assert 100003 not in codes  # SAR cerrado: excluido pese a ser tipo core
    assert 100004 in codes  # SUR vigente sin coordenadas
    assert 100005 not in codes  # COSAM: no es tipo core y no reporta CEAR
    assert 100007 not in codes  # CESFAM sin evidencia CEAR
    assert 100008 not in codes  # Clínica: no es tipo core

    assert not dim["establecimiento_codigo"].duplicated().any()
    assert dim["establecimiento_codigo"].dtype == "int64"


def test_cear_exception_is_evidence_based(fixture_paths: tuple[Path, Path]) -> None:
    maestro_path, urgencias_dir = fixture_paths
    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)

    row = dim.loc[dim["establecimiento_codigo"] == 100006].iloc[0]
    assert row["criterio_inclusion_oferta"] == CRITERIO_EXCEPCION_CEAR
    assert row["tipo_urgencia_reportado"] == "CEAR"
    assert row["reporto_id36_periodo"]
    assert row["ultimo_ano_reporte_id36"] == 2023  # último año con ID36 > 0, no el primero


def test_id36_requires_positive_total_not_just_presence(fixture_paths: tuple[Path, Path]) -> None:
    maestro_path, urgencias_dir = fixture_paths
    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)

    sapu = dim.loc[dim["establecimiento_codigo"] == 100002].iloc[0]
    assert sapu["reporto_id1_periodo"]
    assert not sapu["reporto_id36_periodo"]  # sólo tiene una fila ID36 con total=0
    assert pd.isna(sapu["ultimo_ano_reporte_id36"])


def test_establishment_never_reporting_keeps_null_evidence(fixture_paths: tuple[Path, Path]) -> None:
    maestro_path, urgencias_dir = fixture_paths
    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)

    sur = dim.loc[dim["establecimiento_codigo"] == 100004].iloc[0]
    assert not sur["reporto_id1_periodo"]
    assert not sur["reporto_id36_periodo"]
    assert pd.isna(sur["tipo_urgencia_reportado"])
    assert pd.isna(sur["latitud"]) and pd.isna(sur["longitud"])


def test_establecimiento_codigo_normalized_to_int_for_join(fixture_paths: tuple[Path, Path]) -> None:
    maestro_path, urgencias_dir = fixture_paths
    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)
    assert pd.api.types.is_integer_dtype(dim["establecimiento_codigo"])


def test_tipo_urgencia_reportado_uses_latest_year_within_canonical_window(tmp_path: Path) -> None:
    maestro_path = tmp_path / "maestro.parquet"
    urgencias_dir = tmp_path / "urgencias"
    _write_maestro(maestro_path, [
        (100002, "SAPU luego SAR", "13101", "Santiago", "Servicio de Atención Primaria de Urgencia (SAPU)", "Vigente en Operación Habitual", -33.44, -70.64),
    ])
    for year in range(2021, 2026):
        _write_urgencias_year(urgencias_dir, year, [])
    _write_urgencias_year(urgencias_dir, 2021, [(2021, 100002, 1, 10, "SAPU")])
    _write_urgencias_year(urgencias_dir, 2022, [(2022, 100002, 1, 12, "SAR")])

    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)
    assert dim.iloc[0]["tipo_urgencia_reportado"] == "SAR"


def test_2020_and_2026_are_excluded_from_evidence_window(tmp_path: Path) -> None:
    """Actividad exclusiva en 2020 o 2026 no debe alimentar la evidencia 2021-2025."""
    maestro_path = tmp_path / "maestro.parquet"
    urgencias_dir = tmp_path / "urgencias"
    _write_maestro(maestro_path, [
        (100001, "Hospital Solo 2020/2026", "13101", "Santiago", "Hospital", "Vigente en Operación Habitual", -33.45, -70.65),
    ])
    for year in range(2021, 2026):
        _write_urgencias_year(urgencias_dir, year, [])
    # Actividad real, pero fuera del período canónico: no debe leerse.
    _write_urgencias_year(urgencias_dir, 2020, [(2020, 100001, 1, 999, "Hospital"), (2020, 100001, 36, 999, "Hospital")])
    _write_urgencias_year(urgencias_dir, 2026, [(2026, 100001, 1, 999, "Hospital"), (2026, 100001, 36, 999, "Hospital")])

    dim = build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)
    row = dim.iloc[0]
    assert not row["reporto_id1_periodo"]
    assert not row["reporto_id36_periodo"]
    assert pd.isna(row["ultimo_ano_reporte_id36"])
    assert pd.isna(row["tipo_urgencia_reportado"])


def test_duplicate_establecimiento_codigo_in_maestro_is_rejected(tmp_path: Path) -> None:
    maestro_path = tmp_path / "maestro.parquet"
    urgencias_dir = tmp_path / "urgencias"
    rows = _default_maestro_rows() + [_default_maestro_rows()[0]]
    _write_maestro(maestro_path, rows)
    _write_default_urgencias(urgencias_dir)

    with pytest.raises(ValueError, match="duplicado en el maestro"):
        build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)


def test_missing_maestro_raises_file_not_found(tmp_path: Path) -> None:
    urgencias_dir = tmp_path / "urgencias"
    _write_default_urgencias(urgencias_dir)
    with pytest.raises(FileNotFoundError):
        build_dim_oferta_urgencia_rm(maestro_path=tmp_path / "no_existe.parquet", urgencias_dir=urgencias_dir)


def test_missing_urgencias_year_raises_file_not_found(tmp_path: Path) -> None:
    maestro_path = tmp_path / "maestro.parquet"
    _write_maestro(maestro_path, _default_maestro_rows())
    urgencias_dir = tmp_path / "urgencias"
    urgencias_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)


# --- Validaciones directas sobre validate_dim_oferta ---------------------

def _valid_dim(fixture_paths: tuple[Path, Path]) -> pd.DataFrame:
    maestro_path, urgencias_dir = fixture_paths
    return build_dim_oferta_urgencia_rm(maestro_path=maestro_path, urgencias_dir=urgencias_dir)


def _cear_codes(dim: pd.DataFrame) -> set[int]:
    """Reconstruye el set de códigos CEAR válidos ya reflejado en el propio `dim` de fixture."""
    return set(dim.loc[dim["criterio_inclusion_oferta"] == CRITERIO_EXCEPCION_CEAR, "establecimiento_codigo"])


def test_validate_rejects_duplicate_codigo(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = pd.concat([dim, dim.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicado en la dimensión de oferta"):
        validate_dim_oferta(broken, _cear_codes(dim))


def test_validate_rejects_non_vigente_row(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = dim.copy()
    broken.loc[broken.index[0], "estado_funcionamiento"] = "cerrado"
    with pytest.raises(ValueError, match="no vigente"):
        validate_dim_oferta(broken, _cear_codes(dim))


def test_validate_rejects_id36_without_id1(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = dim.copy()
    idx = broken.index[0]
    broken.loc[idx, "reporto_id1_periodo"] = False
    broken.loc[idx, "reporto_id36_periodo"] = True
    broken.loc[idx, "ultimo_ano_reporte_id36"] = 2021
    with pytest.raises(ValueError, match="incoherente con Urgencias"):
        validate_dim_oferta(broken, _cear_codes(dim))


def test_validate_rejects_partial_null_coordinates(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = dim.copy()
    broken.loc[broken.index[0], "latitud"] = None
    with pytest.raises(ValueError, match="ambas nulas o ambas válidas"):
        validate_dim_oferta(broken, _cear_codes(dim))


def test_validate_rejects_bad_comuna_format(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = dim.copy()
    broken.loc[broken.index[0], "comuna_codigo"] = "1"
    with pytest.raises(ValueError, match="formato CUT"):
        validate_dim_oferta(broken, _cear_codes(dim))


def test_validate_rejects_unknown_criterio(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = dim.copy()
    broken.loc[broken.index[0], "criterio_inclusion_oferta"] = "otro"
    with pytest.raises(ValueError, match="fuera del dominio permitido"):
        validate_dim_oferta(broken, _cear_codes(dim))


def test_validate_rejects_core_criterio_with_non_core_tipo(fixture_paths: tuple[Path, Path]) -> None:
    dim = _valid_dim(fixture_paths)
    broken = dim.copy()
    row_idx = broken.index[broken["criterio_inclusion_oferta"] == CRITERIO_CORE][0]
    broken.loc[row_idx, "tipo_establecimiento"] = "Clínica"
    with pytest.raises(ValueError, match="fuera de \\{Hospital,SAPU,SAR,SUR\\}"):
        validate_dim_oferta(broken, _cear_codes(dim))


# --- Registro en el orquestador -------------------------------------------

def test_stage_is_registered_after_establishments_and_urgencias() -> None:
    assert pipeline.STAGES["build_dim_oferta_urgencia_rm"]["depends_on"] == [
        "clean_establishments", "clean_urgencias",
    ]
    assert "build_dim_oferta_urgencia_rm" in pipeline.PIPELINE_ORDER
    assert (
        pipeline.PIPELINE_ORDER.index("clean_establishments")
        < pipeline.PIPELINE_ORDER.index("build_dim_oferta_urgencia_rm")
    )
    assert (
        pipeline.PIPELINE_ORDER.index("clean_urgencias")
        < pipeline.PIPELINE_ORDER.index("build_dim_oferta_urgencia_rm")
    )


def test_official_output_exists() -> None:
    """Verifica que el output canónico ya haya sido generado por el pipeline oficial."""
    from src.data.build_dim_oferta_urgencia_rm import OUTPUT_PATH
    assert OUTPUT_PATH.exists(), f"Falta output canónico: {OUTPUT_PATH}"
