"""Pruebas unitarias para el módulo de normalización de Atenciones de Urgencia."""

from pathlib import Path
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
