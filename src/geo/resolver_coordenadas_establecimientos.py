"""Lista final de resolución de coordenadas faltantes o anómalas de establecimientos.

Recorre el maestro de establecimientos RM y, para cada uno cuya coordenada no
es utilizable, publica un problema y una resolución justificada. No geocodifica
ni imputa: ninguna coordenada se inventa, se reemplaza por un centroide ni se
corrige; las coordenadas se publican tal como vienen en la fuente. La
resolución solo decide si el caso se excluye de las capas de accesibilidad o si
bloquea su cálculo.

Problemas (`problema_coordenadas`), todos medidos con `src.geo.capas`:
- `sin_coordenadas`: latitud y longitud nulas.
- `fuera_de_rm`: la coordenada no cae en ninguna comuna de la RM.
- `difiere`: cae en una comuna distinta de la declarada. No se puede
  determinar si el error está en la coordenada o en la comuna declarada.
- `limite_ambiguo`: cae sobre un límite compartido entre comunas.

Resoluciones (`resolucion`), en orden de precedencia:
- `requiere_geocodificacion`: el establecimiento integra la oferta de urgencia
  (`dim_oferta_urgencia_rm`), así que su coordenada es insumo de accesibilidad.
  Debe resolverse con una fuente verificable (p. ej. geocodificación de la
  dirección) antes de calcular isócronas; este stage no lo hace.
- `excluir_no_vigente`: el establecimiento ya no opera, por lo que no forma
  parte de la oferta actual que mide la accesibilidad.
- `excluir_fuera_de_oferta`: vigente, pero fuera de la oferta de urgencia; su
  coordenada no se usa en este alcance, así que no se geocodifica ni se corrige.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_dim_oferta_urgencia_rm import ESTADO_VIGENTE
from src.geo.capas import (
    COMUNAS_PATH,
    JOIN_COINCIDE,
    JOIN_DIFIERE,
    JOIN_FUERA_RM,
    JOIN_LIMITE_AMBIGUO,
    JOIN_SIN_COORDENADAS,
    asignar_comuna,
    cargar_comunas,
    puntos_desde_coordenadas,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAESTRO_PATH: Final[Path] = Path("data/processed/establecimientos_rm_clean.parquet")
OFERTA_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
OUTPUT_PATH: Final[Path] = Path("data/processed/geo/establecimientos_coordenadas_resolucion.csv")

RES_REQUIERE_GEOCODIFICACION: Final[str] = "requiere_geocodificacion"
RES_EXCLUIR_NO_VIGENTE: Final[str] = "excluir_no_vigente"
RES_EXCLUIR_FUERA_OFERTA: Final[str] = "excluir_fuera_de_oferta"
RESOLUCIONES: Final[frozenset[str]] = frozenset({
    RES_REQUIERE_GEOCODIFICACION, RES_EXCLUIR_NO_VIGENTE, RES_EXCLUIR_FUERA_OFERTA,
})
PROBLEMAS: Final[frozenset[str]] = frozenset({
    JOIN_SIN_COORDENADAS, JOIN_FUERA_RM, JOIN_DIFIERE, JOIN_LIMITE_AMBIGUO,
})

COLUMNAS: Final[list[str]] = [
    "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_glosa",
    "comuna_codigo", "comuna_glosa", "estado_funcionamiento", "fecha_cierre",
    "latitud", "longitud", "comuna_codigo_espacial", "en_oferta_urgencia",
    "problema_coordenadas", "resolucion", "justificacion",
]

_DESCRIPCION_PROBLEMA: Final[dict[str, str]] = {
    JOIN_SIN_COORDENADAS: "no tiene coordenadas publicadas",
    JOIN_FUERA_RM: "tiene una coordenada fuera de la Región Metropolitana (posible error en la fuente)",
    JOIN_DIFIERE: "tiene una coordenada en una comuna distinta de la declarada (no se puede determinar cuál de las dos es errónea)",
    JOIN_LIMITE_AMBIGUO: "tiene una coordenada sobre un límite compartido entre comunas",
}


def _justificar(fila: pd.Series) -> str:
    problema = _DESCRIPCION_PROBLEMA[fila["problema_coordenadas"]]
    if fila["resolucion"] == RES_REQUIERE_GEOCODIFICACION:
        return (
            f"Integra la oferta de urgencia y {problema}: debe geocodificarse desde una fuente "
            "verificable antes de calcular accesibilidad. No se imputa."
        )
    if fila["resolucion"] == RES_EXCLUIR_NO_VIGENTE:
        return (
            f"No vigente y {problema}: no forma parte de la oferta actual, por lo que no se "
            "geocodifica ni se imputa."
        )
    return (
        f"Vigente, fuera de la oferta de urgencia, y {problema}: su coordenada no se usa en las "
        "capas de accesibilidad; no se corrige ni se reemplaza por el centroide comunal."
    )


def resolver_coordenadas(
    maestro: pd.DataFrame, codigos_oferta: set[int], comunas: pd.DataFrame
) -> pd.DataFrame:
    """Una fila por establecimiento con problema de coordenadas y su resolución justificada."""
    maestro = maestro.reset_index(drop=True)
    puntos = puntos_desde_coordenadas(maestro["latitud"], maestro["longitud"])
    join = asignar_comuna(puntos, maestro["comuna_codigo"], comunas)

    marco = maestro.assign(
        establecimiento_codigo=maestro["establecimiento_codigo"].astype("int64"),
        estado_funcionamiento=maestro["estado_funcionamiento"].str.strip().str.lower(),
        comuna_codigo_espacial=join["comuna_codigo_espacial"],
        problema_coordenadas=join["resultado_join_comuna"],
    )
    marco["en_oferta_urgencia"] = marco["establecimiento_codigo"].isin(codigos_oferta)
    marco = marco[marco["problema_coordenadas"] != JOIN_COINCIDE].copy()

    vigente = marco["estado_funcionamiento"] == ESTADO_VIGENTE
    marco["resolucion"] = RES_EXCLUIR_FUERA_OFERTA
    marco.loc[~vigente, "resolucion"] = RES_EXCLUIR_NO_VIGENTE
    marco.loc[marco["en_oferta_urgencia"], "resolucion"] = RES_REQUIERE_GEOCODIFICACION
    marco["justificacion"] = marco.apply(_justificar, axis=1) if len(marco) else pd.Series(dtype="object")

    resultado = marco[COLUMNAS].sort_values("establecimiento_codigo").reset_index(drop=True)
    validar_resolucion(resultado, maestro, codigos_oferta)
    return resultado


def validar_resolucion(resultado: pd.DataFrame, maestro: pd.DataFrame, codigos_oferta: set[int]) -> None:
    """Grano, dominios, cobertura de todos los faltantes y consistencia con la oferta."""
    if resultado["establecimiento_codigo"].duplicated().any():
        raise ValueError("establecimiento_codigo duplicado en la lista de resolución.")
    if not set(resultado["problema_coordenadas"]) <= PROBLEMAS:
        raise ValueError("problema_coordenadas fuera de dominio.")
    if not set(resultado["resolucion"]) <= RESOLUCIONES:
        raise ValueError("resolucion fuera de dominio.")
    if resultado["justificacion"].isna().any() or (resultado["justificacion"].str.strip() == "").any():
        raise ValueError("Toda fila debe llevar una justificación.")

    sin_coordenadas = int(maestro["latitud"].isna().sum())
    cubiertos = int((resultado["problema_coordenadas"] == JOIN_SIN_COORDENADAS).sum())
    if sin_coordenadas != cubiertos:
        raise ValueError(
            f"La lista cubre {cubiertos} establecimientos sin coordenadas; el maestro tiene {sin_coordenadas}."
        )
    en_oferta = resultado["en_oferta_urgencia"]
    if (en_oferta != (resultado["resolucion"] == RES_REQUIERE_GEOCODIFICACION)).any():
        raise ValueError("Un establecimiento de la oferta debe resolverse como requiere_geocodificacion, y solo ellos.")
    if not set(resultado.loc[en_oferta, "establecimiento_codigo"]) <= codigos_oferta:
        raise ValueError("en_oferta_urgencia inconsistente con dim_oferta_urgencia_rm.")


def build_resolucion_coordenadas(
    maestro_path: Path = MAESTRO_PATH, oferta_path: Path = OFERTA_PATH, comunas_path: Path = COMUNAS_PATH
) -> pd.DataFrame:
    for ruta in (maestro_path, oferta_path):
        if not ruta.is_file():
            raise FileNotFoundError(f"No existe el insumo requerido: {ruta.as_posix()}")
    columnas = [
        "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_glosa",
        "comuna_codigo", "comuna_glosa", "estado_funcionamiento", "fecha_cierre", "latitud", "longitud",
    ]
    maestro = pq.read_table(maestro_path, columns=columnas).to_pandas()
    codigos_oferta = set(pq.read_table(oferta_path, columns=["establecimiento_codigo"])
                         .column(0).to_pylist())
    return resolver_coordenadas(maestro, codigos_oferta, cargar_comunas(comunas_path))


def _atomic_write(frame: pd.DataFrame, output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=output_path.parent, prefix=f"{output_path.name}.", suffix=".tmp"
    ) as temp:
        temp_path = Path(temp.name)
    try:
        frame.to_csv(temp_path, index=False, encoding="utf-8")
        temp_path.replace(output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publica la lista final de resolución de coordenadas de establecimientos RM."
    )
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()

    resultado = build_resolucion_coordenadas()
    _atomic_write(resultado)
    logger.info(
        "Lista de resolución de coordenadas: %s filas -> %s. Por resolución: %s. Por problema: %s.",
        len(resultado), OUTPUT_PATH.as_posix(),
        resultado["resolucion"].value_counts().to_dict(),
        resultado["problema_coordenadas"].value_counts().to_dict(),
    )
    pendientes = int((resultado["resolucion"] == RES_REQUIERE_GEOCODIFICACION).sum())
    if pendientes:
        logger.warning("%s establecimiento(s) de la oferta de urgencia requieren geocodificación.", pendientes)


if __name__ == "__main__":
    main()
