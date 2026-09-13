"""Perfil reproducible de cobertura comuna-semana para Urgencias ID 36.

El perfil no crea una serie modelable ni rellena semanas: separa una semana
sin fila ID 36 de una semana observada cuyo total agregado es cero.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq


YEARS: Final[tuple[int, ...]] = tuple(range(2021, 2026))
CAUSE_CALENDAR: Final[int] = 1
CAUSE_SM: Final[int] = 36
INPUT_DIR: Final[Path] = Path("data/processed/urgencias")
OUTPUT_PATH: Final[Path] = (
    INPUT_DIR / "perfil_cobertura_sm_comuna_semanal_2021_2025.parquet"
)


def _consecutive_run(values: list[bool], target: bool) -> int:
    """Devuelve la mayor corrida consecutiva de ``target`` en ``values``."""
    best = 0
    current = 0
    for value in values:
        if value == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def build_profile(
    calendar_source: pd.DataFrame, sm_source: pd.DataFrame
) -> pd.DataFrame:
    """Construye el perfil a partir de filas ID 1 e ID 36 ya seleccionadas.

    ``calendar_source`` usa ID 1 solamente para preservar el calendario DEIS y
    el universo de comunas que reportó actividad general. ``sm_source`` es el
    único insumo para los conteos de salud mental.
    """
    required_calendar = {
        "ano", "semana", "fecha", "comuna_codigo", "comuna_glosa"
    }
    required_sm = required_calendar | {"establecimiento_codigo", "total"}
    if missing := required_calendar - set(calendar_source.columns):
        raise ValueError(f"Columnas faltantes en calendario: {sorted(missing)}")
    if missing := required_sm - set(sm_source.columns):
        raise ValueError(f"Columnas faltantes en ID 36: {sorted(missing)}")

    calendar = calendar_source.copy()
    calendar["fecha"] = pd.to_datetime(calendar["fecha"], dayfirst=True)
    calendar = (
        calendar.groupby(["ano", "semana"], as_index=False)
        .agg(inicio_semana=("fecha", "min"), fin_semana=("fecha", "max"))
        .sort_values(["inicio_semana", "ano", "semana"])
        .reset_index(drop=True)
    )
    if calendar.empty:
        raise ValueError("No hay semanas DEIS para el período solicitado.")

    communes = (
        calendar_source[["comuna_codigo", "comuna_glosa"]]
        .drop_duplicates()
        .sort_values(["comuna_codigo", "comuna_glosa"])
        .reset_index(drop=True)
    )
    if communes.empty:
        raise ValueError("No hay comunas con reporte general para el período.")

    sm = sm_source.copy()
    sm["fecha"] = pd.to_datetime(sm["fecha"], dayfirst=True)
    weekly = (
        sm.groupby(["ano", "semana", "comuna_codigo", "comuna_glosa"], as_index=False)
        .agg(
            atenciones_sm=("total", "sum"),
            establecimientos=(
                "establecimiento_codigo", lambda values: frozenset(values.astype(str))
            ),
            inicio_semana_observada=("fecha", "min"),
            fin_semana_observada=("fecha", "max"),
        )
    )

    expected = communes.merge(calendar, how="cross")
    joined = expected.merge(
        weekly,
        on=["ano", "semana", "comuna_codigo", "comuna_glosa"],
        how="left",
        validate="one_to_one",
    ).sort_values(["comuna_codigo", "inicio_semana", "ano", "semana"])
    joined["con_reporte"] = joined["atenciones_sm"].notna()

    rows: list[dict[str, object]] = []
    for (code, name), group in joined.groupby(
        ["comuna_codigo", "comuna_glosa"], sort=True, dropna=False
    ):
        reported = group[group["con_reporte"]]
        weekly_counts = reported["atenciones_sm"]
        report_flags = group["con_reporte"].tolist()
        establishment_sets = reported["establecimientos"].tolist()
        composition_changes = sum(
            group.iloc[index]["establecimientos"]
            != group.iloc[index - 1]["establecimientos"]
            for index in range(1, len(group))
            if group.iloc[index]["con_reporte"]
            and group.iloc[index - 1]["con_reporte"]
        )
        zero_weeks = int((weekly_counts == 0).sum())
        total_reported_weeks = int(len(reported))
        expected_weeks = int(len(group))
        missing_weeks = expected_weeks - total_reported_weeks
        rows.append(
            {
                "comuna_codigo": code,
                "comuna_glosa": name,
                "inicio_observado": (
                    reported["inicio_semana_observada"].min().date().isoformat()
                    if not reported.empty else None
                ),
                "fin_observado": (
                    reported["fin_semana_observada"].max().date().isoformat()
                    if not reported.empty else None
                ),
                "semanas_calendario_esperadas": expected_weeks,
                "semanas_con_reporte": total_reported_weeks,
                "semanas_sin_reporte": missing_weeks,
                "proporcion_cobertura": total_reported_weeks / expected_weeks,
                "semanas_id36_cero": zero_weeks,
                "proporcion_ceros": (
                    zero_weeks / total_reported_weeks if total_reported_weeks else None
                ),
                "atenciones_sm_total": int(weekly_counts.sum()),
                "media_semanal": float(weekly_counts.mean()) if total_reported_weeks else None,
                "mediana_semanal": (
                    float(weekly_counts.median()) if total_reported_weeks else None
                ),
                "desviacion_estandar_semanal": (
                    float(weekly_counts.std(ddof=0)) if total_reported_weeks else None
                ),
                "establecimientos_reportantes": len(
                    set().union(*establishment_sets) if establishment_sets else set()
                ),
                "cambios_en_establecimientos": composition_changes,
                "numero_gaps_sin_reporte": sum(
                    not current and (index == 0 or report_flags[index - 1])
                    for index, current in enumerate(report_flags)
                ),
                "maximo_semanas_consecutivas_sin_reporte": _consecutive_run(
                    report_flags, False
                ),
                "maximo_semanas_consecutivas_con_reporte": _consecutive_run(
                    report_flags, True
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("comuna_codigo").reset_index(drop=True)


def load_sources(input_dir: Path = INPUT_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lee sólo ID 1 e ID 36, y sólo las columnas necesarias, desde Parquet."""
    files = [input_dir / f"urgencias_rm_{year}.parquet" for year in YEARS]
    absent = [path.as_posix() for path in files if not path.is_file()]
    if absent:
        raise FileNotFoundError(f"Parquet de Urgencias no disponible: {absent}")
    dataset = ds.dataset(files, format="parquet")
    columns = [
        "ano", "semana", "fecha", "comuna_codigo", "comuna_glosa",
        "establecimiento_codigo", "total",
    ]
    calendar = dataset.to_table(
        filter=pc.field("id_causa") == CAUSE_CALENDAR, columns=columns
    ).to_pandas()
    sm = dataset.to_table(
        filter=pc.field("id_causa") == CAUSE_SM, columns=columns
    ).to_pandas()
    return calendar, sm


def write_profile(profile: pd.DataFrame, output_path: Path = OUTPUT_PATH) -> None:
    """Publica el perfil tras validar un temporal, sin exponer un Parquet parcial."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.unlink(missing_ok=True)
    table = pa.Table.from_pandas(profile, preserve_index=False)
    pq.write_table(table, temporary, compression="snappy")
    if not pq.read_schema(temporary).names:
        raise ValueError("El perfil temporal no contiene columnas.")
    temporary.replace(output_path)


def main() -> None:
    """Genera el perfil canónico para 2021--2025, sin incorporar 2026."""
    calendar, sm = load_sources()
    profile = build_profile(calendar, sm)
    write_profile(profile)
    print(
        "Perfil ID 36 generado: "
        f"{len(profile)} comunas, "
        f"{profile['semanas_calendario_esperadas'].iloc[0]} semanas DEIS por comuna."
    )


if __name__ == "__main__":
    main()
