"""Analiza las causas presentes en los Parquet procesados de Urgencias RM 2020-2026."""

from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")

PROCESSED_DIR = Path("data/processed/urgencias")

all_years_data = []

for year in range(2020, 2027):
    p = PROCESSED_DIR / f"urgencias_rm_{year}.parquet"
    df = pq.read_table(p, columns=["id_causa", "glosa_causa", "total"]).to_pandas()
    
    grp = df.groupby(["id_causa", "glosa_causa"], as_index=False).agg(
        total_atenciones=("total", "sum"),
        filas=("total", "count")
    )
    grp["ano"] = year
    all_years_data.append(grp)

df_all = pd.concat(all_years_data, ignore_index=True)

# Pivot de atenciones por id_causa y glosa_causa
pivot_atenciones = df_all.pivot_table(
    index=["id_causa", "glosa_causa"],
    columns="ano",
    values="total_atenciones",
    fill_value=0
).reset_index()

# Pivot de filas
pivot_filas = df_all.pivot_table(
    index=["id_causa", "glosa_causa"],
    columns="ano",
    values="filas",
    fill_value=0
).reset_index()

pivot_atenciones["total_periodo"] = pivot_atenciones.loc[:, 2020:2026].sum(axis=1)

print("=== TABLA COMPLETA DE CAUSAS EN ATENCIONES DE URGENCIA RM (2020-2026) ===")
print(pivot_atenciones.to_string(index=False))

# Guardar catálogo consolidado en CSV
pivot_atenciones.to_csv("data/processed/urgencias/catalogo_causas_urgencias.csv", index=False, encoding="utf-8")
print("\nCatálogo guardado en data/processed/urgencias/catalogo_causas_urgencias.csv")
