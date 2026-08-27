"""Inspecciona todas las causas de urgencias y su relación matemática y conceptual."""

from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")

df_causas = pd.read_csv("data/processed/urgencias/catalogo_causas_urgencias.csv")
print("=== CATÁLOGO COMPLETO DE CAUSAS DE URGENCIA ===")
for idx, r in df_causas.iterrows():
    print(f"ID {r['id_causa']:2d} | {r['glosa_causa']} | Total Periodo: {r['total_periodo']:,}")

# Verificar la relación de suma interna para trastornos mentales por año
print("\n=== ANÁLISIS DE CONSISTENCIA DE TRASTORNOS MENTALES (F00-F99) ===")
PROCESSED_DIR = Path("data/processed/urgencias")

for year in range(2020, 2027):
    p = PROCESSED_DIR / f"urgencias_rm_{year}.parquet"
    df = pq.read_table(p, columns=["id_causa", "glosa_causa", "total"]).to_pandas()
    
    tot_by_id = df.groupby("id_causa")["total"].sum().to_dict()
    
    c36 = tot_by_id.get(36, 0) # Total Trastornos Mentales
    c38 = tot_by_id.get(38, 0) # F10-F19 Sustancias
    c39 = tot_by_id.get(39, 0) # F30-F39 Humor
    c40 = tot_by_id.get(40, 0) # F40-F48 Neuroticos/Estres
    c41 = tot_by_id.get(41, 0) # Otros trastornos
    
    suma_componentes_f = c38 + c39 + c40 + c41
    diff_f = c36 - suma_componentes_f
    
    c35 = tot_by_id.get(35, 0) # X60-X84 Lesiones autoinfligidas
    c37 = tot_by_id.get(37, 0) # R45.8 Ideacion suicida
    c42 = tot_by_id.get(42, 0) # Hospitalizaciones por trastornos mentales
    
    print(f"\nAño {year}:")
    print(f"  ID 36 (Total F00-F99): {c36:,}")
    print(f"  ID 38 (F10-F19 Sustancias): {c38:,}")
    print(f"  ID 39 (F30-F39 Afectivos): {c39:,}")
    print(f"  ID 40 (F40-F48 Estrés/Ansiedad): {c40:,}")
    print(f"  ID 41 (Otros trastornos): {c41:,}")
    print(f"  Suma (38 + 39 + 40 + 41): {suma_componentes_f:,} (Diferencia vs ID 36 = {diff_f:,})")
    print(f"  ID 37 (R45.8 Ideación Suicida): {c37:,}")
    print(f"  ID 35 (X60-X84 Lesiones Autoinfligidas): {c35:,}")
    print(f"  ID 42 (Hosp. Trastornos Mentales): {c42:,}")

