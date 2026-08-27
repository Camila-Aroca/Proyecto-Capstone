"""Script de auditoría post-normalización para Atenciones de Urgencia 2020-2026."""

import csv
import json
from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = Path("data/raw/urgencias")
PROCESSED_DIR = Path("data/processed/urgencias")
ESTAB_RM_PATH = Path("data/processed/establecimientos_rm_clean.csv")

# 1. Auditar duplicados en catálogo de establecimientos RM (por código antiguo)
df_estab_rm = pd.read_csv(ESTAB_RM_PATH, dtype=str)
print("=== 1. AUDITORÍA DEL CATÁLOGO DE ESTABLECIMIENTOS RM ===")
print(f"Total filas catálogo RM: {len(df_estab_rm)}")
cod_antiguo_counts = df_estab_rm["establecimiento_codigo_antiguo"].dropna().value_counts()
dups_antiguo = cod_antiguo_counts[cod_antiguo_counts > 1]
print(f"Códigos antiguos duplicados en catálogo RM: {len(dups_antiguo)}")
if len(dups_antiguo) > 0:
    print(dups_antiguo)

# 2. Conteo directo de filas RAW CSV vs PROCESSED Parquet
print("\n=== 2. CONTEO REAL DE FILAS POR AÑO ===")
counts_by_year = {}

for year in range(2020, 2027):
    raw_csv = RAW_DIR / f"AtencionesUrgencia{year}.csv"
    proc_parquet = PROCESSED_DIR / f"urgencias_rm_{year}.parquet"
    
    # Contar filas RAW directamente
    raw_rows = 0
    with open(raw_csv, "r", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        for _ in reader:
            raw_rows += 1
            
    # Contar filas Parquet
    p_table = pq.read_table(proc_parquet)
    proc_rows = p_table.num_rows
    
    counts_by_year[year] = {
        "raw_rows_real": raw_rows,
        "proc_rows_real": proc_rows,
        "raw_cols": len(header),
        "proc_cols": p_table.num_columns,
        "proc_schema": {name: str(t) for name, t in zip(p_table.schema.names, p_table.schema.types)}
    }
    print(f"Año {year}: RAW={raw_rows:,} | PROCESSED={proc_rows:,} | RAW Cols={len(header)} | PROCESSED Cols={p_table.num_columns}")

total_raw_sum = sum(v["raw_rows_real"] for v in counts_by_year.values())
total_proc_sum = sum(v["proc_rows_real"] for v in counts_by_year.values())
print(f"\nTOTAL NACIONAL RAW (2020-2026): {total_raw_sum:,}")
print(f"TOTAL RM PROCESSED (2020-2026): {total_proc_sum:,}")

# 3. Validación detallada de calidad y consistencia en los Parquets procesados
print("\n=== 3. AUDITORÍA DE VALORES Y CALIDAD EN PROCESSED ===")
quality_by_year = {}

for year in range(2020, 2027):
    proc_parquet = PROCESSED_DIR / f"urgencias_rm_{year}.parquet"
    df = pq.read_table(proc_parquet).to_pandas()
    
    # Nulos
    null_estab_cod = df["establecimiento_codigo"].isna().sum()
    null_comuna_cod = df["comuna_codigo"].isna().sum()
    null_region_cod = df["region_codigo"].isna().sum()
    null_fecha = df["fecha"].isna().sum()
    null_id_causa = df["id_causa"].isna().sum()
    
    # Rango y valores negativos
    neg_total = (df["total"] < 0).sum()
    neg_edades = (
        (df["menores_1"] < 0) | (df["de_1_a_4"] < 0) | (df["de_5_a_14"] < 0) |
        (df["de_15_a_64"] < 0) | (df["de_65_y_mas"] < 0)
    ).sum()
    
    # Semanas fuera de rango
    invalid_semana = ((df["semana"] < 1) | (df["semana"] > 53)).sum()
    
    # Fechas inválidas (formato DD/MM/YYYY)
    invalid_fechas = (~df["fecha"].str.match(r"^\d{2}/\d{2}/\d{4}$")).sum()
    
    # Inconsistencia suma edades vs total
    suma_edades = df["menores_1"] + df["de_1_a_4"] + df["de_5_a_14"] + df["de_15_a_64"] + df["de_65_y_mas"]
    diff_total = (df["total"] != suma_edades).sum()
    
    # Region unica
    regions = df["region_codigo"].unique().tolist()
    
    # Comunas unicas
    comunas_unicas = df["comuna_codigo"].dropna().unique().tolist()
    
    # Duplicados exactos en todas las columnas
    exact_duplicates = df.duplicated().sum()
    
    # Duplicados en llave natural (fecha, establecimiento_codigo, id_causa, tipo_atencion_urgencia, tipo_campana, tipo_establecimiento_urgencia)
    key_cols = ["fecha", "establecimiento_codigo", "id_causa", "tipo_atencion_urgencia", "tipo_campana", "tipo_establecimiento_urgencia"]
    key_duplicates = df.duplicated(subset=key_cols).sum()
    
    quality_by_year[year] = {
        "null_estab_cod": int(null_estab_cod),
        "null_comuna_cod": int(null_comuna_cod),
        "null_region_cod": int(null_region_cod),
        "null_fecha": int(null_fecha),
        "null_id_causa": int(null_id_causa),
        "neg_total": int(neg_total),
        "neg_edades": int(neg_edades),
        "invalid_semana": int(invalid_semana),
        "invalid_fechas": int(invalid_fechas),
        "diff_total": int(diff_total),
        "regions": regions,
        "num_comunas": len(comunas_unicas),
        "exact_duplicates": int(exact_duplicates),
        "key_duplicates": int(key_duplicates),
    }
    
    print(f"Año {year}:")
    print(f"  Nulos (estab, com, reg, fec, causa): ({null_estab_cod}, {null_comuna_cod}, {null_region_cod}, {null_fecha}, {null_id_causa})")
    print(f"  Negativos (total, edades): ({neg_total}, {neg_edades})")
    print(f"  Inválidos (semana, fechas): ({invalid_semana}, {invalid_fechas})")
    print(f"  Discrepancia Total vs Suma Edades: {diff_total}")
    print(f"  Regiones: {regions} | Comunas únicas: {len(comunas_unicas)}")
    print(f"  Duplicados exactos: {exact_duplicates} | Duplicados llave: {key_duplicates}")

with open("scratch/urgencias_post_normalization_audit.json", "w", encoding="utf-8") as out:
    json.dump({
        "counts_by_year": counts_by_year,
        "quality_by_year": quality_by_year,
    }, out, indent=2, ensure_ascii=False)

print("\nAuditoría guardada en scratch/urgencias_post_normalization_audit.json")
