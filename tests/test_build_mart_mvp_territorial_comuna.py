"""Pruebas dirigidas para el mart canónico MVP territorial a nivel comuna (RM)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_mart_mvp_territorial_comuna import (
    ANO_CENSO,
    ANO_DEMANDA,
    ANO_POBLACION,
    build_mart_mvp_territorial_comuna,
    load_oferta_agregada,
    load_universo_comunal,
    validate_mart,
)
from src.data.clean_censo_comunas import EXPECTED_RM_CUTS

ALL_CUTS = sorted(str(cut) for cut in EXPECTED_RM_CUTS)
# Comuna sin ninguna atención de Urgencia 2025 en el fixture, análoga a Vitacura.
NO_REPORT_CUT = ALL_CUTS[0]
REPORTING_CUTS = ALL_CUTS[1:]


def _glosa(cut: str) -> str:
    return f"Comuna {cut}"


def _write_universo(path: Path) -> None:
    frame = pd.DataFrame({
        "comuna_codigo": ALL_CUTS,
        "comuna_glosa": [_glosa(c) for c in ALL_CUTS],
        "ano_referencia": 2024,
        "poblacion_censada": [10_000 + i for i in range(len(ALL_CUTS))],
        "fuente": "fixture",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def _write_monthly_mart(path: Path) -> None:
    rows = []
    for cut in REPORTING_CUTS:
        for month in range(1, 13):
            rows.append({
                "comuna_codigo": cut, "ano": ANO_DEMANDA, "mes": month,
                "atenciones_id1": 100, "atenciones_id35": 2, "atenciones_id36": 10,
            })
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def _write_urgencias_2025(path: Path) -> None:
    rows = []
    for cut in REPORTING_CUTS:
        # Dos establecimientos reportan ID1 en meses distintos; sólo uno reporta ID36.
        rows.append({"ano": 2025, "comuna_codigo": cut, "establecimiento_codigo": 1, "id_causa": 1})
        rows.append({"ano": 2025, "comuna_codigo": cut, "establecimiento_codigo": 2, "id_causa": 1})
        rows.append({"ano": 2025, "comuna_codigo": cut, "establecimiento_codigo": 1, "id_causa": 1})
        rows.append({"ano": 2025, "comuna_codigo": cut, "establecimiento_codigo": 1, "id_causa": 36})
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def _write_poblacion_anual(path: Path) -> None:
    frame = pd.DataFrame({
        "comuna_codigo": ALL_CUTS,
        "comuna_glosa": [_glosa(c) for c in ALL_CUTS],
        "ano": ANO_POBLACION,
        "poblacion": [20_000 + i for i in range(len(ALL_CUTS))],
        "fuente": "fixture",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def _write_vulnerabilidad(path: Path) -> None:
    frame = pd.DataFrame({
        "comuna_codigo": ALL_CUTS,
        "comuna_glosa": [_glosa(c) for c in ALL_CUTS],
        "ano_referencia": 2022,
        "indicador_vulnerabilidad": [0.05] * len(ALL_CUTS),
        "nombre_indicador": "Tasa de pobreza (fixture)",
        "fuente": "fixture",
        "direccion_indicador": "mayor_valor_mayor_vulnerabilidad",
        "intervalo_confianza_inferior": [0.02] * len(ALL_CUTS),
        "intervalo_confianza_superior": [0.08] * len(ALL_CUTS),
        "tipo_estimacion_sae": "Directa y Sintética (Fay-Herriot)",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def _write_oferta(path: Path) -> None:
    # Una oferta por cada comuna (incluida la que no reporta Urgencias), más
    # un hospital adicional y una excepción CEAR en la primera comuna con reporte.
    rows = []
    for i, cut in enumerate(ALL_CUTS):
        rows.append({
            "establecimiento_codigo": 1000 + i,
            "comuna_codigo": cut,
            "tipo_establecimiento": "Servicio de Atención Primaria de Urgencia (SAPU)",
            "criterio_inclusion_oferta": "catalogo_core",
            "latitud": -33.4 if i % 2 == 0 else None,
            "longitud": -70.6 if i % 2 == 0 else None,
        })
    rows.append({
        "establecimiento_codigo": 9001,
        "comuna_codigo": REPORTING_CUTS[0],
        "tipo_establecimiento": "Hospital",
        "criterio_inclusion_oferta": "catalogo_core",
        "latitud": -33.5, "longitud": -70.7,
    })
    rows.append({
        "establecimiento_codigo": 9002,
        "comuna_codigo": REPORTING_CUTS[0],
        "tipo_establecimiento": "Centro de Salud Familiar (CESFAM)",
        "criterio_inclusion_oferta": "excepcion_cear_documentada",
        "latitud": -33.5, "longitud": -70.7,
    })
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


@pytest.fixture
def fixture_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "universo": tmp_path / "dim_poblacion_comuna_censo2024.parquet",
        "monthly": tmp_path / "mart_urgencias_comuna_monthly.parquet",
        "urgencias_2025": tmp_path / "urgencias_rm_2025.parquet",
        "poblacion_anual": tmp_path / "dim_poblacion_comuna_anual.parquet",
        "vulnerabilidad": tmp_path / "dim_vulnerabilidad_comuna.parquet",
        "oferta": tmp_path / "dim_oferta_urgencia_rm.parquet",
    }
    _write_universo(paths["universo"])
    _write_monthly_mart(paths["monthly"])
    _write_urgencias_2025(paths["urgencias_2025"])
    _write_poblacion_anual(paths["poblacion_anual"])
    _write_vulnerabilidad(paths["vulnerabilidad"])
    _write_oferta(paths["oferta"])
    return paths


def _build(paths: dict[str, Path]) -> pd.DataFrame:
    return build_mart_mvp_territorial_comuna(
        universo_path=paths["universo"],
        monthly_path=paths["monthly"],
        urgencias_2025_path=paths["urgencias_2025"],
        poblacion_anual_path=paths["poblacion_anual"],
        vulnerabilidad_path=paths["vulnerabilidad"],
        oferta_path=paths["oferta"],
    )


def test_full_pipeline_produces_52_rows_matching_official_build(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    assert len(mart) == 52
    assert set(mart["comuna_codigo"]) == set(ALL_CUTS)
    validate_mart(mart, monthly_path=fixture_paths["monthly"], oferta_path=fixture_paths["oferta"])


def test_no_report_comuna_keeps_null_not_zero(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    row = mart.loc[mart["comuna_codigo"] == NO_REPORT_CUT].iloc[0]
    assert row["tiene_reporte_urgencias"] is False or row["tiene_reporte_urgencias"] == False  # noqa: E712
    for column in [
        "atenciones_id1_2025", "atenciones_id35_2025", "atenciones_id36_2025",
        "n_establecimientos_reportantes_id1_2025", "n_establecimientos_reportantes_id36_2025",
        "tasa_atenciones_id1_2025_por_10000",
    ]:
        assert pd.isna(row[column]), f"{column} debería ser NULL, no cero, para una comuna sin reporte."
    # Pero la oferta y la población sí deben estar presentes (no dependen de Urgencias).
    assert row["n_oferta_urgencia_actual"] == 1
    assert pd.notna(row["poblacion_2025"])
    assert pd.notna(row["indicador_vulnerabilidad"])


def test_reporting_comuna_has_populated_demand(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    row = mart.loc[mart["comuna_codigo"] == REPORTING_CUTS[1]].iloc[0]
    assert row["tiene_reporte_urgencias"]
    assert row["atenciones_id1_2025"] == 100 * 12
    assert row["atenciones_id36_2025"] == 10 * 12


def test_annual_reportantes_are_not_summed_from_monthly(fixture_paths: dict[str, Path]) -> None:
    """2 establecimientos reportan ID1 en el año (aunque en meses distintos); no debe dar 24."""
    mart = _build(fixture_paths)
    row = mart.loc[mart["comuna_codigo"] == REPORTING_CUTS[1]].iloc[0]
    assert row["n_establecimientos_reportantes_id1_2025"] == 2
    assert row["n_establecimientos_reportantes_id36_2025"] == 1


def test_rate_is_recomputed_from_annual_counts_not_averaged(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    row = mart.loc[mart["comuna_codigo"] == REPORTING_CUTS[1]].iloc[0]
    expected_rate = (100 * 12) / row["poblacion_2025"] * 10_000
    assert row["tasa_atenciones_id1_2025_por_10000"] == pytest.approx(expected_rate)


def test_vulnerabilidad_is_not_relabeled_as_2025(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    assert (mart["ano_vulnerabilidad"] == 2022).all()
    assert (mart["ano_demanda"] == 2025).all()


def test_oferta_reconciles_with_dimension_total(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    oferta_dim = pq.read_table(fixture_paths["oferta"], columns=["establecimiento_codigo"]).to_pandas()
    assert int(mart["n_oferta_urgencia_actual"].sum()) == len(oferta_dim)
    tipo_sum = mart[["n_hospitales", "n_sapu", "n_sar", "n_sur", "n_otras_excepciones"]].sum(axis=1)
    assert (tipo_sum == mart["n_oferta_urgencia_actual"]).all()


def test_proporcion_con_coordenadas_null_when_no_offer() -> None:
    """Comuna sin ninguna fila en la dimensión de oferta: proporción debe ser NULL, no 0/0."""
    universo = pd.DataFrame({"comuna_codigo": ["13999"], "comuna_glosa": ["Ficticia"]})
    oferta_vacia = pd.DataFrame({
        "establecimiento_codigo": pd.Series(dtype="int64"),
        "comuna_codigo": pd.Series(dtype="str"),
        "tipo_establecimiento": pd.Series(dtype="str"),
        "criterio_inclusion_oferta": pd.Series(dtype="str"),
        "latitud": pd.Series(dtype="float64"),
    })
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "oferta_vacia.parquet"
        pq.write_table(pa.Table.from_pandas(oferta_vacia, preserve_index=False), path)
        aggregated = load_oferta_agregada(path, universo=universo)
    row = aggregated.loc[aggregated["comuna_codigo"] == "13999"].iloc[0]
    assert row["n_oferta_urgencia_actual"] == 0
    assert pd.isna(row["proporcion_oferta_con_coordenadas"])


def test_universo_rejects_incomplete_cut_set(tmp_path: Path) -> None:
    incomplete = tmp_path / "universo_incompleto.parquet"
    frame = pd.DataFrame({
        "comuna_codigo": ALL_CUTS[:-1],
        "comuna_glosa": [_glosa(c) for c in ALL_CUTS[:-1]],
    })
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), incomplete)
    with pytest.raises(ValueError, match="52 comunas"):
        load_universo_comunal(incomplete)


def test_validate_rejects_wrong_row_count(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    broken = mart.iloc[:-1].copy()
    with pytest.raises(ValueError, match="52 filas"):
        validate_mart(broken, monthly_path=fixture_paths["monthly"], oferta_path=fixture_paths["oferta"])


def test_validate_rejects_zero_imputed_instead_of_null(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    broken = mart.copy()
    idx = broken.index[broken["comuna_codigo"] == NO_REPORT_CUT][0]
    broken.loc[idx, "atenciones_id1_2025"] = 0
    with pytest.raises(ValueError, match="no debe imputarse cero"):
        validate_mart(broken, monthly_path=fixture_paths["monthly"], oferta_path=fixture_paths["oferta"])


def test_validate_rejects_mismatched_offer_total(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    broken = mart.copy()
    broken.loc[broken.index[0], "n_oferta_urgencia_actual"] = (
        broken.loc[broken.index[0], "n_oferta_urgencia_actual"] + 1
    )
    broken.loc[broken.index[0], "n_sapu"] = broken.loc[broken.index[0], "n_sapu"] + 1
    with pytest.raises(ValueError, match="no reconcilia con dim_oferta_urgencia_rm"):
        validate_mart(broken, monthly_path=fixture_paths["monthly"], oferta_path=fixture_paths["oferta"])


def test_validate_rejects_relabeled_vulnerabilidad_year(fixture_paths: dict[str, Path]) -> None:
    mart = _build(fixture_paths)
    broken = mart.copy()
    broken["ano_vulnerabilidad"] = 2025
    with pytest.raises(ValueError, match="temporalidad no constante"):
        validate_mart(broken, monthly_path=fixture_paths["monthly"], oferta_path=fixture_paths["oferta"])


# --- Registro en el orquestador -------------------------------------------

def test_stage_is_registered_after_its_dependencies() -> None:
    deps = pipeline.STAGES["build_mart_mvp_territorial_comuna"]["depends_on"]
    assert set(deps) == {
        "clean_censo_poblacion", "clean_poblacion_proyecciones", "clean_pobreza_comunal",
        "clean_urgencias", "build_urgencias_comuna_marts", "build_dim_oferta_urgencia_rm",
    }
    assert "build_mart_mvp_territorial_comuna" in pipeline.PIPELINE_ORDER
    for dep in deps:
        assert pipeline.PIPELINE_ORDER.index(dep) < pipeline.PIPELINE_ORDER.index(
            "build_mart_mvp_territorial_comuna"
        )


def test_official_output_exists() -> None:
    """Verifica que el output canónico ya haya sido generado por el pipeline oficial."""
    from src.data.build_mart_mvp_territorial_comuna import OUTPUT_PATH
    assert OUTPUT_PATH.exists(), f"Falta output canónico: {OUTPUT_PATH}"
