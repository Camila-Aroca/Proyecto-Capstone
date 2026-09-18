"""Construye el mart mensual comunal de Urgencias con desglose etario, en
formato largo: `comuna_codigo` x `fecha_mes` x `grupo_etario_urgencia`,
2021--2025 exclusivamente.

Usa exclusivamente los cinco grupos etarios publicados por DEIS en Urgencias
(`menores_1`, `de_1_a_4`, `de_5_a_14`, `de_15_a_64`, `de_65_y_mas`); Urgencias
no contiene sexo/género, por lo que este mart no lo incorpora. Reutiliza la
carga, agregación y validación causal de
`src/data/build_urgencias_comuna_marts.py`.

No incluye `total` junto a los grupos etarios: `total` ya equivale a la suma
de los cinco grupos por registro (verificado sin excepciones sobre
2021-2025), por lo que mantener ambos duplicaría la misma cifra bajo dos
nombres.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_comuna_marts import (
    COUNT_COLUMNS,
    aggregate_grain,
    atomic_write,
    load_urgencias_source,
    validate_causal_hierarchy,
    validate_non_negative,
)

OUTPUT_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_comuna_etario_monthly.parquet"
)
COMUNA_MONTHLY_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_comuna_monthly.parquet"
)
AGE_GROUPS: Final[tuple[str, ...]] = (
    "menores_1", "de_1_a_4", "de_5_a_14", "de_15_a_64", "de_65_y_mas",
)
AGE_GROUP_COLUMN: Final[str] = "grupo_etario_urgencia"


def load_source() -> pd.DataFrame:
    """Lee Urgencias 2021-2025 agregando las columnas de desglose etario."""
    return load_urgencias_source(extra_columns=AGE_GROUPS)


def build_comuna_etario_monthly_mart(source: pd.DataFrame) -> pd.DataFrame:
    """Construye el mart comuna×mes×grupo_etario a partir de las fechas diarias DEIS.

    Convierte los cinco grupos etarios (columnas anchas) en formato largo
    antes de agregar, usando cada grupo como el valor a sumar en lugar de
    `total`.
    """
    required = {"fecha", "comuna_codigo", "comuna_glosa", "id_causa", *AGE_GROUPS}
    if missing := required - set(source.columns):
        raise ValueError(f"Columnas faltantes para el mart etario: {sorted(missing)}")
    working = source.copy()
    working["fecha"] = pd.to_datetime(working["fecha"])
    working["mes"] = working["fecha"].dt.month
    working["fecha_mes"] = working["fecha"].dt.to_period("M").dt.start_time
    id_vars = ["ano", "mes", "fecha_mes", "comuna_codigo", "comuna_glosa", "id_causa"]
    melted = working[[*id_vars, *AGE_GROUPS]].melt(
        id_vars=id_vars,
        value_vars=list(AGE_GROUPS),
        var_name=AGE_GROUP_COLUMN,
        value_name="total",
    )
    mart = aggregate_grain(
        melted,
        grain_columns=["ano", "mes", "fecha_mes", AGE_GROUP_COLUMN],
        attribute_columns=("comuna_codigo", "comuna_glosa"),
        include_reporters=False,
    )
    mart["fecha_mes"] = mart["fecha_mes"].dt.date.astype(str)
    ordered = ["comuna_codigo", "fecha_mes", AGE_GROUP_COLUMN]
    return mart.sort_values(ordered).reset_index(drop=True)


def validate_mart(mart: pd.DataFrame) -> None:
    """Valida grano único, no negatividad, jerarquía causal y dominio etario."""
    grain_keys = ["comuna_codigo", "fecha_mes", AGE_GROUP_COLUMN]
    if mart.duplicated(grain_keys).any():
        raise ValueError("Grano comuna×mes×grupo_etario no único.")
    if not set(mart[AGE_GROUP_COLUMN].unique()) <= set(AGE_GROUPS):
        raise ValueError("Se detectaron valores de grupo_etario_urgencia fuera del contrato.")
    validate_non_negative(mart)
    validate_causal_hierarchy(mart)
    ano_min, ano_max = mart["ano"].min(), mart["ano"].max()
    if ano_min < 2021 or ano_max > 2025:
        raise ValueError(f"Período fuera del contrato 2021-2025: {ano_min}-{ano_max}.")


def validate_reconciliation_with_comuna_monthly(
    etario_mart: pd.DataFrame, comuna_monthly: pd.DataFrame
) -> None:
    """Verifica que sumar los 5 grupos etarios por comuna×mes reconcilie con el mart comunal."""
    columns = list(COUNT_COLUMNS)
    aggregated = etario_mart.groupby(
        ["comuna_codigo", "fecha_mes"], as_index=False
    )[columns].sum(min_count=1)
    reference = comuna_monthly[["comuna_codigo", "fecha_mes", *columns]]
    merged = aggregated.merge(
        reference,
        on=["comuna_codigo", "fecha_mes"],
        suffixes=("_etario", "_comuna"),
        validate="one_to_one",
    )
    if len(merged) != len(reference):
        raise ValueError(
            "El universo comuna×mes agregado desde grupos etarios no coincide "
            "con mart_urgencias_comuna_monthly."
        )
    for column in columns:
        if not merged[f"{column}_etario"].equals(merged[f"{column}_comuna"]):
            raise ValueError(f"No reconcilia etario→comuna: {column}")


def main() -> None:
    """Genera y valida el mart mensual comunal de Urgencias con desglose etario."""
    source = load_source()
    mart = build_comuna_etario_monthly_mart(source)
    validate_mart(mart)
    comuna_monthly = pq.read_table(
        COMUNA_MONTHLY_PATH, columns=["comuna_codigo", "fecha_mes", *COUNT_COLUMNS]
    ).to_pandas()
    validate_reconciliation_with_comuna_monthly(mart, comuna_monthly)
    atomic_write(mart, OUTPUT_PATH)
    print(f"Mart etario comunal de Urgencias generado: {len(mart):,} filas.")


if __name__ == "__main__":
    main()
