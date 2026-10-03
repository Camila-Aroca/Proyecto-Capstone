"""Reloj, corte observado y refresco mutable de Urgencias."""

from __future__ import annotations

import io
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
import zipfile

import pandas as pd
import pytest

from src.chile_time import current_year_chile, run_date_chile, run_datetime_chile
from src.data.clean_urgencias import fecha_bounds_urgencias
from src.data.download_deis_sources import (
    ingest_deis_source, urgencias_data_cutoff, urgencias_sources,
)
import src.data.download_deis_sources as deis


def test_chile_zone_and_year_across_new_year() -> None:
    instant = datetime(2027, 1, 1, 2, 0, tzinfo=timezone.utc)
    assert run_datetime_chile(instant).tzinfo.key == "America/Santiago"
    assert run_date_chile(instant) == date(2026, 12, 31)
    assert current_year_chile(instant) == 2026
    assert current_year_chile(datetime(2027, 1, 1, 4, tzinfo=timezone.utc)) == 2027
    assert run_datetime_chile(datetime(2026, 1, 1, tzinfo=timezone.utc)).utcoffset() != (
        run_datetime_chile(datetime(2026, 6, 1, tzinfo=timezone.utc)).utcoffset()
    )
    with pytest.raises(ValueError, match="zona horaria"):
        run_date_chile(datetime(2027, 1, 1))


def test_current_year_source_is_dynamic() -> None:
    sources = urgencias_sources(2027)
    assert sources[-1]["year"] == 2027
    assert sources[-1]["url"].endswith("AtencionesUrgencia2027.zip")


def _urgencias_csv(last_day: str) -> bytes:
    return (
        "IdEstablecimiento;IdCausa;Total;fecha;semana;CodigoRegion\n"
        f"01-100;36;1;01/09/2026;35;13\n01-100;36;2;{last_day};35;13\n"
    ).encode("latin-1")


def _archive(content: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("AtencionesUrgencia2026.csv", content)
    return output.getvalue()


def test_cutoff_comes_from_csv_not_run_date(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_bytes(_urgencias_csv("08/09/2026"))
    with patch("src.data.download_deis_sources.run_date_chile", return_value=date(2026, 10, 3)):
        assert urgencias_data_cutoff(path, 2026) == date(2026, 9, 8)


def test_eda_bounds_parse_dd_mm_yyyy_chronologically() -> None:
    assert fecha_bounds_urgencias(pd.Series([
        "31/08/2026", "01/09/2026", "02/10/2026"
    ])) == ("31/08/2026", "02/10/2026")


def test_refresh_records_provenance_and_skips_identical_snapshot(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    cache = tmp_path / "cache"
    manifest = tmp_path / "manifest.json"
    payload = _archive(_urgencias_csv("08/09/2026"))
    url = "https://example.test/AtencionesUrgencia2026.zip"

    def download(_url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    with patch("src.data.download_deis_sources._download_zip", side_effect=download), patch(
        "src.data.download_deis_sources.run_date_chile", return_value=date(2026, 10, 3)
    ):
        first = ingest_deis_source("urgencias", 2026, url, raw_dir,
                                   cache_dir=cache, manifest_path=manifest, refresh_current=True)
        second = ingest_deis_source("urgencias", 2026, url, raw_dir,
                                    cache_dir=cache, manifest_path=manifest, refresh_current=True)

    assert first["published"] and not second["published"] and second["unchanged"]
    assert first["data_cutoff_date"] == "2026-09-08"
    assert (raw_dir / "AtencionesUrgencia2026.csv").read_bytes() == _urgencias_csv("08/09/2026")
    snapshots = json.loads(manifest.read_text(encoding="utf-8"))[0]["snapshots"]
    assert len(snapshots) == 1
    assert all(s["source_url"] == url and s["zip_size"] > 0 and s["raw_size"] > 0
               and len(s["zip_sha256"]) == len(s["raw_sha256"]) == 64
               and s["downloaded_at"] for s in snapshots)


def test_identical_legacy_raw_records_only_verified_download(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "AtencionesUrgencia2026.csv").write_bytes(_urgencias_csv("08/09/2026"))
    manifest = tmp_path / "manifest.json"
    payload = _archive(_urgencias_csv("08/09/2026"))

    def download(_url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    with patch("src.data.download_deis_sources._download_zip", side_effect=download), patch(
        "src.data.download_deis_sources.run_date_chile", return_value=date(2026, 10, 3)
    ):
        result = ingest_deis_source("urgencias", 2026, "https://example.test/source.zip",
                                    raw_dir, cache_dir=tmp_path / "cache",
                                    manifest_path=manifest, refresh_current=True)
    assert not result["published"]
    snapshots = json.loads(manifest.read_text(encoding="utf-8"))[0]["snapshots"]
    assert len(snapshots) == 1
    assert snapshots[0]["source_url"] == "https://example.test/source.zip"


def test_bad_refresh_preserves_previous_raw(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    old = raw_dir / "AtencionesUrgencia2026.csv"
    old.write_bytes(_urgencias_csv("08/09/2026"))
    bad = _archive(_urgencias_csv("08/09/2027"))

    def download(_url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(bad)

    with patch("src.data.download_deis_sources._download_zip", side_effect=download), patch(
        "src.data.download_deis_sources.run_date_chile", return_value=date(2026, 10, 3)
    ):
        with pytest.raises(ValueError, match="fuera del año"):
            ingest_deis_source("urgencias", 2026, "https://example.test/source.zip", raw_dir,
                               cache_dir=tmp_path / "cache", manifest_path=tmp_path / "manifest.json",
                               refresh_current=True)
    assert old.read_bytes() == _urgencias_csv("08/09/2026")


def test_refresh_changed_snapshot_appends_only_real_publications(tmp_path: Path) -> None:
    raw_dir, cache, manifest = tmp_path / "raw", tmp_path / "cache", tmp_path / "manifest.json"
    payloads = iter([_archive(_urgencias_csv("08/09/2026")),
                     _archive(_urgencias_csv("09/09/2026"))])

    def download(_url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(next(payloads))

    with patch("src.data.download_deis_sources._download_zip", side_effect=download), patch(
        "src.data.download_deis_sources.run_date_chile", return_value=date(2026, 10, 3)
    ):
        first = ingest_deis_source("urgencias", 2026, "https://example.test/source.zip",
                                   raw_dir, cache_dir=cache, manifest_path=manifest, refresh_current=True)
        second = ingest_deis_source("urgencias", 2026, "https://example.test/source.zip",
                                    raw_dir, cache_dir=cache, manifest_path=manifest, refresh_current=True)
    assert first["published"] and second["published"]
    assert second["data_cutoff_date"] == "2026-09-09"
    assert (raw_dir / "AtencionesUrgencia2026.csv").read_bytes() == _urgencias_csv("09/09/2026")
    snapshots = json.loads(manifest.read_text(encoding="utf-8"))[0]["snapshots"]
    assert len(snapshots) == 2
    assert snapshots[0]["raw_sha256"] != snapshots[1]["raw_sha256"]


def test_requested_download_failure_exits_nonzero_and_keeps_summary(monkeypatch) -> None:
    summaries = []
    monkeypatch.setattr(sys, "argv", ["download_deis_sources.py", "--refresh-current-urgencias"])
    monkeypatch.setattr(deis, "CURRENT_YEAR", 2026)
    monkeypatch.setattr(deis, "URGENCIAS_CONFIG", urgencias_sources(2026))

    def fail(*args, **kwargs):
        raise OSError("red caída")

    monkeypatch.setattr(deis, "ingest_deis_source", fail)
    monkeypatch.setattr(deis, "_atomic_json_write", lambda path, payload: summaries.append(payload))
    with pytest.raises(SystemExit) as failure:
        deis.main()
    assert failure.value.code == 1
    assert summaries[0]["urgencias"][0]["error"] == "red caída"


def test_full_deis_stage_fails_if_requested_source_failed(monkeypatch) -> None:
    summaries = []
    monkeypatch.setattr(sys, "argv", ["download_deis_sources.py"])
    monkeypatch.setattr(deis, "migrate_legacy_egresos_raw", lambda: [])
    monkeypatch.setattr(deis, "download_and_extract_source", lambda name, *_: (
        [{"year": 2026, "error": "red caída"}] if name == "Atenciones de Urgencia" else []
    ))
    monkeypatch.setattr(deis, "_atomic_json_write", lambda path, payload: summaries.append(payload))
    with pytest.raises(SystemExit) as failure:
        deis.main()
    assert failure.value.code == 1
    assert summaries[0]["urgencias"][0]["error"] == "red caída"
