"""Normalización territorial de Urgencias DEIS desde 2020 hasta el año Chile actual."""

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.chile_time import current_year_chile
from src.data.raw_provenance import RAW_SHA256_METADATA_KEY, file_sha256

RAW_URGENCIAS_DIR = Path("data/raw/urgencias")
PROCESSED_URGENCIAS_DIR = Path("data/processed/urgencias")
ESTABLECIMIENTOS_RM_PATH = Path("data/processed/establecimientos_rm_clean.csv")
ESTABLECIMIENTOS_NAC_PATH = Path("data/processed/establecimientos_salud_clean.parquet")
REPORTS_DIR = Path("reports")
REPORT_MD_PATH = REPORTS_DIR / "eda" / "eda_urgencias_normalizacion.md"
SUPPORTED_YEARS = tuple(range(2020, current_year_chile() + 1))
OUTPUT_SCHEMA = pa.schema([
    ("fecha", pa.string()),
    ("ano", pa.int32()),
    ("semana", pa.int32()),
    ("establecimiento_codigo", pa.int64()),
    ("establecimiento_codigo_antiguo", pa.string()),
    ("establecimiento_glosa", pa.string()),
    ("region_codigo", pa.int32()),
    ("region_glosa", pa.string()),
    ("comuna_codigo", pa.string()),
    ("comuna_glosa", pa.string()),
    ("tipo_establecimiento_glosa", pa.string()),
    ("tipo_establecimiento_urgencia", pa.string()),
    ("tipo_atencion_urgencia", pa.string()),
    ("tipo_campana", pa.string()),
    ("id_causa", pa.int32()),
    ("glosa_causa", pa.string()),
    ("total", pa.int32()),
    ("menores_1", pa.int32()),
    ("de_1_a_4", pa.int32()),
    ("de_5_a_14", pa.int32()),
    ("de_15_a_64", pa.int32()),
    ("de_65_y_mas", pa.int32()),
    ("latitud", pa.float64()),
    ("longitud", pa.float64()),
])


def fecha_bounds_urgencias(values: pd.Series) -> tuple[str, str]:
    """Extremos cronológicos de fechas DEIS publicadas como DD/MM/YYYY."""
    dates = pd.to_datetime(values.drop_duplicates(), format="%d/%m/%Y", errors="raise")
    if dates.empty:
        raise ValueError("No hay fechas de Urgencias para el inventario.")
    return dates.min().strftime("%d/%m/%Y"), dates.max().strftime("%d/%m/%Y")

COLUMN_MAPPING_RAW_TO_SNAKE = {
    "IdEstablecimiento": "id_establecimiento_raw",
    "NEstablecimiento": "nombre_establecimiento_raw",
    "IdCausa": "id_causa",
    "GlosaCausa": "glosa_causa",
    "Total": "total",
    "Menores_1": "menores_1",
    "De_1_a_4": "de_1_a_4",
    "De_5_a_14": "de_5_a_14",
    "De_15_a_64": "de_15_a_64",
    "De_65_y_mas": "de_65_y_mas",
    "fecha": "fecha",
    "semana": "semana",
    "GLOSATIPOESTABLECIMIENTO": "tipo_establecimiento_urgencia_raw",
    "GLOSATIPOATENCION": "tipo_atencion_urgencia_raw",
    "GlosaTipoCampana": "tipo_campana_raw",
    "CodigoRegion": "codigo_region_raw",
    "NombreRegion": "nombre_region_raw",
    "CodigoDependencia": "codigo_dependencia_raw",
    "NombreDependencia": "nombre_dependencia_raw",
    "CodigoComuna": "codigo_comuna_raw",
    "NombreComuna": "nombre_comuna_raw",
}


def load_establishment_catalogs():
    """Carga los catálogos de establecimientos RM y Nacional para mapeo unívoco."""
    df_rm = pd.read_csv(ESTABLECIMIENTOS_RM_PATH, dtype=str)
    df_nac = pd.read_parquet(ESTABLECIMIENTOS_NAC_PATH)

    rm_by_antiguo = {}
    rm_by_nuevo = {}

    for _, r in df_rm.iterrows():
        cod_nuevo = str(r["establecimiento_codigo"]).strip()
        cod_antiguo = str(r["establecimiento_codigo_antiguo"]).strip() if pd.notna(r["establecimiento_codigo_antiguo"]) else None
        
        info = {
            "establecimiento_codigo": int(cod_nuevo),
            "establecimiento_codigo_antiguo": cod_antiguo if cod_antiguo and cod_antiguo != "nan" else None,
            "establecimiento_glosa": r["establecimiento_glosa"],
            "region_codigo": 13,
            "region_glosa": "Metropolitana de Santiago",
            "comuna_codigo": str(r["comuna_codigo"]).strip(),
            "comuna_glosa": r["comuna_glosa"],
            "tipo_establecimiento_glosa": r["tipo_establecimiento_glosa"],
            "ambito_funcionamiento": r["ambito_funcionamiento"],
            "latitud": float(r["latitud"]) if pd.notna(r["latitud"]) else None,
            "longitud": float(r["longitud"]) if pd.notna(r["longitud"]) else None,
        }
        rm_by_nuevo[cod_nuevo] = info
        if cod_antiguo and cod_antiguo != "nan":
            rm_by_antiguo[cod_antiguo] = info

    nac_by_antiguo = {}
    nac_by_nuevo = {}
    for _, r in df_nac.iterrows():
        cod_nuevo = str(r["establecimiento_codigo"]).strip()
        cod_antiguo = str(r["establecimiento_codigo_antiguo"]).strip() if pd.notna(r["establecimiento_codigo_antiguo"]) else None
        reg_cod = int(str(r["region_codigo"]).split(".")[0]) if pd.notna(r["region_codigo"]) else None

        info = {
            "establecimiento_codigo": int(cod_nuevo) if cod_nuevo.isdigit() else cod_nuevo,
            "region_codigo": reg_cod,
            "comuna_codigo": str(r["comuna_codigo"]).strip() if pd.notna(r["comuna_codigo"]) else None,
        }
        nac_by_nuevo[cod_nuevo] = info
        if cod_antiguo and cod_antiguo != "None" and cod_antiguo != "nan":
            nac_by_antiguo[cod_antiguo] = info

    return rm_by_antiguo, rm_by_nuevo, nac_by_antiguo, nac_by_nuevo


def process_urgencias_year(
    year: int,
    rm_by_antiguo: dict,
    rm_by_nuevo: dict,
    nac_by_antiguo: dict,
    nac_by_nuevo: dict,
    raw_dir: Path = RAW_URGENCIAS_DIR,
    output_dir: Path = PROCESSED_URGENCIAS_DIR,
    chunk_size: int = 250000
) -> Dict[str, Any]:
    """Procesa, normaliza y filtra un año de Atenciones de Urgencia para la RM."""
    raw_file = raw_dir / f"AtencionesUrgencia{year}.csv"
    if not raw_file.exists():
        raise FileNotFoundError(f"Archivo raw no encontrado: {raw_file.as_posix()}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_parquet = output_dir / f"urgencias_rm_{year}.parquet"

    total_raw = 0
    total_rm = 0
    total_no_rm = 0
    total_sin_territorio = 0
    rm_estabs_set = set()
    # Controles observados sobre los datos de esta ejecución (no verdicts fijos).
    ids_nulos = 0
    semana_fuera_rango = 0
    totales_negativos = 0
    total_distinto_suma_grupos = 0
    fechas_rm: set[str] = set()
    # El hash identifica el RAW exacto que origina este Parquet: permite detectar
    # un procesado desalineado con el RAW vigente (p. ej. tras una limpieza fallida).
    raw_sha256 = file_sha256(raw_file)

    # Tipos para Parquet
    schema = OUTPUT_SCHEMA.with_metadata({RAW_SHA256_METADATA_KEY: raw_sha256.encode("ascii")})

    # Nunca exponer un Parquet incompleto en la ruta canónica. Una ejecución
    # interrumpida sólo puede dejar un temporal, que se descarta al reintentar.
    temp_parquet = output_dir / f"{output_parquet.name}.tmp"
    temp_parquet.unlink(missing_ok=True)
    writer = pq.ParquetWriter(temp_parquet, schema=schema, compression="snappy")

    # Buffer de filas procesadas para escribir en bloques
    rm_rows_buffer = []

    with open(raw_file, "r", encoding="latin-1", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=";")
        header = reader.fieldnames
        has_region_col = "CodigoRegion" in header

        for row in reader:
            total_raw += 1
            id_estab = str(row.get("IdEstablecimiento", "")).strip()
            if not id_estab:
                ids_nulos += 1

            is_rm = False
            is_known_non_rm = False
            estab_info = None

            # 1. Búsqueda en catálogo RM
            if id_estab in rm_by_antiguo:
                is_rm = True
                estab_info = rm_by_antiguo[id_estab]
            elif id_estab in rm_by_nuevo:
                is_rm = True
                estab_info = rm_by_nuevo[id_estab]
            elif has_region_col:
                cod_reg = str(row.get("CodigoRegion", "")).strip().split(".")[0]
                if cod_reg in ["13", "013"]:
                    is_rm = True
                elif cod_reg != "" and cod_reg not in ["13", "013"]:
                    is_known_non_rm = True

            # 2. Descarte por catálogo nacional si no fue RM
            if not is_rm and not is_known_non_rm:
                if id_estab in nac_by_antiguo:
                    if nac_by_antiguo[id_estab]["region_codigo"] == 13:
                        is_rm = True
                    else:
                        is_known_non_rm = True
                elif id_estab in nac_by_nuevo:
                    if nac_by_nuevo[id_estab]["region_codigo"] == 13:
                        is_rm = True
                    else:
                        is_known_non_rm = True

            if is_rm:
                total_rm += 1
                rm_estabs_set.add(id_estab)

                # Homologar metadatos territoriales si vienen de catálogo o de columnas
                if estab_info:
                    cod_nuevo = estab_info["establecimiento_codigo"]
                    cod_antiguo = estab_info["establecimiento_codigo_antiguo"]
                    nom_estab = estab_info["establecimiento_glosa"]
                    cod_com = estab_info["comuna_codigo"]
                    nom_com = estab_info["comuna_glosa"]
                    tipo_estab_glosa = estab_info["tipo_establecimiento_glosa"]
                    lat = estab_info["latitud"]
                    lon = estab_info["longitud"]
                else:
                    cod_nuevo = int(id_estab.replace("-", "")) if id_estab.replace("-", "").isdigit() else 0
                    cod_antiguo = id_estab
                    nom_estab = row.get("NEstablecimiento", "")
                    cod_com = str(row.get("CodigoComuna", "")).strip()
                    nom_com = row.get("NombreComuna", "")
                    tipo_estab_glosa = None
                    lat = None
                    lon = None

                fec_str = str(row.get("fecha", "")).strip()
                sem_val = int(row.get("semana", 0) or 0)
                id_causa_val = int(row.get("IdCausa", 0) or 0)
                tot_val = int(row.get("Total", 0) or 0)
                m1_val = int(row.get("Menores_1", 0) or 0)
                d1_4_val = int(row.get("De_1_a_4", 0) or 0)
                d5_14_val = int(row.get("De_5_a_14", 0) or 0)
                d15_64_val = int(row.get("De_15_a_64", 0) or 0)
                d65_val = int(row.get("De_65_y_mas", 0) or 0)
                fechas_rm.add(fec_str)
                if not 1 <= sem_val <= 53:
                    semana_fuera_rango += 1
                if tot_val < 0:
                    totales_negativos += 1
                if tot_val != m1_val + d1_4_val + d5_14_val + d15_64_val + d65_val:
                    total_distinto_suma_grupos += 1

                proc_row = {
                    "fecha": fec_str,
                    "ano": year,
                    "semana": sem_val,
                    "establecimiento_codigo": cod_nuevo,
                    "establecimiento_codigo_antiguo": cod_antiguo,
                    "establecimiento_glosa": nom_estab,
                    "region_codigo": 13,
                    "region_glosa": "Metropolitana de Santiago",
                    "comuna_codigo": cod_com,
                    "comuna_glosa": nom_com,
                    "tipo_establecimiento_glosa": tipo_estab_glosa,
                    "tipo_establecimiento_urgencia": row.get("GLOSATIPOESTABLECIMIENTO", ""),
                    "tipo_atencion_urgencia": row.get("GLOSATIPOATENCION", ""),
                    "tipo_campana": row.get("GlosaTipoCampana", ""),
                    "id_causa": id_causa_val,
                    "glosa_causa": row.get("GlosaCausa", ""),
                    "total": tot_val,
                    "menores_1": m1_val,
                    "de_1_a_4": d1_4_val,
                    "de_5_a_14": d5_14_val,
                    "de_15_a_64": d15_64_val,
                    "de_65_y_mas": d65_val,
                    "latitud": lat,
                    "longitud": lon,
                }
                rm_rows_buffer.append(proc_row)

                if len(rm_rows_buffer) >= chunk_size:
                    batch_df = pd.DataFrame(rm_rows_buffer)
                    batch_table = pa.Table.from_pandas(batch_df, schema=schema, preserve_index=False)
                    writer.write_table(batch_table)
                    rm_rows_buffer = []

            elif is_known_non_rm:
                total_no_rm += 1
            else:
                total_sin_territorio += 1

    if rm_rows_buffer:
        batch_df = pd.DataFrame(rm_rows_buffer)
        batch_table = pa.Table.from_pandas(batch_df, schema=schema, preserve_index=False)
        writer.write_table(batch_table)

    writer.close()

    # Validar el footer y el esquema antes de publicar el artefacto canónico.
    validated_schema = pq.read_schema(temp_parquet)
    declared = (validated_schema.metadata or {}).get(RAW_SHA256_METADATA_KEY)
    if not validated_schema.equals(schema, check_metadata=False) or declared != raw_sha256.encode("ascii"):
        raise ValueError(
            f"Esquema Parquet inesperado para {temp_parquet.as_posix()}"
        )
    temp_parquet.replace(output_parquet)

    fechas = pd.to_datetime(pd.Series(sorted(fechas_rm), dtype="string"), format="%d/%m/%Y", errors="coerce")
    fechas_invalidas = int(fechas.isna().sum())
    fechas_validas = fechas.dropna()

    return {
        "year": year,
        "raw_file": raw_file.as_posix(),
        "processed_file": output_parquet.as_posix(),
        "raw_rows": total_raw,
        "rm_rows": total_rm,
        "no_rm_rows": total_no_rm,
        "sin_territorio_rows": total_sin_territorio,
        "rm_estabs_count": len(rm_estabs_set),
        "raw_sha256": raw_sha256,
        "fecha_min": fechas_validas.min().strftime("%d/%m/%Y") if not fechas_validas.empty else None,
        "fecha_max": fechas_validas.max().strftime("%d/%m/%Y") if not fechas_validas.empty else None,
        "raw_tiene_columna_region": has_region_col,
        "controles": {
            "ids_establecimiento_nulos_raw": ids_nulos,
            "fechas_distintas_formato_invalido": fechas_invalidas,
            "semanas_fuera_de_rango_1_53": semana_fuera_rango,
            "totales_negativos": totales_negativos,
            "total_distinto_suma_grupos_etarios": total_distinto_suma_grupos,
        },
    }


def _fmt(value: int) -> str:
    return f"{value:,}"


def _pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "n/d"


def build_report_md(
    results: List[Dict[str, Any]],
    rm_catalog_count: int,
    nac_catalog_count: int,
    current_year: int,
) -> str:
    """Informe de normalización: toda cifra sale de `results` y los catálogos usados.

    No contiene fechas de ejecución ni valores históricos fijos, de modo que el
    mismo input produce el mismo informe. Los controles se reportan como
    conteos observados; los que esta etapa no calcula no se declaran.
    """
    years = [r["year"] for r in results]
    total_raw = sum(r["raw_rows"] for r in results)
    total_rm = sum(r["rm_rows"] for r in results)
    total_no_rm = sum(r["no_rm_rows"] for r in results)
    total_sin_terr = sum(r["sin_territorio_rows"] for r in results)
    con_territorio = total_raw - total_sin_terr
    con_region = [r["year"] for r in results if r.get("raw_tiene_columna_region")]
    sin_region = [r["year"] for r in results if not r.get("raw_tiene_columna_region")]
    rango = f"{min(years)}–{max(years)}"

    fuentes = "\n".join(f"- `{r['raw_file']}`" for r in results)
    filas_retencion = "".join(
        f"| {r['year']} | {_fmt(r['raw_rows'])} | {_fmt(r['rm_rows'])} | {_fmt(r['no_rm_rows'])} "
        f"| {_fmt(r['sin_territorio_rows'])} | {_fmt(r['rm_rows'])} "
        f"| {_pct(r['raw_rows'] - r['sin_territorio_rows'], r['raw_rows'])} |\n"
        for r in results
    )
    filas_cortes = "".join(
        f"| {r['year']} | {r.get('fecha_min') or 'n/d'} | {r.get('fecha_max') or 'n/d'} "
        f"| `{r['raw_sha256'][:12]}…` |\n"
        for r in results
    )
    controles = {
        "Registros RAW sin `IdEstablecimiento`": "ids_establecimiento_nulos_raw",
        "Fechas distintas con formato distinto de `DD/MM/YYYY` (filas RM)": "fechas_distintas_formato_invalido",
        "Filas RM con `semana` fuera de [1, 53]": "semanas_fuera_de_rango_1_53",
        "Filas RM con `Total` negativo": "totales_negativos",
        "Filas RM con `Total` distinto de la suma de grupos etarios": "total_distinto_suma_grupos_etarios",
    }
    filas_controles = "".join(
        f"| {nombre} | {_fmt(sum(r['controles'][clave] for r in results))} |\n"
        for nombre, clave in controles.items()
    )
    actual = next((r for r in results if r["year"] == current_year), None)
    limite_actual = (
        f"2. **Año en curso ({current_year}):** el RAW es una fuente mutable; el último dato observado "
        f"en este procesamiento es {actual['fecha_max']} (ver sección 2). Su volumen no es "
        f"comparable con el de años completos.\n"
        if actual is not None
        else ""
    )
    return f"""# Informe de Normalización y Filtrado Territorial
## Atenciones de Urgencia DEIS {rango} (Región Metropolitana)

**Fuentes RAW:** `data/raw/urgencias/AtencionesUrgencia{min(years)}.csv` a `AtencionesUrgencia{max(years)}.csv`
**Destino Procesado:** `data/processed/urgencias/urgencias_rm_[{min(years)}-{max(years)}].parquet`
**Identificación del snapshot:** cada Parquet declara en su metadato `raw_sha256` el SHA256 del RAW procesado (resumen en la sección 2).

---

## 1. Fuentes Utilizadas

Se procesaron {len(results)} archivos CSV anuales de atenciones de urgencia a nivel nacional del DEIS-MINSAL:
{fuentes}

Para la homologación territorial se utilizó el catálogo procesado de la RM:
- `data/processed/establecimientos_rm_clean.csv` ({_fmt(rm_catalog_count)} códigos de establecimiento únicos)
- `data/processed/establecimientos_salud_clean.parquet` ({_fmt(nac_catalog_count)} códigos de establecimiento únicos nacionales)

---

## 2. Encoding, Separador y Cobertura Temporal

- **Lectura:** `latin-1` con `errors="replace"` y separador punto y coma (`;`), según la configuración de la etapa.
- **Columna `CodigoRegion` en el RAW:** presente en {con_region if con_region else 'ningún año'}; ausente en {sin_region if sin_region else 'ningún año'} (en ese caso el territorio se obtiene del catálogo de establecimientos).

| Año | Fecha mínima (filas RM) | Fecha máxima (filas RM) | SHA256 del RAW |
|---:|---|---|---|
{filas_cortes}
---

## 3. Esquema y Correspondencia de Columnas (RAW → PROCESSED)

| Nombre en RAW | Nombre Normalizado (`snake_case`) | Tipo de Dato |
|---|---|---|
| `fecha` | `fecha` | `string` (`DD/MM/YYYY`) |
| `(calculado)` | `ano` | `int32` |
| `semana` | `semana` | `int32` |
| `IdEstablecimiento` | `establecimiento_codigo` | `int64` (código nuevo DEIS, homologado con el catálogo) |
| `IdEstablecimiento` | `establecimiento_codigo_antiguo` | `string` |
| `NEstablecimiento` | `establecimiento_glosa` | `string` |
| `CodigoRegion` | `region_codigo` | `int32` (= 13) |
| `NombreRegion` | `region_glosa` | `string` (= 'Metropolitana de Santiago') |
| `CodigoComuna` | `comuna_codigo` | `string` |
| `NombreComuna` | `comuna_glosa` | `string` |
| `GLOSATIPOESTABLECIMIENTO` | `tipo_establecimiento_urgencia` | `string` |
| `GLOSATIPOATENCION` | `tipo_atencion_urgencia` | `string` |
| `GlosaTipoCampana` | `tipo_campana` | `string` |
| `IdCausa` | `id_causa` | `int32` |
| `GlosaCausa` | `glosa_causa` | `string` |
| `Total` | `total` | `int32` |
| `Menores_1` | `menores_1` | `int32` |
| `De_1_a_4` | `de_1_a_4` | `int32` |
| `De_5_a_14` | `de_5_a_14` | `int32` |
| `De_15_a_64` | `de_15_a_64` | `int32` |
| `De_65_y_mas` | `de_65_y_mas` | `int32` |
| `(catálogo)` | `latitud` | `float64` |
| `(catálogo)` | `longitud` | `float64` |

---

## 4. Transformaciones Realizadas

1. **Estandarización de nombres:** conversión a `snake_case`.
2. **Homologación de tipos:** columnas numéricas (`Total`, desgloses etarios, `semana`, `id_causa`) a `int32`; un valor vacío en esas columnas se lee como 0.
3. **Cruce territorial:** `IdEstablecimiento` se cruza contra `establecimiento_codigo_antiguo` y `establecimiento_codigo` de `data/processed/establecimientos_rm_clean.csv`; si no hay coincidencia se usa `CodigoRegion` del RAW cuando existe, y luego el catálogo nacional para descartar lo que no es RM.
4. **Filtro RM:** se conservan solo las filas con territorio RM.

---

## 5. Homologación Territorial y Filtrado RM

- **Registros con territorio determinado (RM o no RM):** {_fmt(con_territorio)} de {_fmt(total_raw)} ({_pct(con_territorio, total_raw)}).
- **Registros sin territorio determinado:** {_fmt(total_sin_terr)}.

---

## 6. Tabla de Retención de Registros

| Año | Filas RAW | Filas RM | Filas no RM | Sin territorio | Filas PROCESSED (RM) | Territorio determinado (%) |
|---:|---:|---:|---:|---:|---:|---:|
{filas_retencion}| **TOTAL** | **{_fmt(total_raw)}** | **{_fmt(total_rm)}** | **{_fmt(total_no_rm)}** | **{_fmt(total_sin_terr)}** | **{_fmt(total_rm)}** | **{_pct(con_territorio, total_raw)}** |

---

## 7. Controles Observados

Conteos calculados en esta ejecución. Esta etapa no verifica duplicados en el RAW ni la existencia de causas faltantes.

| Control | Registros |
|---|---:|
{filas_controles}
---

## 8. Registros No Procesables o Sin Correspondencia

- **Registros sin territorio determinado:** {_fmt(total_sin_terr)}.
- **Trazabilidad:** la diferencia entre `Filas RAW` y `Filas PROCESSED` ({_fmt(total_raw - total_rm)}) corresponde a los registros no RM ({_fmt(total_no_rm)}) y a los sin territorio determinado ({_fmt(total_sin_terr)}).

---

## 9. Limitaciones

1. **Resolución temporal:** la serie de atenciones está agrupada a nivel diario y semanal por causa y grupo etario, no a nivel de transacción de paciente individual (datos ecológicos).
{limite_actual}3. **Cambio de causas CIE:** las glosas y agrupaciones de causas del DEIS se auditarán y homologarán específicamente para salud mental (F00–F99) en la siguiente etapa analítica.
"""


def run_full_normalization() -> List[Dict[str, Any]]:
    """Ejecuta la normalización completa 2020-año Chile actual y genera el informe Markdown."""
    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_URGENCIAS_DIR.mkdir(parents=True, exist_ok=True)

    rm_antiguo, rm_nuevo, nac_antiguo, nac_nuevo = load_establishment_catalogs()

    results = []
    for year in SUPPORTED_YEARS:
        print(f"Normalizando Atenciones de Urgencia {year}...")
        res = process_urgencias_year(
            year=year,
            rm_by_antiguo=rm_antiguo,
            rm_by_nuevo=rm_nuevo,
            nac_by_antiguo=nac_antiguo,
            nac_by_nuevo=nac_nuevo,
        )
        results.append(res)
        print(f"  Completado: RAW={res['raw_rows']:,} -> PROCESSED RM={res['rm_rows']:,}")

    report_md = build_report_md(results, len(rm_nuevo), len(nac_nuevo), current_year_chile())
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(report_md)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Normaliza Atenciones de Urgencia DEIS para la RM."
    )
    parser.add_argument(
        "--year", type=int, choices=SUPPORTED_YEARS,
        help="Procesa únicamente el año indicado sin reescribir el reporte global.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Compatibilidad con el orquestador; la etapa ya se ejecuta forzada.",
    )
    args = parser.parse_args()

    if args.year is None:
        results = run_full_normalization()
    else:
        rm_antiguo, rm_nuevo, nac_antiguo, nac_nuevo = load_establishment_catalogs()
        results = [process_urgencias_year(
            year=args.year,
            rm_by_antiguo=rm_antiguo,
            rm_by_nuevo=rm_nuevo,
            nac_by_antiguo=nac_antiguo,
            nac_by_nuevo=nac_nuevo,
        )]
    print("\nProceso de normalización finalizado exitosamente.")
    for r in results:
        print(f"Año {r['year']}: RAW {r['raw_rows']:,} -> PROCESSED RM {r['rm_rows']:,} en {r['processed_file']}")


if __name__ == "__main__":
    main()
