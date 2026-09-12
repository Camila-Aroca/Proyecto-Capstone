"""Pruebas unitarias para el módulo de normalización de Atenciones de Urgencia."""

from pathlib import Path
from unittest.mock import patch
import pytest
import pyarrow.parquet as pq
import pandas as pd

from src.data.clean_urgencias import (
    RAW_URGENCIAS_DIR,
    PROCESSED_URGENCIAS_DIR,
    COLUMN_MAPPING_RAW_TO_SNAKE,
    load_establishment_catalogs,
    process_urgencias_year,
)


def test_catalogs_load():
    """Verifica que los catálogos de establecimientos se carguen con datos."""
    rm_antiguo, rm_nuevo, nac_antiguo, nac_nuevo = load_establishment_catalogs()
    assert len(rm_nuevo) == 1172
    assert len(rm_antiguo) > 0
    assert len(nac_nuevo) > 0


def test_process_urgencias_year_small_fixture(tmp_path: Path):
    """Cubre filtrado territorial, homologacion y esquema sin RAW masivo."""
    raw_path = tmp_path / "AtencionesUrgencia2024.csv"
    raw_path.write_text(
        "IdEstablecimiento;NEstablecimiento;IdCausa;GlosaCausa;Total;"
        "Menores_1;De_1_a_4;De_5_a_14;De_15_a_64;De_65_y_mas;fecha;"
        "semana;GLOSATIPOESTABLECIMIENTO;GLOSATIPOATENCION;GlosaTipoCampana;"
        "CodigoRegion;NombreRegion;CodigoComuna;NombreComuna\n"
        "OLD-RM;Catalogo RM;1;F32;10;1;2;3;3;1;01/01/2024;1;"
        "Hospital;Urgencia;;13;Metropolitana;13101;Santiago\n"
        "200;Fuera RM;1;F32;20;2;4;6;6;2;01/01/2024;1;"
        "Hospital;Urgencia;;15;Arica;15101;Arica\n"
        "999;RM por region;1;F32;30;3;6;9;9;3;01/01/2024;1;"
        "SAR;Urgencia;;13;Metropolitana;13102;Cerrillos\n"
        "UNKNOWN;Sin territorio;1;F32;40;4;8;12;12;4;01/01/2024;1;"
        "SAR;Urgencia;;;;;\n",
        encoding="utf-8",
    )

    rm_info = {
        "establecimiento_codigo": 100,
        "establecimiento_codigo_antiguo": "OLD-RM",
        "establecimiento_glosa": "Catalogo RM",
        "comuna_codigo": "13101",
        "comuna_glosa": "Santiago",
        "tipo_establecimiento_glosa": "Hospital",
        "latitud": -33.4,
        "longitud": -70.6,
    }

    output_dir = tmp_path / "processed"
    result = process_urgencias_year(
        year=2024,
        rm_by_antiguo={"OLD-RM": rm_info},
        rm_by_nuevo={"100": rm_info},
        nac_by_antiguo={},
        nac_by_nuevo={},
        raw_dir=tmp_path,
        output_dir=output_dir,
        chunk_size=1,
    )

    assert result["raw_rows"] == 4
    assert result["rm_rows"] == 2
    assert result["no_rm_rows"] == 1
    assert result["sin_territorio_rows"] == 1

    output_path = output_dir / "urgencias_rm_2024.parquet"
    table = pq.read_table(output_path)
    assert table.num_rows == 2
    assert table.schema.field("region_codigo").type == "int32"
    assert table.schema.field("total").type == "int32"
    assert set(table["region_codigo"].to_pylist()) == {13}
    assert set(table["ano"].to_pylist()) == {2024}


def test_process_urgencias_preserves_canonical_output_on_write_failure(
    tmp_path: Path,
):
    """Una falla de escritura no debe reemplazar el Parquet canónico previo."""
    raw_path = tmp_path / "AtencionesUrgencia2024.csv"
    raw_path.write_text(
        "IdEstablecimiento;NEstablecimiento;IdCausa;GlosaCausa;Total;"
        "Menores_1;De_1_a_4;De_5_a_14;De_15_a_64;De_65_y_mas;fecha;"
        "semana;GLOSATIPOESTABLECIMIENTO;GLOSATIPOATENCION;GlosaTipoCampana;"
        "CodigoRegion;NombreRegion;CodigoComuna;NombreComuna\n"
        "OLD-RM;Catalogo RM;1;F32;10;1;2;3;3;1;01/01/2024;1;"
        "Hospital;Urgencia;;13;Metropolitana;13101;Santiago\n",
        encoding="utf-8",
    )
    rm_info = {
        "establecimiento_codigo": 100,
        "establecimiento_codigo_antiguo": "OLD-RM",
        "establecimiento_glosa": "Catalogo RM",
        "comuna_codigo": "13101",
        "comuna_glosa": "Santiago",
        "tipo_establecimiento_glosa": "Hospital",
        "latitud": -33.4,
        "longitud": -70.6,
    }
    output_dir = tmp_path / "processed"
    output_dir.mkdir()
    canonical = output_dir / "urgencias_rm_2024.parquet"
    canonical.write_bytes(b"previous-canonical-output")

    with patch(
        "src.data.clean_urgencias.pq.ParquetWriter.write_table",
        side_effect=RuntimeError("simulated write failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated write failure"):
            process_urgencias_year(
                year=2024,
                rm_by_antiguo={"OLD-RM": rm_info},
                rm_by_nuevo={"100": rm_info},
                nac_by_antiguo={},
                nac_by_nuevo={},
                raw_dir=tmp_path,
                output_dir=output_dir,
                chunk_size=1,
            )

    assert canonical.read_bytes() == b"previous-canonical-output"


def test_process_urgencias_year_2020(tmp_path: Path):
    """Prueba el procesamiento de un año (ej. 2020) en directorio temporal."""
    rm_antiguo, rm_nuevo, nac_antiguo, nac_nuevo = load_establishment_catalogs()
    
    # Procesar 2020 en tmp_path
    res = process_urgencias_year(
        year=2020,
        rm_by_antiguo=rm_antiguo,
        rm_by_nuevo=rm_nuevo,
        nac_by_antiguo=nac_antiguo,
        nac_by_nuevo=nac_nuevo,
        raw_dir=RAW_URGENCIAS_DIR,
        output_dir=tmp_path,
        chunk_size=50000
    )

    assert res["raw_rows"] == 6446646
    assert res["rm_rows"] == 1720000
    assert res["sin_territorio_rows"] == 0
    assert res["no_rm_rows"] == 4726646

    # Verificar que el parquet generado se puede leer y tiene las columnas esperadas
    parquet_file = tmp_path / "urgencias_rm_2020.parquet"
    assert parquet_file.exists()
    
    t = pq.read_table(parquet_file)
    assert t.num_rows == 1720000
    assert "fecha" in t.column_names
    assert "establecimiento_codigo" in t.column_names
    assert "comuna_codigo" in t.column_names
    assert "region_codigo" in t.column_names
    assert "total" in t.column_names
