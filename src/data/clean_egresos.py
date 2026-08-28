"""Módulo de normalización reproducible para Egresos Hospitalarios DEIS (2020-2025)."""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_EGRESOS_DIR = Path("data/raw/egresos")
PROCESSED_EGRESOS_DIR = Path("data/processed/egresos")

YEAR_CONFIG = {
    2020: {"file": "EGRE_DATOS_ABIERTOS_2020.csv", "encoding": "latin-1"},
    2021: {"file": "EGR_DATOS_ABIERTO_2021.csv", "encoding": "latin-1"},
    2022: {"file": "EGRE_DATOS_ABIERTOS_2022.csv", "encoding": "latin-1"},
    2023: {"file": "EGRESOS_2023.csv", "encoding": "latin-1"},
    2024: {"file": "EGR_DATOS_ABIERTO_2024.csv", "encoding": "utf-8"},
    2025: {"file": "EGR_DATOS_ABIERTO_2025.csv", "encoding": "utf-8"},
}

SCHEMA_PARQUET = pa.schema([
    ("pertenencia_establecimiento_salud", pa.string()),
    ("sexo", pa.string()),
    ("grupo_edad", pa.string()),
    ("etnia", pa.string()),
    ("glosa_pais_origen", pa.string()),
    ("comuna_residencia", pa.int32()),
    ("glosa_comuna_residencia", pa.string()),
    ("region_residencia", pa.int32()),
    ("glosa_region_residencia", pa.string()),
    ("prevision", pa.int32()),
    ("glosa_prevision", pa.string()),
    ("ano_egreso", pa.int32()),
    ("diag1", pa.string()), # Diagnóstico Principal
    ("diag2", pa.string()), # Causa Externa
    ("dias_estada", pa.int32()),
    ("condicion_egreso", pa.int32()),
    ("interv_q", pa.int32()),
    ("proced", pa.int32()),
    ("error", pa.int32()),
])

def try_int(val: str, default: Any = None) -> Any:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

def process_egresos_year(year: int, chunk_size: int = 250000) -> Dict[str, Any]:
    """Procesa, normaliza y exporta a parquet un año de Egresos Hospitalarios."""
    if year not in YEAR_CONFIG:
        raise ValueError(f"Año {year} no configurado.")
    
    config = YEAR_CONFIG[year]
    raw_file = RAW_EGRESOS_DIR / config["file"]
    
    if not raw_file.exists():
        raise FileNotFoundError(f"Archivo raw no encontrado: {raw_file.as_posix()}")
        
    PROCESSED_EGRESOS_DIR.mkdir(parents=True, exist_ok=True)
    output_parquet = PROCESSED_EGRESOS_DIR / f"egresos_{year}.parquet"
    
    total_raw = 0
    temp_parquet = PROCESSED_EGRESOS_DIR / f"egresos_{year}.parquet.tmp"
    writer = pq.ParquetWriter(temp_parquet, schema=SCHEMA_PARQUET, compression="snappy")
    rows_buffer = []

    try:
        with open(raw_file, "r", encoding=config["encoding"]) as f:
            reader = csv.DictReader(f, delimiter=";")
            
            for row in reader:
                total_raw += 1
                
                # Truncation fix for 2024-2025
                pert_est = row.get("PERTENENCIA_ESTABLECIMIENTO_SALUD")
                if pert_est is None and "PERTENENCIA_ESTABLECIMIENTO_SALU" in row:
                    pert_est = row.get("PERTENENCIA_ESTABLECIMIENTO_SALU")
                
                # Handling territorial codes
                comuna_res = try_int(row.get("COMUNA_RESIDENCIA"), default=None)
                region_res = try_int(row.get("REGION_RESIDENCIA"), default=None)
                prev_num = try_int(row.get("PREVISION"), default=None)
                dias_est = try_int(row.get("DIAS_ESTADA"), default=None)
                cond_egr = try_int(row.get("CONDICION_EGRESO"), default=None)
                int_q = try_int(row.get("INTERV_Q"), default=None) if "INTERV_Q" in row else None
                proced = try_int(row.get("PROCED"), default=None) if "PROCED" in row else None
                error_flag = try_int(row.get("ERROR"), default=None) if "ERROR" in row else None
                
                ano = try_int(row.get("ANO_EGRESO"), default=year)
    
                proc_row = {
                    "pertenencia_establecimiento_salud": str(pert_est).strip() if pert_est else "",
                    "sexo": str(row.get("SEXO", "")).strip(),
                    "grupo_edad": str(row.get("GRUPO_EDAD", "")).strip(),
                    "etnia": str(row.get("ETNIA", "")).strip(),
                    "glosa_pais_origen": str(row.get("GLOSA_PAIS_ORIGEN", "")).strip(),
                    "comuna_residencia": comuna_res,
                    "glosa_comuna_residencia": str(row.get("GLOSA_COMUNA_RESIDENCIA", "")).strip(),
                    "region_residencia": region_res,
                    "glosa_region_residencia": str(row.get("GLOSA_REGION_RESIDENCIA", "")).strip(),
                    "prevision": prev_num,
                    "glosa_prevision": str(row.get("GLOSA_PREVISION", "")).strip(),
                    "ano_egreso": ano,
                    "diag1": str(row.get("DIAG1", "")).strip(),
                    "diag2": str(row.get("DIAG2", "")).strip(),
                    "dias_estada": dias_est,
                    "condicion_egreso": cond_egr,
                    "interv_q": int_q,
                    "proced": proced,
                    "error": error_flag,
                }
                
                rows_buffer.append(proc_row)
                
                if len(rows_buffer) >= chunk_size:
                    batch_df = pd.DataFrame(rows_buffer)
                    batch_table = pa.Table.from_pandas(batch_df, schema=SCHEMA_PARQUET, preserve_index=False)
                    writer.write_table(batch_table)
                    rows_buffer = []

        if rows_buffer:
            batch_df = pd.DataFrame(rows_buffer)
            batch_table = pa.Table.from_pandas(batch_df, schema=SCHEMA_PARQUET, preserve_index=False)
            writer.write_table(batch_table)

        writer.close()
        temp_parquet.replace(output_parquet)
    except Exception as e:
        writer.close()
        if temp_parquet.exists():
            temp_parquet.unlink()
        raise e
    
    return {
        "year": year,
        "processed_file": output_parquet.as_posix(),
        "total_rows": total_raw,
    }

def run_full_normalization() -> List[Dict[str, Any]]:
    """Ejecuta la normalización completa 2020-2025."""
    results = []
    for year in range(2020, 2026):
        logger.info(f"Normalizando Egresos {year}...")
        try:
            res = process_egresos_year(year)
            results.append(res)
            logger.info(f"  Completado {year}: {res['total_rows']:,} filas.")
        except FileNotFoundError as e:
            logger.warning(f"  Omitiendo {year}: {e}")
    return results

def main():
    logger.info("Iniciando normalización de Egresos Hospitalarios...")
    results = run_full_normalization()
    logger.info("Proceso finalizado exitosamente.")

if __name__ == "__main__":
    main()
