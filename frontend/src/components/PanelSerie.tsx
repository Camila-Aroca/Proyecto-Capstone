import type { CambioEsperado, CoberturaNivel, SerieConPronostico } from "../api";
import { fmtEntero, fmtFechaLarga, fmtPct } from "../format";
import type { Tokens } from "../tokens";
import { BadgeCambio } from "./BadgeCambio";
import { GraficoSerie, LeyendaSerie } from "./GraficoSerie";

interface Props {
  serie: SerieConPronostico | null;
  tokens: Tokens;
  nivelIntervalo: number | null;
  cobertura: CoberturaNivel[] | null;
}

const VENTANA_RECIENTE = 4;

const promedio = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);

// Misma regla que el backend (`clasificar_cambio`): solo hay alza o baja si el
// nivel reciente queda fuera del intervalo medio del pronostico.
function clasificar(reciente: number | null, inferior: number | null, superior: number | null): CambioEsperado {
  if (reciente == null || inferior == null || superior == null) return "sin_pronostico";
  if (reciente < inferior) return "alza";
  if (reciente > superior) return "baja";
  return "estable";
}

function Esqueleto() {
  return (
    <div className="space-y-4 px-5 pb-5" aria-busy="true" aria-label="Cargando serie">
      <div className="skeleton h-5 w-2/3" />
      <div className="flex gap-8">
        {[0, 1, 2].map((i) => <div key={i} className="skeleton h-12 w-36" />)}
      </div>
      <div className="skeleton h-64 w-full" />
    </div>
  );
}

export function PanelSerie({ serie, tokens, nivelIntervalo, cobertura }: Props) {
  const intervalo = nivelIntervalo ? `${Math.round(nivelIntervalo * 100)}%` : "";
  const pronostico = serie?.pronostico ?? [];
  const primero = pronostico[0];
  const reciente = promedio((serie?.historico ?? []).slice(-VENTANA_RECIENTE).map((p) => p.atenciones));
  const medio = promedio(pronostico.map((p) => p.pronostico));
  const inferior = promedio(pronostico.map((p) => p.limite_inferior));
  const superior = promedio(pronostico.map((p) => p.limite_superior));
  const variacion = reciente && medio != null ? (medio / reciente - 1) * 100 : null;
  const cambio = clasificar(reciente, inferior, superior);
  const coberturaNivel = cobertura?.find((c) => c.nivel === serie?.nivel);

  return (
    <section className="panel" aria-labelledby="serie-titulo">
      <div className="panel-header">
        <div>
          <h2 id="serie-titulo" className="panel-title">{serie?.nombre ?? "Cargando…"}</h2>
          <p className="text-[13px] text-3">Atenciones semanales de urgencia en salud mental</p>
        </div>
        <LeyendaSerie tokens={tokens} intervalo={intervalo} />
      </div>

      {!serie ? (
        <Esqueleto />
      ) : (
        <div className="px-5 pb-4">
          {primero ? (
            <p className="max-w-[75ch] text-[15px] leading-relaxed">
              Para la semana del <strong>{fmtFechaLarga(primero.fecha_inicio)}</strong> se esperan{" "}
              <strong className="num">{fmtEntero(primero.pronostico)} atenciones</strong>, entre{" "}
              <span className="num">{fmtEntero(primero.limite_inferior)}</span> y{" "}
              <span className="num">{fmtEntero(primero.limite_superior)}</span> con un intervalo de {intervalo}.
            </p>
          ) : (
            <p className="text-[14px] text-2">El pronóstico se está calculando; aparecerá aquí en unos segundos.</p>
          )}

          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 sm:flex sm:flex-wrap sm:gap-0 sm:divide-x sm:divide-(--border)">
            <div className="sm:px-6 sm:first:pl-0">
              <dt className="text-[12px] text-3">Nivel reciente</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtEntero(reciente)}</dd>
              <dd className="text-[12px] text-3">promedio de las últimas {VENTANA_RECIENTE} semanas</dd>
            </div>
            <div className="sm:px-6 sm:first:pl-0">
              <dt className="text-[12px] text-3">Pronóstico medio, 4 a 8 semanas</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtEntero(medio)}</dd>
              <dd className="text-[12px] text-3 num">{fmtPct(variacion)} frente al nivel reciente</dd>
            </div>
            <div className="sm:px-6 sm:first:pl-0">
              <dt className="text-[12px] text-3">Cambio esperado</dt>
              <dd className="mt-1.5">
                <BadgeCambio
                  cambio={cambio}
                  titulo="Alza o baja solo si el nivel reciente queda fuera del intervalo del pronóstico."
                />
              </dd>
              <dd className="mt-1 text-[12px] text-3">
                {cambio === "estable" ? "la variación cabe en el ruido semanal" : "fuera del intervalo del pronóstico"}
              </dd>
            </div>
            {coberturaNivel && (
              <div className="sm:px-6 sm:first:pl-0">
                <dt className="text-[12px] text-3">Confiabilidad del intervalo</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
                  {Math.round(coberturaNivel.cobertura_observada * 100)}%
                </dd>
                <dd className="text-[12px] text-3">cubrió fuera de muestra (declarado {intervalo})</dd>
              </div>
            )}
          </dl>

          <div className="mt-5">
            <GraficoSerie serie={serie} tokens={tokens} intervalo={intervalo} />
          </div>
        </div>
      )}
    </section>
  );
}
