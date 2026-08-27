"""Script de verificación y ajuste de tipología para el reporte EDA."""

import pandas as pd
import pyarrow.parquet as pq

df_estab_rm = pd.read_parquet("data/processed/establecimientos_rm_clean.parquet")
print("Tipo de establecimiento_codigo en maestro:", type(df_estab_rm["establecimiento_codigo"].iloc[0]))
print("Muestra:", df_estab_rm["establecimiento_codigo"].head(3).tolist())

df_urg = pq.read_table("data/processed/urgencias/urgencias_rm_2024.parquet", columns=["establecimiento_codigo"]).to_pandas()
print("Tipo de establecimiento_codigo en urgencias:", type(df_urg["establecimiento_codigo"].iloc[0]))
print("Muestra:", df_urg["establecimiento_codigo"].head(3).tolist())
