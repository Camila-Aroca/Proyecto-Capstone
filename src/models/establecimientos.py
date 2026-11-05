"""Panel de series por establecimiento para el pronóstico de demanda.

Reutiliza todo el motor del modelo comunal (matriz supervisada, modelos,
backtesting, reconciliación e intervalos): lo único propio de este nivel es
**qué series entran** y **cómo se arma el panel** desde
`mart_urgencias_establecimiento_weekly`.

Dos objetivos, con la misma maquinaria:

- `atenciones_sm`: atenciones de urgencia en salud mental (ID36).
- `hospitalizaciones_sm`: hospitalizaciones derivadas desde la urgencia por
  F00-F99 (ID42). Solo las informan los hospitales y usan como señal adicional
  las atenciones de salud mental del mismo establecimiento, siempre rezagadas.

El panel agrega una serie total (`RM_SERIES_ID`) que es la **suma de los
establecimientos del universo**, no el total regional publicado: así la
jerarquía total -> establecimientos es exacta y la reconciliación conserva la
coherencia. Por eso su cifra difiere de la serie regional del modelo comunal.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_comuna_marts import load_urgencias_source
from src.data.build_urgencias_establecimiento_weekly_mart import (
    EXTRA_SOURCE_COLUMNS,
    WEEKLY_CAUSES,
    build_establecimiento_weekly_mart,
)
from src.models.features import RM_SERIES_ID, SEASONAL_PERIOD, _add_time_index
from src.models.holdout import DIAS_SEMANA_COMPLETA, MAX_SHARE_EXCLUIDA_PCT, URGENCIAS_PROCESSED_DIR

MART_PATH: Final[Path] = Path("data/processed/marts/mart_urgencias_establecimiento_weekly.parquet")
NIVEL_ESTABLECIMIENTO: Final[str] = "establecimiento"

# Primer año de la ventana. Dos hechos del EDA del mart lo fijan en 2022:
# el Instituto Horwitz, el establecimiento de mayor volumen, no reporta las
# primeras semanas de 2021, y la razón ID42/ID36 cambia de nivel entre 2021 y
# 2023. Una sola ventana para ambos objetivos mantiene comparables sus informes.
ANO_INICIO: Final[int] = 2022
# Promedio semanal mínimo del objetivo en la ventana. Bajo una atención por
# semana la serie es casi solo ruido y su MASE no es interpretable.
MIN_MEDIA_SEMANAL: Final[float] = 1.0
# Piso del promedio semanal en cada año de la ventana. Detecta series que
# empiezan a registrar a mitad de ventana (años en cero o casi), cuya escala
# MASE, calculada sobre esa historia plana, deja la métrica sin sentido. Es la
# mitad del umbral general para no excluir series que solo tuvieron un año bajo.
MIN_MEDIA_ANUAL: Final[float] = 0.5

ATRIBUTOS: Final[tuple[str, ...]] = (
    "comuna_codigo", "comuna_glosa", "establecimiento_glosa", "tipo_establecimiento_urgencia",
)


@dataclass(frozen=True)
class Objetivo:
    """Qué se pronostica y con qué señales."""

    nombre: str
    target: str
    descripcion: str
    # Covariables del mart que entran rezagadas al menos un horizonte.
    exogenas: tuple[str, ...]
    solo_hospitales: bool = False


OBJETIVOS: Final[dict[str, Objetivo]] = {
    "atenciones_sm": Objetivo(
        nombre="atenciones_sm",
        target="atenciones_id36",
        descripcion="Atenciones de urgencia en salud mental (ID36)",
        exogenas=("atenciones_id1",),
    ),
    "hospitalizaciones_sm": Objetivo(
        nombre="hospitalizaciones_sm",
        target="atenciones_id42",
        descripcion="Hospitalizaciones derivadas desde la urgencia por F00-F99 (ID42)",
        exogenas=("atenciones_id1", "atenciones_id36"),
        solo_hospitales=True,
    ),
}


def load_mart(path: Path = MART_PATH) -> pd.DataFrame:
    """Lee del mart solo las columnas que usan los dos objetivos."""
    columnas = {
        "establecimiento_codigo", "ano", "semana", "fecha_inicio_semana", *ATRIBUTOS,
        *(o.target for o in OBJETIVOS.values()),
        *(c for o in OBJETIVOS.values() for c in o.exogenas),
    }
    return pq.read_table(path, columns=sorted(columnas)).to_pandas()


def _ventana(weekly: pd.DataFrame, ano_inicio: int) -> pd.DataFrame:
    """Semanas regulares (sin la 53, que es un fragmento) desde `ano_inicio`."""
    return weekly[(weekly["ano"] >= ano_inicio) & (weekly["semana"] != SEASONAL_PERIOD + 1)]


def select_universe(
    weekly: pd.DataFrame,
    objetivo: Objetivo,
    ano_inicio: int = ANO_INICIO,
    min_media: float = MIN_MEDIA_SEMANAL,
    min_media_anual: float = MIN_MEDIA_ANUAL,
) -> pd.DataFrame:
    """Decide qué establecimientos entran al panel y deja el motivo de cada exclusión.

    Reglas, en orden: tipo (solo hospitales si el objetivo lo exige), cobertura
    completa de la ventana (una semana sin reporte rompería la grilla de rezagos
    y no se imputa), volumen medio mínimo y un piso de volumen en cada año de la
    ventana. Devuelve una fila por
    establecimiento del mart, incluidos los excluidos.
    """
    ventana = _ventana(weekly, ano_inicio)
    total = ventana[["ano", "semana"]].drop_duplicates().shape[0]
    resumen = ventana.groupby("establecimiento_codigo").agg(
        establecimiento_glosa=("establecimiento_glosa", "first"),
        tipo=("tipo_establecimiento_urgencia", "first"),
        comuna_codigo=("comuna_codigo", "first"),
        semanas=("semana", "size"),
        media_semanal=(objetivo.target, "mean"),
    )
    # Los que solo reportan antes de la ventana también se informan.
    fuera = set(weekly["establecimiento_codigo"]) - set(resumen.index)
    if fuera:
        previos = weekly[weekly["establecimiento_codigo"].isin(fuera)].groupby(
            "establecimiento_codigo"
        ).agg(
            establecimiento_glosa=("establecimiento_glosa", "first"),
            tipo=("tipo_establecimiento_urgencia", "first"),
            comuna_codigo=("comuna_codigo", "first"),
        ).assign(semanas=0, media_semanal=float("nan"))
        resumen = pd.concat([resumen, previos])

    motivo = pd.Series("", index=resumen.index, dtype=object)
    if objetivo.solo_hospitales:
        motivo = motivo.mask(resumen["tipo"] != "Hospital", "no es hospital")
    motivo = motivo.mask(
        (motivo == "") & (resumen["semanas"] < total),
        "semanas sin reporte en la ventana",
    )
    motivo = motivo.mask(
        (motivo == "") & (resumen["media_semanal"] < min_media),
        f"volumen medio menor a {min_media:g} por semana",
    )
    # Piso en cada año: ver MIN_MEDIA_ANUAL.
    por_ano = ventana.groupby(["establecimiento_codigo", "ano"])[objetivo.target].mean()
    resumen["media_semanal_minima_anual"] = por_ano.groupby(level=0).min().reindex(resumen.index)
    motivo = motivo.mask(
        (motivo == "") & (resumen["media_semanal_minima_anual"] < min_media_anual),
        f"volumen medio menor a {min_media_anual:g} por semana en algún año de la ventana",
    )
    resumen["incluido"] = motivo == ""
    resumen["motivo_exclusion"] = motivo.where(motivo != "", None)
    resumen["semanas_ventana"] = total
    return resumen.reset_index().sort_values(
        ["incluido", "media_semanal"], ascending=[False, False]
    ).reset_index(drop=True)


def build_establishment_panel(
    weekly: pd.DataFrame,
    objetivo: Objetivo,
    universo: pd.DataFrame,
    ano_inicio: int = ANO_INICIO,
) -> pd.DataFrame:
    """Panel largo `series_id x t` con los establecimientos incluidos y su total.

    Mismo esquema que el panel comunal en lo que usa el motor (`series_id`,
    `nivel`, `t`, `ano`, `semana`, `y` y las covariables), más los atributos
    del establecimiento, que no entran como predictores. No lleva población:
    la de la comuna no representa la población atendida por un establecimiento.
    """
    incluidos = set(universo.loc[universo["incluido"], "establecimiento_codigo"])
    if not incluidos:
        raise ValueError(f"Ningún establecimiento cumple las reglas del objetivo {objetivo.nombre}.")
    ventana = _ventana(weekly, ano_inicio)
    hojas = ventana[ventana["establecimiento_codigo"].isin(incluidos)].copy()
    hojas["series_id"] = hojas["establecimiento_codigo"].astype(str)
    hojas["nivel"] = NIVEL_ESTABLECIMIENTO

    columnas_valor = [objetivo.target, *objetivo.exogenas]
    total = hojas.groupby(["ano", "semana"], as_index=False)[columnas_valor].sum()
    total["series_id"] = RM_SERIES_ID
    total["nivel"] = "region"
    total["establecimiento_glosa"] = "Total de los establecimientos del universo"

    panel = _add_time_index(pd.concat([hojas, total], ignore_index=True))
    panel = panel.rename(columns={objetivo.target: "y"}).sort_values(["series_id", "t"])
    if panel.duplicated(["series_id", "t"]).any():
        raise ValueError("Panel de establecimientos con grano duplicado (series_id, t).")
    if panel.groupby("series_id")["t"].size().nunique() != 1:
        raise ValueError("Las series del panel no comparten la misma longitud.")
    columnas = [
        "series_id", "nivel", *ATRIBUTOS, "t", "ano", "semana", "y", *objetivo.exogenas,
    ]
    return panel[columnas].reset_index(drop=True)


# --------------------------------------------------------------------------
# Año en curso (holdout y pronóstico)
# --------------------------------------------------------------------------

def load_current_weekly(
    anos: list[int], processed_dir: Path = URGENCIAS_PROCESSED_DIR
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Semanal por establecimiento de los años posteriores al mart, solo semanas completas.

    Usa la misma carga y el mismo constructor que el mart de entrenamiento, de
    modo que causas, agregación y calendario son idénticos. La última semana
    publicada suele estar truncada: tratada como completa parecería una caída de
    demanda, así que se excluyen las semanas regulares con menos días que una
    semana completa. Devuelve el semanal y la tabla de semanas excluidas.
    """
    fuente = load_urgencias_source(
        input_dir=processed_dir, extra_columns=EXTRA_SOURCE_COLUMNS,
        years=tuple(anos), causes=WEEKLY_CAUSES,
    )
    dias = fuente.groupby(["ano", "semana"])["fecha"].nunique().rename("dias").reset_index()
    regulares = dias["semana"] != SEASONAL_PERIOD + 1
    incompletas = dias[regulares & (dias["dias"] < DIAS_SEMANA_COMPLETA)]
    semanal = build_establecimiento_weekly_mart(fuente)
    claves = set(zip(incompletas["ano"], incompletas["semana"]))
    semanal = semanal[~pd.Series(list(zip(semanal["ano"], semanal["semana"])), index=semanal.index).isin(claves)]
    return semanal.reset_index(drop=True), incompletas.reset_index(drop=True)


def fixed_universe(
    universo: pd.DataFrame, actual: pd.DataFrame, objetivo: Objetivo,
    max_excluida_pct: float = MAX_SHARE_EXCLUIDA_PCT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Universo del benchmark restringido a los que reportan todas las semanas del año en curso.

    Un establecimiento que deja de reportar deja de tener dato, no demanda cero:
    se excluye y se informa desde cuándo falta. El total del panel se define
    sobre el universo resultante también en el entrenamiento, para que no cambie
    de definición a mitad de la serie. Si lo excluido supera `max_excluida_pct`
    del volumen del objetivo en el año en curso, falla: la evaluación ya no
    representaría al universo seleccionado.
    """
    regulares = actual[actual["semana"] != SEASONAL_PERIOD + 1]
    esperadas = regulares[["ano", "semana"]].drop_duplicates().shape[0]
    incluidos = universo[universo["incluido"]].copy()
    presentes = regulares.groupby("establecimiento_codigo").agg(
        semanas=("semana", "size"), ultima=("fecha_inicio_semana", "max"),
        volumen=(objetivo.target, "sum"),
    )
    incluidos = incluidos.join(presentes, on="establecimiento_codigo", rsuffix="_actual")
    incluidos["semanas_actual"] = incluidos["semanas_actual"].fillna(0).astype(int)
    cortos = incluidos["semanas_actual"] < esperadas
    excluidos = incluidos[cortos][
        ["establecimiento_codigo", "establecimiento_glosa", "tipo", "semanas_actual", "ultima", "volumen"]
    ].rename(columns={"semanas_actual": "semanas_reportadas", "ultima": "ultima_semana"})
    excluidos["semanas_esperadas"] = esperadas
    total = float(incluidos["volumen"].fillna(0).sum())
    excluidos["share_pct"] = (excluidos["volumen"].fillna(0) / total * 100).round(2) if total else 0.0
    if float(excluidos["share_pct"].sum()) > max_excluida_pct:
        raise ValueError(
            f"Lo excluido por cobertura incompleta en el año en curso suma "
            f"{excluidos['share_pct'].sum():.1f}% del volumen de {objetivo.nombre}, "
            f"sobre el máximo de {max_excluida_pct}%."
        )
    final = universo.copy()
    final.loc[final["establecimiento_codigo"].isin(excluidos["establecimiento_codigo"]), "incluido"] = False
    return final, excluidos.reset_index(drop=True)
