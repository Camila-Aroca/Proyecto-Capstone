import subprocess
import sys
import json
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scripts.run_pipeline as rp
from src.data.raw_provenance import RAW_SHA256_METADATA_KEY, file_sha256


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


def _write_urgencias_tree(root: Path, raw_hash_in_summary: str | None, processed_hash: str | None,
                          published: bool = False, with_processed: bool = True) -> str:
    """Árbol mínimo relativo al cwd: RAW, summary de ingesta y Parquet anual."""
    raw = root / "data/raw/urgencias/AtencionesUrgencia2026.csv"
    raw.parent.mkdir(parents=True)
    raw.write_text(
        "IdEstablecimiento;IdCausa;Total;fecha;semana\n"
        "01-100;36;1;01/09/2026;36\n", encoding="latin-1"
    )
    actual = file_sha256(raw)
    (root / "data/processed/urgencias").mkdir(parents=True)
    if with_processed:
        table = pa.table({"x": [1]}).replace_schema_metadata(
            {RAW_SHA256_METADATA_KEY: processed_hash.encode()} if processed_hash else None
        )
        pq.write_table(table, root / "data/processed/urgencias/urgencias_rm_2026.parquet")
    entry = {"year": 2026, "published": published, "data_cutoff_date": "2026-09-01"}
    if raw_hash_in_summary:
        entry["raw_sha256"] = raw_hash_in_summary
    (root / "data/processed/deis_ingest_summary.json").write_text(
        json.dumps({"urgencias": [entry]}), encoding="utf-8")
    return actual


def _run_refresh(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rp, "run_date_chile", lambda: date(2026, 10, 3))
    monkeypatch.setattr(rp.subprocess, "run", lambda *args, **kwargs: None)
    return rp.run_stage("download_deis", refresh_current_urgencias=True)


def test_refresh_unchanged_with_aligned_processed_does_not_propagate(monkeypatch, tmp_path):
    raw_hash = _write_urgencias_tree(tmp_path, None, None, with_processed=False)
    # Se reescribe el Parquet con el hash real del RAW vigente.
    (tmp_path / "data/processed/urgencias/urgencias_rm_2026.parquet").unlink(missing_ok=True)
    pq.write_table(
        pa.table({"x": [1]}).replace_schema_metadata({RAW_SHA256_METADATA_KEY: raw_hash.encode()}),
        tmp_path / "data/processed/urgencias/urgencias_rm_2026.parquet",
    )
    assert _run_refresh(monkeypatch, tmp_path) is False


def test_refresh_identical_raw_but_processed_from_previous_raw_forces_rebuild(monkeypatch, tmp_path):
    """RAW nuevo publicado + clean fallido: el siguiente refresh ve RAW idéntico (published=False)."""
    raw_hash = _write_urgencias_tree(tmp_path, None, "0" * 64)
    summary = tmp_path / "data/processed/deis_ingest_summary.json"
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["urgencias"][0]["raw_sha256"] = raw_hash
    summary.write_text(json.dumps(payload), encoding="utf-8")
    assert _run_refresh(monkeypatch, tmp_path) is True


def test_refresh_identical_raw_with_processed_lacking_provenance_forces_rebuild(monkeypatch, tmp_path):
    _write_urgencias_tree(tmp_path, None, None)
    assert _run_refresh(monkeypatch, tmp_path) is True


def test_refresh_identical_raw_with_missing_processed_forces_rebuild(monkeypatch, tmp_path):
    _write_urgencias_tree(tmp_path, None, None, with_processed=False)
    assert _run_refresh(monkeypatch, tmp_path) is True


def test_refresh_fails_if_raw_missing_even_with_exit_zero(monkeypatch, tmp_path):
    _write_urgencias_tree(tmp_path, None, None)
    (tmp_path / "data/raw/urgencias/AtencionesUrgencia2026.csv").unlink()
    with pytest.raises(SystemExit) as failure:
        _run_refresh(monkeypatch, tmp_path)
    assert failure.value.code == 1


def test_failed_clean_then_identical_refresh_recovers_end_to_end(monkeypatch, tmp_path):
    """Refresh 1 publica RAW nuevo y clean falla; refresh 2 (RAW idéntico) debe regenerar."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--refresh-current-urgencias"])
    monkeypatch.setattr(rp, "current_year_chile", lambda: 2026)
    monkeypatch.setattr(rp, "run_date_chile", lambda: date(2026, 10, 3))
    old_hash = "1" * 64
    raw_hash = _write_urgencias_tree(tmp_path, None, old_hash, published=True)
    summary = tmp_path / "data/processed/deis_ingest_summary.json"
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["urgencias"][0]["raw_sha256"] = raw_hash

    def refresh_then_clean(cmd, **kwargs):
        module = cmd[2]
        if module == "src.data.download_deis_sources":
            summary.write_text(json.dumps(payload), encoding="utf-8")
        elif module == "src.data.clean_urgencias":
            attempts.append(cmd)
            if len(attempts) == 1:
                raise subprocess.CalledProcessError(1, cmd)
            pq.write_table(
                pa.table({"x": [1]}).replace_schema_metadata(
                    {RAW_SHA256_METADATA_KEY: raw_hash.encode()}),
                tmp_path / "data/processed/urgencias/urgencias_rm_2026.parquet",
            )
        return None

    attempts: list = []
    monkeypatch.setattr(rp.subprocess, "run", refresh_then_clean)
    monkeypatch.setattr(rp, "check_outputs_exist", lambda outputs: True)

    with pytest.raises(SystemExit):          # 1) publica RAW; clean falla
        rp.main()
    assert len(attempts) == 1

    payload["urgencias"][0]["published"] = False   # 2) misma fuente: RAW idéntico
    rp.main()
    assert len(attempts) == 2                      # clean se ejecutó de nuevo
    assert rp.current_urgencias_processed_is_stale(2026, raw_hash) is False


def test_stage_with_exit_zero_but_missing_outputs_is_not_success(monkeypatch):
    monkeypatch.setattr(rp.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(rp, "check_outputs_exist", lambda outputs: False)
    with pytest.raises(SystemExit) as failure:
        rp.run_stage("clean_egresos", force=True)
    assert failure.value.code == 1


def test_stage_success_validates_its_declared_outputs(monkeypatch):
    seen = []
    monkeypatch.setattr(rp.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(rp, "check_outputs_exist", lambda outputs: seen.append(outputs) or True)
    assert rp.run_stage("clean_egresos", force=True) is True
    assert seen == [rp.STAGES["clean_egresos"]["outputs"]]


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

        # Sin chequeo previo de SKIP (force), pero sí validación posterior del output anual.
        mock_check.assert_called_once_with(["data/processed/urgencias/urgencias_rm_2026.parquet"])
        args = mock_run.call_args[0][0]
        self.assertIn("--year", args)
        self.assertIn("2026", args)
        self.assertIn("--force", args)
