"""Contraste anual de camas de psiquiatría de la RM desde dos fuentes independientes.

Compara, por año, cuántas camas estuvieron ocupadas en promedio según:

1. **Egresos F00-F99** de residentes de la RM: días de estada acotados al año
   del egreso (`dias_estada_acotado_anual`) divididos por los días del año.
   Es una cota superior: Egresos publica el año, no la fecha, así que una
   estadía larga puede haber empezado el año anterior.
2. **REM-20**: días cama ocupados de las áreas de psiquiatría de los hospitales
   de la oferta RM, divididos por los días del año.

Si ambos caminos dan el mismo orden de magnitud, la escala de la propuesta de
camas (que usa REM-20) queda respaldada por una segunda fuente. No deben
coincidir exactamente y la tabla publica las variantes que explican la brecha:
- Egresos cuenta pacientes con diagnóstico psiquiátrico también en camas no
  psiquiátricas (p. ej. delirium en medicina interna), y de hospitales fuera
  del SNSS; por eso se publica también la variante solo SNSS.
- REM-20 cuenta las áreas forenses, cuyos pacientes rara vez egresan dentro
  del año; por eso se publica también la variante sin forense.
- Egresos ubica al paciente por residencia y REM-20 por hospital: la RM recibe
  pacientes de otras regiones en sus centros de referencia.
"""

from __future__ import annotations

import argparse
import calendar
import logging
import tempfile
from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data.build_egresos_f00_f99 import OUTPUT_PATH as EGRESOS_PATH
from src.data.build_mart_ocupacion_psiquiatria_hospital_rm import OUTPUT_PATH as OCUPACION_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH: Final[Path] = Path("data/processed/marts/contraste_camas_psiquiatria_rm.parquet")
SNSS: Final[str] = "Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS"
# Áreas forenses del REM-20 (adulto evaluación, adulto tratamiento, infanto-adolescente).
AREAS_FORENSES: Final[frozenset[int]] = frozenset({423, 424, 425, 426})
MESES_ANO: Final[int] = 12

SCHEMA: Final[pa.Schema] = pa.schema([
    ("ano", pa.int32()),
    ("egresos_residentes_rm", pa.int64()),
    ("camas_equivalentes_egresos", pa.float64()),
    ("camas_equivalentes_egresos_snss", pa.float64()),
    ("camas_ocupadas_rem20", pa.float64()),
    ("camas_ocupadas_rem20_sin_forense", pa.float64()),
    ("razon_egresos_snss_rem20_sin_forense", pa.float64()),
])


def camas_desde_egresos(egresos: pd.DataFrame) -> pd.DataFrame:
    """Camas ocupadas en promedio por año según los egresos de residentes RM."""
    rm = egresos[egresos["residente_rm"].fillna(False).astype(bool)]
    dias_ano = rm["ano_egreso"].map(lambda a: 366 if calendar.isleap(int(a)) else 365)
    rm = rm.assign(camas=rm["dias_estada_acotado_anual"] / dias_ano,
                   snss=rm["pertenencia_establecimiento_salud"] == SNSS)
    return pd.DataFrame({
        "egresos_residentes_rm": rm.groupby("ano_egreso").size(),
        "camas_equivalentes_egresos": rm.groupby("ano_egreso")["camas"].sum(),
        "camas_equivalentes_egresos_snss": rm[rm["snss"]].groupby("ano_egreso")["camas"].sum(),
    }).rename_axis("ano")


def camas_desde_rem20(ocupacion: pd.DataFrame) -> pd.DataFrame:
    """Camas ocupadas en promedio por año según REM-20, solo años con los 12 meses."""
    completos = ocupacion.groupby("ano")["mes"].nunique()
    anos = completos[completos == MESES_ANO].index
    ocupacion = ocupacion[ocupacion["ano"].isin(anos)]
    dias_ano = pd.Series({a: 366 if calendar.isleap(int(a)) else 365 for a in anos})
    sin_forense = ocupacion[~ocupacion["nivel_cuidado_codigo"].isin(AREAS_FORENSES)]
    return pd.DataFrame({
        "camas_ocupadas_rem20": ocupacion.groupby("ano")["dias_cama_ocupados"].sum() / dias_ano,
        "camas_ocupadas_rem20_sin_forense": sin_forense.groupby("ano")["dias_cama_ocupados"].sum() / dias_ano,
    }).rename_axis("ano")


def build_contraste(egresos: pd.DataFrame, ocupacion: pd.DataFrame) -> pd.DataFrame:
    """Años con ambas fuentes completas."""
    contraste = camas_desde_egresos(egresos).join(camas_desde_rem20(ocupacion), how="inner").reset_index()
    if contraste.empty:
        raise ValueError("No hay años con Egresos y REM-20 completos a la vez.")
    contraste["razon_egresos_snss_rem20_sin_forense"] = (
        contraste["camas_equivalentes_egresos_snss"] / contraste["camas_ocupadas_rem20_sin_forense"]
    )
    contraste["ano"] = contraste["ano"].astype("int32")
    contraste["egresos_residentes_rm"] = contraste["egresos_residentes_rm"].astype("int64")
    for columna in SCHEMA.names[2:]:
        contraste[columna] = contraste[columna].astype(float).round(1 if "razon" not in columna else 3)
    if (contraste[SCHEMA.names[2:]] <= 0).any().any():
        raise ValueError("Camas equivalentes no positivas: revisar insumos.")
    return contraste[SCHEMA.names]


def main() -> None:
    parser = argparse.ArgumentParser(description="Contraste anual de camas de psiquiatría RM: Egresos frente a REM-20.")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    egresos = pq.read_table(EGRESOS_PATH, columns=[
        "ano_egreso", "residente_rm", "pertenencia_establecimiento_salud", "dias_estada_acotado_anual",
    ]).to_pandas()
    ocupacion = pq.read_table(OCUPACION_PATH, columns=["ano", "mes", "nivel_cuidado_codigo", "dias_cama_ocupados"]).to_pandas()
    contraste = build_contraste(egresos, ocupacion)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=OUTPUT_PATH.parent, prefix=f"{OUTPUT_PATH.name}.", suffix=".tmp") as t:
        temporal = Path(t.name)
    pq.write_table(pa.Table.from_pandas(contraste, schema=SCHEMA, preserve_index=False), temporal)
    temporal.replace(OUTPUT_PATH)
    logger.info("Contraste de camas publicado (%s años):\n%s", len(contraste), contraste.to_string(index=False))


if __name__ == "__main__":
    main()
