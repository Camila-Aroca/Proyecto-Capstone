import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import scripts.run_pipeline as rp


def test_pipeline_help_command():
    """Prueba que el orquestador responde correctamente al argumento --help."""
    result = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Orquestador del Pipeline de Datos" in result.stdout
    assert "--stage" in result.stdout

def test_pipeline_invalid_stage():
    """Prueba que el orquestador falla de forma controlada ante una etapa inválida."""
    result = subprocess.run(
        [sys.executable, "scripts/run_pipeline.py", "--stage", "fake_stage"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr

class TestPipelineIdempotency(unittest.TestCase):
    
    @patch('scripts.run_pipeline.Path')
    @patch('pyarrow.parquet.read_schema')
    def test_clean_urgencias_skip_condition(self, mock_read_schema, mock_path):
        """Si falta un solo parquet (ej 2022), check_outputs_exist debe devolver False."""
        outputs = rp.STAGES["clean_urgencias"]["outputs"]
        
        def path_side_effect(out):
            mock_p = MagicMock()
            if "2022" in out:
                mock_p.exists.return_value = False
            else:
                mock_p.exists.return_value = True
                mock_p.stat.return_value.st_size = 100
                mock_p.suffix = '.parquet'
            return mock_p
            
        mock_path.side_effect = path_side_effect
        mock_read_schema.return_value.names = ['col1']
        
        self.assertFalse(rp.check_outputs_exist(outputs))
        
        # Ahora si todos existen
        def path_side_effect_all_exist(out):
            mock_p = MagicMock()
            mock_p.exists.return_value = True
            mock_p.stat.return_value.st_size = 100
            mock_p.suffix = '.parquet'
            return mock_p
            
        mock_path.side_effect = path_side_effect_all_exist
        self.assertTrue(rp.check_outputs_exist(outputs))

    @patch('scripts.run_pipeline.Path')
    def test_download_deis_skip_condition(self, mock_path):
        """Si falta un CSV (ej. EGRESOS_2023), download_deis NO hace skip."""
        outputs = rp.STAGES["download_deis"]["outputs"]
        
        def path_side_effect(out):
            mock_p = MagicMock()
            if "EGRESOS_2023" in out:
                mock_p.exists.return_value = False
            else:
                mock_p.exists.return_value = True
                mock_p.stat.return_value.st_size = 100
                mock_p.suffix = '.csv'
            return mock_p
            
        mock_path.side_effect = path_side_effect
        self.assertFalse(rp.check_outputs_exist(outputs))

    @patch('scripts.run_pipeline.Path')
    @patch('pandas.read_csv')
    def test_csv_corrupto(self, mock_read_csv, mock_path):
        outputs = ["data/raw/egresos/EGRESOS_2020.csv"]
        mock_p = MagicMock()
        mock_p.exists.return_value = True
        mock_p.stat.return_value.st_size = 100
        mock_p.suffix = '.csv'
        mock_path.return_value = mock_p
        
        # Simular lectura de cabecera vacía
        mock_read_csv.return_value.columns = []
        
        self.assertFalse(rp.check_outputs_exist(outputs))
        
    @patch('scripts.run_pipeline.Path')
    @patch('pyarrow.parquet.read_schema')
    def test_parquet_corrupto(self, mock_read_schema, mock_path):
        outputs = ["data/processed/urgencias/urgencias_rm_2020.parquet"]
        mock_p = MagicMock()
        mock_p.exists.return_value = True
        mock_p.stat.return_value.st_size = 100
        mock_p.suffix = '.parquet'
        mock_path.return_value = mock_p
        
        # Simular esquema vacío
        mock_read_schema.return_value.names = []
        
        self.assertFalse(rp.check_outputs_exist(outputs))

    @patch('scripts.run_pipeline.subprocess.run')
    @patch('scripts.run_pipeline.check_outputs_exist')
    def test_force_propagates(self, mock_check, mock_run):
        mock_check.return_value = True
        
        rp.run_stage("download_deis", force=True)
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("--force", args)
