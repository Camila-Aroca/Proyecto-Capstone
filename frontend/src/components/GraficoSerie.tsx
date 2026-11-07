import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";
import type { CamasPsiquiatria, SemanaParcial, SerieConPronostico } from "../api";
import { fmtEntero, fmtFechaCorta, fmtFechaLarga, fmtMedia } from "../format";
import type { Tokens } from "../tokens";
import { CapaMarcas, fechasMarca, marcasPorSemana, type MarcaTemporal } from "./MarcasTemporales";

interface Props {
  serie: SerieConPronostico;
  tokens: Tokens;
  intervalo: string;
  /** Semana en curso, parcial. Solo aplica a la serie regional: el dato es de toda la RM. */
  semanaParcial?: SemanaParcial | null;
  /** Que cuenta la serie, en plural y minusculas: "atenciones" u "hospitalizaciones". */
  unidad?: string;
  /** Color de la serie y de su banda; por defecto la serie principal (petroleo). */
  color?: string;
  banda?: string;
  /** Pronostico con un decimal: en series de conteos bajos (p. ej. 0,2 por semana) el entero diria 0. */
  decimales?: boolean;
  /** Eje de otro grafico (`ejeDeSerie`): este grafico muestra exactamente esas semanas. */
  eje?: SemanaEje[] | null;
  /** Marcas de contexto (festividades, estaciones): lineas verticales y bandas. */
  marcas?: MarcaTemporal[];
  /**
   * Altura minima del eje y, que parte en 0, con marcas en numeros limpios. En series
   * de conteos bajos evita que el eje se ajuste a 0-1 y que una semana con un caso
   * llene todo el grafico.
   */
  pisoEje?: number;
  /**
   * Lectura del hover anclada arriba del grafico (sigue la semana, no salta en vertical
   * ni tapa la linea), con el valor de cada serie junto a su clave de linea.
   */
  tooltipAnclado?: boolean;
}

// Marcas del eje y en enteros limpios: paso 1, 2 o 5 por potencia de 10, nunca menor a
// 1 (son conteos). Con un maximo dado, Recharts repartiria el eje en pasos como 7.
function marcasEnteras(max: number): number[] {
  const bruto = Math.max(max, 1) / 4;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const paso = Math.max(1, [1, 2, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? 10 * potencia);
  return Array.from({ length: Math.ceil(max / paso) + 1 }, (_, i) => i * paso);
}

function ClaveLinea({ color, discontinua = false }: { color: string; discontinua?: boolean }) {
  return (
    <svg width="16" height="8" className="shrink-0" aria-hidden>
      <line x1="0" y1="4" x2="16" y2="4" stroke={color} strokeWidth="2" strokeDasharray={discontinua ? "4 3" : undefined} />
    </svg>
  );
}

function FilaLectura({ clave, etiqueta, valor }: { clave: ReactNode; etiqueta: string; valor: string }) {
  return (
    <div className="flex items-center gap-2">
      {clave}
      <span className="text-2">{etiqueta}</span>
      <span className="ml-auto pl-5 font-semibold">{valor}</span>
    </div>
  );
}

// Lectura de una semana: fecha en segundo plano, una fila por serie (el valor manda) y
// el contexto del calendario separado por una linea, mas tenue.
function LecturaSemana({ p, unidad, intervalo, trazo, banda, fmtPronostico, marcas }: {
  p: Punto;
  unidad: string;
  intervalo: string;
  trazo: string;
  banda: string;
  fmtPronostico: (v: number) => string;
  marcas: MarcaTemporal[];
}) {
  return (
    <div className="panel min-w-52 px-3 py-2 text-[12px] leading-relaxed num shadow-sm">
      <p className="text-3">Semana {p.semana} · {fmtFechaLarga(p.fecha)}</p>
      <div className="mt-1">
        {p.observado != null && (
          <FilaLectura clave={<ClaveLinea color={trazo} />} etiqueta={mayuscula(unidad)} valor={fmtEntero(p.observado)} />
        )}
        {p.pronostico != null && p.banda && (
          <>
            <FilaLectura clave={<ClaveLinea color={trazo} discontinua />} etiqueta="Pronóstico" valor={fmtPronostico(p.pronostico)} />
            <FilaLectura
              clave={<svg width="16" height="8" className="shrink-0" aria-hidden><rect width="16" height="8" rx="2" fill={banda} /></svg>}
              etiqueta={`Intervalo ${intervalo}`}
              valor={`${fmtEntero(p.banda[0])} – ${fmtEntero(p.banda[1])}`}
            />
          </>
        )}
        {p.sinPronostico && <p className="text-3">Sin dato observado ni pronóstico.</p>}
      </div>
      {marcas.length > 0 && (
        <div className="mt-1.5 border-t border-[var(--border)] pt-1.5 text-3">
          {marcas.map((m) => (
            <p key={m.id} className="flex items-center gap-2">
              <svg width="16" height="10" className="shrink-0" aria-hidden>
                <line x1="8" y1="0" x2="8" y2="10" stroke={m.color} strokeWidth="2"
                  strokeDasharray={m.categoria === "festividad" ? "3 2" : undefined} />
              </svg>
              {m.nombre} ({fechasMarca(m)})
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// Halo de la linea de camas (dotacion declarada): dos sombras del mismo color, una
// ceñida y otra difusa. La version sutil es un fondo, no un protagonista.
export const brilloCamas = (color: string, sutil = false) =>
  sutil
    ? `drop-shadow(0 0 1px ${color}) drop-shadow(0 0 4px ${color})`
    : `drop-shadow(0 0 2px ${color}) drop-shadow(0 0 7px ${color})`;

// Texto de las camas del territorio, en la tabla de datos.
export function textoCamas(camas: CamasPsiquiatria, total: number): string {
  const hospitales = camas.n_hospitales_con_camas === 1 ? "1 hospital" : `${camas.n_hospitales_con_camas} hospitales`;
  return `Camas de psiquiatría de los hospitales que reportan a Urgencias (${camas.ano_camas}): ${fmtEntero(total)}, ${hospitales}. Dotación declarada, no ocupación.`;
}

const mayuscula = (texto: string) => texto.charAt(0).toUpperCase() + texto.slice(1);

interface Punto {
  fecha: string;
  ano: number;
  semana: number;
  observado: number | null;
  pronostico: number | null;
  banda: [number, number] | null;
  sinPronostico: boolean;
  /** Acumulado de los dias ya publicados de la semana en curso; no es la semana completa. */
  parcial: number | null;
  diasParciales: number | null;
}

const DIA_MS = 86_400_000;

// Une historia y pronostico en un solo eje temporal. Las semanas entre la ultima
// observada y el primer horizonte (h < 4) se incluyen vacias: el modelo no las
// pronostica, y ocultarlas acortaria visualmente el horizonte real.
function construirPuntos(serie: SerieConPronostico, parcial?: SemanaParcial | null): Punto[] {
  const puntos: Punto[] = serie.historico.map((h) => ({
    fecha: h.fecha_inicio ?? "",
    ano: h.ano,
    semana: h.semana,
    observado: h.atenciones,
    pronostico: null,
    banda: null,
    sinPronostico: false,
    parcial: null,
    diasParciales: null,
  }));
  const pronostico = serie.pronostico ?? [];
  const ultima = serie.historico.at(-1);
  if (ultima?.fecha_inicio && pronostico.length) {
    const base = new Date(ultima.fecha_inicio).getTime();
    for (let h = 1; h < pronostico[0].horizonte; h++) {
      puntos.push({
        fecha: new Date(base + h * 7 * DIA_MS).toISOString().slice(0, 10),
        ano: ultima.ano + Math.floor((ultima.semana + h - 1) / 52),
        semana: ((ultima.semana + h - 1) % 52) + 1,
        observado: null,
        pronostico: null,
        banda: null,
        sinPronostico: true,
        parcial: null,
        diasParciales: null,
      });
    }
  }
  for (const p of pronostico) {
    puntos.push({
      fecha: p.fecha_inicio ?? "",
      ano: p.ano,
      semana: p.semana,
      observado: null,
      pronostico: p.pronostico,
      banda: [p.limite_inferior, p.limite_superior],
      sinPronostico: false,
      parcial: null,
      diasParciales: null,
    });
  }
  if (parcial) {
    // Por año y semana: solo por semana, la parcial caia en la misma semana del año anterior.
    const existente = puntos.find((p) => p.ano === parcial.ano && p.semana === parcial.semana);
    if (existente) {
      existente.parcial = parcial.atenciones;
      existente.diasParciales = parcial.dias_observados;
    } else {
      // Semana que no esta en la historia ni en el pronostico (p. ej. la siguiente a la
      // ultima completa cuando el pronostico parte una semana despues): se inserta en su
      // lugar cronologico, con su fecha a 7 dias por semana de la anterior.
      const orden = (ano: number, semana: number) => ano * 100 + semana;
      const posterior = puntos.findIndex((p) => orden(p.ano, p.semana) > orden(parcial.ano, parcial.semana));
      const previo = posterior === -1 ? puntos.at(-1) : puntos[posterior - 1];
      const semanas = previo
        ? parcial.semana - previo.semana + (parcial.ano - previo.ano) * 52
        : 0;
      const fecha = previo?.fecha && semanas > 0
        ? new Date(new Date(previo.fecha).getTime() + semanas * 7 * DIA_MS).toISOString().slice(0, 10)
        : "";
      const punto: Punto = {
        fecha,
        ano: parcial.ano,
        semana: parcial.semana,
        observado: null,
        pronostico: null,
        banda: null,
        sinPronostico: false,
        parcial: parcial.atenciones,
        diasParciales: parcial.dias_observados,
      };
      if (posterior === -1) puntos.push(punto);
      else puntos.splice(posterior, 0, punto);
    }
  }
  return puntos;
}

/** Semana del eje x de un grafico: su fecha de inicio (categoria del eje) y su numero DEIS. */
export interface SemanaEje {
  fecha: string;
  ano: number;
  semana: number;
  /** True si en el grafico de origen la semana es dato observado (no pronostico ni vacia). */
  observada: boolean;
}

/** Eje x exacto de un grafico de serie, para alinear otro grafico a las mismas semanas. */
export function ejeDeSerie(serie: SerieConPronostico, parcial?: SemanaParcial | null): SemanaEje[] {
  return construirPuntos(serie, parcial)
    .filter((p) => p.fecha)
    .map(({ fecha, ano, semana, observado }) => ({ fecha, ano, semana, observada: observado != null }));
}

// Reindexa los puntos a un eje ajeno: cada semana del eje lleva el punto propio de esa
// fecha, o queda vacia (sin dato observado ni pronostico), nunca en cero.
function alinear(puntos: Punto[], eje: SemanaEje[]): Punto[] {
  const porFecha = new Map(puntos.map((p) => [p.fecha, p]));
  return eje.map((e) => porFecha.get(e.fecha) ?? {
    fecha: e.fecha, ano: e.ano, semana: e.semana, observado: null, pronostico: null, banda: null,
    sinPronostico: true, parcial: null, diasParciales: null,
  });
}

export function LeyendaSerie({ tokens, intervalo, conParcial = true, color, banda }: {
  tokens: Tokens;
  intervalo: string;
  /** Solo la serie regional tiene semana en curso parcial. */
  conParcial?: boolean;
  color?: string;
  banda?: string;
}) {
  const trazo = color ?? tokens["series-1"];
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-2" aria-label="Leyenda del gráfico">
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden><line x1="0" y1="4" x2="20" y2="4" stroke={trazo} strokeWidth="2" /></svg>
        Observado
      </li>
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden><line x1="0" y1="4" x2="20" y2="4" stroke={trazo} strokeWidth="2" strokeDasharray="4 3" /></svg>
        Pronóstico
      </li>
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="10" aria-hidden><rect width="20" height="10" rx="2" fill={banda ?? tokens.band} /></svg>
        Intervalo {intervalo}
      </li>
      {conParcial && <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="10" aria-hidden>
          <circle cx="10" cy="5" r="4" fill={tokens.surface} stroke={tokens["ink-3"]} strokeWidth="2" strokeDasharray="2 2" />
        </svg>
        Semana en curso (parcial)
      </li>}
    </ul>
  );
}

// Equivalente en tabla del grafico: ningun valor queda accesible solo por hover
// ni solo por color. Va plegada para no competir con el grafico, pero existe
// siempre y es navegable por teclado.
export function TablaSerie({ serie, intervalo, semanaParcial, camas, unidad = "atenciones", decimales = false }: {
  serie: SerieConPronostico;
  intervalo: string;
  semanaParcial?: SemanaParcial | null;
  camas?: CamasPsiquiatria | null;
  unidad?: string;
  decimales?: boolean;
}) {
  const fmtPronostico = decimales ? fmtMedia : fmtEntero;
  const observadas = serie.historico.slice(-12);
  const pronosticadas = serie.pronostico ?? [];
  return (
    <details className="mt-4 border-t border-[var(--border)] pt-3">
      <summary className="cursor-pointer text-[13px] text-2 select-none">
        Ver los datos en tabla
      </summary>
      <div className="mt-3 max-h-72 overflow-auto">
        <table className="w-full border-collapse text-[13px] num">
          <caption className="sr-only">
            {mayuscula(unidad)} semanales observadas y pronosticadas de {serie.nombre}
          </caption>
          <thead>
            <tr className="text-left text-[12px] text-3">
              <th scope="col" className="px-2.5 py-1.5 font-medium">Semana</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Inicio</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">{mayuscula(unidad)}</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Intervalo {intervalo}</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Tipo</th>
            </tr>
          </thead>
          <tbody>
            {observadas.map((h) => (
              <tr key={`o-${h.ano}-${h.semana}`} className="border-t border-[var(--border)]">
                <td className="px-2.5 py-1.5">{h.ano}-S{String(h.semana).padStart(2, "0")}</td>
                <td className="px-2.5 py-1.5">{h.fecha_inicio ? fmtFechaCorta(h.fecha_inicio) : "—"}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtEntero(h.atenciones)}</td>
                <td className="px-2.5 py-1.5 text-right text-3">—</td>
                <td className="px-2.5 py-1.5 text-2">Observado</td>
              </tr>
            ))}
            {semanaParcial && (
              <tr className="border-t border-[var(--border)]">
                <td className="px-2.5 py-1.5">
                  {semanaParcial.ano}-S{String(semanaParcial.semana).padStart(2, "0")}
                </td>
                <td className="px-2.5 py-1.5 text-3">—</td>
                <td className="px-2.5 py-1.5 text-right">{fmtEntero(semanaParcial.atenciones)}</td>
                <td className="px-2.5 py-1.5 text-right text-3">—</td>
                <td className="px-2.5 py-1.5 text-2">
                  Parcial: {semanaParcial.dias_observados} de {semanaParcial.dias_esperados} días
                </td>
              </tr>
            )}
            {pronosticadas.map((p) => (
              <tr key={`p-${p.horizonte}`} className="border-t border-[var(--border)]">
                <td className="px-2.5 py-1.5">{p.ano}-S{String(p.semana).padStart(2, "0")}</td>
                <td className="px-2.5 py-1.5">{p.fecha_inicio ? fmtFechaCorta(p.fecha_inicio) : "—"}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtPronostico(p.pronostico)}</td>
                <td className="px-2.5 py-1.5 text-right">
                  {fmtEntero(p.limite_inferior)} – {fmtEntero(p.limite_superior)}
                </td>
                <td className="px-2.5 py-1.5 text-2">Pronóstico (h+{p.horizonte})</td>
              </tr>
            ))}
          </tbody>
        </table>
        {camas?.total_camas_psiquiatria != null && (
          <div className="mt-4 text-[13px]">
            <p className="font-medium">{textoCamas(camas, camas.total_camas_psiquiatria)}</p>
            <ul className="mt-1.5 space-y-0.5 text-2 num">
              {camas.hospitales.map((h) => (
                <li key={h.establecimiento_codigo}>
                  {h.nombre}: {fmtEntero(h.camas_psiquiatria)} camas
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}

export function GraficoSerie({
  serie, tokens, intervalo, semanaParcial, unidad = "atenciones", color, banda, decimales = false, eje, marcas,
  pisoEje, tooltipAnclado = false,
}: Props) {
  const propios = construirPuntos(serie, semanaParcial);
  const puntos = eje ? alinear(propios, eje) : propios;
  const fechas = puntos.map((p) => p.fecha);
  const marcasSemana = marcas?.length ? marcasPorSemana(fechas, marcas) : null;
  const trazo = color ?? tokens["series-1"];
  const fmtPronostico = decimales ? fmtMedia : fmtEntero;
  let marcasY: number[] | undefined;
  if (pisoEje != null) {
    let maximo = pisoEje;
    for (const p of puntos) {
      for (const v of [p.observado, p.pronostico, p.banda?.[1], p.parcial]) if (v != null && v > maximo) maximo = v;
    }
    marcasY = marcasEnteras(maximo);
  }
  return (
    <div
      className="relative h-72"
      role="img"
      aria-label={`${mayuscula(unidad)} semanales observadas y pronosticadas de ${serie.nombre}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={puntos} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={tokens.grid} vertical={false} />
          <XAxis
            dataKey="fecha"
            tickFormatter={(f: string) => fmtFechaCorta(f)}
            tick={{ fill: tokens["ink-3"], fontSize: 11 }}
            axisLine={{ stroke: tokens.axis }}
            tickLine={false}
            minTickGap={40}
          />
          <YAxis
            domain={marcasY ? [0, marcasY[marcasY.length - 1]] : ["auto", "auto"]}
            ticks={marcasY}
            allowDecimals={!decimales}
            tickFormatter={(v: number) => fmtEntero(v)}
            tick={{ fill: tokens["ink-3"], fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: tokens.axis, strokeWidth: 1 }}
            isAnimationActive={false}
            position={tooltipAnclado ? { y: 0 } : undefined}
            content={({ active, payload }) => {
              const p = active ? (payload?.[0]?.payload as Punto | undefined) : undefined;
              if (!p) return null;
              if (tooltipAnclado) {
                return (
                  <LecturaSemana
                    p={p}
                    unidad={unidad}
                    intervalo={intervalo}
                    trazo={trazo}
                    banda={banda ?? tokens.band}
                    fmtPronostico={fmtPronostico}
                    marcas={marcasSemana?.get(p.fecha) ?? []}
                  />
                );
              }
              return (
                <div className="panel px-3 py-2 text-[12px] num shadow-sm">
                  <p className="font-semibold">Semana {p.semana} · {fmtFechaLarga(p.fecha)}</p>
                  {p.observado != null && <p>Observado: {fmtEntero(p.observado)} {unidad}</p>}
                  {p.pronostico != null && p.banda && (
                    <>
                      <p>Pronóstico: {fmtPronostico(p.pronostico)} {unidad}</p>
                      <p className="text-2">Intervalo {intervalo}: {fmtEntero(p.banda[0])} – {fmtEntero(p.banda[1])}</p>
                    </>
                  )}
                  {p.parcial != null && (
                    <p className="text-2">
                      Semana en curso: {fmtEntero(p.parcial)} atenciones en {p.diasParciales} de 7 días.
                      Parcial, no comparable con semanas completas.
                    </p>
                  )}
                  {p.sinPronostico && (
                    <p className="text-2">Semana sin dato observado ni pronóstico.</p>
                  )}
                  {marcasSemana?.get(p.fecha)?.map((m) => (
                    <p key={m.id} className="mt-0.5 flex items-center gap-1.5 text-2">
                      <svg width="10" height="10" aria-hidden>
                        <line x1="5" y1="0" x2="5" y2="10" stroke={m.color} strokeWidth="2"
                          strokeDasharray={m.categoria === "festividad" ? "3 2" : undefined} />
                      </svg>
                      {m.nombre} ({fechasMarca(m)})
                    </p>
                  ))}
                </div>
              );
            }}
          />
          {marcas?.length ? <CapaMarcas marcas={marcas} fechas={fechas} /> : null}
          <Area dataKey="banda" stroke="none" fill={banda ?? tokens.band} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="observado" stroke={trazo} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
          <Line
            dataKey="pronostico"
            stroke={trazo}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 4, fill: tokens.surface, stroke: trazo, strokeWidth: 2 }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
            connectNulls={false}
          />
          <Line
            dataKey="parcial"
            stroke="none"
            dot={{ r: 4, fill: tokens.surface, stroke: tokens["ink-3"], strokeWidth: 2, strokeDasharray: "2 2" }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
