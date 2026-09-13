"""Pruebas unitarias para la dimensión anual de población comunal RM (INE 2002-2035)."""

from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.clean_censo_comunas import EXPECTED_RM_CUTS
from src.data.clean_poblacion_proyecciones import (
    RAW_PATH,
    SHEET_NAME,
    YEARS,
    build_dim_poblacion_comuna_anual,
)


POBLACION_POR_FILA = 100  # cada combinación sexo×edad aporta este valor por año


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({
        "comuna_codigo": [str(cut) for cut in sorted(EXPECTED_RM_CUTS)],
        "comuna_glosa": [f"Comuna {cut}" for cut in sorted(EXPECTED_RM_CUTS)],
    })
    pq.write_table(table, path)


def _write_workbook(path: Path, *, cuts=None, tamper_year: int | None = None,
                     tamper_sexo: bool = False) -> None:
    cuts = sorted(EXPECTED_RM_CUTS) if cuts is None else cuts
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    header = ["Region", "Nombre Region", "Provincia", "Nombre Provincia", "Comuna", "Nombre Comuna", "Sexo", "Edad"]
    header += [f"Poblacion {2002 + i}" for i in range(34)]
    sheet.append(header)

    def year_value(year: int) -> int:
        return POBLACION_POR_FILA + (year - 2021)

    first_row_written = False
    for cut in cuts:
        for sexo in (1, 2):
            for edad in (0, 1):
                row = [13, "Metropolitana de Santiago", 131, "Santiago", cut, f"Comuna {cut}", sexo, edad]
                for i in range(34):
                    year = 2002 + i
                    row.append(year_value(year) if year in YEARS else 0)
                if tamper_sexo and not first_row_written:
                    row[6] = 9
                    first_row_written = True
                if tamper_year is not None and not first_row_written:
                    col_index = 8 + (tamper_year - 2002)
                    row[col_index] = None
                    first_row_written = True
                sheet.append(row)

    # Fila de otra región para verificar el filtro RM.
    other_row = [5, "Valparaíso", 51, "Valparaíso", 5101, "Valparaíso", 1, 0]
    other_row += [999] * 34
    sheet.append(other_row)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def test_build_dim_poblacion_comuna_anual_success(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "dim_poblacion_comuna_censo2024.parquet"
    output_path = tmp_path / "dim_poblacion_comuna_anual.parquet"
    _write_workbook(raw_path)
    _write_catalog(catalog_path)

    result = build_dim_poblacion_comuna_anual(
        raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=output_path
    )

    assert result["filas"] == 52 * len(YEARS)
    assert result["comunas_unicas"] == 52
    assert result["anos"] == list(YEARS)

    table = pq.read_table(output_path).to_pandas()
    assert set(table["comuna_codigo"]) == {str(cut) for cut in EXPECTED_RM_CUTS}
    assert not table.duplicated(["comuna_codigo", "ano"]).any()
    assert (table["poblacion"] > 0).all()
    assert table["tipo_poblacion"].eq("proyeccion").all()
    assert table["fuente"].str.len().gt(0).all()

    year_2021_total = table.loc[table["ano"] == 2021, "poblacion"].iloc[0]
    assert year_2021_total == POBLACION_POR_FILA * 4  # 2 sexos x 2 edades
    year_2025_total = table.loc[table["ano"] == 2025, "poblacion"].iloc[0]
    assert year_2025_total == (POBLACION_POR_FILA + 4) * 4

    glosa = table.loc[table["comuna_codigo"] == "13101", "comuna_glosa"].iloc[0]
    assert glosa == "Comuna 13101"


def test_missing_comuna_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    incomplete_cuts = sorted(EXPECTED_RM_CUTS)[:-1]
    _write_workbook(raw_path, cuts=incomplete_cuts)
    _write_catalog(catalog_path)

    with pytest.raises(ValueError, match="Comunas RM inconsistentes"):
        build_dim_poblacion_comuna_anual(
            raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_null_population_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    _write_workbook(raw_path, tamper_year=2023)
    _write_catalog(catalog_path)

    with pytest.raises(ValueError, match="Población nula"):
        build_dim_poblacion_comuna_anual(
            raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_invalid_sexo_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    _write_workbook(raw_path, tamper_sexo=True)
    _write_catalog(catalog_path)

    with pytest.raises(ValueError, match="sexo inesperado"):
        build_dim_poblacion_comuna_anual(
            raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_missing_glosa_catalog_raises_file_not_found(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    _write_workbook(raw_path)

    with pytest.raises(FileNotFoundError):
        build_dim_poblacion_comuna_anual(
            raw_path=raw_path, glosa_catalog_path=tmp_path / "no_existe.parquet", output_path=tmp_path / "out.parquet"
        )


def test_missing_raw_raises_file_not_found(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.parquet"
    _write_catalog(catalog_path)
    with pytest.raises(FileNotFoundError):
        build_dim_poblacion_comuna_anual(
            raw_path=tmp_path / "no_existe.xlsx", glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_official_raw_exists() -> None:
    """Verifica que el snapshot RAW oficial esté presente para reproducibilidad local."""
    assert RAW_PATH.exists(), f"Falta archivo raw: {RAW_PATH}"
