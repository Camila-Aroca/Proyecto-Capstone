"""MVP de cobertura territorial simple: distancia de la población a la oferta de urgencia.

Grano: 1 fila = 1 comuna RM (52). La población se representa con las manzanas
(urbano) y entidades (rural) del Censo 2024, cada una como un punto ponderado
por `n_per`; ambas capas no se solapan (`MANZENT` disjunto). Para cada punto se
calcula la distancia en línea recta (haversine sobre el elipsoide aproximado por
una esfera de radio medio) al establecimiento más cercano de
`capa_oferta_urgencia_rm`, sin importar la comuna del establecimiento, y se
agrega por comuna con cuantiles y proporciones ponderados por población.

Es una métrica de proximidad, no de accesibilidad: no usa red vial, transporte
público ni tiempos de viaje (eso es materia de OSM/GTFS e isócronas). Las
limitaciones se publican en `reports/geo/cobertura_urgencia_comuna.md`.

El punto representativo de cada unidad es `point_on_surface` (siempre dentro
del polígono). Las geometrías inválidas que publica el Censo no se reparan: para
ellas se usa el centroide y se informan en el reporte.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from src.geo.capas import COLUMNA_GEOMETRIA_CENSO, N_COMUNAS_RM, PATRON_COMUNA_RM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CENSO_DIR: Final[Path] = Path("data/processed/censo")
CAPAS_POBLACION: Final[tuple[str, ...]] = ("Manzanas", "Entidades")
POBLACION_PATH: Final[Path] = CENSO_DIR / "dim_poblacion_comuna_censo2024.parquet"
OFERTA_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
CAPA_OFERTA_PATH: Final[Path] = Path("data/processed/geo/capa_oferta_urgencia_rm.parquet")
OUTPUT_PATH: Final[Path] = Path("data/processed/geo/cobertura_urgencia_comuna.parquet")
REPORT_PATH: Final[Path] = Path("reports/geo/cobertura_urgencia_comuna.md")
REPORT_TITLE: Final[str] = "# Cobertura territorial simple de la oferta de urgencia (RM)"

RADIO_TIERRA_KM: Final[float] = 6371.0088
UMBRALES_KM: Final[tuple[int, ...]] = (2, 5, 10)
BLOQUE_ESTABLECIMIENTOS: Final[int] = 25

SCHEMA: Final[pa.Schema] = pa.schema([
    ("comuna_codigo", pa.string()),
    ("comuna_glosa", pa.string()),
    ("poblacion_censada_2024", pa.int64()),
    ("poblacion_unidades_censales", pa.int64()),
    ("proporcion_poblacion_representada", pa.float64()),
    ("n_unidades_censales_pobladas", pa.int64()),
    ("n_oferta_urgencia_en_comuna", pa.int64()),
    ("habitantes_por_establecimiento", pa.float64()),
    ("distancia_media_km", pa.float64()),
    ("distancia_mediana_km", pa.float64()),
    ("distancia_p90_km", pa.float64()),
    *[(f"proporcion_poblacion_a_{u}km", pa.float64()) for u in UMBRALES_KM],
    ("distancia_mediana_id36_km", pa.float64()),
    ("proporcion_poblacion_a_5km_id36", pa.float64()),
])


def cargar_unidades_poblacion(censo_dir: Path = CENSO_DIR) -> tuple[pd.DataFrame, dict[str, int]]:
    """Puntos representativos de manzanas y entidades con población (`n_per` > 0).

    Devuelve las unidades y un resumen por capa (filas, sin población, geometrías
    inválidas) para el reporte. Una geometría nula o un `n_per` nulo o negativo
    hace fallar la carga; las unidades con `n_per` = 0 no pesan y se descartan.
    """
    frames: list[pd.DataFrame] = []
    resumen: dict[str, int] = {}
    for capa in CAPAS_POBLACION:
        path = censo_dir / f"Cartografia_censo2024_RM_{capa}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"No existe la capa censal: {path.as_posix()}")
        tabla = pq.read_table(path, columns=["CUT", "MANZENT", "n_per", COLUMNA_GEOMETRIA_CENSO]).to_pandas()
        if tabla["n_per"].isna().any() or (tabla["n_per"] < 0).any():
            raise ValueError(f"{capa}: n_per nulo o negativo.")
        geometrias = shapely.from_wkb(tabla[COLUMNA_GEOMETRIA_CENSO].to_numpy())
        if shapely.is_missing(geometrias).any() or shapely.is_empty(geometrias).any():
            raise ValueError(f"{capa}: geometrías nulas o vacías.")
        validas = shapely.is_valid(geometrias)
        puntos = np.where(
            validas, shapely.point_on_surface(np.where(validas, geometrias, None)), shapely.centroid(geometrias)
        )
        poblada = (tabla["n_per"] > 0).to_numpy()
        resumen[f"{capa.lower()}_filas"] = len(tabla)
        resumen[f"{capa.lower()}_sin_poblacion"] = int((~poblada).sum())
        resumen[f"{capa.lower()}_invalidas_pobladas"] = int((~validas & poblada).sum())
        frames.append(pd.DataFrame({
            "manzent": tabla["MANZENT"].to_numpy(),
            "comuna_codigo": tabla["CUT"].astype("int64").astype(str).str.zfill(5).to_numpy(),
            "poblacion": tabla["n_per"].astype("int64").to_numpy(),
            "longitud": shapely.get_x(puntos),
            "latitud": shapely.get_y(puntos),
        })[poblada])

    unidades = pd.concat(frames, ignore_index=True)
    if unidades["manzent"].duplicated().any():
        raise ValueError("Manzanas y entidades comparten MANZENT: la población se contaría dos veces.")
    if not unidades["comuna_codigo"].str.match(PATRON_COMUNA_RM).all():
        raise ValueError("Unidades censales con comuna fuera de la RM.")
    return unidades.drop(columns="manzent"), resumen


def distancia_minima_km(
    longitud: np.ndarray, latitud: np.ndarray, destino_longitud: np.ndarray, destino_latitud: np.ndarray
) -> np.ndarray:
    """Distancia haversine (km) de cada origen al destino más cercano.

    Procesa los destinos por bloques para acotar la memoria a
    `len(origenes) × BLOQUE_ESTABLECIMIENTOS` en vez de la matriz completa.
    """
    if len(destino_longitud) == 0:
        raise ValueError("Se necesita al menos un destino para calcular distancias.")
    lat1, lon1 = np.radians(latitud)[:, None], np.radians(longitud)[:, None]
    minima = np.full(len(longitud), np.inf)
    for inicio in range(0, len(destino_longitud), BLOQUE_ESTABLECIMIENTOS):
        lat2 = np.radians(destino_latitud[inicio:inicio + BLOQUE_ESTABLECIMIENTOS])[None, :]
        lon2 = np.radians(destino_longitud[inicio:inicio + BLOQUE_ESTABLECIMIENTOS])[None, :]
        a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
        minima = np.minimum(minima, (2 * RADIO_TIERRA_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))).min(axis=1))
    return minima


def cuantil_ponderado(valores: np.ndarray, pesos: np.ndarray, q: float) -> float:
    """Menor valor cuya población acumulada alcanza la fracción `q` del total."""
    orden = np.argsort(valores, kind="stable")
    acumulado = np.cumsum(pesos[orden])
    return float(valores[orden][np.searchsorted(acumulado, q * acumulado[-1])])


def _resumen_comuna(grupo: pd.DataFrame) -> pd.Series:
    pesos = grupo["poblacion"].to_numpy(dtype=float)
    distancia, distancia_id36 = grupo["distancia_km"].to_numpy(), grupo["distancia_id36_km"].to_numpy()
    total = pesos.sum()
    return pd.Series({
        "poblacion_unidades_censales": int(total),
        "n_unidades_censales_pobladas": len(grupo),
        "distancia_media_km": float((distancia * pesos).sum() / total),
        "distancia_mediana_km": cuantil_ponderado(distancia, pesos, 0.5),
        "distancia_p90_km": cuantil_ponderado(distancia, pesos, 0.9),
        **{f"proporcion_poblacion_a_{u}km": float(pesos[distancia <= u].sum() / total) for u in UMBRALES_KM},
        "distancia_mediana_id36_km": cuantil_ponderado(distancia_id36, pesos, 0.5),
        "proporcion_poblacion_a_5km_id36": float(pesos[distancia_id36 <= 5].sum() / total),
    })


def calcular_cobertura(
    unidades: pd.DataFrame, oferta: pd.DataFrame, poblacion: pd.DataFrame
) -> pd.DataFrame:
    """Cobertura por comuna.

    `oferta` trae `longitud`, `latitud`, `comuna_codigo` y `reporto_id36_periodo`;
    `poblacion` es la dimensión oficial (`comuna_codigo`, `comuna_glosa`,
    `poblacion_censada`). Toda comuna de `poblacion` queda en la salida.
    """
    con_id36 = oferta[oferta["reporto_id36_periodo"].astype(bool)]
    unidades = unidades.assign(
        distancia_km=distancia_minima_km(
            unidades["longitud"].to_numpy(), unidades["latitud"].to_numpy(),
            oferta["longitud"].to_numpy(), oferta["latitud"].to_numpy(),
        ),
        distancia_id36_km=distancia_minima_km(
            unidades["longitud"].to_numpy(), unidades["latitud"].to_numpy(),
            con_id36["longitud"].to_numpy(), con_id36["latitud"].to_numpy(),
        ),
    )
    por_comuna = unidades.groupby("comuna_codigo")[["poblacion", "distancia_km", "distancia_id36_km"]].apply(
        _resumen_comuna
    )
    desconocidas = sorted(set(por_comuna.index) - set(poblacion["comuna_codigo"]))
    if desconocidas:
        raise ValueError(f"Unidades censales en comunas ausentes de la dimensión de población: {desconocidas}")

    n_oferta = oferta.groupby("comuna_codigo").size()
    cobertura = poblacion.rename(columns={"poblacion_censada": "poblacion_censada_2024"})[
        ["comuna_codigo", "comuna_glosa", "poblacion_censada_2024"]
    ].merge(por_comuna, left_on="comuna_codigo", right_index=True, how="left", validate="one_to_one")
    cobertura["n_oferta_urgencia_en_comuna"] = (
        cobertura["comuna_codigo"].map(n_oferta).fillna(0).astype("int64")
    )
    cobertura["habitantes_por_establecimiento"] = (
        cobertura["poblacion_censada_2024"] / cobertura["n_oferta_urgencia_en_comuna"].replace(0, np.nan)
    )
    cobertura["proporcion_poblacion_representada"] = (
        cobertura["poblacion_unidades_censales"] / cobertura["poblacion_censada_2024"]
    )
    return cobertura[SCHEMA.names].sort_values("comuna_codigo").reset_index(drop=True)


def validar_cobertura(cobertura: pd.DataFrame, n_oferta: int) -> None:
    """Grano, dominios y coherencia interna de las métricas."""
    if len(cobertura) != N_COMUNAS_RM or cobertura["comuna_codigo"].nunique() != N_COMUNAS_RM:
        raise ValueError(f"Se esperaban {N_COMUNAS_RM} comunas únicas; hay {cobertura['comuna_codigo'].nunique()}.")
    metricas = [c for c in SCHEMA.names if c.startswith(("distancia_", "proporcion_poblacion_a_"))]
    if cobertura[metricas + ["poblacion_unidades_censales"]].isna().any().any():
        raise ValueError("Comunas sin unidades censales pobladas: no hay base para medir cobertura.")
    if (cobertura[[c for c in metricas if c.startswith("distancia_")]] < 0).any().any():
        raise ValueError("Distancias negativas.")
    proporciones = cobertura[[c for c in metricas if c.startswith("proporcion_")]]
    if ((proporciones < 0) | (proporciones > 1)).any().any():
        raise ValueError("Proporciones de población fuera de [0, 1].")
    umbrales = [cobertura[f"proporcion_poblacion_a_{u}km"] for u in UMBRALES_KM]
    if any((menor > mayor + 1e-12).any() for menor, mayor in zip(umbrales, umbrales[1:])):
        raise ValueError("La proporción cubierta debe crecer con el umbral de distancia.")
    if (cobertura["distancia_mediana_km"] > cobertura["distancia_p90_km"]).any():
        raise ValueError("Mediana mayor que el percentil 90.")
    if (cobertura["distancia_mediana_id36_km"] < cobertura["distancia_mediana_km"] - 1e-9).any():
        raise ValueError("La oferta con ID36 es un subconjunto: su distancia mediana no puede ser menor.")
    if cobertura["n_oferta_urgencia_en_comuna"].sum() != n_oferta:
        raise ValueError("Los establecimientos por comuna no reconcilian con la oferta.")


def build_cobertura_urgencia_comuna(
    censo_dir: Path = CENSO_DIR,
    poblacion_path: Path = POBLACION_PATH,
    oferta_path: Path = OFERTA_PATH,
    capa_oferta_path: Path = CAPA_OFERTA_PATH,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Construye y valida la cobertura comunal; devuelve también el resumen de insumos."""
    for path in (poblacion_path, oferta_path, capa_oferta_path):
        if not path.is_file():
            raise FileNotFoundError(f"No existe el insumo: {path.as_posix()}")
    capa = pq.read_table(capa_oferta_path, columns=["establecimiento_codigo", "comuna_codigo", "geometry"]).to_pandas()
    puntos = shapely.from_wkb(capa["geometry"].to_numpy())
    if shapely.is_missing(puntos).any():
        raise ValueError("Establecimientos de la oferta sin coordenadas: no se pueden medir distancias.")
    flags = pq.read_table(oferta_path, columns=["establecimiento_codigo", "reporto_id36_periodo"]).to_pandas()
    oferta = pd.DataFrame({
        "establecimiento_codigo": capa["establecimiento_codigo"].astype("int64"),
        "comuna_codigo": capa["comuna_codigo"],
        "longitud": shapely.get_x(puntos),
        "latitud": shapely.get_y(puntos),
    }).merge(flags.astype({"establecimiento_codigo": "int64"}), on="establecimiento_codigo",
             how="left", validate="one_to_one")
    if oferta["reporto_id36_periodo"].isna().any():
        raise ValueError("La capa de oferta tiene establecimientos ausentes de la dimensión de oferta.")

    unidades, resumen = cargar_unidades_poblacion(censo_dir)
    poblacion = pq.read_table(
        poblacion_path, columns=["comuna_codigo", "comuna_glosa", "poblacion_censada"]
    ).to_pandas()
    cobertura = calcular_cobertura(unidades, oferta, poblacion)
    validar_cobertura(cobertura, len(oferta))
    resumen.update({
        "n_oferta": len(oferta),
        "n_oferta_id36": int(oferta["reporto_id36_periodo"].sum()),
        "poblacion_unidades": int(unidades["poblacion"].sum()),
        "poblacion_oficial": int(poblacion["poblacion_censada"].sum()),
        **{f"poblacion_a_{u}km": int(round((cobertura[f"proporcion_poblacion_a_{u}km"]
                                            * cobertura["poblacion_unidades_censales"]).sum()))
           for u in UMBRALES_KM},
    })
    return cobertura, resumen


def _pct(valor: float) -> str:
    return f"{valor:.1%}".replace(".", ",")


def _km(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def _miles(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def render_reporte(cobertura: pd.DataFrame, resumen: dict[str, int]) -> str:
    """Reporte Markdown: método, resultados RM, tabla comunal y limitaciones."""
    total = resumen["poblacion_unidades"]
    peores = cobertura.sort_values("distancia_mediana_km", ascending=False).head(5)
    lineas = [
        REPORT_TITLE,
        "",
        "Generado por el stage `build_cobertura_urgencia_comuna` (`src/geo/build_cobertura_urgencia_comuna.py`).",
        "Dataset: `data/processed/geo/cobertura_urgencia_comuna.parquet`; diccionario en",
        "[`reports/dictionary/diccionario_cobertura_urgencia_comuna.md`]"
        "(../dictionary/diccionario_cobertura_urgencia_comuna.md).",
        "",
        "## Método",
        "",
        "- **Población:** manzanas (urbano) y entidades (rural) del Censo 2024, cada una representada por un punto"
        " interior (`point_on_surface`) y ponderada por su población censada (`n_per`).",
        f"- **Oferta:** los {resumen['n_oferta']} establecimientos de `capa_oferta_urgencia_rm` (hospitales, SAPU, SAR,"
        f" SUR y la excepción CEAR documentada). La variante `_id36` usa solo los {resumen['n_oferta_id36']} que"
        " reportaron atenciones de salud mental (ID36) en 2021-2025.",
        "- **Distancia:** línea recta (haversine, radio medio terrestre) desde cada unidad censal al establecimiento más"
        " cercano, esté o no en la misma comuna.",
        "- **Agregación:** por comuna de la unidad censal; la mediana, el percentil 90 y las proporciones están"
        " ponderados por población. Los umbrales de "
        + ", ".join(f"{u}" for u in UMBRALES_KM)
        + " km son descriptivos, no estándares normativos.",
        "",
        "## Resultados RM",
        "",
        "| Indicador | Valor |",
        "|---|---|",
        f"| Población representada por las unidades censales | {_miles(total)} de {_miles(resumen['poblacion_oficial'])}"
        f" ({_pct(total / resumen['poblacion_oficial'])}) |",
        *[f"| Población a ≤ {u} km en línea recta de un establecimiento | {_miles(resumen[f'poblacion_a_{u}km'])}"
          f" ({_pct(resumen[f'poblacion_a_{u}km'] / total)}) |" for u in UMBRALES_KM],
        f"| Comunas sin establecimiento de la oferta en su territorio |"
        f" {int((cobertura['n_oferta_urgencia_en_comuna'] == 0).sum())} |",
        "",
        "Comunas con mayor distancia mediana: "
        + "; ".join(f"{r.comuna_glosa} ({_km(r.distancia_mediana_km)} km)" for r in peores.itertuples())
        + ".",
        "",
        "## Tabla comunal",
        "",
        "| Comuna | Población 2024 | Establecimientos | Hab./establecimiento | Mediana km | P90 km |"
        + "".join(f" ≤ {u} km |" for u in UMBRALES_KM)
        + " Mediana km ID36 | ≤ 5 km ID36 |",
        "|---|---:|---:|---:|---:|---:|" + "---:|" * len(UMBRALES_KM) + "---:|---:|",
    ]
    for r in cobertura.sort_values("distancia_mediana_km", ascending=False).itertuples():
        hab = "—" if pd.isna(r.habitantes_por_establecimiento) else _miles(r.habitantes_por_establecimiento)
        lineas.append(
            f"| {r.comuna_glosa} ({r.comuna_codigo}) | {_miles(r.poblacion_censada_2024)} |"
            f" {r.n_oferta_urgencia_en_comuna} | {hab} | {_km(r.distancia_mediana_km)} | {_km(r.distancia_p90_km)} |"
            + "".join(f" {_pct(getattr(r, f'proporcion_poblacion_a_{u}km'))} |" for u in UMBRALES_KM)
            + f" {_km(r.distancia_mediana_id36_km)} | {_pct(r.proporcion_poblacion_a_5km_id36)} |"
        )
    lineas += [
        "",
        "## Limitaciones",
        "",
        "- **Proximidad, no accesibilidad.** La distancia en línea recta subestima el recorrido real y no considera"
        " red vial, relieve, transporte público, horarios ni tiempos de viaje. Esa evaluación corresponde a"
        " OSM/GTFS e isócronas (NEXT-033/NEXT-034).",
        "- **Disponibilidad, no capacidad.** Un establecimiento cuenta igual sin importar su tipo, horario, dotación"
        " o resolutividad en salud mental; no es una medida de capacidad ni de cupos.",
        f"- **Denominador poblacional.** Las unidades censales suman {_pct(total / resumen['poblacion_oficial'])}"
        " de la población censada oficial; la brecha ya documentada en `clean_censo` no se imputa. Las proporciones"
        " de cobertura usan como denominador la población de las unidades, y `habitantes_por_establecimiento` usa la"
        " población oficial.",
        f"- **Unidades sin población y geometrías inválidas.** Se descartan {_miles(resumen['manzanas_sin_poblacion'])}"
        f" manzanas y {_miles(resumen['entidades_sin_poblacion'])} entidades con `n_per` = 0 (no pesan). "
        f"{resumen['manzanas_invalidas_pobladas'] + resumen['entidades_invalidas_pobladas']} unidades pobladas tienen"
        " geometría inválida en la fuente; no se reparan y se representan por su centroide.",
        "- **Efecto borde.** Solo se considera la oferta de la RM: la población cercana al límite regional podría"
        " tener un establecimiento más próximo en otra región.",
        "- **Temporalidades distintas.** La población es el Censo 2024 y la oferta es el snapshot actual del"
        " catálogo DEIS; no representan el mismo instante.",
        "- **Lectura ecológica.** Son métricas territoriales agregadas: no describen el acceso de ninguna persona"
        " ni se cruzan con Urgencias o Egresos a nivel de registro.",
        "",
    ]
    return "\n".join(lineas)


def _escribir_texto_atomico(texto: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent,
                                     prefix=f"{path.name}.", suffix=".tmp") as temp:
        temp.write(texto)
        temp_path = Path(temp.name)
    temp_path.replace(path)


def escribir_cobertura(cobertura: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    """Escribe el Parquet de forma atómica con el schema declarado."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tabla = pa.Table.from_pandas(cobertura, schema=SCHEMA, preserve_index=False)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f"{path.name}.", suffix=".tmp") as temp:
        temp_path = Path(temp.name)
    try:
        pq.write_table(tabla, temp_path, compression="snappy")
        if pq.read_schema(temp_path).names != SCHEMA.names:
            raise ValueError("Parquet temporal con columnas distintas al schema.")
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcula la cobertura territorial simple de la oferta de urgencia.")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()

    cobertura, resumen = build_cobertura_urgencia_comuna()
    escribir_cobertura(cobertura)
    _escribir_texto_atomico(render_reporte(cobertura, resumen), REPORT_PATH)
    logger.info(
        "Cobertura publicada: %s comunas -> %s; reporte -> %s. Población a ≤5 km: %s de %s.",
        len(cobertura), OUTPUT_PATH.as_posix(), REPORT_PATH.as_posix(),
        resumen["poblacion_a_5km"], resumen["poblacion_unidades"],
    )


if __name__ == "__main__":
    main()
