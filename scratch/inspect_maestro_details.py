"""Script para inspección detallada de variables administrativas y de red en el maestro y egresos."""

import csv
from pathlib import Path
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ESTAB_RM_CSV = Path("data/processed/establecimientos_rm_clean.csv")
ESTAB_RAW_CSV = Path("data/raw/deis/establecimientos_salud_actualizado.csv")
EGRESOS_2024_CSV = Path("data/raw/egresos/EGR_DATOS_ABIERTO_2024.csv")

# 1. Columnas en establecimientos_rm_clean.csv
df_rm = pd.read_csv(ESTAB_RM_CSV, dtype=str)
print("=== COLUMNAS EN data/processed/establecimientos_rm_clean.csv ===")
print(df_rm.columns.tolist())
print(df_rm.head(2).T)

# 2. Columnas en RAW deis/establecimientos_salud_actualizado.csv
print("\n=== COLUMNAS EN data/raw/deis/establecimientos_salud_actualizado.csv ===")
df_raw = pd.read_csv(ESTAB_RAW_CSV, sep=";", encoding="utf-8", dtype=str)
print(df_raw.columns.tolist())
print("\nValores únicos de 'DependenciaAdministrativa' en RAW:")
print(df_raw["DependenciaAdministrativa"].value_counts())

# 3. Inspeccionar si hay alguna columna de Servicio de Salud o Dependencia en RAW
print("\nBúsqueda de 'Servicio' o 'Red' o 'Dependencia' en columnas RAW:")
for col in df_raw.columns:
    if any(k in col.lower() for k in ["serv", "red", "depen", "hosp", "ref", "pert"]):
        print(f"Columna: {col} -> Valores únicos: {df_raw[col].nunique()} -> Muestra: {df_raw[col].dropna().unique()[:5]}")

# 4. Valores de PERTENENCIA_ESTABLECIMIENTO_SALU en Egresos 2024
print("\n=== VALORES DE PERTENENCIA EN EGRESOS 2024 ===")
df_egr = pd.read_csv(EGRESOS_2024_CSV, sep=";", encoding="utf-8", nrows=10000, dtype=str)
print(df_egr["PERTENENCIA_ESTABLECIMIENTO_SALU"].value_counts())
