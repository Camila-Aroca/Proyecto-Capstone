// Tablas del panel de ocupacion: saturacion por area y ocupacion mensual.
import type { AreaPsiquiatria, PuntoOcupacionMensual } from "../../api";
import { fmtMesLargo } from "../../format";
import { fmtCamas, fmtIndice, nombreArea } from "./formato";

export function TablaAreas({ areas, ventana, elegida, elegir }: {
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
export function TablaMeses({ meses }: { meses: PuntoOcupacionMensual[] }) {
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
