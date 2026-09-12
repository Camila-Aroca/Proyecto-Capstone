"""Pruebas de ingesta RAW segura para la cartografía comunal del Censo."""

import io
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point

from src.data.download_censo import TARGET_FILE_NAME, ingest_censo


def _geoparquet_bytes() -> bytes:
    schema = pa.schema(
        [("CUT", pa.int64()), ("COMUNA", pa.string()), ("COD_REGION", pa.int64()), ("SHAPE", pa.binary())],
        metadata={b"geo": json.dumps({"columns": {"SHAPE": {"encoding": "WKB"}}}).encode()},
    )
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_arrays(
        [pa.array([13101]), pa.array(["Santiago"]), pa.array([13]), pa.array([Point(0, 0).wkb])], schema=schema,
    ), sink)
    return sink.getvalue().to_pybytes()


def _zip_payload(member_data: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"cartografia/{TARGET_FILE_NAME}", member_data)
    return buffer.getvalue()


def test_transport_is_outside_raw_and_is_cleaned_after_success(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / TARGET_FILE_NAME
    cache_dir = tmp_path / ".cache" / "downloads"
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(_zip_payload(_geoparquet_bytes()))):
        assert ingest_censo(force=True, url="https://example.test/censo.zip", raw_path=raw_path,
                            cache_dir=cache_dir, manifest_path=tmp_path / "manifest.json")

    assert raw_path.is_file()
    assert not list(raw_path.parent.glob("*.zip"))
    assert not list(cache_dir.glob("*.zip"))


def test_invalid_extraction_preserves_previous_raw(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / TARGET_FILE_NAME
    raw_path.parent.mkdir()
    raw_path.write_bytes(b"previous raw")
    cache_dir = tmp_path / ".cache" / "downloads"
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(_zip_payload(b"not parquet"))):
        with pytest.raises(Exception):
            ingest_censo(force=True, url="https://example.test/censo.zip", raw_path=raw_path,
                         cache_dir=cache_dir, manifest_path=tmp_path / "manifest.json")

    assert raw_path.read_bytes() == b"previous raw"
    assert list(cache_dir.glob("*.zip"))


def test_safe_publication_replaces_only_validated_candidate(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / TARGET_FILE_NAME
    raw_path.parent.mkdir()
    raw_path.write_bytes(b"old")
    with patch("src.data.download_censo.urllib.request.urlopen", return_value=io.BytesIO(_zip_payload(_geoparquet_bytes()))):
        ingest_censo(force=True, url="https://example.test/censo.zip", raw_path=raw_path,
                     cache_dir=tmp_path / ".cache", manifest_path=tmp_path / "manifest.json")

    assert raw_path.read_bytes() != b"old"
    assert not list(raw_path.parent.glob("*.tmp"))
