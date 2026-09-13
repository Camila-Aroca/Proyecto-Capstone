"""Construye marts comunales históricos de atenciones de Urgencia DEIS.

Los marts agregan conteos de atenciones (no personas) para 2021--2025. No
generan semanas ni meses ausentes, ni sustituyen la ausencia de una causa por
cero. El calendario semanal conserva la codificación publicada por DEIS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.data.profile_urgencias_sm_coverage import INPUT_DIR, YEARS


CAUSES: Final[tuple[int, ...]] = (1, 35, 36, 37, 38, 39, 40, 41)
MARTS_DIR: Final[Path] = Path("data/processed/marts")
WEEKLY_OUTPUT: Final[Path] = MARTS_DIR / "mart_urgencias_comuna_weekly.parquet"
MONTHLY_OUTPUT: Final[Path] = MARTS_DIR / "mart_urgencias_comuna_monthly.parquet"
COUNT_COLUMNS: Final[tuple[str, ...]] = tuple(
    f"atenciones_id{cause}" for cause in CAUSES
)
RATIO_SPECS: Final[dict[str, tuple[str, str]]] = {
    "proporcion_id36_sobre_id1": ("atenciones_id36", "atenciones_id1"),
    "proporcion_id37_sobre_id36": ("atenciones_id37", "atenciones_id36"),
    "proporcion_id38_sobre_id36": ("atenciones_id38", "atenciones_id36"),
    "proporcion_id39_sobre_id36": ("atenciones_id39", "atenciones_id36"),
    "proporcion_id40_sobre_id36": ("atenciones_id40", "atenciones_id36"),
    "proporcion_id41_sobre_id36": ("atenciones_id41", "atenciones_id36"),
}


def load_urgencias_source(input_dir: Path = INPUT_DIR) -> pd.DataFrame:
    """Lee sólo los IDs y las columnas requeridas desde los Parquet históricos."""
    files = [input_dir / f"urgencias_rm_{year}.parquet" for year in YEARS]
    absent = [path.as_posix() for path in files if not path.is_file()]
    if absent:
        raise FileNotFoundError(f"Parquet de Urgencias no disponible: {absent}")
    dataset = ds.dataset(files, format="parquet")
    table = dataset.to_table(
        filter=pc.field("id_causa").isin(CAUSES),
        columns=[
            "ano", "semana", "fecha", "comuna_codigo", "comuna_glosa",
            "establecimiento_codigo", "id_causa", "total",
        ],
    )
    source = table.to_pandas()
    source["fecha"] = pd.to_datetime(source["fecha"], dayfirst=True)
    return source


def _aggregate_grain(
    source: pd.DataFrame, grain_columns: list[str]
) -> pd.DataFrame:
    """Agrega causas y establecimientos reportantes a un grano temporal."""
    required = set(grain_columns) | {
        "comuna_codigo", "comuna_glosa", "establecimiento_codigo",
        "id_causa", "total",
    }
    if missing := required - set(source.columns):
        raise ValueError(f"Columnas faltantes en Urgencias: {sorted(missing)}")
    if not source["id_causa"].isin(CAUSES).all():
        raise ValueError("El origen contiene IDs fuera del contrato del mart.")

    keys = grain_columns + ["comuna_codigo", "comuna_glosa", "id_causa"]
    aggregated = (
        source.groupby(keys, as_index=False)
        .agg(
            atenciones=("total", "sum"),
            establecimientos_reportantes=("establecimiento_codigo", "nunique"),
        )
    )
    index = grain_columns + ["comuna_codigo", "comuna_glosa"]
    counts = aggregated.pivot(
        index=index, columns="id_causa", values="atenciones"
    ).rename(columns=lambda cause: f"atenciones_id{cause}")
    reporters = aggregated[aggregated["id_causa"].isin([1, 36])].pivot(
        index=index, columns="id_causa", values="establecimientos_reportantes"
    ).rename(
        columns={
            1: "n_establecimientos_reportantes_id1",
            36: "n_establecimientos_reportantes_id36",
        }
    )
    mart = counts.join(reporters, how="outer").reset_index()
    for column in COUNT_COLUMNS:
        if column not in mart:
            mart[column] = pd.NA
    for column in [
        "n_establecimientos_reportantes_id1",
        "n_establecimientos_reportantes_id36",
    ]:
        if column not in mart:
            mart[column] = pd.NA
    return mart


def _add_ratios(mart: pd.DataFrame) -> pd.DataFrame:
    """Calcula razones de atenciones; denominadores cero o ausentes dan nulo."""
    result = mart.copy()
    for name, (numerator, denominator) in RATIO_SPECS.items():
        result[name] = result[numerator].div(result[denominator]).where(
            result[denominator].gt(0)
        )
    return result


def build_weekly_mart(source: pd.DataFrame) -> pd.DataFrame:
    """Construye el mart comuna×semana usando el inicio observado DEIS."""
    required = {"ano", "semana", "fecha"}
    if missing := required - set(source.columns):
        raise ValueError(f"Columnas faltantes para semana: {sorted(missing)}")
    working = source.copy()
    working["fecha"] = pd.to_datetime(working["fecha"])
    starts = (
        working.groupby(["ano", "semana"], as_index=False)["fecha"]
        .min()
        .rename(columns={"fecha": "fecha_inicio_semana"})
    )
    mart = _aggregate_grain(working, ["ano", "semana"])
    mart = mart.merge(starts, on=["ano", "semana"], how="left", validate="many_to_one")
    mart["fecha_inicio_semana"] = mart["fecha_inicio_semana"].dt.date.astype(str)
    ordered = ["comuna_codigo", "comuna_glosa", "fecha_inicio_semana", "ano", "semana"]
    return _add_ratios(mart).sort_values(ordered).reset_index(drop=True)


def build_monthly_mart(source: pd.DataFrame) -> pd.DataFrame:
    """Construye el mart comuna×mes a partir de las fechas diarias DEIS."""
    if "fecha" not in source:
        raise ValueError("Columna faltante para mes: fecha")
    working = source.copy()
    working["fecha"] = pd.to_datetime(working["fecha"])
    working["mes"] = working["fecha"].dt.month
    working["fecha_mes"] = working["fecha"].dt.to_period("M").dt.start_time
    mart = _aggregate_grain(working, ["ano", "mes", "fecha_mes"])
    mart["fecha_mes"] = mart["fecha_mes"].dt.date.astype(str)
    ordered = ["comuna_codigo", "comuna_glosa", "fecha_mes"]
    return _add_ratios(mart).sort_values(ordered).reset_index(drop=True)


def validate_mart(mart: pd.DataFrame, grain: str) -> None:
    """Valida contrato, jerarquía de causas, ratios y reportantes del mart."""
    grain_keys = (
        ["comuna_codigo", "fecha_inicio_semana", "ano", "semana"]
        if grain == "weekly"
        else ["comuna_codigo", "fecha_mes"]
    )
    if mart.duplicated(grain_keys).any():
        raise ValueError(f"Grano {grain} no único.")
    if mart[list(COUNT_COLUMNS)].lt(0).any().any():
        raise ValueError("Se detectaron atenciones negativas.")
    components = [f"atenciones_id{cause}" for cause in (37, 38, 39, 40, 41)]
    complete_hierarchy = mart[["atenciones_id36", *components]].notna().all(axis=1)
    if not (
        mart.loc[complete_hierarchy, "atenciones_id36"]
        == mart.loc[complete_hierarchy, components].sum(axis=1)
    ).all():
        raise ValueError("ID36 no reconcilia con IDs 37--41.")
    comparable = mart[["atenciones_id36", "atenciones_id1"]].notna().all(axis=1)
    if not (
        mart.loc[comparable, "atenciones_id36"]
        <= mart.loc[comparable, "atenciones_id1"]
    ).all():
        raise ValueError("ID36 excede ID1.")
    for ratio, (_, denominator) in RATIO_SPECS.items():
        values = mart[ratio].dropna()
        if not values.between(0, 1).all():
            raise ValueError(f"Ratio fuera de [0, 1]: {ratio}")
        if not mart.loc[mart[denominator].le(0), ratio].isna().all():
            raise ValueError(f"Ratio definido con denominador no positivo: {ratio}")
    reporters = mart[
        ["n_establecimientos_reportantes_id1", "n_establecimientos_reportantes_id36"]
    ]
    if reporters.lt(0).any().any():
        raise ValueError("Se detectaron establecimientos reportantes negativos.")
    comparable_reporters = reporters.notna().all(axis=1)
    if not (
        reporters.loc[comparable_reporters, "n_establecimientos_reportantes_id36"]
        <= reporters.loc[comparable_reporters, "n_establecimientos_reportantes_id1"]
    ).all():
        raise ValueError("Reportantes ID36 exceden el universo ID1.")


def validate_reconciliation(weekly: pd.DataFrame, monthly: pd.DataFrame) -> None:
    """Verifica que las sumas anuales comuna×causa coincidan entre ambos marts."""
    columns = list(COUNT_COLUMNS)
    weekly_totals = weekly.groupby(["comuna_codigo", "ano"], as_index=False)[columns].sum(
        min_count=1
    )
    monthly_totals = monthly.groupby(["comuna_codigo", "ano"], as_index=False)[columns].sum(
        min_count=1
    )
    merged = weekly_totals.merge(
        monthly_totals,
        on=["comuna_codigo", "ano"],
        suffixes=("_weekly", "_monthly"),
        validate="one_to_one",
    )
    for column in columns:
        if not merged[f"{column}_weekly"].equals(merged[f"{column}_monthly"]):
            raise ValueError(f"No reconcilia semanal→mensual: {column}")


def _atomic_write(frame: pd.DataFrame, output_path: Path) -> None:
    """Escribe un Parquet temporal y lo publica sólo si su esquema es legible."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.unlink(missing_ok=True)
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), temporary, compression="snappy")
    if not pq.read_schema(temporary).names:
        raise ValueError(f"Parquet temporal sin columnas: {temporary.as_posix()}")
    temporary.replace(output_path)


def main() -> None:
    """Genera y valida ambos marts comunales históricos de Urgencias."""
    source = load_urgencias_source()
    weekly = build_weekly_mart(source)
    monthly = build_monthly_mart(source)
    validate_mart(weekly, "weekly")
    validate_mart(monthly, "monthly")
    validate_reconciliation(weekly, monthly)
    _atomic_write(weekly, WEEKLY_OUTPUT)
    _atomic_write(monthly, MONTHLY_OUTPUT)
    print(
        "Marts de Urgencias generados: "
        f"weekly={len(weekly):,} filas, monthly={len(monthly):,} filas."
    )


if __name__ == "__main__":
    main()
