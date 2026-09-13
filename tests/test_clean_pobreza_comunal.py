"""Pruebas unitarias para la dimensión de vulnerabilidad socioeconómica comunal RM (MDS/Casen 2022)."""

from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.clean_censo_comunas import EXPECTED_RM_CUTS
from src.data.clean_pobreza_comunal import (
    ANO_REFERENCIA,
    DIRECCION_INDICADOR,
    RAW_PATH,
    SHEET_NAME,
    build_dim_vulnerabilidad_comuna,
)


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({
        "comuna_codigo": [str(cut) for cut in sorted(EXPECTED_RM_CUTS)],
        "comuna_glosa": [f"Comuna {cut}" for cut in sorted(EXPECTED_RM_CUTS)],
    })
    pq.write_table(table, path)


def _write_workbook(
    path: Path,
    *,
    cuts=None,
    tasa_por_comuna: dict[int, float] | None = None,
    presencia_por_comuna: dict[int, str] | None = None,
    tampered_ci_comuna: int | None = None,
) -> None:
    cuts = sorted(EXPECTED_RM_CUTS) if cuts is None else cuts
    tasa_por_comuna = tasa_por_comuna or {}
    presencia_por_comuna = presencia_por_comuna or {}

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    sheet.append(["Título del cuadro"])
    sheet.append([None])
    sheet.append([
        "Código", "Región", "Nombre comuna", "Personas proyectadas",
        "Personas en pobreza", "Porcentaje pobreza", "Límite inferior",
        "Límite superior", "Presencia muestra", "Tipo estimación SAE",
    ])
    for cut in cuts:
        tasa = tasa_por_comuna.get(cut, 0.05)
        lower, upper = tasa - 0.02, tasa + 0.02
        if tampered_ci_comuna == cut:
            lower, upper = tasa + 0.5, tasa + 0.6
        sheet.append([
            cut, "Metropolitana", f"Comuna {cut}", 100_000, int(100_000 * tasa), tasa,
            max(lower, 0.0), upper, presencia_por_comuna.get(cut, "Sí"),
            "Directa y Sintética (Fay-Herriot)",
        ])
    # Fila de otra región para verificar el filtro RM.
    sheet.append([5101, "Valparaíso", "Valparaíso", 100_000, 5_000, 0.05, 0.03, 0.07, "Sí", "Directa y Sintética (Fay-Herriot)"])
    # Nota al pie (columna 1 no numérica) que debe detener el parseo.
    sheet.append(["Nota metodológica: ..."])

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def test_build_dim_vulnerabilidad_comuna_success(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    output_path = tmp_path / "dim_vulnerabilidad_comuna.parquet"
    tasas = {cut: 0.05 + (i % 10) * 0.01 for i, cut in enumerate(sorted(EXPECTED_RM_CUTS))}
    _write_workbook(raw_path, tasa_por_comuna=tasas)
    _write_catalog(catalog_path)

    result = build_dim_vulnerabilidad_comuna(
        raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=output_path
    )

    assert result["filas"] == 52
    assert result["comunas_unicas"] == 52
    assert result["ano_referencia"] == ANO_REFERENCIA

    table = pq.read_table(output_path).to_pandas()
    assert set(table["comuna_codigo"]) == {str(cut) for cut in EXPECTED_RM_CUTS}
    assert not table.duplicated(["comuna_codigo"]).any()
    assert (table["ano_referencia"] == ANO_REFERENCIA).all()
    assert table["direccion_indicador"].eq(DIRECCION_INDICADOR).all()
    assert table["indicador_vulnerabilidad"].between(0.0, 1.0).all()
    assert (table["intervalo_confianza_inferior"] <= table["indicador_vulnerabilidad"]).all()
    assert (table["indicador_vulnerabilidad"] <= table["intervalo_confianza_superior"]).all()
    assert table["fuente"].str.len().gt(0).all()

    glosa = table.loc[table["comuna_codigo"] == "13101", "comuna_glosa"].iloc[0]
    assert glosa == "Comuna 13101"


def test_missing_comuna_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    incomplete_cuts = sorted(EXPECTED_RM_CUTS)[:-1]
    _write_workbook(raw_path, cuts=incomplete_cuts)
    _write_catalog(catalog_path)

    with pytest.raises(ValueError, match="Comunas RM inconsistentes"):
        build_dim_vulnerabilidad_comuna(
            raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_missing_sample_presence_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    first_cut = sorted(EXPECTED_RM_CUTS)[0]
    _write_workbook(raw_path, presencia_por_comuna={first_cut: "No"})
    _write_catalog(catalog_path)

    with pytest.raises(ValueError, match="sin presencia en la muestra Casen"):
        build_dim_vulnerabilidad_comuna(
            raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_inconsistent_confidence_interval_is_rejected(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    catalog_path = tmp_path / "catalog.parquet"
    first_cut = sorted(EXPECTED_RM_CUTS)[0]
    _write_workbook(raw_path, tampered_ci_comuna=first_cut)
    _write_catalog(catalog_path)

    with pytest.raises(ValueError, match="Intervalo de confianza inconsistente"):
        build_dim_vulnerabilidad_comuna(
            raw_path=raw_path, glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_missing_glosa_catalog_raises_file_not_found(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.xlsx"
    _write_workbook(raw_path)

    with pytest.raises(FileNotFoundError):
        build_dim_vulnerabilidad_comuna(
            raw_path=raw_path, glosa_catalog_path=tmp_path / "no_existe.parquet", output_path=tmp_path / "out.parquet"
        )


def test_missing_raw_raises_file_not_found(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.parquet"
    _write_catalog(catalog_path)
    with pytest.raises(FileNotFoundError):
        build_dim_vulnerabilidad_comuna(
            raw_path=tmp_path / "no_existe.xlsx", glosa_catalog_path=catalog_path, output_path=tmp_path / "out.parquet"
        )


def test_official_raw_exists() -> None:
    """Verifica que el snapshot RAW oficial esté presente para reproducibilidad local."""
    assert RAW_PATH.exists(), f"Falta archivo raw: {RAW_PATH}"
