// Propuesta anual de camas: el calculo de un area y el desglose del hospital.
import type { AreaPsiquiatria, PropuestaCamas } from "../../api";
import { fmtDecimal, fmtEntero } from "../../format";
import { Fraccion, fmtCamas, nombreArea } from "./formato";

export function PropuestaArea({ area, propuesta, dotacionVisible }: {
  area: AreaPsiquiatria;
  propuesta: PropuestaCamas;
  dotacionVisible: number | null;
}) {
  return (
    <div className="mt-4 max-w-[85ch] text-[13px] text-2" aria-live="polite">
      <p className="font-semibold">Propuesta de capacidad para {propuesta.ano_objetivo} · {nombreArea(area.nivel_cuidado)}</p>
      {propuesta.motivo ? <p className="mt-1 text-3">Sin propuesta: {propuesta.motivo}</p> : <>
        <p className="mt-1 num">
          Objetivo: <strong>{fmtEntero(propuesta.camas_objetivo)} camas habilitadas</strong>.
          {propuesta.fuente_base === "disponibles_rem20"
            ? ` Aumento estimado de capacidad: +${fmtEntero(propuesta.aumento_dotacion)} camas respecto de ${fmtDecimal(propuesta.base_capacidad)} disponibles por día (REM-20). No permite distinguir camas nuevas de camas por rehabilitar.`
            : ` Aumento de dotación: +${fmtEntero(propuesta.aumento_dotacion)} camas respecto de ${fmtEntero(dotacionVisible)} declaradas (${area.ano_dotacion}).`}
          {propuesta.habilitar_existentes != null && propuesta.habilitar_existentes > 0
            ? ` Antes de ampliar: evaluar habilitar hasta ${fmtCamas(propuesta.habilitar_existentes)} camas declaradas hoy no disponibles, en promedio.` : ""}
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
  );
}

export function DesglosePropuesta({ areas, parcial }: { areas: AreaPsiquiatria[] | null; parcial: boolean }) {
  return (
    <details className="mt-3 text-[12px] text-3">
      <summary className="cursor-pointer">Desglose de la propuesta de camas de psiquiatría del hospital</summary>
      <p className="mt-2">Se suman los aumentos de cada área de psiquiatría, sin compensarlos con camas libres de otras áreas.
        {parcial ? " El subtotal excluye las áreas sin cálculo respaldado; no se consideran cero." : ""}
        {" "}Seleccione un área en la tabla para ver su capacidad y cálculo.</p>
      <ul className="mt-2 space-y-1">
        {(areas ?? []).map((a) => <li key={a.nivel_cuidado_codigo}>
          {nombreArea(a.nivel_cuidado)}: {a.propuesta_camas?.aumento_dotacion == null
            ? a.propuesta_camas?.motivo ?? "sin datos para calcular"
            : `+${fmtEntero(a.propuesta_camas.aumento_dotacion)} camas`}.
        </li>)}
      </ul>
    </details>
  );
}
