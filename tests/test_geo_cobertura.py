"""Pruebas del MVP de cobertura territorial simple (distancia población-oferta)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import shapely

import scripts.run_pipeline as pipeline
from src.data.output_contracts import validate_expected_schema
from src.geo.build_capa_oferta_urgencia_rm import SCHEMA as SCHEMA_CAPA
from src.geo.build_cobertura_urgencia_comuna import (
    REPORT_TITLE,
    build_cobertura_urgencia_comuna,
    calcular_cobertura,
    cuantil_ponderado,
    distancia_minima_km,
    escribir_cobertura,
    render_reporte,
    validar_cobertura,
)
from src.geo.capas import escribir_geoparquet
from tests.test_geo_capas import CRS_4674

KM_POR_GRADO_LATITUD = 6371.0088 * np.pi / 180
CUTS = [str(13101 + i) for i in range(52)]


def test_distancia_haversine_conocida_y_minimo_entre_bloques() -> None:
    # 30 destinos fuerzan dos bloques; el más cercano está en el segundo.
    destino_lat = np.array([-30.0] * 29 + [-33.1])
    destino_lon = np.full(30, -70.0)
    distancia = distancia_minima_km(np.array([-70.0]), np.array([-33.0]), destino_lon, destino_lat)
    assert distancia[0] == pytest.approx(0.1 * KM_POR_GRADO_LATITUD, rel=1e-9)


def test_distancia_sin_destinos_falla() -> None:
    with pytest.raises(ValueError):
        distancia_minima_km(np.array([0.0]), np.array([0.0]), np.array([]), np.array([]))


def test_cuantil_ponderado_usa_la_poblacion() -> None:
    valores, pesos = np.array([1.0, 5.0, 9.0]), np.array([10.0, 80.0, 10.0])
    assert cuantil_ponderado(valores, pesos, 0.5) == 5.0
    assert cuantil_ponderado(valores, pesos, 0.95) == 9.0
    assert cuantil_ponderado(valores, pesos, 0.05) == 1.0


def _oferta(filas: list[tuple[str, float, float, bool]]) -> pd.DataFrame:
    return pd.DataFrame(filas, columns=["comuna_codigo", "longitud", "latitud", "reporto_id36_periodo"])


def _poblacion(cuts: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"comuna_codigo": cuts, "comuna_glosa": [f"C{c}" for c in cuts],
                         "poblacion_censada": [1000] * len(cuts)})


def test_cobertura_pondera_y_cruza_comunas() -> None:
    # 13101 tiene el único establecimiento con ID36; 13102 no tiene oferta propia.
    oferta = _oferta([("13101", -70.0, -33.0, True), ("13101", -70.0, -33.5, False)])
    unidades = pd.DataFrame({
        "comuna_codigo": ["13101", "13101", "13102"],
        "poblacion": [900, 100, 500],
        "longitud": [-70.0, -70.0, -70.0],
        "latitud": [-33.0, -33.5, -33.03],
    })
    cobertura = calcular_cobertura(unidades, oferta, _poblacion(["13101", "13102"])).set_index("comuna_codigo")

    c1, c2 = cobertura.loc["13101"], cobertura.loc["13102"]
    assert c1["distancia_mediana_km"] == pytest.approx(0.0)
    assert c1["proporcion_poblacion_a_2km"] == pytest.approx(1.0)
    # La unidad de 100 personas está a 0,5° del único establecimiento con ID36.
    assert c1["proporcion_poblacion_a_5km_id36"] == pytest.approx(0.9)
    assert c1["n_oferta_urgencia_en_comuna"] == 2 and c1["habitantes_por_establecimiento"] == 500
    # Sin oferta propia, la comuna se mide contra el establecimiento de la comuna vecina.
    assert c2["n_oferta_urgencia_en_comuna"] == 0 and pd.isna(c2["habitantes_por_establecimiento"])
    assert c2["distancia_mediana_km"] == pytest.approx(0.03 * KM_POR_GRADO_LATITUD, rel=1e-6)
    assert c2["proporcion_poblacion_representada"] == pytest.approx(0.5)


def _cobertura_valida() -> pd.DataFrame:
    oferta = _oferta([(c, -70.0 + i * 0.1, -33.0, True) for i, c in enumerate(CUTS)])
    unidades = pd.DataFrame({"comuna_codigo": CUTS, "poblacion": 100,
                             "longitud": [-70.0 + i * 0.1 for i in range(52)], "latitud": -33.01})
    return calcular_cobertura(unidades, oferta, _poblacion(CUTS))


def test_validacion_acepta_cobertura_coherente() -> None:
    validar_cobertura(_cobertura_valida(), 52)


@pytest.mark.parametrize("alteracion", [
    lambda c: c.iloc[:-1],
    lambda c: c.assign(proporcion_poblacion_a_2km=1.0, proporcion_poblacion_a_5km=0.5),
    lambda c: c.assign(distancia_p90_km=c["distancia_mediana_km"] - 0.1),
    lambda c: c.assign(proporcion_poblacion_a_10km=1.5),
    lambda c: c.assign(distancia_mediana_id36_km=c["distancia_mediana_km"] - 0.5),
    lambda c: c.assign(distancia_media_km=np.nan),
])
def test_validacion_rechaza_incoherencias(alteracion) -> None:
    with pytest.raises(ValueError):
        validar_cobertura(alteracion(_cobertura_valida()), 52)


def test_validacion_rechaza_oferta_sin_reconciliar() -> None:
    with pytest.raises(ValueError):
        validar_cobertura(_cobertura_valida(), 53)


def _escribir_insumos(tmp: Path) -> dict[str, Path]:
    """Una manzana poblada, una vacía y una entidad rural por comuna, y un establecimiento cada una."""
    censo = tmp / "censo"
    censo.mkdir()
    for capa, desplazamiento, n_per in (("Manzanas", 0.0, 100), ("Entidades", 0.02, 10)):
        filas = [(int(c), f"{capa[0]}{c}", n_per, -70.0 + i * 0.1, -33.0 - desplazamiento)
                 for i, c in enumerate(CUTS)]
        if capa == "Manzanas":
            filas.append((13101, "M-vacia", 0, -70.0, -34.0))
        cajas = [shapely.box(x, y, x + 0.001, y + 0.001) for *_, x, y in filas]
        pq.write_table(pa.table({
            "CUT": [f[0] for f in filas], "MANZENT": [f[1] for f in filas],
            "n_per": pa.array([float(f[2]) for f in filas]),
            "SHAPE": shapely.to_wkb(np.array(cajas, dtype=object)),
        }), censo / f"Cartografia_censo2024_RM_{capa}.parquet")

    pq.write_table(pa.table({"comuna_codigo": CUTS, "comuna_glosa": [f"C{c}" for c in CUTS],
                             "poblacion_censada": [120] * 52}), censo / "dim_poblacion_comuna_censo2024.parquet")
    codigos = list(range(1, 53))
    oferta_path = tmp / "dim_oferta_urgencia_rm.parquet"
    pq.write_table(pa.table({"establecimiento_codigo": codigos,
                             "reporto_id36_periodo": [i % 2 == 0 for i in range(52)]}), oferta_path)
    capa_path = tmp / "capa_oferta_urgencia_rm.parquet"
    escribir_geoparquet(pd.DataFrame({
        "establecimiento_codigo": codigos, "comuna_codigo": CUTS, "comuna_codigo_espacial": CUTS,
        "resultado_join_comuna": "coincide",
        "geometry": shapely.points([-70.0 + i * 0.1 for i in range(52)], [-33.0] * 52),
    }), capa_path, SCHEMA_CAPA, CRS_4674, ["Point"])
    return {"censo_dir": censo, "poblacion_path": censo / "dim_poblacion_comuna_censo2024.parquet",
            "oferta_path": oferta_path, "capa_oferta_path": capa_path}


def test_end_to_end_cumple_contrato_y_reporta_limitaciones(tmp_path: Path) -> None:
    cobertura, resumen = build_cobertura_urgencia_comuna(**_escribir_insumos(tmp_path))

    assert len(cobertura) == 52
    assert resumen["manzanas_sin_poblacion"] == 1 and resumen["poblacion_unidades"] == 52 * 110
    assert (cobertura["n_unidades_censales_pobladas"] == 2).all()
    assert cobertura["proporcion_poblacion_representada"].eq(110 / 120).all()

    salida = tmp_path / "geo" / "cobertura_urgencia_comuna.parquet"
    escribir_cobertura(cobertura, salida)
    assert validate_expected_schema(salida)

    reporte = render_reporte(cobertura, resumen)
    assert reporte.startswith(REPORT_TITLE)
    assert "## Limitaciones" in reporte and "Proximidad, no accesibilidad" in reporte


def test_falla_si_manzanas_y_entidades_comparten_unidad(tmp_path: Path) -> None:
    insumos = _escribir_insumos(tmp_path)
    entidades = insumos["censo_dir"] / "Cartografia_censo2024_RM_Entidades.parquet"
    tabla = pq.read_table(entidades)
    pq.write_table(tabla.set_column(1, "MANZENT", pa.array(["M13101"] + tabla["MANZENT"].to_pylist()[1:])),
                   entidades)
    with pytest.raises(ValueError, match="MANZENT"):
        build_cobertura_urgencia_comuna(**insumos)


def test_stage_registrado_despues_de_sus_dependencias() -> None:
    stage = pipeline.STAGES["build_cobertura_urgencia_comuna"]
    assert stage["module"] == "src.geo.build_cobertura_urgencia_comuna"
    for dependencia in stage["depends_on"]:
        assert pipeline.PIPELINE_ORDER.index(dependencia) < pipeline.PIPELINE_ORDER.index(
            "build_cobertura_urgencia_comuna"
        )
