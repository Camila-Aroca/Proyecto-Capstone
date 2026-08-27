"""Pruebas unitarias para el procesamiento de cartografía comunal Censo 2024 RM."""

from pathlib import Path
import pytest
import pyarrow.parquet as pq

from src.data.clean_censo_comunas import (
    RAW_CENSO_COMUNAL,
    PROCESSED_CENSO_RM_COMUNAL,
    EXPECTED_RM_CUTS,
    process_censo_comunal_rm,
)


def test_raw_censo_comunal_exists():
    """Verifica que el archivo raw exista."""
    assert RAW_CENSO_COMUNAL.exists(), f"Falta archivo raw: {RAW_CENSO_COMUNAL}"


def test_process_censo_comunal_rm(tmp_path: Path):
    """Prueba la función de procesamiento y validación en un directorio temporal."""
    output_tmp = tmp_path / "Cartografia_censo2024_RM_Comunal.parquet"
    res = process_censo_comunal_rm(raw_path=RAW_CENSO_COMUNAL, output_path=output_tmp)

    assert res["filas"] == 52
    assert res["comunas_unicas"] == 52
    assert res["estan_52_comunas"] is True
    assert res["cod_region_unico"] is True
    assert res["geometrias_nulas"] == 0
    assert res["geometrias_invalidas"] == 0
    assert res["duplicados_cut"] == 0
    assert res["validacion_exitosa"] is True

    # Verificar que el GeoParquet guardado se abre y tiene las 52 filas
    t = pq.read_table(output_tmp)
    assert t.num_rows == 52
    assert set(t["CUT"].to_pylist()) == EXPECTED_RM_CUTS
