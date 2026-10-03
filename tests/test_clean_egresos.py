import os
import subprocess
import sys
from pathlib import Path
import pyarrow.parquet as pq
import pytest
from unittest.mock import patch
import math
from src.data.clean_egresos import try_int, process_egresos_year, run_full_normalization, YEAR_CONFIG
from src.data.download_deis_sources import canonical_egresos_raw_path

def test_try_int():
    assert try_int("123") == 123
    assert try_int("123.0") == 123
    assert try_int("", default=-1) == -1
    assert try_int(None, default=None) is None
    assert try_int("NaN", default=None) is None
    assert try_int("0", default=None) == 0

def test_process_egresos_year_mocked(tmp_path):
    # Crear un CSV temporal simulando 2024 con la columna truncada
    mock_csv_path = tmp_path / canonical_egresos_raw_path(2024).name
    mock_csv_content = (
        "PERTENENCIA_ESTABLECIMIENTO_SALU;SEXO;COMUNA_RESIDENCIA;REGION_RESIDENCIA;DIAG1;DIAG2\n"
        "Sistema Público;HOMBRE;13101;13;F32;X60\n"
        ";MUJER;NaN;;;\n"
    )
    mock_csv_path.write_text(mock_csv_content, encoding="utf-8")

    # Parchear los paths en el módulo
    with patch("src.data.clean_egresos.RAW_EGRESOS_DIR", tmp_path), \
         patch("src.data.clean_egresos.PROCESSED_EGRESOS_DIR", tmp_path):
        
        res = process_egresos_year(2024)
        
        assert res["total_rows"] == 2
        
        # Verificar el archivo parquet generado
        parquet_path = tmp_path / "egresos_2024.parquet"
        assert parquet_path.exists()
        
        table = pq.read_table(parquet_path)
        df = table.to_pandas()
        
        assert len(df) == 2
        
        # Verificar corrección del truncamiento
        assert "pertenencia_establecimiento_salud" in df.columns
        assert df.iloc[0]["pertenencia_establecimiento_salud"] == "Sistema Público"
        
        # Verificar numéricos (missing numérico original -> sigue missing, cero original -> cero)
        assert df.iloc[0]["comuna_residencia"] == 13101
        assert df.iloc[0]["region_residencia"] == 13
        assert math.isnan(df.iloc[1]["comuna_residencia"]) # NaN default (ahora None/NaN en pandas)
        assert math.isnan(df.iloc[1]["region_residencia"]) # Emtpy default
        
        # Columna ausente en un ao -> pd.NA/None, no 0.
        # En 2024 no existe INTERV_Q, por lo tanto df debe tener None/NaN, NO 0.
        assert math.isnan(df.iloc[0]["interv_q"])
        assert math.isnan(df.iloc[0]["proced"])
        
        # Columna ERROR (ausente en el mock) -> NaN
        assert math.isnan(df.iloc[0]["error"])
        
        # Verificar diagnósticos
        assert df.iloc[0]["diag1"] == "F32"
        assert df.iloc[0]["diag2"] == "X60"

def test_process_egresos_schema_homogenization(tmp_path):
    # Test that 2020 (with INTERV_Q) and 2024 (without) have identical schema
    mock_csv_path20 = tmp_path / canonical_egresos_raw_path(2020).name
    mock_csv_content20 = "ANO_EGRESO;INTERV_Q;PROCED\n2020;1;0\n"
    mock_csv_path20.write_text(mock_csv_content20, encoding="latin-1")
    
    mock_csv_path24 = tmp_path / canonical_egresos_raw_path(2024).name
    mock_csv_content24 = "ANO_EGRESO\n2024\n"
    mock_csv_path24.write_text(mock_csv_content24, encoding="utf-8")
    
    with patch("src.data.clean_egresos.RAW_EGRESOS_DIR", tmp_path), \
         patch("src.data.clean_egresos.PROCESSED_EGRESOS_DIR", tmp_path):
        process_egresos_year(2020)
        process_egresos_year(2024)
        
        t20 = pq.read_table(tmp_path / "egresos_2020.parquet")
        t24 = pq.read_table(tmp_path / "egresos_2024.parquet")
        
        # 4. Esquemas anuales quedan homologados
        assert t20.schema == t24.schema
        
        df20 = t20.to_pandas()
        df24 = t24.to_pandas()
        
        # 3. Cero original -> sigue siendo cero
        assert df20.iloc[0]["proced"] == 0
        assert df20.iloc[0]["interv_q"] == 1
        
        # 1. Columna ausente -> NaN
        assert math.isnan(df24.iloc[0]["proced"])

def test_process_egresos_year_invalid_year():
    with pytest.raises(ValueError):
        process_egresos_year(1999)

def test_process_egresos_atomic_write(tmp_path):
    mock_csv_path20 = tmp_path / canonical_egresos_raw_path(2020).name
    mock_csv_content20 = "ANO_EGRESO\n2020\n"
    mock_csv_path20.write_text(mock_csv_content20, encoding="latin-1")
    
    # Pre-create a valid output file to simulate an existing previous successful run
    output_parquet = tmp_path / "egresos_2020.parquet"
    output_parquet.write_text("VALID_PARQUET_CONTENT")
    
    with patch("src.data.clean_egresos.RAW_EGRESOS_DIR", tmp_path), \
         patch("src.data.clean_egresos.PROCESSED_EGRESOS_DIR", tmp_path), \
         patch("src.data.clean_egresos.pq.ParquetWriter.write_table", side_effect=Exception("Simulated Write Error")):
        
        with pytest.raises(Exception, match="Simulated Write Error"):
            process_egresos_year(2020)
            
        # Verify the original output was untouched
        assert output_parquet.read_text() == "VALID_PARQUET_CONTENT"
        
        # Verify temp file was cleaned up
        temp_parquet = tmp_path / "egresos_2020.parquet.tmp"
        assert not temp_parquet.exists()


def test_run_full_normalization_fails_without_partial_outputs_when_raw_missing(tmp_path):
    raw_dir, out_dir = tmp_path / "raw", tmp_path / "processed"
    raw_dir.mkdir()
    # Solo existe un año: los demás son requeridos por el contrato del stage.
    (raw_dir / canonical_egresos_raw_path(2020).name).write_text("ANO_EGRESO\n2020\n", encoding="latin-1")

    with patch("src.data.clean_egresos.RAW_EGRESOS_DIR", raw_dir),          patch("src.data.clean_egresos.PROCESSED_EGRESOS_DIR", out_dir):
        with pytest.raises(FileNotFoundError, match="egresos_2021"):
            run_full_normalization()

    assert not out_dir.exists() or not list(out_dir.glob("*"))


def test_clean_egresos_module_exits_nonzero_without_raw(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "src.data.clean_egresos"],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    assert result.returncode != 0
    assert "FileNotFoundError" in result.stderr
    assert not (tmp_path / "data" / "processed" / "egresos").exists() or not list(
        (tmp_path / "data" / "processed" / "egresos").glob("*.parquet")
    )
