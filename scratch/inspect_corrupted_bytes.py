import csv
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 1. Comprobar bytes exactos en 2024 para Maipú y Ñuñoa
p2024 = Path("data/raw/egresos/EGR_DATOS_ABIERTO_2024.csv")
with open(p2024, "rb") as f:
    for line in f:
        if b"13119" in line: # Maipú
            print("Línea cruda en bytes para comuna 13119 (Maipú) en 2024:")
            print(line[:200])
            break

# 2. Comprobar si los códigos numéricos están intactos
with open(p2024, "r", encoding="utf-8", errors="replace") as f:
    r = csv.DictReader(f, delimiter=";")
    maipu_sample = None
    nunoa_sample = None
    for row in r:
        if row["COMUNA_RESIDENCIA"] == "13119" and not maipu_sample:
            maipu_sample = row
        if row["COMUNA_RESIDENCIA"] == "13120" and not nunoa_sample:
            nunoa_sample = row
        if maipu_sample and nunoa_sample:
            break

print("\nEjemplo de registro Maipú (13119) en 2024:")
print(maipu_sample)

print("\nEjemplo de registro Ñuñoa (13120) en 2024:")
print(nunoa_sample)

# 3. Comprobar si columnas clínicas o numéricas tienen algún problema
print("\nComprobando si DIAG1, DIAG2, DIAS_ESTADA, PREVISION, SEXO tienen caracteres corruptos:")
with open(p2024, "r", encoding="utf-8", errors="replace") as f:
    r = csv.DictReader(f, delimiter=";")
    diag_corrupt = 0
    dias_corrupt = 0
    for row in r:
        if any(c in row["DIAG1"] for c in ["\ufffd", "Ã", "Â"]):
            diag_corrupt += 1
        if any(c in row["DIAS_ESTADA"] for c in ["\ufffd", "Ã", "Â"]):
            dias_corrupt += 1

print(f"DIAG1 corruptos: {diag_corrupt}")
print(f"DIAS_ESTADA corruptos: {dias_corrupt}")
