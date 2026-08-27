"""Script de auditoría de causas en Atenciones de Urgencia 2020-2026."""

import json
from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

PROCESSED_DIR = Path("data/processed/urgencias")
DICT_PATH = Path("data/raw/urgencias/DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx")

# 1. Inspeccionar Diccionario Oficial DEIS
print("=== 1. INSPECCIÓN DICCIONARIO OFICIAL DEIS ===")
if DICT_PATH.exists():
    xls = pd.ExcelFile(DICT_PATH)
    print(f"Hojas en diccionario: {xls.sheet_names}")
    for sheet in xls.sheet_names:
        df_sheet = pd.read_excel(DICT_PATH, sheet_name=sheet)
        print(f"\n--- Hoja: {sheet} ({len(df_sheet)} filas, {len(df_sheet.columns)} cols) ---")
        print("Columnas:", list(df_sheet.columns))
        print(df_sheet.head(10))
else:
    print("Diccionario no encontrado en", DICT_PATH)

# 2. Inventario de causas en los 7 Parquet procesados
print("\n=== 2. INVENTARIO DE CAUSAS POR AÑO ===")
yearly_causas = {}
matrix_causas = defaultdict(lambda: {y: 0 for y in range(2020, 2027)})
matrix_causas_rows = defaultdict(lambda: {y: 0 for y in range(2020, 2027)})

all_pairs = set()

for year in range(2020, 2027):
    p = PROCESSED_DIR / f"urgencias_rm_{year}.parquet"
    df = pq.read_table(p, columns=["id_causa", "glosa_causa", "total"]).to_pandas()
    
    # Agrupar por id_causa y glosa_causa sumando total
    grp = df.groupby(["id_causa", "glosa_causa"], as_index=False).agg(
        total_atenciones=("total", "sum"),
        filas=("total", "count")
    )
    
    unique_ids = df["id_causa"].unique().tolist()
    unique_glosas = df["glosa_causa"].unique().tolist()
    null_ids = df["id_causa"].isna().sum()
    null_glosas = df["glosa_causa"].isna().sum()
    
    yearly_causas[year] = {
        "unique_ids_count": len(unique_ids),
        "unique_glosas_count": len(unique_glosas),
        "null_ids": int(null_ids),
        "null_glosas": int(null_glosas),
        "pairs": grp.to_dict(orient="records"),
        "total_atenciones_ano": int(df["total"].sum()),
    }
    
    print(f"Año {year}: {len(unique_ids)} id_causa únicos, {len(unique_glosas)} glosa_causa únicas, Total Atenciones={df['total'].sum():,}")
    
    for _, r in grp.iterrows():
        pair_key = (r["id_causa"], r["glosa_causa"])
        all_pairs.add(pair_key)
        matrix_causas[pair_key][year] = int(r["total_atenciones"])
        matrix_causas_rows[pair_key][year] = int(r["filas"])

print(f"\nTotal combinaciones únicas (id_causa, glosa_causa) en todo el período: {len(all_pairs)}")

# 3. Construir tabla comparativa
rows_matrix = []
for (id_c, glosa_c), years_dict in sorted(all_pairs, key=lambda x: x[0]):
    row = {
        "id_causa": id_c,
        "glosa_causa": glosa_c,
        **{f"atenciones_{y}": years_dict[y] for y in range(2020, 2027)},
        "total_periodo": sum(years_dict.values())
    }
    rows_matrix.append(row)

df_matrix = pd.DataFrame(rows_matrix)
print("\n=== MATRIZ DE CAUSAS 2020-2026 (ATENCIONES) ===")
print(df_matrix.to_string(index=False))

# Guardar en scratch para análisis posterior
with open("scratch/causas_urgencias_audit.json", "w", encoding="utf-8") as out:
    json.dump({
        "yearly_causas": yearly_causas,
        "matrix": rows_matrix
    }, out, indent=2, ensure_ascii=False)
