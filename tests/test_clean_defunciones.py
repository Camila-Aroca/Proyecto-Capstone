"""Consolidación con lotes sintéticos registrados; sin red ni conteos fijos."""

import csv
import datetime as dt
import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.raw_provenance import file_sha256, record_raw_snapshot
from tests.test_download_defunciones import COLUMNS


def record(year, **values):
    row = dict.fromkeys(COLUMNS, "")
    row.update({COLUMNS[0]: str(year), "FECHA_DEF": f"{year}-01-02", "SEXO_NOMBRE": "Mujer",
                "EDAD_TIPO": "1", "EDAD_CANT": "70", "COD_COMUNA": "1101",
                "COMUNA": "Iquique", "NOMBRE_REGION": "Tarapaca", "DIAG1": "I219",
                "LUGAR_DEFUNCION": "Hospital o Clinica"})
    row.update(values)
    return row


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "raw_root": "raw/defunciones", "provenance_manifest": "raw/manifest.json",
        "start_date": "2020-01-01", "end_date": None, "encoding": "latin-1",
        "date_formats": ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"], "batch_size": 2,
        "outputs": {"parquet": "processed/defunciones/unificado.parquet",
                    "summary": "reports/resultado.json", "report": "reports/resultado.md",
                    "dictionary": "reports/diccionario.md"},
    }
    config_path = Path("config.json")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    rows = {
        "lote_a": [record(2019), record(2020, GLOSA_CAPITULO_DIAG1=" Glosa "),
                   record(2020, GLOSA_CAPITULO_DIAG1=" Glosa "), record(2020, FECHA_DEF="")],
        "lote_b": [record(2021, COD_COMUNA="99999"),
                   record(2022, FECHA_DEF="no-fecha", EDAD_TIPO="?", EDAD_CANT="desconocida",
                          COD_COMUNA="ABC", DIAG1="F320", DIAG2=" X700 ")],
    }

    def write(source, records, columns=None):
        path = Path(config["raw_root"]) / f"{source}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="latin-1", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns or COLUMNS, delimiter=";")
            writer.writeheader()
            writer.writerows(records)
        record_raw_snapshot(source, "https://example.test/public.csv", path,
                            manifest_path=Path(config["provenance_manifest"]),
                            source_metadata={"dataset": "defunciones"})
        return path

    for source, records in rows.items():
        write(source, records)
    return config_path, config, rows, write


def load(tree):
    module = importlib.import_module("src.data.clean_defunciones")
    return module, module.load_config(tree[0])


def test_consolidation_selects_latest_preliminary_snapshot_without_deleting_history(tree):
    module, settings = load(tree)
    _, _, _, write = tree
    write("deis_defunciones_2024_2026_27102026", [record(2024)])
    write("deis_defunciones_2024_2026_10112026", [record(2024, DIAG1="F320")])
    manifest = Path(settings["provenance_manifest"])
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["source_id"].startswith("deis_defunciones_2024_"):
            entry["snapshots"][-1]["source_url"] = ("https://repositoriodeis.minsal.cl/DatosAbiertos/VITALES/DEFUNCIONES_FUENTE_DEIS_"
                                                      + entry["source_id"].removeprefix("deis_defunciones_") + ".zip")
    manifest.write_text(json.dumps(entries), encoding="utf-8")
    sources = module.discover_inputs(settings)
    ids = {source["source_id"] for source in sources}
    assert "deis_defunciones_2024_2026_10112026" in ids
    assert "deis_defunciones_2024_2026_27102026" not in ids
    assert Path(settings["raw_root"], "deis_defunciones_2024_2026_27102026.csv").exists()
    # Un clon nuevo puede conservar la procedencia histórica sin el RAW viejo.
    Path(settings["raw_root"], "deis_defunciones_2024_2026_27102026.csv").unlink()
    assert {source["source_id"] for source in module.discover_inputs(settings)} == ids


def test_concatenates_all_columns_preserving_duplicates_and_exception_values(tree):
    module, settings = load(tree)
    config = tree[1]
    originals = {p: p.read_bytes() for p in Path("raw").rglob("*") if p.is_file()}
    result = module.consolidate(settings)
    table = pq.read_table(config["outputs"]["parquet"])
    data = table.to_pylist()
    assert table.schema.equals(module.SCHEMA, check_metadata=False)
    assert len(data) == 5
    assert [r["ano_defuncion"] for r in data] == [2020, 2020, 2020, 2021, 2022]
    assert data[0]["fuente_fila"] == 2
    assert data[0]["fuente_archivo"] == "raw/defunciones/lote_a.csv"
    assert data[0]["fecha_defuncion"] == dt.date(2020, 1, 2)
    assert data[0]["comuna_codigo_original"] == "1101"
    assert data[0]["comuna_codigo"] == "01101"
    assert data[0]["glosa_capitulo_diag1"] == "Glosa"
    assert data[2]["fecha_defuncion"] is None
    assert "fecha_ausente" in data[2]["excepciones"]
    assert data[3]["comuna_codigo"] == "99999"
    assert data[4]["fecha_defuncion_original"] == "no-fecha"
    assert data[4]["edad_cantidad_original"] == "desconocida"
    assert data[4]["edad_cantidad"] is None
    assert data[4]["comuna_codigo_original"] == "ABC"
    assert data[4]["comuna_codigo"] is None
    assert data[4]["diag1"] == "F320" and data[4]["diag2"] == "X700"
    assert result["raw_duplicates"] == result["normalized_duplicates"] == 1
    assert result["counts_by_year"] == {"2020": 3, "2021": 1, "2022": 1}
    assert result["null_counts"]["fecha_defuncion"] == 2
    assert result["preservation_verified"] is True
    assert all(p.read_bytes() == before for p, before in originals.items())
    assert len(list(Path("processed").rglob("*.parquet"))) == 1
    assert all(pq.ParquetFile(config["outputs"]["parquet"]).metadata.row_group(i).column(0).compression == "ZSTD"
               for i in range(pq.ParquetFile(config["outputs"]["parquet"]).metadata.num_row_groups))


def test_period_is_configurable_without_changing_filenames_or_code(tree):
    tree[1]["start_date"] = "2021-01-01"
    tree[1]["end_date"] = "2021-12-31"
    tree[0].write_text(json.dumps(tree[1]), encoding="utf-8")
    module, settings = load(tree)
    result = module.consolidate(settings)
    assert result["rows"] == 1
    assert result["counts_by_year"] == {"2021": 1}


def test_overlapping_years_fail_without_replacing_previous_output(tree):
    module, settings = load(tree)
    module.consolidate(settings)
    output = Path(tree[1]["outputs"]["parquet"])
    before = output.read_bytes()
    tree[3]("lote_b", [record(2020)])
    with pytest.raises(ValueError, match="solapamiento"):
        module.consolidate(settings)
    assert output.read_bytes() == before


def test_incompatible_schema_and_unregistered_sources_fail(tree):
    module, settings = load(tree)
    tree[3]("lote_b", tree[2]["lote_b"], columns=list(reversed(COLUMNS)))
    with pytest.raises(ValueError, match="27 columnas"):
        module.consolidate(settings)
    assert not Path(tree[1]["outputs"]["parquet"]).exists()


def test_publication_failure_restores_all_previous_artifacts(tree):
    module, settings = load(tree)
    module.consolidate(settings)
    before = {Path(p): Path(p).read_bytes() for p in tree[1]["outputs"].values()}
    real_replace = module._replace_file
    calls = []

    def fail_once(candidate, target):
        calls.append(target)
        if len(calls) == 2:
            raise OSError("publication failed")
        return real_replace(candidate, target)

    with patch.object(module, "_replace_file", side_effect=fail_once):
        with pytest.raises(OSError):
            module.consolidate(settings)
    assert all(path.read_bytes() == content for path, content in before.items())


def test_freshness_checks_raw_config_and_corrupt_parquet(tree):
    module, settings = load(tree)
    module.consolidate(settings)
    output = Path(tree[1]["outputs"]["parquet"])
    module.validate_product(output, settings)
    tree[3]("lote_b", [record(2023)])
    with pytest.raises(ValueError, match="RAW|procedencia"):
        module.validate_product(output, settings)
    module.consolidate(settings)
    changed = dict(settings, start_date="2021-01-01")
    with pytest.raises(ValueError, match="configuraci"):
        module.validate_product(output, changed)
    output.write_bytes(b"not parquet")
    with pytest.raises(Exception):
        module.validate_product(output, settings)


def test_missing_inputs_duplicate_content_or_ragged_rows_fail(tree):
    module, settings = load(tree)
    raw = Path(tree[1]["raw_root"])
    (raw / "unexpected.csv").write_text("a;b\n1;2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="registrad"):
        module.consolidate(settings)
    (raw / "unexpected.csv").unlink()
    (raw / "lote_b.csv").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        module.consolidate(settings)


def test_ragged_record_with_valid_provenance_is_rejected(tree):
    module, settings = load(tree)
    path = Path(tree[1]["raw_root"]) / "lote_b.csv"
    with path.open("a", encoding="latin-1") as handle:
        handle.write("bad;row\n")
    record_raw_snapshot("lote_b", "https://example.test/public.csv", path,
                        manifest_path=Path(tree[1]["provenance_manifest"]))
    with pytest.raises(ValueError, match="columnas"):
        module.consolidate(settings)


def test_duplicate_file_content_is_rejected_instead_of_deduplicated(tree):
    module, settings = load(tree)
    raw = Path(tree[1]["raw_root"])
    path = raw / "lote_b.csv"
    path.write_bytes((raw / "lote_a.csv").read_bytes())
    record_raw_snapshot("lote_b", "https://example.test/public.csv", path,
                        manifest_path=Path(tree[1]["provenance_manifest"]))
    with pytest.raises(ValueError, match="contenido duplicado"):
        module.consolidate(settings)


def test_summary_and_orchestrator_detect_drift_without_network(tree, monkeypatch):
    module, settings = load(tree)
    from scripts import run_pipeline as pipeline
    module.consolidate(settings)
    monkeypatch.setattr(module, "CONFIG_PATH", tree[0])
    outputs = list(tree[1]["outputs"].values())
    assert pipeline.check_outputs_exist(outputs)
    report = Path(tree[1]["outputs"]["report"])
    report.write_text(report.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    assert not pipeline.check_outputs_exist(outputs)


def test_pipeline_registers_only_the_affected_branch(monkeypatch):
    from scripts import run_pipeline as pipeline
    assert "clean_defunciones" in pipeline.STAGES
    assert pipeline.STAGES["clean_defunciones"]["depends_on"] == ["download_defunciones"]
    calls = []
    monkeypatch.setattr(pipeline.sys, "argv", ["run_pipeline.py", "--stage", "clean_defunciones"])
    monkeypatch.setattr(pipeline, "run_stage", lambda name, **kwargs: calls.append(name) or True)
    pipeline.main()
    # Su único consumidor es la rama de suicidios: un cambio en Defunciones la regenera
    # completa, y nada de Urgencias/Egresos.
    assert calls == [
        "clean_defunciones",
        "build_mart_suicidios_comuna_weekly",
        "eda_mart_suicidios_comuna_weekly",
        "benchmark_suicidios",
        "evaluate_holdout_suicidios",
        "forecast_suicidios",
    ]


@pytest.mark.data_integration
def test_real_raw_to_parquet_preservation():
    """Lectura independiente y fila a fila de las 27 variables publicadas."""
    module = importlib.import_module("src.data.clean_defunciones")
    settings = module.load_config()
    path = Path(settings["outputs"]["parquet"])
    audit = module.validate_product(path, settings)
    observed = pq.ParquetFile(path).iter_batches(batch_size=8192)
    iterator = (r for batch in observed for r in batch.to_pylist())
    count = 0
    for source in audit["inputs"]:
        with Path(source["path"]).open(encoding=settings["encoding"], newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for number, original in enumerate(reader, 1):
                year = int(original[COLUMNS[0]])
                if year < dt.date.fromisoformat(settings["start_date"]).year:
                    continue
                row = next(iterator)
                assert row["fuente_archivo"] == source["path"] and row["fuente_fila"] == number
                for raw, column in module.COLUMN_MAP.items():
                    value = original[raw].strip() or None
                    if raw == "FECHA_DEF":
                        expected = dt.date.fromisoformat(value) if value else None
                    elif raw in (COLUMNS[0], "EDAD_TIPO", "EDAD_CANT"):
                        expected = int(value) if value is not None else None
                    elif raw == "COD_COMUNA":
                        expected = original[raw]
                    else:
                        expected = value
                    assert row[column] == expected, (source["source_id"], number, raw)
                count += 1
        assert file_sha256(Path(source["path"])) == source["sha256"]
    assert next(iterator, None) is None
    assert count == audit["rows"]
    assert sum(audit["counts_by_year"].values()) == count
