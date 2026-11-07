// Marcas de contexto sobre un grafico semanal: lineas verticales hasta el eje x y, si
// la marca dura varios dias, una banda del mismo color, mas transparente, entre sus
// lineas. Son contexto para leer la serie, no explicaciones de sus variaciones.
//
// El eje x es categorico (una categoria por semana), pero una fecha cae en cualquier
// dia: su posicion se interpola entre las semanas vecinas usando la escala del propio
// grafico, asi la marca queda exacta aunque la semana tenga otro largo (bordes de
// año) y aunque el eje este alineado con el de otro grafico.
import type { ReactElement } from "react";
import { usePlotArea, useXAxisScale } from "recharts";
import { fmtFechaCorta } from "../format";

const DIA_MS = 86_400_000;
// Recesivas: el protagonista es la serie.
const OPACIDAD_LINEA = 0.75;
const OPACIDAD_BANDA = 0.09;

export interface MarcaTemporal {
  id: string;
  nombre: string;
  /** Agrupa las marcas en la leyenda y define el trazo (punteado para festividades). */
  categoria: "festividad" | "estacion";
  /** Primer y ultimo dia incluidos (AAAA-MM-DD). */
  inicio: string;
  fin: string;
  detalle: string;
  color: string;
}

const ms = (iso: string) => new Date(iso).getTime();

/** Texto corto de las fechas de una marca: "24 dic" o "24 dic – 25 dic". */
export function fechasMarca(m: MarcaTemporal): string {
  return m.inicio === m.fin ? fmtFechaCorta(m.inicio) : `${fmtFechaCorta(m.inicio)} – ${fmtFechaCorta(m.fin)}`;
}

/**
 * Marcas que tocan cada semana del eje: la semana de `fechas[i]` va hasta el dia antes
 * de `fechas[i + 1]` (la ultima, 7 dias). Alimenta el tooltip.
 */
export function marcasPorSemana(fechas: string[], marcas: MarcaTemporal[]): Map<string, MarcaTemporal[]> {
  const salida = new Map<string, MarcaTemporal[]>();
  fechas.forEach((fecha, i) => {
    const inicio = ms(fecha);
    const siguiente = fechas[i + 1];
    const fin = siguiente && ms(siguiente) > inicio ? ms(siguiente) : inicio + 7 * DIA_MS;
    const propias = marcas.filter((m) => ms(m.inicio) < fin && ms(m.fin) + DIA_MS > inicio);
    if (propias.length) salida.set(fecha, propias);
  });
  return salida;
}

/** Capa SVG dentro del grafico (hija de ComposedChart): bandas detras, lineas encima. */
export function CapaMarcas({ marcas, fechas }: { marcas: MarcaTemporal[]; fechas: string[] }) {
  const escala = useXAxisScale();
  const area = usePlotArea();
  if (!escala || !area || !marcas.length) return null;

  // Anclas fecha -> pixel de cada semana del eje, en orden temporal estricto.
  const anclas: { t: number; x: number }[] = [];
  for (const fecha of fechas) {
    const x = escala(fecha);
    const t = ms(fecha);
    if (typeof x === "number" && Number.isFinite(x) && (!anclas.length || t > anclas[anclas.length - 1].t)) {
      anclas.push({ t, x });
    }
  }
  if (anclas.length < 2) return null;

  const aPixel = (t: number): number => {
    let k = anclas.findIndex((a) => a.t > t) - 1;
    if (k === -2) k = anclas.length - 2; // despues de la ultima ancla: se extrapola con el ultimo tramo
    if (k < 0) k = 0; // antes de la primera: con el primero
    const a = anclas[k];
    const b = anclas[k + 1];
    return a.x + ((t - a.t) / (b.t - a.t)) * (b.x - a.x);
  };
  const izquierda = area.x;
  const derecha = area.x + area.width;
  const dentro = (x: number) => x >= izquierda - 0.5 && x <= derecha + 0.5;

  const bandas: ReactElement[] = [];
  const lineas: ReactElement[] = [];
  for (const m of marcas) {
    const punteada = m.categoria === "festividad" ? "4 3" : undefined;
    const linea = (x: number, clave: string) =>
      dentro(x) && lineas.push(
        <line key={clave} x1={x} x2={x} y1={area.y} y2={area.y + area.height} stroke={m.color}
          strokeOpacity={OPACIDAD_LINEA} strokeWidth={1.25} strokeDasharray={punteada} />,
      );
    if (m.inicio === m.fin) {
      // Un solo dia: una linea a mitad del dia.
      linea(aPixel(ms(m.inicio) + DIA_MS / 2), `${m.id}-dia`);
      continue;
    }
    const x1 = aPixel(ms(m.inicio));
    const x2 = aPixel(ms(m.fin) + DIA_MS); // fin incluido: la banda termina al cerrar el ultimo dia
    const a = Math.max(x1, izquierda);
    const b = Math.min(x2, derecha);
    if (b > a) {
      bandas.push(
        <rect key={`${m.id}-banda`} x={a} y={area.y} width={b - a} height={area.height} fill={m.color}
          fillOpacity={OPACIDAD_BANDA} />,
      );
    }
    linea(x1, `${m.id}-inicio`);
    linea(x2, `${m.id}-fin`);
  }
  return (
    // Sin tooltip nativo (<title>) ni eventos de puntero: el hover lo atiende solo el Tooltip del grafico,
    // que ya nombra las marcas de la semana; la regla completa esta en "Ver las fechas marcadas".
    <g className="marcas-temporales" aria-hidden pointerEvents="none">
      {bandas}
      {lineas}
    </g>
  );
}
