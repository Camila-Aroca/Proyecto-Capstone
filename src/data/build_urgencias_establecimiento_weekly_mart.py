"""Construye el mart semanal de atenciones de Urgencia por establecimiento.

Grano: `establecimiento_codigo` x (`ano`, `semana`) con la semana publicada por
DEIS, 2021--2025. Es el insumo del pronóstico por establecimiento, que necesita
la misma grilla semanal que el modelo comunal.

Además de las causas del contrato comunal (ID1 y la familia de salud mental
ID35 a ID41) incorpora **ID42, hospitalizaciones derivadas desde la urgencia
por trastornos mentales (F00-F99)**, publicadas en la sección 2 del archivo
DEIS. ID42 no es una subcausa de ID36 y no entra en la jerarquía causal.

Reglas de completitud, verificadas sobre 2021-2025 antes de fijarlas aquí:

- Cuando un establecimiento reporta una semana, publica siempre sus filas de
  ID36 e ID42, aunque el valor sea cero. Un cero del mart es, por lo tanto, un
  cero publicado. En ese período solo los hospitales informan ID42 positivo;
  es un hecho observado que documenta el EDA, no una regla que se imponga.
- Una semana sin filas del establecimiento es ausencia de reporte: no se
  genera la fila ni se rellena con cero.

No incorpora población ni tasas: la población comunal no representa la
población atendida de un establecimiento (ver el mart mensual).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_comuna_marts import (
    CAUSES,
    COUNT_COLUMNS,
    add_ratios,
    atomic_write,
    load_urgencias_source,
    validate_causal_hierarchy,
    validate_non_negative,
    validate_ratios,
)

OUTPUT_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_establecimiento_weekly.parquet"
)
COMUNA_WEEKLY_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_comuna_weekly.parquet"
)
# Hospitalizaciones derivadas desde urgencia por F00-F99 (sección 2 DEIS).
HOSPITALIZACION_CAUSE: Final[int] = 42
HOSPITALIZACION_COLUMN: Final[str] = f"atenciones_id{HOSPITALIZACION_CAUSE}"
WEEKLY_CAUSES: Final[tuple[int, ...]] = (*CAUSES, HOSPITALIZACION_CAUSE)
WEEKLY_COUNT_COLUMNS: Final[tuple[str, ...]] = (*COUNT_COLUMNS, HOSPITALIZACION_COLUMN)
EXTRA_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "establecimiento_glosa", "tipo_establecimiento_urgencia",
)
ATTRIBUTE_COLUMNS: Final[tuple[str, ...]] = (
    "comuna_codigo", "comuna_glosa", "establecimiento_glosa",
    "tipo_establecimiento_urgencia",
)
GRAIN: Final[list[str]] = ["establecimiento_codigo", "ano", "semana"]
PERIODO: Final[tuple[int, int]] = (2021, 2025)


def load_source() -> pd.DataFrame:
    """Lee Urgencias 2021-2025 con las causas del mart y los datos del establecimiento."""
    return load_urgencias_source(extra_columns=EXTRA_SOURCE_COLUMNS, causes=WEEKLY_CAUSES)


def build_establecimiento_weekly_mart(source: pd.DataFrame) -> pd.DataFrame:
    """Agrega el origen diario a establecimiento x semana DEIS.

    `fecha_inicio_semana` es la fecha mínima observada de cada semana en todo el
    origen, la misma regla del mart comunal semanal, de modo que ambos marts
    comparten calendario. Los atributos del establecimiento entran en la llave
    de agregación: si alguno variara dentro de una semana, el grano quedaría
    duplicado y la validación lo detecta.
    """
    required = {"ano", "semana", "fecha", "id_causa", "total", "establecimiento_codigo",
                *ATTRIBUTE_COLUMNS}
    if missing := required - set(source.columns):
        raise ValueError(f"Columnas faltantes para el mart semanal: {sorted(missing)}")
    if not source["id_causa"].isin(WEEKLY_CAUSES).all():
        raise ValueError("El origen contiene IDs fuera del contrato del mart semanal.")

    working = source.copy()
    working["fecha"] = pd.to_datetime(working["fecha"])
    starts = (
        working.groupby(["ano", "semana"], as_index=False)["fecha"].min()
        .rename(columns={"fecha": "fecha_inicio_semana"})
    )
    index = [*GRAIN, *ATTRIBUTE_COLUMNS]
    mart = (
        working.groupby([*index, "id_causa"], as_index=False)["total"].sum()
        .pivot(index=index, columns="id_causa", values="total")
        .rename(columns=lambda cause: f"atenciones_id{cause}")
        .reset_index()
    )
    mart.columns.name = None
    for column in WEEKLY_COUNT_COLUMNS:
        if column not in mart:
            mart[column] = pd.NA
        # Nulo = la causa no se publicó esa semana; no se convierte en cero.
        mart[column] = mart[column].astype("Int64")
    mart = mart.merge(starts, on=["ano", "semana"], how="left", validate="many_to_one")
    mart["fecha_inicio_semana"] = mart["fecha_inicio_semana"].dt.date.astype(str)
    mart = add_ratios(mart)
    ordered = [*GRAIN, *ATTRIBUTE_COLUMNS, "fecha_inicio_semana", *WEEKLY_COUNT_COLUMNS]
    resto = [column for column in mart.columns if column not in ordered]
    return mart[ordered + resto].sort_values(GRAIN).reset_index(drop=True)


def validate_mart(mart: pd.DataFrame) -> None:
    """Grano único, llaves sin nulos, no negatividad, jerarquía causal y período."""
    if mart.duplicated(GRAIN).any():
        raise ValueError("Grano establecimiento×semana no único.")
    if mart[GRAIN].isna().any().any():
        raise ValueError("Grano establecimiento×semana con llave nula.")
    validate_non_negative(mart, list(WEEKLY_COUNT_COLUMNS))
    validate_causal_hierarchy(mart)
    validate_ratios(mart)
    ano_min, ano_max = int(mart["ano"].min()), int(mart["ano"].max())
    if ano_min < PERIODO[0] or ano_max > PERIODO[1]:
        raise ValueError(f"Período fuera del contrato {PERIODO[0]}-{PERIODO[1]}: {ano_min}-{ano_max}.")


def validate_reconciliation_with_comuna_weekly(
    mart: pd.DataFrame, comuna_weekly: pd.DataFrame
) -> None:
    """Sumar establecimientos por comuna x semana debe dar el mart comunal semanal.

    Ambos marts salen del mismo origen; la comparación cubre las causas del
    contrato comunal (`COUNT_COLUMNS`). ID42 no existe en el mart comunal.
    """
    columns = list(COUNT_COLUMNS)
    agregado = mart.groupby(["comuna_codigo", "ano", "semana"], as_index=False)[columns].sum(
        min_count=1
    )
    referencia = comuna_weekly[["comuna_codigo", "ano", "semana", *columns]]
    unido = agregado.merge(
        referencia, on=["comuna_codigo", "ano", "semana"], suffixes=("_estab", "_comuna"),
        how="outer", validate="one_to_one", indicator=True,
    )
    if (unido["_merge"] != "both").any():
        raise ValueError(
            "El universo comuna×semana agregado desde establecimiento no coincide "
            "con mart_urgencias_comuna_weekly."
        )
    for column in columns:
        estab = unido[f"{column}_estab"].astype("Int64")
        comuna = unido[f"{column}_comuna"].astype("Int64")
        if not estab.equals(comuna):
            raise ValueError(f"No reconcilia establecimiento→comuna semanal: {column}")


def main() -> None:
    """Genera, valida y publica el mart semanal de Urgencias por establecimiento."""
    mart = build_establecimiento_weekly_mart(load_source())
    validate_mart(mart)
    comuna_weekly = pq.read_table(
        COMUNA_WEEKLY_PATH, columns=["comuna_codigo", "ano", "semana", *COUNT_COLUMNS]
    ).to_pandas()
    validate_reconciliation_with_comuna_weekly(mart, comuna_weekly)
    atomic_write(mart, OUTPUT_PATH)
    print(
        f"Mart semanal por establecimiento generado: {len(mart):,} filas, "
        f"{mart['establecimiento_codigo'].nunique()} establecimientos."
    )


if __name__ == "__main__":
    main()
