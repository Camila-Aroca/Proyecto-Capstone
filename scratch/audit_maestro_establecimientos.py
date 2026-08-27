"""Script de auditoría exhaustiva del maestro de establecimientos y relaciones asistenciales/territoriales."""

import csv
import json
from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

ESTAB_RM_CSV = Path("data/processed/establecimientos_rm_clean.csv")
ESTAB_RAW_CSV = Path("data/raw/deis/establecimientos_salud_actualizado.csv")
ESTAB_NAC_PARQUET = Path("data/processed/establecimientos_salud_clean.parquet")
URGENCIAS_DIR = Path("data/processed/urgencias")
EGRESOS_DIR = Path("data/raw/egresos")

# 1. Auditoría del Maestro RM Procesado
print("=== 1. AUDITORÍA DEL MAESTRO RM PROCESADO ===")
df_rm = pd.read_csv(ESTAB_RM_CSV, dtype=str)
print(f"Filas: {len(df_rm)} | Columnas: {len(df_rm.columns)}")
print("Columnas exactas:", list(df_rm.columns))
print("\nTipos, Nulos y Únicos en Maestro RM:")
for col in df_rm.columns:
    nulls = df_rm[col].isna().sum()
    uniques = df_rm[col].nunique()
    print(f"  - {col}: Nulos={nulls} ({nulls/len(df_rm)*100:.1f}%), Únicos={uniques}, Muestra={df_rm[col].dropna().head(3).tolist()}")

# 2. Inspección del archivo RAW original de DEIS
print("\n=== 2. INSPECCIÓN DEL ARCHIVO RAW ORIGINAL DEIS ===")
if ESTAB_RAW_CSV.exists():
    df_raw = pd.read_csv(ESTAB_RAW_CSV, sep=";", encoding="utf-8", dtype=str)
    print(f"Filas RAW Nacional: {len(df_raw)} | Columnas RAW: {len(df_raw.columns)}")
    print("Columnas RAW exactas:", list(df_raw.columns))
    # Muestra de columnas administrativas
    print("\nMuestra de valores en RAW:")
    for col in df_raw.columns:
        print(f"  - RAW '{col}': Nulos={df_raw[col].isna().sum()}, Únicos={df_raw[col].nunique()}, Top={df_raw[col].value_counts().head(2).to_dict()}")

# 3. Tipos de establecimientos en la RM
print("\n=== 3. TIPOS DE ESTABLECIMIENTOS EN MAESTRO RM ===")
tipo_counts = df_rm["tipo_establecimiento_glosa"].value_counts()
print(tipo_counts)

# Identificar Hospitales, SAPU, SAR, CESFAM
hosp_mask = df_rm["tipo_establecimiento_glosa"].str.contains("Hospital|Clínica|Instituto", case=False, na=False)
sapu_mask = df_rm["tipo_establecimiento_glosa"].str.contains("SAPU", case=False, na=False)
sar_mask = df_rm["tipo_establecimiento_glosa"].str.contains("SAR", case=False, na=False)
cesfam_mask = df_rm["tipo_establecimiento_glosa"].str.contains("CESFAM|Centro de Salud Familiar", case=False, na=False)

print(f"\nTotal Hospitales / Clínicas / Institutos en RM: {hosp_mask.sum()}")
print(f"Total SAPU en RM: {sapu_mask.sum()}")
print(f"Total SAR en RM: {sar_mask.sum()}")
print(f"Total CESFAM en RM: {cesfam_mask.sum()}")

# 4. Auditoría de Coordenadas en Maestro RM
print("\n=== 4. AUDITORÍA DE COORDENADAS EN MAESTRO RM ===")
lat_valid = df_rm["latitud"].dropna()
lon_valid = df_rm["longitud"].dropna()
print(f"Establecimientos con coordenadas válidas: {len(lat_valid)} de {len(df_rm)} ({len(lat_valid)/len(df_rm)*100:.2f}%)")
print(f"Establecimientos sin coordenadas: {len(df_rm) - len(lat_valid)}")
# Duplicados por coordenadas
coord_dups = df_rm.dropna(subset=["latitud", "longitud"]).duplicated(subset=["latitud", "longitud"], keep=False).sum()
print(f"Establecimientos que comparten coordenadas exactas: {coord_dups}")

# 5. Cruce Maestro RM con Atenciones de Urgencia 2020-2026
print("\n=== 5. CRUCE MAESTRO RM CON ATENCIONES DE URGENCIA ===")
estab_rm_nuevos = set(df_rm["establecimiento_codigo"].astype(str).str.strip())
estab_rm_antiguos = set(df_rm["establecimiento_codigo_antiguo"].dropna().astype(str).str.strip())
map_rm_info = df_rm.set_index("establecimiento_codigo").to_dict("index")

urg_coverage = []
for year in range(2020, 2027):
    p = URGENCIAS_DIR / f"urgencias_rm_{year}.parquet"
    df_urg = pq.read_table(p, columns=["establecimiento_codigo", "establecimiento_codigo_antiguo", "latitud", "longitud"]).to_pandas()
    
    unique_cods = df_urg["establecimiento_codigo"].astype(str).unique()
    unique_antiguos = df_urg["establecimiento_codigo_antiguo"].dropna().astype(str).unique()
    
    found_in_master = [c for c in unique_cods if c in estab_rm_nuevos]
    not_found = [c for c in unique_cods if c not in estab_rm_nuevos]
    
    with_coords = df_urg.dropna(subset=["latitud", "longitud"])["establecimiento_codigo"].astype(str).unique()
    without_coords = [c for c in unique_cods if c not in with_coords]
    
    urg_coverage.append({
        "year": year,
        "unique_estabs": len(unique_cods),
        "found_in_master": len(found_in_master),
        "not_found": len(not_found),
        "coverage_pct": round(len(found_in_master) / len(unique_cods) * 100, 2),
        "with_coords_count": len(with_coords),
        "without_coords_count": len(without_coords),
        "without_coords_sample": without_coords[:5]
    })
    print(f"Año {year}: Únicos={len(unique_cods)} | Encontrados={len(found_in_master)} | Cobertura={len(found_in_master)/len(unique_cods)*100:.1f}% | Con Coords={len(with_coords)} | Sin Coords={len(without_coords)}")

# 6. Inspección de Egresos Hospitalarios (Identificadores de Establecimiento)
print("\n=== 6. INSPECCIÓN DE IDENTIFICADORES EN EGRESOS HOSPITALARIOS ===")
for year in range(2020, 2026):
    egr_files = list(EGRESOS_DIR.glob(f"*{year}*.csv"))
    if not egr_files:
        continue
    egr_p = egr_files[0]
    with open(egr_p, "r", encoding="latin-1", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        sample_row = next(reader)
    print(f"\nEgresos {year} ({egr_p.name}):")
    print("  Columnas:", header)
    print("  ¿Existe ESTABLECIMIENTO_CODIGO?:", any("ESTAB" in c.upper() and "COD" in c.upper() for c in header))
    print("  ¿Existe ID_ESTABLECIMIENTO?:", any("ID" in c.upper() and "ESTAB" in c.upper() for c in header))
    print("  ¿Existe NOMBRE_ESTABLECIMIENTO?:", any("NOM" in c.upper() and "ESTAB" in c.upper() for c in header))
    print("  Columnas relacionadas con establecimiento:", [c for c in header if "ESTAB" in c.upper() or "HOSP" in c.upper()])

# Guardar resultados en scratch
with open("scratch/maestro_establecimientos_audit.json", "w", encoding="utf-8") as out:
    json.dump({
        "urg_coverage": urg_coverage,
    }, out, indent=2, ensure_ascii=False)
