"""Contratos de SKIP para outputs de datos y compatibilidad del mart de forecasting."""

import csv
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts import run_pipeline as pipeline
from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS
from src.data.clean_urgencias import OUTPUT_SCHEMA
from src.models.features import load_weekly_mart
from src.models.metrics import evaluate_predictions


def _urgencias_parquet(path: Path, *, missing: str | None = None,
                       wrong_type: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [field for field in OUTPUT_SCHEMA if field.name != missing]
    arrays = [pa.array([], type=pa.string() if field.name == wrong_type else field.type)
              for field in fields]
    pq.write_table(pa.Table.from_arrays(arrays, names=[field.name for field in fields]), path)


def test_valid_schema_allows_skip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = Path("data/processed/urgencias/urgencias_rm_2026.parquet")
    _urgencias_parquet(output)
    assert pipeline.check_outputs_exist([output.as_posix()])
    assert pipeline.run_stage("clean_urgencias", year=2026) is False


@pytest.mark.parametrize("defect", ["missing", "wrong_type"])
def test_missing_or_incompatible_schema_cannot_skip(tmp_path, monkeypatch, defect):
    monkeypatch.chdir(tmp_path)
    output = Path("data/processed/urgencias/urgencias_rm_2026.parquet")
    _urgencias_parquet(output, **{"missing" if defect == "missing" else "wrong_type": "ano"})
    assert not pipeline.check_outputs_exist([output.as_posix()])


def test_invalid_output_is_rebuilt_then_checked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = Path("data/processed/urgencias/urgencias_rm_2026.parquet")
    _urgencias_parquet(output, missing="ano")
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: _urgencias_parquet(output))
    assert pipeline.run_stage("clean_urgencias", year=2026) is True
    assert pipeline.check_outputs_exist([output.as_posix()])


def test_stage_zero_exit_with_wrong_schema_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = Path("data/processed/urgencias/urgencias_rm_2026.parquet")
    _urgencias_parquet(output, wrong_type="ano")
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(SystemExit) as failure:
        pipeline.run_stage("clean_urgencias", year=2026)
    assert failure.value.code == 1


def test_legacy_urgencias_csv_without_region_passes_minimum_contract(tmp_path):
    raw = tmp_path / "AtencionesUrgencia2020.csv"
    raw.write_text(
        "IdEstablecimiento;IdCausa;Total;fecha;semana\n"
        "01-100;36;1;01/01/2020;1\n", encoding="latin-1"
    )
    assert pipeline.check_outputs_exist([str(raw)])


def test_establishments_csv_allows_missing_coordinates_but_rejects_text(tmp_path):
    output = tmp_path / "establecimientos_rm_clean.csv"
    header = "establecimiento_codigo,region_codigo,comuna_codigo,latitud,longitud\n"
    output.write_text(header + "1,13,13101,,\n", encoding="utf-8")
    assert pipeline.check_outputs_exist([str(output)])
    output.write_text(header + "1,13,13101,invalid,-70.6\n", encoding="utf-8")
    assert not pipeline.check_outputs_exist([str(output)])


MISSING_COORDS_COLUMNS = [
    "establecimiento_codigo", "establecimiento_codigo_antiguo",
    "establecimiento_glosa", "tipo_establecimiento_glosa",
    "ambito_funcionamiento", "comuna_codigo", "comuna_glosa",
    "latitud", "longitud", "estado_funcionamiento",
]


def _missing_coords_csv(path: Path, rows: list[list[str]],
                        columns: list[str] = MISSING_COORDS_COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def test_missing_coords_accepts_empty_and_nullable_source_rows(tmp_path):
    path = tmp_path / "registros_sin_coordenadas.csv"
    _missing_coords_csv(path, [])
    assert pipeline.check_outputs_exist([str(path)])
    _missing_coords_csv(path, [
        ["110012", "10-012", "Clínica móvil", "", "", "13503", "Curacaví", "", "", "Cerrado"],
        ["202306", "", "SUR", "SUR", "", "13302", "Lampa", "-33.1", "", ""],
    ])
    assert pipeline.check_outputs_exist([str(path)])


def test_missing_coords_rejects_columns_and_coordinate_type_across_all_rows(tmp_path):
    path = tmp_path / "registros_sin_coordenadas.csv"
    row = ["110012", "", "Clínica", "", "", "13503", "Curacaví", "", "", ""]
    _missing_coords_csv(path, [row], MISSING_COORDS_COLUMNS[:-1])
    assert not pipeline.check_outputs_exist([str(path)])
    _missing_coords_csv(path, [row] * 32 + [row[:7] + ["desconocida", "", ""]])
    assert not pipeline.check_outputs_exist([str(path)])


def test_missing_coords_stage_rechecks_after_recovery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path("reports/eda/registros_sin_coordenadas.csv")
    _missing_coords_csv(path, [])
    assert pipeline.run_stage("eda_establishments") is False
    path.write_text("latitud,longitud\nvalor,\n", encoding="utf-8")
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: _missing_coords_csv(path, []))
    assert pipeline.run_stage("eda_establishments") is True


def test_weekly_contract_preserves_forecasting_reader(tmp_path):
    path = tmp_path / "mart_urgencias_comuna_weekly.parquet"
    row = {"ano": 2025, "semana": 1, "fecha_inicio_semana": "2025-01-01",
           "comuna_codigo": "13101", "comuna_glosa": "Santiago",
           "poblacion_anual": 1000, "n_establecimientos_reportantes_id36": 1}
    row.update({column: 1 for column in COUNT_COLUMNS})
    pq.write_table(pa.Table.from_pylist([row]), path)
    assert pipeline.check_outputs_exist([str(path)])
    loaded = load_weekly_mart(path)
    assert loaded.loc[0, "comuna_codigo"] == "13101"
    assert loaded.loc[0, "atenciones_id36"] == 1


def _model_summary(path: Path) -> None:
    predictions = pd.DataFrame([{
        "series_id": "13101", "horizonte": 4, "y_real": 10.0,
        "y_pred": 9.0, "y_inferior": 8.0, "y_superior": 12.0,
    }])
    summary = evaluate_predictions(predictions, {"13101": 2.0})
    summary["modelo"] = "baseline_estacional"
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False)


@pytest.mark.parametrize("name", [
    "benchmark_demanda_sm_resumen.csv", "holdout_demanda_sm_resumen.csv",
])
def test_model_summary_accepts_producer_metrics_and_rejects_defects(tmp_path, name):
    path = tmp_path / name
    _model_summary(path)
    assert pipeline.check_outputs_exist([str(path)])
    frame = pd.read_csv(path, dtype={"series_id": str})
    frame.drop(columns="series_id").to_csv(path, index=False)
    assert not pipeline.check_outputs_exist([str(path)])
    frame["series_id"] = "13101"
    frame["cobertura"] = "incompatible"
    frame.to_csv(path, index=False)
    assert not pipeline.check_outputs_exist([str(path)])
    frame["cobertura"] = ""
    frame.to_csv(path, index=False)
    assert not pipeline.check_outputs_exist([str(path)])


def test_series_summary_accepts_numeric_values_and_rejects_text(tmp_path):
    path = tmp_path / "eda_series_demanda_sm_resumen.csv"
    path.write_text("metrica,valor\nperiodos_modelables,260\nadf_p_nivel,0.2\n", encoding="utf-8")
    assert pipeline.check_outputs_exist([str(path)])
    path.write_text("metrica,valor\nperiodos_modelables,incorrecto\n", encoding="utf-8")
    assert not pipeline.check_outputs_exist([str(path)])


def _selection() -> dict:
    return {
        "modelo_recomendado": "baseline_estacional", "construible": True,
        "criterio": "menor MASE", "nivel_intervalo": 0.8,
        "horizontes": [4, 5, 6, 7, 8], "semilla": 42,
        "periodo_backtest": {
            "ano_min": 2021, "ano_max": 2025, "origenes": 13,
            "paso": 4, "t_primer_origen": 200, "t_ultimo_origen": 248,
        },
        "metricas_backtest": {
            "mase_region": 0.8, "mase_comuna": 0.9,
            "cobertura_region": 0.8, "cobertura_comuna": 0.75,
        },
    }


def test_selection_contract_preserves_holdout_and_api_fields(tmp_path):
    path = tmp_path / "benchmark_demanda_sm_seleccion.json"
    selection = _selection()
    path.write_text(json.dumps(selection), encoding="utf-8")
    assert pipeline.check_outputs_exist([str(path)])
    from scripts.evaluate_holdout_demanda_sm import load_selection
    assert load_selection(path)["modelo_recomendado"] == "baseline_estacional"
    selection["periodo_backtest"].pop("t_ultimo_origen")
    path.write_text(json.dumps(selection), encoding="utf-8")
    assert not pipeline.check_outputs_exist([str(path)])
    selection = _selection()
    selection["horizontes"] = ["4"]
    path.write_text(json.dumps(selection), encoding="utf-8")
    assert not pipeline.check_outputs_exist([str(path)])


def test_holdout_summary_remains_readable_by_api(tmp_path):
    from src.api.service import cobertura_holdout
    from src.models.features import RM_SERIES_ID

    path = tmp_path / "holdout_demanda_sm_resumen.csv"
    _model_summary(path)
    frame = pd.read_csv(path, dtype={"series_id": str})
    region = frame.copy()
    region["series_id"] = RM_SERIES_ID
    pd.concat([region, frame], ignore_index=True).to_csv(path, index=False)
    assert pipeline.check_outputs_exist([str(path)])
    coverage = cobertura_holdout(path, "baseline_estacional", 0.8)
    assert coverage is not None
    assert [row["nivel"] for row in coverage] == ["region", "comuna"]


@pytest.mark.parametrize("name,title", [
    ("eda_series_demanda_sm.md", "# EDA de series temporales: demanda de urgencia en salud mental (RM)"),
    ("benchmark_demanda_sm.md", "# Benchmark de modelos de demanda de urgencia en salud mental (RM)"),
    ("holdout_demanda_sm.md", "# Evaluacion en holdout del modelo de demanda de urgencia en salud mental"),
])
def test_model_report_requires_producer_heading(tmp_path, name, title):
    path = tmp_path / name
    path.write_text(title + "\n\nContenido.\n", encoding="utf-8")
    assert pipeline.check_outputs_exist([str(path)])
    path.write_text("# Otro informe\n", encoding="utf-8")
    assert not pipeline.check_outputs_exist([str(path)])


def test_modeling_stage_rechecks_schema_after_recovery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    summary = Path("reports/modeling/benchmark_demanda_sm_resumen.csv")
    report = Path("reports/modeling/benchmark_demanda_sm.md")
    selection = Path("reports/modeling/benchmark_demanda_sm_seleccion.json")
    _model_summary(summary)
    report.write_text("# Benchmark de modelos de demanda de urgencia en salud mental (RM)\n", encoding="utf-8")
    selection.write_text(json.dumps(_selection()), encoding="utf-8")
    assert pipeline.run_stage("benchmark_demanda_sm") is False
    summary.write_text("modelo,mae\nbaseline_estacional,1\n", encoding="utf-8")
    assert not pipeline.check_outputs_exist([str(summary)])
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: _model_summary(summary))
    assert pipeline.run_stage("benchmark_demanda_sm") is True
