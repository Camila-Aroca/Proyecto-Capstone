"""Script de auditoría exhaustiva de mojibake y encoding en Egresos 2024 y 2025."""

import csv
import json
from pathlib import Path
import sys
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

FILES_TO_AUDIT = [
    {"year": 2024, "path": Path("data/raw/egresos/EGR_DATOS_ABIERTO_2024.csv")},
    {"year": 2025, "path": Path("data/raw/egresos/EGR_DATOS_ABIERTO_2025.csv")},
]

HISTORICAL_FILES = [
    {"year": 2020, "path": Path("data/raw/egresos/EGRE_DATOS_ABIERTOS_2020.csv"), "enc": "latin-1"},
    {"year": 2021, "path": Path("data/raw/egresos/EGR_DATOS_ABIERTO_2021.csv"), "enc": "latin-1"},
    {"year": 2022, "path": Path("data/raw/egresos/EGRE_DATOS_ABIERTOS_2022.csv"), "enc": "latin-1"},
    {"year": 2023, "path": Path("data/raw/egresos/EGRESOS_2023.csv"), "enc": "latin-1"},
]

# Patrones típicos de mojibake (doble codificación UTF-8 -> Latin-1 -> UTF-8)
# Ejemplos: Ã¡ (á), Ã© (é), Ã­ (í), Ã³ (ó), Ãº (ú), Ã± (ñ), Ã (Á), Ã‰ (É), Ã (Í), Ã“ (Ó), Ãš (Ú), Ã‘ (Ñ), \ufffd ()
SUSPECT_PATTERNS = ["Ã", "Â", "\ufffd", "ï¿½", ""]


def audit_file(file_info):
    year = file_info["year"]
    path = file_info["path"]
    
    # 1. Comprobar bytes directamente
    with open(path, "rb") as f:
        header_bytes = f.readline()
        # Verificar primeros 10 MB de bytes
        sample_bytes = f.read(10 * 1024 * 1024)

    utf8_ok = True
    try:
        sample_bytes.decode("utf-8")
    except UnicodeDecodeError:
        utf8_ok = False

    # 2. Escaneo fila a fila con UTF-8 y con Latin-1
    # Para capturar qué caracteres aparecen bajo UTF-8
    results_by_col = defaultdict(lambda: {"count": 0, "values": Counter(), "sample_rows": []})
    total_affected_rows = set()
    total_rows = 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        
        for row_idx, row in enumerate(reader, start=2):
            total_rows += 1
            row_has_mojibake = False
            for col_idx, val in enumerate(row):
                if col_idx < len(header):
                    col_name = header[col_idx]
                    if any(p in val for p in SUSPECT_PATTERNS):
                        row_has_mojibake = True
                        results_by_col[col_name]["count"] += 1
                        results_by_col[col_name]["values"][val] += 1
                        if len(results_by_col[col_name]["sample_rows"]) < 5:
                            results_by_col[col_name]["sample_rows"].append({
                                "row_num": row_idx,
                                "val": val,
                                "row_data": dict(zip(header, row))
                            })
            if row_has_mojibake:
                total_affected_rows.add(row_idx)

    return {
        "year": year,
        "file_name": path.name,
        "total_rows": total_rows,
        "num_cols": len(header),
        "header": header,
        "utf8_byte_valid": utf8_ok,
        "total_affected_rows_count": len(total_affected_rows),
        "results_by_col": {
            k: {
                "count": v["count"],
                "distinct_values_count": len(v["values"]),
                "distinct_values": dict(v["values"].most_common(20)),
                "sample_rows": v["sample_rows"]
            }
            for k, v in results_by_col.items()
        }
    }


def main():
    print("Iniciando auditoría detallada de Egresos 2024 y 2025...")
    audit_results = {}
    for f in FILES_TO_AUDIT:
        print(f"  Auditando {f['year']} ({f['path'].name})...")
        res = audit_file(f)
        audit_results[f["year"]] = res
        print(f"    Filas totales: {res['total_rows']:,}")
        print(f"    Filas afectadas con mojibake/caracteres corruptos: {res['total_affected_rows_count']:,} ({res['total_affected_rows_count']/res['total_rows']*100:.4f}%)")
        print(f"    Columnas afectadas: {list(res['results_by_col'].keys())}")

    # Guardar reporte JSON completo
    with open("scratch/egresos_mojibake_deep.json", "w", encoding="utf-8") as out:
        json.dump(audit_results, out, indent=2, ensure_ascii=False)

    print("\nAuditoría finalizada. Guardado en scratch/egresos_mojibake_deep.json")


if __name__ == "__main__":
    main()
