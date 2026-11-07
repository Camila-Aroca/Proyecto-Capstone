"""Endpoint del pronóstico semanal de suicidios por territorio de residencia.

La API **no calcula** este pronóstico: lo lee del output persistido de
`forecast_suicidios`. Si falta o quedó desactualizado frente al mart o a la
selección, responde `503` indicando la etapa a ejecutar, en vez de recalcular o de
servir un pronóstico cuyo origen no coincide con la historia que se muestra.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Final

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.schemas import SerieSuicidios
from src.api.service import Estado, registros
from src.models import suicidios as su
from src.models.features import RM_SERIES_ID

logger = logging.getLogger(__name__)

# Ventana del total reciente: 52 semanas de calendario (364 días) que terminan en la
# última semana completa. Se cuenta sobre el mart y no sobre el panel, para incluir los
# fragmentos de borde de año (semana 53) que el modelo excluye pero que son defunciones.
DIAS_RECIENTES: Final[int] = 364
ADVERTENCIAS: Final[list[str]] = [
    "Son defunciones registradas por lesiones autoinfligidas intencionalmente (CIE-10 X60-X84), DEIS.",
    "La comuna es la de residencia de la persona fallecida, no el lugar del hecho ni un establecimiento: "
    "no se compara uno a uno con las atenciones de urgencia, que se cuentan donde se atendieron.",
    "En una comuna el pronóstico es la tasa esperada de la semana (a menudo bajo 1), no una predicción de casos.",
    "La última semana publicada se excluye mientras su inscripción esté incompleta.",
]


@dataclass(frozen=True)
class RutasSuicidios:
    mart: Path = su.MART_PATH
    pronostico: Path = su.RUTA_PRONOSTICO
    manifiesto: Path = su.RUTA_MANIFIESTO
    holdout_resumen: Path = su.RUTA_HOLDOUT_RESUMEN


# --------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------

def historia(panel: pd.DataFrame, calendario: pd.DataFrame, series_id: str, semanas: int) -> pd.DataFrame:
    propia = panel[panel["series_id"] == series_id].sort_values("t").tail(semanas)
    propia = propia.merge(calendario[["ano", "semana", "fecha_inicio_semana"]], on=["ano", "semana"], how="left")
    return propia.rename(columns={"y": "suicidios", "fecha_inicio_semana": "fecha_inicio"})[
        ["ano", "semana", "fecha_inicio", "suicidios"]].astype({"suicidios": int})


def tasa_reciente(mart: pd.DataFrame, series_id: str, hasta: Any, dias: int = DIAS_RECIENTES
                  ) -> tuple[int, float | None]:
    """Suicidios de los `dias` días que terminan en `hasta` y su tasa anual por 100.000 habitantes.

    Suma las celdas del mart (semanas y fragmentos) contenidas en la ventana; la región
    es la suma de las comunas. La población es la del año de `hasta`.
    """
    fin = pd.Timestamp(hasta).date()
    inicio = fin - pd.Timedelta(days=dias - 1).to_pytimedelta()
    propio = mart if series_id == RM_SERIES_ID else mart[mart["comuna_codigo"] == series_id]
    ventana = propio[(propio["fecha_inicio_semana"] >= inicio) & (propio["fecha_fin_semana"] <= fin)]
    total = int(ventana["suicidios"].sum())
    ano = propio[propio["fecha_fin_semana"] == fin].drop_duplicates("comuna_codigo")
    poblacion = float(ano["poblacion_anual"].sum())
    return total, (round(total / poblacion * 100_000 * 365.25 / dias, 2) if poblacion > 0 else None)


def cobertura_por_nivel(holdout: pd.DataFrame | None, modelo: str, nivel: str) -> dict[str, Any] | None:
    """Cobertura observada y declarada del modelo en el holdout, ponderada por evaluaciones."""
    if holdout is None:
        return None
    propias = holdout[holdout["modelo"] == modelo]
    propias = propias[(propias["series_id"] == RM_SERIES_ID) == (nivel == "region")]
    if propias.empty or propias["cobertura_esperada"].isna().any():
        return None
    n = propias["n"]
    return {"observada": round(float((propias["cobertura"] * n).sum() / n.sum()), 4),
            "esperada": round(float((propias["cobertura_esperada"] * n).sum() / n.sum()), 4),
            "evaluaciones": int(n.sum())}


def pronostico_serie(pronostico: pd.DataFrame, series_id: str) -> list[dict[str, Any]]:
    propio = pronostico[pronostico["series_id"] == series_id].sort_values("horizonte").rename(columns={
        "y_pred": "pronostico", "y_inferior": "limite_inferior", "y_superior": "limite_superior",
        "fecha_inicio_semana": "fecha_inicio"})
    propio["pronostico"] = propio["pronostico"].round(2)
    propio["cobertura_esperada"] = propio["cobertura_esperada"].round(4)
    return registros(propio[["horizonte", "ano", "semana", "fecha_inicio", "pronostico", "limite_inferior",
                             "limite_superior", "cobertura_esperada"]])


# --------------------------------------------------------------------------
# Servicio con estado
# --------------------------------------------------------------------------

@dataclass
class ServicioSuicidios:
    rutas: RutasSuicidios = field(default_factory=RutasSuicidios)
    panel: pd.DataFrame | None = None
    mart: pd.DataFrame | None = None
    calendario: pd.DataFrame | None = None
    pronostico: pd.DataFrame | None = None
    manifiesto: dict[str, Any] | None = None
    holdout: pd.DataFrame | None = None
    nombres: dict[str, str] = field(default_factory=dict)
    estado: Estado = field(default_factory=Estado)
    _bloqueo: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def cargar(self) -> None:
        """Lee pronóstico, manifiesto e historia; un pronóstico vencido deja el estado en error."""
        if not self._bloqueo.acquire(blocking=False):
            return
        self.estado.marcar("calculando")
        try:
            pronostico, manifiesto = su.cargar(self.rutas.pronostico, self.rutas.manifiesto)
            if motivo := su.motivo_desactualizacion(manifiesto):
                raise RuntimeError(f"El pronóstico de suicidios está desactualizado ({motivo}): ejecute el "
                                   "stage `forecast_suicidios` del pipeline.")
            mart = su.load_mart(self.rutas.mart)
            panel = su.build_panel(mart)
            ultima = manifiesto["ultima_semana_observada"]
            if int(panel["t"].max()) != int(ultima["t"]):
                raise RuntimeError("La historia del mart no termina en la semana de origen del pronóstico: "
                                   "ejecute el stage `forecast_suicidios`.")
            self.calendario = su.calendario(mart)
            self.holdout = (pd.read_csv(self.rutas.holdout_resumen, dtype={"series_id": str})
                            if self.rutas.holdout_resumen.exists() else None)
            self.nombres = panel.drop_duplicates("series_id").set_index("series_id")["comuna_glosa"].to_dict()
            self.panel, self.pronostico, self.manifiesto = panel, pronostico, manifiesto
            self.mart = mart[["comuna_codigo", "fecha_inicio_semana", "fecha_fin_semana", "suicidios",
                              "poblacion_anual"]]
            self.estado.marcar("listo")
        except Exception as error:  # noqa: BLE001 - se informa en el endpoint
            logger.exception("Falló la carga del pronóstico de suicidios")
            self.estado.marcar("error", str(error))
        finally:
            self._bloqueo.release()

    def serie(self, series_id: str, semanas: int) -> dict[str, Any]:
        nivel = "region" if series_id == RM_SERIES_ID else "comuna"
        ultima = self.panel.loc[self.panel["t"] == self.panel["t"].max(), ["ano", "semana"]].iloc[0]
        fin = self.calendario.loc[(self.calendario["ano"] == ultima["ano"])
                                  & (self.calendario["semana"] == ultima["semana"]), "fecha_inicio_semana"].iloc[0]
        total, tasa = tasa_reciente(self.mart, series_id, pd.Timestamp(fin) + pd.Timedelta(days=6))
        m = self.manifiesto
        return {
            "series_id": series_id, "nombre": self.nombres[series_id], "nivel": nivel,
            "historico": registros(historia(self.panel, self.calendario, series_id, semanas)),
            "pronostico": pronostico_serie(self.pronostico, series_id),
            "suicidios_ultimas_52_semanas": total, "tasa_anual_por_100000": tasa,
            "modelo": m["modelo"], "nivel_intervalo": m["nivel_intervalo"],
            "ultima_semana_observada": {k: m["ultima_semana_observada"][k] for k in ("ano", "semana")},
            "fecha_corte_datos": m["fecha_corte_datos"],
            "semanas_registro_incompleto": m.get("semanas_registro_incompleto", []),
            "cobertura_holdout": cobertura_por_nivel(self.holdout, m["modelo"], nivel),
            "advertencias": ADVERTENCIAS,
        }


# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1")


def obtener_servicio(request: Request) -> ServicioSuicidios:
    return request.app.state.suicidios


ServicioS = Annotated[ServicioSuicidios, Depends(obtener_servicio)]


@router.get("/suicidios/{series_id}", response_model=SerieSuicidios)
def suicidios(
    series_id: str,
    servicio: ServicioS,
    semanas: Annotated[int, Query(ge=1, le=520, description="Semanas históricas a devolver.")] = 52,
) -> dict[str, Any]:
    """Suicidios semanales observados y pronosticados de la región o de una comuna de residencia."""
    if servicio.estado.estado == "error":
        raise HTTPException(status_code=503, detail=servicio.estado.detalle)
    if servicio.estado.estado != "listo":
        raise HTTPException(status_code=503, detail="Cargando el pronóstico de suicidios.",
                            headers={"Retry-After": "5"})
    if series_id not in servicio.nombres:
        raise HTTPException(status_code=404, detail="El territorio no existe en el mart de suicidios.")
    return servicio.serie(series_id, semanas)
