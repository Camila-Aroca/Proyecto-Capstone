"""Vincula cada hospital de la oferta de urgencia RM con sus camas de psiquiatría (SNSS).

Une, por la llave `establecimiento_codigo` (el código DEIS de 6 dígitos que comparten
ambas fuentes), los hospitales de `dim_oferta_urgencia_rm` con la dotación de camas
del SNSS (`dotacion_camas_snss.parquet`). No se cruza por nombre ni por el código
textual de Urgencias (`NN-NNN`, que en el RAW trae un espacio final): la dimensión de
oferta ya resolvió ese código contra el maestro de establecimientos.

Qué es "camas de psiquiatría": la suma de las áreas funcionales cuyo nombre contiene
"Psiquiatr" (adulto, infanto-adolescente, forense y cuidados intensivos en psiquiatría;
códigos 418-429 salvo 425/427). Se excluyen la fila `Total` (área 100) y el área
sociosanitaria, que no es psiquiatría. Es dotación anual declarada, no ocupación ni
disponibilidad en tiempo real.

Año de referencia: el último año con columna `camas_AAAA` en el Parquet de dotación,
detectado dinámicamente (nunca fijo en el código).

Qué hospitales alimentaron el modelo de demanda: el target es `atenciones_id36`, y
`reporto_id36_periodo` (heredado de `dim_oferta_urgencia_rm`) marca los que reportaron
ID36 > 0 al menos una vez en el período canónico 2021-2025. La dimensión conserva
todos los hospitales de la oferta para que el vínculo sea auditable, pero los totales
territoriales de camas deben usar solo `reporto_id36_periodo = True`: un hospital con
camas que nunca aportó ID36 (p. ej. el Hospital Psiquiátrico El Peral) no es parte
de la demanda modelada. Es "alguna vez en 2021-2025", no "todos los años".

Universo y nulos (nada se imputa):
- Una fila por hospital de la oferta (`tipo_establecimiento == "Hospital"`), con
  o sin dotación SNSS: así el vínculo es auditable y no se descarta nada en silencio.
- `en_dotacion_snss = False`: el hospital no figura en la dotación SNSS (p. ej. clínicas
  privadas o de las FF.AA.); sus camas quedan nulas, no en cero. La dotación de los
  establecimientos no SNSS es otro libro, "dato referencial", y no se mezcla aquí.
- `camas_psiquiatria` nula: el hospital está en la dotación pero no declara cifra en
  ningún área de psiquiatría ese año (sin área o celdas en blanco). No equivale a cero.
  Un cero declarado en el origen se conserva como 0.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import re
import tempfile
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DIM_OFERTA_PATH: Final[Path] = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
CAMAS_SNSS_PATH: Final[Path] = Path("data/processed/camas/dotacion_camas_snss.parquet")
OUTPUT_PATH: Final[Path] = Path("data/processed/camas/dim_camas_psiquiatria_hospital_rm.parquet")

TIPO_HOSPITAL: Final[str] = "Hospital"
AREA_TOTAL_CODIGO: Final[int] = 100  # fila "Total" del libro SNSS
AREA_PSIQUIATRIA: Final[re.Pattern[str]] = re.compile(r"Psiquiatr", re.IGNORECASE)
CAMAS_ANO: Final[re.Pattern[str]] = re.compile(r"^camas_(\d{4})$")
COMUNA_RM: Final[re.Pattern[str]] = re.compile(r"^13\d{3}$")

SCHEMA: Final[pa.Schema] = pa.schema([
    ("establecimiento_codigo", pa.int64()),
    ("establecimiento_nombre", pa.string()),
    ("comuna_codigo", pa.string()),
    ("en_dotacion_snss", pa.bool_()),
    ("reporto_id36_periodo", pa.bool_()),
    ("ano_camas", pa.int32()),
    ("camas_psiquiatria", pa.float64()),
    ("n_areas_psiquiatria", pa.int32()),
])


def ultimo_ano_camas(columnas: list[str]) -> int:
    """Último año con columna `camas_AAAA`; falla si el Parquet no trae ninguna."""
    anos = [int(m.group(1)) for c in columnas if (m := CAMAS_ANO.match(c))]
    if not anos:
        raise ValueError("La dotación de camas no tiene columnas `camas_AAAA`.")
    return max(anos)


def camas_psiquiatria_por_establecimiento(camas: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Suma de camas de las áreas de psiquiatría por establecimiento en `ano`.

    `camas_psiquiatria` es nula si ninguna área de psiquiatría declara cifra;
    `n_areas_psiquiatria` cuenta las áreas con cifra declarada.
    """
    columna = f"camas_{ano}"
    es_psiquiatria = camas["area_funcional"].fillna("").str.contains(AREA_PSIQUIATRIA)
    areas = camas[es_psiquiatria & (camas["area_funcional_codigo"] != AREA_TOTAL_CODIGO)]
    if areas.duplicated(["establecimiento_codigo", "area_funcional_codigo"]).any():
        raise ValueError("La dotación repite un área de psiquiatría por establecimiento.")
    agregado = areas.groupby("establecimiento_codigo")[columna].agg(
        camas_psiquiatria=lambda s: s.sum(min_count=1),
        n_areas_psiquiatria="count",
    )
    return agregado.reset_index()


def validate_dim(dim: pd.DataFrame, oferta_hospitales: int) -> None:
    """Controles previos a publicar; una violación detiene la etapa."""
    if len(dim) != oferta_hospitales:
        raise ValueError("La dimensión no conserva todos los hospitales de la oferta.")
    if dim["establecimiento_codigo"].duplicated().any():
        raise ValueError("`establecimiento_codigo` no es único.")
    if not dim["comuna_codigo"].fillna("").str.match(COMUNA_RM).all():
        raise ValueError("`comuna_codigo` fuera del formato 13xxx.")
    if dim["reporto_id36_periodo"].isna().any():
        raise ValueError("`reporto_id36_periodo` no puede ser nulo.")
    if dim["ano_camas"].nunique() != 1:
        raise ValueError("`ano_camas` debe ser único.")
    camas = dim["camas_psiquiatria"]
    if (camas.dropna() < 0).any():
        raise ValueError("`camas_psiquiatria` negativa.")
    if camas[~dim["en_dotacion_snss"]].notna().any():
        raise ValueError("Hospital fuera de la dotación SNSS con camas asignadas.")
    if (camas.notna() != (dim["n_areas_psiquiatria"] > 0)).any():
        raise ValueError("`camas_psiquiatria` incoherente con `n_areas_psiquiatria`.")


def build_dim_camas_psiquiatria_hospital_rm(
    oferta: pd.DataFrame, camas: pd.DataFrame
) -> pd.DataFrame:
    """Un hospital de la oferta por fila, con sus camas de psiquiatría del último año."""
    ano = ultimo_ano_camas(list(camas.columns))
    hospitales = oferta.loc[
        oferta["tipo_establecimiento"] == TIPO_HOSPITAL,
        ["establecimiento_codigo", "establecimiento_nombre", "comuna_codigo",
         "reporto_id36_periodo"],
    ].copy()
    agregado = camas_psiquiatria_por_establecimiento(camas, ano)
    dim = hospitales.merge(agregado, on="establecimiento_codigo", how="left")
    dim["en_dotacion_snss"] = dim["establecimiento_codigo"].isin(
        set(camas["establecimiento_codigo"])
    )
    dim["n_areas_psiquiatria"] = dim["n_areas_psiquiatria"].fillna(0).astype("int32")
    dim["ano_camas"] = pd.Series(ano, index=dim.index, dtype="int32")
    dim = dim.sort_values("establecimiento_codigo").reset_index(drop=True)
    dim = dim[[field.name for field in SCHEMA]]
    validate_dim(dim, oferta_hospitales=len(hospitales))
    return dim


def _atomic_write(dim: pd.DataFrame, output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(dim, schema=SCHEMA, preserve_index=False)
    with tempfile.NamedTemporaryFile(
        dir=output_path.parent, suffix=".tmp", delete=False
    ) as handle:
        tmp = Path(handle.name)
    try:
        pq.write_table(table, tmp, compression="zstd")
        pq.read_table(tmp)  # legible antes de reemplazar
        tmp.replace(output_path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    oferta = pd.read_parquet(
        DIM_OFERTA_PATH,
        columns=["establecimiento_codigo", "establecimiento_nombre", "comuna_codigo",
                 "tipo_establecimiento", "reporto_id36_periodo"],
    )
    camas = pd.read_parquet(CAMAS_SNSS_PATH)
    dim = build_dim_camas_psiquiatria_hospital_rm(oferta, camas)
    _atomic_write(dim)
    con_camas = int(dim["camas_psiquiatria"].notna().sum())
    logger.info(
        "Publicado %s: %d hospitales, %d en dotación SNSS, %d con camas de psiquiatría (%d)",
        OUTPUT_PATH.as_posix(), len(dim), int(dim["en_dotacion_snss"].sum()), con_camas,
        int(dim["ano_camas"].iloc[0]),
    )


if __name__ == "__main__":
    main()
