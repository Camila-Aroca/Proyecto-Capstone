"""Tests for the stable Egresos RAW contract published by DEIS downloads."""

import io
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

import pytest

from src.data.download_deis_sources import (
    canonical_egresos_raw_path,
    extract_canonical_egresos_csv,
    ingest_deis_source,
    migrate_legacy_egresos_raw,
    record_deis_snapshot,
)


@pytest.mark.parametrize(
    ("year", "published_name"),
    [
        (2020, "EGRE_DATOS_ABIERTOS_2020.csv"),
        (2024, "EGR_DATOS_ABIERTO_2024.csv"),
    ],
)
def test_extract_egresos_uses_canonical_name_for_deis_variants(
    tmp_path: Path, year: int, published_name: str
) -> None:
    archive_path = tmp_path / f"EGRESOS_{year}.zip"
    content = "ANO_EGRESO;DIAG1\n2024;F32\n".encode("utf-8")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(published_name, content)
        archive.writestr(
            "Diccionario BD egresos hospitalario.xlsx",
            b"PK\x05\x06" + b"\x00" * 18,
        )

    result = extract_canonical_egresos_csv(archive_path, year, tmp_path)

    expected_path = tmp_path / canonical_egresos_raw_path(year).name
    assert result["raw_path"] == expected_path
    assert result["archive_member"] == published_name
    assert expected_path.read_bytes() == content


def test_extract_egresos_rejects_ambiguous_csv_members(tmp_path: Path) -> None:
    archive_path = tmp_path / "EGRESOS_2024.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("first.csv", b"a\n1\n")
        archive.writestr("second.csv", b"a\n2\n")

    with pytest.raises(ValueError, match="exactly one"):
        extract_canonical_egresos_csv(archive_path, 2024, tmp_path)


def _zip_bytes(member_name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    dictionary = io.BytesIO()
    with zipfile.ZipFile(dictionary, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types />")
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member_name, content)
        archive.writestr("diccionario.xlsx", dictionary.getvalue())
    return buffer.getvalue()


def test_ingest_downloads_outside_raw_and_cleans_zip_after_success(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    cache_dir = tmp_path / ".cache" / "downloads"
    manifest = tmp_path / "manifest.json"
    payload = _zip_bytes("nombre_variable_2024.csv", b"ANO_EGRESO;DIAG1\n2024;F32\n")

    with patch("src.data.download_deis_sources.urllib.request.urlopen", return_value=io.BytesIO(payload)):
        result = ingest_deis_source("egresos", 2024, "https://example.test/EGRESOS_2024.zip", raw_dir, cache_dir=cache_dir, manifest_path=manifest)

    assert result["raw_path"].endswith("egresos_2024.csv")
    assert (raw_dir / "egresos_2024.csv").is_file()
    assert not list(cache_dir.glob("*.zip"))
    assert not list(raw_dir.glob("*.zip"))
    assert (raw_dir / "diccionario.xlsx").is_file()


def test_ingest_failure_preserves_previous_raw_and_leaves_no_partial_canonical(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    canonical = raw_dir / "egresos_2024.csv"
    canonical.write_bytes(b"previous raw")
    cache_dir = tmp_path / ".cache" / "downloads"
    bad_payload = _zip_bytes("variable.csv", b"not-a-delimited-header\n")

    with patch("src.data.download_deis_sources.urllib.request.urlopen", return_value=io.BytesIO(bad_payload)):
        with pytest.raises(ValueError, match="sin cabecera"):
            ingest_deis_source("egresos", 2024, "https://example.test/bad.zip", raw_dir, force=True, cache_dir=cache_dir, manifest_path=tmp_path / "manifest.json")

    assert canonical.read_bytes() == b"previous raw"
    assert not list(raw_dir.glob("*.tmp"))
    assert list(cache_dir.glob("*.zip"))  # retained only outside RAW for diagnosis


def test_provenance_appends_snapshot_history(tmp_path: Path) -> None:
    zip_path = tmp_path / "source.zip"
    raw_path = tmp_path / "egresos_2024.csv"
    zip_path.write_bytes(b"zip bytes")
    raw_path.write_bytes(b"raw bytes")
    manifest = tmp_path / "manifest.json"

    record_deis_snapshot("egresos", 2024, "https://example.test/a.zip", zip_path, raw_path, "a.csv", manifest, "2026-01-01T00:00:00+00:00")
    record_deis_snapshot("egresos", 2024, "https://example.test/b.zip", zip_path, raw_path, "b.csv", manifest, "2026-01-02T00:00:00+00:00")

    entry = json.loads(manifest.read_text(encoding="utf-8"))[0]
    assert entry["source_id"] == "deis_egresos_2024"
    assert [snapshot["archive_member"] for snapshot in entry["snapshots"]] == ["a.csv", "b.csv"]


def test_migrate_legacy_egresos_preserves_bytes_and_legacy_file(tmp_path: Path) -> None:
    legacy = tmp_path / "EGR_DATOS_ABIERTO_2024.csv"
    legacy.write_bytes(b"ANO_EGRESO;DIAG1\n2024;F32\n")

    result = migrate_legacy_egresos_raw(tmp_path)

    canonical = tmp_path / "egresos_2024.csv"
    assert canonical.read_bytes() == legacy.read_bytes()
    assert legacy.exists()
    assert result == [
        {
            "year": 2024,
            "legacy_path": legacy.as_posix(),
            "canonical_path": canonical.as_posix(),
            "legacy_sha256": result[0]["legacy_sha256"],
            "canonical_sha256": result[0]["legacy_sha256"],
            "identical": True,
            "migrated": True,
        }
    ]
