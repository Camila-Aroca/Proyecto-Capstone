// Cliente tipado de la API del SAAD. Los tipos reflejan src/api/schemas.py.
// Todo valor ausente llega como null y se muestra como "sin dato", nunca como 0.

export type EstadoProceso = "pendiente" | "calculando" | "listo" | "error";
export type Nivel = "region" | "comuna" | "establecimiento";
export type CambioEsperado = "alza" | "baja" | "estable" | "sin_pronostico";

export interface BarraCaracterizacion { etiqueta: string; valor: number }
export interface Caracterizacion {
  total: number;
  sexo: BarraCaracterizacion[] | null;
  edad: BarraCaracterizacion[];
  desde: string;
  hasta: string;
  semanas: number;
  escenario: {
    ano_referencia: number;
    sexo: BarraCaracterizacion[];
    referencia: BarraCaracterizacion[];
    fuente: string;
    metodo: string;
    advertencia: string;
  } | null;
}

export interface PuntoHistorico {
  ano: number;
  semana: number;
  fecha_inicio: string | null;
  atenciones: number;
}

export interface PuntoPronostico {
  horizonte: number;
  ano: number;
  semana: number;
  fecha_inicio: string | null;
  pronostico: number;
  limite_inferior: number;
  limite_superior: number;
}

export interface SerieConPronostico {
  series_id: string;
  nombre: string;
  nivel: Nivel;
  historico: PuntoHistorico[];
  pronostico: PuntoPronostico[] | null;
  estado_pronostico: EstadoProceso;
}

export interface Territorio {
  series_id: string;
  nombre: string;
  nivel: Nivel;
  tiene_pronostico: boolean;
  motivo_sin_pronostico: string | null;
}

export interface SemanaParcial {
  ano: number;
  semana: number;
  dias_observados: number;
  dias_esperados: number;
  /** Acumulado de los dias ya publicados, no el total de la semana. */
  atenciones: number;
}

export interface ResumenComuna {
  series_id: string;
  nombre: string;
  tiene_pronostico: boolean;
  motivo_sin_pronostico: string | null;
  promedio_ultimas_semanas: number | null;
  pronostico_promedio: number | null;
  variacion_pct: number | null;
  limite_inferior_promedio: number | null;
  limite_superior_promedio: number | null;
  cambio_esperado: CambioEsperado;
  /** True si el cambio queda fuera del intervalo: se distingue del ruido semanal. */
  fuera_del_intervalo: boolean | null;
  tasa_pronostico_por_10000: number | null;
  indicador_vulnerabilidad: number | null;
  oferta_urgencia_actual: number | null;
}

export interface CoberturaNivel {
  nivel: Nivel;
  cobertura_observada: number;
  evaluaciones: number;
  dentro_de_tolerancia: boolean;
}

export type OrigenPronostico = "persistido" | "en_memoria";

export interface Meta {
  modelo: string | null;
  horizontes: number[];
  /** Variacion a partir de la cual el resumen comunal declara alza o baja. */
  umbral_cambio_pct: number;
  /** Semana regional en curso, parcial: no comparable con semanas completas. */
  semana_en_curso: SemanaParcial | null;
  nivel_intervalo: number | null;
  ultima_semana_observada: PuntoHistorico | null;
  pronostico_calculado_en: string | null;
  origen_pronostico: OrigenPronostico | null;
  comunas_con_pronostico: number;
  metricas_backtest: Record<string, number> | null;
  cobertura_holdout: CoberturaNivel[] | null;
  advertencias: string[];
}

export interface HospitalCamas {
  establecimiento_codigo: number;
  nombre: string;
  camas_psiquiatria: number;
}

export interface CamasPsiquiatria {
  series_id: string;
  /** Ultimo ano de la dotacion de camas del SNSS. */
  ano_camas: number;
  /** Suma de camas de psiquiatria del territorio; null = sin dato, nunca 0. */
  total_camas_psiquiatria: number | null;
  n_hospitales_con_camas: number;
  n_hospitales_snss: number;
  /** Hospitales del territorio que reportaron ID36 en 2021-2025 (alimentan el modelo). */
  n_hospitales_modelo: number;
  hospitales: HospitalCamas[];
}

export interface Salud {
  estado_datos: EstadoProceso;
  estado_pronostico: EstadoProceso;
  detalle: string | null;
}

// --- Pronostico por establecimiento -------------------------------------
// Sin pronostico nunca es cero: cada objetivo trae el motivo.

export type ObjetivoEstablecimiento = "atenciones_sm" | "hospitalizaciones_sm";

export interface ResumenObjetivoEstablecimiento {
  incluido: boolean;
  motivo_sin_pronostico: string | null;
  promedio_ultimas_semanas: number | null;
  pronostico_promedio: number | null;
  variacion_pct: number | null;
  limite_inferior_promedio: number | null;
  limite_superior_promedio: number | null;
}

export type NivelColapso = "holgura" | "presion" | "saturacion" | "sobre_capacidad";

/** Ocupacion de las camas de psiquiatria del hospital en los ultimos 12 meses publicados (REM-20). */
export interface ColapsoPsiquiatria {
  nivel: NivelColapso;
  indice_ocupacional: number;
  meses: number;
  area_mes_sobre_capacidad: number;
  desde: string;
  hasta: string;
}

export interface EstablecimientoResumen {
  establecimiento_codigo: number;
  nombre: string;
  tipo: string;
  comuna_codigo: string;
  comuna: string;
  latitud: number | null;
  longitud: number | null;
  /** Dotacion declarada de psiquiatria; null = sin dato, nunca 0. */
  camas_psiquiatria: number | null;
  objetivos: Partial<Record<ObjetivoEstablecimiento, ResumenObjetivoEstablecimiento>>;
  /** Null = sin areas de psiquiatria en el REM-20 (no es cero). */
  colapso_psiquiatria?: ColapsoPsiquiatria | null;
}

export interface PuntoSemanal {
  ano: number;
  semana: number;
  fecha_inicio: string | null;
  valor: number;
}

export interface SerieObjetivoEstablecimiento {
  objetivo: ObjetivoEstablecimiento;
  descripcion: string;
  historico: PuntoSemanal[];
  pronostico: PuntoPronostico[] | null;
  motivo_sin_pronostico: string | null;
}

/** Total mensual de las camas de psiquiatria de un hospital (REM-20, promedio diario del mes). */
export interface PuntoOcupacionMensual {
  ano: number;
  mes: number;
  fecha_inicio: string;
  camas_ocupadas_promedio: number;
  camas_disponibles_promedio: number;
  /** Disponibles - ocupadas por dia: la brecha. Negativa = sobre la capacidad. */
  camas_libres_promedio: number;
  indice_ocupacional: number | null;
}

/** Saturacion de un area de psiquiatria en la ventana mostrada. */
export interface AreaPsiquiatria {
  nivel_cuidado_codigo: number;
  nivel_cuidado: string;
  meses: number;
  /** Meses con menos de una cama libre por dia, en promedio. */
  meses_sin_holgura: number;
  meses_sobre_capacidad: number;
  indice_ocupacional: number | null;
  ultimo_camas_ocupadas_promedio: number;
  ultimo_camas_disponibles_promedio: number;
  ultimo_camas_libres_promedio: number;
  /** Camas declaradas del area (libro de dotacion, ultimo ano); null = no declara, no cero. */
  dotacion_declarada?: number | null;
  ano_dotacion?: number | null;
  /** Causa observada de que el area no tenga dotacion declarada. */
  motivo_sin_dotacion?: string | null;
  /** Ocupacion mensual del area en la misma ventana. */
  serie: PuntoOcupacionMensual[];
}

export interface EstablecimientoDetalle {
  establecimiento_codigo: number;
  nombre: string;
  tipo: string;
  comuna_codigo: string;
  comuna: string;
  camas_psiquiatria: number | null;
  series: SerieObjetivoEstablecimiento[];
  /** Null = el hospital no tiene areas de psiquiatria en el REM-20 (no es cero). */
  ocupacion_psiquiatria?: PuntoOcupacionMensual[] | null;
  areas_psiquiatria?: AreaPsiquiatria[] | null;
}

export interface MetaObjetivoEstablecimiento {
  objetivo: ObjetivoEstablecimiento;
  descripcion: string;
  modelo: string;
  horizontes: number[];
  nivel_intervalo: number;
  establecimientos_con_pronostico: number;
  cobertura_holdout: number | null;
  pronosticos_fuera_de_rango: number;
}

export interface MetaEstablecimientos {
  ultima_semana_observada: { ano: number; semana: number };
  ultima_semana_fecha_inicio: string | null;
  /** Mismo umbral de alza o baja que la vista comunal. */
  umbral_cambio_pct: number;
  pronostico_generado_en: string;
  objetivos: MetaObjetivoEstablecimiento[];
  advertencias: string[];
}

// --- Suicidios semanales (defunciones X60-X84, comuna de residencia) -----

export interface PuntoSuicidios {
  ano: number;
  semana: number;
  fecha_inicio: string | null;
  suicidios: number;
}

export interface PuntoPronosticoSuicidios extends PuntoPronostico {
  /** Probabilidad que el modelo asigna al intervalo; en un conteo es >= al nivel nominal. */
  cobertura_esperada: number | null;
}

export interface CoberturaSuicidios {
  observada: number;
  esperada: number;
  evaluaciones: number;
}

export interface SerieSuicidios {
  series_id: string;
  nombre: string;
  nivel: Nivel;
  historico: PuntoSuicidios[];
  pronostico: PuntoPronosticoSuicidios[];
  suicidios_ultimas_52_semanas: number;
  /** Null si no hay poblacion para el territorio (nunca 0 por ausencia). */
  tasa_anual_por_100000: number | null;
  modelo: string;
  nivel_intervalo: number;
  ultima_semana_observada: { ano: number; semana: number };
  fecha_corte_datos: string;
  semanas_registro_incompleto: string[];
  cobertura_holdout: CoberturaSuicidios | null;
  advertencias: string[];
}

// --- Calendario de contexto: festividades de reunion y estaciones ----------

export type CategoriaEvento = "festividad" | "estacion";

export interface EventoCalendario {
  evento_id: string;
  nombre: string;
  categoria: CategoriaEvento;
  fecha_inicio: string;
  /** Ultimo dia incluido; igual al inicio si es un solo dia. */
  fecha_fin: string;
  /** Regla con que se obtuvo la fecha. */
  detalle: string;
}

const BASE = "/api/v1";
const MAX_REINTENTOS = 30;

export class ErrorApi extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const esperar = (ms: number) => new Promise((r) => setTimeout(r, ms));

// GET con reintento: un 503 con Retry-After significa "calculando", no "fallo".
async function obtener<T>(ruta: string, senal?: AbortSignal): Promise<T> {
  for (let intento = 0; intento < MAX_REINTENTOS; intento++) {
    const respuesta = await fetch(`${BASE}${ruta}`, { signal: senal });
    if (respuesta.ok) return (await respuesta.json()) as T;

    const cuerpo = await respuesta.json().catch(() => ({}));
    const detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : respuesta.statusText;
    const reintento = respuesta.headers.get("Retry-After");
    if (respuesta.status === 503 && reintento) {
      await esperar(Number(reintento) * 1000);
      continue;
    }
    throw new ErrorApi(respuesta.status, detalle);
  }
  throw new ErrorApi(503, "El backend sigue calculando; intente mas tarde.");
}

export const api = {
  caracterizacion: (fuente: string, nivel: Nivel, codigo: string, semanas: string, senal: AbortSignal) =>
    obtener<Caracterizacion>(`/caracterizacion/${fuente}/${nivel}/${encodeURIComponent(codigo)}?semanas=${encodeURIComponent(semanas)}`, senal),
  salud: () => obtener<Salud>("/salud"),
  meta: () => obtener<Meta>("/meta"),
  territorios: () => obtener<Territorio[]>("/territorios"),
  serie: (id: string, semanas: number, senal?: AbortSignal) =>
    obtener<SerieConPronostico>(`/series/${encodeURIComponent(id)}?semanas=${semanas}`, senal),
  camasPsiquiatria: (id: string, senal?: AbortSignal) =>
    obtener<CamasPsiquiatria>(`/camas-psiquiatria/${encodeURIComponent(id)}`, senal),
  resumenComunal: () => obtener<ResumenComuna[]>("/resumen-comunal"),
  geoComunas: () => obtener<GeoJSON.FeatureCollection>("/geo/comunas"),
  suicidios: (id: string, semanas: number, senal?: AbortSignal) =>
    obtener<SerieSuicidios>(`/suicidios/${encodeURIComponent(id)}?semanas=${semanas}`, senal),
  calendarioEventos: (desde: string, hasta: string) =>
    obtener<EventoCalendario[]>(`/calendario-eventos?desde=${desde}&hasta=${hasta}`),
  establecimientos: () => obtener<EstablecimientoResumen[]>("/establecimientos"),
  metaEstablecimientos: () => obtener<MetaEstablecimientos>("/establecimientos-meta"),
  establecimiento: (codigo: number, semanas: number, senal?: AbortSignal) =>
    obtener<EstablecimientoDetalle>(`/establecimientos/${codigo}?semanas=${semanas}`, senal),
};
