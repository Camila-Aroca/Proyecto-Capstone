import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("scratch/urgencias_mapping_stats.json", encoding="utf-8") as f:
    stats = json.load(f)

print("| Año | Filas RAW | Filas RM | Filas no RM | Sin territorio | Filas PROCESSED |")
print("|---:|---:|---:|---:|---:|---:|")
for s in stats:
    print(f"| {s['year']} | {s['raw_rows']:,} | {s['rm_rows']:,} | {s['no_rm_rows']:,} | {s['sin_territorio_rows']:,} | {s['rm_rows']:,} |")

print("\n--- DETALLE POR AÑO ---")
for s in stats:
    print(f"Año {s['year']}:")
    print(f"  RAW: {s['raw_rows']:,}")
    print(f"  RM: {s['rm_rows']:,} ({s['rm_rows']/s['raw_rows']*100:.2f}%)")
    print(f"  Establecimientos RM únicos activos en atenciones: {s['rm_estabs_count']}")
    print(f"  Nulos en ID: {s['null_id_count']}")
    print(f"  Fechas inválidas: {s['invalid_date_count']}")
    print(f"  Semanas inválidas: {s['invalid_semana_count']}")
    print(f"  Totales negativos: {s['negative_total_count']}")
    print(f"  Discrepancia suma grupos etarios vs Total: {s['age_mismatch_count']}")
