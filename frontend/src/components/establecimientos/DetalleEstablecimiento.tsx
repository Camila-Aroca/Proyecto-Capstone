// Panel del establecimiento elegido: ruta de vuelta al territorio, frase del
// pronostico, cifras clave, serie y, para hospitalizaciones, la ocupacion de camas.
import { useLayoutEffect, useRef } from "react";
import type {
  EstablecimientoDetalle,
  EstablecimientoResumen,
  MetaObjetivoEstablecimiento,
  ObjetivoEstablecimiento,
} from "../../api";
import { fmtEntero, fmtFechaLarga, fmtPct, SIN_DATO } from "../../format";
import { enlace, RUTA_TABLERO } from "../../ruta";
import type { Tokens } from "../../tokens";
import { BadgeCambio } from "../BadgeCambio";
import { Caracterizacion } from "../Caracterizacion";
import { GraficoSerie, LeyendaSerie, TablaSerie } from "../GraficoSerie";
import { PanelOcupacion } from "../PanelOcupacion";
import { aSerie, cambioDe, fmtCifra, OBJETIVOS } from "./comun";

interface Props {
  seleccion: number | null;
  resumen: EstablecimientoResumen | undefined;
  detalle: EstablecimientoDetalle | null;
  objetivo: ObjetivoEstablecimiento;
  metaObjetivo: MetaObjetivoEstablecimiento | null;
  umbral: number | null;
  /** Si la vista eligio el establecimiento (y no la persona): se dice por que. */
  automatica: boolean;
  /** Comuna filtrada; cambia el texto de la eleccion automatica. */
  comuna: string | null;
  tokens: Tokens;
}

function Esqueleto({ alturaMinima }: { alturaMinima: number }) {
  return (
    <div className="space-y-4 px-5 pb-5" style={{ minHeight: alturaMinima }} aria-busy="true" aria-label="Cargando establecimiento">
      <div className="skeleton h-5 w-2/3" />
      <div className="flex gap-8">
        {[0, 1, 2].map((i) => <div key={i} className="skeleton h-12 w-36" />)}
      </div>
      <div className="skeleton h-64 w-full" />
    </div>
  );
}

export function DetalleEstablecimiento({
  seleccion, resumen, detalle, objetivo, metaObjetivo, umbral, automatica, comuna, tokens,
}: Props) {
  const intervalo = metaObjetivo ? `${Math.round(metaObjetivo.nivel_intervalo * 100)}%` : "";
  const horizontes = metaObjetivo?.horizontes ?? [];
  const rango = horizontes.length ? `${horizontes[0]} a ${horizontes[horizontes.length - 1]} semanas` : "";
  const resumenObjetivo = resumen?.objetivos[objetivo];
  const cambioSeleccion = resumen ? cambioDe(resumen, objetivo, umbral) : null;
  const serie = detalle && detalle.establecimiento_codigo === seleccion ? aSerie(detalle, objetivo) : null;
  const motivo = detalle?.series.find((s) => s.objetivo === objetivo)?.motivo_sin_pronostico
    ?? resumenObjetivo?.motivo_sin_pronostico;
  const primero = serie?.pronostico?.[0];
  const { unidad, subtitulo } = OBJETIVOS[objetivo];

  // Al cambiar de establecimiento el detalle se reemplaza por un esqueleto; si fuera
  // mas bajo, la pagina se acortaria y el navegador moveria el scroll al final.
  const cuerpoDetalle = useRef<HTMLDivElement>(null);
  const alturaDetalle = useRef(0);
  useLayoutEffect(() => {
    if (serie && cuerpoDetalle.current) alturaDetalle.current = cuerpoDetalle.current.offsetHeight;
  });

  return (
    <section className="panel" aria-labelledby="estab-titulo">
      <div className="panel-header">
        <div className="min-w-0">
          {/* Camino de vuelta al territorio: el establecimiento es el nivel mas fino del tablero. */}
          <nav aria-label="Ubicación" className="mb-1 text-[12px] text-3">
            <ol className="flex flex-wrap items-center gap-x-1.5">
              <li><a href={RUTA_TABLERO} className="hover:underline">Región Metropolitana</a></li>
              {resumen && (
                <>
                  <li aria-hidden>›</li>
                  <li>
                    <a href={enlace(RUTA_TABLERO, { territorio: resumen.comuna_codigo })} className="hover:underline">
                      {resumen.comuna}
                    </a>
                  </li>
                </>
              )}
            </ol>
          </nav>
          <h2 id="estab-titulo" className="panel-title">{resumen?.nombre ?? "Cargando…"}</h2>
          <p className="text-[13px] text-3">
            {resumen ? `${resumen.tipo} · ` : ""}{subtitulo}
            {automatica && resumen && (
              <span> · se muestra el de mayor pronóstico{comuna ? " de la comuna" : ""}; elija otro en la tabla</span>
            )}
          </p>
        </div>
        <LeyendaSerie tokens={tokens} intervalo={intervalo} conParcial={false} />
      </div>

      {!serie ? (
        <Esqueleto alturaMinima={alturaDetalle.current} />
      ) : (
        <div className="px-5 pb-4" ref={cuerpoDetalle}>
          <div aria-live="polite">
            {primero ? (
              <p className="max-w-[75ch] text-[15px] leading-relaxed">
                Para la semana del <strong>{fmtFechaLarga(primero.fecha_inicio)}</strong> se esperan{" "}
                <strong className="num">{fmtCifra(primero.pronostico)} {unidad}</strong>, entre{" "}
                <span className="num">{fmtCifra(primero.limite_inferior)}</span> y{" "}
                <span className="num">{fmtCifra(primero.limite_superior)}</span> con un intervalo de {intervalo}.
              </p>
            ) : (
              <p className="max-w-[75ch] text-[14px] text-2">
                Sin pronóstico para este establecimiento. {motivo ?? ""} Se muestra solo lo observado.
              </p>
            )}
          </div>

          <dl className="cifras-clave mt-4">
            <div>
              <dt className="text-[12px] text-3">Nivel reciente</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtCifra(resumenObjetivo?.promedio_ultimas_semanas)}</dd>
              <dd className="text-[12px] text-3">promedio de las últimas 4 semanas</dd>
            </div>
            {resumenObjetivo?.incluido && (
              <>
                <div>
                  <dt className="text-[12px] text-3">Pronóstico medio, {rango}</dt>
                  <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtCifra(resumenObjetivo.pronostico_promedio)}</dd>
                  <dd className="text-[12px] text-3 num">{fmtPct(resumenObjetivo.variacion_pct)} frente al nivel reciente</dd>
                </div>
                {cambioSeleccion && (
                  <div>
                    <dt className="text-[12px] text-3">Cambio esperado</dt>
                    <dd className="mt-1.5"><BadgeCambio cambio={cambioSeleccion.cambio} fueraDelIntervalo={cambioSeleccion.fuera} /></dd>
                    <dd className="mt-1 text-[12px] text-3">
                      {cambioSeleccion.cambio === "estable"
                        ? `variación menor a ${umbral ?? "—"}%`
                        : cambioSeleccion.fuera
                          ? "se distingue de la fluctuación semanal"
                          : "cabe dentro de la fluctuación semanal"}
                    </dd>
                  </div>
                )}
              </>
            )}
            {metaObjetivo?.cobertura_holdout != null && (
              <div>
                <dt className="text-[12px] text-3">Confiabilidad del intervalo</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
                  {Math.round(metaObjetivo.cobertura_holdout * 100)}%
                </dd>
                <dd className="text-[12px] text-3">cubrió fuera de muestra (declarado {intervalo})</dd>
              </div>
            )}
            {resumen?.tipo === "Hospital" && (
              <div>
                <dt className="text-[12px] text-3">Camas de psiquiatría</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
                  {resumen.camas_psiquiatria == null ? SIN_DATO : fmtEntero(resumen.camas_psiquiatria)}
                </dd>
                <dd className="text-[12px] text-3">dotación declarada, no ocupación</dd>
              </div>
            )}
          </dl>

          <div className="mt-5">
            <GraficoSerie serie={serie} tokens={tokens} intervalo={intervalo} unidad={unidad} />
            <TablaSerie serie={serie} intervalo={intervalo} unidad={unidad} />
            <Caracterizacion serie={serie} fuente={objetivo === "hospitalizaciones_sm" ? "hospitalizaciones" : "urgencias"} />
          </div>

          {objetivo === "hospitalizaciones_sm" && detalle?.ocupacion_psiquiatria?.length ? (
            <PanelOcupacion
              key={detalle.establecimiento_codigo}
              establecimientoCodigo={detalle.establecimiento_codigo}
              meses={detalle.ocupacion_psiquiatria}
              areas={detalle.areas_psiquiatria ?? null}
              dotacion={resumen?.camas_psiquiatria ?? null}
              tokens={tokens}
            />
          ) : objetivo === "hospitalizaciones_sm" && resumen?.tipo === "Hospital" && detalle ? (
            <p className="mt-5 border-t border-[var(--border)] pt-4 text-[13px] text-3">
              Este hospital no registra áreas de psiquiatría en las estadísticas hospitalarias (REM-20): no hay
              ocupación de camas de psiquiatría que mostrar (ausencia de dato, no cero).
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
