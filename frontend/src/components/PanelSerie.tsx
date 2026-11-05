import type { CamasPsiquiatria, CoberturaNivel, SemanaParcial, SerieConPronostico } from "../api";
import { clasificar, fueraDelIntervalo } from "../cambio";
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
  /** Camas de psiquiatria del territorio seleccionado; null mientras carga o si la capa no existe. */
  camas: CamasPsiquiatria | null;
  /** Puente a la vista por establecimiento del territorio; null si no hay establecimientos. */
  establecimientos: { href: string; texto: string } | null;
}

const VENTANA_RECIENTE = 4;

const promedio = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);

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

export function PanelSerie({
  serie, tokens, nivelIntervalo, cobertura, umbralCambioPct, semanaParcial, camas, establecimientos,
}: Props) {
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
          <p className="text-[13px] text-3">
            Atenciones semanales de urgencia en salud mental
            {establecimientos && (
              <>
                {" · "}
                <a href={establecimientos.href} className="link-button">{establecimientos.texto}</a>
              </>
            )}
          </p>
        </div>
        <LeyendaSerie tokens={tokens} intervalo={intervalo} conParcial={parcialAplicable != null} />
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

          <dl className="cifras-clave mt-4">
            <div>
              <dt className="text-[12px] text-3">Nivel reciente</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight">{fmtEntero(reciente)}</dd>
              <dd className="text-[12px] text-3">promedio de las últimas {VENTANA_RECIENTE} semanas</dd>
            </div>
            <div>
              <dt className="text-[12px] text-3">Pronóstico medio, {rango}</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight">{fmtEntero(medio)}</dd>
              <dd className="text-[12px] text-3 num">{fmtPct(variacion)} frente al nivel reciente</dd>
            </div>
            <div>
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
              <div>
                <dt className="text-[12px] text-3">Confiabilidad del intervalo</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight">
                  {Math.round(coberturaNivel.cobertura_observada * 100)}%
                </dd>
                <dd className="text-[12px] text-3">cubrió fuera de muestra (declarado {intervalo})</dd>
              </div>
            )}
            {camas && (
              <div>
                <dt className="text-[12px] text-3">Camas de psiquiatría ({camas.ano_camas})</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
                  {camas.total_camas_psiquiatria == null ? "sin dato" : fmtEntero(camas.total_camas_psiquiatria)}
                </dd>
                <dd className="text-[12px] text-3">
                  {camas.total_camas_psiquiatria == null
                    ? "ningún hospital del territorio las declara"
                    : `dotación declarada en ${camas.n_hospitales_con_camas === 1 ? "1 hospital" : `${camas.n_hospitales_con_camas} hospitales`}, no ocupación`}
                </dd>
              </div>
            )}
          </dl>

          <div className="mt-5">
            {/* Las camas no van sobre este eje: una dotacion anual junto a atenciones
                semanales sugiere una comparacion de capacidad que no corresponde. */}
            <GraficoSerie serie={serie} tokens={tokens} intervalo={intervalo} semanaParcial={parcialAplicable} />
            <TablaSerie serie={serie} intervalo={intervalo} semanaParcial={parcialAplicable} camas={camas} />
          </div>
        </div>
      )}
    </section>
  );
}
