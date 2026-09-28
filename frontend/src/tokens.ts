import { useEffect, useState } from "react";
import type { CambioEsperado } from "./api";

// Recharts y Leaflet escriben los colores como atributos SVG, donde var(--x) no
// es confiable entre navegadores. Este hook resuelve los tokens CSS a valores
// concretos y los recalcula cuando cambia el modo claro/oscuro del sistema.

const NOMBRES = [
  "surface", "surface-2", "ink", "ink-2", "ink-3", "muted", "grid", "axis",
  "series-1", "band", "accent", "alza", "baja", "estable", "sin-dato",
  "seq-1", "seq-2", "seq-3", "seq-4", "seq-5",
] as const;

export type Token = (typeof NOMBRES)[number];
export type Tokens = Record<Token, string> & { oscuro: boolean };

const CONSULTA_OSCURO = "(prefers-color-scheme: dark)";

function leer(): Tokens {
  const estilos = getComputedStyle(document.documentElement);
  const valores = Object.fromEntries(
    NOMBRES.map((n) => [n, estilos.getPropertyValue(`--${n}`).trim()]),
  ) as Record<Token, string>;
  return { ...valores, oscuro: window.matchMedia(CONSULTA_OSCURO).matches };
}

export function useTokens(): Tokens {
  const [tokens, setTokens] = useState<Tokens>(leer);
  useEffect(() => {
    const consulta = window.matchMedia(CONSULTA_OSCURO);
    const actualizar = () => setTokens(leer());
    consulta.addEventListener("change", actualizar);
    return () => consulta.removeEventListener("change", actualizar);
  }, []);
  return tokens;
}

// --- Cambio esperado ------------------------------------------------------
// Alza o baja solo cuando el backend la declara distinguible del ruido
// semanal; el resto es "estable". Icono + texto, nunca color solo.

export const CAMBIO: Record<CambioEsperado, { etiqueta: string; icono: string; token: Token }> = {
  alza: { etiqueta: "Alza", icono: "▲", token: "alza" },
  baja: { etiqueta: "Baja", icono: "▼", token: "baja" },
  estable: { etiqueta: "Sin cambio claro", icono: "–", token: "estable" },
  sin_pronostico: { etiqueta: "Sin pronóstico", icono: "∅", token: "sin-dato" },
};

// --- Concentracion (tasa por 10.000 hab.) ---------------------------------
// Quintiles de las comunas con pronostico: cada clase tiene la misma cantidad
// de comunas, asi el mapa no queda dominado por un solo valor extremo.

export const CLASES_SECUENCIALES: Token[] = ["seq-1", "seq-2", "seq-3", "seq-4", "seq-5"];

export function cortesQuintiles(valores: number[]): number[] {
  const ordenados = [...valores].sort((a, b) => a - b);
  if (!ordenados.length) return [];
  return [0.2, 0.4, 0.6, 0.8].map((q) => ordenados[Math.floor(q * (ordenados.length - 1))]);
}

export function claseSecuencial(valor: number, cortes: number[]): number {
  const indice = cortes.findIndex((c) => valor <= c);
  return indice === -1 ? cortes.length : indice;
}
