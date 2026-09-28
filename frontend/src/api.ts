// Cliente tipado de la API del SAAD. Los tipos reflejan src/api/schemas.py.
// Todo valor ausente llega como null y se muestra como "sin dato", nunca como 0.

export type EstadoProceso = "pendiente" | "calculando" | "listo" | "error";
export type Nivel = "region" | "comuna";
export type CambioEsperado = "alza" | "baja" | "estable" | "sin_pronostico";

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

export interface Meta {
  modelo: string | null;
  horizontes: number[];
  nivel_intervalo: number | null;
  ultima_semana_observada: PuntoHistorico | null;
  pronostico_calculado_en: string | null;
  comunas_con_pronostico: number;
  metricas_backtest: Record<string, number> | null;
  cobertura_holdout: CoberturaNivel[] | null;
  advertencias: string[];
}

export interface Salud {
  estado_datos: EstadoProceso;
  estado_pronostico: EstadoProceso;
  detalle: string | null;
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
  salud: () => obtener<Salud>("/salud"),
  meta: () => obtener<Meta>("/meta"),
  territorios: () => obtener<Territorio[]>("/territorios"),
  serie: (id: string, semanas: number, senal?: AbortSignal) =>
    obtener<SerieConPronostico>(`/series/${encodeURIComponent(id)}?semanas=${semanas}`, senal),
  resumenComunal: () => obtener<ResumenComuna[]>("/resumen-comunal"),
  geoComunas: () => obtener<GeoJSON.FeatureCollection>("/geo/comunas"),
};
