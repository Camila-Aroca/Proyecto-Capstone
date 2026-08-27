"""Script de auditoría técnica exhaustiva de formato sobre archivos RAW (Urgencias, Egresos, Censo)."""

import csv
import io
import json
from pathlib import Path
import sys
import pyarrow.parquet as pq
import pandas as pd
from shapely import wkb

# Configurar salida en UTF-8
sys.stdout.reconfigure(encoding="utf-8")


def detect_file_encoding_and_mojibake(file_path: Path, sample_size: int = 5000000) -> dict:
    """Inspecciona bytes directos del archivo para determinar codificación real y presencia de mojibake."""
    with open(file_path, "rb") as f:
        raw_bytes = f.read(sample_size)

    # 1. Comprobar BOM
    has_utf8_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    
    # 2. Comprobar validez UTF-8
    is_valid_utf8 = False
    try:
        decoded_utf8 = raw_bytes.decode("utf-8")
        is_valid_utf8 = True
    except UnicodeDecodeError:
        decoded_utf8 = None

    # 3. Comprobar validez Latin-1 / CP1252
    try:
        decoded_latin1 = raw_bytes.decode("latin-1")
    except Exception:
        decoded_latin1 = None

    # 4. Análisis de patrones de bytes para tildes
    # Patrones UTF-8 válidos: \xc3[\x80-\xbf] (ej. \xc3\xa1 = á, \xc3\xb3 = ó, \xc3\xb1 = ñ, \xc3\x8d = Í)
    # Patrones Latin-1 válidos: \xe1 = á, \xe9 = é, \xed = í, \xf3 = ó, \xfa = ú, \xf1 = ñ, \xcd = Í, \xd3 = Ó
    # Patrones Doble UTF-8 (Mojibake real en archivo): \xc3\x83, \xc3\x82, \xef\xbf\xbd (carácter de reemplazo )
    
    has_mojibake_bytes = (b"\xc3\x83" in raw_bytes) or (b"\xc3\x82" in raw_bytes) or (b"\xef\xbf\xbd" in raw_bytes)
    
    if is_valid_utf8:
        # Si es UTF-8 válido pero contiene secuencias de doble codificación
        if has_mojibake_bytes:
            real_encoding = "UTF-8 (con mojibake preexistente en origen)"
        else:
            real_encoding = "UTF-8-SIG" if has_utf8_bom else "UTF-8"
    else:
        # No es UTF-8 válido
        real_encoding = "Latin-1 / CP1252"

    return {
        "is_valid_utf8": is_valid_utf8,
        "has_utf8_bom": has_utf8_bom,
        "real_encoding": real_encoding,
        "has_mojibake_bytes": has_mojibake_bytes
    }


def audit_csv_file(file_path: Path) -> dict:
    """Audita separador, estructura de columnas, balance de campos y fechas de un CSV."""
    enc_info = detect_file_encoding_and_mojibake(file_path)
    
    # Determinar encoding para lectura
    read_encoding = "utf-8-sig" if enc_info["has_utf8_bom"] else ("utf-8" if enc_info["is_valid_utf8"] else "latin-1")

    # Detectar separador inspeccionando las primeras líneas
    with open(file_path, "r", encoding=read_encoding, errors="replace") as f:
        first_line = f.readline()
        second_line = f.readline()

    semicolon_count = first_line.count(";")
    comma_count = first_line.count(",")
    pipe_count = first_line.count("|")
    tab_count = first_line.count("\t")

    counts = {";": semicolon_count, ",": comma_count, "|": pipe_count, "\t": tab_count}
    sep = max(counts, key=counts.get)
    if counts[sep] == 0:
        sep = ";"  # fallback

    # Parsear cabecera
    header_reader = csv.reader([first_line], delimiter=sep)
    header = next(header_reader)
    expected_cols = len(header)

    # Auditar líneas y estructura completa
    line_count = 0
    mismatched_lines = 0
    mismatched_samples = []
    mojibake_in_text = False
    mojibake_sample_cols = set()

    # Detección de caracteres sospechosos en header
    for col in header:
        if any(c in col for c in ["Ã", "Â", "", "ï¿½"]):
            mojibake_in_text = True
            mojibake_sample_cols.add(col)

    # Lectura controlada de líneas completas
    date_cols_candidates = []
    for col in header:
        col_upper = col.upper()
        if any(term in col_upper for term in ["FECHA", "FEC_", "DATE", "AÑO", "MES", "DIA", "SEMANA"]):
            date_cols_candidates.append(col)

    territorial_cols = [c for c in header if any(t in c.upper() for t in ["REGION", "COMUNA", "SERVICIO", "ESTABLECIMIENTO", "COD_", "GLOSA"])]

    date_samples = {c: set() for c in date_cols_candidates}
    sample_rows = []

    with open(file_path, "r", encoding=read_encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=sep)
        try:
            actual_header = next(reader)
        except StopIteration:
            actual_header = []

        for row_idx, row in enumerate(reader, start=2):
            line_count += 1
            if len(row) != expected_cols:
                mismatched_lines += 1
                if len(mismatched_samples) < 3:
                    mismatched_samples.append((row_idx, len(row), expected_cols))

            # Muestreo de fechas y detección de mojibake en primeras 1000 filas
            if row_idx <= 1000:
                for idx_c, val in enumerate(row):
                    if idx_c < expected_cols:
                        col_name = header[idx_c]
                        if any(c in val for c in ["Ã", "Â", "", "ï¿½"]):
                            mojibake_in_text = True
                            mojibake_sample_cols.add(col_name)
                        if col_name in date_cols_candidates and len(date_samples[col_name]) < 5:
                            if val.strip():
                                date_samples[col_name].add(val.strip())
            if row_idx <= 4:
                sample_rows.append(row)

    return {
        "file_name": file_path.name,
        "file_path": file_path.as_posix(),
        "file_size_bytes": file_path.stat().st_size,
        "file_size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
        "encoding_info": enc_info,
        "read_encoding_used": read_encoding,
        "separator": sep,
        "num_rows": line_count,
        "num_cols": expected_cols,
        "columns": header,
        "mismatched_lines": mismatched_lines,
        "mismatched_samples": mismatched_samples,
        "mojibake_detected": mojibake_in_text or enc_info["has_mojibake_bytes"],
        "mojibake_columns": list(mojibake_sample_cols),
        "date_columns": date_cols_candidates,
        "date_samples": {k: list(v) for k, v in date_samples.items()},
        "territorial_columns": territorial_cols,
        "sample_rows_head": sample_rows[:2]
    }


def audit_geoparquet_file(file_path: Path) -> dict:
    """Audita archivos GeoParquet del Censo."""
    meta = pq.read_metadata(file_path)
    schema = pq.read_schema(file_path)
    table = pq.read_table(file_path)
    df = table.to_pandas()

    geo_meta_raw = schema.metadata.get(b"geo") if schema.metadata else None
    geo_meta = json.loads(geo_meta_raw.decode("utf-8")) if geo_meta_raw else {}
    primary_geom = geo_meta.get("primary_column", "SHAPE" if "SHAPE" in df.columns else "geometry")
    columns_geo = geo_meta.get("columns", {}).get(primary_geom, {})
    crs_info = columns_geo.get("crs", None)
    
    if isinstance(crs_info, dict):
        crs_str = f"{crs_info.get('name', 'Unknown')} (EPSG:{crs_info.get('id', {}).get('code', '')})"
    else:
        crs_str = str(crs_info)

    # Chequear texto en busca de mojibake o errores de decodificación
    mojibake_cols = []
    text_cols = [c for c in df.columns if df[c].dtype == "object" and c != primary_geom]
    for c in text_cols:
        sample_vals = df[c].dropna().astype(str).head(1000).tolist()
        if any(any(m in v for m in ["Ã", "Â", "", "ï¿½"]) for v in sample_vals):
            mojibake_cols.append(c)

    # Validar geometrías
    null_geom = 0
    invalid_geom = 0
    if primary_geom in df.columns:
        for wkb_b in df[primary_geom]:
            if wkb_b is None or len(wkb_b) == 0:
                null_geom += 1
                continue
            try:
                g = wkb.loads(wkb_b)
                if not g.is_valid:
                    invalid_geom += 1
            except Exception:
                invalid_geom += 1

    return {
        "file_name": file_path.name,
        "file_path": file_path.as_posix(),
        "file_size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
        "num_rows": len(df),
        "num_cols": len(df.columns),
        "columns": list(df.columns),
        "dtypes": [(c, str(df[c].dtype)) for c in df.columns],
        "crs": crs_str,
        "primary_geom_col": primary_geom,
        "null_geoms": null_geom,
        "invalid_geoms": invalid_geom,
        "mojibake_in_text": len(mojibake_cols) > 0,
        "mojibake_cols": mojibake_cols
    }


def main():
    urgencias_dir = Path("data/raw/urgencias")
    egresos_dir = Path("data/raw/egresos")
    censo_dir = Path("data/raw/censo")

    urgencias_csvs = sorted(urgencias_dir.glob("AtencionesUrgencia*.csv"))
    egresos_csvs = sorted(egresos_dir.glob("*.csv"))
    censo_comunal = censo_dir / "Cartografia_censo2024_Pais_Comunal.parquet"

    print("Iniciando auditoría técnica de Atenciones de Urgencia...")
    urg_results = []
    for csv_file in urgencias_csvs:
        print(f"  Auditando: {csv_file.name}")
        res = audit_csv_file(csv_file)
        urg_results.append(res)

    print("\nIniciando auditoría técnica de Egresos Hospitalarios...")
    egr_results = []
    for csv_file in egresos_csvs:
        print(f"  Auditando: {csv_file.name}")
        res = audit_csv_file(csv_file)
        egr_results.append(res)

    print("\nIniciando auditoría técnica de Cartografía Censo 2024...")
    censo_result = audit_geoparquet_file(censo_comunal)

    audit_data = {
        "urgencias": urg_results,
        "egresos": egr_results,
        "censo_comunal": censo_result
    }

    with open("scratch/raw_format_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)

    print("\nAuditoría finalizada. Resultados guardados en scratch/raw_format_audit_results.json")


if __name__ == "__main__":
    main()
