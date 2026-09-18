"""EDA reproducible de `mart_urgencias_establecimiento_monthly`.

Script de solo lectura: no modifica el mart ni genera outputs canónicos del
pipeline. Calcula las cifras citadas en
`reports/eda/eda_mart_urgencias_establecimiento.md` y en
`reports/dictionary/diccionario_mart_urgencias_establecimiento_monthly.md`,
y escribe una tabla resumen de apoyo en
`reports/eda/eda_mart_urgencias_establecimiento_resumen.csv`.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS
from src.data.clean_censo_comunas import EXPECTED_RM_CUTS

sys.stdout.reconfigure(encoding="utf-8")

ESTABLECIMIENTO_PATH = Path("data/processed/marts/mart_urgencias_establecimiento_monthly.parquet")
COMUNA_MONTHLY_PATH = Path("data/processed/marts/mart_urgencias_comuna_monthly.parquet")
OUTPUT_SUMMARY = Path("reports/eda/eda_mart_urgencias_establecimiento_resumen.csv")


def _missing_rm_comunas(mart: pd.DataFrame) -> set[str]:
    expected = {str(cut) for cut in EXPECTED_RM_CUTS}
    return expected - set(mart["comuna_codigo"].unique())


def main() -> None:
    mart = pq.read_table(ESTABLECIMIENTO_PATH).to_pandas()
    monthly = pq.read_table(COMUNA_MONTHLY_PATH).to_pandas()

    print("=== Forma del mart ===")
    print(f"{mart.shape[0]:,} filas x {mart.shape[1]} columnas")

    print("\n=== Cobertura ===")
    n_establecimientos = mart["establecimiento_codigo"].nunique()
    n_comunas = mart["comuna_codigo"].nunique()
    print("establecimientos únicos:", n_establecimientos)
    print("comunas únicas:", n_comunas)
    print("comunas RM faltantes:", sorted(_missing_rm_comunas(mart)))
    print("ano mínimo/máximo:", mart["ano"].min(), mart["ano"].max())
    meses_por_establecimiento = mart.groupby("establecimiento_codigo").size()
    print(
        "meses reportados por establecimiento: min",
        meses_por_establecimiento.min(),
        "max",
        meses_por_establecimiento.max(),
        "(60 = todos los meses 2021-2025)",
    )
    n_establecimientos_completos = (meses_por_establecimiento == 60).sum()
    print(
        f"establecimientos con los 60 meses reportados: {n_establecimientos_completos} de {n_establecimientos}"
    )

    print("\n=== tipo_establecimiento_urgencia (filas del mart) ===")
    tipo_counts = mart["tipo_establecimiento_urgencia"].value_counts()
    print(tipo_counts)
    n_establecimientos_por_tipo = mart.drop_duplicates("establecimiento_codigo")[
        "tipo_establecimiento_urgencia"
    ].value_counts()
    print("\nestablecimientos únicos por tipo:")
    print(n_establecimientos_por_tipo)

    print("\n=== Nulos en columnas de conteo ===")
    print(mart[list(COUNT_COLUMNS)].isna().sum())

    print("\n=== Nulos en ratios (denominador 0 o ausente) ===")
    ratio_cols = [c for c in mart.columns if c.startswith("proporcion_")]
    print(mart[ratio_cols].isna().sum())

    print("\n=== Reconciliación establecimiento→comuna vs mart_urgencias_comuna_monthly ===")
    aggregated = mart.groupby(["comuna_codigo", "fecha_mes"], as_index=False)[
        list(COUNT_COLUMNS)
    ].sum(min_count=1)
    reference = monthly[["comuna_codigo", "fecha_mes", *COUNT_COLUMNS]]
    merged = aggregated.merge(
        reference, on=["comuna_codigo", "fecha_mes"], suffixes=("_estab", "_comuna")
    )
    reconciles = all(
        merged[f"{c}_estab"].equals(merged[f"{c}_comuna"]) for c in COUNT_COLUMNS
    )
    print(
        f"filas comuna×mes agregadas desde establecimiento: {len(aggregated):,}; "
        f"filas de referencia en mart comunal: {len(reference):,}; "
        f"universo comuna×mes idéntico: {len(aggregated) == len(reference)}"
    )
    print("¿reconcilia exactamente por causa (ID1, ID35-41)?", reconciles)

    print("\n=== Totales de atenciones 2021-2025 por causa (mart de establecimiento) ===")
    print(mart[list(COUNT_COLUMNS)].sum())

    summary = pd.DataFrame(
        {
            "metrica": [
                "filas", "establecimientos_unicos", "comunas_unicas",
                "establecimientos_con_60_meses",
                "reconciliacion_establecimiento_comuna_ok",
                "universo_comuna_mes_identico",
            ],
            "valor": [
                mart.shape[0], n_establecimientos, n_comunas,
                int(n_establecimientos_completos),
                bool(reconciles),
                bool(len(aggregated) == len(reference)),
            ],
        }
    )
    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\nResumen escrito en {OUTPUT_SUMMARY.as_posix()}")


if __name__ == "__main__":
    main()
