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
import type { SerieConPronostico } from "../api";
import { fmtEntero, fmtFechaCorta, fmtFechaLarga } from "../format";
import type { Tokens } from "../tokens";

interface Props {
  serie: SerieConPronostico;
  tokens: Tokens;
  intervalo: string;
}

interface Punto {
  fecha: string;
  semana: number;
  observado: number | null;
  pronostico: number | null;
  banda: [number, number] | null;
  sinPronostico: boolean;
}

const DIA_MS = 86_400_000;

// Une historia y pronostico en un solo eje temporal. Las semanas entre la ultima
// observada y el primer horizonte (h < 4) se incluyen vacias: el modelo no las
// pronostica, y ocultarlas acortaria visualmente el horizonte real.
function construirPuntos(serie: SerieConPronostico): Punto[] {
  const puntos: Punto[] = serie.historico.map((h) => ({
    fecha: h.fecha_inicio ?? "",
    semana: h.semana,
    observado: h.atenciones,
    pronostico: null,
    banda: null,
    sinPronostico: false,
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
    });
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
    </ul>
  );
}

export function GraficoSerie({ serie, tokens, intervalo }: Props) {
  const puntos = construirPuntos(serie);
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
                  {p.sinPronostico && (
                    <p className="text-2">Sin pronóstico: el modelo cubre de 4 a 8 semanas.</p>
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
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
