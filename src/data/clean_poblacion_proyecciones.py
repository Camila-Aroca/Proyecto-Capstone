"""Construye la dimensión anual de población comunal RM (2021-2025).

Fuente: INE, "Estimaciones y Proyecciones de la Población de Chile a nivel
comunal 2002-2035" (base Censo 2017, documento metodológico noviembre 2019).
El cuadro publica población residente habitual por sexo, edad simple (0 a 80,
top-coded en "80 y más") y comuna, al 30 de junio de cada año. Los años
2021-2025 corresponden en su totalidad al tramo de PROYECCIÓN (posterior al
Censo 2017 usado como ancla), no al tramo de estimación intercensal
2002-2017.

Esta dimensión es distinta e independiente de
`dim_poblacion_comuna_censo2024.parquet`: esa dimensión usa población
efectivamente censada en el Censo 2024 (año fijo, fuente censal, población de
hecho/empadronada); esta usa población residente habitual proyectada por el
INE a partir del Censo 2017 (serie anual 2002-2035, metodológicamente
distinta: interpolación logística ajustada con antecedentes
sociodemográficos, no recuento directo). Ninguna debe usarse como proxy de la
otra; la diferencia observada entre ambas para 2024 se documenta pero no se
exige igualdad.

El workbook fuente presenta corrupción de codificación irreversible (U+FFFD)
en las columnas de texto de región/comuna; el código único territorial (CUT)
numérico no está afectado. Por eso `comuna_glosa` se toma del catálogo
comunal ya validado (`dim_poblacion_comuna_censo2024.parquet`), no del texto
de este workbook.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import tempfile
from typing import Any, Final

from openpyxl import load_workbook
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data.clean_censo_comunas import EXPECTED_RM_CUTS


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_PATH = Path("data/raw/poblacion/ine_estimaciones_proyecciones_2002_2035_comunas.xlsx")
GLOSA_CATALOG_PATH = Path("data/processed/censo/dim_poblacion_comuna_censo2024.parquet")
OUTPUT_PATH = Path("data/processed/censo/dim_poblacion_comuna_anual.parquet")

SHEET_NAME = "Est. y Proy. de Pob. Comunal"
REGION_METROPOLITANA_CODIGO = 13
YEARS: Final[tuple[int, ...]] = (2021, 2022, 2023, 2024, 2025)
FIRST_YEAR_COLUMN = 2002
# Ultimo anio publicado por el producto INE ("2002-2035"); limita las lecturas.
LAST_YEAR_COLUMN = 2035
FIRST_YEAR_COLUMN_INDEX = 8
SEXOS_ESPERADOS: Final[frozenset[int]] = frozenset({1, 2})
EDAD_MIN = 0
EDAD_MAX = 80
TIPO_POBLACION = "proyeccion"
FUENTE = (
    "INE, Estimaciones y Proyecciones de la Poblacion de Chile 2002-2035 a nivel "
    "comunal (base Censo 2017, documento metodologico noviembre 2019); poblacion "
    "residente habitual al 30 de junio de cada ano, agregada desde sexo y edad "
    "simple (0-80, top-coded 80 y mas)."
)

SCHEMA = pa.schema([
    ("comuna_codigo", pa.string()),
    ("comuna_glosa", pa.string()),
    ("ano", pa.int32()),
    ("poblacion", pa.int64()),
    ("fuente", pa.string()),
    ("tipo_poblacion", pa.string()),
])


def _year_column_index(year: int) -> int:
    return FIRST_YEAR_COLUMN_INDEX + (year - FIRST_YEAR_COLUMN)


def _load_comuna_glosas(catalog_path: Path) -> dict[str, str]:
    """Lee comuna_codigo->comuna_glosa desde el catálogo comunal ya validado."""
    if not catalog_path.exists():
        raise FileNotFoundError(f"No existe el catálogo de glosas comunales requerido: {catalog_path.as_posix()}")
    table = pq.read_table(catalog_path, columns=["comuna_codigo", "comuna_glosa"])
    glosas = dict(zip(table["comuna_codigo"].to_pylist(), table["comuna_glosa"].to_pylist()))
    missing = {str(cut) for cut in EXPECTED_RM_CUTS} - glosas.keys()
    if missing:
        raise ValueError(f"Catálogo de glosas comunales incompleto, faltan CUT: {sorted(missing)}")
    return glosas


def _aggregate_rm_population(
    raw_path: Path, years: tuple[int, ...] = YEARS
) -> dict[tuple[str, int], int]:
    """Suma población por comuna×año desde filas sexo×edad simple, sin doble conteo."""
    workbook = load_workbook(raw_path, read_only=True, data_only=True)
    try:
        sheet = workbook[SHEET_NAME]
        totals: dict[tuple[str, int], int] = {}
        for row in sheet.iter_rows(min_row=2, values_only=True):
            region = row[0]
            if region != REGION_METROPOLITANA_CODIGO:
                continue
            comuna_cut, sexo, edad = row[4], row[6], row[7]
            if sexo not in SEXOS_ESPERADOS:
                raise ValueError(f"Código de sexo inesperado en la fuente INE: {sexo!r}.")
            if edad is None or not (EDAD_MIN <= edad <= EDAD_MAX):
                raise ValueError(f"Edad simple fuera de rango esperado [{EDAD_MIN}, {EDAD_MAX}]: {edad!r}.")
            comuna_codigo = str(int(comuna_cut))
            for year in years:
                value = row[_year_column_index(year)]
                if value is None:
                    raise ValueError(f"Población nula en la fuente INE para comuna {comuna_codigo}, año {year}.")
                key = (comuna_codigo, year)
                totals[key] = totals.get(key, 0) + int(value)
        return totals
    finally:
        workbook.close()


def _validate_totals(
    totals: dict[tuple[str, int], int], years: tuple[int, ...] = YEARS
) -> None:
    expected_codes = {str(cut) for cut in EXPECTED_RM_CUTS}
    observed_codes = {code for code, _ in totals.keys()}
    if observed_codes != expected_codes:
        missing = expected_codes - observed_codes
        extra = observed_codes - expected_codes
        raise ValueError(
            f"Comunas RM inconsistentes con el CUT oficial. Faltantes: {sorted(missing)}, "
            f"inesperadas: {sorted(extra)}."
        )
    expected_combinations = len(expected_codes) * len(years)
    if len(totals) != expected_combinations:
        raise ValueError(
            f"Cobertura comuna×año incompleta: se esperaban {expected_combinations} combinaciones, "
            f"se obtuvieron {len(totals)}."
        )
    for (comuna_codigo, year), poblacion in totals.items():
        if poblacion <= 0:
            raise ValueError(f"Población no positiva para comuna {comuna_codigo}, año {year}.")


def load_rm_population(
    raw_path: Path = RAW_PATH, years: tuple[int, ...] = YEARS
) -> pd.DataFrame:
    """Poblacion proyectada RM por comuna y anio, en memoria y validada.

    Permite leer anios fuera del periodo canonico de la dimension (por ejemplo,
    el anio en curso para evaluar un pronostico) desde el mismo cuadro oficial
    INE y con las mismas validaciones, **sin** modificar
    `dim_poblacion_comuna_anual.parquet`, cuyo contrato sigue siendo 2021-2025.
    """
    fuera = [y for y in years if not FIRST_YEAR_COLUMN <= y <= LAST_YEAR_COLUMN]
    if fuera:
        raise ValueError(
            f"Anios fuera del cuadro INE ({FIRST_YEAR_COLUMN}-{LAST_YEAR_COLUMN}): {fuera}"
        )
    if not raw_path.exists():
        raise FileNotFoundError(f"No existe el RAW requerido: {raw_path.as_posix()}")
    totals = _aggregate_rm_population(raw_path, years)
    _validate_totals(totals, years)
    return pd.DataFrame(
        [
            {"comuna_codigo": comuna, "ano": ano, "poblacion": poblacion}
            for (comuna, ano), poblacion in sorted(totals.items())
        ]
    )


def build_dim_poblacion_comuna_anual(
    raw_path: Path = RAW_PATH,
    glosa_catalog_path: Path = GLOSA_CATALOG_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, Any]:
    """Genera `dim_poblacion_comuna_anual.parquet` de forma validada y atómica."""
    if not raw_path.exists():
        raise FileNotFoundError(f"No existe el RAW requerido: {raw_path.as_posix()}")

    glosas = _load_comuna_glosas(glosa_catalog_path)
    totals = _aggregate_rm_population(raw_path)
    _validate_totals(totals)

    records = [
        {
            "comuna_codigo": comuna_codigo,
            "comuna_glosa": glosas[comuna_codigo],
            "ano": year,
            "poblacion": poblacion,
            "fuente": FUENTE,
            "tipo_poblacion": TIPO_POBLACION,
        }
        for (comuna_codigo, year), poblacion in sorted(totals.items())
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records, schema=SCHEMA)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=output_path.parent, prefix=f"{output_path.name}.", suffix=".tmp"
    ) as temp:
        temp_path = Path(temp.name)
    try:
        pq.write_table(table, temp_path, compression="snappy")
        temp_path.replace(output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    verify_table = pq.read_table(output_path)
    return {
        "archivo_generado": output_path.as_posix(),
        "filas": verify_table.num_rows,
        "anos": sorted(set(verify_table["ano"].to_pylist())),
        "comunas_unicas": len(set(verify_table["comuna_codigo"].to_pylist())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye la dimensión anual de población comunal RM 2021-2025 (INE).")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    result = build_dim_poblacion_comuna_anual()
    logger.info("Dimensión anual de población comunal generada: %s", result)


if __name__ == "__main__":
    main()
