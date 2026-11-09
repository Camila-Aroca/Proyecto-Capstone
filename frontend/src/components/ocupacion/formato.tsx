// Formato y piezas comunes del panel de ocupacion de camas de psiquiatria.
import type { ReactNode } from "react";
import { fmtDecimal, fmtEntero } from "../../format";

// Menos de una cama libre por dia en promedio: mismo umbral que el EDA del mart.
export const UMBRAL_HOLGURA = 1;

export const fmtCamas = (v: number | null | undefined) => (v != null && Math.abs(v) < 10 ? fmtDecimal(v) : fmtEntero(v));
export const fmtIndice = (v: number | null | undefined) => (v == null ? "sin dato" : `${fmtDecimal(v)}%`);
// "418 - Área Psiquiatría Adulto Corta estadía" -> "Psiquiatría Adulto Corta estadía"
export const nombreArea = (glosa: string) => glosa.replace(/^\d{3}\s*-\s*/, "").replace(/^Área\s+(de\s+)?/i, "");

// Division con barra horizontal (numerador sobre denominador). Lo visual va oculto a los
// lectores de pantalla, que reciben la lectura en palabras.
export function Fraccion({ num, den, lectura }: { num: ReactNode; den: ReactNode; lectura: string }) {
  return (
    <>
      <span aria-hidden className="inline-flex flex-col items-center text-center leading-tight align-middle">
        <span className="border-b border-current px-1.5 pb-0.5">{num}</span>
        <span className="px-1.5 pt-0.5">{den}</span>
      </span>
      <span className="sr-only">{lectura}</span>
    </>
  );
}
