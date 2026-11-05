import type { CambioEsperado } from "./api";

// Mismas dos etiquetas que el backend comunal, para leer ambas vistas igual.
// `clasificar` mide el tamano del cambio contra el umbral declarado por la API;
// `fueraDelIntervalo` dice si ademas se distingue de la fluctuacion semanal.

export function clasificar(variacion: number | null | undefined, umbralPct: number | null | undefined): CambioEsperado {
  if (variacion == null || umbralPct == null) return "sin_pronostico";
  if (variacion >= umbralPct) return "alza";
  if (variacion <= -umbralPct) return "baja";
  return "estable";
}

export function fueraDelIntervalo(
  reciente: number | null | undefined, inferior: number | null | undefined, superior: number | null | undefined,
): boolean | null {
  if (reciente == null || inferior == null || superior == null) return null;
  return reciente < inferior || reciente > superior;
}
