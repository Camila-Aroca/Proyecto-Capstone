// Ocupacion mensual de las camas de psiquiatria de un hospital (REM-20). Va como
// grafico companero del de hospitalizaciones y no en su mismo eje: el ID42 es un
// flujo semanal (hospitalizaciones indicadas en la urgencia) y esto es un stock
// mensual (pacientes en cama por dia, de cualquier origen). Mezclarlos en una
// escala aplastaria la serie de hospitalizaciones y sugeriria una comparacion
// uno a uno que no existe.
import { useRef, useState, type ReactNode } from "react";
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
import type { AreaPsiquiatria, PuntoOcupacionMensual } from "../api";
import { fmtDecimal, fmtEntero, fmtMesCorto, fmtMesLargo } from "../format";
import type { Tokens } from "../tokens";
import { brilloCamas } from "./GraficoSerie";
import { resumirPropuestas } from '../propuestaCamas';

interface Props {
  meses: PuntoOcupacionMensual[];
  areas: AreaPsiquiatria[] | null;
  /** Dotacion declarada de psiquiatria; null si el hospital no la declara. */
  dotacion: number | null;
  tokens: Tokens;
}

// Menos de una cama libre por dia en promedio: mismo umbral que el EDA del mart.
const UMBRAL_HOLGURA = 1;

const fmtCamas = (v: number | null | undefined) => (v != null && Math.abs(v) < 10 ? fmtDecimal(v) : fmtEntero(v));
const fmtIndice = (v: number | null | undefined) => (v == null ? "sin dato" : `${fmtDecimal(v)}%`);
// "418 - Área Psiquiatría Adulto Corta estadía" -> "Psiquiatría Adulto Corta estadía"
const nombreArea = (glosa: string) => glosa.replace(/^\d{3}\s*-\s*/, "").replace(/^Área\s+(de\s+)?/i, "");

// Division con barra horizontal (numerador sobre denominador). Lo visual va oculto a los
// lectores de pantalla, que reciben la lectura en palabras.
function Fraccion({ num, den, lectura }: { num: ReactNode; den: ReactNode; lectura: string }) {
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
          <svg width="20" height="8" aria-hidden style={{ overflow: 'visible', opacity: 0.5, filter: brilloCamas(tokens['propuesta-camas'], true) }}>
            <line x1="0" y1="4" x2="20" y2="4" stroke={tokens['propuesta-camas']} strokeWidth="1.5" strokeDasharray="2 5" strokeLinecap="round" />
          </svg>
          Propuesta de dotación, {anoPropuesta}
        </li>
      )}
    </ul>
  );
}

function GraficoOcupacion({ meses, dotacion, tokens, titulo, propuesta }: Omit<Props, "areas"> & { titulo: string; propuesta: number | null }) {
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
        {propuesta != null && <span style={{ color: tokens['propuesta-camas'] }}>
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
              stroke={tokens['propuesta-camas']} strokeWidth={1.5} strokeOpacity={0.5}
              strokeDasharray="2 5" strokeLinecap="round"
              style={{ filter: brilloCamas(tokens['propuesta-camas'], true) }} />
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

function TablaAreas({ areas, ventana, elegida, elegir }: {
  areas: AreaPsiquiatria[];
  ventana: number;
  elegida: number | null;
  elegir: (codigo: number | null) => void;
}) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full border-collapse text-[13px] num">
        <caption className="mb-1.5 text-left text-[12px] text-3">
          Saturación por área, últimos {ventana} meses publicados. «Sin holgura»: menos de una cama libre por día en
          promedio del mes; se cuenta sobre los meses en que el área tuvo camas habilitadas. El total del hospital puede
          ocultar un área llena: sus camas no atienden a pacientes de otra área. Elija un área para verla en el gráfico.
        </caption>
        <thead>
          <tr className="text-left text-[12px] text-3">
            <th scope="col" className="px-2.5 py-1.5 font-medium">Área</th>
            <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Ocupación del período</th>
            <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Camas libres por día, último mes</th>
            <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Meses sin holgura</th>
          </tr>
        </thead>
        <tbody>
          {areas.map((a) => {
            const siempre = a.meses > 0 && a.meses_sin_holgura === a.meses;
            const cerrada = a.ultimo_camas_disponibles_promedio === 0;
            const activa = a.nivel_cuidado_codigo === elegida;
            return (
              <tr
                key={a.nivel_cuidado_codigo}
                className="transition-colors duration-150 hover:bg-(--accent-weak)"
                style={{
                  borderTop: "1px solid var(--grid)",
                  background: activa ? "var(--accent-weak)" : undefined,
                  boxShadow: activa ? "inset 0 0 0 1px var(--accent)" : undefined,
                }}
              >
                <th scope="row" className="px-2.5 py-1.5 text-left font-normal">
                  <button
                    type="button"
                    onClick={() => elegir(activa ? null : a.nivel_cuidado_codigo)}
                    aria-pressed={activa}
                    className={`min-h-6 text-left hover:underline ${activa ? "font-semibold" : "font-medium"}`}
                  >
                    {nombreArea(a.nivel_cuidado)}
                  </button>
                </th>
                <td className="px-2.5 py-1.5 text-right">{fmtIndice(a.indice_ocupacional)}</td>
                <td className="px-2.5 py-1.5 text-right">
                  {cerrada
                    ? <span className="text-3">sin camas habilitadas</span>
                    : a.ultimo_camas_libres_promedio < 0
                      ? `${fmtCamas(a.ultimo_camas_libres_promedio)} (sobre la capacidad)`
                      : `${fmtCamas(a.ultimo_camas_libres_promedio)} de ${fmtCamas(a.ultimo_camas_disponibles_promedio)}`}
                </td>
                <td className={`px-2.5 py-1.5 text-right ${siempre ? "font-semibold" : ""}`}>
                  {a.meses === 0 ? "—" : siempre ? `todos (${a.meses})` : `${a.meses_sin_holgura} de ${a.meses}`}
                  {a.meses_sobre_capacidad > 0 && <span className="text-2">, {a.meses_sobre_capacidad} sobre la capacidad</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Equivalente en tabla del grafico, plegado como el del pronostico.
function TablaMeses({ meses }: { meses: PuntoOcupacionMensual[] }) {
  return (
    <details className="mt-4 border-t border-[var(--border)] pt-3">
      <summary className="cursor-pointer text-[13px] text-2 select-none">Ver la ocupación mensual en tabla</summary>
      <div className="mt-3 max-h-72 overflow-auto">
        <table className="w-full border-collapse text-[13px] num">
          <caption className="sr-only">Camas de psiquiatría ocupadas, disponibles y libres por mes</caption>
          <thead>
            <tr className="text-left text-[12px] text-3">
              <th scope="col" className="px-2.5 py-1.5 font-medium">Mes</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Ocupadas</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Disponibles</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Libres</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Ocupación</th>
            </tr>
          </thead>
          <tbody>
            {[...meses].reverse().map((m) => (
              <tr key={`${m.ano}-${m.mes}`} className="border-t border-[var(--border)]">
                <td className="px-2.5 py-1.5">{fmtMesLargo(m.fecha_inicio)}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtCamas(m.camas_ocupadas_promedio)}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtCamas(m.camas_disponibles_promedio)}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtCamas(m.camas_libres_promedio)}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtIndice(m.indice_ocupacional)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function PanelOcupacion({ meses, areas, dotacion, tokens }: Props) {
  // null = total del hospital. Se reinicia al cambiar de hospital (la vista monta el panel con su codigo como key).
  const [elegida, setElegida] = useState<number | null>(null);
  const area = areas?.find((a) => a.nivel_cuidado_codigo === elegida) ?? null;
  const serie = area?.serie.length ? area.serie : meses;
  const ultimo = serie[serie.length - 1];
  // Solo areas con camas habilitadas el ultimo mes: una cerrada no esta saturada.
  const habilitadas = (areas ?? []).filter((a) => a.ultimo_camas_disponibles_promedio > 0);
  const saturadas = habilitadas.filter((a) => a.ultimo_camas_libres_promedio < UMBRAL_HOLGURA);
  const ventana = Math.max(...(areas ?? []).map((a) => a.meses), meses.length);
  const sinCamas = ultimo.camas_disponibles_promedio === 0;
  // La dotación sigue a lo elegido: la del hospital (suma de sus áreas) o la del área.
  const dotacionVisible = area ? (area.dotacion_declarada ?? null) : dotacion;
  const capacidadVisible = dotacionVisible ?? ultimo.camas_disponibles_promedio;
  const anosDotacion = [...new Set((areas ?? []).flatMap((a) => a.ano_dotacion == null ? [] : [a.ano_dotacion]))];
  const anoDotacionVisible = area?.ano_dotacion ?? (anosDotacion.length === 1 ? anosDotacion[0] : null);
  const propuesta = area?.propuesta_camas;
  const resumen = resumirPropuestas(areas, capacidadVisible);
  const aumentoVisible = area ? (propuesta?.aumento_dotacion ?? null) : resumen.aumento;
  const anoPropuesta = area ? propuesta?.ano_objetivo : resumen.ano;
  const lineaPropuesta = aumentoVisible != null && aumentoVisible > 0
    ? area ? (propuesta?.base_capacidad ?? capacidadVisible) + aumentoVisible : resumen.capacidadPropuesta : null;
  return (
    <section className="mt-6 border-t border-[var(--border)] pt-5" aria-labelledby="ocupacion-titulo">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div>
          <h3 id="ocupacion-titulo" className="text-[15px] font-semibold">Camas de psiquiatría: ocupación mensual</h3>
          <p className="text-[13px] text-3">
            Pacientes en cama por día, en promedio de cada mes, frente a las camas disponibles · REM-20, hasta{" "}
            {fmtMesLargo(ultimo.fecha_inicio)}
          </p>
        </div>
        <LeyendaOcupacion tokens={tokens} conDotacion={dotacionVisible != null}
          anoPropuesta={lineaPropuesta != null ? anoPropuesta : null} />
      </div>

      {areas && areas.length > 1 && (
        <div className="segmented mt-3" role="group" aria-label="Qué mostrar en el gráfico de ocupación">
          <button type="button" aria-pressed={area == null} onClick={() => setElegida(null)}>
            Total del hospital
          </button>
          {area && (
            <button type="button" aria-pressed onClick={() => setElegida(null)} title="Volver al total del hospital">
              {nombreArea(area.nivel_cuidado)} ✕
            </button>
          )}
        </div>
      )}
      {areas && areas.length > 1 && !area && (
        <p className="mt-1.5 text-[12px] text-3">Elija un área en la tabla para ver su ocupación en el gráfico.</p>
      )}

      <dl className="cifras-clave mt-4" aria-live="polite">
        <div>
          <dt className="text-[12px] text-3">Ocupación, {fmtMesLargo(ultimo.fecha_inicio)}</dt>
          <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
            {sinCamas ? "sin camas" : fmtIndice(ultimo.indice_ocupacional)}
          </dd>
          <dd className="text-[12px] text-3 num">
            {sinCamas
              ? "el área no tuvo camas habilitadas ese mes"
              : `${fmtCamas(ultimo.camas_ocupadas_promedio)} de ${fmtCamas(ultimo.camas_disponibles_promedio)} camas por día`}
          </dd>
        </div>
        {!sinCamas && (
          <div>
            <dt className="text-[12px] text-3">Camas libres por día</dt>
            <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
              {ultimo.camas_libres_promedio < 0
                ? `−${fmtCamas(-ultimo.camas_libres_promedio)}`
                : fmtCamas(ultimo.camas_libres_promedio)}
            </dd>
            <dd className="text-[12px] text-3">
              {ultimo.camas_libres_promedio < 0
                ? "sobre la capacidad, en promedio"
                : area ? "en promedio del mes, en esta área" : "en promedio del mes, todas las áreas"}
            </dd>
          </div>
        )}
        {area ? (
          <div>
            <dt className="text-[12px] text-3">Meses sin holgura</dt>
            <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
              {area.meses === 0 ? "—" : `${area.meses_sin_holgura} de ${area.meses}`}
            </dd>
            <dd className="text-[12px] text-3">meses con camas habilitadas en el período</dd>
          </div>
        ) : habilitadas.length > 0 && (
          <div>
            <dt className="text-[12px] text-3">Áreas sin holgura</dt>
            <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{saturadas.length} de {habilitadas.length}</dd>
            <dd className="text-[12px] text-3">con camas habilitadas: menos de una libre por día, último mes</dd>
          </div>
        )}
        <div>
          <dt className="text-[12px] text-3">Camas de psiquiatría{area ? ' del área' : ' del hospital'}</dt>
          <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
            {dotacionVisible == null ? fmtDecimal(capacidadVisible) : fmtEntero(capacidadVisible)}
          </dd>
          <dd className="text-[12px] text-3">
            {dotacionVisible == null ? `Disponibles por día, REM-20 (${fmtMesLargo(ultimo.fecha_inicio)})`
              : `Dotación declarada${anoDotacionVisible != null ? ` (${anoDotacionVisible})` : ''}`}
          </dd>
        </div>
        <div>
          <dt className="text-[12px] text-3">Aumento de dotación propuesto{anoPropuesta ? `, ${anoPropuesta}` : ''}</dt>
          {/* Sin cifra: la cifra grande queda atenuada ("—") y el estado va en el distintivo punteado
              de "sin dato" de la app, no como una frase en el tamaño de una cifra. */}
          <dd className={`mt-0.5 text-xl font-semibold tracking-tight num${aumentoVisible == null ? ' text-3' : ''}`}>
            {aumentoVisible == null ? '—' : `+${fmtEntero(aumentoVisible)} camas`}
          </dd>
          {aumentoVisible == null && (
            <dd className="mt-1">
              <span className="badge badge-sin_pronostico">
                <span className="badge-icon" aria-hidden>∅</span>
                Sin cálculo respaldado
              </span>
            </dd>
          )}
          <dd className={`text-[12px] text-3${aumentoVisible == null ? ' mt-1' : ''}`}>
            {!area ? `${resumen.areasConPropuesta} de ${resumen.areasTotales} áreas de psiquiatría${resumen.parcial ? '; subtotal parcial' : '; suma por área'}` : propuesta?.motivo ? propuesta.motivo
              : propuesta?.aumento_dotacion == null ? 'actualice los datos de capacidad'
              : propuesta.fuente_base === 'disponibles_rem20' ? 'respecto de disponibles REM-20; estimación'
              : 'respecto de la dotación declarada'}
          </dd>
        </div>
      </dl>

      {area && propuesta && (
        <div className="mt-4 max-w-[85ch] text-[13px] text-2" aria-live="polite">
          <p className="font-semibold">Propuesta de capacidad para {propuesta.ano_objetivo} · {nombreArea(area.nivel_cuidado)}</p>
          {propuesta.motivo ? <p className="mt-1 text-3">Sin propuesta: {propuesta.motivo}</p> : <>
            <p className="mt-1 num">
              Objetivo: <strong>{fmtEntero(propuesta.camas_objetivo)} camas habilitadas</strong>.
              {propuesta.fuente_base === 'disponibles_rem20'
                ? ` Aumento estimado de capacidad: +${fmtEntero(propuesta.aumento_dotacion)} camas respecto de ${fmtDecimal(propuesta.base_capacidad)} disponibles por día (REM-20). No permite distinguir camas nuevas de camas por rehabilitar.`
                : ` Aumento de dotación: +${fmtEntero(propuesta.aumento_dotacion)} camas respecto de ${fmtEntero(dotacionVisible)} declaradas (${area.ano_dotacion}).`}
              {propuesta.habilitar_existentes != null && propuesta.habilitar_existentes > 0
                ? ` Antes de ampliar: evaluar habilitar hasta ${fmtCamas(propuesta.habilitar_existentes)} camas declaradas hoy no disponibles, en promedio.` : ''}
            </p>
            <details className="mt-2 text-[12px] text-3">
              <summary className="cursor-pointer">Cálculo, evidencia y condiciones de implementación</summary>
              <p className="mt-3">Escenario de continuidad: se repite la carga de {propuesta.desde} a {propuesta.hasta}, sin crecimiento supuesto.</p>
              <ol className="mt-3 grid gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 sm:grid-cols-3" aria-label="Cómo se calcula el objetivo de camas">
                <li>
                  <p className="text-[11px] text-3">1. Carga del mes de mayor demanda</p>
                  <p className="mt-1 text-[15px] font-medium text-2 num">
                    <Fraccion num={fmtEntero(propuesta.pico_dias_cama_ocupados)} den={fmtEntero(propuesta.pico_dias_mes)}
                      lectura={`${fmtEntero(propuesta.pico_dias_cama_ocupados)} dividido por ${fmtEntero(propuesta.pico_dias_mes)}`} />
                  </p>
                  <p className="mt-1 text-[11px]">Días cama ocupados (una cama durante un día) ÷ días del mes</p>
                </li>
                <li className="border-t border-[var(--border)] pt-2 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-3">
                  <p className="text-[11px] text-3">2. Margen de planificación</p>
                  <p className="mt-1 text-[15px] font-medium text-2 num">
                    <Fraccion num="Carga" den="0,85" lectura="La carga del paso 1 dividida por 0,85" />
                  </p>
                  <p className="mt-1 text-[11px]">Objetivo de ocupación del 85%</p>
                </li>
                <li className="border-t border-[var(--border)] pt-2 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-3">
                  <p className="text-[11px] text-3">3. Capacidad objetivo</p>
                  <p className="mt-1 text-[15px] font-medium text-2 num">{fmtEntero(propuesta.camas_objetivo)} camas</p>
                  <p className="mt-1 text-[11px]">Se redondea hacia arriba solo al final</p>
                </li>
              </ol>
              <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                <div><dt className="inline">Con ocupación objetivo del 90%: </dt><dd className="inline font-medium text-2 num">{fmtEntero(propuesta.camas_objetivo_90)} camas</dd></div>
                <div><dt className="inline">Brecha frente al último mes: </dt><dd className="inline font-medium text-2 num">{fmtCamas(propuesta.brecha_habilitacion)} camas/día</dd></div>
              </dl>
              {!propuesta.referencia_aguda && <p className="mt-3 border-l-2 border-[var(--border-strong)] pl-3">En esta área, el 85% es un supuesto de planificación; no está validado como umbral específico de la especialidad.</p>}
              <details className="mt-3">
                <summary className="cursor-pointer text-2">Referencia y condiciones de uso</summary>
                <p className="mt-2">Referencia del 85%: <a className="underline" href="https://mentalhealthwatch.rcpsych.ac.uk/indicators/bed-occupancy-across-mental-health-trust" target="_blank" rel="noreferrer">Royal College of Psychiatrists</a>.
                  No es una norma chilena, una garantía diaria de cama ni un pronóstico anual validado. No mide espera, derivaciones rechazadas ni picos diarios.</p>
                <p className="mt-2">Implementar requiere validar presupuesto, personal, espacio y plazos localmente: estas fuentes no los incluyen. Las camas de otras áreas no sustituyen las de esta área.</p>
              </details>
            </details>
          </>}
        </div>
      )}
      {!area && (
        <details className="mt-3 text-[12px] text-3">
          <summary className="cursor-pointer">Desglose de la propuesta de camas de psiquiatría del hospital</summary>
          <p className="mt-2">Se suman los aumentos de cada área de psiquiatría, sin compensarlos con camas libres de otras áreas.
            {resumen.parcial ? ' El subtotal excluye las áreas sin cálculo respaldado; no se consideran cero.' : ''}
            {' '}Seleccione un área en la tabla para ver su capacidad y cálculo.</p>
          <ul className="mt-2 space-y-1">
            {(areas ?? []).map((a) => <li key={a.nivel_cuidado_codigo}>
              {nombreArea(a.nivel_cuidado)}: {a.propuesta_camas?.aumento_dotacion == null
                ? a.propuesta_camas?.motivo ?? 'sin datos para calcular'
                : `+${fmtEntero(a.propuesta_camas.aumento_dotacion)} camas`}.
            </li>)}
          </ul>
        </details>
      )}

      <div className="mt-5">
        <GraficoOcupacion
          meses={serie}
          dotacion={dotacionVisible}
          tokens={tokens}
          titulo={area ? nombreArea(area.nivel_cuidado) : "total del hospital"}
          propuesta={lineaPropuesta}
        />
        {lineaPropuesta != null && <p className="mt-1 text-[12px] text-2">
          <svg className="mr-1.5 inline" width="20" height="8" aria-hidden="true"><line x1="0" y1="4" x2="20" y2="4"
            stroke={tokens['propuesta-camas']} strokeWidth="1.5" strokeOpacity="0.5" strokeDasharray="2 5" strokeLinecap="round" /></svg>
          Propuesta {anoPropuesta}: {Number.isInteger(lineaPropuesta) ? fmtEntero(lineaPropuesta) : fmtDecimal(lineaPropuesta)} camas
          {dotacionVisible == null ? ' de capacidad estimada' : ' de dotación total'} (aumento +{fmtEntero(aumentoVisible)}).
          {!area && resumen.parcial ? ' Subtotal de áreas con cálculo respaldado.' : ''}
        </p>}
        {areas && areas.length > 0 && (
          <TablaAreas areas={areas} ventana={ventana} elegida={elegida} elegir={setElegida} />
        )}
        <p className="mt-3 max-w-[75ch] text-[12px] text-3">
          Promedio mensual publicado por el DEIS, no ocupación en tiempo real. Cuenta pacientes en camas de psiquiatría
          de cualquier origen, no solo los que llegan por la urgencia. Quien espera cama en la urgencia en camilla, silla
          o sillón no ocupa una de estas camas y no queda registrado: la ocupación real puede ser mayor que la que se
          muestra, en una magnitud que la fuente no permite medir.
        </p>
        {area?.motivo_sin_dotacion && (
          <p className="mt-2 max-w-[75ch] text-[12px] text-3">
            Sin dotación declarada para esta área: {area.motivo_sin_dotacion} El gráfico usa las camas disponibles del
            REM-20 como capacidad observada.
          </p>
        )}
        <TablaMeses meses={serie} />
        <details className="mt-2 border-t border-[var(--border)] pt-3">
          <summary className="cursor-pointer text-[13px] text-2 select-none">Ver caracterización por género y edad</summary>
          <p className="mt-3 text-[12px] text-3">REM-20 no publica sexo ni edad de quienes ocupan las camas. Las áreas de adultos e infanto-adolescentes se pueden consultar en el selector de áreas; no representan edades individuales.</p>
        </details>
      </div>
    </section>
  );
}
