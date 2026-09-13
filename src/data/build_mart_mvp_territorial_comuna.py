"""Construye el mart canónico MVP territorial a nivel comuna (RM).

Integra, en una única fila por comuna, evidencia ya validada de cinco fuentes
independientes con temporalidades distintas que este mart mantiene explícitas
en lugar de mezclarlas:

- **Demanda de Urgencia, corte anual CERRADO 2025** (`ano_demanda=2025`):
  atenciones ID1/ID35/ID36 agregadas desde
  `mart_urgencias_comuna_monthly.parquet` (suma de los 12 meses, nunca
  promedio/suma de tasas ya calculadas) y establecimientos reportantes únicos
  anuales derivados directamente de `urgencias_rm_2025.parquet` (un `nunique`
  mensual no puede sumarse entre meses sin duplicar establecimientos que
  reportan en más de un mes). Las tasas por 10.000 habitantes se recalculan
  aquí como `atenciones_2025 / poblacion_2025 * 10.000`, no se agregan tasas
  mensuales ya calculadas.
- **Población proyectada 2025** (`ano_poblacion=2025`,
  `dim_poblacion_comuna_anual.parquet`, INE base Censo 2017) y **población
  efectivamente censada 2024** (`ano_censo=2024`,
  `dim_poblacion_comuna_censo2024.parquet`): dos semánticas poblacionales
  distintas que este mart nunca combina ni sustituye una por otra.
- **Vulnerabilidad socioeconómica, período único CERRADO 2022**
  (`ano_vulnerabilidad=2022`, `dim_vulnerabilidad_comuna.parquet`, tasa de
  pobreza por ingresos Casen/SAE): un indicador estático que este mart no
  presenta como si describiera 2025.
- **Oferta de urgencia, snapshot ACTUAL** (`oferta_temporalidad`,
  `dim_oferta_urgencia_rm.parquet`, 174 establecimientos vigentes): no es una
  serie histórica ni representa la oferta vigente en 2025.

El universo de 52 comunas RM proviene de `dim_poblacion_comuna_censo2024`
(dimensión ya validada exactamente contra el CUT oficial RM), no de
Urgencias: una comuna sin ninguna fila de Urgencias en 2025 (Vitacura,
`13132`, según evidencia observada en `mart_urgencias_comuna_monthly`) sigue
presente en el mart con `tiene_reporte_urgencias=False` y sus métricas de
demanda en NULL, nunca en cero. La oferta y la vulnerabilidad, en cambio, no
dependen del reporte de Urgencias y están completas para las 52 comunas.

Este mart no calcula accesibilidad, centroides, distancias, isócronas,
cobertura poblacional ni scores compuestos: es exclusivamente la integración
tabular comunal de fuentes ya construidas y validadas.
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

from src.data.clean_censo_comunas import EXPECTED_RM_CUTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

UNIVERSO_PATH: Final[Path] = Path("data/processed/censo/dim_poblacion_comuna_censo2024.parquet")
MONTHLY_MART_PATH: Final[Path] = Path("data/processed/marts/mart_urgencias_comuna_monthly.parquet")
URGENCIAS_2025_PATH: Final[Path] = Path("data/processed/urgencias/urgencias_rm_2025.parquet")
POBLACION_ANUAL_PATH: Final[Path] = Path("data/processed/censo/dim_poblacion_comuna_anual.parquet")
VULNERABILIDAD_PATH: Final[Path] = Path("data/processed/pobreza/dim_vulnerabilidad_comuna.parquet")
OFERTA_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
OUTPUT_PATH: Final[Path] = Path("data/processed/marts/mart_mvp_territorial_comuna.parquet")

ANO_DEMANDA: Final[int] = 2025
ANO_POBLACION: Final[int] = 2025
ANO_CENSO: Final[int] = 2024
OFERTA_TEMPORALIDAD: Final[str] = "snapshot_actual"

DEMAND_CAUSES: Final[tuple[int, ...]] = (1, 35, 36)
SAPU_PATTERN: Final[str] = r"\(SAPU\)$"
SAR_PATTERN: Final[str] = r"\(SAR\)$"
SUR_PATTERN: Final[str] = r"\(SUR\)$"
CRITERIO_EXCEPCION: Final[str] = "excepcion_cear_documentada"

SCHEMA: Final[pa.Schema] = pa.schema([
    ("comuna_codigo", pa.string()),
    ("comuna_glosa", pa.string()),
    ("ano_demanda", pa.int32()),
    ("tiene_reporte_urgencias", pa.bool_()),
    ("atenciones_id1_2025", pa.int64()),
    ("atenciones_id35_2025", pa.int64()),
    ("atenciones_id36_2025", pa.int64()),
    ("n_establecimientos_reportantes_id1_2025", pa.int64()),
    ("n_establecimientos_reportantes_id36_2025", pa.int64()),
    ("tasa_atenciones_id1_2025_por_10000", pa.float64()),
    ("tasa_atenciones_id35_2025_por_10000", pa.float64()),
    ("tasa_atenciones_id36_2025_por_10000", pa.float64()),
    ("ano_poblacion", pa.int32()),
    ("poblacion_2025", pa.int64()),
    ("ano_censo", pa.int32()),
    ("poblacion_censada_2024", pa.int64()),
    ("ano_vulnerabilidad", pa.int32()),
    ("indicador_vulnerabilidad", pa.float64()),
    ("nombre_indicador_vulnerabilidad", pa.string()),
    ("direccion_indicador_vulnerabilidad", pa.string()),
    ("intervalo_confianza_inferior_vulnerabilidad", pa.float64()),
    ("intervalo_confianza_superior_vulnerabilidad", pa.float64()),
    ("tipo_estimacion_sae", pa.string()),
    ("oferta_temporalidad", pa.string()),
    ("n_oferta_urgencia_actual", pa.int64()),
    ("n_hospitales", pa.int64()),
    ("n_sapu", pa.int64()),
    ("n_sar", pa.int64()),
    ("n_sur", pa.int64()),
    ("n_otras_excepciones", pa.int64()),
    ("n_oferta_con_coordenadas", pa.int64()),
    ("proporcion_oferta_con_coordenadas", pa.float64()),
])


def load_universo_comunal(path: Path = UNIVERSO_PATH) -> pd.DataFrame:
    """Lee el catálogo comunal RM ya validado (52 comunas), independiente de Urgencias."""
    frame = pq.read_table(path, columns=["comuna_codigo", "comuna_glosa"]).to_pandas()
    if frame["comuna_codigo"].duplicated().any():
        raise ValueError("comuna_codigo duplicado en el universo comunal.")
    if set(frame["comuna_codigo"]) != {str(cut) for cut in EXPECTED_RM_CUTS}:
        raise ValueError("El universo comunal no coincide exactamente con el CUT oficial RM (52 comunas).")
    return frame


def load_demanda_2025(path: Path = MONTHLY_MART_PATH, ano: int = ANO_DEMANDA) -> pd.DataFrame:
    """Agrega atenciones ID1/ID35/ID36 desde el mart mensual (suma de 12 meses, nunca de tasas)."""
    columns = ["comuna_codigo", "ano"] + [f"atenciones_id{c}" for c in DEMAND_CAUSES]
    frame = pq.read_table(path, columns=columns).to_pandas()
    yearly = frame[frame["ano"] == ano]
    if yearly.empty:
        raise ValueError(f"Sin filas de demanda para el año {ano} en {path.as_posix()}.")
    aggregated = (
        yearly.groupby("comuna_codigo", as_index=False)[[f"atenciones_id{c}" for c in DEMAND_CAUSES]]
        .sum(min_count=1)
        .rename(columns={f"atenciones_id{c}": f"atenciones_id{c}_{ano}" for c in DEMAND_CAUSES})
    )
    return aggregated


def load_reportantes_unicos_2025(
    path: Path = URGENCIAS_2025_PATH, ano: int = ANO_DEMANDA
) -> pd.DataFrame:
    """Deriva reportantes únicos anuales desde el processed de Urgencias (nunca desde el mensual).

    Un `nunique` mensual no puede sumarse entre meses: un mismo establecimiento
    que reporta en varios meses del año se contaría varias veces. Este conteo
    se calcula directamente sobre las filas anuales de Urgencias 2025.
    """
    if not path.is_file():
        raise FileNotFoundError(f"No existe el processed de Urgencias requerido: {path.as_posix()}")
    frame = pq.read_table(
        path, columns=["ano", "comuna_codigo", "establecimiento_codigo", "id_causa"]
    ).to_pandas()
    frame = frame[(frame["ano"] == ano) & (frame["id_causa"].isin([1, 36]))]
    grouped = (
        frame.groupby(["comuna_codigo", "id_causa"])["establecimiento_codigo"]
        .nunique()
        .unstack("id_causa")
        .rename(
            columns={
                1: f"n_establecimientos_reportantes_id1_{ano}",
                36: f"n_establecimientos_reportantes_id36_{ano}",
            }
        )
        .reset_index()
    )
    for column in (
        f"n_establecimientos_reportantes_id1_{ano}",
        f"n_establecimientos_reportantes_id36_{ano}",
    ):
        if column not in grouped:
            grouped[column] = pd.NA
    return grouped


def load_poblacion_2025(path: Path = POBLACION_ANUAL_PATH, ano: int = ANO_POBLACION) -> pd.DataFrame:
    """Lee la población proyectada INE del año de demanda (`poblacion_2025`)."""
    frame = pq.read_table(path, columns=["comuna_codigo", "ano", "poblacion"]).to_pandas()
    yearly = frame[frame["ano"] == ano].drop(columns="ano").rename(columns={"poblacion": f"poblacion_{ano}"})
    if yearly.duplicated("comuna_codigo").any():
        raise ValueError(f"comuna_codigo duplicado en población anual {ano}.")
    return yearly


def load_poblacion_censada_2024(path: Path = UNIVERSO_PATH, ano: int = ANO_CENSO) -> pd.DataFrame:
    """Lee la población efectivamente censada 2024 (semántica distinta de la proyección anual)."""
    frame = pq.read_table(path, columns=["comuna_codigo", "poblacion_censada"]).to_pandas()
    return frame.rename(columns={"poblacion_censada": f"poblacion_censada_{ano}"})


def load_vulnerabilidad(path: Path = VULNERABILIDAD_PATH) -> pd.DataFrame:
    """Lee la dimensión de vulnerabilidad (Casen 2022) y renombra columnas ambiguas."""
    frame = pq.read_table(
        path,
        columns=[
            "comuna_codigo", "ano_referencia", "indicador_vulnerabilidad", "nombre_indicador",
            "direccion_indicador", "intervalo_confianza_inferior", "intervalo_confianza_superior",
            "tipo_estimacion_sae",
        ],
    ).to_pandas()
    if frame.duplicated("comuna_codigo").any():
        raise ValueError("comuna_codigo duplicado en la dimensión de vulnerabilidad.")
    return frame.rename(columns={
        "ano_referencia": "ano_vulnerabilidad",
        "nombre_indicador": "nombre_indicador_vulnerabilidad",
        "direccion_indicador": "direccion_indicador_vulnerabilidad",
        "intervalo_confianza_inferior": "intervalo_confianza_inferior_vulnerabilidad",
        "intervalo_confianza_superior": "intervalo_confianza_superior_vulnerabilidad",
    })


def load_oferta_agregada(path: Path = OFERTA_PATH, universo: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrega el snapshot ACTUAL de oferta de urgencia por comuna (no serie 2025)."""
    frame = pq.read_table(
        path, columns=["comuna_codigo", "tipo_establecimiento", "criterio_inclusion_oferta", "latitud"]
    ).to_pandas()

    comunas = sorted(set(frame["comuna_codigo"]) | (set(universo["comuna_codigo"]) if universo is not None else set()))
    base = pd.Series(0, index=pd.Index(comunas, name="comuna_codigo"), dtype="int64")

    def _count(mask: pd.Series) -> pd.Series:
        counted = frame.loc[mask].groupby("comuna_codigo").size()
        return base.add(counted, fill_value=0).astype("int64")

    is_excepcion = frame["criterio_inclusion_oferta"] == CRITERIO_EXCEPCION
    n_total = _count(pd.Series(True, index=frame.index))
    n_hospitales = _count(frame["tipo_establecimiento"].eq("Hospital") & ~is_excepcion)
    n_sapu = _count(frame["tipo_establecimiento"].str.contains(SAPU_PATTERN, regex=True, na=False) & ~is_excepcion)
    n_sar = _count(frame["tipo_establecimiento"].str.contains(SAR_PATTERN, regex=True, na=False) & ~is_excepcion)
    n_sur = _count(frame["tipo_establecimiento"].str.contains(SUR_PATTERN, regex=True, na=False) & ~is_excepcion)
    n_otras = _count(is_excepcion)
    n_con_coords = _count(frame["latitud"].notna())

    aggregated = pd.DataFrame({
        "n_oferta_urgencia_actual": n_total,
        "n_hospitales": n_hospitales,
        "n_sapu": n_sapu,
        "n_sar": n_sar,
        "n_sur": n_sur,
        "n_otras_excepciones": n_otras,
        "n_oferta_con_coordenadas": n_con_coords,
    }).reset_index()
    aggregated["proporcion_oferta_con_coordenadas"] = (
        aggregated["n_oferta_con_coordenadas"]
        .div(aggregated["n_oferta_urgencia_actual"])
        .where(aggregated["n_oferta_urgencia_actual"].gt(0))
    )
    return aggregated


def build_mart_mvp_territorial_comuna(
    universo_path: Path = UNIVERSO_PATH,
    monthly_path: Path = MONTHLY_MART_PATH,
    urgencias_2025_path: Path = URGENCIAS_2025_PATH,
    poblacion_anual_path: Path = POBLACION_ANUAL_PATH,
    vulnerabilidad_path: Path = VULNERABILIDAD_PATH,
    oferta_path: Path = OFERTA_PATH,
) -> pd.DataFrame:
    """Integra las cinco fuentes ya validadas en un mart de una fila por comuna RM."""
    universo = load_universo_comunal(universo_path)
    demanda = load_demanda_2025(monthly_path)
    reportantes = load_reportantes_unicos_2025(urgencias_2025_path)
    poblacion_2025 = load_poblacion_2025(poblacion_anual_path)
    poblacion_censo = load_poblacion_censada_2024(universo_path)
    vulnerabilidad = load_vulnerabilidad(vulnerabilidad_path)
    oferta = load_oferta_agregada(oferta_path, universo=universo)

    mart = universo.merge(demanda, on="comuna_codigo", how="left", validate="one_to_one")
    mart = mart.merge(reportantes, on="comuna_codigo", how="left", validate="one_to_one")
    mart["tiene_reporte_urgencias"] = mart["atenciones_id1_2025"].notna()

    mart = mart.merge(poblacion_2025, on="comuna_codigo", how="left", validate="one_to_one")
    mart = mart.merge(poblacion_censo, on="comuna_codigo", how="left", validate="one_to_one")
    mart = mart.merge(vulnerabilidad, on="comuna_codigo", how="left", validate="one_to_one")
    mart = mart.merge(oferta, on="comuna_codigo", how="left", validate="one_to_one")

    for cause in DEMAND_CAUSES:
        rate_col = f"tasa_atenciones_id{cause}_{ANO_DEMANDA}_por_10000"
        count_col = f"atenciones_id{cause}_{ANO_DEMANDA}"
        mart[rate_col] = mart[count_col].div(mart[f"poblacion_{ANO_POBLACION}"]) * 10_000

    mart["ano_demanda"] = ANO_DEMANDA
    mart["ano_poblacion"] = ANO_POBLACION
    mart["ano_censo"] = ANO_CENSO
    mart["oferta_temporalidad"] = OFERTA_TEMPORALIDAD

    for column in (
        f"atenciones_id1_{ANO_DEMANDA}", f"atenciones_id35_{ANO_DEMANDA}", f"atenciones_id36_{ANO_DEMANDA}",
        f"n_establecimientos_reportantes_id1_{ANO_DEMANDA}", f"n_establecimientos_reportantes_id36_{ANO_DEMANDA}",
    ):
        mart[column] = mart[column].astype("Int64")

    mart = mart.rename(columns={f"poblacion_{ANO_POBLACION}": "poblacion_2025"})
    mart = mart[[field.name for field in SCHEMA]].sort_values("comuna_codigo").reset_index(drop=True)
    return mart


def validate_mart(mart: pd.DataFrame, monthly_path: Path = MONTHLY_MART_PATH, oferta_path: Path = OFERTA_PATH) -> None:
    """Valida grano, cobertura, reconciliaciones y tratamiento NULL-no-cero."""
    expected_cuts = {str(cut) for cut in EXPECTED_RM_CUTS}

    if len(mart) != 52:
        raise ValueError(f"Se esperaban 52 filas (52 comunas RM); se obtuvieron {len(mart)}.")
    if mart["comuna_codigo"].duplicated().any():
        raise ValueError("comuna_codigo duplicado en el mart.")
    if set(mart["comuna_codigo"]) != expected_cuts:
        raise ValueError("El mart no cubre exactamente las 52 comunas RM del CUT oficial.")

    mandatory_no_null = [
        "comuna_codigo", "comuna_glosa", "ano_demanda", "tiene_reporte_urgencias",
        "ano_poblacion", "poblacion_2025", "ano_censo", "poblacion_censada_2024",
        "ano_vulnerabilidad", "indicador_vulnerabilidad", "nombre_indicador_vulnerabilidad",
        "direccion_indicador_vulnerabilidad", "intervalo_confianza_inferior_vulnerabilidad",
        "intervalo_confianza_superior_vulnerabilidad", "tipo_estimacion_sae",
        "oferta_temporalidad", "n_oferta_urgencia_actual", "n_hospitales", "n_sapu",
        "n_sar", "n_sur", "n_otras_excepciones", "n_oferta_con_coordenadas",
    ]
    for column in mandatory_no_null:
        if mart[column].isna().any():
            raise ValueError(f"Columna obligatoria con nulos inesperados: {column}")

    if (mart["poblacion_2025"] <= 0).any():
        raise ValueError("poblacion_2025 no positiva en al menos una comuna.")
    if (mart["poblacion_censada_2024"] <= 0).any():
        raise ValueError("poblacion_censada_2024 no positiva en al menos una comuna.")

    for constant_col, expected in (
        ("ano_demanda", ANO_DEMANDA), ("ano_poblacion", ANO_POBLACION),
        ("ano_censo", ANO_CENSO), ("ano_vulnerabilidad", 2022),
        ("oferta_temporalidad", OFERTA_TEMPORALIDAD),
    ):
        if not (mart[constant_col] == expected).all():
            raise ValueError(f"Campo de temporalidad no constante o incorrecto: {constant_col}")

    demand_cols = [f"atenciones_id{c}_2025" for c in DEMAND_CAUSES]
    rate_cols = [f"tasa_atenciones_id{c}_2025_por_10000" for c in DEMAND_CAUSES]
    reporter_cols = ["n_establecimientos_reportantes_id1_2025", "n_establecimientos_reportantes_id36_2025"]
    sin_reporte = ~mart["tiene_reporte_urgencias"]
    con_reporte = mart["tiene_reporte_urgencias"]
    for column in demand_cols + rate_cols + reporter_cols:
        if mart.loc[sin_reporte, column].notna().any():
            raise ValueError(f"Comuna sin reporte de Urgencias con {column} distinto de NULL (no debe imputarse cero).")
        if mart.loc[con_reporte, column].isna().any():
            raise ValueError(f"Comuna con reporte de Urgencias tiene {column} nulo inesperadamente.")

    for column in demand_cols + reporter_cols:
        if (mart.loc[con_reporte, column] < 0).any():
            raise ValueError(f"Valor negativo inesperado en {column}.")

    if not (
        mart.loc[con_reporte, "n_establecimientos_reportantes_id36_2025"]
        <= mart.loc[con_reporte, "n_establecimientos_reportantes_id1_2025"]
    ).all():
        raise ValueError("Reportantes ID36 exceden el universo ID1 en 2025.")
    if not (
        mart.loc[con_reporte, "atenciones_id36_2025"] <= mart.loc[con_reporte, "atenciones_id1_2025"]
    ).all():
        raise ValueError("atenciones_id36_2025 excede atenciones_id1_2025.")

    for count_col, rate_col in zip(demand_cols, rate_cols):
        recomputed = (
            mart.loc[con_reporte, count_col].astype("float64")
            / mart.loc[con_reporte, "poblacion_2025"].astype("float64")
            * 10_000
        )
        if not np.allclose(recomputed.to_numpy(), mart.loc[con_reporte, rate_col].to_numpy()):
            raise ValueError(f"{rate_col} no reconcilia con {count_col}/poblacion_2025*10000.")

    tipo_sum = mart[["n_hospitales", "n_sapu", "n_sar", "n_sur", "n_otras_excepciones"]].sum(axis=1)
    if not (tipo_sum == mart["n_oferta_urgencia_actual"]).all():
        raise ValueError("La suma de tipos de oferta no reconcilia con n_oferta_urgencia_actual.")
    if int(mart["n_oferta_con_coordenadas"].sum()) > int(mart["n_oferta_urgencia_actual"].sum()):
        raise ValueError("n_oferta_con_coordenadas excede n_oferta_urgencia_actual agregado.")

    oferta_universe = pq.read_table(oferta_path, columns=["establecimiento_codigo"]).to_pandas()
    total_oferta_dim = len(oferta_universe)
    if int(mart["n_oferta_urgencia_actual"].sum()) != total_oferta_dim:
        raise ValueError(
            f"n_oferta_urgencia_actual agregado ({int(mart['n_oferta_urgencia_actual'].sum())}) "
            f"no reconcilia con dim_oferta_urgencia_rm ({total_oferta_dim})."
        )

    prop_valid = mart["proporcion_oferta_con_coordenadas"].dropna()
    if not prop_valid.between(0, 1).all():
        raise ValueError("proporcion_oferta_con_coordenadas fuera de [0, 1].")
    if not mart.loc[mart["n_oferta_urgencia_actual"].eq(0), "proporcion_oferta_con_coordenadas"].isna().all():
        raise ValueError("proporcion_oferta_con_coordenadas debe ser NULL cuando no hay oferta (denominador 0).")

    monthly = pq.read_table(
        monthly_path, columns=["comuna_codigo", "ano"] + [f"atenciones_id{c}" for c in DEMAND_CAUSES]
    ).to_pandas()
    monthly_totals = (
        monthly[monthly["ano"] == ANO_DEMANDA]
        .groupby("comuna_codigo", as_index=False)[[f"atenciones_id{c}" for c in DEMAND_CAUSES]]
        .sum(min_count=1)
    )
    check = mart.loc[con_reporte, ["comuna_codigo"] + demand_cols].merge(
        monthly_totals, on="comuna_codigo", how="inner", validate="one_to_one"
    )
    for cause, demand_col in zip(DEMAND_CAUSES, demand_cols):
        if not (check[demand_col] == check[f"atenciones_id{cause}"]).all():
            raise ValueError(f"{demand_col} no reconcilia con la suma mensual 2025 de mart_urgencias_comuna_monthly.")


def _atomic_write(mart: pd.DataFrame, output_path: Path = OUTPUT_PATH) -> None:
    """Escribe el Parquet final de forma atómica (temporal validado -> reemplazo)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(mart, schema=SCHEMA, preserve_index=False)
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
        description="Construye el mart canónico MVP territorial a nivel comuna (RM).",
    )
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()

    mart = build_mart_mvp_territorial_comuna()
    validate_mart(mart)
    _atomic_write(mart)

    logger.info(
        "Mart MVP territorial comunal generado: %s filas. Sin reporte de Urgencias 2025: %s. "
        "Oferta total reconciliada: %s.",
        len(mart),
        int((~mart["tiene_reporte_urgencias"]).sum()),
        int(mart["n_oferta_urgencia_actual"].sum()),
    )


if __name__ == "__main__":
    main()
