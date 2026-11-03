"""Perfilado RAW agregado, con anomalías documentadas y sin transformar datos."""

import importlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.test_download_defunciones import archive_bytes, csv_bytes, paths


def test_profile_counts_all_records_missingness_and_date_anomalies(tmp_path: Path):
    module = importlib.import_module("scripts.eda_defunciones")
    path = tmp_path / "fixture.csv"
    first = csv_bytes(2024)
    second = csv_bytes(2024, FECHA_DEF="2025-01-01", DIAG1="F320", DIAG2="X700", EDAD_TIPO="2", EDAD_CANT="3")
    third = csv_bytes(2024, FECHA_DEF="invalid", DIAG1="*", EDAD_TIPO="0", EDAD_CANT="999")
    path.write_bytes(first + second.split(b"\n", 1)[1] + third.split(b"\n", 1)[1])
    before = path.read_bytes()
    result = module.profile_csv(path, expected_years=range(2024, 2027))
    assert result["rows"] == 3
    assert result["years"] == {"2024": 3}
    assert result["blank"]["DIAG2"] == 2
    assert result["asterisk"]["DIAG1"] == 1
    assert result["invalid_dates"] == 1
    assert result["date_year_mismatch"] == 1
    assert result["age_types"] == {"1": 1, "2": 1, "0": 1}
    assert result["diag1_f_prefix"] == 1
    assert path.read_bytes() == before


def test_profile_rejects_ragged_rows_instead_of_skipping(tmp_path):
    module = importlib.import_module("scripts.eda_defunciones")
    path = tmp_path / "fixture.csv"
    path.write_bytes(csv_bytes() + b"short;row\n")
    with pytest.raises(ValueError, match="columnas"):
        module.profile_csv(path, expected_years=range(2024, 2027))


def test_profile_does_not_equate_numeric_historical_codes_with_cie10(tmp_path):
    module = importlib.import_module("scripts.eda_defunciones")
    path = tmp_path / "fixture.csv"
    path.write_bytes(csv_bytes(1990, DIAG1="2900", CAPITULO_DIAG1=""))
    result = module.profile_csv(path, expected_years=range(1990, 2024))
    assert result["diag1_numeric"] == 1
    assert result["diag1_cie10_shape"] == 0
    assert result["diag1_f_prefix"] == 0


def test_generate_report_uses_both_registered_raw_sources_without_modifying_them(tmp_path, monkeypatch):
    downloader = importlib.import_module("src.data.download_defunciones")
    eda = importlib.import_module("scripts.eda_defunciones")
    kwargs = paths(tmp_path)
    for source in downloader.DEFUNCIONES_SOURCES:
        payload = archive_bytes(source, csv_bytes(source.first_year))
        with patch.object(downloader.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
            downloader.ingest_source(source, **kwargs)
    report, summary = tmp_path / "eda.md", tmp_path / "eda.json"
    monkeypatch.setattr(eda, "DEST_DIR", kwargs["dest_dir"])
    monkeypatch.setattr(eda, "MANIFEST_PATH", kwargs["manifest_path"])
    monkeypatch.setattr(eda, "REPORT_PATH", report)
    monkeypatch.setattr(eda, "SUMMARY_PATH", summary)
    monkeypatch.setattr(eda, "CONTEXT_PATH", tmp_path / "context_not_downloaded.parquet")
    before = {p: p.read_bytes() for p in kwargs["dest_dir"].rglob("*") if p.is_file()}
    eda.generate_report()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert set(payload["sources"]) == {s.key for s in downloader.DEFUNCIONES_SOURCES}
    assert sum(s["profile"]["rows"] for s in payload["sources"].values()) == 2
    assert all(s["provenance_matches"] for s in payload["sources"].values())
    assert all(p.read_bytes() == content for p, content in before.items())
    assert report.read_text(encoding="utf-8").startswith(eda.TITLE)
    content = report.read_text(encoding="utf-8")
    assert "## Hallazgos de salud mental y suicidio" in content
    assert "No se analiza suicidio" not in content
    assert "Fuente contextual no disponible" in content
    eda.validate_summary(summary)
    health = next(iter(payload["sources"].values()))["profile"]["mental_health"]
    health["annual"][next(iter(health["annual"]))]["rm_f_diag1"] = 99
    summary.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="salud mental|RM"):
        eda.validate_summary(summary)


def test_output_contract_rejects_incomplete_eda_json(tmp_path):
    from scripts import run_pipeline
    summary = tmp_path / "eda_defunciones_raw_resumen.json"
    summary.write_text('{"sources":{}}', encoding="utf-8")
    assert not run_pipeline.check_outputs_exist([summary.as_posix()])


def test_health_profile_separates_external_causes_age_units_and_study_period(tmp_path):
    from scripts import eda_defunciones as eda

    rows = [
        csv_bytes(2021, DIAG1="F039", EDAD_CANT="80", NOMBRE_REGION="Metropolitana de Santiago"),
        csv_bytes(2022, DIAG1="F10.2", EDAD_TIPO="2", EDAD_CANT="70"),
        csv_bytes(2023, DIAG1="T719", DIAG2="X700", EDAD_CANT="30"),
        csv_bytes(2023, DIAG1="X700", DIAG2="", EDAD_CANT="30"),
        csv_bytes(2024, DIAG1="F99999", DIAG2="Y87.0"),
        csv_bytes(2025, DIAG2="Y100"),
        csv_bytes(2026, DIAG1="F039", DIAG2="X700"),
        csv_bytes(1990, DIAG1="2900"),
    ]
    path = tmp_path / "fixture.csv"
    path.write_bytes(rows[0] + b"".join(row.split(b"\n", 1)[1] for row in rows[1:]))
    result = eda.profile_csv(path, expected_years=range(1990, 2027))
    health = result["mental_health"]
    assert health["annual"]["2021"]["rm_f_diag1"] == 1
    assert health["annual"]["2023"]["self_diag2"] == 1
    assert health["annual"]["2023"]["self_diag1"] == 1
    assert health["annual"]["2024"]["f_diag1"] == 0
    assert health["annual"]["2024"]["sequela_diag2"] == 1
    assert health["annual"]["2025"]["undetermined_diag2"] == 1
    assert health["annual"]["1990"]["f_diag1"] == 0
    assert health["f_categories"] == {"F03": 1, "F10": 1}
    assert health["age"]["f"] == {"65+": 1, "otra_unidad_o_no_interpretable": 1}
    assert health["sex"]["self"] == {"Hombre": 1}


def test_context_comparison_preserves_disagreement_and_reports_missing_source(tmp_path):
    from scripts import eda_defunciones as eda
    import pyarrow as pa
    import pyarrow.parquet as pq

    payload = {"sources": {"fixture": {"profile": {"mental_health": {
        "annual": {"2021": {"self_diag2": 5, "rm_self_diag2": 2}}
    }}}}}
    path = tmp_path / "context.parquet"
    assert eda.compare_suicide_context(payload, path)["status"] == "not_available"
    pq.write_table(pa.table({"year": [2021, 2021], "sex": ["Total", "Total"],
        "indicator": ["defunciones_suicidio"] * 2, "geography_level": ["nacional", "regional"],
        "region_code": [None, 13], "value": [5.0, 3.0]}), path)
    comparison = eda.compare_suicide_context(payload, path)
    assert comparison["compared"] == 2
    assert comparison["matched"] == 1
    assert comparison["differences"] == [{"year": "2021", "scope": "RM", "raw": 2, "context": 3}]
    assert len(comparison["sha256"]) == 64
