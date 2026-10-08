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
import type { SemanaParcial, SerieConPronostico } from "../api";
import { fmtEntero, fmtFechaCorta, fmtFechaLarga } from "../format";
import type { Tokens } from "../tokens";

interface Props {
  serie: SerieConPronostico;
  tokens: Tokens;
  intervalo: string;
  /** Semana en curso, parcial. Solo aplica a la serie regional: el dato es de toda la RM. */
  semanaParcial?: SemanaParcial | null;
}

interface Punto {
  fecha: string;
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
    const existente = puntos.find((p) => p.semana === parcial.semana);
    if (existente) {
      existente.parcial = parcial.atenciones;
      existente.diasParciales = parcial.dias_observados;
    } else {
      puntos.push({
        fecha: "",
        semana: parcial.semana,
        observado: null,
        pronostico: null,
        banda: null,
        sinPronostico: false,
        parcial: parcial.atenciones,
        diasParciales: parcial.dias_observados,
      });
    }
  }
  return puntos;
}

export function LeyendaSerie({ tokens, intervalo }: { tokens: Tokens; intervalo: string }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-2" aria-label="Leyenda del gráfico">
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden><line x1="0" y1="4" x2="20" y2="4" stroke={tokens["series-1"]} strokeWidth="2" /></svg>
        Observado
      </li>
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="8" aria-hidden><line x1="0" y1="4" x2="20" y2="4" stroke={tokens["series-1"]} strokeWidth="2" strokeDasharray="4 3" /></svg>
        Pronóstico
      </li>
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="10" aria-hidden><rect width="20" height="10" rx="2" fill={tokens.band} /></svg>
        Intervalo {intervalo}
      </li>
      <li className="inline-flex items-center gap-1.5">
        <svg width="20" height="10" aria-hidden>
          <circle cx="10" cy="5" r="4" fill={tokens.surface} stroke={tokens["ink-3"]} strokeWidth="2" strokeDasharray="2 2" />
        </svg>
        Semana en curso (parcial)
      </li>
    </ul>
  );
}

// Equivalente en tabla del grafico: ningun valor queda accesible solo por hover
// ni solo por color. Va plegada para no competir con el grafico, pero existe
// siempre y es navegable por teclado.
export function TablaSerie({ serie, intervalo, semanaParcial }: {
  serie: SerieConPronostico;
  intervalo: string;
  semanaParcial?: SemanaParcial | null;
}) {
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
            Atenciones semanales observadas y pronosticadas de {serie.nombre}
          </caption>
          <thead>
            <tr className="text-left text-[12px] text-3">
              <th scope="col" className="px-2.5 py-1.5 font-medium">Semana</th>
              <th scope="col" className="px-2.5 py-1.5 font-medium">Inicio</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Atenciones</th>
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
                <td className="px-2.5 py-1.5 text-right">{fmtEntero(p.pronostico)}</td>
                <td className="px-2.5 py-1.5 text-right">
                  {fmtEntero(p.limite_inferior)} – {fmtEntero(p.limite_superior)}
                </td>
                <td className="px-2.5 py-1.5 text-2">Pronóstico (h+{p.horizonte})</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function GraficoSerie({ serie, tokens, intervalo, semanaParcial }: Props) {
  const puntos = construirPuntos(serie, semanaParcial);
  return (
    <div className="h-72" role="img" aria-label={`Atenciones semanales observadas y pronosticadas de ${serie.nombre}`}>
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
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => fmtEntero(v)}
            tick={{ fill: tokens["ink-3"], fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: tokens.axis, strokeWidth: 1 }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              const p = active ? (payload?.[0]?.payload as Punto | undefined) : undefined;
              if (!p) return null;
              return (
                <div className="panel px-3 py-2 text-[12px] num shadow-sm">
                  <p className="font-semibold">Semana {p.semana} · {fmtFechaLarga(p.fecha)}</p>
                  {p.observado != null && <p>Observado: {fmtEntero(p.observado)} atenciones</p>}
                  {p.pronostico != null && p.banda && (
                    <>
                      <p>Pronóstico: {fmtEntero(p.pronostico)} atenciones</p>
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
                </div>
              );
            }}
          />
          <Area dataKey="banda" stroke="none" fill={tokens.band} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="observado" stroke={tokens["series-1"]} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
          <Line
            dataKey="pronostico"
            stroke={tokens["series-1"]}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 4, fill: tokens.surface, stroke: tokens["series-1"], strokeWidth: 2 }}
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
