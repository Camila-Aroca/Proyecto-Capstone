"""Ocupación mensual de las camas de psiquiatría de los hospitales de la oferta RM.

Une, por `establecimiento_codigo`, los hospitales de `dim_oferta_urgencia_rm` con el
detalle de los indicadores hospitalarios REM-20 (`indicadores_hospitalarios_snss`)
de sus áreas de psiquiatría, y publica **una fila por área de psiquiatría de un
hospital y mes publicado**. El grano es el área, no el hospital, porque un área
puede estar saturada aunque el total del hospital no lo esté; el total del hospital
se obtiene sumando sus áreas (`por_hospital`).

**Qué es un área de psiquiatría:** el mismo criterio que
`dim_camas_psiquiatria_hospital_rm`: nivel de cuidado cuyo nombre contiene
"Psiquiatr" (adulto, infanto-adolescente, forense y cuidados intensivos). El área
sociosanitaria (427) no lo es.

**Cálculo (identidades exactas, sin estimación):**

- Los días cama ocupados de un mes son, por definición del diccionario REM-20, la
  suma diaria de las camas con paciente: ``O = Σ_d o_d``. Por eso
  ``camas_ocupadas_promedio = O / D`` (``D`` = días del mes) es exactamente el
  número medio de camas con paciente por día, es decir, el promedio diario de
  pacientes hospitalizados en esas áreas.
- Igual con los disponibles: ``camas_disponibles_promedio = Σ disponibles / D``. Es
  la misma operación con que el origen publica el "Promedio Cama Disponibles"
  mensual de cada área; la etapa **verifica** que la suma de esos promedios
  publicados reproduzca el valor calculado dentro del redondeo de la fuente (2
  decimales por área) y falla si no, porque la identidad que sustenta el cálculo
  dejaría de valer.
- ``camas_libres_promedio = (disponibles − ocupados) / D``: camas libres por día en
  promedio, es decir, la brecha de capacidad. Negativa = el área registró más días
  cama ocupados que disponibles (ocupación sobre la capacidad).
- ``indice_ocupacional = 100 · ocupados / disponibles``. Al agregar áreas se usa la
  razón de sumas, no el promedio de índices (promediar índices de áreas de distinto
  tamaño sesga hacia las áreas chicas). Nulo si no hubo días cama disponibles.

**Lectura de la saturación.** Los días cama ocupados cuentan pacientes en camas de
las áreas de hospitalización. Un paciente que espera en la urgencia en camilla,
silla o sillón no ocupa una de esas camas y no se registra aquí: la ocupación
observada es un piso de la demanda de camas, no su techo (inferencia de la
definición del indicador; la fuente no cuantifica esa espera).

Solo meses publicados: un mes aún no publicado del año en curso no genera fila (no
es cero). Un hospital sin áreas de psiquiatría en el REM-20 no tiene filas.

Qué **no** es: no mide la espera en la urgencia ni pacientes en camillas fuera de
las áreas de hospitalización, y no es ocupación en tiempo real (último mes
publicado por el DEIS). Los pacientes en cama no provienen solo de la urgencia: no
es comparable uno a uno con el ID42 de Urgencias.
"""

from __future__ import annotations

import argparse
import calendar
import logging
import os
from pathlib import Path
import tempfile
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data import clean_estadisticas_hospitalarias as rem20

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# "Sin holgura": menos de una cama libre por día, en promedio del mes. Es un umbral en
# camas (interpretable en áreas chicas y grandes), no en porcentaje.
UMBRAL_HOLGURA_CAMAS: Final[float] = 1.0

# Nivel de colapso de un hospital (ocupación de sus camas de psiquiatría en la ventana,
# como razón de sumas). Umbrales de la literatura, no del dato:
# - 85 %: ocupación máxima recomendada para salas de psiquiatría (Royal College of
#   Psychiatrists); sobre ella los riesgos son discernibles (Bagust, Place y Posnett,
#   BMJ 1999;319:155-8).
# - 90 %: desde esa ocupación media se esperan escasez regular de camas y crisis
#   periódicas (Bagust et al. 1999; simulación de un hospital de agudos sin pacientes
#   psiquiátricos: se usa como referencia, no como calibración local).
VENTANA_COLAPSO_MESES: Final[int] = 12
UMBRAL_PRESION_PCT: Final[float] = 85.0
UMBRAL_SATURACION_PCT: Final[float] = 90.0
NIVELES_COLAPSO: Final[tuple[str, ...]] = ("holgura", "presion", "saturacion", "sobre_capacidad")
DIM_OFERTA_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
INDICADORES_PATH: Final[Path] = rem20.OUTPUT_DIR / rem20.INDICADORES_FILENAME
OUTPUT_PATH: Final[Path] = Path("data/processed/marts/mart_ocupacion_psiquiatria_hospital_rm.parquet")

TIPO_HOSPITAL: Final[str] = "Hospital"
AREA_PSIQUIATRIA: Final[str] = "Psiquiatr"  # mismo criterio que dim_camas_psiquiatria_hospital_rm
OCUPADOS: Final[str] = "Dias Cama Ocupados"
DISPONIBLES: Final[str] = "Dias Cama Disponibles"
PROMEDIO_DISPONIBLES: Final[str] = "Promedio Cama Disponibles"
# La fuente publica el promedio mensual de cada área con 2 decimales: la suma de n
# áreas puede alejarse del valor exacto hasta n · 0,005.
REDONDEO_POR_AREA: Final[float] = 0.005

SCHEMA: Final[pa.Schema] = pa.schema([
    ("establecimiento_codigo", pa.int64()),
    ("nivel_cuidado_codigo", pa.int32()),
    ("nivel_cuidado", pa.string()),
    ("ano", pa.int32()),
    ("mes", pa.int32()),
    ("fecha_inicio_mes", pa.date32()),
    ("dias_mes", pa.int32()),
    ("dias_cama_ocupados", pa.float64()),
    ("dias_cama_disponibles", pa.float64()),
    ("camas_ocupadas_promedio", pa.float64()),
    ("camas_disponibles_promedio", pa.float64()),
    ("camas_libres_promedio", pa.float64()),
    ("indice_ocupacional", pa.float64()),
])
KEY: Final[tuple[str, ...]] = ("establecimiento_codigo", "nivel_cuidado_codigo", "ano", "mes")


def areas_psiquiatria_mensual(indicadores: pd.DataFrame) -> pd.DataFrame:
    """Largo por área de psiquiatría y mes: ocupados, disponibles y promedio publicado.

    Descarta solo los meses sin ningún valor (aún no publicados); un mes con valor en
    un indicador y nulo en otro es una inconsistencia del origen y detiene la etapa.
    """
    psiq = indicadores[indicadores["nivel_cuidado"].str.contains(AREA_PSIQUIATRIA, case=False, regex=False)
                       & indicadores["indicador"].isin([OCUPADOS, DISPONIBLES, PROMEDIO_DISPONIBLES])]
    meses = list(rem20.MESES_COLUMNAS)
    largo = psiq.melt(id_vars=["ano", "servicio_salud_codigo", "establecimiento_codigo", "nivel_cuidado_codigo",
                               "indicador"], value_vars=meses, var_name="mes_nombre", value_name="valor")
    largo["mes"] = largo["mes_nombre"].map({m: i for i, m in enumerate(meses, start=1)})
    ancho = largo.pivot_table(index=["ano", "mes", "servicio_salud_codigo", "establecimiento_codigo",
                                     "nivel_cuidado_codigo"], columns="indicador", values="valor",
                              aggfunc="first", dropna=False).reset_index()
    nombres = psiq.drop_duplicates(["ano", "servicio_salud_codigo", "establecimiento_codigo", "nivel_cuidado_codigo"])
    ancho = ancho.merge(nombres[["ano", "servicio_salud_codigo", "establecimiento_codigo", "nivel_cuidado_codigo",
                                 "nivel_cuidado"]], how="left")
    for columna in (OCUPADOS, DISPONIBLES, PROMEDIO_DISPONIBLES):
        if columna not in ancho:
            ancho[columna] = float("nan")
    valores = ancho[[OCUPADOS, DISPONIBLES, PROMEDIO_DISPONIBLES]]
    publicado = valores.notna().any(axis=1)
    incompleto = publicado & valores.isna().any(axis=1)
    if incompleto.any():
        ejemplo = ancho.loc[incompleto].iloc[0].to_dict()
        raise ValueError(f"Área de psiquiatría con un mes publicado a medias en el REM-20: {ejemplo}")
    return ancho.loc[publicado].reset_index(drop=True)


def _derivar(frame: pd.DataFrame) -> pd.DataFrame:
    """Promedios diarios, brecha e índice desde los días cama del mes (identidades exactas)."""
    frame["dias_mes"] = [calendar.monthrange(int(a), int(m))[1] for a, m in zip(frame["ano"], frame["mes"])]
    frame["fecha_inicio_mes"] = pd.to_datetime(dict(year=frame["ano"], month=frame["mes"], day=1)).dt.date
    frame["camas_ocupadas_promedio"] = frame["dias_cama_ocupados"] / frame["dias_mes"]
    frame["camas_disponibles_promedio"] = frame["dias_cama_disponibles"] / frame["dias_mes"]
    frame["camas_libres_promedio"] = frame["camas_disponibles_promedio"] - frame["camas_ocupadas_promedio"]
    frame["indice_ocupacional"] = (100 * frame["dias_cama_ocupados"]
                                   / frame["dias_cama_disponibles"].where(frame["dias_cama_disponibles"] > 0))
    return frame


def build(oferta: pd.DataFrame, indicadores: pd.DataFrame) -> pd.DataFrame:
    """Una fila por área de psiquiatría de un hospital de la oferta y mes publicado."""
    hospitales = oferta.loc[oferta["tipo_establecimiento"] == TIPO_HOSPITAL, "establecimiento_codigo"]
    areas = areas_psiquiatria_mensual(indicadores)
    areas = areas[areas["establecimiento_codigo"].isin(set(hospitales.astype("int64")))]
    # Un área bajo dos Servicios de Salud el mismo mes se suma (no ocurre en el snapshot vigente).
    mart = areas.groupby(["establecimiento_codigo", "nivel_cuidado_codigo", "ano", "mes"], as_index=False).agg(
        nivel_cuidado=("nivel_cuidado", "first"),
        dias_cama_ocupados=(OCUPADOS, "sum"),
        dias_cama_disponibles=(DISPONIBLES, "sum"),
        promedio_publicado=(PROMEDIO_DISPONIBLES, "sum"),
        filas_origen=(OCUPADOS, "size"),
    )
    mart = _derivar(mart)
    verificar_identidad(mart)
    return mart[[f.name for f in SCHEMA]].sort_values(list(KEY)).reset_index(drop=True)


def por_hospital(mart: pd.DataFrame) -> pd.DataFrame:
    """Total de psiquiatría del hospital por mes: suma de días cama de sus áreas, no de índices."""
    total = mart.groupby(["establecimiento_codigo", "ano", "mes"], as_index=False).agg(
        dias_cama_ocupados=("dias_cama_ocupados", "sum"),
        dias_cama_disponibles=("dias_cama_disponibles", "sum"),
        n_areas_psiquiatria=("nivel_cuidado_codigo", "nunique"),
    )
    return _derivar(total).sort_values(["establecimiento_codigo", "ano", "mes"]).reset_index(drop=True)


def resumen_areas(areas: pd.DataFrame) -> pd.DataFrame:
    """Saturación de cada área en las filas dadas (ya recortadas a un período).

    Solo cuentan los meses **con camas disponibles**: un área con 0 días cama
    disponibles en un mes no estuvo habilitada (cerrada o sin camas), no saturada, y
    sus 0 camas libres no son falta de holgura. Sobre esos meses: meses sin holgura
    (< UMBRAL_HOLGURA_CAMAS camas libres por día en promedio), meses sobre la capacidad
    (camas libres < 0) e índice del período como razón de sumas. Los valores
    `ultimo_*` son los del último mes publicado, habilitado o no.
    """
    ordenadas = areas.sort_values(["ano", "mes"])
    habilitada = ordenadas["dias_cama_disponibles"] > 0
    ordenadas = ordenadas.assign(
        _con_camas=habilitada,
        _sin_holgura=habilitada & (ordenadas["camas_libres_promedio"] < UMBRAL_HOLGURA_CAMAS),
        _sobre=habilitada & (ordenadas["camas_libres_promedio"] < 0),
        _disponibles=ordenadas["camas_disponibles_promedio"].where(habilitada),
        _libres=ordenadas["camas_libres_promedio"].where(habilitada),
    )
    return ordenadas.groupby(["establecimiento_codigo", "nivel_cuidado_codigo"], as_index=False).agg(
        nivel_cuidado=("nivel_cuidado", "last"),
        meses=("_con_camas", "sum"),
        meses_sin_holgura=("_sin_holgura", "sum"),
        meses_sobre_capacidad=("_sobre", "sum"),
        camas_disponibles_promedio=("_disponibles", "mean"),
        camas_libres_promedio=("_libres", "mean"),
        dias_cama_ocupados=("dias_cama_ocupados", "sum"),
        dias_cama_disponibles=("dias_cama_disponibles", "sum"),
        ultimo_camas_ocupadas_promedio=("camas_ocupadas_promedio", "last"),
        ultimo_camas_disponibles_promedio=("camas_disponibles_promedio", "last"),
        ultimo_camas_libres_promedio=("camas_libres_promedio", "last"),
    ).assign(indice_ocupacional=lambda d: 100 * d.dias_cama_ocupados
             / d.dias_cama_disponibles.where(d.dias_cama_disponibles > 0))


def clasificar_colapso(indice_pct: float | None, meses_sobre_capacidad: int) -> str | None:
    """Nivel según la ocupación de la ventana; "sobre_capacidad" si algún área superó sus camas."""
    if meses_sobre_capacidad > 0:
        return "sobre_capacidad"
    if indice_pct is None or pd.isna(indice_pct):
        return None
    if indice_pct >= UMBRAL_SATURACION_PCT:
        return "saturacion"
    if indice_pct >= UMBRAL_PRESION_PCT:
        return "presion"
    return "holgura"


def nivel_colapso(mart: pd.DataFrame, meses: int = VENTANA_COLAPSO_MESES) -> pd.DataFrame:
    """Nivel de colapso por hospital en los últimos `meses` publicados del mart.

    La ventana es la misma para todos los hospitales (los últimos meses publicados
    del REM-20), para que los niveles sean comparables. Sobre los área-mes con camas
    disponibles: índice = 100 · Σ ocupados / Σ disponibles (razón de sumas) y
    cantidad de área-mes sobre la capacidad (ocupados > disponibles).
    """
    indice = mart["ano"] * 12 + mart["mes"]
    ventana = mart[indice > indice.max() - meses]
    habilitada = ventana[ventana["dias_cama_disponibles"] > 0]
    ultimo = indice.max()
    resumen = habilitada.groupby("establecimiento_codigo").agg(
        dias_cama_ocupados=("dias_cama_ocupados", "sum"),
        dias_cama_disponibles=("dias_cama_disponibles", "sum"),
        meses=("fecha_inicio_mes", "nunique"),
        area_mes_sobre_capacidad=("camas_libres_promedio", lambda x: int((x < 0).sum())),
    ).reset_index()
    resumen["indice_ocupacional"] = 100 * resumen["dias_cama_ocupados"] / resumen["dias_cama_disponibles"]
    resumen["nivel"] = [clasificar_colapso(i, n) for i, n in
                        zip(resumen["indice_ocupacional"], resumen["area_mes_sobre_capacidad"])]
    resumen["desde"] = pd.Timestamp(year=int((ultimo - meses) // 12), month=int((ultimo - meses) % 12) + 1, day=1).date()
    resumen["hasta"] = pd.Timestamp(year=int((ultimo - 1) // 12), month=int((ultimo - 1) % 12) + 1, day=1).date()
    return resumen


def motivo_sin_dotacion(declarada: pd.Series | None, ano_libro: int | None, primer_ano: int | None) -> str | None:
    """Causa observada de que un área no tenga dotación declarada; null si la tiene.

    Distingue lo que el dato permite afirmar: el libro lista el área sin cifra; el
    área aparece en el REM-20 después del último año del libro; o el área no figura
    en el libro, sin causa determinable.
    """
    if ano_libro is None:
        return None
    if declarada is not None:
        return None if not pd.isna(declarada["camas"]) else f"El libro de dotación {ano_libro} lista el área sin cifra."
    if primer_ano is not None and primer_ano > ano_libro:
        return (f"El área se habilitó en {primer_ano}, después del último año del libro de dotación "
                f"({ano_libro}): aún no tiene dotación declarada.")
    return f"El área no figura en el libro de dotación {ano_libro}; la causa no es determinable con estos datos."


def verificar_identidad(mart: pd.DataFrame) -> None:
    """El promedio de camas disponibles publicado por la fuente = días disponibles / días del mes."""
    tolerancia = REDONDEO_POR_AREA * mart["filas_origen"] + 1e-9
    diferencia = (mart["camas_disponibles_promedio"] - mart["promedio_publicado"]).abs()
    fallan = mart[diferencia > tolerancia]
    if not fallan.empty:
        raise ValueError(
            f"{len(fallan)} área-mes no cumplen promedio publicado = días disponibles / días del mes "
            f"(p. ej. {fallan.iloc[0][['establecimiento_codigo', 'ano', 'mes']].to_dict()}); el cálculo de camas "
            "promedio dejaría de estar respaldado por la fuente.")


def validate_mart(mart: pd.DataFrame) -> None:
    if mart.duplicated(list(KEY)).any():
        raise ValueError("Mart de ocupación: llave establecimiento-área-año-mes duplicada.")
    if mart[["dias_cama_ocupados", "dias_cama_disponibles", "dias_mes"]].isna().any().any():
        raise ValueError("Mart de ocupación: conteos nulos en un mes publicado.")
    if (mart[["dias_cama_ocupados", "dias_cama_disponibles"]] < 0).any().any():
        raise ValueError("Mart de ocupación: días cama negativos.")
    if not mart["mes"].between(1, 12).all():
        raise ValueError("Mart de ocupación: mes fuera de 1-12.")


def build_mart_ocupacion_psiquiatria_hospital_rm(
    oferta_path: Path = DIM_OFERTA_PATH, indicadores_path: Path = INDICADORES_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, object]:
    for path in (oferta_path, indicadores_path):
        if not path.is_file():
            raise FileNotFoundError(f"No existe el input requerido: {path.as_posix()}")
    oferta = pq.read_table(oferta_path, columns=["establecimiento_codigo", "tipo_establecimiento"]).to_pandas()
    indicadores = pq.read_table(indicadores_path, columns=[
        "ano", "servicio_salud_codigo", "establecimiento_codigo", "nivel_cuidado_codigo", "nivel_cuidado",
        "indicador", *rem20.MESES_COLUMNAS]).to_pandas()
    mart = build(oferta, indicadores)
    validate_mart(mart)
    _atomic_write(mart, output_path)
    resumen = {"filas": len(mart), "hospitales": int(mart["establecimiento_codigo"].nunique()),
               "areas": int(mart[["establecimiento_codigo", "nivel_cuidado_codigo"]].drop_duplicates().shape[0]),
               "desde": f"{int(mart['ano'].min())}", "ultimo_mes": f"{int(mart['ano'].max())}-"
               f"{int(mart.loc[mart['ano'] == mart['ano'].max(), 'mes'].max()):02d}"}
    logger.info("Mart de ocupación de psiquiatría generado: %s", resumen)
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
    parser = argparse.ArgumentParser(description="Mart mensual de ocupación de camas de psiquiatría (RM).")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    build_mart_ocupacion_psiquiatria_hospital_rm()


if __name__ == "__main__":
    main()
