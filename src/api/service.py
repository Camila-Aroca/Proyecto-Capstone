"""Servicio de datos y pronosticos que respalda la API.

**Por que la API es rapida.** Reentrenar el modelo en cada request tomaria
segundos. En cambio:

1. `cargar` lee una vez los outputs del pipeline (panel observado, mart
   territorial, cartografia) y los deja en memoria.
2. `calcular_pronostico` ajusta el modelo seleccionado y guarda el pronostico
   en memoria. Se ejecuta en segundo plano al arrancar; mientras tanto las
   consultas de datos responden normalmente y las de pronostico informan que
   se esta calculando.
3. Cada request solo filtra y serializa tablas pequenas.

La API **consume** outputs del pipeline; no los genera. Si falta alguno, lo
informa con el stage que hay que ejecutar, en vez de inventar un reemplazo. El
modelo se instancia desde el registro unico segun la seleccion congelada del
benchmark, de modo que se sirve exactamente la configuracion evaluada.

Las funciones de calculo son puras y estan fuera de la clase para poder
probarlas sin cargar datos reales.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from shapely.geometry import mapping

from src.models.features import RM_SERIES_ID, TARGET
from src.models.forecast import DatosActuales, load_current_panel
from src.models.holdout import DIAS_SEMANA_COMPLETA
from src.models.metrics import coverage_tolerance
from src.models.persistence import (
    RUTA_MANIFIESTO,
    RUTA_PRONOSTICO,
    leer_manifiesto,
    motivo_desactualizacion,
    nombres_series,
)
from src.models.persistence import calcular_pronostico as ajustar_pronostico
from src.models.persistence import cargar as cargar_pronostico_persistido

logger = logging.getLogger(__name__)

# Semanas observadas que definen el nivel reciente contra el que se compara el pronostico.
VENTANA_RECIENTE: Final[int] = 4
# Cambio relativo a partir del cual el tablero declara alza o baja. Umbral de producto:
# fija que tan grande debe ser el movimiento para destacarlo, no si es estadisticamente
# distinguible, que es lo que responde `fuera_del_intervalo`.
UMBRAL_CAMBIO_PCT: Final[float] = 7.0
# Tolerancia de simplificacion de poligonos, en grados (~100 m): suficiente para
# un mapa comunal y reduce el GeoJSON a una fraccion de su tamano.
TOLERANCIA_GEOMETRIA: Final[float] = 0.001


@dataclass(frozen=True)
class Rutas:
    """Outputs del pipeline que consume la API, con el stage que los produce."""

    territorial: Path = Path("data/processed/marts/mart_mvp_territorial_comuna.parquet")
    cartografia: Path = Path("data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet")
    seleccion: Path = Path("reports/modeling/benchmark_demanda_sm_seleccion.json")
    holdout_resumen: Path = Path("reports/modeling/holdout_demanda_sm_resumen.csv")
    pronostico: Path = RUTA_PRONOSTICO
    manifiesto_pronostico: Path = RUTA_MANIFIESTO


@dataclass
class Estado:
    estado: str = "pendiente"
    detalle: str | None = None
    actualizado_en: datetime | None = None

    def marcar(self, estado: str, detalle: str | None = None) -> None:
        self.estado, self.detalle = estado, detalle
        self.actualizado_en = datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Funciones puras
# --------------------------------------------------------------------------

def registros(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Filas como diccionarios, con NaN convertido a None y fechas a `date`."""
    salida = frame.copy()
    for columna in salida.columns:
        if pd.api.types.is_datetime64_any_dtype(salida[columna]):
            salida[columna] = salida[columna].dt.date
    salida = salida.astype(object).where(salida.notna(), None)
    return salida.to_dict("records")


def exclusiones(diagnostico: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Comunas sin pronostico y el motivo, tomadas del diagnostico del holdout."""
    motivos: dict[str, str] = {}
    sin_historia = diagnostico.get("comunas_sin_historia", pd.DataFrame())
    for fila in sin_historia.itertuples():
        motivos[str(fila.comuna_codigo)] = (
            "Sin historia de reporte en el período de entrenamiento: no es pronosticable."
        )
    incompletas = diagnostico.get("comunas_cobertura_incompleta", pd.DataFrame())
    for fila in incompletas.itertuples():
        motivos[str(fila.comuna_codigo)] = (
            f"Dejó de reportar desde la semana {int(fila.ultima_semana_con_datos) + 1}: "
            "ausencia de dato, no demanda cero."
        )
    return motivos


def semana_en_curso(diagnostico: dict[str, pd.DataFrame]) -> dict[str, Any] | None:
    """Semana parcial mas reciente: ya publicada, todavia incompleta.

    El modelo la excluye y debe seguir excluida: compararla con semanas completas
    exagera una caida inexistente, porque tres de siete dias publicados se leen como
    un descenso del 60%. Se expone aparte y etiquetada, para que el producto pueda
    mostrar que hay dato en curso sin mezclarlo con la serie observada.
    """
    incompletas = diagnostico.get("semanas_incompletas", pd.DataFrame())
    if incompletas.empty:
        return None
    fila = incompletas.sort_values(["ano", "semana"]).iloc[-1]
    return {
        "ano": int(fila["ano"]),
        "semana": int(fila["semana"]),
        "dias_observados": int(fila["dias"]),
        "dias_esperados": DIAS_SEMANA_COMPLETA,
        "atenciones": float(fila[TARGET]),
    }


def historico(
    panel: pd.DataFrame, calendario: pd.DataFrame, series_id: str, semanas: int
) -> pd.DataFrame:
    """Ultimas `semanas` observadas de una serie, con su fecha de inicio."""
    serie = panel[panel["series_id"] == series_id].sort_values("t").tail(semanas)
    serie = serie.merge(calendario, on=["ano", "semana"], how="left")
    return serie.rename(columns={"y": "atenciones", "fecha_inicio_semana": "fecha_inicio"})[
        ["ano", "semana", "fecha_inicio", "atenciones"]
    ]


def formatear_pronostico(pronostico: pd.DataFrame, nombres: dict[str, str]) -> pd.DataFrame:
    """Columnas de la API a partir de la salida de `forecast_future`."""
    salida = pronostico.rename(
        columns={
            "y_pred": "pronostico",
            "y_inferior": "limite_inferior",
            "y_superior": "limite_superior",
            "fecha_inicio_semana": "fecha_inicio",
        }
    )
    salida["nombre"] = salida["series_id"].map(nombres)
    salida["nivel"] = np.where(salida["series_id"] == RM_SERIES_ID, "region", "comuna")
    for columna in ("pronostico", "limite_inferior", "limite_superior"):
        salida[columna] = salida[columna].round(1)
    return salida[
        [
            "series_id", "nombre", "nivel", "horizonte", "ano", "semana", "fecha_inicio",
            "pronostico", "limite_inferior", "limite_superior",
        ]
    ]


def clasificar_cambio(resumen: pd.DataFrame, umbral_pct: float = UMBRAL_CAMBIO_PCT) -> pd.Series:
    """Alza o baja segun el tamano del cambio esperado, con umbral explicito.

    Es una decision de producto, no estadistica: fija que tan grande debe ser el
    cambio para destacarlo en el tablero. Si se distingue o no del ruido semanal
    lo responde `fuera_del_intervalo`, que acompana a esta etiqueta.
    """
    # Conversion explicita: un ausente como None deja la columna como objeto y
    # la comparacion fallaria; como NaN, cualquier comparacion es falsa.
    variacion = pd.to_numeric(resumen["variacion_pct"], errors="coerce")
    return pd.Series(
        np.select(
            [
                ~resumen["tiene_pronostico"].astype(bool) | variacion.isna(),
                variacion >= umbral_pct,
                variacion <= -umbral_pct,
            ],
            ["sin_pronostico", "alza", "baja"],
            default="estable",
        ),
        index=resumen.index,
    )


def fuera_del_intervalo(resumen: pd.DataFrame) -> pd.Series:
    """Si el nivel reciente queda fuera del intervalo medio del pronostico.

    Segunda etiqueta del cambio. Un movimiento puede superar el umbral y aun asi
    ser compatible con la fluctuacion semanal: en comunas de bajo volumen el
    intervalo supera el 100% del nivel reciente, de modo que pasar de 2,5 a 3
    atenciones cumple cualquier umbral porcentual sin ser una senal. Separar
    ambas cosas permite mostrar movimiento sin presentarlo como demostrado.
    """
    reciente = pd.to_numeric(resumen["promedio_ultimas_semanas"], errors="coerce")
    inferior = pd.to_numeric(resumen["limite_inferior_promedio"], errors="coerce")
    superior = pd.to_numeric(resumen["limite_superior_promedio"], errors="coerce")
    evaluable = (
        resumen["tiene_pronostico"].astype(bool)
        & reciente.notna()
        & inferior.notna()
        & superior.notna()
    )
    fuera = (reciente < inferior) | (reciente > superior)
    return pd.Series(np.where(evaluable, fuera, None), index=resumen.index, dtype=object)


def resumen_comunal(
    panel: pd.DataFrame,
    pronostico: pd.DataFrame,
    territorial: pd.DataFrame,
    motivos: dict[str, str],
    ventana: int = VENTANA_RECIENTE,
) -> pd.DataFrame:
    """Una fila por comuna RM: nivel reciente, pronostico y contexto territorial.

    Incluye las comunas sin pronostico con su motivo y metricas en null, para
    que el producto nunca las muestre como demanda cero.
    """
    comunas = panel[panel["nivel"] == "comuna"]
    reciente = (
        comunas.sort_values("t").groupby("series_id").tail(ventana)
        .groupby("series_id")["y"].mean().rename("promedio_ultimas_semanas")
    )
    futuro = pronostico[pronostico["series_id"] != RM_SERIES_ID]
    promedio = futuro.groupby("series_id")["y_pred"].mean().rename("pronostico_promedio")
    # Tasa de cada semana con la poblacion de su propio anio, luego promediada:
    # correcta aunque el horizonte cruce a un anio sin observaciones.
    tasa = (
        (futuro["y_pred"] / futuro["poblacion_anual"] * 10_000)
        .groupby(futuro["series_id"])
        .mean()
        .rename("tasa_pronostico_por_10000")
    )
    banda = futuro.groupby("series_id")[["y_inferior", "y_superior"]].mean().rename(
        columns={"y_inferior": "limite_inferior_promedio", "y_superior": "limite_superior_promedio"}
    )

    base = territorial.rename(columns={"comuna_codigo": "series_id", "comuna_glosa": "nombre"})
    base = base[["series_id", "nombre", "indicador_vulnerabilidad", "n_oferta_urgencia_actual"]]
    resumen = base.set_index("series_id").join(reciente).join(promedio).join(tasa).join(banda)
    resumen["variacion_pct"] = (
        (resumen["pronostico_promedio"] / resumen["promedio_ultimas_semanas"] - 1) * 100
    ).where(resumen["promedio_ultimas_semanas"] > 0)
    resumen["tiene_pronostico"] = resumen["pronostico_promedio"].notna()
    resumen["cambio_esperado"] = clasificar_cambio(resumen)
    resumen["fuera_del_intervalo"] = fuera_del_intervalo(resumen)
    resumen["motivo_sin_pronostico"] = [
        None if tiene else motivos.get(s, "Sin serie modelable en el período evaluado.")
        for s, tiene in zip(resumen.index, resumen["tiene_pronostico"])
    ]
    resumen = resumen.rename(columns={"n_oferta_urgencia_actual": "oferta_urgencia_actual"})
    for columna, decimales in (
        ("promedio_ultimas_semanas", 1), ("pronostico_promedio", 1),
        ("variacion_pct", 1), ("tasa_pronostico_por_10000", 2),
        ("indicador_vulnerabilidad", 4), ("limite_inferior_promedio", 1),
        ("limite_superior_promedio", 1),
    ):
        resumen[columna] = resumen[columna].round(decimales)
    return resumen.reset_index().sort_values("pronostico_promedio", ascending=False, na_position="last")


def cartografia_geojson(ruta: Path, tolerancia: float = TOLERANCIA_GEOMETRIA) -> dict[str, Any]:
    """GeoJSON comunal simplificado para el mapa.

    La cartografia esta en SIRGAS 2000 (EPSG:4674), que para un mapa web es
    practicamente coincidente con WGS84; no se reproyecta.
    """
    tabla = pq.read_table(ruta, columns=["CUT", "COMUNA", "SHAPE"]).to_pandas()
    geometrias = shapely.simplify(shapely.from_wkb(tabla["SHAPE"]), tolerancia, preserve_topology=True)
    geometrias = shapely.set_precision(geometrias, 1e-5)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"series_id": str(cut), "nombre": nombre},
                "geometry": mapping(geometria),
            }
            for cut, nombre, geometria in zip(tabla["CUT"], tabla["COMUNA"], geometrias)
        ],
    }


def cobertura_holdout(ruta: Path, modelo: str, nivel: float) -> list[dict[str, Any]] | None:
    """Cobertura real del modelo fuera de muestra, desde el resumen del holdout."""
    if not ruta.exists():
        return None
    resumen = pd.read_csv(ruta, dtype={"series_id": str})
    resumen = resumen[resumen["modelo"] == modelo]
    if resumen.empty:
        return None
    salida = []
    for nombre_nivel, mascara in (
        ("region", resumen["series_id"] == RM_SERIES_ID),
        ("comuna", resumen["series_id"] != RM_SERIES_ID),
    ):
        grupo = resumen[mascara]
        evaluaciones = int(grupo["n"].sum())
        cobertura = float((grupo["cobertura"] * grupo["n"]).sum() / evaluaciones)
        salida.append(
            {
                "nivel": nombre_nivel,
                "cobertura_observada": round(cobertura, 4),
                "evaluaciones": evaluaciones,
                "dentro_de_tolerancia": abs(cobertura - nivel)
                <= coverage_tolerance(evaluaciones, nivel),
            }
        )
    return salida


# --------------------------------------------------------------------------
# Servicio con estado
# --------------------------------------------------------------------------

@dataclass
class ServicioDemanda:
    """Estado en memoria de la API: datos cargados y pronostico calculado."""

    rutas: Rutas = field(default_factory=Rutas)
    datos: DatosActuales | None = None
    territorial: pd.DataFrame | None = None
    geojson: dict[str, Any] | None = None
    seleccion: dict[str, Any] | None = None
    pronostico: pd.DataFrame | None = None
    origen_pronostico: str | None = None
    pronostico_generado_en: datetime | None = None
    aviso_pronostico: str | None = None
    nombres: dict[str, str] = field(default_factory=dict)
    motivos: dict[str, str] = field(default_factory=dict)
    estado_datos: Estado = field(default_factory=Estado)
    estado_pronostico: Estado = field(default_factory=Estado)
    _bloqueo: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def cargar(self) -> None:
        """Lee los outputs del pipeline. Un faltante deja el estado en error, no cae."""
        self.estado_datos.marcar("calculando")
        try:
            for ruta, stage in (
                (self.rutas.territorial, "build_mart_mvp_territorial_comuna"),
                (self.rutas.cartografia, "clean_censo"),
            ):
                if not ruta.exists():
                    raise FileNotFoundError(
                        f"Falta {ruta.as_posix()}: ejecute el stage `{stage}` del pipeline."
                    )
            datos = load_current_panel()
            territorial = pq.read_table(self.rutas.territorial).to_pandas()
            geojson = cartografia_geojson(self.rutas.cartografia)
            seleccion = (
                json.loads(self.rutas.seleccion.read_text(encoding="utf-8"))
                if self.rutas.seleccion.exists()
                else None
            )
        except Exception as error:  # noqa: BLE001 - se informa por /salud
            logger.exception("Fallo la carga de datos de la API")
            self.estado_datos.marcar("error", str(error))
            return
        self.datos, self.territorial, self.geojson, self.seleccion = (
            datos, territorial, geojson, seleccion
        )
        self.nombres = nombres_series(datos.panel)
        self.motivos = exclusiones(datos.diagnostico)
        self.estado_datos.marcar("listo")

    def _motivo_recalculo(self) -> str | None:
        """Por que no se puede reutilizar el pronostico persistido, o None si sirve."""
        if not (self.rutas.pronostico.exists() and self.rutas.manifiesto_pronostico.exists()):
            return "no hay un pronóstico persistido"
        try:
            return motivo_desactualizacion(leer_manifiesto(self.rutas.manifiesto_pronostico))
        except (OSError, ValueError, KeyError) as error:
            return f"el manifiesto del pronóstico no es legible ({error})"

    def _obtener_pronostico(self) -> tuple[pd.DataFrame, str, datetime, str | None]:
        """Reutiliza el pronostico del disco; si no sirve, lo recalcula y lo informa."""
        motivo = self._motivo_recalculo()
        if motivo is None:
            pronostico, manifiesto = cargar_pronostico_persistido(
                self.rutas.pronostico, self.rutas.manifiesto_pronostico
            )
            generado = datetime.fromisoformat(
                str(manifiesto["generado_en_utc"]).replace("Z", "+00:00")
            )
            logger.info("Pronostico reutilizado desde %s", self.rutas.pronostico.as_posix())
            return pronostico, "persistido", generado, None

        logger.info("Se recalcula el pronostico en memoria: %s", motivo)
        return (
            ajustar_pronostico(self.datos, self.seleccion),
            "en_memoria",
            datetime.now(timezone.utc),
            f"El pronóstico se calculó en memoria porque {motivo}. Ejecute el stage "
            "`forecast_demanda_sm` del pipeline para persistirlo y evitar recalcularlo.",
        )

    def calcular_pronostico(self) -> None:
        """Deja el pronostico listo. Idempotente y seguro entre hilos.

        Ajustar el modelo toma segundos. El stage `forecast_demanda_sm` lo hace una vez
        y deja el resultado en disco con su manifiesto; aqui solo se recalcula cuando ese
        output falta o quedo desactualizado respecto del panel o de la seleccion.
        """
        if not self._bloqueo.acquire(blocking=False):
            return
        try:
            if self.datos is None:
                self.estado_pronostico.marcar("error", "Los datos no estan cargados.")
                return
            if self.seleccion is None:
                self.estado_pronostico.marcar(
                    "error",
                    f"Falta {self.rutas.seleccion.as_posix()}: ejecute el stage "
                    "`benchmark_demanda_sm` para seleccionar el modelo.",
                )
                return
            self.estado_pronostico.marcar("calculando")
            (
                self.pronostico,
                self.origen_pronostico,
                self.pronostico_generado_en,
                self.aviso_pronostico,
            ) = self._obtener_pronostico()
            self.estado_pronostico.marcar("listo")
        except Exception as error:  # noqa: BLE001 - se informa por /salud
            logger.exception("Fallo el calculo del pronostico")
            self.estado_pronostico.marcar("error", str(error))
        finally:
            self._bloqueo.release()
