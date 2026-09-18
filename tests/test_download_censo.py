"""Pruebas de ingesta RAW segura para la cartografía Censo 2024 (comunal + subcomunal)."""

import io
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point

from src.data.download_censo import (
    DICTIONARY_FILE_NAME,
    LAYER_FILE_NAMES,
    REQUIRED_DICTIONARY_SHEETS,
    ingest_censo,
)


def _geoparquet_bytes(cut: int = 13101) -> bytes:
    schema = pa.schema(
        [("CUT", pa.int64()), ("COMUNA", pa.string()), ("COD_REGION", pa.int64()), ("SHAPE", pa.binary())],
        metadata={b"geo": json.dumps({"columns": {"SHAPE": {"encoding": "WKB"}}}).encode()},
    )
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_arrays(
        [pa.array([cut]), pa.array(["Santiago"]), pa.array([13]), pa.array([Point(0, 0).wkb])], schema=schema,
    ), sink)
    return sink.getvalue().to_pybytes()


def _dictionary_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_name in REQUIRED_DICTIONARY_SHEETS:
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(["Nombre de campo", "Tipo", "Descripcion", "Visualizacion"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _zip_payload(*, replace: dict[str, bytes] | None = None, omit: set[str] | None = None) -> bytes:
    """Construye un ZIP con los 5 miembros de capas + diccionario, con overrides opcionales."""
    replace = replace or {}
    omit = omit or set()
    members = {name: _geoparquet_bytes() for name in LAYER_FILE_NAMES.values()}
    members[DICTIONARY_FILE_NAME] = _dictionary_bytes()
    members.update(replace)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for filename, data in members.items():
            if filename in omit:
                continue
            archive.writestr(f"cartografia/{filename}", data)
    return buffer.getvalue()


def _raw_paths(tmp_path: Path) -> dict[str, Path]:
    raw_dir = tmp_path / "raw"
    return {name: raw_dir / fname for name, fname in LAYER_FILE_NAMES.items()}


def test_transport_is_outside_raw_and_is_cleaned_after_success(tmp_path: Path) -> None:
    raw_paths = _raw_paths(tmp_path)
    dictionary_path = tmp_path / "raw" / DICTIONARY_FILE_NAME
    cache_dir = tmp_path / ".cache" / "downloads"
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(_zip_payload())):
        published = ingest_censo(force=True, url="https://example.test/censo.zip", raw_paths=raw_paths,
                                  dictionary_path=dictionary_path, cache_dir=cache_dir,
                                  manifest_path=tmp_path / "manifest.json")

    assert all(published.values())
    for path in list(raw_paths.values()) + [dictionary_path]:
        assert path.is_file()
    assert not list(raw_paths["Comunal"].parent.glob("*.zip"))
    assert not list(cache_dir.glob("*.zip"))


def test_skip_when_all_targets_already_valid(tmp_path: Path) -> None:
    raw_paths = _raw_paths(tmp_path)
    dictionary_path = tmp_path / "raw" / DICTIONARY_FILE_NAME
    cache_dir = tmp_path / ".cache" / "downloads"

    def _urlopen_should_not_be_called(*args, **kwargs):
        raise AssertionError("No debería descargarse el ZIP si todos los objetivos ya son válidos.")

    # Publica un snapshot inicial válido.
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(_zip_payload())):
        ingest_censo(force=True, url="https://example.test/censo.zip", raw_paths=raw_paths,
                     dictionary_path=dictionary_path, cache_dir=cache_dir,
                     manifest_path=tmp_path / "manifest.json")

    with patch("src.data.download_censo.urllib.request.urlopen", side_effect=_urlopen_should_not_be_called):
        published = ingest_censo(force=False, url="https://example.test/censo.zip", raw_paths=raw_paths,
                                  dictionary_path=dictionary_path, cache_dir=cache_dir,
                                  manifest_path=tmp_path / "manifest.json")

    assert not any(published.values())


def test_invalid_member_preserves_only_its_previous_raw(tmp_path: Path) -> None:
    raw_paths = _raw_paths(tmp_path)
    dictionary_path = tmp_path / "raw" / DICTIONARY_FILE_NAME
    dictionary_path.parent.mkdir(parents=True)
    for path in list(raw_paths.values()) + [dictionary_path]:
        path.write_bytes(b"previous raw " + path.name.encode())
    cache_dir = tmp_path / ".cache" / "downloads"

    broken_zip = _zip_payload(replace={LAYER_FILE_NAMES["Manzanas"]: b"not parquet"})
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(broken_zip)):
        with pytest.raises(Exception):
            ingest_censo(force=True, url="https://example.test/censo.zip", raw_paths=raw_paths,
                         dictionary_path=dictionary_path, cache_dir=cache_dir,
                         manifest_path=tmp_path / "manifest.json")

    assert raw_paths["Manzanas"].read_bytes() == b"previous raw " + raw_paths["Manzanas"].name.encode()
    # El ZIP fallido se conserva fuera de RAW para diagnóstico.
    assert list(cache_dir.glob("*.zip"))


def test_safe_publication_replaces_only_validated_candidate(tmp_path: Path) -> None:
    raw_paths = _raw_paths(tmp_path)
    dictionary_path = tmp_path / "raw" / DICTIONARY_FILE_NAME
    dictionary_path.parent.mkdir(parents=True)
    for path in list(raw_paths.values()) + [dictionary_path]:
        path.write_bytes(b"old")
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(_zip_payload())):
        ingest_censo(force=True, url="https://example.test/censo.zip", raw_paths=raw_paths,
                     dictionary_path=dictionary_path, cache_dir=tmp_path / ".cache",
                     manifest_path=tmp_path / "manifest.json")

    for path in list(raw_paths.values()) + [dictionary_path]:
        assert path.read_bytes() != b"old"
        assert not list(path.parent.glob("*.tmp"))
