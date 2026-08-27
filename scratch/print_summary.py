import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

with open("scratch/deis_ingest_summary.json", encoding="utf-8") as f:
    s = json.load(f)

print("### Atenciones de Urgencia\n")
print("| Año | ZIP | Datos extraídos | Diccionario | Nombre del diccionario |")
print("|---:|---|---|---|---|")
for u in s["urgencias"]:
    datos_str = ", ".join(u["datos"])
    print(f"| {u['year']} | `{u['zip']}` | `{datos_str}` | {u['tiene_diccionario']} | {u['nombre_diccionario']} |")

print("\n### Egresos Hospitalarios\n")
print("| Año | ZIP | Datos extraídos | Diccionario | Nombre del diccionario |")
print("|---:|---|---|---|---|")
for e in s["egresos"]:
    datos_str = ", ".join(e["datos"])
    dict_name = f"`{e['nombre_diccionario']}`" if e["tiene_diccionario"] == "Sí" else e["nombre_diccionario"]
    print(f"| {e['year']} | `{e['zip']}` | `{datos_str}` | {e['tiene_diccionario']} | {dict_name} |")

print("\n--- DETALLES ADICIONALES ---")
print(f"Ruta RAW urgencias: data/raw/urgencias/")
print(f"Ruta RAW egresos: data/raw/egresos/")
print("Egresos 2026: NO DISPONIBLE")
