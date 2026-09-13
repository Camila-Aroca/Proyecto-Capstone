"""Construye la dimensión canónica de oferta territorial de urgencia (RM).

Snapshot ACTUAL del catálogo de establecimientos, no una serie histórica:
representa qué establecimientos vigentes constituyen hoy la oferta de
atención de urgencia, según `establecimientos_rm_clean.parquet`. La evidencia
de reporte en Urgencias (`reporto_id1_periodo`, `reporto_id36_periodo`,
`ultimo_ano_reporte_id36`, `tipo_urgencia_reportado`) es información temporal
complementaria, no el criterio de inclusión: un establecimiento del tipo
correcto pertenece a la oferta aunque nunca haya reportado actividad en el
período observado.

Esa evidencia temporal usa el período canónico CERRADO 2021-2025, no
2020-2026: 2020 queda excluido por la discontinuidad metodológica no resuelta
en el registro de salud mental documentada en
`reports/eda/eda_demanda_urgencias_rm.md` (DEIS incorporó la obligatoriedad y
el desglose de ID36 recién a fines de 2020), y 2026 queda excluido por ser un
año parcial y mutable (el RAW del año en curso puede sobrescribirse). 2020 y
2026 no alimentan estos atributos; solo pueden citarse como contexto adicional
en EDA, claramente separados del período canónico.

Criterio de inclusión (`criterio_inclusion_oferta`):
- `catalogo_core`: `tipo_establecimiento_glosa` es exactamente "Hospital" o
  termina en el acrónimo DEIS "(SAPU)", "(SAR)" o "(SUR)", y
  `estado_funcionamiento` normalizado (recortado y en minúsculas, para
  absorber la variante de capitalización observada en la fuente) es
  "vigente en operación habitual".
- `excepcion_cear_documentada`: establecimientos vigentes que no caen en el
  criterio anterior pero reportan alguna vez, en los Parquet de Urgencias
  2021-2025, `tipo_establecimiento_urgencia = "CEAR"` (evidencia empírica de
  reporte de urgencia, no un supuesto sobre el tipo catalogado). El código
  no se hardcodea: se detecta dinámicamente contra la fuente de Urgencias en
  cada ejecución, por lo que deja de incluirse automáticamente si la fuente
  deja de respaldarlo. En el snapshot vigente al construir este módulo
  corresponde al CESFAM Juan Pablo II (La Reina, código 112320).

Este stage explícitamente NO usa `tiene_servicio_urgencia` ni `tipo_urgencia`
del maestro como criterio de inclusión ni de exclusión: el Instituto
Psiquiátrico Dr. José Horwitz Barak (código 109102) tiene
`tiene_servicio_urgencia = "NO"` en el maestro, pero reporta miles de
atenciones de urgencia por año en Urgencias 2021-2025 (mayoritariamente
`ID 36`, salud mental); esos campos del maestro quedaron demostrados no
confiables para esta decisión (ver `reports/eda/eda_dim_oferta_urgencia_rm.md`).
Tampoco se exige `ID36 > 0` para pertenecer a la oferta: eso excluiría, sin
evidencia de que no exista el dispositivo, a establecimientos del tipo
correcto que aún no reportan actividad de salud mental en el período.

COSAM (salud mental ambulatoria) y el resto de CESFAM/CECOSF/PSR (fuera de la
excepción documentada) quedan fuera de la oferta: no reportan actividad de
urgencia en ningún año 2021-2025 y su `tipo_establecimiento_glosa` no
corresponde a un dispositivo de urgencia.

No se implementan aquí OSM/GTFS ni isócronas; esta dimensión es únicamente el
insumo de oferta para esa capa futura.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import tempfile
from typing import Final

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAESTRO_PATH: Final[Path] = Path("data/processed/establecimientos_rm_clean.parquet")
URGENCIAS_DIR: Final[Path] = Path("data/processed/urgencias")
OUTPUT_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")

YEARS: Final[tuple[int, ...]] = tuple(range(2021, 2026))
ESTADO_VIGENTE: Final[str] = "vigente en operación habitual"
CORE_ACRONYM_PATTERN: Final[str] = r"\((?:SAPU|SAR|SUR)\)$"
CRITERIO_CORE: Final[str] = "catalogo_core"
CRITERIO_EXCEPCION_CEAR: Final[str] = "excepcion_cear_documentada"
TIPO_CEAR: Final[str] = "CEAR"

# Bounding box geográfico laxo de la Región Metropolitana, ya usado como
# control de calidad en `src/data/clean_establishments.py::audit_rm_quality`.
RM_LAT_RANGE: Final[tuple[float, float]] = (-34.5, -32.5)
RM_LON_RANGE: Final[tuple[float, float]] = (-72.0, -69.5)

SCHEMA: Final[pa.Schema] = pa.schema([
    ("establecimiento_codigo", pa.int64()),
    ("establecimiento_nombre", pa.string()),
    ("comuna_codigo", pa.string()),
    ("comuna_glosa", pa.string()),
    ("tipo_establecimiento", pa.string()),
    ("estado_funcionamiento", pa.string()),
    ("latitud", pa.float64()),
    ("longitud", pa.float64()),
    ("criterio_inclusion_oferta", pa.string()),
    ("reporto_id1_periodo", pa.bool_()),
    ("reporto_id36_periodo", pa.bool_()),
    ("ultimo_ano_reporte_id36", pa.int32()),
    ("tipo_urgencia_reportado", pa.string()),
])


def _normalize_estado(series: pd.Series) -> pd.Series:
    """Recorta y pasa a minúsculas `estado_funcionamiento` para filtrar vigentes de forma reproducible."""
    return series.astype(str).str.strip().str.lower()


def _is_core_tipo(tipo_establecimiento_glosa: pd.Series) -> pd.Series:
    """Identifica Hospital/SAPU/SAR/SUR por el acrónimo DEIS o la palabra exacta "Hospital"."""
    return (tipo_establecimiento_glosa == "Hospital") | (
        tipo_establecimiento_glosa.str.contains(CORE_ACRONYM_PATTERN, regex=True, na=False)
    )


def load_maestro_universe(maestro_path: Path = MAESTRO_PATH) -> pd.DataFrame:
    """Lee el maestro de establecimientos y normaliza código/estado para join y filtro."""
    if not maestro_path.exists():
        raise FileNotFoundError(f"No existe el maestro requerido: {maestro_path.as_posix()}")
    columns = [
        "establecimiento_codigo", "establecimiento_glosa", "comuna_codigo",
        "comuna_glosa", "tipo_establecimiento_glosa", "estado_funcionamiento",
        "latitud", "longitud",
    ]
    frame = pq.read_table(maestro_path, columns=columns).to_pandas()
    # Normalización explícita para joins: el maestro publica el código como
    # string (6 dígitos, sin ceros a la izquierda) y Urgencias lo publica
    # como int64; sin este cast, un join directo pierde filas en silencio.
    frame["establecimiento_codigo"] = frame["establecimiento_codigo"].astype("int64")
    if frame["establecimiento_codigo"].duplicated().any():
        raise ValueError("establecimiento_codigo duplicado en el maestro de establecimientos.")
    frame["estado_normalizado"] = _normalize_estado(frame["estado_funcionamiento"])
    return frame


def load_urgencias_evidence(
    input_dir: Path = URGENCIAS_DIR, years: tuple[int, ...] = YEARS
) -> pd.DataFrame:
    """Agrega, por `establecimiento_codigo` (int64), evidencia de reporte sobre
    el período canónico CERRADO 2021-2025 (excluye 2020 por la discontinuidad
    metodológica de salud mental y 2026 por ser un año parcial/mutable; ver
    `reports/eda/eda_demanda_urgencias_rm.md`).

    `reporto_id1_periodo`/`reporto_id36_periodo` son presencia de al menos una
    fila del `id_causa` correspondiente (`id_causa=36` exige además
    `total > 0`, es decir, atención de salud mental efectivamente registrada,
    no solo la fila-cero de reporte). `tipo_urgencia_reportado` es el valor de
    `tipo_establecimiento_urgencia` observado en el año más reciente dentro de
    2021-2025 en que el establecimiento aparece en la fuente (regla
    determinista: algunos códigos cambian de tipo reportado entre años; se
    documenta el más reciente dentro del período canónico, no el histórico
    completo). `reporto_cear_alguna_vez` es una columna interna (no forma
    parte del contrato publicado) usada únicamente para detectar la excepción
    documentada, también acotada a 2021-2025.
    """
    files = [input_dir / f"urgencias_rm_{year}.parquet" for year in years]
    missing = [f.as_posix() for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError(f"Parquet de Urgencias no disponible: {missing}")

    frames = [
        pd.read_parquet(
            f,
            columns=[
                "ano", "establecimiento_codigo", "id_causa", "total",
                "tipo_establecimiento_urgencia",
            ],
        )
        for f in files
    ]
    source = pd.concat(frames, ignore_index=True)
    source["establecimiento_codigo"] = source["establecimiento_codigo"].astype("int64")

    id1_codes = set(source.loc[source["id_causa"] == 1, "establecimiento_codigo"])
    id36_positive = source[(source["id_causa"] == 36) & (source["total"] > 0)]
    id36_codes = set(id36_positive["establecimiento_codigo"])
    ultimo_ano = id36_positive.groupby("establecimiento_codigo")["ano"].max()
    cear_codes = set(
        source.loc[source["tipo_establecimiento_urgencia"] == TIPO_CEAR, "establecimiento_codigo"]
    )

    latest_tipo = (
        source.sort_values("ano")
        .drop_duplicates("establecimiento_codigo", keep="last")
        .set_index("establecimiento_codigo")["tipo_establecimiento_urgencia"]
    )

    all_codes = sorted(set(source["establecimiento_codigo"]))
    evidence = pd.DataFrame({"establecimiento_codigo": all_codes})
    evidence["reporto_id1_periodo"] = evidence["establecimiento_codigo"].isin(id1_codes)
    evidence["reporto_id36_periodo"] = evidence["establecimiento_codigo"].isin(id36_codes)
    evidence["ultimo_ano_reporte_id36"] = (
        evidence["establecimiento_codigo"].map(ultimo_ano).astype("Int32")
    )
    evidence["tipo_urgencia_reportado"] = evidence["establecimiento_codigo"].map(latest_tipo)
    evidence["reporto_cear_alguna_vez"] = evidence["establecimiento_codigo"].isin(cear_codes)
    return evidence


def validate_dim_oferta(dim: pd.DataFrame, cear_codes: set[int]) -> None:
    """Valida unicidad, tipos permitidos + excepción, cobertura, coordenadas y flags de reporte."""
    if dim.empty:
        raise ValueError("La dimensión de oferta de urgencia quedó vacía.")

    if dim["establecimiento_codigo"].duplicated().any():
        raise ValueError("establecimiento_codigo duplicado en la dimensión de oferta.")

    if not pd.api.types.is_integer_dtype(dim["establecimiento_codigo"]):
        raise ValueError("establecimiento_codigo debe ser entero (normalizado para join con Urgencias).")

    core_rows = dim["criterio_inclusion_oferta"] == CRITERIO_CORE
    excepcion_rows = dim["criterio_inclusion_oferta"] == CRITERIO_EXCEPCION_CEAR
    if (core_rows | excepcion_rows).sum() != len(dim):
        raise ValueError("criterio_inclusion_oferta contiene valores fuera del dominio permitido.")

    if not _is_core_tipo(dim.loc[core_rows, "tipo_establecimiento"]).all():
        raise ValueError("Fila catalogo_core con tipo_establecimiento fuera de {Hospital,SAPU,SAR,SUR}.")
    if _is_core_tipo(dim.loc[excepcion_rows, "tipo_establecimiento"]).any():
        raise ValueError("Fila excepcion_cear_documentada coincide con el tipo core; está duplicando criterio.")
    if not set(dim.loc[excepcion_rows, "establecimiento_codigo"]).issubset(cear_codes):
        raise ValueError("Excepción CEAR incluye un código sin evidencia de reporte CEAR en Urgencias.")

    if not (dim["estado_funcionamiento"] == ESTADO_VIGENTE).all():
        raise ValueError("La dimensión de oferta incluye un establecimiento no vigente.")

    mandatory_text = [
        "establecimiento_nombre", "comuna_codigo", "comuna_glosa",
        "tipo_establecimiento", "estado_funcionamiento", "criterio_inclusion_oferta",
    ]
    for column in mandatory_text:
        if dim[column].isna().any():
            raise ValueError(f"Columna obligatoria con nulos: {column}")
    if not dim["comuna_codigo"].str.match(r"^13\d{3}$").all():
        raise ValueError("comuna_codigo fuera del formato CUT esperado para la RM (13xxx).")

    coord_null = dim["latitud"].isna()
    if not (coord_null == dim["longitud"].isna()).all():
        raise ValueError("latitud y longitud deben ser ambas nulas o ambas válidas, nunca una sola.")
    lat_valid = dim.loc[~coord_null, "latitud"]
    lon_valid = dim.loc[~coord_null, "longitud"]
    if not lat_valid.between(*RM_LAT_RANGE).all() or not lon_valid.between(*RM_LON_RANGE).all():
        raise ValueError("Coordenadas fuera del bounding box esperado para la RM.")

    if (dim["reporto_id36_periodo"] & ~dim["reporto_id1_periodo"]).any():
        raise ValueError("reporto_id36_periodo=True sin reporto_id1_periodo=True: incoherente con Urgencias.")
    if not (dim["ultimo_ano_reporte_id36"].notna() == dim["reporto_id36_periodo"]).all():
        raise ValueError("ultimo_ano_reporte_id36 debe estar presente si y solo si reporto_id36_periodo=True.")
    valid_ultimo_ano = dim["ultimo_ano_reporte_id36"].dropna()
    if not valid_ultimo_ano.between(min(YEARS), max(YEARS)).all():
        raise ValueError("ultimo_ano_reporte_id36 fuera del período de evidencia soportado.")
    if not (dim["tipo_urgencia_reportado"].notna() == dim["reporto_id1_periodo"]).all():
        raise ValueError("tipo_urgencia_reportado debe estar presente si y solo si reporto_id1_periodo=True.")


def build_dim_oferta_urgencia_rm(
    maestro_path: Path = MAESTRO_PATH,
    urgencias_dir: Path = URGENCIAS_DIR,
) -> pd.DataFrame:
    """Construye, valida y devuelve la dimensión canónica de oferta de urgencia (RM)."""
    maestro = load_maestro_universe(maestro_path)
    evidence = load_urgencias_evidence(urgencias_dir)

    vigente = maestro["estado_normalizado"] == ESTADO_VIGENTE
    core_mask = _is_core_tipo(maestro["tipo_establecimiento_glosa"])

    cear_codes = set(
        evidence.loc[evidence["reporto_cear_alguna_vez"], "establecimiento_codigo"]
    )
    excepcion_mask = maestro["establecimiento_codigo"].isin(cear_codes) & vigente & ~core_mask
    included_mask = (core_mask & vigente) | excepcion_mask

    working = maestro.loc[included_mask].copy()
    working["criterio_inclusion_oferta"] = np.where(
        excepcion_mask.loc[working.index], CRITERIO_EXCEPCION_CEAR, CRITERIO_CORE
    )

    working = working.merge(
        evidence.drop(columns="reporto_cear_alguna_vez"),
        on="establecimiento_codigo",
        how="left",
        validate="one_to_one",
    )
    working["reporto_id1_periodo"] = working["reporto_id1_periodo"].fillna(False).astype(bool)
    working["reporto_id36_periodo"] = working["reporto_id36_periodo"].fillna(False).astype(bool)
    working["ultimo_ano_reporte_id36"] = working["ultimo_ano_reporte_id36"].astype("Int32")

    dim = pd.DataFrame({
        "establecimiento_codigo": working["establecimiento_codigo"],
        "establecimiento_nombre": working["establecimiento_glosa"],
        "comuna_codigo": working["comuna_codigo"],
        "comuna_glosa": working["comuna_glosa"],
        "tipo_establecimiento": working["tipo_establecimiento_glosa"],
        "estado_funcionamiento": working["estado_normalizado"],
        "latitud": working["latitud"],
        "longitud": working["longitud"],
        "criterio_inclusion_oferta": working["criterio_inclusion_oferta"],
        "reporto_id1_periodo": working["reporto_id1_periodo"],
        "reporto_id36_periodo": working["reporto_id36_periodo"],
        "ultimo_ano_reporte_id36": working["ultimo_ano_reporte_id36"],
        "tipo_urgencia_reportado": working["tipo_urgencia_reportado"],
    }).sort_values("establecimiento_codigo").reset_index(drop=True)

    validate_dim_oferta(dim, cear_codes)
    return dim


def _atomic_write(dim: pd.DataFrame, output_path: Path = OUTPUT_PATH) -> None:
    """Escribe el Parquet final de forma atómica (temporal validado -> reemplazo)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(dim, schema=SCHEMA, preserve_index=False)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=output_path.parent, prefix=f"{output_path.name}.", suffix=".tmp"
    ) as temp:
        temp_path = Path(temp.name)
    try:
        pq.write_table(table, temp_path, compression="snappy")
        if not pq.read_schema(temp_path).names:
            raise ValueError(f"Parquet temporal sin columnas: {temp_path.as_posix()}")
        temp_path.replace(output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye la dimensión canónica de oferta territorial de urgencia (RM).",
    )
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()

    dim = build_dim_oferta_urgencia_rm()
    _atomic_write(dim)

    resumen = dim["tipo_establecimiento"].value_counts().to_dict()
    logger.info(
        "Dimensión de oferta de urgencia generada: %s filas -> %s. "
        "Excepción CEAR: %s. Sin coordenadas: %s.",
        len(dim), resumen,
        int((dim["criterio_inclusion_oferta"] == CRITERIO_EXCEPCION_CEAR).sum()),
        int(dim["latitud"].isna().sum()),
    )


if __name__ == "__main__":
    main()
