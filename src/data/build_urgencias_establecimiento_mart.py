"""Construye el mart mensual de atenciones de Urgencia por establecimiento.

Grano: `establecimiento_codigo` x `fecha_mes` (mes calendario derivado de la
`fecha` diaria del origen), 2021--2025 exclusivamente. Reutiliza la carga,
agregación, ratios y validación causal de
`src/data/build_urgencias_comuna_marts.py` para no duplicar esa lógica.

No incorpora población ni tasas por 10.000 habitantes: la población comunal
(`dim_poblacion_comuna_anual`) es un denominador territorial y no representa
la población atendida de un establecimiento individual (varios
establecimientos comparten comuna; un establecimiento puede atender
población de otras comunas). Inventar una tasa por establecimiento a partir
de ese denominador sería un supuesto no respaldado por los datos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_comuna_marts import (
    COUNT_COLUMNS,
    add_ratios,
    aggregate_grain,
    atomic_write,
    load_urgencias_source,
    validate_causal_hierarchy,
    validate_non_negative,
    validate_ratios,
)

OUTPUT_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_establecimiento_monthly.parquet"
)
COMUNA_MONTHLY_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_comuna_monthly.parquet"
)
EXTRA_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "establecimiento_glosa", "tipo_establecimiento_urgencia",
)
ATTRIBUTE_COLUMNS: Final[tuple[str, ...]] = (
    "comuna_codigo", "comuna_glosa", "establecimiento_glosa",
    "tipo_establecimiento_urgencia",
)


def load_source() -> pd.DataFrame:
    """Lee Urgencias 2021-2025 agregando las columnas de establecimiento."""
    return load_urgencias_source(extra_columns=EXTRA_SOURCE_COLUMNS)


def build_establecimiento_monthly_mart(source: pd.DataFrame) -> pd.DataFrame:
    """Construye el mart establecimiento×mes a partir de las fechas diarias DEIS.

    `tipo_establecimiento_urgencia` se incorpora como atributo del grano
    porque, verificado sobre 2021-2025, cada `establecimiento_codigo`
    reporta un único valor de `tipo_establecimiento_urgencia`,
    `establecimiento_glosa` y `comuna_codigo` (regla determinista, sin
    fragmentar el grano establecimiento×mes).
    """
    required = {"fecha", "establecimiento_codigo", *ATTRIBUTE_COLUMNS}
    if missing := required - set(source.columns):
        raise ValueError(f"Columnas faltantes para el mart de establecimiento: {sorted(missing)}")
    working = source.copy()
    working["fecha"] = pd.to_datetime(working["fecha"])
    working["mes"] = working["fecha"].dt.month
    working["fecha_mes"] = working["fecha"].dt.to_period("M").dt.start_time
    mart = aggregate_grain(
        working,
        grain_columns=["ano", "mes", "fecha_mes", "establecimiento_codigo"],
        attribute_columns=ATTRIBUTE_COLUMNS,
        include_reporters=False,
    )
    mart["fecha_mes"] = mart["fecha_mes"].dt.date.astype(str)
    mart = add_ratios(mart)
    ordered = ["establecimiento_codigo", "fecha_mes"]
    return mart.sort_values(ordered).reset_index(drop=True)


def validate_mart(mart: pd.DataFrame) -> None:
    """Valida grano único, no negatividad, jerarquía causal y ratios."""
    grain_keys = ["establecimiento_codigo", "fecha_mes"]
    if mart.duplicated(grain_keys).any():
        raise ValueError("Grano establecimiento×mes no único.")
    if mart["establecimiento_codigo"].isna().any() or mart["fecha_mes"].isna().any():
        raise ValueError("Grano establecimiento×mes con llave nula.")
    validate_non_negative(mart)
    validate_causal_hierarchy(mart)
    validate_ratios(mart)
    ano_min, ano_max = mart["ano"].min(), mart["ano"].max()
    if ano_min < 2021 or ano_max > 2025:
        raise ValueError(f"Período fuera del contrato 2021-2025: {ano_min}-{ano_max}.")


def validate_reconciliation_with_comuna_monthly(
    establecimiento_mart: pd.DataFrame, comuna_monthly: pd.DataFrame
) -> None:
    """Verifica que sumar establecimientos por comuna×mes reconcilie con el mart comunal.

    Ambos marts derivan del mismo origen filtrado por las mismas causas; sumar
    el mart de establecimiento por `comuna_codigo`×`fecha_mes` debe coincidir
    exactamente con `mart_urgencias_comuna_monthly` para las causas del
    contrato (`COUNT_COLUMNS`).
    """
    columns = list(COUNT_COLUMNS)
    aggregated = establecimiento_mart.groupby(
        ["comuna_codigo", "fecha_mes"], as_index=False
    )[columns].sum(min_count=1)
    reference = comuna_monthly[["comuna_codigo", "fecha_mes", *columns]]
    merged = aggregated.merge(
        reference,
        on=["comuna_codigo", "fecha_mes"],
        suffixes=("_estab", "_comuna"),
        validate="one_to_one",
    )
    if len(merged) != len(reference):
        raise ValueError(
            "El universo comuna×mes agregado desde establecimiento no coincide "
            "con mart_urgencias_comuna_monthly."
        )
    for column in columns:
        if not merged[f"{column}_estab"].equals(merged[f"{column}_comuna"]):
            raise ValueError(f"No reconcilia establecimiento→comuna: {column}")


def main() -> None:
    """Genera y valida el mart mensual de Urgencias por establecimiento."""
    source = load_source()
    mart = build_establecimiento_monthly_mart(source)
    validate_mart(mart)
    comuna_monthly = pq.read_table(
        COMUNA_MONTHLY_PATH, columns=["comuna_codigo", "fecha_mes", *COUNT_COLUMNS]
    ).to_pandas()
    validate_reconciliation_with_comuna_monthly(mart, comuna_monthly)
    atomic_write(mart, OUTPUT_PATH)
    print(f"Mart de Urgencias por establecimiento generado: {len(mart):,} filas.")


if __name__ == "__main__":
    main()
