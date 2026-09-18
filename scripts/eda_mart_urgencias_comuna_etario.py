"""EDA reproducible de `mart_urgencias_comuna_etario_monthly`.

Script de solo lectura: no modifica el mart ni genera outputs canónicos del
pipeline. Calcula las cifras citadas en
`reports/eda/eda_mart_urgencias_comuna_etario.md` y en
`reports/dictionary/diccionario_mart_urgencias_comuna_etario_monthly.md`,
y escribe una tabla resumen de apoyo en
`reports/eda/eda_mart_urgencias_comuna_etario_resumen.csv`.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_comuna_etario_mart import AGE_GROUPS
from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS
from src.data.clean_censo_comunas import EXPECTED_RM_CUTS

sys.stdout.reconfigure(encoding="utf-8")

ETARIO_PATH = Path("data/processed/marts/mart_urgencias_comuna_etario_monthly.parquet")
COMUNA_MONTHLY_PATH = Path("data/processed/marts/mart_urgencias_comuna_monthly.parquet")
OUTPUT_SUMMARY = Path("reports/eda/eda_mart_urgencias_comuna_etario_resumen.csv")


def _missing_rm_comunas(mart: pd.DataFrame) -> set[str]:
    expected = {str(cut) for cut in EXPECTED_RM_CUTS}
    return expected - set(mart["comuna_codigo"].unique())


def main() -> None:
    mart = pq.read_table(ETARIO_PATH).to_pandas()
    monthly = pq.read_table(COMUNA_MONTHLY_PATH).to_pandas()

    print("=== Forma del mart ===")
    print(f"{mart.shape[0]:,} filas x {mart.shape[1]} columnas")

    print("\n=== Cobertura ===")
    n_comunas = mart["comuna_codigo"].nunique()
    print("comunas únicas:", n_comunas)
    print("comunas RM faltantes:", sorted(_missing_rm_comunas(mart)))
    print("ano mínimo/máximo:", mart["ano"].min(), mart["ano"].max())
    print("grupos etarios presentes:", sorted(mart["grupo_etario_urgencia"].unique().tolist()))
    print("¿coincide exactamente con el contrato de 5 grupos?", set(mart["grupo_etario_urgencia"].unique()) == set(AGE_GROUPS))
    filas_por_grupo = mart.groupby("grupo_etario_urgencia").size()
    print("filas por grupo etario:\n", filas_por_grupo)

    print("\n=== Nulos en columnas de conteo ===")
    print(mart[list(COUNT_COLUMNS)].isna().sum())

    print("\n=== Totales de atenciones 2021-2025 por causa y grupo etario (ID36) ===")
    por_grupo_id36 = mart.groupby("grupo_etario_urgencia")["atenciones_id36"].sum().sort_values(ascending=False)
    print(por_grupo_id36)
    print("participación de cada grupo sobre el total ID36 2021-2025:")
    print((por_grupo_id36 / por_grupo_id36.sum() * 100).round(2))

    print("\n=== Identidad ID36 = ID37+...+ID41 por fila (grano comuna×mes×grupo_etario) ===")
    components = [f"atenciones_id{c}" for c in (37, 38, 39, 40, 41)]
    identidad_ok = (mart["atenciones_id36"] == mart[components].sum(axis=1)).all()
    print("¿se cumple en el 100% de las filas?", bool(identidad_ok))

    print("\n=== Reconciliación etario→comuna vs mart_urgencias_comuna_monthly ===")
    aggregated = mart.groupby(["comuna_codigo", "fecha_mes"], as_index=False)[
        list(COUNT_COLUMNS)
    ].sum(min_count=1)
    reference = monthly[["comuna_codigo", "fecha_mes", *COUNT_COLUMNS]]
    merged = aggregated.merge(
        reference, on=["comuna_codigo", "fecha_mes"], suffixes=("_etario", "_comuna")
    )
    reconciles = all(
        merged[f"{c}_etario"].equals(merged[f"{c}_comuna"]) for c in COUNT_COLUMNS
    )
    print(
        f"filas comuna×mes agregadas desde grupos etarios: {len(aggregated):,}; "
        f"filas de referencia en mart comunal: {len(reference):,}; "
        f"universo comuna×mes idéntico: {len(aggregated) == len(reference)}"
    )
    print("¿reconcilia exactamente por causa (ID1, ID35-41)?", reconciles)

    summary = pd.DataFrame(
        {
            "metrica": [
                "filas", "comunas_unicas", "grupos_etarios",
                "identidad_id36_por_fila_ok",
                "reconciliacion_etario_comuna_ok",
                "universo_comuna_mes_identico",
            ],
            "valor": [
                mart.shape[0], n_comunas, len(AGE_GROUPS),
                bool(identidad_ok),
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
