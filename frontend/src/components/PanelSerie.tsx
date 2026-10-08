import type { CambioEsperado, CoberturaNivel, SemanaParcial, SerieConPronostico } from "../api";
import { fmtEntero, fmtFechaLarga, fmtPct } from "../format";
import type { Tokens } from "../tokens";
import { BadgeCambio } from "./BadgeCambio";
import { GraficoSerie, LeyendaSerie, TablaSerie } from "./GraficoSerie";

interface Props {
  serie: SerieConPronostico | null;
  tokens: Tokens;
  nivelIntervalo: number | null;
  cobertura: CoberturaNivel[] | null;
  /** Umbral de alza/baja declarado por la API, para no fijarlo aqui tambien. */
  umbralCambioPct: number | null;
  /** Semana en curso (parcial). Es un dato regional: solo se usa en la serie de la RM. */
  semanaParcial: SemanaParcial | null;
}

const VENTANA_RECIENTE = 4;

const promedio = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);

// Mismas dos etiquetas que el backend. `clasificar` mide el tamano del cambio
// contra el umbral declarado por la API; `fueraDelIntervalo` dice si ademas se
// distingue de la fluctuacion semanal.
function clasificar(variacion: number | null, umbralPct: number | null): CambioEsperado {
  if (variacion == null || umbralPct == null) return "sin_pronostico";
  if (variacion >= umbralPct) return "alza";
  if (variacion <= -umbralPct) return "baja";
  return "estable";
}

function fueraDelIntervalo(
  reciente: number | null, inferior: number | null, superior: number | null,
): boolean | null {
  if (reciente == null || inferior == null || superior == null) return null;
  return reciente < inferior || reciente > superior;
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

export function PanelSerie({ serie, tokens, nivelIntervalo, cobertura, umbralCambioPct, semanaParcial }: Props) {
  const intervalo = nivelIntervalo ? `${Math.round(nivelIntervalo * 100)}%` : "";
  const pronostico = serie?.pronostico ?? [];
  const primero = pronostico[0];
  const reciente = promedio((serie?.historico ?? []).slice(-VENTANA_RECIENTE).map((p) => p.atenciones));
  const medio = promedio(pronostico.map((p) => p.pronostico));
  const inferior = promedio(pronostico.map((p) => p.limite_inferior));
  const superior = promedio(pronostico.map((p) => p.limite_superior));
  const variacion = reciente && medio != null ? (medio / reciente - 1) * 100 : null;
  const cambio = clasificar(variacion, umbralCambioPct);
  const fuera = fueraDelIntervalo(reciente, inferior, superior);
  const coberturaNivel = cobertura?.find((c) => c.nivel === serie?.nivel);
  // El dato parcial es de toda la RM: mostrarlo en una comuna seria atribuirle
  // un volumen que no es suyo.
  const parcialAplicable = serie?.nivel === "region" ? semanaParcial : null;
  const rango = pronostico.length
    ? `${pronostico[0].horizonte} a ${pronostico[pronostico.length - 1].horizonte} semanas`
    : "";

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
              <dd className="mt-0.5 text-xl font-semibold tracking-tight">{fmtEntero(reciente)}</dd>
              <dd className="text-[12px] text-3">promedio de las últimas {VENTANA_RECIENTE} semanas</dd>
            </div>
            <div className="sm:px-6 sm:first:pl-0">
              <dt className="text-[12px] text-3">Pronóstico medio, {rango}</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight">{fmtEntero(medio)}</dd>
              <dd className="text-[12px] text-3 num">{fmtPct(variacion)} frente al nivel reciente</dd>
            </div>
            <div className="sm:px-6 sm:first:pl-0">
              <dt className="text-[12px] text-3">Cambio esperado</dt>
              <dd className="mt-1.5">
                <BadgeCambio cambio={cambio} fueraDelIntervalo={fuera} />
              </dd>
              <dd className="mt-1 text-[12px] text-3">
                {cambio === "estable"
                  ? `variación menor a ${umbralCambioPct ?? "—"}%`
                  : fuera
                    ? "se distingue de la fluctuación semanal"
                    : "cabe dentro de la fluctuación semanal"}
              </dd>
            </div>
            {coberturaNivel && (
              <div className="sm:px-6 sm:first:pl-0">
                <dt className="text-[12px] text-3">Confiabilidad del intervalo</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight">
                  {Math.round(coberturaNivel.cobertura_observada * 100)}%
                </dd>
                <dd className="text-[12px] text-3">cubrió fuera de muestra (declarado {intervalo})</dd>
              </div>
            )}
          </dl>

          <div className="mt-5">
            <GraficoSerie serie={serie} tokens={tokens} intervalo={intervalo} semanaParcial={parcialAplicable} />
            <TablaSerie serie={serie} intervalo={intervalo} semanaParcial={parcialAplicable} />
          </div>
        </div>
      )}
    </section>
  );
}
