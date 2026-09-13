"""EDA reproducible de `mart_urgencias_comuna_weekly` y `mart_urgencias_comuna_monthly`.

Script de solo lectura: no modifica los marts ni genera outputs canónicos del
pipeline. Calcula las cifras citadas en
`reports/eda/eda_mart_urgencias_comuna.md` y en los diccionarios de
`reports/dictionary/`, y escribe una tabla resumen de apoyo en
`reports/eda/eda_mart_urgencias_comuna_resumen.csv`.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.dataset as ds
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.data.clean_censo_comunas import EXPECTED_RM_CUTS

sys.stdout.reconfigure(encoding="utf-8")

WEEKLY_PATH = Path("data/processed/marts/mart_urgencias_comuna_weekly.parquet")
MONTHLY_PATH = Path("data/processed/marts/mart_urgencias_comuna_monthly.parquet")
URGENCIAS_DIR = Path("data/processed/urgencias")
YEARS = range(2021, 2026)
CAUSES = (1, 35, 36, 37, 38, 39, 40, 41)
COUNT_COLUMNS = [f"atenciones_id{cause}" for cause in CAUSES]
OUTPUT_SUMMARY = Path("reports/eda/eda_mart_urgencias_comuna_resumen.csv")


def _load_glosa_causa() -> pd.DataFrame:
    files = [URGENCIAS_DIR / f"urgencias_rm_{year}.parquet" for year in YEARS]
    dataset = ds.dataset(files, format="parquet")
    table = dataset.to_table(
        filter=pc.field("id_causa").isin(CAUSES), columns=["id_causa", "glosa_causa"]
    )
    return table.to_pandas().drop_duplicates().sort_values("id_causa")


def _missing_rm_comunas(mart: pd.DataFrame) -> set[str]:
    expected = {str(cut) for cut in EXPECTED_RM_CUTS}
    return expected - set(mart["comuna_codigo"].unique())


def main() -> None:
    weekly = pq.read_table(WEEKLY_PATH).to_pandas()
    monthly = pq.read_table(MONTHLY_PATH).to_pandas()

    print("=== Forma de los marts ===")
    print(f"weekly: {weekly.shape[0]:,} filas x {weekly.shape[1]} columnas")
    print(f"monthly: {monthly.shape[0]:,} filas x {monthly.shape[1]} columnas")

    print("\n=== Cobertura comuna×periodo ===")
    print("weekly comunas únicas:", weekly["comuna_codigo"].nunique())
    print("monthly comunas únicas:", monthly["comuna_codigo"].nunique())
    print("weekly comunas RM faltantes:", sorted(_missing_rm_comunas(weekly)))
    print("monthly comunas RM faltantes:", sorted(_missing_rm_comunas(monthly)))
    print("filas por comuna (weekly), valores únicos:", sorted(weekly.groupby("comuna_codigo").size().unique().tolist()))
    print("filas por comuna (monthly), valores únicos:", sorted(monthly.groupby("comuna_codigo").size().unique().tolist()))

    print("\n=== Glosas observadas por id_causa (fuente Urgencias limpia) ===")
    print(_load_glosa_causa().to_string(index=False))

    print("\n=== Totales de atenciones 2021-2025 por causa (weekly) ===")
    print(weekly[COUNT_COLUMNS].sum())

    print("\n=== Nulos en columnas de conteo ===")
    print("weekly:\n", weekly[COUNT_COLUMNS].isna().sum())
    print("monthly:\n", monthly[COUNT_COLUMNS].isna().sum())

    print("\n=== Reconciliación anual weekly vs monthly (ID1, ID36) ===")
    w = weekly.groupby("ano")[["atenciones_id1", "atenciones_id36"]].sum(min_count=1)
    m = monthly.groupby("ano")[["atenciones_id1", "atenciones_id36"]].sum(min_count=1)
    print("weekly:\n", w)
    print("monthly:\n", m)
    print("¿reconcilian exactamente?", w.equals(m))

    print("\n=== Nulos en ratios (denominador 0 o ausente) ===")
    ratio_cols = [c for c in weekly.columns if c.startswith("proporcion_")]
    print(weekly[ratio_cols].isna().sum())

    print("\n=== Distribución tasa_atenciones_id36_por_10000 (weekly) ===")
    print(weekly["tasa_atenciones_id36_por_10000"].describe())

    print("\n=== Establecimientos reportantes ID1 vs ID36 ===")
    equal_share = (
        weekly["n_establecimientos_reportantes_id1"] == weekly["n_establecimientos_reportantes_id36"]
    ).mean()
    print(f"proporción de filas con reportantes ID1 == ID36 (weekly): {equal_share:.4f}")

    print("\n=== Calendario semanal DEIS ===")
    print("semana mínima/máxima:", weekly["semana"].min(), weekly["semana"].max())
    print("filas con semana=53:", int((weekly["semana"] == 53).sum()))

    summary = pd.DataFrame(
        {
            "metrica": [
                "weekly_filas", "monthly_filas",
                "weekly_comunas_unicas", "monthly_comunas_unicas",
                "reconciliacion_anual_id1_id36_ok",
                "reportantes_id1_igual_id36_weekly_proporcion",
                "tasa_id36_por_10000_media_weekly",
                "tasa_id36_por_10000_max_weekly",
            ],
            "valor": [
                weekly.shape[0], monthly.shape[0],
                weekly["comuna_codigo"].nunique(), monthly["comuna_codigo"].nunique(),
                bool(w.equals(m)),
                round(float(equal_share), 4),
                round(float(weekly["tasa_atenciones_id36_por_10000"].mean()), 4),
                round(float(weekly["tasa_atenciones_id36_por_10000"].max()), 4),
            ],
        }
    )
    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\nResumen escrito en {OUTPUT_SUMMARY.as_posix()}")


if __name__ == "__main__":
    main()
