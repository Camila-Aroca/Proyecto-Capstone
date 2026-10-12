"""Publica la capa de puntos de la oferta de urgencia RM con su comuna espacial.

Grano: 1 fila = 1 establecimiento de `dim_oferta_urgencia_rm`. Solo agrega la
geometría y el resultado del join espacial; los atributos del establecimiento
se obtienen uniendo por `establecimiento_codigo` con la dimensión, sin
duplicarlos aquí. El CRS publicado es el mismo PROJJSON de la cartografía
comunal (EPSG:4674). Ver supuestos de CRS y del join en `src/geo/capas.py`.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.geo.capas import (
    COLUMNA_GEOMETRIA_CENSO,
    COMUNAS_PATH,
    JOIN_COINCIDE,
    RESULTADOS_JOIN,
    asignar_comuna,
    cargar_comunas,
    crs_geoparquet,
    escribir_geoparquet,
    puntos_desde_coordenadas,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OFERTA_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
OUTPUT_PATH: Final[Path] = Path("data/processed/geo/capa_oferta_urgencia_rm.parquet")

SCHEMA: Final[pa.Schema] = pa.schema([
    ("establecimiento_codigo", pa.int64()),
    ("comuna_codigo", pa.string()),
    ("comuna_codigo_espacial", pa.string()),
    ("resultado_join_comuna", pa.string()),
    ("geometry", pa.binary()),
])


def validar_capa(capa: pd.DataFrame, n_oferta: int) -> None:
    """Grano, dominio del resultado y coherencia entre resultado y códigos."""
    if len(capa) != n_oferta:
        raise ValueError(f"La capa tiene {len(capa)} filas; la dimensión de oferta tiene {n_oferta}.")
    if capa["establecimiento_codigo"].duplicated().any():
        raise ValueError("establecimiento_codigo duplicado en la capa de oferta.")
    fuera_dominio = set(capa["resultado_join_comuna"]) - RESULTADOS_JOIN
    if fuera_dominio:
        raise ValueError(f"resultado_join_comuna fuera del dominio: {sorted(fuera_dominio)}")
    coincide = capa["resultado_join_comuna"] == JOIN_COINCIDE
    iguales = (capa["comuna_codigo_espacial"] == capa["comuna_codigo"]).fillna(False).astype(bool)
    if not (coincide == iguales).all():
        raise ValueError("resultado_join_comuna incoherente con comuna_codigo_espacial.")


def build_capa_oferta_urgencia_rm(
    oferta_path: Path = OFERTA_PATH, comunas_path: Path = COMUNAS_PATH
) -> pd.DataFrame:
    """Construye y valida la capa de puntos de la oferta (geometría como objetos shapely)."""
    if not oferta_path.is_file():
        raise FileNotFoundError(f"No existe la dimensión de oferta: {oferta_path.as_posix()}")
    oferta = pq.read_table(
        oferta_path, columns=["establecimiento_codigo", "comuna_codigo", "latitud", "longitud"]
    ).to_pandas()
    comunas = cargar_comunas(comunas_path)

    puntos = puntos_desde_coordenadas(oferta["latitud"], oferta["longitud"])
    join = asignar_comuna(puntos, oferta["comuna_codigo"], comunas)
    capa = pd.DataFrame({
        "establecimiento_codigo": oferta["establecimiento_codigo"].astype("int64").to_numpy(),
        "comuna_codigo": oferta["comuna_codigo"].to_numpy(),
        "comuna_codigo_espacial": join["comuna_codigo_espacial"].to_numpy(),
        "resultado_join_comuna": join["resultado_join_comuna"].to_numpy(),
        "geometry": puntos,
    }).sort_values("establecimiento_codigo").reset_index(drop=True)

    validar_capa(capa, len(oferta))
    return capa


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica la capa de puntos de la oferta de urgencia RM.")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()

    capa = build_capa_oferta_urgencia_rm()
    crs = crs_geoparquet(COMUNAS_PATH, COLUMNA_GEOMETRIA_CENSO)
    escribir_geoparquet(capa, OUTPUT_PATH, SCHEMA, crs, ["Point"])
    logger.info(
        "Capa de oferta de urgencia publicada: %s filas -> %s. Resultado del join comunal: %s.",
        len(capa), OUTPUT_PATH.as_posix(), capa["resultado_join_comuna"].value_counts().to_dict(),
    )


if __name__ == "__main__":
    main()
