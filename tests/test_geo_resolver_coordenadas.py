"""Pruebas de la lista de resolución de coordenadas de establecimientos."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_dim_oferta_urgencia_rm import ESTADO_VIGENTE
from src.data.output_contracts import validate_expected_schema
from src.geo.capas import cargar_comunas
from src.geo.resolver_coordenadas_establecimientos import (
    RES_EXCLUIR_FUERA_OFERTA,
    RES_EXCLUIR_NO_VIGENTE,
    RES_REQUIERE_GEOCODIFICACION,
    _atomic_write,
    resolver_coordenadas,
)
from tests.test_geo_capas import _escribir_comunas

CERRADO = "cerrado"


@pytest.fixture
def comunas(tmp_path: Path) -> pd.DataFrame:
    return cargar_comunas(_escribir_comunas(tmp_path / "comunal.parquet"))


def _maestro(filas: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(filas, columns=[
        "establecimiento_codigo", "comuna_codigo", "estado_funcionamiento", "latitud", "longitud",
    ]).assign(
        establecimiento_glosa="x", tipo_establecimiento_glosa="t", comuna_glosa="c", fecha_cierre=None,
    ).astype({"establecimiento_codigo": str})


# En la comuna sintética 13101 (x en [-72,-71]) y 13102 (x en [-71,-70]).
def test_clasifica_problemas_y_resoluciones(comunas: pd.DataFrame) -> None:
    maestro = _maestro([
        (1, "13101", ESTADO_VIGENTE, -33.5, -71.5),   # coincide: no entra
        (2, "13101", CERRADO, None, None),             # sin coordenadas, cerrado
        (3, "13101", ESTADO_VIGENTE, None, None),      # sin coordenadas, vigente, fuera de oferta
        (4, "13101", ESTADO_VIGENTE, -33.5, -70.5),   # cae en 13102
        (5, "13101", ESTADO_VIGENTE, -39.0, -72.2),   # fuera de la RM
        (6, "13101", ESTADO_VIGENTE, None, None),      # sin coordenadas, en la oferta
    ])
    resultado = resolver_coordenadas(maestro, {6}, comunas).set_index("establecimiento_codigo")

    assert list(resultado.index) == [2, 3, 4, 5, 6]
    assert resultado.loc[2, ["problema_coordenadas", "resolucion"]].tolist() == ["sin_coordenadas", RES_EXCLUIR_NO_VIGENTE]
    assert resultado.loc[3, "resolucion"] == RES_EXCLUIR_FUERA_OFERTA
    assert resultado.loc[4, ["problema_coordenadas", "comuna_codigo_espacial"]].tolist() == ["difiere", "13102"]
    assert resultado.loc[5, "problema_coordenadas"] == "fuera_de_rm"
    assert resultado.loc[6, "resolucion"] == RES_REQUIERE_GEOCODIFICACION
    assert resultado["justificacion"].str.len().min() > 0


def test_no_modifica_ni_imputa_coordenadas(comunas: pd.DataFrame) -> None:
    maestro = _maestro([(5, "13101", ESTADO_VIGENTE, -39.0, -72.2), (2, "13101", CERRADO, None, None)])
    resultado = resolver_coordenadas(maestro, set(), comunas).set_index("establecimiento_codigo")
    assert resultado.loc[5, ["latitud", "longitud"]].tolist() == [-39.0, -72.2]
    assert resultado.loc[2, ["latitud", "longitud"]].isna().all()


def test_sin_problemas_devuelve_lista_vacia(comunas: pd.DataFrame) -> None:
    resultado = resolver_coordenadas(_maestro([(1, "13101", ESTADO_VIGENTE, -33.5, -71.5)]), set(), comunas)
    assert resultado.empty


def test_contrato_acepta_lista_y_lista_vacia(comunas: pd.DataFrame, tmp_path: Path) -> None:
    maestro = _maestro([(2, "13101", CERRADO, None, None), (5, "13101", ESTADO_VIGENTE, -39.0, -72.2)])
    salida = tmp_path / "establecimientos_coordenadas_resolucion.csv"
    _atomic_write(resolver_coordenadas(maestro, set(), comunas), salida)
    assert validate_expected_schema(salida)

    vacia = tmp_path / "vacia" / "establecimientos_coordenadas_resolucion.csv"
    _atomic_write(resolver_coordenadas(_maestro([(1, "13101", ESTADO_VIGENTE, -33.5, -71.5)]), set(), comunas), vacia)
    assert validate_expected_schema(vacia)


def test_contrato_rechaza_resolucion_vacia(comunas: pd.DataFrame, tmp_path: Path) -> None:
    resultado = resolver_coordenadas(_maestro([(2, "13101", CERRADO, None, None)]), set(), comunas)
    salida = tmp_path / "establecimientos_coordenadas_resolucion.csv"
    _atomic_write(resultado.assign(resolucion=""), salida)
    with pytest.raises(ValueError):
        validate_expected_schema(salida)


def test_stage_registrado_despues_de_sus_dependencias() -> None:
    stage = pipeline.STAGES["resolve_coordenadas_establecimientos"]
    assert stage["module"] == "src.geo.resolver_coordenadas_establecimientos"
    for dependencia in stage["depends_on"]:
        assert pipeline.PIPELINE_ORDER.index(dependencia) < pipeline.PIPELINE_ORDER.index(
            "resolve_coordenadas_establecimientos"
        )
