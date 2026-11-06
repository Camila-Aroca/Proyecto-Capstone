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
OrigenPronostico = Literal["persistido", "en_memoria"]


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
            "Alza o baja cuando la variacion esperada alcanza el umbral declarado en "
            "`/meta` (`umbral_cambio_pct`); si no, 'estable'. Es el tamano del cambio, "
            "no su significancia: para eso esta `fuera_del_intervalo`."
        )
    )
    fuera_del_intervalo: bool | None = Field(
        default=None,
        description=(
            "True si el nivel reciente queda fuera del intervalo del pronostico: el cambio "
            "se distingue de la fluctuacion semanal. False si queda dentro, caso en que el "
            "movimiento es compatible con el ruido. Null si no hay pronostico."
        ),
    )
    tasa_pronostico_por_10000: float | None = Field(
        description="Intensidad de atenciones pronosticada por 10.000 habitantes (no prevalencia)."
    )
    indicador_vulnerabilidad: float | None = Field(
        description="Tasa de pobreza por ingresos Casen 2022 (proporcion 0-1)."
    )
    oferta_urgencia_actual: int | None


class HospitalCamas(BaseModel):
    establecimiento_codigo: int
    nombre: str
    camas_psiquiatria: float


class CamasPsiquiatriaTerritorio(BaseModel):
    series_id: str
    ano_camas: int = Field(description="Ultimo ano de la dotacion de camas del SNSS.")
    total_camas_psiquiatria: float | None = Field(
        description=(
            "Suma de camas de las areas de psiquiatria de los hospitales del territorio que "
            "reportaron ID36 en 2021-2025 (los que alimentan el modelo). "
            "Null si ninguno declara cifra: ausencia de dato, no cero. Es dotacion "
            "declarada, no ocupacion ni disponibilidad."
        )
    )
    n_hospitales_con_camas: int = Field(
        description="Hospitales del territorio con cifra de psiquiatria; los que suman."
    )
    n_hospitales_snss: int = Field(
        description="Hospitales del modelo en el territorio que figuran en la dotacion SNSS."
    )
    n_hospitales_modelo: int = Field(
        description=(
            "Hospitales del territorio que reportaron ID36 en 2021-2025 (alimentan el "
            "modelo), tengan o no camas de psiquiatria."
        )
    )
    hospitales: list[HospitalCamas]


class CoberturaNivel(BaseModel):
    nivel: Nivel
    cobertura_observada: float
    evaluaciones: int
    dentro_de_tolerancia: bool


class SemanaParcial(BaseModel):
    ano: int
    semana: int
    dias_observados: int
    dias_esperados: int
    atenciones: float = Field(
        description="Acumulado de los dias ya publicados, no el total de la semana."
    )


class Meta(BaseModel):
    modelo: str | None
    horizontes: list[int]
    umbral_cambio_pct: float = Field(
        description=(
            "Variacion esperada, en por ciento, a partir de la cual el resumen comunal "
            "declara alza o baja."
        )
    )
    semana_en_curso: SemanaParcial | None = Field(
        default=None,
        description=(
            "Semana parcial en curso a nivel regional: publicada pero aun incompleta. "
            "Excluida del modelo y NO comparable con semanas completas; se entrega solo "
            "para mostrarla etiquetada como provisional."
        ),
    )
    nivel_intervalo: float | None
    ultima_semana_observada: PuntoHistorico | None
    pronostico_calculado_en: datetime | None
    origen_pronostico: OrigenPronostico | None = Field(
        default=None,
        description=(
            "'persistido': se reutilizo el output del stage `forecast_demanda_sm`; "
            "'en_memoria': se recalculo al arrancar porque ese output faltaba o estaba "
            "desactualizado."
        ),
    )
    comunas_con_pronostico: int
    metricas_backtest: dict[str, float] | None
    cobertura_holdout: list[CoberturaNivel] | None = Field(
        description="Cobertura real de los intervalos fuera de muestra, si el informe existe."
    )
    advertencias: list[str]


# --------------------------------------------------------------------------
# Pronóstico por establecimiento
# --------------------------------------------------------------------------

ObjetivoEstablecimiento = Literal["atenciones_sm", "hospitalizaciones_sm"]


class ResumenObjetivoEstablecimiento(BaseModel):
    incluido: bool = Field(description="Si el establecimiento tiene pronóstico para este objetivo.")
    motivo_sin_pronostico: str | None = None
    promedio_ultimas_semanas: float | None = Field(
        description="Media de las últimas semanas observadas; null si no reporta."
    )
    pronostico_promedio: float | None = Field(
        description="Media del pronóstico puntual sobre los horizontes publicables."
    )
    variacion_pct: float | None
    limite_inferior_promedio: float | None
    limite_superior_promedio: float | None


NivelColapso = Literal["holgura", "presion", "saturacion", "sobre_capacidad"]


class ColapsoPsiquiatria(BaseModel):
    nivel: NivelColapso = Field(
        description=(
            "Ocupación de las camas de psiquiatría del hospital en la ventana (razón de sumas): holgura < 85 %, "
            "presión 85-90 %, saturación >= 90 %; sobre_capacidad si algún área superó sus camas disponibles."
        )
    )
    indice_ocupacional: float
    meses: int = Field(description="Meses de la ventana con camas habilitadas en el hospital.")
    area_mes_sobre_capacidad: int
    desde: date
    hasta: date


class EstablecimientoResumen(BaseModel):
    establecimiento_codigo: int
    nombre: str
    tipo: str = Field(description="Tipo según Urgencias: Hospital, SAPU, SAR, SUR o CEAR.")
    comuna_codigo: str
    comuna: str
    latitud: float | None = Field(description="Null si el maestro DEIS no lo georreferencia.")
    longitud: float | None
    camas_psiquiatria: float | None = Field(
        description="Dotación declarada de psiquiatría (último año del libro SNSS); null si no informa."
    )
    objetivos: dict[ObjetivoEstablecimiento, ResumenObjetivoEstablecimiento]
    colapso_psiquiatria: ColapsoPsiquiatria | None = Field(
        default=None, description="Null si el establecimiento no tiene áreas de psiquiatría en el REM-20.",
    )


class PuntoSemanal(BaseModel):
    ano: int
    semana: int
    fecha_inicio: date | None
    valor: float


class PuntoPronosticoEstablecimiento(BaseModel):
    horizonte: int
    ano: int
    semana: int
    fecha_inicio: date | None
    pronostico: float
    limite_inferior: float
    limite_superior: float


class SerieObjetivoEstablecimiento(BaseModel):
    objetivo: ObjetivoEstablecimiento
    descripcion: str
    historico: list[PuntoSemanal]
    pronostico: list[PuntoPronosticoEstablecimiento] | None = Field(
        description="Null si el establecimiento no tiene pronóstico; el motivo viene aparte."
    )
    motivo_sin_pronostico: str | None = None


class PuntoOcupacionMensual(BaseModel):
    ano: int
    mes: int
    fecha_inicio: date
    camas_ocupadas_promedio: float = Field(
        description="Días cama ocupados del mes / días del mes: pacientes en cama de psiquiatría por día, en promedio."
    )
    camas_disponibles_promedio: float = Field(description="Días cama disponibles del mes / días del mes.")
    camas_libres_promedio: float = Field(
        description="Disponibles − ocupadas, por día en promedio: la brecha de capacidad. Negativa = sobre la capacidad."
    )
    indice_ocupacional: float | None = Field(
        description="100 · ocupados / disponibles del mes (razón de sumas); null si no hubo camas disponibles."
    )


class AreaPsiquiatria(BaseModel):
    nivel_cuidado_codigo: int
    nivel_cuidado: str
    meses: int = Field(description="Meses de la ventana con camas disponibles (habilitadas) en el área.")
    meses_sin_holgura: int = Field(description="Meses con menos de una cama libre por día, en promedio.")
    meses_sobre_capacidad: int = Field(description="Meses con más días cama ocupados que disponibles.")
    indice_ocupacional: float | None = Field(description="Del período, como razón de sumas.")
    ultimo_camas_ocupadas_promedio: float
    ultimo_camas_disponibles_promedio: float
    ultimo_camas_libres_promedio: float
    dotacion_declarada: float | None = Field(
        default=None, description="Camas declaradas del área en el último año del libro de dotación; null si no declara.",
    )
    ano_dotacion: int | None = None
    motivo_sin_dotacion: str | None = Field(
        default=None, description="Por qué el área no tiene dotación declarada; null si la tiene.",
    )
    serie: list[PuntoOcupacionMensual] = Field(description="Ocupación mensual del área en la misma ventana.")


class EstablecimientoDetalle(BaseModel):
    establecimiento_codigo: int
    nombre: str
    tipo: str
    comuna_codigo: str
    comuna: str
    camas_psiquiatria: float | None
    series: list[SerieObjetivoEstablecimiento]
    ocupacion_psiquiatria: list[PuntoOcupacionMensual] | None = Field(
        default=None,
        description=(
            "Ocupación mensual de las camas de psiquiatría (REM-20, último mes publicado), en la ventana de la "
            "historia semanal. Null si el hospital no tiene áreas de psiquiatría en el REM-20 o la capa no existe."
        ),
    )
    areas_psiquiatria: list[AreaPsiquiatria] | None = Field(
        default=None, description="Saturación de cada área de psiquiatría en la misma ventana; null si no hay.",
    )


class MetaObjetivoEstablecimiento(BaseModel):
    objetivo: ObjetivoEstablecimiento
    descripcion: str
    modelo: str
    horizontes: list[int]
    nivel_intervalo: float
    establecimientos_con_pronostico: int
    cobertura_holdout: float | None = Field(
        description="Cobertura real de los intervalos en los establecimientos, fuera de muestra."
    )
    pronosticos_fuera_de_rango: int = Field(
        description="Pronósticos retenidos por exceder el doble del máximo reciente del establecimiento."
    )


class MetaEstablecimientos(BaseModel):
    ultima_semana_observada: dict[str, int]
    ultima_semana_fecha_inicio: date | None = Field(
        default=None, description="Inicio de la última semana observada, del calendario común."
    )
    umbral_cambio_pct: float = Field(
        description="Mismo umbral de alza o baja que el resumen comunal, para leer ambas vistas igual."
    )
    pronostico_generado_en: datetime
    objetivos: list[MetaObjetivoEstablecimiento]
    advertencias: list[str]
