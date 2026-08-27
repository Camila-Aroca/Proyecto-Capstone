"""Script exploratorio para homologación territorial de Urgencias 2020-2026."""

import csv
import json
from pathlib import Path
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# Cargar catálogo de establecimientos RM y Nacional
estab_rm = pd.read_csv("data/processed/establecimientos_rm_clean.csv", dtype=str)
print(f"Establecimientos RM cargados: {len(estab_rm)} filas")
print("Columnas clave en catálogo RM:")
print("  - establecimiento_codigo:", estab_rm["establecimiento_codigo"].head(3).tolist())
print("  - establecimiento_codigo_antiguo:", estab_rm["establecimiento_codigo_antiguo"].head(3).tolist())

# Crear sets y diccionarios de mapeo para RM
rm_codigos_nuevos = set(estab_rm["establecimiento_codigo"].str.strip())
rm_codigos_antiguos = set(estab_rm["establecimiento_codigo_antiguo"].dropna().str.strip())

# Mapeo a comuna y región
map_rm_by_nuevo = estab_rm.set_index("establecimiento_codigo").to_dict("index")
map_rm_by_antiguo = estab_rm.dropna(subset=["establecimiento_codigo_antiguo"]).set_index("establecimiento_codigo_antiguo").to_dict("index")

print(f"Total códigos nuevos RM: {len(rm_codigos_nuevos)}")
print(f"Total códigos antiguos RM: {len(rm_codigos_antiguos)}")

# Cargar catálogo nacional para verificar establecimientos no-RM
estab_nac = pd.read_parquet("data/processed/establecimientos_salud_clean.parquet")
nac_codigos_nuevos = set(estab_nac["establecimiento_codigo"].astype(str).str.strip())
nac_codigos_antiguos = set(estab_nac["establecimiento_codigo_antiguo"].dropna().astype(str).str.strip())
print(f"Total establecimientos nacionales: {len(estab_nac)}")

# Inspeccionar cada año de urgencias
urg_dir = Path("data/raw/urgencias")
for year in range(2020, 2027):
    p = urg_dir / f"AtencionesUrgencia{year}.csv"
    if not p.exists():
        continue
    
    # Muestreo de las primeras 50,000 filas para inspección rápida
    df_sample = pd.read_csv(p, sep=";", encoding="latin-1", nrows=10000, dtype=str)
    id_estab_sample = df_sample["IdEstablecimiento"].dropna().str.strip().unique()
    
    # Revisar formato de IdEstablecimiento
    has_hyphen = any("-" in str(x) for x in id_estab_sample)
    
    print(f"\n=== AÑO {year} ===")
    print(f"  Columnas ({len(df_sample.columns)}): {list(df_sample.columns)}")
    print(f"  Muestra IdEstablecimiento: {id_estab_sample[:5]}")
    print(f"  ¿Formato con guion (antiguo)?: {has_hyphen}")
    
    if "CodigoRegion" in df_sample.columns:
        reg_unique = df_sample["CodigoRegion"].unique()
        print(f"  CodigoRegion únicos (muestra): {reg_unique}")
