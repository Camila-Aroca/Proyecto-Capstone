// Definiciones compartidas por la vista por establecimiento, su detalle y su tabla.
import type {
  CambioEsperado,
  EstablecimientoDetalle,
  EstablecimientoResumen,
  NivelColapso,
  ObjetivoEstablecimiento,
  SerieConPronostico,
} from "../../api";
import { clasificar, fueraDelIntervalo } from "../../cambio";
import { fmtDecimal, fmtEntero } from "../../format";

export const OBJETIVOS: Record<ObjetivoEstablecimiento, { etiqueta: string; unidad: string; subtitulo: string }> = {
  atenciones_sm: {
    etiqueta: "Atenciones",
    unidad: "atenciones",
    subtitulo: "Atenciones semanales de urgencia en salud mental",
  },
  hospitalizaciones_sm: {
    etiqueta: "Hospitalizaciones",
    unidad: "hospitalizaciones",
    subtitulo: "Hospitalizaciones semanales indicadas desde la urgencia por trastornos mentales (F00-F99)",
  },
};

export const esObjetivo = (v: string | null): v is ObjetivoEstablecimiento =>
  v === "atenciones_sm" || v === "hospitalizaciones_sm";

// Volumenes de un digito pierden casi toda su informacion redondeados a entero.
export const fmtCifra = (v: number | null | undefined) => (v != null && Math.abs(v) < 10 ? fmtDecimal(v) : fmtEntero(v));

// Nivel de colapso: ocupacion de las camas de psiquiatria del hospital en los ultimos 12
// meses publicados (REM-20). Umbrales de la literatura, los mismos de la API y del EDA.
export const NIVELES: Record<NivelColapso, { etiqueta: string; orden: number }> = {
  holgura: { etiqueta: "Holgura", orden: 0 },
  presion: { etiqueta: "Presión", orden: 1 },
  saturacion: { etiqueta: "Saturación", orden: 2 },
  sobre_capacidad: { etiqueta: "Sobre la capacidad", orden: 3 },
};

/** El detalle de la API en la forma que usan el grafico y la tabla de la serie. */
export function aSerie(detalle: EstablecimientoDetalle, objetivo: ObjetivoEstablecimiento): SerieConPronostico | null {
  const serie = detalle.series.find((s) => s.objetivo === objetivo);
  if (!serie) return null;
  return {
    series_id: String(detalle.establecimiento_codigo),
    nombre: detalle.nombre,
    nivel: "establecimiento",
    historico: serie.historico.map((p) => ({
      ano: p.ano, semana: p.semana, fecha_inicio: p.fecha_inicio, atenciones: p.valor,
    })),
    pronostico: serie.pronostico,
    estado_pronostico: "listo",
  };
}

/** Cambio esperado de un establecimiento, con el mismo criterio que la vista por comuna. */
export function cambioDe(
  fila: EstablecimientoResumen, objetivo: ObjetivoEstablecimiento, umbral: number | null,
): { cambio: CambioEsperado; fuera: boolean | null } {
  const o = fila.objetivos[objetivo];
  if (!o?.incluido) return { cambio: "sin_pronostico", fuera: null };
  return {
    cambio: clasificar(o.variacion_pct, umbral),
    fuera: fueraDelIntervalo(o.promedio_ultimas_semanas, o.limite_inferior_promedio, o.limite_superior_promedio),
  };
}
