"""Contratos de descarga RAW; fixtures sintéticas, sin red."""

import importlib
import io
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

from openpyxl import Workbook
import pytest

import scripts.run_pipeline as pipeline


COLUMNS = (
    "AÑO;FECHA_DEF;SEXO_NOMBRE;EDAD_TIPO;EDAD_CANT;COD_COMUNA;COMUNA;"
    "NOMBRE_REGION;DIAG1;CAPITULO_DIAG1;GLOSA_CAPITULO_DIAG1;"
    "CODIGO_GRUPO_DIAG1;GLOSA_GRUPO_DIAG1;CODIGO_CATEGORIA_DIAG1;"
    "GLOSA_CATEGORIA_DIAG1;CODIGO_SUBCATEGORIA_DIAG1;GLOSA_SUBCATEGORIA_DIAG1;"
    "DIAG2;CAPITULO_DIAG2;GLOSA_CAPITULO_DIAG2;CODIGO_GRUPO_DIAG2;"
    "GLOSA_GRUPO_DIAG2;CODIGO_CATEGORIA_DIAG2;GLOSA_CATEGORIA_DIAG2;"
    "CODIGO_SUBCATEGORIA_DIAG2;GLOSA_SUBCATEGORIA_DIAG2;LUGAR_DEFUNCION"
).split(";")


def csv_bytes(year: int = 2024, **overrides: str) -> bytes:
    row = dict.fromkeys(COLUMNS, "")
    row.update({"AÑO": str(year), "FECHA_DEF": f"{year}-01-02",
                "SEXO_NOMBRE": "Hombre", "EDAD_TIPO": "1", "EDAD_CANT": "70",
                "COD_COMUNA": "13101", "COMUNA": "Santiago",
                "NOMBRE_REGION": "Metropolitana", "DIAG1": "I219"})
    row.update(overrides)
    return (";".join(COLUMNS) + "\n" + ";".join(row[c] for c in COLUMNS) + "\n").encode("latin-1")


def workbook_bytes(marker: str = "Descripción") -> bytes:
    output = io.BytesIO()
    workbook = Workbook()
    workbook.active.title = "Diccionario Dato Abierto "
    workbook.active.append([marker])
    workbook.create_sheet("Manual de Uso").append(["Manual"])
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def archive_bytes(source, content: bytes | None = None, extra: str | None = None,
                  dictionary: bytes | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(source.csv_filename, content if content is not None else csv_bytes())
        archive.writestr("Diccionario de Datos y Manual de Uso BBDD-COVID19 liberada.xlsx",
                         dictionary if dictionary is not None else workbook_bytes())
        if extra:
            archive.writestr(extra, b"untrusted")
    return output.getvalue()


def paths(tmp_path: Path) -> dict:
    return {"dest_dir": tmp_path / "raw" / "defunciones",
            "cache_dir": tmp_path / "cache",
            "manifest_path": tmp_path / "manifest.json"}


def test_ingestion_preserves_originals_registers_provenance_and_removes_zip(tmp_path):
    module = importlib.import_module("src.data.download_defunciones")
    source = module.DEFUNCIONES_SOURCES[1]
    kwargs = paths(tmp_path)
    content = csv_bytes()
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(archive_bytes(source, content))):
        assert module.ingest_source(source, **kwargs)
    raw = kwargs["dest_dir"] / source.key / source.csv_filename
    assert raw.read_bytes() == content
    assert (raw.parent / module.DICTIONARY_FILENAME).exists()
    entries = json.loads(kwargs["manifest_path"].read_text(encoding="utf-8"))
    assert len(entries) == 2
    snapshot = entries[0]["snapshots"][0]
    assert snapshot["source_url"] == source.url
    assert snapshot["raw_size"] == len(content)
    assert snapshot["transport"]["archive_member"] == source.csv_filename
    assert len(snapshot["transport"]["sha256"]) == 64
    assert not list(kwargs["cache_dir"].rglob("*.zip"))
    assert not list(kwargs["dest_dir"].rglob("*.zip"))


def test_skip_and_identical_force_preserve_raw_and_history(tmp_path):
    module = importlib.import_module("src.data.download_defunciones")
    source = module.DEFUNCIONES_SOURCES[1]
    kwargs = paths(tmp_path)
    payload = archive_bytes(source)
    with patch.object(module.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(payload)) as download:
        assert module.ingest_source(source, **kwargs)
        before = kwargs["manifest_path"].read_bytes()
        assert not module.ingest_source(source, **kwargs)
        assert download.call_count == 1
        raw = kwargs["dest_dir"] / source.key / source.csv_filename
        modified = raw.stat().st_mtime_ns
        assert not module.ingest_source(source, force=True, **kwargs)
        assert raw.stat().st_mtime_ns == modified
        assert kwargs["manifest_path"].read_bytes() == before


@pytest.mark.parametrize("extra", ["../escape.csv", "/absolute.csv", "C:/escape.csv", "..\\escape.csv", "unexpected.txt"])
def test_unsafe_or_unexpected_archive_members_are_rejected(tmp_path, extra):
    module = importlib.import_module("src.data.download_defunciones")
    source = module.DEFUNCIONES_SOURCES[1]
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(archive_bytes(source, extra=extra))):
        with pytest.raises(ValueError):
            module.ingest_source(source, **paths(tmp_path))
    assert not paths(tmp_path)["manifest_path"].exists()
    assert not list(paths(tmp_path)["dest_dir"].rglob("*.csv"))


@pytest.mark.parametrize("content", [b"", b"html error", csv_bytes(2023), csv_bytes() + b"wrong;width\n"])
def test_invalid_csv_does_not_replace_previous_snapshot(tmp_path, content):
    module = importlib.import_module("src.data.download_defunciones")
    source = module.DEFUNCIONES_SOURCES[1]
    kwargs = paths(tmp_path)
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(archive_bytes(source))):
        module.ingest_source(source, **kwargs)
    before = kwargs["manifest_path"].read_bytes()
    raw = kwargs["dest_dir"] / source.key / source.csv_filename
    previous = raw.read_bytes()
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(archive_bytes(source, content))):
        with pytest.raises(ValueError):
            module.ingest_source(source, force=True, **kwargs)
    assert raw.read_bytes() == previous
    assert kwargs["manifest_path"].read_bytes() == before


def test_manifest_failure_rolls_back_both_files(tmp_path):
    module = importlib.import_module("src.data.download_defunciones")
    source = module.DEFUNCIONES_SOURCES[1]
    kwargs = paths(tmp_path)
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(archive_bytes(source))):
        module.ingest_source(source, **kwargs)
    before = kwargs["manifest_path"].read_bytes()
    raw = kwargs["dest_dir"] / source.key / source.csv_filename
    previous = raw.read_bytes()
    real_record = module.record_raw_snapshot
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise OSError("manifest unavailable")
        return real_record(*args, **kwargs)

    changed = archive_bytes(source, csv_bytes(2025), dictionary=workbook_bytes("Updated dictionary"))
    with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(changed)), \
            patch.object(module, "record_raw_snapshot", side_effect=fail_on_second):
        with pytest.raises(OSError):
            module.ingest_source(source, force=True, **kwargs)
    assert raw.read_bytes() == previous
    assert kwargs["manifest_path"].read_bytes() == before


def test_force_changed_source_appends_history_and_preserves_other_entries(tmp_path):
    module = importlib.import_module("src.data.download_defunciones")
    source = module.DEFUNCIONES_SOURCES[1]
    kwargs = paths(tmp_path)
    kwargs["manifest_path"].write_text('[{"source_id":"existing","snapshots":[]}]', encoding="utf-8")
    for year in (2024, 2025):
        with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(archive_bytes(source, csv_bytes(year)))):
            assert module.ingest_source(source, force=True, **kwargs)
    entries = json.loads(kwargs["manifest_path"].read_text(encoding="utf-8"))
    assert entries[0] == {"source_id": "existing", "snapshots": []}
    assert len(entries[1]["snapshots"]) == 2
    assert entries[1]["snapshots"][0]["raw_sha256"] != entries[1]["snapshots"][1]["raw_sha256"]


def test_pipeline_limits_descendants_to_defunciones_branch(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline.sys, "argv", ["run_pipeline.py", "--stage", "download_defunciones"])
    monkeypatch.setattr(pipeline, "run_stage", lambda name, **kwargs: calls.append(name) or True)
    pipeline.main()
    # La rama de Defunciones llega hasta el pronóstico de suicidios, su único consumidor;
    # nunca a Urgencias ni a Egresos.
    assert calls == [
        "download_defunciones", "eda_defunciones", "clean_defunciones",
        "build_mart_suicidios_comuna_weekly", "eda_mart_suicidios_comuna_weekly",
        "benchmark_suicidios", "evaluate_holdout_suicidios", "forecast_suicidios",
    ]


def test_output_contract_rejects_invalid_defunciones_csv(tmp_path):
    raw = tmp_path / "DEFUNCIONES_FUENTE_DEIS_2024_2026_27102026.csv"
    raw.write_bytes(csv_bytes())
    assert pipeline.check_outputs_exist([raw.as_posix()])
    raw.write_bytes(b"wrong;columns\n1;2\n")
    assert not pipeline.check_outputs_exist([raw.as_posix()])
