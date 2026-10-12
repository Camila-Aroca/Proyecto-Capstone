"""Pruebas del módulo src/geo: CRS, capa comunal, join espacial y capa de oferta."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import shapely

import scripts.run_pipeline as pipeline
from src.data.output_contracts import validate_expected_schema
from src.geo.build_capa_oferta_urgencia_rm import SCHEMA, build_capa_oferta_urgencia_rm
from src.geo.capas import (
    JOIN_COINCIDE,
    JOIN_DIFIERE,
    JOIN_FUERA_RM,
    JOIN_LIMITE_AMBIGUO,
    JOIN_SIN_COORDENADAS,
    asignar_comuna,
    cargar_comunas,
    crs_geoparquet,
    escribir_geoparquet,
    puntos_desde_coordenadas,
    unir_atributos_comunales,
)

CRS_4674 = {"type": "GeographicCRS", "name": "SIRGAS 2000", "id": {"authority": "EPSG", "code": 4674}}
CRS_4326 = {"type": "GeographicCRS", "name": "WGS 84", "id": {"authority": "EPSG", "code": 4326}}
CUTS = [13101 + i for i in range(52)]


def _cuadrado(i: int) -> shapely.MultiPolygon:
    """Comuna sintética i: cuadrado unitario en una grilla de 13 columnas."""
    x, y = -72.0 + i % 13, -34.0 + i // 13
    return shapely.MultiPolygon([shapely.box(x, y, x + 1, y + 1)])


def _escribir_comunas(path: Path, crs: dict = CRS_4674, geometrias: list | None = None) -> Path:
    geometrias = geometrias or [_cuadrado(i) for i in range(52)]
    tabla = pa.table({
        "CUT": pa.array(CUTS, pa.int32()),
        "COMUNA": [f"Comuna {cut}" for cut in CUTS],
        "PROVINCIA": ["Santiago"] * 52,
        "SHAPE": shapely.to_wkb(np.array(geometrias, dtype=object)),
    })
    geo = {"version": "1.1.0", "primary_column": "SHAPE",
           "columns": {"SHAPE": {"encoding": "WKB", "geometry_types": ["MultiPolygon"], "crs": crs}}}
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabla.replace_schema_metadata({b"geo": json.dumps(geo).encode()}), path)
    return path


@pytest.fixture
def comunas_path(tmp_path: Path) -> Path:
    return _escribir_comunas(tmp_path / "comunal.parquet")


def test_cargar_comunas_normaliza_cut_y_valida(comunas_path: Path) -> None:
    comunas = cargar_comunas(comunas_path)
    assert len(comunas) == 52
    assert comunas["comuna_codigo"].iloc[0] == "13101"
    assert list(comunas.columns) == ["comuna_codigo", "comuna_glosa", "provincia_glosa", "geometry"]


def test_cargar_comunas_rechaza_otro_crs(tmp_path: Path) -> None:
    path = _escribir_comunas(tmp_path / "comunal.parquet", crs=CRS_4326)
    with pytest.raises(ValueError, match="EPSG:4326"):
        cargar_comunas(path)


def test_cargar_comunas_no_repara_geometrias_invalidas(tmp_path: Path) -> None:
    geometrias = [_cuadrado(i) for i in range(52)]
    geometrias[3] = shapely.MultiPolygon([shapely.Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])])
    path = _escribir_comunas(tmp_path / "comunal.parquet", geometrias=geometrias)
    with pytest.raises(ValueError, match="13104"):
        cargar_comunas(path)


def test_puntos_rechaza_coordenada_a_medias() -> None:
    with pytest.raises(ValueError, match="ambas"):
        puntos_desde_coordenadas(pd.Series([-33.4, np.nan]), pd.Series([-70.6, -70.6]))


def test_asignar_comuna_cubre_todos_los_resultados(comunas_path: Path) -> None:
    comunas = cargar_comunas(comunas_path)
    # Cuadrado 0 = 13101 en x [-72,-71]; cuadrado 1 = 13102 en x [-71,-70].
    latitud = pd.Series([-33.5, -33.5, -33.5, 10.0, np.nan])
    longitud = pd.Series([-71.5, -70.5, -71.0, 10.0, np.nan])
    declarada = pd.Series(["13101", "13101", "13101", "13101", "13101"])

    resultado = asignar_comuna(puntos_desde_coordenadas(latitud, longitud), declarada, comunas)

    assert resultado["resultado_join_comuna"].tolist() == [
        JOIN_COINCIDE, JOIN_DIFIERE, JOIN_LIMITE_AMBIGUO, JOIN_FUERA_RM, JOIN_SIN_COORDENADAS,
    ]
    assert resultado["comuna_codigo_espacial"].tolist()[:2] == ["13101", "13102"]
    assert resultado["comuna_codigo_espacial"].iloc[2:].isna().all()


def test_unir_atributos_conserva_comunas_sin_dato_como_nulo(comunas_path: Path) -> None:
    comunas = cargar_comunas(comunas_path)
    atributos = pd.DataFrame({"comuna_codigo": ["13101"], "tasa": [12.5]})
    unida = unir_atributos_comunales(comunas, atributos)
    assert len(unida) == 52
    assert unida.loc[unida["comuna_codigo"] == "13101", "tasa"].item() == 12.5
    assert unida.loc[unida["comuna_codigo"] != "13101", "tasa"].isna().all()


@pytest.mark.parametrize("atributos, mensaje", [
    (pd.DataFrame({"comuna_codigo": ["13101", "13101"], "tasa": [1.0, 2.0]}), "duplicado"),
    (pd.DataFrame({"comuna_codigo": ["05101"], "tasa": [1.0]}), "fuera de la capa"),
    (pd.DataFrame({"comuna_codigo": ["13101"], "comuna_glosa": ["x"]}), "repiten columnas"),
])
def test_unir_atributos_rechaza_joins_invalidos(comunas_path: Path, atributos: pd.DataFrame, mensaje: str) -> None:
    with pytest.raises(ValueError, match=mensaje):
        unir_atributos_comunales(cargar_comunas(comunas_path), atributos)


def _escribir_oferta(path: Path, filas: list[tuple]) -> Path:
    frame = pd.DataFrame(filas, columns=["establecimiento_codigo", "comuna_codigo", "latitud", "longitud"])
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)
    return path


def test_capa_oferta_end_to_end_cumple_contrato(tmp_path: Path, comunas_path: Path) -> None:
    oferta_path = _escribir_oferta(tmp_path / "dim.parquet", [
        (200, "13102", -33.5, -70.5),
        (100, "13101", -33.5, -71.5),
        (300, "13101", None, None),
    ])
    capa = build_capa_oferta_urgencia_rm(oferta_path, comunas_path)
    assert capa["establecimiento_codigo"].tolist() == [100, 200, 300]
    assert capa["resultado_join_comuna"].tolist() == [JOIN_COINCIDE, JOIN_COINCIDE, JOIN_SIN_COORDENADAS]

    salida = tmp_path / "geo" / "capa_oferta_urgencia_rm.parquet"
    escribir_geoparquet(capa, salida, SCHEMA, crs_geoparquet(comunas_path, "SHAPE"), ["Point"])

    assert validate_expected_schema(salida)
    geo = json.loads(pq.read_schema(salida).metadata[b"geo"])["columns"]["geometry"]
    assert geo["crs"]["id"]["code"] == 4674
    assert geo["bbox"] == [-71.5, -33.5, -70.5, -33.5]
    leida = pq.read_table(salida).to_pandas()
    assert leida["geometry"].iloc[2] is None
    assert shapely.from_wkb(leida["geometry"].iloc[0]).equals(shapely.Point(-71.5, -33.5))


def test_capa_oferta_marca_comuna_distinta_sin_corregirla(tmp_path: Path, comunas_path: Path) -> None:
    oferta_path = _escribir_oferta(tmp_path / "dim.parquet", [(100, "13101", -33.5, -70.5)])
    capa = build_capa_oferta_urgencia_rm(oferta_path, comunas_path)
    fila = capa.iloc[0]
    assert (fila["comuna_codigo"], fila["comuna_codigo_espacial"]) == ("13101", "13102")
    assert fila["resultado_join_comuna"] == JOIN_DIFIERE


def test_contrato_rechaza_capa_con_otro_crs(tmp_path: Path, comunas_path: Path) -> None:
    oferta_path = _escribir_oferta(tmp_path / "dim.parquet", [(100, "13101", -33.5, -71.5)])
    capa = build_capa_oferta_urgencia_rm(oferta_path, comunas_path)
    salida = tmp_path / "capa_oferta_urgencia_rm.parquet"
    escribir_geoparquet(capa, salida, SCHEMA, CRS_4326, ["Point"])
    with pytest.raises(ValueError, match="EPSG:4674"):
        validate_expected_schema(salida)


def test_stage_registrado_despues_de_sus_dependencias() -> None:
    stage = pipeline.STAGES["build_capa_oferta_urgencia_rm"]
    assert stage["module"] == "src.geo.build_capa_oferta_urgencia_rm"
    orden = pipeline.PIPELINE_ORDER
    for dependencia in stage["depends_on"]:
        assert orden.index(dependencia) < orden.index("build_capa_oferta_urgencia_rm")
