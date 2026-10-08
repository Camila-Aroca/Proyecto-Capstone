import { useMemo, useState } from "react";
import type { CambioEsperado, ResumenComuna } from "../api";
import { fmtDecimal, fmtEntero, fmtPct } from "../format";
import { BadgeCambio } from "./BadgeCambio";

const CAMBIO_AYUDA =
  "Alza o baja según el tamaño del cambio esperado. El signo ≈ marca los que caben dentro de la fluctuación semanal.";

interface Props {
  filas: ResumenComuna[];
  seleccion: string;
  onSeleccionar: (seriesId: string) => void;
}

type Clave = "nombre" | "promedio_ultimas_semanas" | "pronostico_promedio" | "cambio_esperado"
  | "tasa_pronostico_por_10000" | "indicador_vulnerabilidad" | "oferta_urgencia_actual";

const COLUMNAS: { clave: Clave; titulo: string; ayuda?: string; texto?: boolean }[] = [
  { clave: "nombre", titulo: "Comuna", texto: true },
  { clave: "promedio_ultimas_semanas", titulo: "Reciente", ayuda: "Promedio semanal de las últimas 4 semanas observadas" },
  { clave: "pronostico_promedio", titulo: "Pronóstico", ayuda: "Promedio semanal pronosticado, 4 a 8 semanas" },
  { clave: "cambio_esperado", titulo: "Cambio", ayuda: CAMBIO_AYUDA, texto: true },
  { clave: "tasa_pronostico_por_10000", titulo: "Tasa", ayuda: "Atenciones pronosticadas por 10.000 habitantes a la semana; no es prevalencia" },
  { clave: "indicador_vulnerabilidad", titulo: "Pobreza", ayuda: "Tasa de pobreza por ingresos, Casen 2022" },
  { clave: "oferta_urgencia_actual", titulo: "Oferta", ayuda: "Establecimientos de urgencia vigentes en la comuna" },
];

// Orden para la columna de cambio: primero lo que exige atencion.
const ORDEN_CAMBIO: Record<CambioEsperado, number> = { alza: 0, baja: 1, estable: 2, sin_pronostico: 3 };

function valor(fila: ResumenComuna, clave: Clave): number | string | null {
  if (clave === "cambio_esperado") return ORDEN_CAMBIO[fila.cambio_esperado];
  return fila[clave];
}

// Tabla ordenable: es tambien la vista accesible de lo que muestra el mapa.
export function TablaComunal({ filas, seleccion, onSeleccionar }: Props) {
  const [orden, setOrden] = useState<{ clave: Clave; asc: boolean }>({ clave: "cambio_esperado", asc: true });

  const ordenadas = useMemo(() => {
    const copia = [...filas];
    copia.sort((a, b) => {
      const va = valor(a, orden.clave);
      const vb = valor(b, orden.clave);
      // Las comunas sin dato van siempre al final, sin importar el sentido.
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = typeof va === "string" ? va.localeCompare(String(vb), "es") : Number(va) - Number(vb);
      if (cmp === 0 && orden.clave === "cambio_esperado") {
        // Desempate por magnitud del pronostico: dentro de "alza", la mayor primero.
        return (b.pronostico_promedio ?? -1) - (a.pronostico_promedio ?? -1);
      }
      return orden.asc ? cmp : -cmp;
    });
    return copia;
  }, [filas, orden]);

  const alternar = (clave: Clave) =>
    setOrden((o) => ({
      clave,
      asc: o.clave === clave ? !o.asc : clave === "nombre" || clave === "cambio_esperado",
    }));

  return (
    <section className="panel flex flex-col" aria-labelledby="tabla-titulo">
      <div className="panel-header">
        <h2 id="tabla-titulo" className="panel-title">Resumen por comuna</h2>
        <p className="text-[12px] text-3">{filas.length ? `${filas.length} comunas · tasa por 10.000 hab. a la semana · clic en el nombre para ver su serie` : ""}</p>
      </div>
      <div className="mx-5 mb-5 max-h-122 overflow-auto rounded-lg border lg:max-h-none lg:min-h-0 lg:flex-[1_1_0px]" style={{ borderColor: "var(--border)" }}>
        {!filas.length ? (
          <div className="space-y-2 p-3" aria-busy="true" aria-label="Cargando tabla">
            {Array.from({ length: 10 }, (_, i) => <div key={i} className="skeleton h-6 w-full" />)}
          </div>
        ) : (
          <table className="w-full border-collapse text-[13px] num">
            <thead className="sticky top-0 z-1" style={{ background: "var(--surface-2)" }}>
              <tr>
                {COLUMNAS.map((c) => (
                  <th
                    key={c.clave}
                    scope="col"
                    title={c.ayuda}
                    className={`whitespace-nowrap px-2.5 py-2 text-[12px] font-semibold text-2 ${c.texto ? "text-left" : "text-right"}`}
                    aria-sort={orden.clave === c.clave ? (orden.asc ? "ascending" : "descending") : "none"}
                  >
                    <button type="button" onClick={() => alternar(c.clave)} className="inline-flex items-center gap-1 hover:text-(--ink)">
                      {c.titulo}
                      <span aria-hidden className="text-[10px]" style={{ opacity: orden.clave === c.clave ? 1 : 0.35 }}>
                        {orden.clave === c.clave && !orden.asc ? "▼" : "▲"}
                      </span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ordenadas.map((fila) => {
                const activa = fila.series_id === seleccion;
                return (
                  <tr
                    key={fila.series_id}
                    className="transition-colors duration-150 hover:bg-(--accent-weak)"
                    style={{
                      borderTop: "1px solid var(--grid)",
                      background: activa ? "var(--accent-weak)" : undefined,
                      boxShadow: activa ? "inset 0 0 0 1px var(--accent)" : undefined,
                    }}
                  >
                    <td className="px-2.5 py-1.5 text-left">
                      {fila.tiene_pronostico ? (
                        <button
                          type="button"
                          onClick={() => onSeleccionar(fila.series_id)}
                          aria-pressed={activa}
                          className="text-left font-medium hover:underline"
                        >
                          {fila.nombre}
                        </button>
                      ) : (
                        <span className="text-3" title={fila.motivo_sin_pronostico ?? undefined}>{fila.nombre}</span>
                      )}
                    </td>
                    <td className="px-2.5 py-1.5 text-right">{fmtEntero(fila.promedio_ultimas_semanas)}</td>
                    <td className="px-2.5 py-1.5 text-right">{fila.tiene_pronostico ? fmtEntero(fila.pronostico_promedio) : <span className="text-3">—</span>}</td>
                    <td className="px-2.5 py-1.5 text-left">
                      <span className="inline-flex items-center gap-2">
                        <BadgeCambio
                          cambio={fila.cambio_esperado}
                          fueraDelIntervalo={fila.fuera_del_intervalo}
                          compacto
                          titulo={fila.motivo_sin_pronostico ?? undefined}
                        />
                        {fila.tiene_pronostico && <span className="text-[12px] text-3">{fmtPct(fila.variacion_pct)}</span>}
                      </span>
                    </td>
                    <td className="px-2.5 py-1.5 text-right">{fila.tiene_pronostico ? fmtDecimal(fila.tasa_pronostico_por_10000) : <span className="text-3">—</span>}</td>
                    <td className="px-2.5 py-1.5 text-right">
                      {fila.indicador_vulnerabilidad == null ? <span className="text-3">—</span> : `${fmtDecimal(fila.indicador_vulnerabilidad * 100)}%`}
                    </td>
                    <td className="px-2.5 py-1.5 text-right">{fmtEntero(fila.oferta_urgencia_actual)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
