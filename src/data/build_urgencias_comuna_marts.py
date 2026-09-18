"""Construye marts comunales históricos de atenciones de Urgencia DEIS.

Los marts agregan conteos de atenciones (no personas) para 2021--2025. No
generan semanas ni meses ausentes, ni sustituyen la ausencia de una causa por
cero. El calendario semanal conserva la codificación publicada por DEIS.

Ambos marts incorporan tasas de atenciones por 10.000 habitantes usando como
denominador `dim_poblacion_comuna_anual.parquet` (INE, estimaciones y
proyecciones 2002-2035 base Censo 2017; ver
`src/data/clean_poblacion_proyecciones.py`). Esa dimensión es anual: el mart
mensual reutiliza la misma población para los 12 meses de un año y el
semanal reutiliza la misma población para todas las semanas de un año, sin
interpolar. Estas tasas cuantifican atenciones (evento), no personas únicas
atendidas; no representan porcentaje de población atendida ni deben
interpretarse como prevalencia o incidencia.

Este módulo también expone las funciones reutilizables de carga (
`load_urgencias_source`), agregación (`aggregate_grain`), ratios
(`add_ratios`), escritura atómica (`atomic_write`) y validación de jerarquía
causal (`validate_non_negative`, `validate_causal_hierarchy`,
`validate_ratios`) que consumen `src/data/build_urgencias_establecimiento_mart.py`
y `src/data/build_urgencias_comuna_etario_mart.py`, para no duplicar la
lógica de agregación/validación de Urgencias entre marts.
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
POBLACION_ANUAL_PATH: Final[Path] = Path("data/processed/censo/dim_poblacion_comuna_anual.parquet")
RATE_CAUSES: Final[tuple[int, ...]] = (1, 35, 36)
RATE_COLUMNS: Final[tuple[str, ...]] = tuple(
    f"tasa_atenciones_id{cause}_por_10000" for cause in RATE_CAUSES
)


def load_poblacion_anual(path: Path = POBLACION_ANUAL_PATH) -> pd.DataFrame:
    """Lee la dimensión anual de población comunal y valida su grano/positividad."""
    table = pq.read_table(path, columns=["comuna_codigo", "ano", "poblacion"])
    frame = table.to_pandas()
    frame["ano"] = frame["ano"].astype("int64")
    if frame.duplicated(["comuna_codigo", "ano"]).any():
        raise ValueError("Dimensión de población anual con grano duplicado (comuna_codigo, ano).")
    if (frame["poblacion"] <= 0).any():
        raise ValueError("Población anual no positiva en la dimensión de población.")
    return frame.rename(columns={"poblacion": "poblacion_anual"})


def _add_tasas(mart: pd.DataFrame, poblacion_anual: pd.DataFrame) -> pd.DataFrame:
    """Une la población anual (misma cifra para todo el año) y calcula tasas por 10.000 hab."""
    merged = mart.merge(
        poblacion_anual, on=["comuna_codigo", "ano"], how="left", validate="many_to_one"
    )
    if merged["poblacion_anual"].isna().any():
        missing = (
            merged.loc[merged["poblacion_anual"].isna(), ["comuna_codigo", "ano"]]
            .drop_duplicates()
            .to_dict("records")
        )
        raise ValueError(f"Sin denominador poblacional para comuna×año: {missing}")
    for cause in RATE_CAUSES:
        merged[f"tasa_atenciones_id{cause}_por_10000"] = (
            merged[f"atenciones_id{cause}"].div(merged["poblacion_anual"]) * 10_000
        )
    return merged


BASE_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "ano", "semana", "fecha", "comuna_codigo", "comuna_glosa",
    "establecimiento_codigo", "id_causa", "total",
)


def load_urgencias_source(
    input_dir: Path = INPUT_DIR, extra_columns: tuple[str, ...] = ()
) -> pd.DataFrame:
    """Lee sólo los IDs y las columnas requeridas desde los Parquet históricos.

    `extra_columns` permite a los marts de establecimiento/etario pedir
    columnas adicionales (p. ej. `establecimiento_glosa` o los desgloses
    etarios) sin duplicar la lectura filtrada por `id_causa`.
    """
    files = [input_dir / f"urgencias_rm_{year}.parquet" for year in YEARS]
    absent = [path.as_posix() for path in files if not path.is_file()]
    if absent:
        raise FileNotFoundError(f"Parquet de Urgencias no disponible: {absent}")
    columns = list(BASE_SOURCE_COLUMNS) + [
        column for column in extra_columns if column not in BASE_SOURCE_COLUMNS
    ]
    dataset = ds.dataset(files, format="parquet")
    table = dataset.to_table(
        filter=pc.field("id_causa").isin(CAUSES),
        columns=columns,
    )
    source = table.to_pandas()
    source["fecha"] = pd.to_datetime(source["fecha"], dayfirst=True)
    return source


def aggregate_grain(
    source: pd.DataFrame,
    grain_columns: list[str],
    attribute_columns: tuple[str, ...] = ("comuna_codigo", "comuna_glosa"),
    include_reporters: bool = True,
) -> pd.DataFrame:
    """Agrega causas (y, opcionalmente, establecimientos reportantes) a un grano dado.

    `attribute_columns` son columnas que dependen funcionalmente del grano
    (p. ej. `comuna_glosa` de `comuna_codigo`, o `establecimiento_glosa` de
    `establecimiento_codigo`) y se preservan sin fragmentar el grano.
    `include_reporters` se desactiva para grillas donde el conteo de
    establecimientos reportantes no aplica (grano ya es establecimiento, o
    grano etario sin ese desglose).
    """
    required = set(grain_columns) | set(attribute_columns) | {"id_causa", "total"}
    if include_reporters:
        required |= {"establecimiento_codigo"}
    if missing := required - set(source.columns):
        raise ValueError(f"Columnas faltantes en Urgencias: {sorted(missing)}")
    if not source["id_causa"].isin(CAUSES).all():
        raise ValueError("El origen contiene IDs fuera del contrato del mart.")

    keys = grain_columns + list(attribute_columns) + ["id_causa"]
    agg_spec = {"atenciones": ("total", "sum")}
    if include_reporters:
        agg_spec["establecimientos_reportantes"] = ("establecimiento_codigo", "nunique")
    aggregated = source.groupby(keys, as_index=False).agg(**agg_spec)
    index = grain_columns + list(attribute_columns)
    counts = aggregated.pivot(
        index=index, columns="id_causa", values="atenciones"
    ).rename(columns=lambda cause: f"atenciones_id{cause}")
    if include_reporters:
        reporters = aggregated[aggregated["id_causa"].isin([1, 36])].pivot(
            index=index, columns="id_causa", values="establecimientos_reportantes"
        ).rename(
            columns={
                1: "n_establecimientos_reportantes_id1",
                36: "n_establecimientos_reportantes_id36",
            }
        )
        mart = counts.join(reporters, how="outer").reset_index()
    else:
        mart = counts.reset_index()
    for column in COUNT_COLUMNS:
        if column not in mart:
            mart[column] = pd.NA
    if include_reporters:
        for column in [
            "n_establecimientos_reportantes_id1",
            "n_establecimientos_reportantes_id36",
        ]:
            if column not in mart:
                mart[column] = pd.NA
    return mart


def add_ratios(mart: pd.DataFrame) -> pd.DataFrame:
    """Calcula razones de atenciones; denominadores cero o ausentes dan nulo."""
    result = mart.copy()
    for name, (numerator, denominator) in RATIO_SPECS.items():
        result[name] = result[numerator].div(result[denominator]).where(
            result[denominator].gt(0)
        )
    return result


def build_weekly_mart(
    source: pd.DataFrame, poblacion_anual: pd.DataFrame | None = None
) -> pd.DataFrame:
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
    mart = aggregate_grain(working, ["ano", "semana"])
    mart = mart.merge(starts, on=["ano", "semana"], how="left", validate="many_to_one")
    mart["fecha_inicio_semana"] = mart["fecha_inicio_semana"].dt.date.astype(str)
    mart = add_ratios(mart)
    poblacion_anual = load_poblacion_anual() if poblacion_anual is None else poblacion_anual
    mart = _add_tasas(mart, poblacion_anual)
    ordered = ["comuna_codigo", "comuna_glosa", "fecha_inicio_semana", "ano", "semana"]
    return mart.sort_values(ordered).reset_index(drop=True)


def build_monthly_mart(
    source: pd.DataFrame, poblacion_anual: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Construye el mart comuna×mes a partir de las fechas diarias DEIS."""
    if "fecha" not in source:
        raise ValueError("Columna faltante para mes: fecha")
    working = source.copy()
    working["fecha"] = pd.to_datetime(working["fecha"])
    working["mes"] = working["fecha"].dt.month
    working["fecha_mes"] = working["fecha"].dt.to_period("M").dt.start_time
    mart = aggregate_grain(working, ["ano", "mes", "fecha_mes"])
    mart["fecha_mes"] = mart["fecha_mes"].dt.date.astype(str)
    mart = add_ratios(mart)
    poblacion_anual = load_poblacion_anual() if poblacion_anual is None else poblacion_anual
    mart = _add_tasas(mart, poblacion_anual)
    ordered = ["comuna_codigo", "comuna_glosa", "fecha_mes"]
    return mart.sort_values(ordered).reset_index(drop=True)


def validate_non_negative(mart: pd.DataFrame, columns: list[str] | None = None) -> None:
    """Verifica que las columnas de conteo (por defecto `COUNT_COLUMNS`) no sean negativas."""
    columns = list(COUNT_COLUMNS) if columns is None else columns
    if mart[columns].lt(0).any().any():
        raise ValueError("Se detectaron atenciones negativas.")


def validate_causal_hierarchy(mart: pd.DataFrame) -> None:
    """Verifica ID36 = ID37+...+ID41 (donde la jerarquía está completa) y ID36 <= ID1."""
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


def validate_ratios(mart: pd.DataFrame) -> None:
    """Verifica que los ratios de `RATIO_SPECS` estén en [0, 1] y nulos si el denominador no es positivo."""
    for ratio, (_, denominator) in RATIO_SPECS.items():
        values = mart[ratio].dropna()
        if not values.between(0, 1).all():
            raise ValueError(f"Ratio fuera de [0, 1]: {ratio}")
        if not mart.loc[mart[denominator].le(0), ratio].isna().all():
            raise ValueError(f"Ratio definido con denominador no positivo: {ratio}")


def validate_mart(mart: pd.DataFrame, grain: str) -> None:
    """Valida contrato, jerarquía de causas, ratios y reportantes del mart."""
    grain_keys = (
        ["comuna_codigo", "fecha_inicio_semana", "ano", "semana"]
        if grain == "weekly"
        else ["comuna_codigo", "fecha_mes"]
    )
    if mart.duplicated(grain_keys).any():
        raise ValueError(f"Grano {grain} no único.")
    validate_non_negative(mart)
    validate_causal_hierarchy(mart)
    validate_ratios(mart)
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
    if "poblacion_anual" not in mart.columns:
        raise ValueError("Falta la columna poblacion_anual: el enriquecimiento de tasas no se aplicó.")
    if mart["poblacion_anual"].isna().any() or (mart["poblacion_anual"] <= 0).any():
        raise ValueError("poblacion_anual nula o no positiva en el mart.")
    for rate_column in RATE_COLUMNS:
        if rate_column not in mart.columns:
            raise ValueError(f"Falta la columna de tasa esperada: {rate_column}")
        if (mart[rate_column].dropna() < 0).any():
            raise ValueError(f"Tasa negativa detectada: {rate_column}")


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


def atomic_write(frame: pd.DataFrame, output_path: Path) -> None:
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
    poblacion_anual = load_poblacion_anual()
    weekly = build_weekly_mart(source, poblacion_anual)
    monthly = build_monthly_mart(source, poblacion_anual)
    validate_mart(weekly, "weekly")
    validate_mart(monthly, "monthly")
    validate_reconciliation(weekly, monthly)
    atomic_write(weekly, WEEKLY_OUTPUT)
    atomic_write(monthly, MONTHLY_OUTPUT)
    print(
        "Marts de Urgencias generados: "
        f"weekly={len(weekly):,} filas, monthly={len(monthly):,} filas."
    )


if __name__ == "__main__":
    main()
