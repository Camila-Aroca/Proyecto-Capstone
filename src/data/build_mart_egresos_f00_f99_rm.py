"""Perfil anual de las hospitalizaciones por salud mental de los residentes de la RM.

Lee `egresos_f00_f99_nacional_2020_2025` (egresos con diagnóstico principal
F00-F99) y publica dos tablas, por **comuna de residencia** del paciente y para
la región completa:

- `mart_egresos_f00_f99_rm_anual.parquet` (grano territorio × año): egresos,
  tasa por 10.000 habitantes, días de estada (mediana y p90), proporción en
  hospitales del SNSS y de estadías de más de un año.
- `mart_egresos_f00_f99_rm_desglose.parquet` (grano territorio × año ×
  dimensión × categoría): egresos por sexo, grupo de edad, grupo diagnóstico y
  previsión, con las columnas armonizadas entre años.

Complementa a Urgencias, no la reemplaza: Urgencias cuenta dónde se atendió la
persona (el establecimiento) y Egresos dónde vive. Egresos no identifica el
hospital ni a la persona: un egreso es un evento (una persona puede egresar
varias veces) y no se enlaza con Urgencias por registro.

La población es la proyección INE por comuna y año, que cubre 2021 en
adelante: los egresos de 2020 se publican, pero su tasa queda nula (sin
denominador, no cero). Una comuna sin egresos en un año tiene 0 egresos (el
registro es exhaustivo) y estadía nula.
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

from src.data.build_egresos_f00_f99 import GRUPOS_EDAD_ARMONIZADOS
from src.data.build_egresos_f00_f99 import OUTPUT_PATH as EGRESOS_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

POBLACION_PATH: Final[Path] = Path("data/processed/censo/dim_poblacion_comuna_anual.parquet")
ANUAL_PATH: Final[Path] = Path("data/processed/marts/mart_egresos_f00_f99_rm_anual.parquet")
DESGLOSE_PATH: Final[Path] = Path("data/processed/marts/mart_egresos_f00_f99_rm_desglose.parquet")
REGION_ID: Final[str] = "RM"
N_COMUNAS_RM: Final[int] = 52
SNSS: Final[str] = "Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS"

# Bloques del capítulo V de la CIE-10, con nombres de lectura directa.
GRUPOS_DIAGNOSTICO: Final[tuple[tuple[int, int, str], ...]] = (
    (0, 9, "Orgánicos, incluidas demencias y delirium (F00-F09)"),
    (10, 19, "Consumo de sustancias (F10-F19)"),
    (20, 29, "Esquizofrenia y otras psicosis (F20-F29)"),
    (30, 39, "Trastornos del ánimo (F30-F39)"),
    (40, 48, "Ansiedad y estrés (F40-F48)"),
    (50, 59, "Alimentación, sueño y otros fisiológicos (F50-F59)"),
    (60, 69, "Personalidad y comportamiento (F60-F69)"),
    (70, 79, "Discapacidad intelectual (F70-F79)"),
    (80, 89, "Trastornos del desarrollo (F80-F89)"),
    (90, 98, "Inicio en la infancia y adolescencia (F90-F98)"),
    (99, 99, "No especificado (F99)"),
)
SEXOS: Final[tuple[str, ...]] = ("Mujer", "Hombre", "Intersex o indeterminado", "Sin dato")
PREVISIONES: Final[dict[str, str]] = {
    "FONASA": "FONASA", "ISAPRE": "ISAPRE", "CAPREDENA": "Fuerzas Armadas y de Orden",
    "DIPRECA": "Fuerzas Armadas y de Orden", "SISA": "Fuerzas Armadas y de Orden",
    "NINGUNA": "Ninguna", "DESCONOCIDO": "Sin dato", "*": "Sin dato",
}
ORDEN_PREVISION: Final[tuple[str, ...]] = ("FONASA", "ISAPRE", "Fuerzas Armadas y de Orden", "Ninguna", "Sin dato")

SCHEMA_ANUAL: Final[pa.Schema] = pa.schema([
    ("series_id", pa.string()),
    ("nivel", pa.string()),
    ("nombre", pa.string()),
    ("ano", pa.int32()),
    ("egresos", pa.int64()),
    ("poblacion", pa.int64()),
    ("tasa_por_10000", pa.float64()),
    ("dias_estada_mediana", pa.float64()),
    ("dias_estada_p90", pa.float64()),
    ("proporcion_snss", pa.float64()),
    ("proporcion_estadia_mayor_a_un_ano", pa.float64()),
])
SCHEMA_DESGLOSE: Final[pa.Schema] = pa.schema([
    ("series_id", pa.string()),
    ("ano", pa.int32()),
    ("dimension", pa.string()),
    ("categoria", pa.string()),
    ("orden", pa.int32()),
    ("egresos", pa.int64()),
])


def grupo_diagnostico(diag1: pd.Series) -> pd.Series:
    """Bloque CIE-10 del diagnóstico principal (`F329` -> trastornos del ánimo)."""
    numero = diag1.str[1:3].astype(int)
    grupos = pd.Series(pd.NA, index=diag1.index, dtype="object")
    for desde, hasta, nombre in GRUPOS_DIAGNOSTICO:
        grupos[(numero >= desde) & (numero <= hasta)] = nombre
    if grupos.isna().any():
        raise ValueError(f"Diagnósticos fuera de los bloques F00-F99: {sorted(diag1[grupos.isna()].unique())[:5]}")
    return grupos


def cargar_residentes_rm(path: Path = EGRESOS_PATH) -> pd.DataFrame:
    """Egresos de residentes de la RM con las columnas que usa el perfil."""
    columnas = ["ano_egreso", "comuna_residencia", "residente_rm", "pertenencia_establecimiento_salud",
                "glosa_prevision", "diag1", "dias_estada", "sexo_armonizado", "grupo_edad_armonizado",
                "estadia_mayor_a_un_ano"]
    egresos = pq.read_table(path, columns=columnas).to_pandas()
    rm = egresos[egresos["residente_rm"].fillna(False).astype(bool)].copy()
    if rm["comuna_residencia"].isna().any():
        raise ValueError("Egresos de residentes RM sin comuna de residencia.")
    rm["comuna_codigo"] = rm["comuna_residencia"].astype(int).astype(str).str.zfill(5)
    rm["grupo_diagnostico"] = grupo_diagnostico(rm["diag1"])
    sin_regla = set(rm["glosa_prevision"]) - set(PREVISIONES)
    if sin_regla:
        raise ValueError(f"Previsiones sin regla de agrupación: {sorted(sin_regla)}")
    rm["prevision"] = rm["glosa_prevision"].map(PREVISIONES)
    return rm.rename(columns={"ano_egreso": "ano"})


def _metricas(grupo: pd.DataFrame) -> pd.Series:
    dias = grupo["dias_estada"].to_numpy(dtype=float)
    return pd.Series({
        "egresos": len(grupo),
        "dias_estada_mediana": float(np.median(dias)) if len(dias) else np.nan,
        "dias_estada_p90": float(np.quantile(dias, 0.9)) if len(dias) else np.nan,
        "proporcion_snss": float((grupo["pertenencia_establecimiento_salud"] == SNSS).mean()) if len(grupo) else np.nan,
        "proporcion_estadia_mayor_a_un_ano": float(grupo["estadia_mayor_a_un_ano"].mean()) if len(grupo) else np.nan,
    })


def build_anual(rm: pd.DataFrame, poblacion: pd.DataFrame) -> pd.DataFrame:
    """Una fila por territorio (región y 52 comunas) y año, con cero egresos explícitos."""
    comunas = poblacion[["comuna_codigo", "comuna_glosa"]].drop_duplicates("comuna_codigo")
    if len(comunas) != N_COMUNAS_RM:
        raise ValueError(f"Se esperaban {N_COMUNAS_RM} comunas en la población; hay {len(comunas)}.")
    desconocidas = sorted(set(rm["comuna_codigo"]) - set(comunas["comuna_codigo"]))
    if desconocidas:
        raise ValueError(f"Comunas de residencia fuera de las 52 de la RM: {desconocidas}")
    anos = sorted(rm["ano"].unique())
    grilla = pd.MultiIndex.from_product([comunas["comuna_codigo"], anos], names=["comuna_codigo", "ano"])

    por_comuna = (
        rm.groupby(["comuna_codigo", "ano"]).apply(_metricas, include_groups=False)
        .reindex(grilla).reset_index()
    )
    por_comuna["egresos"] = por_comuna["egresos"].fillna(0)
    por_comuna = por_comuna.merge(comunas, on="comuna_codigo").rename(
        columns={"comuna_codigo": "series_id", "comuna_glosa": "nombre"}
    ).assign(nivel="comuna")

    region = rm.groupby("ano").apply(_metricas, include_groups=False).reset_index()
    region = region.assign(series_id=REGION_ID, nombre="Región Metropolitana", nivel="region")

    anual = pd.concat([region, por_comuna], ignore_index=True)
    pob = poblacion[["comuna_codigo", "ano", "poblacion"]]
    pob_region = pob.groupby("ano", as_index=False)["poblacion"].sum().assign(comuna_codigo=REGION_ID)
    pob = pd.concat([pob, pob_region], ignore_index=True).rename(columns={"comuna_codigo": "series_id"})
    anual = anual.merge(pob, on=["series_id", "ano"], how="left")
    anual["tasa_por_10000"] = anual["egresos"] / anual["poblacion"] * 10_000
    anual["egresos"] = anual["egresos"].astype("int64")
    anual["poblacion"] = anual["poblacion"].astype("Int64")
    anual["ano"] = anual["ano"].astype("int32")
    return anual[SCHEMA_ANUAL.names].sort_values(["nivel", "series_id", "ano"], ascending=[False, True, True]) \
        .reset_index(drop=True)


def build_desglose(rm: pd.DataFrame) -> pd.DataFrame:
    """Egresos por sexo, edad, diagnóstico y previsión, por territorio y año."""
    dimensiones = {
        "sexo": ("sexo_armonizado", SEXOS),
        "grupo_edad": ("grupo_edad_armonizado", GRUPOS_EDAD_ARMONIZADOS),
        "grupo_diagnostico": ("grupo_diagnostico", tuple(g[2] for g in GRUPOS_DIAGNOSTICO)),
        "prevision": ("prevision", ORDEN_PREVISION),
    }
    marcos = []
    territorios = pd.concat([rm.assign(series_id=rm["comuna_codigo"]), rm.assign(series_id=REGION_ID)])
    for dimension, (columna, orden) in dimensiones.items():
        conteo = territorios.groupby(["series_id", "ano", columna]).size().rename("egresos").reset_index()
        fuera = set(conteo[columna]) - set(orden)
        if fuera:
            raise ValueError(f"{dimension}: categorías sin orden declarado: {sorted(fuera)}")
        marcos.append(conteo.rename(columns={columna: "categoria"}).assign(
            dimension=dimension, orden=conteo[columna].map({c: i for i, c in enumerate(orden)}),
        ))
    desglose = pd.concat(marcos, ignore_index=True)
    desglose["ano"] = desglose["ano"].astype("int32")
    desglose["orden"] = desglose["orden"].astype("int32")
    desglose["egresos"] = desglose["egresos"].astype("int64")
    return desglose[SCHEMA_DESGLOSE.names].sort_values(["series_id", "ano", "dimension", "orden"]) \
        .reset_index(drop=True)


def validar(anual: pd.DataFrame, desglose: pd.DataFrame, rm: pd.DataFrame) -> None:
    """Reconciliación: comunas suman la región y cada dimensión suma los egresos."""
    region = anual[anual["nivel"] == "region"].set_index("ano")["egresos"]
    comunas = anual[anual["nivel"] == "comuna"].groupby("ano")["egresos"].sum()
    if not region.equals(comunas):
        raise ValueError("Los egresos de las comunas no suman los de la región.")
    if int(region.sum()) != len(rm):
        raise ValueError("La región no reconcilia con los egresos de residentes RM.")
    por_dimension = desglose.groupby(["series_id", "ano", "dimension"])["egresos"].sum().unstack("dimension")
    totales = anual.set_index(["series_id", "ano"])["egresos"]
    con_egresos = totales[totales > 0]
    if not por_dimension.reindex(con_egresos.index).eq(con_egresos, axis=0).all().all():
        raise ValueError("Algún desglose no suma los egresos de su territorio y año.")
    if (anual["tasa_por_10000"].dropna() < 0).any():
        raise ValueError("Tasas negativas.")


def _escribir(frame: pd.DataFrame, schema: pa.Schema, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tabla = pa.Table.from_pandas(frame, schema=schema, preserve_index=False)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f"{path.name}.", suffix=".tmp") as temp:
        temp_path = Path(temp.name)
    try:
        pq.write_table(tabla, temp_path, compression="snappy")
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def build_mart_egresos_f00_f99_rm(
    egresos_path: Path = EGRESOS_PATH, poblacion_path: Path = POBLACION_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rm = cargar_residentes_rm(egresos_path)
    poblacion = pq.read_table(poblacion_path).to_pandas()
    anual, desglose = build_anual(rm, poblacion), build_desglose(rm)
    validar(anual, desglose, rm)
    return anual, desglose


def main() -> None:
    parser = argparse.ArgumentParser(description="Perfil anual de egresos F00-F99 de residentes RM.")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    anual, desglose = build_mart_egresos_f00_f99_rm()
    _escribir(anual, SCHEMA_ANUAL, ANUAL_PATH)
    _escribir(desglose, SCHEMA_DESGLOSE, DESGLOSE_PATH)
    region = anual[anual["nivel"] == "region"]
    logger.info("Perfil de egresos RM: %s filas anuales, %s de desglose. Egresos por año: %s",
                len(anual), len(desglose), dict(zip(region["ano"], region["egresos"])))


if __name__ == "__main__":
    main()
