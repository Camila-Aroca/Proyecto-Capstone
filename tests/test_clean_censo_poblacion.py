"""Pruebas unitarias para la dimensión de población censada 2024 por comuna (RM)."""

from pathlib import Path

import openpyxl
import pyarrow.parquet as pq
import pytest

from src.data.clean_censo_comunas import EXPECTED_RM_CUTS
from src.data.clean_censo_poblacion import (
    RAW_PATH,
    build_dim_poblacion_comuna_censo2024,
)


RM_ROWS = [
    (13, "Metropolitana de Santiago", 131, "Santiago", cut, f"Comuna {cut}", 1000 + index)
    for index, cut in enumerate(sorted(EXPECTED_RM_CUTS))
]
RM_TOTAL = sum(row[6] for row in RM_ROWS)


def _write_workbook(path: Path, *, rm_rows=None, region_total=None, duplicate_last=False) -> None:
    rm_rows = RM_ROWS if rm_rows is None else rm_rows
    region_total = RM_TOTAL if region_total is None else region_total

    workbook = openpyxl.Workbook()
    sheet1 = workbook.active
    sheet1.title = "1"
    for _ in range(4):
        sheet1.append([None] * 6)
    sheet1.append([13, "Metropolitana de Santiago", region_total, None, None, None])

    sheet2 = workbook.create_sheet("2")
    for _ in range(4):
        sheet2.append([None] * 7)
    for row in rm_rows:
        sheet2.append(list(row))
    if duplicate_last:
        sheet2.append(list(rm_rows[-1]))
    # Filas de otra región para verificar el filtro por RM.
    sheet2.append([5, "Valparaíso", 51, "Valparaíso", 5101, "Valparaíso", 300000])

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def test_build_dim_poblacion_comuna_censo2024(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    output_path = tmp_path / "dim_poblacion_comuna_censo2024.parquet"
    _write_workbook(raw_path)

    result = build_dim_poblacion_comuna_censo2024(raw_path=raw_path, output_path=output_path)

    assert result["filas"] == 52
    assert result["comunas_unicas"] == 52
    assert result["poblacion_total_rm"] == RM_TOTAL

    table = pq.read_table(output_path)
    assert table.num_rows == 52
    assert set(table.column("comuna_codigo").to_pylist()) == {str(cut) for cut in EXPECTED_RM_CUTS}
    assert all(year == 2024 for year in table.column("ano_referencia").to_pylist())
    assert all(pop > 0 for pop in table.column("poblacion_censada").to_pylist())


def test_missing_comuna_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    output_path = tmp_path / "out.parquet"
    incomplete_rows = RM_ROWS[:-1]
    incomplete_total = sum(row[6] for row in incomplete_rows)
    _write_workbook(raw_path, rm_rows=incomplete_rows, region_total=incomplete_total)

    with pytest.raises(ValueError, match="52 comunas"):
        build_dim_poblacion_comuna_censo2024(raw_path=raw_path, output_path=output_path)


def test_duplicate_cut_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    output_path = tmp_path / "out.parquet"
    _write_workbook(raw_path, duplicate_last=True)

    with pytest.raises(ValueError):
        build_dim_poblacion_comuna_censo2024(raw_path=raw_path, output_path=output_path)


def test_region_total_mismatch_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    output_path = tmp_path / "out.parquet"
    _write_workbook(raw_path, region_total=RM_TOTAL + 1)

    with pytest.raises(ValueError, match="no coincide"):
        build_dim_poblacion_comuna_censo2024(raw_path=raw_path, output_path=output_path)


def test_missing_raw_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_dim_poblacion_comuna_censo2024(raw_path=tmp_path / "no_existe.xlsx", output_path=tmp_path / "out.parquet")


def test_official_raw_exists() -> None:
    """Verifica que el snapshot RAW oficial esté presente para reproducibilidad local."""
    assert RAW_PATH.exists(), f"Falta archivo raw: {RAW_PATH}"
