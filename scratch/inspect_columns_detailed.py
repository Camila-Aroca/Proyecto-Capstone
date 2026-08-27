import csv
import json
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

urgencias_dir = Path("data/raw/urgencias")
egresos_dir = Path("data/raw/egresos")

print("=== COLUMNAS ATENCIONES DE URGENCIA ===")
for p in sorted(urgencias_dir.glob("AtencionesUrgencia*.csv")):
    with open(p, "r", encoding="latin-1") as f:
        r = csv.reader(f, delimiter=";")
        header = next(r)
        first_row = next(r)
        print(f"\n[{p.name}] - {len(header)} columnas:")
        for col_name, sample_val in zip(header, first_row):
            print(f"  - {col_name}: ej. '{sample_val}'")

print("\n=== COLUMNAS EGRESOS HOSPITALARIOS ===")
for p in sorted(egresos_dir.glob("*.csv")):
    enc = "utf-8" if "2024" in p.name or "2025" in p.name else "latin-1"
    with open(p, "r", encoding=enc, errors="replace") as f:
        r = csv.reader(f, delimiter=";")
        header = next(r)
        first_row = next(r)
        print(f"\n[{p.name}] (enc: {enc}) - {len(header)} columnas:")
        for col_name, sample_val in zip(header, first_row):
            print(f"  - {col_name}: ej. '{sample_val}'")
