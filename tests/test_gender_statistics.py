"""Pruebas de ingesta y normalización de fuentes contextuales de género."""

import io
import json
from pathlib import Path

from openpyxl import Workbook
import pyarrow.parquet as pq

import scripts.run_pipeline as pipeline
from src.data import download_gender_statistics as download
from src.data import normalize_gender_statistics as normalize


def _save_workbook(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    workbook = Workbook()
    first_sheet = workbook.active
    first_name, first_rows = next(iter(sheets.items()))
    first_sheet.title = first_name
    for row in first_rows:
        first_sheet.append(row)
    for name, rows in list(sheets.items())[1:]:
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    workbook.save(path)
    workbook.close()


def test_download_source_publishes_valid_raw_and_appends_provenance(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture.xlsx"
    _save_workbook(fixture, {"NACIONAL": [["título"], ["dato"]]})
    content = fixture.read_bytes()
    raw_dir = tmp_path / "raw"
    cache_dir = tmp_path / "cache"
    manifest = raw_dir / "provenance_manifest.json"
    monkeypatch.setattr(download, "RAW_DIR", raw_dir)
    monkeypatch.setattr(download, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(download, "MANIFEST_PATH", manifest)

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *args, **kwargs: Response(content))
    source = {"id": "test", "filename": "test.xlsx", "url": "https://example.test/test.xlsx"}

    assert download.download_source(source) is True
    assert (raw_dir / "test.xlsx").read_bytes() == content
    saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(saved_manifest) == 1
    assert saved_manifest[0]["source_url"] == source["url"]
    assert saved_manifest[0]["file_size"] == len(content)
    assert len(saved_manifest[0]["sha256"]) == 64

    assert download.download_source(source) is False
    assert len(json.loads(manifest.read_text(encoding="utf-8"))) == 1


def test_append_provenance_preserves_snapshot_history(tmp_path, monkeypatch):
    raw_path = tmp_path / "raw.xlsx"
    raw_path.write_bytes(b"one")
    manifest = tmp_path / "provenance_manifest.json"
    monkeypatch.setattr(download, "MANIFEST_PATH", manifest)
    source = {"id": "test", "filename": "raw.xlsx", "url": "https://example.test/raw.xlsx"}

    download.append_provenance(source, raw_path, raw_path, "2026-01-01T00:00:00+00:00")
    raw_path.write_bytes(b"two")
    download.append_provenance(source, raw_path, raw_path, "2026-01-02T00:00:00+00:00")

    manifest_rows = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(manifest_rows) == 2
    assert manifest_rows[0]["sha256"] != manifest_rows[1]["sha256"]


def test_parse_suicidio_regional_preserves_symbol_and_column_offset(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    filename = raw_dir / normalize.SOURCE_FILES["suicidio_ratio_hm_tasas_nacional_regional"]
    _save_workbook(filename, {
        "NACIONAL": [
            ["título"], [], ["año"],
            [2023, 100, 80, 20, 1000, 500, 500, 10.0, 16.0, 4.0, 4.0],
        ],
        "REGIONAL": [
            ["título"], [], ["año"],
            [2022, "Metropolitana", 13, 20, 15, 5, 100, 50, 50, 20.0, 30.0, 10.0, "-"],
        ],
    })
    monkeypatch.setattr(normalize, "RAW_DIR", raw_dir)

    records = normalize.parse_suicidio_ratio_tasas()
    regional_total = next(
        row for row in records
        if row["source_sheet"] == "REGIONAL" and row["indicator"] == "defunciones_suicidio" and row["sex"] == "Total"
    )
    regional_ratio = next(
        row for row in records
        if row["source_sheet"] == "REGIONAL" and row["indicator"] == "ratio_defunciones_suicidio"
    )
    assert regional_total["value"] == 20.0
    assert regional_total["geography"] == "Metropolitana"
    assert regional_ratio["value"] is None
    assert regional_ratio["value_text"] == "-"


def test_write_records_uses_schema_and_rejects_natural_key_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(normalize, "PROCESSED_DIR", tmp_path)
    source_id = "prevalencia_sintomas_depresivos_sexo"
    record = normalize._record(
        source_id, "NACIONAL", "nacional", "Nacional", None, "2003", 2003,
        "Hombres", "prevalencia_sintomas_depresivos_ultimo_ano", 10.4, "%",
    )
    output = normalize.write_records(source_id, [record])
    assert pq.read_table(output).schema == normalize.SCHEMA
    try:
        normalize.validate_records([record, record], source_id)
    except ValueError as error:
        assert "Duplicado" in str(error)
    else:
        raise AssertionError("Se esperaba detección de duplicado según clave natural.")


def test_gender_context_stages_are_registered_in_the_dag():
    assert pipeline.STAGES["normalize_contexto_genero"]["depends_on"] == ["download_contexto_genero"]
    assert pipeline.STAGES["eda_contexto_genero"]["depends_on"] == ["normalize_contexto_genero"]
    assert pipeline.PIPELINE_ORDER.index("download_contexto_genero") < pipeline.PIPELINE_ORDER.index("normalize_contexto_genero")
