import subprocess
import sys
import json
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import scripts.run_pipeline as rp


def test_refresh_current_urgencias_only_runs_affected_branch(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--refresh-current-urgencias"])
    monkeypatch.setattr(rp, "current_year_chile", lambda: 2027)
    monkeypatch.setattr(rp, "run_stage", lambda stage, **kwargs: calls.append((stage, kwargs)) or False)
    rp.main()
    assert [stage for stage, _ in calls] == [
        "download_deis", "clean_urgencias", "eda_urgencias"
    ]
    assert calls[1][1]["year"] == 2027


def test_changed_snapshot_forces_only_current_downstream(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--refresh-current-urgencias"])
    monkeypatch.setattr(rp, "current_year_chile", lambda: 2026)

    def stage(name, **kwargs):
        calls.append((name, kwargs))
        return name in {"download_deis", "clean_urgencias"}

    monkeypatch.setattr(rp, "run_stage", stage)
    rp.main()
    assert [name for name, _ in calls] == [
        "download_deis", "clean_urgencias", "eda_urgencias"
    ]
    assert all(kwargs["upstream_changed"] for _, kwargs in calls[1:])
    assert all(not kwargs["force"] for _, kwargs in calls)


def test_force_refresh_with_identical_snapshot_does_not_force_downstream(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--refresh-current-urgencias", "--force"])
    monkeypatch.setattr(rp, "current_year_chile", lambda: 2026)
    monkeypatch.setattr(rp, "run_stage", lambda name, **kwargs: calls.append((name, kwargs)) or False)
    rp.main()
    assert calls[0][1]["force"]
    assert all(not kwargs["force"] and not kwargs["upstream_changed"]
               for _, kwargs in calls[1:])


def test_refresh_unchanged_does_not_propagate(monkeypatch, tmp_path):
    summary = tmp_path / "deis_ingest_summary.json"
    summary.write_text(json.dumps({"urgencias": [{"published": False,
        "data_cutoff_date": "2026-09-01"}]}), encoding="utf-8")
    real_path = rp.Path
    monkeypatch.setattr(rp, "run_date_chile", lambda: date(2026, 10, 3))
    monkeypatch.setattr(rp, "Path", lambda value: summary if value ==
                        "data/processed/deis_ingest_summary.json" else real_path(value))
    monkeypatch.setattr(rp.subprocess, "run", lambda *args, **kwargs: None)
    assert not rp.run_stage("download_deis", refresh_current_urgencias=True)


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

def test_censo_cartografia_stages_are_registered():
    """El download y clean de las 5 capas de cartografia Censo 2024 deben estar en el DAG."""
    assert rp.STAGES["download_censo"]["depends_on"] == []
    assert rp.STAGES["clean_censo"]["depends_on"] == ["download_censo"]
    assert "download_censo" in rp.PIPELINE_ORDER
    assert "clean_censo" in rp.PIPELINE_ORDER
    assert rp.PIPELINE_ORDER.index("download_censo") < rp.PIPELINE_ORDER.index("clean_censo")

    download_outputs = rp.STAGES["download_censo"]["outputs"]
    for capa in ("Comunal", "Distrital", "Zonal", "Entidades", "Manzanas"):
        assert any(capa in out for out in download_outputs), f"Falta capa {capa} en outputs de download_censo"
    assert any("Diccionario_variables_geograficas" in out for out in download_outputs)

    clean_outputs = rp.STAGES["clean_censo"]["outputs"]
    for capa in ("Comunal", "Distrital", "Zonal", "Entidades", "Manzanas"):
        assert any(f"RM_{capa}" in out for out in clean_outputs), f"Falta capa RM {capa} en outputs de clean_censo"


def test_censo_poblacion_stages_are_registered():
    """El download y clean de población comunal Censo 2024 deben estar en el DAG."""
    assert rp.STAGES["download_censo_poblacion"]["depends_on"] == []
    assert rp.STAGES["clean_censo_poblacion"]["depends_on"] == ["download_censo_poblacion"]
    assert "download_censo_poblacion" in rp.PIPELINE_ORDER
    assert "clean_censo_poblacion" in rp.PIPELINE_ORDER
    assert rp.PIPELINE_ORDER.index("download_censo_poblacion") < rp.PIPELINE_ORDER.index("clean_censo_poblacion")


def test_poblacion_proyecciones_stages_are_registered():
    """El download y clean de la dimensión anual de población (INE) deben estar en el DAG."""
    assert rp.STAGES["download_poblacion_proyecciones"]["depends_on"] == []
    assert rp.STAGES["clean_poblacion_proyecciones"]["depends_on"] == [
        "download_poblacion_proyecciones", "clean_censo_poblacion"
    ]
    assert "download_poblacion_proyecciones" in rp.PIPELINE_ORDER
    assert "clean_poblacion_proyecciones" in rp.PIPELINE_ORDER
    assert (
        rp.PIPELINE_ORDER.index("download_poblacion_proyecciones")
        < rp.PIPELINE_ORDER.index("clean_poblacion_proyecciones")
    )
    assert (
        rp.PIPELINE_ORDER.index("clean_censo_poblacion")
        < rp.PIPELINE_ORDER.index("clean_poblacion_proyecciones")
    )
    assert (
        rp.PIPELINE_ORDER.index("clean_poblacion_proyecciones")
        < rp.PIPELINE_ORDER.index("build_urgencias_comuna_marts")
    )


def test_pobreza_comunal_stages_are_registered():
    """El download y clean de la dimensión de vulnerabilidad comunal (MDS/Casen) deben estar en el DAG."""
    assert rp.STAGES["download_pobreza_comunal"]["depends_on"] == []
    assert rp.STAGES["clean_pobreza_comunal"]["depends_on"] == [
        "download_pobreza_comunal", "clean_censo_poblacion"
    ]
    assert "download_pobreza_comunal" in rp.PIPELINE_ORDER
    assert "clean_pobreza_comunal" in rp.PIPELINE_ORDER
    assert (
        rp.PIPELINE_ORDER.index("download_pobreza_comunal")
        < rp.PIPELINE_ORDER.index("clean_pobreza_comunal")
    )
    assert (
        rp.PIPELINE_ORDER.index("clean_censo_poblacion")
        < rp.PIPELINE_ORDER.index("clean_pobreza_comunal")
    )


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
        """Si falta un CSV canÃ³nico (ej. egresos_2023), download_deis NO hace skip."""
        outputs = rp.STAGES["download_deis"]["outputs"]
        
        def path_side_effect(out):
            mock_p = MagicMock()
            if "egresos_2023" in out:
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
        outputs = ["data/raw/egresos/egresos_2020.csv"]
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

    @patch('scripts.run_pipeline.subprocess.run')
    @patch('scripts.run_pipeline.check_outputs_exist')
    def test_clean_urgencias_year_targets_one_output_and_forwards_year(
        self, mock_check, mock_run
    ):
        rp.run_stage("clean_urgencias", force=True, year=2026)

        mock_check.assert_not_called()
        args = mock_run.call_args[0][0]
        self.assertIn("--year", args)
        self.assertIn("2026", args)
        self.assertIn("--force", args)
