// Grafico de ocupacion mensual (REM-20) y su leyenda. Va como grafico companero del
// de hospitalizaciones y no en su mismo eje: el ID42 es un flujo semanal y esto es
// un stock mensual (pacientes en cama por dia, de cualquier origen).
import { useRef, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PuntoOcupacionMensual } from "../../api";
import { fmtDecimal, fmtEntero, fmtMesCorto, fmtMesLargo } from "../../format";
import type { Tokens } from "../../tokens";
import { brilloCamas } from "../GraficoSerie";
import { fmtCamas, fmtIndice } from "./formato";

interface Punto extends PuntoOcupacionMensual {
  /** Banda de 0 a las camas disponibles: la capacidad, como area neutra de fondo. */
  capacidad: [number, number];
}

export function LeyendaOcupacion({ tokens, conDotacion, anoPropuesta }: {
  tokens: Tokens; conDotacion: boolean; anoPropuesta?: number | null;
}) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-2" aria-label="Leyenda del gráfico de ocupación">
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden><line x1="0" y1="4" x2="20" y2="4" stroke={tokens["series-1"]} strokeWidth="2" /></svg>
        Ocupadas (promedio diario)
      </li>
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="10" aria-hidden><rect width="20" height="10" rx="2" fill={tokens.grid} stroke={tokens.axis} /></svg>
        Disponibles
      </li>
      {conDotacion && (
        <li className="inline-flex items-center gap-1.5">
          <svg width="20" height="8" aria-hidden style={{ overflow: "visible", opacity: 0.5, filter: brilloCamas(tokens.camas, true) }}>
            <line x1="0" y1="4" x2="20" y2="4" stroke={tokens.camas} strokeWidth="1.5" strokeDasharray="2 5" strokeLinecap="round" />
          </svg>
          Dotación declarada
        </li>
      )}
      {anoPropuesta != null && (
        <li className="inline-flex items-center gap-1.5">
          <svg width="20" height="8" aria-hidden style={{ overflow: "visible", opacity: 0.5, filter: brilloCamas(tokens["propuesta-camas"], true) }}>
            <line x1="0" y1="4" x2="20" y2="4" stroke={tokens["propuesta-camas"]} strokeWidth="1.5" strokeDasharray="2 5" strokeLinecap="round" />
          </svg>
          Propuesta de dotación, {anoPropuesta}
        </li>
      )}
    </ul>
  );
}

export function GraficoOcupacion({ meses, dotacion, tokens, titulo, propuesta }: {
  meses: PuntoOcupacionMensual[];
  /** Dotacion declarada visible; null si no se declara. */
  dotacion: number | null;
  tokens: Tokens;
  titulo: string;
  propuesta: number | null;
}) {
  const puntos: Punto[] = meses.map((m) => ({ ...m, capacidad: [0, m.camas_disponibles_promedio] }));
  // Mismo hover que la linea de camas del grafico de hospitalizaciones: franja ancha
  // transparente sobre la linea de dotacion y un tooltip propio que oculta el del mes.
  const contenedor = useRef<HTMLDivElement>(null);
  const [sobreDotacion, setSobreDotacion] = useState<{ x: number; y: number } | null>(null);
  const moverSobreDotacion = (e: { clientX: number; clientY: number }) => {
    const caja = contenedor.current?.getBoundingClientRect();
    if (caja) setSobreDotacion({ x: e.clientX - caja.left, y: e.clientY - caja.top });
  };
  return (
    <>
    {(dotacion != null || propuesta != null) && (
      <div className="mb-2 flex flex-wrap justify-end gap-x-4 gap-y-1 text-[11px] num" aria-label="Referencias de capacidad del gráfico">
        {dotacion != null && <span style={{ color: tokens.camas }}>
          Dotación: {Number.isInteger(dotacion) ? fmtEntero(dotacion) : fmtDecimal(dotacion)} camas
        </span>}
        {propuesta != null && <span style={{ color: tokens["propuesta-camas"] }}>
          Propuesta: {Number.isInteger(propuesta) ? fmtEntero(propuesta) : fmtDecimal(propuesta)} camas
        </span>}
      </div>
    )}
    <div
      ref={contenedor}
      className="relative h-56"
      role="img"
      aria-label={`Camas de psiquiatría ocupadas y disponibles por mes: ${titulo}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={puntos} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={tokens.grid} vertical={false} />
          <XAxis
            dataKey="fecha_inicio"
            tickFormatter={(f: string) => fmtMesCorto(f)}
            tick={{ fill: tokens["ink-3"], fontSize: 11 }}
            axisLine={{ stroke: tokens.axis }}
            tickLine={false}
            minTickGap={24}
          />
          {/* Desde cero: la brecha se lee en camas reales, sin exagerarla con el eje. */}
          <YAxis
            domain={[0, "auto"]}
            tickFormatter={(v: number) => fmtEntero(v)}
            tick={{ fill: tokens["ink-3"], fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={sobreDotacion ? false : { stroke: tokens.axis, strokeWidth: 1 }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              const p = active && !sobreDotacion ? (payload?.[0]?.payload as Punto | undefined) : undefined;
              if (!p) return null;
              const libres = p.camas_libres_promedio;
              return (
                <div className="panel px-3 py-2 text-[12px] num shadow-sm">
                  <p className="font-semibold">{fmtMesLargo(p.fecha_inicio)}</p>
                  <p>Ocupadas: {fmtCamas(p.camas_ocupadas_promedio)} camas por día</p>
                  <p>Disponibles: {fmtCamas(p.camas_disponibles_promedio)}</p>
                  <p>
                    {libres < 0
                      ? `Sobre la capacidad: ${fmtCamas(-libres)} camas por día`
                      : `Libres: ${fmtCamas(libres)} camas por día`}
                  </p>
                  <p className="text-2">Ocupación {fmtIndice(p.indice_ocupacional)}</p>
                </div>
              );
            }}
          />
          <Area
            dataKey="capacidad"
            stroke={tokens.axis}
            strokeWidth={1}
            fill={tokens.grid}
            fillOpacity={1}
            activeDot={false}
            isAnimationActive={false}
          />
          {dotacion != null && (
            <>
              <ReferenceLine
                y={dotacion}
                ifOverflow="extendDomain"
                stroke={tokens.camas}
                strokeWidth={1.5}
                strokeOpacity={0.5}
                strokeDasharray="2 5"
                strokeLinecap="round"
                style={{ filter: brilloCamas(tokens.camas, true) }}
              />
              <ReferenceLine
                y={dotacion}
                ifOverflow="extendDomain"
                stroke="transparent"
                strokeWidth={16}
                onMouseEnter={moverSobreDotacion}
                onMouseMove={moverSobreDotacion}
                onMouseLeave={() => setSobreDotacion(null)}
              />
            </>
          )}
          <Line
            dataKey="camas_ocupadas_promedio"
            stroke={tokens["series-1"]}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          {propuesta != null && (
            <ReferenceLine y={propuesta} ifOverflow="extendDomain"
              stroke={tokens["propuesta-camas"]} strokeWidth={1.5} strokeOpacity={0.5}
              strokeDasharray="2 5" strokeLinecap="round"
              style={{ filter: brilloCamas(tokens["propuesta-camas"], true) }} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      {sobreDotacion && dotacion != null && (
        <div
          role="tooltip"
          className="panel pointer-events-none absolute z-10 max-w-[260px] px-3 py-2 text-[12px] shadow-sm"
          style={{
            left: Math.max(Math.min(sobreDotacion.x + 12, (contenedor.current?.clientWidth ?? 0) - 272), 0),
            top: Math.max(sobreDotacion.y - 64, 0),
            borderColor: tokens.camas,
          }}
        >
          Dotación declarada {titulo === "total del hospital" ? "de psiquiatría del hospital" : `del área ${titulo}`}:{" "}
          {fmtEntero(dotacion)} camas. Es el stock anual declarado (SNSS); las disponibles del REM-20 descuentan las
          no habilitadas.
        </div>
      )}
    </div>
    </>
  );
}
