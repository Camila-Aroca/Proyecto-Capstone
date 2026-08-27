import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("scratch/raw_format_audit_results.json", encoding="utf-8") as f:
    audit = json.load(f)

print("="*80)
print("1. ATENCIONES DE URGENCIA (2020-2026)")
print("="*80)
for u in audit["urgencias"]:
    print(f"Archivo: {u['file_name']}")
    print(f"  Tamaño: {u['file_size_mb']} MB ({u['file_size_bytes']:,} bytes)")
    print(f"  Filas: {u['num_rows']:,} | Columnas: {u['num_cols']}")
    print(f"  Encoding real: {u['encoding_info']['real_encoding']} (BOM: {u['encoding_info']['has_utf8_bom']})")
    print(f"  Separador: '{u['separator']}'")
    print(f"  Filas con campos desiguales: {u['mismatched_lines']}")
    print(f"  Mojibake en texto: {u['mojibake_detected']} (Cols: {u['mojibake_columns']})")
    print(f"  Columnas fechas: {u['date_columns']} -> Muestras: {u['date_samples']}")
    print(f"  Primeras 5 columnas: {u['columns'][:5]}")
    print()

print("="*80)
print("2. EGRESOS HOSPITALARIOS (2020-2025)")
print("="*80)
for e in audit["egresos"]:
    print(f"Archivo: {e['file_name']}")
    print(f"  Tamaño: {e['file_size_mb']} MB ({e['file_size_bytes']:,} bytes)")
    print(f"  Filas: {e['num_rows']:,} | Columnas: {e['num_cols']}")
    print(f"  Encoding real: {e['encoding_info']['real_encoding']} (BOM: {e['encoding_info']['has_utf8_bom']})")
    print(f"  Separador: '{e['separator']}'")
    print(f"  Filas con campos desiguales: {e['mismatched_lines']}")
    print(f"  Mojibake en texto: {e['mojibake_detected']} (Cols: {e['mojibake_columns']})")
    print(f"  Columnas fechas: {e['date_columns']} -> Muestras: {e['date_samples']}")
    print(f"  Primeras 5 columnas: {e['columns'][:5]}")
    print()

print("="*80)
print("3. CARTOGRAFIA CENSO 2024")
print("="*80)
c = audit["censo_comunal"]
print(f"Archivo: {c['file_name']}")
print(f"  Tamaño: {c['file_size_mb']} MB | Filas: {c['num_rows']:,} | Columnas: {c['num_cols']}")
print(f"  CRS: {c['crs']} | Columna geométrica: {c['primary_geom_col']}")
print(f"  Geometrías nulas: {c['null_geoms']} | Inválidas: {c['invalid_geoms']}")
print(f"  Mojibake en texto: {c['mojibake_in_text']} (Cols: {c['mojibake_cols']})")
