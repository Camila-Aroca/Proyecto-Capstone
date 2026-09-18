"""Módulo para procesar y filtrar la cartografía Censo 2024 (comunal y subcomunal) para la RM.

La capa Comunal (`process_censo_comunal_rm`) es la implementación histórica del
proyecto. Las capas subcomunales (Distrital, Zonal, Entidades, Manzanas) amplían
este mismo módulo en lugar de duplicarlo, reutilizando `EXPECTED_RM_CUTS` y los
mismos criterios de validación (dominio territorial, llave sin duplicados,
geometría legible, CRS preservado). Cada capa tiene su propio grano y llave:
CUT (Comunal), ID_DISTRITO (Distrital), ID_ZONA (Zonal) y MANZENT (Entidades,
Manzanas). No todas las capas subcomunales cubren las 52 comunas RM: Zonal es
exclusivamente urbana (falta San Pedro, 13505, sin zonas urbanas) y Entidades es
exclusivamente rural dispersa (ausente en comunas totalmente urbanizadas), lo
cual es un hecho observado de la fuente y no un error de filtrado.
"""

import os
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import shapely
from shapely import wkb

RAW_DIR = Path("data/raw/censo")
PROCESSED_DIR = Path("data/processed/censo")

RAW_CENSO_COMUNAL = RAW_DIR / "Cartografia_censo2024_Pais_Comunal.parquet"
RAW_CENSO_DISTRITAL = RAW_DIR / "Cartografia_censo2024_Pais_Distrital.parquet"
RAW_CENSO_ZONAL = RAW_DIR / "Cartografia_censo2024_Pais_Zonal.parquet"
RAW_CENSO_ENTIDADES = RAW_DIR / "Cartografia_censo2024_Pais_Entidades.parquet"
RAW_CENSO_MANZANAS = RAW_DIR / "Cartografia_censo2024_Pais_Manzanas.parquet"

PROCESSED_CENSO_RM_COMUNAL = PROCESSED_DIR / "Cartografia_censo2024_RM_Comunal.parquet"
PROCESSED_CENSO_RM_DISTRITAL = PROCESSED_DIR / "Cartografia_censo2024_RM_Distrital.parquet"
PROCESSED_CENSO_RM_ZONAL = PROCESSED_DIR / "Cartografia_censo2024_RM_Zonal.parquet"
PROCESSED_CENSO_RM_ENTIDADES = PROCESSED_DIR / "Cartografia_censo2024_RM_Entidades.parquet"
PROCESSED_CENSO_RM_MANZANAS = PROCESSED_DIR / "Cartografia_censo2024_RM_Manzanas.parquet"

REGION_RM = 13
DEMOGRAFIA_COLUMNS = ("n_per", "n_hombres", "n_mujeres")

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


def _read_rm_table(raw_path: Path) -> pa.Table:
    """Lee únicamente las filas RM (COD_REGION=13) vía predicate pushdown."""
    if not raw_path.exists():
        raise FileNotFoundError(f"No existe el archivo raw: {raw_path.as_posix()}")
    return pq.read_table(raw_path, filters=[("COD_REGION", "=", REGION_RM)])


def _extract_crs(table: pa.Table, geometry_column: str = "SHAPE") -> str:
    geo_meta_raw = table.schema.metadata.get(b"geo") if table.schema.metadata else None
    if not geo_meta_raw:
        return "No detectado"
    geo_meta = json.loads(geo_meta_raw.decode("utf-8"))
    crs_info = geo_meta.get("columns", {}).get(geometry_column, {}).get("crs", {})
    if not isinstance(crs_info, dict):
        return str(crs_info) if crs_info else "No detectado"
    crs_name = crs_info.get("name", "Unknown")
    crs_code = crs_info.get("id", {}).get("code", "")
    return f"{crs_name} (EPSG:{crs_code})" if crs_code else crs_name


def _validate_geometries(geometry_column: pa.ChunkedArray) -> tuple[int, int]:
    """Valida nulidad e integridad topológica de forma vectorizada (shapely 2.x)."""
    wkb_values = geometry_column.to_pylist()
    null_count = sum(1 for value in wkb_values if not value)
    non_null = [value for value in wkb_values if value]
    if not non_null:
        return null_count, 0
    geoms = shapely.from_wkb(non_null)
    invalid_count = int((~shapely.is_valid(geoms)).sum())
    return null_count, invalid_count


def _validate_key(table: pa.Table, key_column: str) -> tuple[int, int]:
    """Devuelve (nulos, duplicados) de la llave dentro del grano ya filtrado a RM."""
    values = table[key_column].to_pylist()
    null_count = sum(1 for value in values if value is None)
    non_null = [value for value in values if value is not None]
    dup_count = len(non_null) - len(set(non_null))
    return null_count, dup_count


def _validate_demografia(table: pa.Table) -> Dict[str, Any]:
    """Valida no negatividad; reporta (sin exigir) la igualdad n_hombres+n_mujeres=n_per."""
    negativos = {}
    for column in DEMOGRAFIA_COLUMNS:
        if column not in table.column_names:
            continue
        valores = pc.fill_null(table[column], 0)
        negativos[column] = int(pc.sum(pc.less(valores, 0)).as_py() or 0)

    equidad_inconsistente = 0
    if all(column in table.column_names for column in DEMOGRAFIA_COLUMNS):
        n_per = table["n_per"].to_pylist()
        n_hombres = table["n_hombres"].to_pylist()
        n_mujeres = table["n_mujeres"].to_pylist()
        for total, hombres, mujeres in zip(n_per, n_hombres, n_mujeres):
            if total is None:
                continue
            if hombres is None or mujeres is None or (hombres + mujeres) != total:
                equidad_inconsistente += 1
    return {"negativos": negativos, "equidad_sexo_inconsistente": equidad_inconsistente}


def _write_atomic(table: pa.Table, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.parent / f".{output_path.name}.tmp"
    try:
        pq.write_table(table, temp_path)
        verify = pq.read_table(temp_path)
        if verify.num_rows != table.num_rows:
            raise ValueError(f"Relectura post-escritura no coincide en filas para {output_path.name}.")
        del verify
        # En Windows, un lector de disco (antivirus/indexador) puede retener
        # brevemente un lock exclusivo sobre el .tmp recién escrito; reintentar
        # el reemplazo atómico evita fallos espurios sin afectar la atomicidad.
        last_error: OSError | None = None
        for attempt in range(5):
            try:
                os.replace(temp_path, output_path)
                last_error = None
                break
            except PermissionError as error:
                last_error = error
                time.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            raise last_error
    finally:
        temp_path.unlink(missing_ok=True)


def process_censo_subcomunal_rm(
    layer_name: str,
    raw_path: Path,
    output_path: Path,
    *,
    key_column: str,
    expect_full_52: bool,
    distrito_ids_rm: Optional[set] = None,
) -> Dict[str, Any]:
    """Filtra una capa subcomunal del Censo 2024 a RM y publica su GeoParquet.

    No asume que la capa cubre las 52 comunas RM (`expect_full_52=False` permite
    capas parciales por construcción, como Zonal o Entidades) ni que
    n_hombres+n_mujeres=n_per (se reporta la inconsistencia, no se corrige).
    """
    table = _read_rm_table(raw_path)
    num_rows = table.num_rows
    if num_rows == 0:
        raise ValueError(f"Capa {layer_name}: el filtro RM (COD_REGION=13) no produjo filas.")

    cuts = {cut for cut in table["CUT"].to_pylist() if cut is not None}
    fuera_de_dominio = cuts - EXPECTED_RM_CUTS
    if fuera_de_dominio:
        raise ValueError(f"Capa {layer_name}: CUT fuera del dominio RM: {sorted(fuera_de_dominio)}")
    if expect_full_52 and cuts != EXPECTED_RM_CUTS:
        faltantes = EXPECTED_RM_CUTS - cuts
        raise ValueError(f"Capa {layer_name}: faltan comunas RM esperadas: {sorted(faltantes)}")

    key_nulls, key_dups = _validate_key(table, key_column)
    if key_nulls:
        raise ValueError(f"Capa {layer_name}: llave {key_column} con {key_nulls} valor(es) nulo(s).")
    if key_dups:
        raise ValueError(f"Capa {layer_name}: llave {key_column} con {key_dups} duplicado(s) en el grano RM.")

    geom_nulls, geom_invalid = _validate_geometries(table["SHAPE"])

    jerarquia_huerfanos: Optional[list] = None
    if distrito_ids_rm is not None and "ID_DISTRITO" in table.column_names:
        distritos_usados = {value for value in table["ID_DISTRITO"].to_pylist() if value is not None}
        huerfanos = sorted(distritos_usados - distrito_ids_rm)
        jerarquia_huerfanos = huerfanos
        if huerfanos:
            raise ValueError(f"Capa {layer_name}: ID_DISTRITO sin distrito RM válido: {huerfanos[:10]}")

    demografia = None
    if any(column in table.column_names for column in DEMOGRAFIA_COLUMNS):
        demografia = _validate_demografia(table)
        negativos_detectados = {c: v for c, v in demografia["negativos"].items() if v}
        if negativos_detectados:
            raise ValueError(f"Capa {layer_name}: variables demográficas negativas: {negativos_detectados}")

    crs = _extract_crs(table)
    _write_atomic(table, output_path)

    return {
        "capa": layer_name,
        "archivo_generado": output_path.as_posix(),
        "filas": num_rows,
        "comunas_representadas": len(cuts),
        "todas_las_52_comunas": cuts == EXPECTED_RM_CUTS,
        "crs": crs,
        "geometrias_nulas": geom_nulls,
        "geometrias_invalidas": geom_invalid,
        "duplicados_llave": key_dups,
        "jerarquia_distrital_huerfanos": jerarquia_huerfanos,
        "demografia": demografia,
        "validacion_exitosa": geom_nulls == 0 and geom_invalid == 0 and key_dups == 0,
    }


def _rm_distrito_ids(raw_path: Path = RAW_CENSO_DISTRITAL) -> set:
    """Extrae el conjunto de ID_DISTRITO válidos en RM, para validar jerarquía en capas hijas."""
    table = _read_rm_table(raw_path)
    return {value for value in table["ID_DISTRITO"].to_pylist() if value is not None}


def process_censo_distrital_rm(
    raw_path: Path = RAW_CENSO_DISTRITAL,
    output_path: Path = PROCESSED_CENSO_RM_DISTRITAL,
) -> Dict[str, Any]:
    """Filtra la capa Distrital (sin variables demográficas) a RM."""
    return process_censo_subcomunal_rm(
        "Distrital", raw_path, output_path, key_column="ID_DISTRITO", expect_full_52=True,
    )


def process_censo_zonal_rm(
    raw_path: Path = RAW_CENSO_ZONAL,
    output_path: Path = PROCESSED_CENSO_RM_ZONAL,
    *,
    distrito_ids_rm: Optional[set] = None,
) -> Dict[str, Any]:
    """Filtra la capa Zonal (urbana, con demografía) a RM. No cubre 13505 (sin zonas urbanas)."""
    return process_censo_subcomunal_rm(
        "Zonal", raw_path, output_path, key_column="ID_ZONA", expect_full_52=False,
        distrito_ids_rm=distrito_ids_rm if distrito_ids_rm is not None else _rm_distrito_ids(),
    )


def process_censo_entidades_rm(
    raw_path: Path = RAW_CENSO_ENTIDADES,
    output_path: Path = PROCESSED_CENSO_RM_ENTIDADES,
    *,
    distrito_ids_rm: Optional[set] = None,
) -> Dict[str, Any]:
    """Filtra la capa Entidades (rural dispersa, con demografía) a RM.

    Cubre solo las comunas RM con población rural registrada como entidad
    (no incluye Aldeas, que se publican dentro de la capa Manzanas).
    """
    return process_censo_subcomunal_rm(
        "Entidades", raw_path, output_path, key_column="MANZENT", expect_full_52=False,
        distrito_ids_rm=distrito_ids_rm if distrito_ids_rm is not None else _rm_distrito_ids(),
    )


def process_censo_manzanas_rm(
    raw_path: Path = RAW_CENSO_MANZANAS,
    output_path: Path = PROCESSED_CENSO_RM_MANZANAS,
    *,
    distrito_ids_rm: Optional[set] = None,
) -> Dict[str, Any]:
    """Filtra la capa Manzanas (urbana + Aldeas rurales, con demografía) a RM.

    Incluye manzanas con `MZ_BASE_CENSO=0` (sin datos tabulados, `n_per=0`); no se
    imputan ni se excluyen, ya que no es posible determinar con esta fuente si
    corresponden a manzanas efectivamente deshabitadas o a supresión estadística.
    """
    return process_censo_subcomunal_rm(
        "Manzanas", raw_path, output_path, key_column="MANZENT", expect_full_52=True,
        distrito_ids_rm=distrito_ids_rm if distrito_ids_rm is not None else _rm_distrito_ids(),
    )


def process_censo_cartografia_rm() -> Dict[str, Dict[str, Any]]:
    """Ejecuta las 5 capas (Comunal + subcomunal) en un único punto de entrada del stage."""
    resultados = {"Comunal": process_censo_comunal_rm()}
    resultados["Distrital"] = process_censo_distrital_rm()
    distrito_ids_rm = _rm_distrito_ids()
    resultados["Zonal"] = process_censo_zonal_rm(distrito_ids_rm=distrito_ids_rm)
    resultados["Entidades"] = process_censo_entidades_rm(distrito_ids_rm=distrito_ids_rm)
    resultados["Manzanas"] = process_censo_manzanas_rm(distrito_ids_rm=distrito_ids_rm)
    return resultados


def main() -> None:
    """Función de ejecución CLI: procesa las 5 capas de cartografía Censo 2024 para RM."""
    resultados = process_censo_cartografia_rm()
    for nombre, res in resultados.items():
        print(f"--- {nombre} ---")
        print(f"Archivo generado: {res['archivo_generado']}")
        print(f"Filas: {res['filas']}")
        if "comunas_unicas" in res:
            print(f"Comunas únicas: {res['comunas_unicas']}")
            print(f"¿Están las 52 comunas?: {'Sí' if res['estan_52_comunas'] else 'No'}")
        else:
            print(f"Comunas representadas: {res['comunas_representadas']} (¿52/52?: {'Sí' if res['todas_las_52_comunas'] else 'No'})")
        print(f"CRS: {res['crs']}")
        print(f"Geometrías inválidas: {res['geometrias_invalidas']}")
        print(f"Estado de validación: {'APROBADO' if res['validacion_exitosa'] else 'RECHAZADO'}")


if __name__ == "__main__":
    main()
