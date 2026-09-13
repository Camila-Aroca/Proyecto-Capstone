"""EDA reproducible de `mart_mvp_territorial_comuna`.

Script de solo lectura: no modifica el mart ni genera outputs canónicos del
pipeline. Calcula las cifras citadas en
`reports/eda/eda_mart_mvp_territorial_comuna.md` y en
`reports/dictionary/diccionario_mart_mvp_territorial_comuna.md`, y escribe una
tabla resumen de apoyo en
`reports/eda/eda_mart_mvp_territorial_comuna_resumen.csv`.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")

MART_PATH = Path("data/processed/marts/mart_mvp_territorial_comuna.parquet")
OFERTA_PATH = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
OUTPUT_SUMMARY = Path("reports/eda/eda_mart_mvp_territorial_comuna_resumen.csv")

DEMAND_COLUMNS = ["atenciones_id1_2025", "atenciones_id35_2025", "atenciones_id36_2025"]
RATE_COLUMNS = [
    "tasa_atenciones_id1_2025_por_10000",
    "tasa_atenciones_id35_2025_por_10000",
    "tasa_atenciones_id36_2025_por_10000",
]
TIPO_COLUMNS = ["n_hospitales", "n_sapu", "n_sar", "n_sur", "n_otras_excepciones"]


def main() -> None:
    mart = pq.read_table(MART_PATH).to_pandas()
    oferta = pq.read_table(OFERTA_PATH, columns=["establecimiento_codigo"]).to_pandas()

    print("=== Forma del mart ===")
    print(f"{mart.shape[0]:,} filas x {mart.shape[1]} columnas")
    print("comuna_codigo únicos:", mart["comuna_codigo"].nunique())
    print("duplicados comuna_codigo:", int(mart["comuna_codigo"].duplicated().sum()))

    print("\n=== Cobertura de reporte de Urgencias 2025 ===")
    sin_reporte = mart.loc[~mart["tiene_reporte_urgencias"], ["comuna_codigo", "comuna_glosa"]]
    print("comunas con reporte:", int(mart["tiene_reporte_urgencias"].sum()))
    print("comunas sin reporte (hecho observado, no imputado):")
    print(sin_reporte.to_string(index=False))

    print("\n=== NULL vs 0 en columnas de demanda (comunas sin reporte) ===")
    check_cols = DEMAND_COLUMNS + RATE_COLUMNS + [
        "n_establecimientos_reportantes_id1_2025", "n_establecimientos_reportantes_id36_2025",
    ]
    sin_reporte_mask = ~mart["tiene_reporte_urgencias"]
    print(mart.loc[sin_reporte_mask, check_cols].isna().all())

    print("\n=== Constantes de temporalidad ===")
    for col, expected in [
        ("ano_demanda", 2025), ("ano_poblacion", 2025), ("ano_censo", 2024),
        ("ano_vulnerabilidad", 2022), ("oferta_temporalidad", "snapshot_actual"),
    ]:
        print(f"{col}: valores únicos = {sorted(mart[col].unique().tolist())}, esperado={expected}")

    print("\n=== Población: positividad y distribución ===")
    print(mart[["poblacion_2025", "poblacion_censada_2024"]].describe())
    print("min poblacion_2025:", int(mart["poblacion_2025"].min()))
    print("min poblacion_censada_2024:", int(mart["poblacion_censada_2024"].min()))

    print("\n=== Vulnerabilidad: cobertura y distribución ===")
    print("indicador_vulnerabilidad no nulos:", int(mart["indicador_vulnerabilidad"].notna().sum()), "/ 52")
    print(mart["indicador_vulnerabilidad"].describe())
    print("tipo_estimacion_sae:\n", mart["tipo_estimacion_sae"].value_counts())

    print("\n=== Oferta: reconciliación contra dim_oferta_urgencia_rm ===")
    total_mart = int(mart["n_oferta_urgencia_actual"].sum())
    total_dim = len(oferta)
    print(f"suma n_oferta_urgencia_actual (mart): {total_mart}")
    print(f"filas dim_oferta_urgencia_rm: {total_dim}")
    print("reconcilian exactamente:", total_mart == total_dim)
    tipo_sum = mart[TIPO_COLUMNS].sum()
    print("\nsuma por tipo:\n", tipo_sum)
    print("suma de tipos == n_oferta_urgencia_actual agregado:", int(tipo_sum.sum()) == total_mart)

    print("\n=== Demanda 2025: reconciliación con mart_urgencias_comuna_monthly ===")
    monthly = pq.read_table(
        Path("data/processed/marts/mart_urgencias_comuna_monthly.parquet"),
        columns=["comuna_codigo", "ano", "atenciones_id1", "atenciones_id35", "atenciones_id36"],
    ).to_pandas()
    monthly_totals = (
        monthly[monthly["ano"] == 2025]
        .groupby("comuna_codigo", as_index=False)[["atenciones_id1", "atenciones_id35", "atenciones_id36"]]
        .sum(min_count=1)
    )
    check = mart.loc[mart["tiene_reporte_urgencias"], ["comuna_codigo"] + DEMAND_COLUMNS].merge(
        monthly_totals, on="comuna_codigo", how="inner"
    )
    reconciles = all(
        (check[demand_col] == check[cause_col]).all()
        for demand_col, cause_col in zip(DEMAND_COLUMNS, ["atenciones_id1", "atenciones_id35", "atenciones_id36"])
    )
    print("reconcilian exactamente (52 - sin_reporte comunas):", reconciles)

    print("\n=== Tasas: recálculo desde conteo anual / población 2025 ===")
    con_reporte = mart["tiene_reporte_urgencias"]
    recompute_ok = True
    for count_col, rate_col in zip(DEMAND_COLUMNS, RATE_COLUMNS):
        recomputed = mart.loc[con_reporte, count_col].astype(float) / mart.loc[con_reporte, "poblacion_2025"] * 10_000
        ok = (recomputed.round(6) == mart.loc[con_reporte, rate_col].round(6)).all()
        recompute_ok = recompute_ok and ok
        print(f"{rate_col} recalculada correctamente: {ok}")

    print("\n=== Distribución descriptiva de tasas (solo comunas con reporte) ===")
    print(mart.loc[con_reporte, RATE_COLUMNS].describe())

    summary = pd.DataFrame({
        "metrica": [
            "filas_mart", "comunas_unicas", "comunas_con_reporte_urgencias_2025",
            "comunas_sin_reporte_urgencias_2025", "oferta_total_mart", "oferta_total_dim",
            "oferta_reconcilia", "demanda_2025_reconcilia_monthly", "tasas_recalculadas_ok",
            "poblacion_2025_min", "poblacion_censada_2024_min", "indicador_vulnerabilidad_cobertura",
        ],
        "valor": [
            mart.shape[0], mart["comuna_codigo"].nunique(), int(mart["tiene_reporte_urgencias"].sum()),
            int((~mart["tiene_reporte_urgencias"]).sum()), total_mart, total_dim,
            total_mart == total_dim, reconciles, recompute_ok,
            int(mart["poblacion_2025"].min()), int(mart["poblacion_censada_2024"].min()),
            f"{int(mart['indicador_vulnerabilidad'].notna().sum())}/52",
        ],
    })
    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\nResumen escrito en {OUTPUT_SUMMARY.as_posix()}")


if __name__ == "__main__":
    main()
