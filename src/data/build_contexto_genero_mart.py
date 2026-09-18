"""Construye el mart canónico de contexto interpretativo por sexo/género.

El mart es una capa de serving que concatena, sin joins ni enriquecimiento,
los cuatro Parquet normalizados de ``data/processed/contexto_genero``. Conserva
las temporalidades, ámbitos geográficos, categorías de sexo y valores
publicados de cada fuente; no es una feature ni un insumo de join automático
con Urgencias o Egresos.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
from typing import Final, Mapping, Sequence

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.data.normalize_gender_statistics import OUTPUT_FILES, SCHEMA


PROCESSED_DIR: Final[Path] = Path("data/processed/contexto_genero")
OUTPUT_PATH: Final[Path] = Path(
    "data/processed/marts/mart_contexto_genero_indicador_sexo.parquet"
)
SOURCE_IDS: Final[tuple[str, ...]] = tuple(OUTPUT_FILES)
GRAIN_COLUMNS: Final[tuple[str, ...]] = (
    "source_id",
    "source_sheet",
    "geography_level",
    "geography",
    "region_code",
    "period",
    "sex",
    "indicator",
    "unit",
)


def source_paths(processed_dir: Path = PROCESSED_DIR) -> dict[str, Path]:
    """Devuelve las cuatro fuentes normalizadas requeridas, en orden estable."""
    return {source_id: processed_dir / OUTPUT_FILES[source_id] for source_id in SOURCE_IDS}


def _validate_table(table: pa.Table, expected_source_ids: Sequence[str] = SOURCE_IDS) -> None:
    """Valida contrato, cobertura de fuentes, grano y valores publicados."""
    if table.schema != SCHEMA:
        raise ValueError("El mart no conserva exactamente el schema normalizado de contexto_genero.")
    if table.num_rows == 0:
        raise ValueError("El mart de contexto_genero no puede estar vacío.")

    frame = table.to_pandas()
    observed_source_ids = set(frame["source_id"])
    if observed_source_ids != set(expected_source_ids):
        raise ValueError(
            "source_id del mart no coincide con las fuentes esperadas: "
            f"observados={sorted(observed_source_ids)}, esperados={sorted(expected_source_ids)}"
        )
    grain_without_nullable_region = [column for column in GRAIN_COLUMNS if column != "region_code"]
    if frame[grain_without_nullable_region].isna().any().any():
        raise ValueError("La clave lógica del mart contiene nulos fuera de region_code.")
    # region_code es nulo legítimamente para las observaciones nacionales.
    duplicates = frame.duplicated(grain_without_nullable_region + ["region_code"])
    if duplicates.any():
        raise ValueError("El grano lógico del mart no es único.")
    published_value = frame["value"].notna()
    published_text = frame["value_text"].notna()
    if not (published_value ^ published_text).all():
        raise ValueError("Cada observación debe conservar exactamente value o value_text publicado.")
    if frame.loc[
        frame["source_id"].eq("ansiedad_depresion_sintomas_18_mas_sexo"), "year"
    ].notna().any():
        raise ValueError("PHQ-4 debe conservar year=NULL.")
    depressive = frame[frame["source_id"].eq("prevalencia_sintomas_depresivos_sexo")]
    if set(depressive["period"]) != {"2003", "2009-10", "2016-17"}:
        raise ValueError("El mart no conserva los períodos publicados de síntomas depresivos.")
    regional_text = frame.loc[
        frame["source_id"].eq("suicidio_ratio_hm_tasas_nacional_regional"), "value_text"
    ].dropna()
    if "-" not in set(regional_text):
        raise ValueError("El mart no conserva el símbolo publicado '-' de ratios regionales.")


def build_mart(input_paths: Mapping[str, Path] | None = None) -> pa.Table:
    """Concatena las fuentes contextuales sin alterar columnas ni valores."""
    paths = source_paths() if input_paths is None else dict(input_paths)
    if set(paths) != set(SOURCE_IDS):
        raise ValueError("Las fuentes del mart deben ser exactamente los cuatro source_id esperados.")
    tables: list[pa.Table] = []
    source_row_counts: dict[str, int] = {}
    for source_id in SOURCE_IDS:
        path = paths[source_id]
        if not path.is_file():
            raise FileNotFoundError(f"Input de contexto_genero no disponible: {path.as_posix()}")
        table = pq.read_table(path)
        if table.schema != SCHEMA:
            raise ValueError(f"Schema incompatible en {path.as_posix()}.")
        source_values = set(table.column("source_id").to_pylist())
        if source_values != {source_id}:
            raise ValueError(f"source_id inesperado en {path.as_posix()}: {sorted(source_values)}")
        source_row_counts[source_id] = table.num_rows
        tables.append(table)
    mart = pa.concat_tables(tables)
    sort_indices = pc.sort_indices(mart, sort_keys=[(column, "ascending") for column in GRAIN_COLUMNS])
    mart = pc.take(mart, sort_indices)
    _validate_table(mart)
    mart_row_counts = (
        mart.to_pandas()["source_id"].value_counts().reindex(SOURCE_IDS).to_dict()
    )
    if mart_row_counts != source_row_counts:
        raise ValueError("El mart no reconcilia exactamente las filas por source_id con sus inputs.")
    return mart


def validate_output(path: Path = OUTPUT_PATH) -> pa.Table:
    """Lee y valida un mart ya publicado para la condición de SKIP."""
    table = pq.read_table(path)
    _validate_table(table)
    return table


def atomic_write(table: pa.Table, output_path: Path = OUTPUT_PATH) -> None:
    """Publica el Parquet validado mediante reemplazo atómico."""
    _validate_table(table)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=output_path.parent, prefix=f"{output_path.name}.", suffix=".tmp"
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        pq.write_table(table, temporary_path, compression="snappy")
        validate_output(temporary_path)
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def build_and_publish(*, force: bool = False, output_path: Path = OUTPUT_PATH) -> bool:
    """Genera el mart, o realiza SKIP si su output actual es válido."""
    if output_path.is_file() and not force:
        try:
            validate_output(output_path)
        except (OSError, ValueError, pa.ArrowException):
            pass
        else:
            print(f"[SKIP] Mart contextual válido: {output_path.as_posix()}")
            return False
    mart = build_mart()
    atomic_write(mart, output_path)
    print(f"Mart contextual por sexo generado: {mart.num_rows:,} filas.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye el mart canónico de contexto interpretativo por sexo/género.",
    )
    parser.add_argument("--force", action="store_true", help="Regenera el output canónico.")
    args = parser.parse_args()
    build_and_publish(force=args.force)


if __name__ == "__main__":
    main()
