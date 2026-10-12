"""Capas base de la RM (comunas y establecimientos) con CRS explícito y joins territoriales.

CRS de trabajo: SIRGAS 2000 geográfico (EPSG:4674), el CRS real de la
cartografía Censo 2024 publicada por `clean_censo`. No se reproyecta: los joins
punto-en-polígono son correctos en coordenadas geográficas, y distancias o
áreas en metros quedan para la capa de accesibilidad, que deberá elegir su
propia proyección.

Las coordenadas de establecimientos del maestro DEIS se publican como
latitud/longitud decimales sin datum declarado y se interpretan en EPSG:4674.
SIRGAS 2000 y WGS 84 (realizaciones actuales) difieren en menos de 1 m, por
debajo de la precisión de esas coordenadas; el supuesto se declara aquí en vez
de transformar con un datum que la fuente no informa.

Ningún join corrige datos: cada establecimiento recibe un `resultado_join_comuna`
que deja visible si su punto coincide con la comuna declarada, cae en otra,
queda fuera de la RM, toca un límite compartido o no tiene coordenadas.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

COMUNAS_PATH: Final[Path] = Path("data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet")
COLUMNA_GEOMETRIA_CENSO: Final[str] = "SHAPE"
EPSG_TRABAJO: Final[int] = 4674
N_COMUNAS_RM: Final[int] = 52
PATRON_COMUNA_RM: Final[str] = r"^13\d{3}$"

JOIN_COINCIDE: Final[str] = "coincide"
JOIN_DIFIERE: Final[str] = "difiere"
JOIN_FUERA_RM: Final[str] = "fuera_de_rm"
JOIN_LIMITE_AMBIGUO: Final[str] = "limite_ambiguo"
JOIN_SIN_COORDENADAS: Final[str] = "sin_coordenadas"
RESULTADOS_JOIN: Final[frozenset[str]] = frozenset({
    JOIN_COINCIDE, JOIN_DIFIERE, JOIN_FUERA_RM, JOIN_LIMITE_AMBIGUO, JOIN_SIN_COORDENADAS,
})


def crs_geoparquet(path: Path, columna: str) -> dict[str, Any]:
    """PROJJSON del CRS declarado para `columna` en la metadata GeoParquet de `path`."""
    metadata = pq.read_schema(path).metadata or {}
    if b"geo" not in metadata:
        raise ValueError(f"{path.name}: sin metadata GeoParquet.")
    columnas = json.loads(metadata[b"geo"].decode("utf-8")).get("columns", {})
    crs = columnas.get(columna, {}).get("crs")
    if not isinstance(crs, dict):
        raise ValueError(f"{path.name}: la columna {columna} no declara CRS PROJJSON.")
    return crs


def epsg(crs: dict[str, Any]) -> int:
    """Código EPSG de un CRS PROJJSON; falla si no está identificado por EPSG."""
    identificador = crs.get("id") or {}
    if identificador.get("authority") != "EPSG" or not isinstance(identificador.get("code"), int):
        raise ValueError(f"CRS sin identificador EPSG: {crs.get('name')!r}")
    return identificador["code"]


def cargar_comunas(path: Path = COMUNAS_PATH) -> pd.DataFrame:
    """Capa comunal RM validada: `comuna_codigo` (CUT de 5 caracteres), glosas y geometría.

    El CUT entero de la cartografía se normaliza al `comuna_codigo` texto que usan
    los marts y `dim_oferta_urgencia_rm`, para que los joins sean directos.
    Geometrías nulas o inválidas hacen fallar la carga en vez de repararse.
    """
    if not path.is_file():
        raise FileNotFoundError(f"No existe la cartografía comunal: {path.as_posix()}")
    codigo_crs = epsg(crs_geoparquet(path, COLUMNA_GEOMETRIA_CENSO))
    if codigo_crs != EPSG_TRABAJO:
        raise ValueError(f"Cartografía comunal en EPSG:{codigo_crs}; se esperaba EPSG:{EPSG_TRABAJO}.")

    tabla = pq.read_table(path, columns=["CUT", "COMUNA", "PROVINCIA", COLUMNA_GEOMETRIA_CENSO]).to_pandas()
    comunas = pd.DataFrame({
        "comuna_codigo": tabla["CUT"].astype("int64").astype(str).str.zfill(5),
        "comuna_glosa": tabla["COMUNA"],
        "provincia_glosa": tabla["PROVINCIA"],
        "geometry": shapely.from_wkb(tabla[COLUMNA_GEOMETRIA_CENSO].to_numpy()),
    }).sort_values("comuna_codigo").reset_index(drop=True)

    if len(comunas) != N_COMUNAS_RM or comunas["comuna_codigo"].nunique() != N_COMUNAS_RM:
        raise ValueError(f"Se esperaban {N_COMUNAS_RM} comunas RM únicas; hay {comunas['comuna_codigo'].nunique()}.")
    if not comunas["comuna_codigo"].str.match(PATRON_COMUNA_RM).all():
        raise ValueError("comuna_codigo fuera del formato CUT de la RM (13xxx).")
    geometrias = comunas["geometry"].to_numpy()
    if shapely.is_missing(geometrias).any() or shapely.is_empty(geometrias).any():
        raise ValueError("Cartografía comunal con geometrías nulas o vacías.")
    invalidas = comunas.loc[~shapely.is_valid(geometrias), "comuna_codigo"].tolist()
    if invalidas:
        raise ValueError(f"Cartografía comunal con geometrías inválidas: {invalidas}")
    return comunas


def puntos_desde_coordenadas(latitud: pd.Series, longitud: pd.Series) -> np.ndarray:
    """Puntos (lon, lat) en EPSG:4674; None donde no hay coordenadas.

    Una coordenada con solo uno de sus dos valores es un dato roto, no un punto
    faltante, y hace fallar la construcción.
    """
    sin_lat, sin_lon = latitud.isna().to_numpy(), longitud.isna().to_numpy()
    if (sin_lat != sin_lon).any():
        raise ValueError("latitud y longitud deben ser ambas nulas o ambas informadas.")
    puntos = np.full(len(latitud), None, dtype=object)
    con_coordenadas = ~sin_lat
    puntos[con_coordenadas] = shapely.points(
        longitud.to_numpy(dtype=float)[con_coordenadas], latitud.to_numpy(dtype=float)[con_coordenadas]
    )
    return puntos


def asignar_comuna(
    puntos: np.ndarray, comuna_declarada: pd.Series, comunas: pd.DataFrame
) -> pd.DataFrame:
    """Join espacial punto-en-comuna y su contraste con la comuna declarada.

    Usa `intersects`, de modo que un punto sobre el límite exterior de la RM
    sigue asignado; si toca a más de una comuna (límite compartido) no se elige
    una arbitrariamente y queda como `limite_ambiguo`.
    """
    if len(puntos) != len(comuna_declarada):
        raise ValueError("puntos y comuna_declarada deben tener el mismo largo.")
    arbol = shapely.STRtree(comunas["geometry"].to_numpy())
    con_punto = np.flatnonzero(~shapely.is_missing(puntos))
    idx_local, idx_comuna = arbol.query(puntos[con_punto], predicate="intersects")
    candidatos = pd.DataFrame({
        "fila": con_punto[idx_local],
        "codigo": comunas["comuna_codigo"].to_numpy()[idx_comuna],
    })
    n_por_fila = candidatos["fila"].value_counts()

    espacial = pd.Series(pd.NA, index=range(len(puntos)), dtype="string")
    unicos = candidatos[candidatos["fila"].map(n_por_fila) == 1]
    espacial.iloc[unicos["fila"].to_numpy()] = unicos["codigo"].to_numpy()

    declarada = comuna_declarada.reset_index(drop=True).astype("string")
    resultado = np.select(
        [
            shapely.is_missing(puntos),
            np.isin(np.arange(len(puntos)), n_por_fila.index[n_por_fila > 1]),
            espacial.isna().to_numpy(),
            (espacial == declarada).fillna(False).to_numpy(dtype=bool),
        ],
        [JOIN_SIN_COORDENADAS, JOIN_LIMITE_AMBIGUO, JOIN_FUERA_RM, JOIN_COINCIDE],
        default=JOIN_DIFIERE,
    )
    return pd.DataFrame({"comuna_codigo_espacial": espacial, "resultado_join_comuna": resultado})


def unir_atributos_comunales(
    comunas: pd.DataFrame, atributos: pd.DataFrame, columnas: list[str] | None = None
) -> pd.DataFrame:
    """Agrega atributos por `comuna_codigo` a la capa comunal sin perder ni inventar comunas.

    Toda comuna de la capa se conserva; las que no tienen atributos quedan con
    nulos, nunca con ceros. Un código en `atributos` que no existe en la capa, o
    repetido, hace fallar el join.
    """
    if atributos["comuna_codigo"].duplicated().any():
        raise ValueError("atributos con comuna_codigo duplicado: el join comunal debe ser 1 a 1.")
    desconocidas = sorted(set(atributos["comuna_codigo"]) - set(comunas["comuna_codigo"]))
    if desconocidas:
        raise ValueError(f"atributos con comunas fuera de la capa RM: {desconocidas}")
    seleccion = atributos if columnas is None else atributos[["comuna_codigo", *columnas]]
    solapadas = (set(seleccion.columns) & set(comunas.columns)) - {"comuna_codigo"}
    if solapadas:
        raise ValueError(f"atributos repiten columnas de la capa comunal: {sorted(solapadas)}")
    return comunas.merge(seleccion, on="comuna_codigo", how="left", validate="one_to_one")


def escribir_geoparquet(
    frame: pd.DataFrame,
    path: Path,
    schema: pa.Schema,
    crs: dict[str, Any],
    tipos_geometria: list[str],
    columna_geometria: str = "geometry",
) -> None:
    """Escribe GeoParquet 1.1 (WKB) de forma atómica, declarando CRS, tipos y bbox."""
    geometrias = frame[columna_geometria].to_numpy()
    presentes = geometrias[~shapely.is_missing(geometrias)]
    salida = frame.copy()
    salida[columna_geometria] = shapely.to_wkb(geometrias)
    metadata_geo = {
        "version": "1.1.0",
        "primary_column": columna_geometria,
        "columns": {columna_geometria: {
            "encoding": "WKB",
            "geometry_types": tipos_geometria,
            "crs": crs,
            **({"bbox": [float(v) for v in shapely.total_bounds(presentes)]} if len(presentes) else {}),
        }},
    }
    tabla = pa.Table.from_pandas(salida, schema=schema, preserve_index=False)
    tabla = tabla.replace_schema_metadata({b"geo": json.dumps(metadata_geo).encode("utf-8")})

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f"{path.name}.", suffix=".tmp") as temp:
        temp_path = Path(temp.name)
    try:
        pq.write_table(tabla, temp_path, compression="snappy")
        if epsg(crs_geoparquet(temp_path, columna_geometria)) != epsg(crs):
            raise ValueError(f"GeoParquet temporal con CRS distinto al declarado: {temp_path.as_posix()}")
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
