"""Endpoints del pronóstico por establecimiento.

La API **no calcula** este pronóstico: lo lee del output persistido de
`forecast_establecimientos_sm`. Si falta o quedó desactualizado frente a los
datos (por ejemplo, tras una actualización del año en curso), responde `503`
indicando la etapa que hay que ejecutar, en vez de recalcular en memoria o de
servir un pronóstico cuyo origen ya no coincide con la historia que se muestra.

Un pronóstico marcado `fuera_de_rango` por la guardia de plausibilidad no se
publica: el establecimiento queda sin pronóstico y con el motivo.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Final

import pandas as pd
import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.schemas import EstablecimientoDetalle, EstablecimientoResumen, MetaEstablecimientos
from src.api.service import UMBRAL_CAMBIO_PCT, Estado, registros
from src.models.establecimientos import OBJETIVOS, load_current_weekly, load_mart
from src.models.features import SEASONAL_PERIOD
from src.models.holdout import holdout_years
from src.models.pronostico_establecimientos import (
    FACTOR_PLAUSIBLE,
    RUTA_MANIFIESTO,
    RUTA_PRONOSTICO,
    RUTA_SELECCION,
    cargar,
    motivo_desactualizacion,
)

logger = logging.getLogger(__name__)

# Semanas observadas que definen el nivel reciente de un establecimiento.
VENTANA_RECIENTE: Final[int] = 4
MOTIVO_FUERA_DE_RANGO: Final[str] = (
    f"El pronóstico superó {FACTOR_PLAUSIBLE:g} veces el máximo observado del establecimiento "
    "en el último año y se retuvo por precaución."
)


@dataclass(frozen=True)
class RutasEstablecimientos:
    pronostico: Path = RUTA_PRONOSTICO
    manifiesto: Path = RUTA_MANIFIESTO
    seleccion: Path = RUTA_SELECCION
    universo: Path = Path("reports/modeling/benchmark_establecimientos_sm_universo.csv")
    holdout_resumen: Path = Path("reports/modeling/holdout_establecimientos_sm_resumen.csv")
    oferta: Path = Path("data/processed/geo/dim_oferta_urgencia_rm.parquet")
    camas: Path = Path("data/processed/camas/dim_camas_psiquiatria_hospital_rm.parquet")


# --------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------

def publicable(pronostico: pd.DataFrame) -> pd.DataFrame:
    """Solo los pronósticos que pasaron la guardia de plausibilidad."""
    return pronostico[~pronostico["fuera_de_rango"].astype(bool)]


def motivos_sin_pronostico(
    universo: pd.DataFrame, pronostico: pd.DataFrame, manifiesto: dict[str, Any]
) -> dict[tuple[str, int], str]:
    """Motivo de cada establecimiento sin pronóstico publicable, por objetivo."""
    motivos: dict[tuple[str, int], str] = {}
    for fila in universo.itertuples():
        if not fila.incluido and isinstance(fila.motivo_exclusion, str):
            motivos[(fila.objetivo, int(fila.establecimiento_codigo))] = (
                f"Fuera del universo del modelo: {fila.motivo_exclusion}."
            )
    for nombre, info in (manifiesto.get("objetivos") or {}).items():
        for codigo in info.get("excluidos_por_cobertura_en_curso", []):
            motivos[(nombre, int(codigo))] = (
                "Dejó de reportar semanas del año en curso: ausencia de dato, no demanda cero."
            )
    retenidos = pronostico[pronostico["fuera_de_rango"].astype(bool)]
    for objetivo, series_id in retenidos[["objetivo", "series_id"]].drop_duplicates().itertuples(index=False):
        motivos[(objetivo, int(series_id))] = MOTIVO_FUERA_DE_RANGO
    return motivos


def resumen_establecimientos(
    semanal: pd.DataFrame,
    pronostico: pd.DataFrame,
    atributos: pd.DataFrame,
    motivos: dict[tuple[str, int], str],
    ventana: int = VENTANA_RECIENTE,
) -> list[dict[str, Any]]:
    """Una entrada por establecimiento con su resumen por objetivo."""
    regular = semanal[semanal["semana"] != SEASONAL_PERIOD + 1].sort_values(["ano", "semana"])
    ultimas = regular.groupby("establecimiento_codigo").tail(ventana)
    validos = publicable(pronostico)
    salida = []
    for fila in atributos.itertuples():
        codigo = int(fila.establecimiento_codigo)
        objetivos = {}
        for nombre, objetivo in OBJETIVOS.items():
            propias = validos[(validos["objetivo"] == nombre) & (validos["series_id"] == str(codigo))]
            observadas = ultimas.loc[ultimas["establecimiento_codigo"] == codigo, objetivo.target]
            reciente = float(observadas.mean()) if not observadas.empty else None
            medio = float(propias["y_pred"].mean()) if not propias.empty else None
            objetivos[nombre] = {
                "incluido": not propias.empty,
                "motivo_sin_pronostico": None if not propias.empty else motivos.get(
                    (nombre, codigo), "Sin pronóstico para este objetivo."
                ),
                "promedio_ultimas_semanas": None if reciente is None else round(reciente, 1),
                "pronostico_promedio": None if medio is None else round(medio, 1),
                "variacion_pct": (
                    round((medio / reciente - 1) * 100, 1) if medio is not None and reciente else None
                ),
                "limite_inferior_promedio": round(float(propias["y_inferior"].mean()), 1) if medio is not None else None,
                "limite_superior_promedio": round(float(propias["y_superior"].mean()), 1) if medio is not None else None,
            }
        salida.append({**fila._asdict(), "establecimiento_codigo": codigo, "objetivos": objetivos})
    return salida


def detalle_establecimiento(
    codigo: int,
    semanal: pd.DataFrame,
    pronostico: pd.DataFrame,
    calendario: pd.DataFrame,
    atributos: pd.Series,
    motivos: dict[tuple[str, int], str],
    semanas: int,
) -> dict[str, Any]:
    """Historia semanal y pronóstico de ambos objetivos para un establecimiento."""
    propia = semanal[
        (semanal["establecimiento_codigo"] == codigo) & (semanal["semana"] != SEASONAL_PERIOD + 1)
    ].sort_values(["ano", "semana"]).tail(semanas)
    # La fecha sale del calendario común (fecha mínima de cada semana en todo el origen).
    propia = propia.drop(columns=["fecha_inicio_semana"], errors="ignore").merge(
        calendario, on=["ano", "semana"], how="left"
    )
    validos = publicable(pronostico)
    series = []
    for nombre, objetivo in OBJETIVOS.items():
        historia = propia.rename(columns={objetivo.target: "valor", "fecha_inicio_semana": "fecha_inicio"})[
            ["ano", "semana", "fecha_inicio", "valor"]
        ]
        futuro = validos[(validos["objetivo"] == nombre) & (validos["series_id"] == str(codigo))]
        futuro = futuro.sort_values("horizonte").rename(columns={
            "y_pred": "pronostico", "y_inferior": "limite_inferior", "y_superior": "limite_superior",
            "fecha_inicio_semana": "fecha_inicio",
        })
        for columna in ("pronostico", "limite_inferior", "limite_superior"):
            futuro[columna] = futuro[columna].round(1)
        series.append({
            "objetivo": nombre,
            "descripcion": objetivo.descripcion,
            "historico": registros(historia),
            "pronostico": registros(futuro[[
                "horizonte", "ano", "semana", "fecha_inicio", "pronostico", "limite_inferior", "limite_superior",
            ]]) if not futuro.empty else None,
            "motivo_sin_pronostico": None if not futuro.empty else motivos.get(
                (nombre, codigo), "Sin pronóstico para este objetivo."
            ),
        })
    return {**atributos.to_dict(), "establecimiento_codigo": codigo, "series": series}


def cobertura_objetivo(holdout: pd.DataFrame | None, objetivo: str, modelo: str) -> float | None:
    """Cobertura fuera de muestra del modelo en los establecimientos, ponderada por evaluaciones."""
    if holdout is None:
        return None
    propias = holdout[(holdout["objetivo"] == objetivo) & (holdout["modelo"] == modelo) & (holdout["series_id"] != "RM")]
    if propias.empty:
        return None
    return round(float((propias["cobertura"] * propias["n"]).sum() / propias["n"].sum()), 4)


# --------------------------------------------------------------------------
# Servicio con estado
# --------------------------------------------------------------------------

@dataclass
class ServicioEstablecimientos:
    """Estado en memoria del pronóstico por establecimiento."""

    rutas: RutasEstablecimientos = field(default_factory=RutasEstablecimientos)
    semanal: pd.DataFrame | None = None
    calendario: pd.DataFrame | None = None
    pronostico: pd.DataFrame | None = None
    manifiesto: dict[str, Any] | None = None
    seleccion: dict[str, Any] | None = None
    atributos: pd.DataFrame | None = None
    motivos: dict[tuple[str, int], str] = field(default_factory=dict)
    holdout: pd.DataFrame | None = None
    estado: Estado = field(default_factory=Estado)
    _bloqueo: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def cargar(self) -> None:
        """Lee pronóstico, historia y atributos; un pronóstico vencido deja el estado en error."""
        if not self._bloqueo.acquire(blocking=False):
            return
        self.estado.marcar("calculando")
        try:
            pronostico, manifiesto = cargar(self.rutas.pronostico, self.rutas.manifiesto)
            if motivo := motivo_desactualizacion(manifiesto):
                raise RuntimeError(
                    f"El pronóstico por establecimiento está desactualizado ({motivo}): ejecute el "
                    "stage `forecast_establecimientos_sm` del pipeline."
                )
            mart = load_mart()
            anos = holdout_years(int(mart["ano"].max()))
            actual = load_current_weekly(anos)[0] if anos else mart.iloc[0:0]
            semanal = pd.concat([mart, actual[mart.columns]], ignore_index=True)
            universo = pd.read_csv(self.rutas.universo)
            self.atributos = construir_atributos(semanal, self.rutas.oferta, self.rutas.camas)
            self.calendario = (
                semanal.groupby(["ano", "semana"], as_index=False)["fecha_inicio_semana"].min()
                .assign(fecha_inicio_semana=lambda d: pd.to_datetime(d["fecha_inicio_semana"]).dt.date)
            )
            self.holdout = (
                pd.read_csv(self.rutas.holdout_resumen, dtype={"series_id": str})
                if self.rutas.holdout_resumen.exists() else None
            )
            self.seleccion = json.loads(self.rutas.seleccion.read_text(encoding="utf-8"))
            self.semanal, self.pronostico, self.manifiesto = semanal, pronostico, manifiesto
            self.motivos = motivos_sin_pronostico(universo, pronostico, manifiesto)
            self.estado.marcar("listo")
        except Exception as error:  # noqa: BLE001 - se informa en los endpoints
            logger.exception("Fallo la carga del pronóstico por establecimiento")
            self.estado.marcar("error", str(error))
        finally:
            self._bloqueo.release()


def construir_atributos(semanal: pd.DataFrame, ruta_oferta: Path, ruta_camas: Path) -> pd.DataFrame:
    """Nombre, tipo, comuna, coordenadas y camas de psiquiatría de cada establecimiento."""
    ultimo = semanal.sort_values(["ano", "semana"]).drop_duplicates("establecimiento_codigo", keep="last")
    base = ultimo[[
        "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_urgencia",
        "comuna_codigo", "comuna_glosa",
    ]].rename(columns={
        "establecimiento_glosa": "nombre", "tipo_establecimiento_urgencia": "tipo", "comuna_glosa": "comuna",
    })
    if ruta_oferta.exists():
        oferta = pq.read_table(ruta_oferta, columns=["establecimiento_codigo", "latitud", "longitud"]).to_pandas()
        base = base.merge(oferta, on="establecimiento_codigo", how="left")
    else:
        base = base.assign(latitud=None, longitud=None)
    if ruta_camas.exists():
        camas = pq.read_table(ruta_camas, columns=["establecimiento_codigo", "camas_psiquiatria"]).to_pandas()
        base = base.merge(camas, on="establecimiento_codigo", how="left")
    else:
        base = base.assign(camas_psiquiatria=None)
    base["comuna_codigo"] = base["comuna_codigo"].astype(str)
    return base.sort_values("nombre").reset_index(drop=True)


# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1")


def obtener_servicio(request: Request) -> ServicioEstablecimientos:
    return request.app.state.establecimientos


ServicioE = Annotated[ServicioEstablecimientos, Depends(obtener_servicio)]


def _exigir(servicio: ServicioEstablecimientos) -> None:
    if servicio.estado.estado == "listo":
        return
    if servicio.estado.estado == "error":
        raise HTTPException(status_code=503, detail=servicio.estado.detalle)
    raise HTTPException(
        status_code=503, detail="Cargando el pronóstico por establecimiento.",
        headers={"Retry-After": "5"},
    )


@router.get("/establecimientos", response_model=list[EstablecimientoResumen])
def listar_establecimientos(servicio: ServicioE) -> list[dict[str, Any]]:
    """Establecimientos de urgencia con su resumen de atenciones y hospitalizaciones esperadas."""
    _exigir(servicio)
    filas = resumen_establecimientos(servicio.semanal, servicio.pronostico, servicio.atributos, servicio.motivos)
    return [{k: (None if pd.isna(v) else v) if not isinstance(v, dict) else v for k, v in f.items()} for f in filas]


@router.get("/establecimientos-meta", response_model=MetaEstablecimientos)
def meta_establecimientos(servicio: ServicioE) -> dict[str, Any]:
    """Modelos servidos, cobertura real fuera de muestra y advertencias de lectura."""
    _exigir(servicio)
    objetivos, ultima = [], None
    for nombre, info in servicio.manifiesto["objetivos"].items():
        ultima = info["ultima_semana_observada"]
        objetivos.append({
            "objetivo": nombre,
            "descripcion": OBJETIVOS[nombre].descripcion,
            "modelo": info["modelo"],
            "horizontes": info["horizontes"],
            "nivel_intervalo": info["nivel_intervalo"],
            "establecimientos_con_pronostico": info["establecimientos"],
            "cobertura_holdout": cobertura_objetivo(servicio.holdout, nombre, info["modelo"]),
            "pronosticos_fuera_de_rango": info.get("fuera_de_rango", 0),
        })
    semana = {k: ultima[k] for k in ("ano", "semana")}
    calendario = servicio.calendario
    fecha = None
    if calendario is not None and not calendario.empty:
        coincide = calendario[(calendario["ano"] == semana["ano"]) & (calendario["semana"] == semana["semana"])]
        if not coincide.empty:
            fecha = pd.Timestamp(coincide["fecha_inicio_semana"].iloc[0]).date()
    return {
        "ultima_semana_observada": semana,
        "ultima_semana_fecha_inicio": fecha,
        "umbral_cambio_pct": UMBRAL_CAMBIO_PCT,
        "pronostico_generado_en": datetime.fromisoformat(
            str(servicio.manifiesto["generado_en_utc"]).replace("Z", "+00:00")
        ),
        "objetivos": objetivos,
        "advertencias": [
            "Las cifras son atenciones y hospitalizaciones (eventos), no personas.",
            "Las hospitalizaciones se cuentan en el hospital donde ocurrió la urgencia, no donde "
            "quedó hospitalizado el paciente: no miden la ocupación de sus camas.",
            "Las camas son la dotación anual declarada, no camas disponibles.",
            "Un establecimiento sin pronóstico no tiene demanda cero: no tiene un pronóstico confiable.",
        ],
    }


@router.get("/establecimientos/{codigo}", response_model=EstablecimientoDetalle)
def establecimiento(
    codigo: int,
    servicio: ServicioE,
    semanas: Annotated[int, Query(ge=1, le=520, description="Semanas históricas a devolver.")] = 52,
) -> dict[str, Any]:
    """Historia semanal y pronóstico de un establecimiento."""
    _exigir(servicio)
    atributos = servicio.atributos.set_index("establecimiento_codigo")
    if codigo not in atributos.index:
        raise HTTPException(status_code=404, detail="El establecimiento no existe en los datos de Urgencias.")
    fila = atributos.loc[codigo].where(atributos.loc[codigo].notna(), None)
    return detalle_establecimiento(
        codigo, servicio.semanal, servicio.pronostico, servicio.calendario, fila, servicio.motivos, semanas,
    )
