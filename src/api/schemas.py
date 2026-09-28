"""Contratos de respuesta de la API (Pydantic v2).

Los nombres de campos siguen la semantica del proyecto: `atenciones` son
eventos de urgencia en salud mental (ID36 DEIS, ID37 incluido), no personas
unicas. Todo valor ausente se entrega como `null`, nunca como cero.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoProceso = Literal["pendiente", "calculando", "listo", "error"]
Nivel = Literal["region", "comuna"]


class Salud(BaseModel):
    estado_datos: EstadoProceso
    estado_pronostico: EstadoProceso
    detalle: str | None = None


class Territorio(BaseModel):
    series_id: str
    nombre: str
    nivel: Nivel
    tiene_pronostico: bool
    motivo_sin_pronostico: str | None = None


class PuntoHistorico(BaseModel):
    ano: int
    semana: int
    fecha_inicio: date | None
    atenciones: float


class PuntoPronostico(BaseModel):
    horizonte: int = Field(description="Semanas despues de la ultima semana observada.")
    ano: int
    semana: int
    fecha_inicio: date | None
    pronostico: float
    limite_inferior: float
    limite_superior: float


class SerieConPronostico(BaseModel):
    series_id: str
    nombre: str
    nivel: Nivel
    historico: list[PuntoHistorico]
    pronostico: list[PuntoPronostico] | None = Field(
        description="Null mientras el pronostico se esta calculando."
    )
    estado_pronostico: EstadoProceso


class PronosticoSerie(PuntoPronostico):
    series_id: str
    nombre: str
    nivel: Nivel


class ResumenComuna(BaseModel):
    series_id: str
    nombre: str
    tiene_pronostico: bool
    motivo_sin_pronostico: str | None = None
    promedio_ultimas_semanas: float | None = Field(
        description="Media de atenciones de las ultimas semanas observadas."
    )
    pronostico_promedio: float | None = Field(
        description="Media del pronostico puntual sobre los horizontes."
    )
    variacion_pct: float | None
    limite_inferior_promedio: float | None = Field(
        description="Media del limite inferior del intervalo sobre los horizontes."
    )
    limite_superior_promedio: float | None = Field(
        description="Media del limite superior del intervalo sobre los horizontes."
    )
    cambio_esperado: Literal["alza", "baja", "estable", "sin_pronostico"] = Field(
        description=(
            "Alza o baja solo si el nivel reciente queda fuera del intervalo del pronostico; "
            "si no, 'estable': el cambio no se distingue del ruido semanal."
        )
    )
    tasa_pronostico_por_10000: float | None = Field(
        description="Intensidad de atenciones pronosticada por 10.000 habitantes (no prevalencia)."
    )
    indicador_vulnerabilidad: float | None = Field(
        description="Tasa de pobreza por ingresos Casen 2022 (proporcion 0-1)."
    )
    oferta_urgencia_actual: int | None


class CoberturaNivel(BaseModel):
    nivel: Nivel
    cobertura_observada: float
    evaluaciones: int
    dentro_de_tolerancia: bool


class Meta(BaseModel):
    modelo: str | None
    horizontes: list[int]
    nivel_intervalo: float | None
    ultima_semana_observada: PuntoHistorico | None
    pronostico_calculado_en: datetime | None
    comunas_con_pronostico: int
    metricas_backtest: dict[str, float] | None
    cobertura_holdout: list[CoberturaNivel] | None = Field(
        description="Cobertura real de los intervalos fuera de muestra, si el informe existe."
    )
    advertencias: list[str]
