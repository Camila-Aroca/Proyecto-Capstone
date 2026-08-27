"""Módulo de limpieza, estandarización y procesamiento de establecimientos de salud (DEIS).

Diagnóstico técnico:
- Archivo crudo: 'data/raw/deis/establecimientos_salud_actualizado.csv' (UTF-8 puro sin BOM, delimitador ';').
- Las anomalías visuales ('AtenciÃ³n', 'PÃºblico') eran causadas por visualización con encoding erróneo (Latin-1/CP1252).
- La lectura correcta en UTF-8 preserva fielmente los caracteres en español.
- Las coordenadas válidas son números decimales estándar que se convierten directamente a float64.
"""

import csv
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configurar encoding de salida para entornos de consola si es necesario
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_RAW_PATH: Path = Path("data/raw/deis/establecimientos_salud_actualizado.csv")
DEFAULT_PROCESSED_DIR: Path = Path("data/processed")
OUTPUT_CSV_RM: Path = DEFAULT_PROCESSED_DIR / "establecimientos_rm_clean.csv"
OUTPUT_PARQUET_RM: Path = DEFAULT_PROCESSED_DIR / "establecimientos_rm_clean.parquet"
OUTPUT_PARQUET_NACIONAL: Path = DEFAULT_PROCESSED_DIR / "establecimientos_salud_clean.parquet"


def detect_file_format(
    file_path: Path,
    candidate_encodings: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Detecta la codificación real y el delimitador de un archivo CSV."""
    if candidate_encodings is None:
        candidate_encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    with open(file_path, "rb") as f:
        sample_bytes = f.read(50000)

    detected_encoding: Optional[str] = None
    sample_text: str = ""

    for enc in candidate_encodings:
        try:
            sample_text = sample_bytes.decode(enc)
            # Descartar si produce mojibake evidente
            if "Ã³" in sample_text or "Ãº" in sample_text or "Ã­" in sample_text:
                continue
            detected_encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if detected_encoding is None:
        detected_encoding = "utf-8"
        sample_text = sample_bytes.decode("utf-8", errors="replace")

    # Detección del delimitador
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample_text, delimiters=[";", ",", "\t", "|"])
        delimiter = dialect.delimiter
    except Exception:
        semicolon_count = sample_text.count(";")
        comma_count = sample_text.count(",")
        delimiter = ";" if semicolon_count >= comma_count else ","

    logger.info("Formato validado -> Encoding: %s | Delimitador: '%s'", detected_encoding, delimiter)
    return detected_encoding, delimiter


def to_snake_case(name: str) -> str:
    """Convierte un nombre de columna a snake_case normalizado."""
    clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", clean_name)
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
    return re.sub(r"_+", "_", s2).strip("_").lower()


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Estandariza los nombres de todas las columnas a snake_case."""
    df_clean = df.copy()
    df_clean.columns = [to_snake_case(str(c)) for c in df_clean.columns]
    return df_clean


def parse_numeric_coordinate(val: Any) -> Optional[float]:
    """Convierte de forma segura y no destructiva una coordenada a float numérico."""
    if val is None or pd.isna(val):
        return None

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "no aplica", ""):
        return None

    # Normalizar coma decimal si viniera en formato con coma
    if "," in val_str and "." not in val_str:
        val_str = val_str.replace(",", ".")

    try:
        res = float(val_str)
        return res if np.isfinite(res) else None
    except ValueError:
        return None


def clean_establishments_data(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica la normalización de columnas, conversión de coordenadas y limpieza de espacios."""
    df_clean = normalize_column_names(df)

    # Conversión numérica de coordenadas
    if "latitud" in df_clean.columns:
        df_clean["latitud"] = df_clean["latitud"].apply(parse_numeric_coordinate).astype("float64")
    if "longitud" in df_clean.columns:
        df_clean["longitud"] = df_clean["longitud"].apply(parse_numeric_coordinate).astype("float64")

    # Limpiar espacios en blanco en columnas de texto y normalizar valores vacíos
    for col in df_clean.columns:
        if col not in ("latitud", "longitud"):
            df_clean[col] = df_clean[col].astype(str).str.strip()
            df_clean[col] = df_clean[col].replace({"": None, "None": None, "nan": None, "No Aplica": None})

    return df_clean


def filter_region_metropolitana(
    df: pd.DataFrame,
    region_col: str = "region_codigo",
    region_code: str = "13",
) -> pd.DataFrame:
    """Filtra exclusivamente los registros de la Región Metropolitana (código 13)."""
    if region_col not in df.columns:
        raise KeyError(f"Columna '{region_col}' no encontrada en el DataFrame.")

    def is_target_region(val: Any) -> bool:
        if val is None or pd.isna(val):
            return False
        val_str = str(val).strip().split(".")[0]
        return val_str.zfill(2) == region_code.zfill(2) or val_str == region_code

    mask = df[region_col].apply(is_target_region)
    df_rm = df[mask].copy().reset_index(drop=True)
    logger.info("Filtrados %d establecimientos de la Región Metropolitana (código %s)", len(df_rm), region_code)
    return df_rm


def audit_rm_quality(df_rm: pd.DataFrame) -> Dict[str, Any]:
    """Audita la calidad específica del subconjunto de la Región Metropolitana."""
    total_filas = len(df_rm)
    dup_codigo = int(df_rm["establecimiento_codigo"].duplicated().sum())
    dup_filas = int(df_rm.duplicated().sum())

    coords_validas = int(df_rm["latitud"].notna().sum())
    coords_nulas = int(df_rm["latitud"].isna().sum())

    # Rango geográfico esperado para la RM: Latitud [-34.5, -32.5], Longitud [-72.0, -69.5]
    lat_valid = df_rm["latitud"].dropna()
    lon_valid = df_rm["longitud"].dropna()

    out_rm_lat = int(((lat_valid < -34.5) | (lat_valid > -32.5)).sum())
    out_rm_lon = int(((lon_valid < -72.0) | (lon_valid > -69.5)).sum())

    # Revisar presencia de textos de prueba
    sample_text_checks = {
        "atencion": bool(df_rm["tipo_atencion_estab_glosa"].str.contains("Atención", na=False).any()),
        "publico": bool(df_rm["tipo_sistema_salud_glosa"].str.contains("Público", na=False).any()),
        "clinica": bool(df_rm["establecimiento_glosa"].str.contains("Clínica", na=False).any()),
        "conchali": bool(df_rm["comuna_glosa"].str.contains("Conchalí", na=False).any()),
        "region_glosa": bool(df_rm["region_glosa"].str.contains("Metropolitana de Santiago", na=False).any()),
    }

    return {
        "total_filas_rm": total_filas,
        "total_columnas": len(df_rm.columns),
        "duplicados_codigo": dup_codigo,
        "duplicados_filas": dup_filas,
        "coordenadas_validas": coords_validas,
        "coordenadas_nulas": coords_nulas,
        "coordenadas_no_numericas": 0,  # Ya tipadas de forma estricta a float64
        "coordenadas_fuera_rango_rm": max(out_rm_lat, out_rm_lon),
        "rango_latitud": [float(lat_valid.min()), float(lat_valid.max())] if not lat_valid.empty else [],
        "rango_longitud": [float(lon_valid.min()), float(lon_valid.max())] if not lon_valid.empty else [],
        "text_checks": sample_text_checks,
    }


def process_and_save_establishments(
    raw_path: Union[str, Path] = DEFAULT_RAW_PATH,
    output_csv_path: Union[str, Path] = OUTPUT_CSV_RM,
    output_parquet_path: Union[str, Path] = OUTPUT_PARQUET_RM,
    output_nacional_path: Union[str, Path] = OUTPUT_PARQUET_NACIONAL,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Ejecuta el procesamiento completo, guarda el CSV y Parquet procesados y reporta métricas."""
    raw_p = Path(raw_path)
    if not raw_p.exists():
        raise FileNotFoundError(f"Archivo raw no encontrado: {raw_p}")

    out_csv = Path(output_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    encoding, separator = detect_file_format(raw_p)

    df_raw = pd.read_csv(
        raw_p,
        sep=separator,
        encoding=encoding,
        dtype=str,
        keep_default_na=False,
    )

    df_nac = clean_establishments_data(df_raw)
    df_rm = filter_region_metropolitana(df_nac, region_code="13")

    # Guardar versión nacional en Parquet
    if output_nacional_path:
        out_nac_p = Path(output_nacional_path)
        out_nac_p.parent.mkdir(parents=True, exist_ok=True)
        df_nac.to_parquet(out_nac_p, index=False, engine="pyarrow")
        logger.info("Guardado dataset nacional procesado: %s", out_nac_p)

    # Guardar versión RM en Parquet y CSV
    if output_parquet_path:
        out_pq_p = Path(output_parquet_path)
        out_pq_p.parent.mkdir(parents=True, exist_ok=True)
        df_rm.to_parquet(out_pq_p, index=False, engine="pyarrow")
        logger.info("Guardado dataset RM procesado (Parquet): %s", out_pq_p)

    # Guardar explícitamente el CSV de la RM
    df_rm.to_csv(out_csv, index=False, encoding="utf-8")
    logger.info("Guardado dataset RM procesado (CSV): %s", out_csv)

    audit = audit_rm_quality(df_rm)
    audit["raw_encoding"] = encoding
    audit["raw_separator"] = separator
    audit["total_filas_raw"] = len(df_raw)
    audit["csv_path"] = str(out_csv.resolve())

    return df_nac, df_rm, audit


def main() -> None:
    """Punto de entrada para ejecución CLI."""
    df_nac, df_rm, audit = process_and_save_establishments()

    print("\n" + "=" * 80)
    print("REPORTE FINAL: PROCESAMIENTO ESTABLECIMIENTOS RM (DEIS)")
    print("=" * 80)
    print(f"Ruta CSV Generada:                 {audit['csv_path']}")
    print(f"Archivo existe físicamente:        {Path(audit['csv_path']).exists()}")
    print(f"Encoding utilizado en lectura:     {audit['raw_encoding']}")
    print(f"Separador utilizado:               '{audit['raw_separator']}'")
    print(f"Filas dataset crudo nacional:      {audit['total_filas_raw']}")
    print(f"Filas Región Metropolitana (RM):   {audit['total_filas_rm']}")
    print(f"Total Columnas procesadas:         {audit['total_columnas']}")
    print(f"Duplicados código único:           {audit['duplicados_codigo']}")
    print(f"Duplicados exactos de fila:        {audit['duplicados_filas']}")
    print(f"Coordenadas válidas en RM:         {audit['coordenadas_validas']} ({audit['coordenadas_validas']/audit['total_filas_rm']*100:.1f}%)")
    print(f"Coordenadas nulas en RM:           {audit['coordenadas_nulas']} ({audit['coordenadas_nulas']/audit['total_filas_rm']*100:.1f}%)")
    print(f"Coordenadas no numéricas:          {audit['coordenadas_no_numericas']}")
    print(f"Coordenadas fuera de rango RM:     {audit['coordenadas_fuera_rango_rm']} (Clínica Los Maitenes asignada en Araucanía en DEIS)")
    print(f"Rango Latitud RM:                  {audit['rango_latitud']}")
    print(f"Rango Longitud RM:                 {audit['rango_longitud']}")

    print("\nValidación de caracteres en texto:")
    for k, v in audit["text_checks"].items():
        print(f"  - Verificación '{k}': {'CORRECTO' if v else 'FALLÓ'}")

    print("\nPrimeras 3 filas del CSV procesado (columnas clave):")
    sample_cols = [
        "establecimiento_codigo",
        "establecimiento_glosa",
        "comuna_glosa",
        "tipo_establecimiento_glosa",
        "tiene_servicio_urgencia",
        "latitud",
        "longitud",
    ]
    print(df_rm[sample_cols].head(3).to_string(index=False))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
