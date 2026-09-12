"""Pruebas de publicación segura del RAW de establecimientos DEIS."""

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from src.data.download_establishments import (
    REQUIRED_COLUMNS,
    detect_csv_format,
    ingest_establishments,
    validate_and_preview,
)


def _valid_csv() -> bytes:
    headers = sorted(REQUIRED_COLUMNS)
    return (";".join(headers) + "\n" + ";".join("valor" for _ in headers) + "\n").encode()


def test_detect_csv_format_semicolon(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_bytes(_valid_csv())
    assert detect_csv_format(path)[1] == ";"
    assert validate_and_preview(path)[0]


def test_download_is_temporary_and_publication_is_safe(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "establecimientos_salud_actualizado.csv"
    cache_dir = tmp_path / ".cache" / "downloads"
    manifest = tmp_path / "raw" / "provenance_manifest.json"
    with patch("src.data.download_establishments.urllib.request.urlopen", return_value=io.BytesIO(_valid_csv())):
        assert ingest_establishments(force=True, url="https://example.test/establecimientos.csv",
                                    raw_path=raw_path, cache_dir=cache_dir, manifest_path=manifest)

    assert raw_path.read_bytes() == _valid_csv()
    assert not list(raw_path.parent.glob("*.tmp"))
    assert not list(cache_dir.iterdir())
    assert "deis_establecimientos" in manifest.read_text(encoding="utf-8")


def test_invalid_csv_does_not_replace_previous_raw_and_cleans_temporary(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "establecimientos_salud_actualizado.csv"
    raw_path.parent.mkdir()
    raw_path.write_bytes(b"previous raw")
    cache_dir = tmp_path / ".cache" / "downloads"
    with patch("src.data.download_establishments.urllib.request.urlopen", return_value=io.BytesIO(b"html,error\n")):
        with pytest.raises(ValueError, match="columnas mínimas"):
            ingest_establishments(force=True, url="https://example.test/invalid.csv",
                                raw_path=raw_path, cache_dir=cache_dir,
                                manifest_path=tmp_path / "manifest.json")

    assert raw_path.read_bytes() == b"previous raw"
    assert not cache_dir.exists() or not list(cache_dir.iterdir())
