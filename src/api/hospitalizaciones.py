"""Endpoint del perfil de hospitalizaciones por salud mental de los residentes.

Sirve los outputs de `build_mart_egresos_f00_f99_rm` y, para la región,
`build_contraste_camas_psiquiatria_rm`. No calcula nada: si falta un output
responde 503 con la etapa que lo produce. Los archivos se releen cuando cambian
en disco, sin reiniciar la API.

Egresos cuenta la comuna donde vive la persona, a diferencia de Urgencias, que
cuenta el establecimiento donde se atendió. Es un dato anual (Egresos publica
el año del egreso, no su fecha).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Final

import pandas as pd
import pyarrow.parquet as pq
from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import HospitalizacionesResidentes
from src.data.build_contraste_camas_psiquiatria_rm import OUTPUT_PATH as CONTRASTE_PATH
from src.data.build_mart_egresos_f00_f99_rm import ANUAL_PATH, DESGLOSE_PATH, REGION_ID

router = APIRouter(prefix="/api/v1")

ADVERTENCIAS: Final[list[str]] = [
    "Son egresos (eventos), no personas: quien se hospitaliza dos veces en el año cuenta dos veces.",
    "Se asignan a la comuna donde vive la persona, no a la del hospital; Urgencias, en cambio, cuenta el establecimiento.",
    "Incluye hospitalizaciones con diagnóstico principal F00-F99 en cualquier tipo de cama y en hospitales "
    "públicos y privados.",
    "Dato anual: Egresos publica el año del egreso, no su fecha. La tasa de 2020 queda sin dato porque la "
    "proyección de población comunal empieza en 2021.",
]


@lru_cache(maxsize=8)
def _leer(path: str, _modificado: float) -> pd.DataFrame:
    return pq.read_table(path).to_pandas()


def leer(path: Path, stage: str) -> pd.DataFrame:
    """Lee un output del pipeline; se recarga solo si el archivo cambió."""
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Falta {path.as_posix()}: ejecute el stage `{stage}` del pipeline.")
    return _leer(str(path), path.stat().st_mtime)


def _nulos(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.astype(object).where(frame.notna(), None).to_dict("records")


def perfil(
    anual: pd.DataFrame, desglose: pd.DataFrame, contraste: pd.DataFrame | None, series_id: str, ano: int | None,
) -> dict[str, Any]:
    """Serie anual del territorio, desgloses de un año y, para la región, el contraste de camas."""
    serie = anual[anual["series_id"] == series_id].sort_values("ano")
    if serie.empty:
        raise HTTPException(status_code=404, detail="Territorio sin perfil de egresos: use 'RM' o un código de comuna.")
    anos = serie["ano"].tolist()
    ano_desglose = ano if ano is not None else max(anos)
    if ano_desglose not in anos:
        raise HTTPException(status_code=422, detail=f"Año sin egresos publicados; disponibles: {anos}.")
    del_ano = desglose[(desglose["series_id"] == series_id) & (desglose["ano"] == ano_desglose)]
    total = int(serie.loc[serie["ano"] == ano_desglose, "egresos"].iloc[0])
    desgloses = {
        dimension: [
            {"categoria": f.categoria, "egresos": int(f.egresos),
             "proporcion": None if total == 0 else round(f.egresos / total, 4)}
            for f in grupo.sort_values("orden").itertuples()
        ]
        for dimension, grupo in del_ano.groupby("dimension")
    }
    primera = serie.iloc[0]
    puntos = serie[["ano", "egresos", "poblacion", "tasa_por_10000", "dias_estada_mediana", "dias_estada_p90",
                    "proporcion_snss", "proporcion_estadia_mayor_a_un_ano"]].round(
        {"tasa_por_10000": 2, "proporcion_snss": 4, "proporcion_estadia_mayor_a_un_ano": 4})
    return {
        "series_id": series_id,
        "nombre": primera["nombre"],
        "nivel": primera["nivel"],
        "anual": _nulos(puntos),
        "ano_desglose": ano_desglose,
        "desglose": desgloses,
        "contraste_camas": (
            _nulos(contraste.sort_values("ano")) if contraste is not None and series_id == REGION_ID else None
        ),
        "advertencias": ADVERTENCIAS,
    }


@router.get("/hospitalizaciones-residentes/{series_id}", response_model=HospitalizacionesResidentes)
def hospitalizaciones_residentes(
    series_id: str,
    ano: Annotated[int | None, Query(description="Año de los desgloses; por defecto, el último publicado.")] = None,
) -> dict[str, Any]:
    """Egresos por salud mental de quienes viven en el territorio: tasa, estadía y perfil."""
    anual = leer(ANUAL_PATH, "build_mart_egresos_f00_f99_rm")
    desglose = leer(DESGLOSE_PATH, "build_mart_egresos_f00_f99_rm")
    # El contraste es un complemento: si falta, el perfil se sirve igual.
    contraste = _leer(str(CONTRASTE_PATH), CONTRASTE_PATH.stat().st_mtime) if CONTRASTE_PATH.exists() else None
    return perfil(anual, desglose, contraste, series_id, ano)
