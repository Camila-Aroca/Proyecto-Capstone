"""Suicidios semanales de residentes de cada comuna RM (mart `mart_suicidios_comuna_weekly`).

Cuenta, desde `defunciones_nacional.parquet`, las defunciones de **residentes de la
RM** cuya causa externa (`DIAG2`) pertenece a las lesiones autoinfligidas
intencionalmente, CIE-10 **X60-X84**, y publica una fila por comuna x semana DEIS.

**Definición del caso.** La categoría de `codigo_categoria_diag2` en X60-X84. La
etapa verifica que coincida exactamente con el grupo publicado por la fuente
(`codigo_grupo_diag2 == "X60-X84"`) y falla si no. Filtrar `DIAG1` en F00-F99 dejaría
fuera estas muertes: `DIAG1` trae la lesión (capítulos S/T), no la causa externa.

**Territorio = residencia.** `comuna_codigo` es la comuna de residencia declarada,
no el lugar del suicidio ni de la defunción, ni el establecimiento. Por eso la
relación con Urgencias (comuna del establecimiento) es solo ecológica.

**Calendario DEIS.** Semana epidemiológica (domingo a sábado; la semana 1 es la que
contiene el 4 de enero) y año **calendario** de la fecha, que es exactamente la
codificación publicada por Urgencias: los días de comienzo o fin de año que caen en
la semana de otro año epidemiológico quedan como `semana = 53` o se suman a la
semana 1/52 del año calendario. La regla se verifica contra todas las fechas de
Urgencias en `scripts/eda_mart_suicidios_comuna_weekly.py`. Como algunas semanas
regulares tienen 4, 6, 8 o 9 días, se publica `dias_semana`: el modelo lo usa como
exposición en vez de tratar todas las semanas como de 7 días.

**Ceros reales.** La base de defunciones es un registro censal: una comuna-semana
sin defunciones registradas es cero registrado (no ausencia de reporte, como sí
ocurre en Urgencias). La grilla es completa: las 52 comunas por cada semana.

**Corte y registro incompleto.** Solo se publican semanas cuyos días son todos
anteriores o iguales a la última fecha de defunción del archivo. Las defunciones de
los últimos días tardan en inscribirse: `registro_completo` es False para las
semanas finales cuyas defunciones por todas las causas de la RM, por día, caen bajo
`UMBRAL_REGISTRO` veces la mediana de las `SEMANAS_REFERENCIA` semanas previas.
También alerta si el último día cae bajo la mitad de la mediana de los ocho
días equivalentes anteriores. Se marca, no se corrige ni se imputa; superar las
alertas no demuestra completitud y el modelo usa solo semanas no marcadas.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import logging
import os
from pathlib import Path
import tempfile
from typing import Final

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.data.clean_poblacion_proyecciones import load_rm_population

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFUNCIONES_PATH: Final[Path] = Path("data/processed/defunciones/defunciones_nacional.parquet")
COMUNAS_PATH: Final[Path] = Path("data/processed/censo/dim_poblacion_comuna_censo2024.parquet")
OUTPUT_PATH: Final[Path] = Path("data/processed/marts/mart_suicidios_comuna_weekly.parquet")

GRUPO_SUICIDIO: Final[str] = "X60-X84"
# Categorías CIE-10 X60 a X84, ambas incluidas.
PATRON_SUICIDIO: Final[str] = r"^X(6\d|7\d|8[0-4])$"
PREFIJO_RM: Final[str] = "13"
SEMANA_FRAGMENTO: Final[int] = 53

# Completitud del registro en las semanas finales. Referencia: mediana de las
# defunciones diarias (todas las causas, RM) de las 8 semanas regulares previas. En
# el snapshot evaluado ninguna semana interior de 2021-2026 bajó de 0,787 (2021-S31,
# descenso tras una ola COVID; 2020 queda fuera por las olas, mínimo 0,599), y la
# última semana publicada está en 0,72: un registro bajo 0,75 no es variación
# observada del período, es inscripción pendiente. Cifras recalculadas en el EDA.
SEMANAS_REFERENCIA: Final[int] = 8
UMBRAL_REGISTRO: Final[float] = 0.75
# Alerta conservadora del último día, contrastado con ocho días equivalentes.
UMBRAL_ULTIMO_DIA: Final[float] = 0.5

KEY: Final[tuple[str, ...]] = ("comuna_codigo", "ano", "semana")
SCHEMA: Final[pa.Schema] = pa.schema([
    ("comuna_codigo", pa.string()),
    ("comuna_glosa", pa.string()),
    ("ano", pa.int16()),
    ("semana", pa.int16()),
    ("fecha_inicio_semana", pa.date32()),
    ("fecha_fin_semana", pa.date32()),
    ("dias_semana", pa.int8()),
    ("suicidios", pa.int32()),
    ("defunciones_total", pa.int32()),
    ("poblacion_anual", pa.int64()),
    ("registro_completo", pa.bool_()),
])


# --------------------------------------------------------------------------
# Calendario DEIS
# --------------------------------------------------------------------------

def _inicio_ano_epidemiologico(ano: int) -> date:
    """Domingo que abre la semana epidemiológica 1: la semana que contiene el 4 de enero."""
    cuatro = date(ano, 1, 4)
    return cuatro - timedelta(days=(cuatro.weekday() + 1) % 7)


def semana_deis(fecha: date) -> tuple[int, int]:
    """(año calendario, semana epidemiológica) con que DEIS codifica una fecha."""
    inicio = _inicio_ano_epidemiologico(fecha.year)
    if fecha < inicio:
        inicio = _inicio_ano_epidemiologico(fecha.year - 1)
    elif fecha >= _inicio_ano_epidemiologico(fecha.year + 1):
        inicio = _inicio_ano_epidemiologico(fecha.year + 1)
    return fecha.year, (fecha - inicio).days // 7 + 1


def calendario_deis(desde: date, hasta: date) -> pd.DataFrame:
    """Una fila por (año, semana) DEIS con su primer y último día y número de días."""
    dias = pd.date_range(desde, hasta, freq="D")
    codigos = [semana_deis(d.date()) for d in dias]
    frame = pd.DataFrame({"fecha": dias.date, "ano": [c[0] for c in codigos], "semana": [c[1] for c in codigos]})
    return (
        frame.groupby(["ano", "semana"], as_index=False)
        .agg(fecha_inicio_semana=("fecha", "min"), fecha_fin_semana=("fecha", "max"), dias_semana=("fecha", "size"))
        .sort_values(["ano", "fecha_inicio_semana"]).reset_index(drop=True)
    )


def dias_semana(ano: int, semana: int) -> int:
    """Días del año calendario `ano` que DEIS codifica como `semana` (pura función del calendario)."""
    return int(calendario_deis(date(ano, 1, 1), date(ano, 12, 31)).set_index(["ano", "semana"])
               .loc[(ano, semana), "dias_semana"])


# --------------------------------------------------------------------------
# Construcción
# --------------------------------------------------------------------------

def load_defunciones_rm(path: Path = DEFUNCIONES_PATH) -> pd.DataFrame:
    """Defunciones de residentes RM con fecha: solo las columnas que usa el mart."""
    dataset = ds.dataset(path)
    filtro = pc.starts_with(pc.field("comuna_codigo"), PREFIJO_RM)
    return dataset.to_table(
        columns=["fecha_defuncion", "comuna_codigo", "codigo_categoria_diag2", "codigo_grupo_diag2"],
        filter=filtro,
    ).to_pandas()


def fecha_corte(path: Path = DEFUNCIONES_PATH) -> date:
    """Última fecha de defunción del archivo nacional: límite de lo observable."""
    maximo = pc.max(ds.dataset(path).to_table(columns=["fecha_defuncion"]).column("fecha_defuncion")).as_py()
    if maximo is None:
        raise ValueError("El archivo de defunciones no trae fechas.")
    return maximo


def es_suicidio(defunciones: pd.DataFrame) -> pd.Series:
    """X60-X84 en la causa externa, verificado contra el grupo publicado por la fuente."""
    por_categoria = defunciones["codigo_categoria_diag2"].fillna("").str.match(PATRON_SUICIDIO)
    por_grupo = defunciones["codigo_grupo_diag2"].fillna("") == GRUPO_SUICIDIO
    if not por_categoria.equals(por_grupo):
        raise ValueError(
            f"La categoría X60-X84 y el grupo publicado '{GRUPO_SUICIDIO}' difieren en "
            f"{int((por_categoria != por_grupo).sum())} registros: revisar la codificación de DIAG2."
        )
    return por_categoria


def marcar_registro(semanal_rm: pd.DataFrame, umbral: float = UMBRAL_REGISTRO,
                    referencia: int = SEMANAS_REFERENCIA) -> pd.Series:
    """`registro_completo` por semana: False solo en las semanas finales con registro rezagado.

    `semanal_rm` trae una fila por (año, semana) regular, en orden cronológico, con
    `defunciones_total` y `dias_semana` de toda la RM. Se recorre desde el final y se
    detiene en la primera semana que alcanza el umbral: una caída interior no es
    rezago de inscripción y no se marca.
    """
    por_dia = (semanal_rm["defunciones_total"] / semanal_rm["dias_semana"]).to_numpy(dtype=float)
    completo = np.ones(len(por_dia), dtype=bool)
    for i in range(len(por_dia) - 1, referencia - 1, -1):
        mediana = float(np.median(por_dia[i - referencia:i]))
        if por_dia[i] >= umbral * mediana:
            break
        completo[i] = False
    return pd.Series(completo, index=semanal_rm.index)


def marcar_registro_diario(semanal_rm: pd.DataFrame, diarios_rm: pd.Series,
                           umbral: float = UMBRAL_ULTIMO_DIA,
                           referencia: int = SEMANAS_REFERENCIA) -> pd.Series:
    """Alerta en semanas finales si su último día cae frente a días equivalentes.

    Es una alerta conservadora, no una prueba de completitud. No evalúa días
    interiores de la semana ni marca cuando faltan ocho semanas de historia.
    """
    completo = pd.Series(True, index=semanal_rm.index)
    if diarios_rm.empty:
        return completo
    inicio = min(diarios_rm.index)
    for i in reversed(semanal_rm.index):
        dia = semanal_rm.loc[i, "fecha_fin_semana"]
        fechas = [dia - timedelta(days=7 * n) for n in range(1, referencia + 1)]
        if min(fechas) < inicio:
            break
        mediana = float(np.median([diarios_rm.get(fecha, 0) for fecha in fechas]))
        if mediana <= 0 or diarios_rm.get(dia, 0) >= umbral * mediana:
            break
        completo.loc[i] = False
    return completo


def build(defunciones: pd.DataFrame, comunas: pd.DataFrame, poblacion: pd.DataFrame,
          desde: date, corte: date) -> pd.DataFrame:
    """Grilla completa comuna x semana DEIS hasta la última semana con todos sus días observados."""
    defunciones = defunciones[defunciones["fecha_defuncion"].notna()]
    defunciones = defunciones[(defunciones["fecha_defuncion"] >= desde) & (defunciones["fecha_defuncion"] <= corte)]
    universo = set(comunas["comuna_codigo"])
    fuera = sorted(set(defunciones["comuna_codigo"]) - universo)
    if fuera:
        raise ValueError(
            f"Residentes RM con comuna fuera de las 52 comunas: {fuera}. Decidir y documentar su "
            "tratamiento antes de publicar (no se descartan en silencio)."
        )
    defunciones = defunciones.assign(suicidio=es_suicidio(defunciones))
    codigos = [semana_deis(f) for f in defunciones["fecha_defuncion"]]
    defunciones = defunciones.assign(ano=[c[0] for c in codigos], semana=[c[1] for c in codigos])
    conteos = defunciones.groupby(["comuna_codigo", "ano", "semana"]).agg(
        suicidios=("suicidio", "sum"), defunciones_total=("suicidio", "size"))

    calendario = calendario_deis(desde, corte)
    # La semana que contiene el corte puede seguir más allá del archivo: si su último
    # día observado no es sábado (ni 31 de diciembre), está truncada y no se publica.
    calendario = calendario[_semana_cerrada(calendario)]

    grilla = comunas[["comuna_codigo", "comuna_glosa"]].merge(calendario, how="cross")
    mart = grilla.merge(conteos, left_on=list(KEY), right_index=True, how="left")
    mart[["suicidios", "defunciones_total"]] = mart[["suicidios", "defunciones_total"]].fillna(0).astype("int64")
    mart = mart.merge(poblacion.rename(columns={"poblacion": "poblacion_anual"}),
                      on=["comuna_codigo", "ano"], how="left", validate="many_to_one")
    if mart["poblacion_anual"].isna().any():
        raise ValueError("Falta la población proyectada INE de alguna comuna-año.")

    regulares = calendario[calendario["semana"] != SEMANA_FRAGMENTO].copy()
    totales = mart.groupby(["ano", "semana"])["defunciones_total"].sum()
    regulares["defunciones_total"] = totales.reindex(
        pd.MultiIndex.from_frame(regulares[["ano", "semana"]])).to_numpy()
    regulares = regulares.reset_index(drop=True)
    diarios = defunciones.groupby("fecha_defuncion").size()
    regulares["registro_completo"] = (marcar_registro(regulares) & marcar_registro_diario(regulares, diarios)).to_numpy()
    mart = mart.merge(regulares[["ano", "semana", "registro_completo"]], on=["ano", "semana"], how="left")
    # Los fragmentos (semana 53) no entran al modelo; se publican como observados.
    mart["registro_completo"] = mart["registro_completo"].fillna(True).astype(bool)
    return mart[[f.name for f in SCHEMA]].sort_values(["comuna_codigo", "ano", "fecha_inicio_semana"]).reset_index(drop=True)


def _semana_cerrada(calendario: pd.DataFrame) -> pd.Series:
    """True si la semana tiene todos sus días: termina en sábado o en el 31 de diciembre."""
    fin = pd.to_datetime(calendario["fecha_fin_semana"])
    return (fin.dt.weekday == 5) | ((fin.dt.month == 12) & (fin.dt.day == 31))


def validate_mart(mart: pd.DataFrame, n_suicidios_fuente: int) -> None:
    """Grano, completitud de la grilla y conciliación exacta con la fuente."""
    if mart.duplicated(list(KEY)).any():
        raise ValueError("Mart de suicidios: llave comuna-año-semana duplicada.")
    semanas = mart.groupby("comuna_codigo").size()
    if semanas.nunique() != 1:
        raise ValueError("Mart de suicidios: la grilla no tiene las mismas semanas en todas las comunas.")
    if (mart[["suicidios", "defunciones_total"]] < 0).any().any() or (mart["suicidios"] > mart["defunciones_total"]).any():
        raise ValueError("Mart de suicidios: conteos negativos o suicidios mayores que las defunciones.")
    if int(mart["suicidios"].sum()) != n_suicidios_fuente:
        raise ValueError(
            f"Mart de suicidios no concilia con la fuente: {int(mart['suicidios'].sum())} frente a "
            f"{n_suicidios_fuente} defunciones X60-X84 de residentes RM en el período publicado."
        )
    if not mart["dias_semana"].between(1, 10).all():
        raise ValueError("Mart de suicidios: semana con días fuera de 1-10.")


def build_mart_suicidios_comuna_weekly(
    defunciones_path: Path = DEFUNCIONES_PATH, comunas_path: Path = COMUNAS_PATH,
    output_path: Path = OUTPUT_PATH, desde: date | None = None,
) -> dict[str, object]:
    for path in (defunciones_path, comunas_path):
        if not path.is_file():
            raise FileNotFoundError(f"No existe el input requerido: {path.as_posix()}")
    defunciones = load_defunciones_rm(defunciones_path)
    corte = fecha_corte(defunciones_path)
    inicio = desde or min(d for d in defunciones["fecha_defuncion"] if d is not None).replace(month=1, day=1)
    comunas = pq.read_table(comunas_path, columns=["comuna_codigo", "comuna_glosa"]).to_pandas()
    poblacion = load_rm_population(years=tuple(range(inicio.year, corte.year + 1)))
    mart = build(defunciones, comunas, poblacion, inicio, corte)

    publicado_hasta = max(mart["fecha_fin_semana"])
    en_periodo = defunciones[defunciones["fecha_defuncion"].notna()
                             & (defunciones["fecha_defuncion"] >= inicio)
                             & (defunciones["fecha_defuncion"] <= publicado_hasta)]
    validate_mart(mart, int(es_suicidio(en_periodo).sum()))
    _atomic_write(mart, output_path)
    incompletas = mart.loc[~mart["registro_completo"], ["ano", "semana"]].drop_duplicates()
    resumen = {
        "filas": len(mart), "comunas": int(mart["comuna_codigo"].nunique()),
        "suicidios": int(mart["suicidios"].sum()), "desde": str(inicio), "fecha_corte": str(corte),
        "ultima_semana_publicada": str(publicado_hasta),
        "semanas_registro_incompleto": [f"{a}-S{s:02d}" for a, s in incompletas.itertuples(index=False)],
    }
    logger.info("Mart de suicidios generado: %s", resumen)
    return resumen


def _atomic_write(mart: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(mart, schema=SCHEMA, preserve_index=False)
    with tempfile.NamedTemporaryFile(delete=False, dir=output_path.parent, prefix=f".{output_path.name}.",
                                     suffix=".tmp") as temp:
        temporary = Path(temp.name)
    try:
        pq.write_table(table, temporary, compression="zstd")
        if pq.read_metadata(temporary).num_rows != len(mart):
            raise ValueError("La relectura del mart no coincide en filas.")
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mart semanal de suicidios por comuna de residencia (RM).")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    build_mart_suicidios_comuna_weekly()


if __name__ == "__main__":
    main()
