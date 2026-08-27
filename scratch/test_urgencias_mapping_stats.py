"""Script para calcular estadísticas completas de mapeo y retención de Atenciones de Urgencia 2020-2026."""

import csv
import json
from pathlib import Path
import sys
import pandas as pd
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

# Cargar catálogo de establecimientos RM
df_estab_rm = pd.read_csv("data/processed/establecimientos_rm_clean.csv", dtype=str)
df_estab_nac = pd.read_parquet("data/processed/establecimientos_salud_clean.parquet")

# Diccionarios de búsqueda rápida para RM
rm_by_antiguo = {}
rm_by_nuevo = {}
for idx, r in df_estab_rm.iterrows():
    cod_nuevo = str(r["establecimiento_codigo"]).strip()
    cod_antiguo = str(r["establecimiento_codigo_antiguo"]).strip() if pd.notna(r["establecimiento_codigo_antiguo"]) else None
    
    info = {
        "establecimiento_codigo": int(cod_nuevo),
        "establecimiento_glosa": r["establecimiento_glosa"],
        "region_codigo": 13,
        "region_glosa": "Metropolitana de Santiago",
        "comuna_codigo": str(r["comuna_codigo"]).strip(),
        "comuna_glosa": r["comuna_glosa"],
        "tipo_establecimiento_glosa": r["tipo_establecimiento_glosa"],
        "ambito_funcionamiento": r["ambito_funcionamiento"],
        "latitud": float(r["latitud"]) if pd.notna(r["latitud"]) else None,
        "longitud": float(r["longitud"]) if pd.notna(r["longitud"]) else None,
    }
    rm_by_nuevo[cod_nuevo] = info
    if cod_antiguo and cod_antiguo != "nan":
        rm_by_antiguo[cod_antiguo] = info

# Diccionarios de búsqueda rápida para Nacional (para determinar si un no-RM pertenece a otra región)
nac_by_antiguo = {}
nac_by_nuevo = {}
for idx, r in df_estab_nac.iterrows():
    cod_nuevo = str(r["establecimiento_codigo"]).strip()
    cod_antiguo = str(r["establecimiento_codigo_antiguo"]).strip() if pd.notna(r["establecimiento_codigo_antiguo"]) else None
    reg_cod = int(str(r["region_codigo"]).split(".")[0]) if pd.notna(r["region_codigo"]) else None
    
    info = {
        "establecimiento_codigo": int(cod_nuevo) if cod_nuevo.isdigit() else cod_nuevo,
        "region_codigo": reg_cod,
        "comuna_codigo": str(r["comuna_codigo"]).strip() if pd.notna(r["comuna_codigo"]) else None,
    }
    nac_by_nuevo[cod_nuevo] = info
    if cod_antiguo and cod_antiguo != "None" and cod_antiguo != "nan":
        nac_by_antiguo[cod_antiguo] = info

print(f"Catálogo RM: {len(rm_by_nuevo)} códigos nuevos, {len(rm_by_antiguo)} códigos antiguos")
print(f"Catálogo Nacional: {len(nac_by_nuevo)} códigos nuevos, {len(nac_by_antiguo)} códigos antiguos")

urg_dir = Path("data/raw/urgencias")
yearly_stats = []

for year in range(2020, 2027):
    p = urg_dir / f"AtencionesUrgencia{year}.csv"
    if not p.exists():
        continue
    
    print(f"\nProcesando {p.name}...")
    total_raw = 0
    total_rm = 0
    total_no_rm = 0
    total_sin_territorio = 0
    
    # Chequeos de calidad
    null_id_count = 0
    invalid_date_count = 0
    invalid_semana_count = 0
    negative_total_count = 0
    age_mismatch_count = 0
    
    # Establecimientos no encontrados en catálogo RM ni Nacional
    unmapped_estabs = Counter()
    rm_estabs_found = Counter()
    
    date_min = None
    date_max = None
    
    with open(p, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f, delimiter=";")
        header = reader.fieldnames
        has_region_col = "CodigoRegion" in header
        
        for row in reader:
            total_raw += 1
            id_estab = str(row.get("IdEstablecimiento", "")).strip()
            
            if not id_estab or id_estab == "nan":
                null_id_count += 1
                
            # Mapeo a RM
            is_rm = False
            is_known_non_rm = False
            estab_info = None
            
            # 1. Búsqueda directa en catálogo RM
            if id_estab in rm_by_antiguo:
                is_rm = True
                estab_info = rm_by_antiguo[id_estab]
            elif id_estab in rm_by_nuevo:
                is_rm = True
                estab_info = rm_by_nuevo[id_estab]
            elif has_region_col:
                # Verificar columna CodigoRegion en 2023-2026
                cod_reg = str(row.get("CodigoRegion", "")).strip().split(".")[0]
                if cod_reg in ["13", "013"]:
                    is_rm = True
                elif cod_reg != "" and cod_reg not in ["13", "013"]:
                    is_known_non_rm = True
            
            if not is_rm and not is_known_non_rm:
                # Comprobar si está en catálogo nacional en otra región
                if id_estab in nac_by_antiguo:
                    if nac_by_antiguo[id_estab]["region_codigo"] == 13:
                        is_rm = True
                    else:
                        is_known_non_rm = True
                elif id_estab in nac_by_nuevo:
                    if nac_by_nuevo[id_estab]["region_codigo"] == 13:
                        is_rm = True
                    else:
                        is_known_non_rm = True
                        
            if is_rm:
                total_rm += 1
                rm_estabs_found[id_estab] += 1
            elif is_known_non_rm:
                total_no_rm += 1
            else:
                total_sin_territorio += 1
                unmapped_estabs[id_estab] += 1
                
            # Validación de calidad básica
            fec = str(row.get("fecha", "")).strip()
            if len(fec) != 10 or fec[2] != "/" or fec[5] != "/":
                invalid_date_count += 1
            else:
                if date_min is None or fec < date_min:
                    date_min = fec
                if date_max is None or fec > date_max:
                    date_max = fec
                    
            try:
                sem = int(row.get("semana", -1))
                if sem < 1 or sem > 53:
                    invalid_semana_count += 1
            except ValueError:
                invalid_semana_count += 1
                
            try:
                tot = int(row.get("Total", 0))
                if tot < 0:
                    negative_total_count += 1
                
                # Comprobar suma de grupos etarios
                m1 = int(row.get("Menores_1", 0) or 0)
                d1_4 = int(row.get("De_1_a_4", 0) or 0)
                d5_14 = int(row.get("De_5_a_14", 0) or 0)
                d15_64 = int(row.get("De_15_a_64", 0) or 0)
                d65 = int(row.get("De_65_y_mas", 0) or 0)
                if (m1 + d1_4 + d5_14 + d15_64 + d65) != tot:
                    age_mismatch_count += 1
            except ValueError:
                pass

    stat = {
        "year": year,
        "raw_rows": total_raw,
        "rm_rows": total_rm,
        "no_rm_rows": total_no_rm,
        "sin_territorio_rows": total_sin_territorio,
        "rm_estabs_count": len(rm_estabs_found),
        "unmapped_estabs_count": len(unmapped_estabs),
        "unmapped_estabs_top": unmapped_estabs.most_common(10),
        "null_id_count": null_id_count,
        "invalid_date_count": invalid_date_count,
        "invalid_semana_count": invalid_semana_count,
        "negative_total_count": negative_total_count,
        "age_mismatch_count": age_mismatch_count,
    }
    yearly_stats.append(stat)
    print(f"  Año {year}: RAW={total_raw:,} | RM={total_rm:,} ({total_rm/total_raw*100:.2f}%) | No-RM={total_no_rm:,} | Sin Territorio={total_sin_territorio:,} | Unmapped Estabs={len(unmapped_estabs)}")

with open("scratch/urgencias_mapping_stats.json", "w", encoding="utf-8") as out:
    json.dump(yearly_stats, out, indent=2, ensure_ascii=False)

print("\nEstadísticas guardadas en scratch/urgencias_mapping_stats.json")
