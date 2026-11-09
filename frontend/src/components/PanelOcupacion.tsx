// Ocupacion mensual de las camas de psiquiatria de un hospital (REM-20). Va como
// grafico companero del de hospitalizaciones y no en su mismo eje: el ID42 es un
// flujo semanal (hospitalizaciones indicadas en la urgencia) y esto es un stock
// mensual (pacientes en cama por dia, de cualquier origen). Mezclarlos en una
// escala aplastaria la serie de hospitalizaciones y sugeriria una comparacion
// uno a uno que no existe.
import { useState } from "react";
import type { AreaPsiquiatria, PuntoOcupacionMensual } from "../api";
import { fmtDecimal, fmtEntero, fmtMesLargo } from "../format";
import { resumirPropuestas } from "../propuestaCamas";
import type { Tokens } from "../tokens";
import { AREA_LARGA_ESTADIA, AyudaCierreHorwitz, HORWITZ } from "./ocupacion/AyudaCierreHorwitz";
import { fmtCamas, fmtIndice, nombreArea, UMBRAL_HOLGURA } from "./ocupacion/formato";
import { GraficoOcupacion, LeyendaOcupacion } from "./ocupacion/GraficoOcupacion";
import { DesglosePropuesta, PropuestaArea } from "./ocupacion/PropuestaCamas";
import { TablaAreas, TablaMeses } from "./ocupacion/TablasOcupacion";

interface Props {
  meses: PuntoOcupacionMensual[];
  areas: AreaPsiquiatria[] | null;
  /** Dotacion declarada de psiquiatria; null si el hospital no la declara. */
  dotacion: number | null;
  tokens: Tokens;
}

export function PanelOcupacion({ establecimientoCodigo, meses, areas, dotacion, tokens }: Props & { establecimientoCodigo: number }) {
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
            <span className="group relative inline-flex items-center">
              <button type="button" aria-pressed onClick={() => setElegida(null)}>
                {nombreArea(area.nivel_cuidado)} ✕<span className="sr-only">, volver al total del hospital</span>
              </button>
              {establecimientoCodigo === HORWITZ && area.nivel_cuidado_codigo === AREA_LARGA_ESTADIA && (
                <AyudaCierreHorwitz />
              )}
            </span>
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
          <dt className="text-[12px] text-3">Camas de psiquiatría{area ? " del área" : " del hospital"}</dt>
          <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
            {dotacionVisible == null ? fmtDecimal(capacidadVisible) : fmtEntero(capacidadVisible)}
          </dd>
          <dd className="text-[12px] text-3">
            {dotacionVisible == null ? `Disponibles por día, REM-20 (${fmtMesLargo(ultimo.fecha_inicio)})`
              : `Dotación declarada${anoDotacionVisible != null ? ` (${anoDotacionVisible})` : ""}`}
          </dd>
        </div>
        <div>
          <dt className="text-[12px] text-3">Aumento de dotación propuesto{anoPropuesta ? `, ${anoPropuesta}` : ""}</dt>
          {/* Sin cifra: la cifra grande queda atenuada ("—") y el estado va en el distintivo punteado
              de "sin dato" de la app, no como una frase en el tamaño de una cifra. */}
          <dd className={`mt-0.5 text-xl font-semibold tracking-tight num${aumentoVisible == null ? " text-3" : ""}`}>
            {aumentoVisible == null ? "—" : `+${fmtEntero(aumentoVisible)} camas`}
          </dd>
          {aumentoVisible == null && (
            <dd className="mt-1">
              <span className="badge badge-sin_pronostico">
                <span className="badge-icon" aria-hidden>∅</span>
                Sin cálculo respaldado
              </span>
            </dd>
          )}
          <dd className={`text-[12px] text-3${aumentoVisible == null ? " mt-1" : ""}`}>
            {!area ? `${resumen.areasConPropuesta} de ${resumen.areasTotales} áreas de psiquiatría${resumen.parcial ? "; subtotal parcial" : "; suma por área"}` : propuesta?.motivo ? propuesta.motivo
              : propuesta?.aumento_dotacion == null ? "actualice los datos de capacidad"
              : propuesta.fuente_base === "disponibles_rem20" ? "respecto de disponibles REM-20; estimación"
              : "respecto de la dotación declarada"}
          </dd>
        </div>
      </dl>

      {area && propuesta && (
        <PropuestaArea area={area} propuesta={propuesta} dotacionVisible={dotacionVisible} />
      )}
      {!area && <DesglosePropuesta areas={areas} parcial={resumen.parcial} />}

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
            stroke={tokens["propuesta-camas"]} strokeWidth="1.5" strokeOpacity="0.5" strokeDasharray="2 5" strokeLinecap="round" /></svg>
          Propuesta {anoPropuesta}: {Number.isInteger(lineaPropuesta) ? fmtEntero(lineaPropuesta) : fmtDecimal(lineaPropuesta)} camas
          {dotacionVisible == null ? " de capacidad estimada" : " de dotación total"} (aumento +{fmtEntero(aumentoVisible)}).
          {!area && resumen.parcial ? " Subtotal de áreas con cálculo respaldado." : ""}
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
