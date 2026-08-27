"""Módulo para procesar y filtrar la cartografía comunal del Censo 2024 para la Región Metropolitana."""

import json
from pathlib import Path
from typing import Any, Dict

import pyarrow.compute as pc
import pyarrow.parquet as pq
from shapely import wkb

RAW_CENSO_COMUNAL = Path("data/raw/censo/Cartografia_censo2024_Pais_Comunal.parquet")
PROCESSED_DIR = Path("data/processed/censo")
PROCESSED_CENSO_RM_COMUNAL = PROCESSED_DIR / "Cartografia_censo2024_RM_Comunal.parquet"

EXPECTED_RM_CUTS = {
    13101, 13102, 13103, 13104, 13105, 13106, 13107, 13108, 13109, 13110,
    13111, 13112, 13113, 13114, 13115, 13116, 13117, 13118, 13119, 13120,
    13121, 13122, 13123, 13124, 13125, 13126, 13127, 13128, 13129, 13130,
    13131, 13132, 13201, 13202, 13203, 13301, 13302, 13303, 13401, 13402,
    13403, 13404, 13501, 13502, 13503, 13504, 13505, 13601, 13602, 13603,
    13604, 13605,
}


def process_censo_comunal_rm(
    raw_path: Path = RAW_CENSO_COMUNAL,
    output_path: Path = PROCESSED_CENSO_RM_COMUNAL,
) -> Dict[str, Any]:
    """Lee la cartografía comunal nacional, filtra para la RM (COD_REGION=13) y guarda como GeoParquet."""
    if not raw_path.exists():
        raise FileNotFoundError(f"No existe el archivo raw: {raw_path.as_posix()}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Leer tabla GeoParquet preservando schema y metadata geoespacial
    table = pq.read_table(raw_path)
    
    # 2. Filtrar exclusivamente Región Metropolitana (COD_REGION == 13)
    mask = pc.equal(table["COD_REGION"], 13)
    table_rm = table.filter(mask)

    if table_rm.num_rows != 52:
        raise ValueError(f"Se esperaban 52 comunas para la RM, pero se obtuvieron {table_rm.num_rows}")

    # 3. Escribir GeoParquet procesado manteniendo schema original y metadata
    pq.write_table(table_rm, output_path)

    # 4. Validación exhaustiva releyendo el archivo generado
    table_verify = pq.read_table(output_path)
    df_verify = table_verify.to_pandas()

    num_rows = len(df_verify)
    unique_cuts = set(df_verify["CUT"])
    unique_comunas = df_verify["COMUNA"].nunique()
    cod_reg_unique = df_verify["COD_REGION"].unique().tolist()
    
    dup_cut_count = int(df_verify["CUT"].duplicated().sum())
    null_geom_count = int(df_verify["SHAPE"].isna().sum())

    # Validar integridad topológica de las geometrías WKB
    invalid_geom_count = 0
    for wkb_bytes in df_verify["SHAPE"]:
        if wkb_bytes is None or len(wkb_bytes) == 0:
            continue
        try:
            geom = wkb.loads(wkb_bytes)
            if not geom.is_valid:
                invalid_geom_count += 1
        except Exception:
            invalid_geom_count += 1

    # Extraer CRS de metadata
    geo_meta_raw = table_verify.schema.metadata.get(b"geo") if table_verify.schema.metadata else None
    if geo_meta_raw:
        geo_meta = json.loads(geo_meta_raw.decode("utf-8"))
        crs_info = geo_meta.get("columns", {}).get("SHAPE", {}).get("crs", {})
        crs_name = crs_info.get("name", "Unknown") if isinstance(crs_info, dict) else str(crs_info)
        crs_code = crs_info.get("id", {}).get("code", "") if isinstance(crs_info, dict) else ""
        crs_str = f"{crs_name} (EPSG:{crs_code})" if crs_code else crs_name
    else:
        crs_str = "No detectado"

    all_52_present = (unique_cuts == EXPECTED_RM_CUTS) and (num_rows == 52)

    return {
        "archivo_generado": output_path.as_posix(),
        "filas": num_rows,
        "comunas_unicas": unique_comunas,
        "estan_52_comunas": all_52_present,
        "cod_region_unico": cod_reg_unique == [13],
        "crs": crs_str,
        "geometrias_nulas": null_geom_count,
        "geometrias_invalidas": invalid_geom_count,
        "duplicados_cut": dup_cut_count,
        "validacion_exitosa": all_52_present and (invalid_geom_count == 0) and (dup_cut_count == 0),
    }


def main() -> None:
    """Función de ejecución CLI."""
    res = process_censo_comunal_rm()
    print("Procesamiento y validación completados:")
    print(f"Archivo generado: {res['archivo_generado']}")
    print(f"Filas: {res['filas']}")
    print(f"Comunas únicas: {res['comunas_unicas']}")
    print(f"¿Están las 52 comunas?: {'Sí' if res['estan_52_comunas'] else 'No'}")
    print(f"CRS: {res['crs']}")
    print(f"Geometrías inválidas: {res['geometrias_invalidas']}")
    print(f"Duplicados CUT: {res['duplicados_cut']}")
    print(f"Estado de validación: {'APROBADO' if res['validacion_exitosa'] else 'RECHAZADO'}")


if __name__ == "__main__":
    main()
