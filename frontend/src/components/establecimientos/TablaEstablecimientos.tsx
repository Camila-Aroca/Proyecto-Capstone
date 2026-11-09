// Tabla de establecimientos con busqueda, filtro por tipo y orden por columna.
// Es tambien la via para elegir el establecimiento del panel y para filtrar por comuna.
import { useEffect, useMemo, useState } from "react";
import type { EstablecimientoResumen, ObjetivoEstablecimiento } from "../../api";
import { fmtDecimal, fmtEntero, fmtMesCorto, fmtPct } from "../../format";
import { enlace, RUTA_TABLERO } from "../../ruta";
import { BadgeCambio } from "../BadgeCambio";
import { Tip } from "../Tip";
import { AyudaColapso, ID_AYUDA_COLAPSO } from "./AyudaColapso";
import { cambioDe, fmtCifra, NIVELES, OBJETIVOS } from "./comun";

const TODOS = "todos";

type Clave = "nombre" | "tipo" | "comuna" | "reciente" | "pronostico" | "cambio" | "camas" | "colapso";

const COLUMNAS: { clave: Clave; titulo: string; ayuda?: string; texto?: boolean }[] = [
  { clave: "nombre", titulo: "Establecimiento", texto: true },
  { clave: "tipo", titulo: "Tipo", texto: true },
  { clave: "comuna", titulo: "Comuna", texto: true, ayuda: "Clic en la comuna para ver solo sus establecimientos" },
  { clave: "reciente", titulo: "Reciente", ayuda: "Promedio semanal de las últimas 4 semanas observadas" },
  { clave: "pronostico", titulo: "Pronóstico", ayuda: "Promedio semanal pronosticado, 1 a 8 semanas" },
  { clave: "cambio", titulo: "Cambio", texto: true, ayuda: "Mismo criterio que la vista por comuna. El signo ≈ marca los que caben dentro de la fluctuación semanal." },
  { clave: "camas", titulo: "Camas psiq.", ayuda: "Dotación declarada de camas de psiquiatría (SNSS); — si el establecimiento no declara" },
  { clave: "colapso", titulo: "Nivel de colapso", texto: true },
];

function valor(fila: EstablecimientoResumen, objetivo: ObjetivoEstablecimiento, clave: Clave): number | string | null {
  const o = fila.objetivos[objetivo];
  switch (clave) {
    case "nombre": return fila.nombre;
    case "tipo": return fila.tipo;
    case "comuna": return fila.comuna;
    case "reciente": return o?.promedio_ultimas_semanas ?? null;
    case "pronostico": return o?.incluido ? o.pronostico_promedio : null;
    case "cambio": return o?.incluido ? o.variacion_pct : null;
    case "camas": return fila.camas_psiquiatria;
    // Primero el nivel y, dentro del nivel, la ocupacion: ordena de mas a menos saturado.
    case "colapso": return fila.colapso_psiquiatria
      ? NIVELES[fila.colapso_psiquiatria.nivel].orden * 1000 + fila.colapso_psiquiatria.indice_ocupacional
      : null;
  }
}

interface Props {
  /** Establecimientos del objetivo y la comuna activos, antes de busqueda y tipo. */
  establecimientos: EstablecimientoResumen[];
  /** False mientras la lista no llega de la API. */
  cargada: boolean;
  objetivo: ObjetivoEstablecimiento;
  umbral: number | null;
  seleccion: number | null;
  onElegir: (codigo: number) => void;
  comuna: string | null;
  nombreComuna: string | null;
  onFiltrarComuna: (codigo: string | null) => void;
}

export function TablaEstablecimientos({
  establecimientos, cargada, objetivo, umbral, seleccion, onElegir, comuna, nombreComuna, onFiltrarComuna,
}: Props) {
  const [tipo, setTipo] = useState<string>(TODOS);
  const [busqueda, setBusqueda] = useState("");
  const [orden, setOrden] = useState<{ clave: Clave; asc: boolean }>({ clave: "camas", asc: false });

  // Al cambiar de comuna se parte de cero: la busqueda y el tipo anteriores ya no aplican.
  useEffect(() => {
    setBusqueda("");
    setTipo(TODOS);
  }, [comuna]);

  const tipos = useMemo(
    () => [...new Set(establecimientos.map((f) => f.tipo))].sort((a, b) => a.localeCompare(b, "es")),
    [establecimientos],
  );
  const conPronostico = establecimientos.filter((f) => f.objetivos[objetivo]?.incluido).length;

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLocaleLowerCase("es");
    const filtradas = establecimientos.filter((f) =>
      (tipo === TODOS || f.tipo === tipo)
      && (!texto || f.nombre.toLocaleLowerCase("es").includes(texto) || f.comuna.toLocaleLowerCase("es").includes(texto)));
    return filtradas.sort((a, b) => {
      const va = valor(a, objetivo, orden.clave);
      const vb = valor(b, objetivo, orden.clave);
      // Sin dato va siempre al final, sin importar el sentido del orden.
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = typeof va === "string" ? va.localeCompare(String(vb), "es") : Number(va) - Number(vb);
      return orden.asc ? cmp : -cmp;
    });
  }, [establecimientos, tipo, busqueda, orden, objetivo]);

  const alternar = (clave: Clave) =>
    setOrden((o) => ({ clave, asc: o.clave === clave ? !o.asc : ["nombre", "tipo", "comuna"].includes(clave) }));

  return (
    <section className="panel flex flex-col" aria-labelledby="tabla-estab-titulo">
      <div className="panel-header gap-y-3">
        <div>
          <h2 id="tabla-estab-titulo" className="panel-title">
            {nombreComuna ? `Establecimientos de ${nombreComuna}` : "Establecimientos de la región"}
          </h2>
          <p className="text-[12px] text-3">
            {cargada
              ? `${conPronostico} de ${establecimientos.length} con pronóstico${filas.length !== establecimientos.length ? ` · ${filas.length} con el filtro` : ""} · clic en el nombre para ver su serie`
              : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {comuna && (
            <span className="inline-flex items-center gap-2 text-[13px]">
              <a href={enlace(RUTA_TABLERO, { territorio: comuna })} className="link-button">
                Ver {nombreComuna ?? "la comuna"} en el tablero
              </a>
              <button type="button" onClick={() => onFiltrarComuna(null)} className="link-button">
                Toda la región
              </button>
            </span>
          )}
          <label htmlFor="buscar-estab" className="sr-only">Buscar por nombre o comuna</label>
          <input
            id="buscar-estab"
            type="search"
            className="input w-full sm:w-60"
            placeholder="Buscar por nombre o comuna"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
          <label htmlFor="tipo-estab" className="sr-only">Tipo de establecimiento</label>
          <select id="tipo-estab" className="select" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value={TODOS}>Todos los tipos</option>
            {tipos.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>
      <div className="mx-5 mb-5 max-h-128 overflow-auto rounded-lg border" style={{ borderColor: "var(--border)" }}>
        {!cargada ? (
          <div className="space-y-2 p-3" aria-busy="true" aria-label="Cargando tabla">
            {Array.from({ length: 10 }, (_, i) => <div key={i} className="skeleton h-6 w-full" />)}
          </div>
        ) : !filas.length ? (
          <p className="p-4 text-[13px] text-2">Ningún establecimiento coincide con la búsqueda o el tipo elegido.</p>
        ) : (
          <table className="w-full border-collapse text-[13px] num">
            <caption className="sr-only">
              {OBJETIVOS[objetivo].etiqueta} recientes y pronosticadas por establecimiento
            </caption>
            <thead className="sticky top-0 z-1" style={{ background: "var(--surface-2)" }}>
              <tr>
                {COLUMNAS.map((c) => (
                  <th
                    key={c.clave}
                    scope="col"
                    className={`whitespace-nowrap px-2.5 py-1.5 text-[12px] font-semibold text-2 ${c.texto ? "text-left" : "text-right"} ${c.clave === "colapso" ? "group relative" : ""}`}
                    aria-sort={orden.clave === c.clave ? (orden.asc ? "ascending" : "descending") : "none"}
                  >
                    <Tip texto={c.ayuda} lado={c.texto ? "izquierda" : "derecha"}>
                      <button
                        type="button"
                        onClick={() => alternar(c.clave)}
                        aria-describedby={c.clave === "colapso" ? ID_AYUDA_COLAPSO : undefined}
                        className="inline-flex min-h-6 items-center gap-1 hover:text-(--ink)"
                      >
                        {c.titulo}
                        {c.clave === "colapso" && (
                          <svg aria-hidden width="12" height="12" viewBox="0 0 16 16" fill="none" className="opacity-60">
                            <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
                            <path d="M8 7v4.5M8 4.6v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                          </svg>
                        )}
                        <span aria-hidden className="text-[10px]" style={{ opacity: orden.clave === c.clave ? 1 : 0.35 }}>
                          {orden.clave === c.clave && !orden.asc ? "▼" : "▲"}
                        </span>
                      </button>
                    </Tip>
                    {c.clave === "colapso" && <AyudaColapso />}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((fila) => {
                const o = fila.objetivos[objetivo];
                const activa = fila.establecimiento_codigo === seleccion;
                const { cambio, fuera } = cambioDe(fila, objetivo, umbral);
                return (
                  <tr
                    key={fila.establecimiento_codigo}
                    className="transition-colors duration-150 hover:bg-(--accent-weak)"
                    style={{
                      borderTop: "1px solid var(--grid)",
                      background: activa ? "var(--accent-weak)" : undefined,
                      boxShadow: activa ? "inset 0 0 0 1px var(--accent)" : undefined,
                    }}
                  >
                    <td className="px-2.5 py-1.5 text-left">
                      <button
                        type="button"
                        onClick={() => onElegir(fila.establecimiento_codigo)}
                        aria-pressed={activa}
                        className={`min-h-6 text-left hover:underline ${o?.incluido ? "font-medium" : "text-2"}`}
                      >
                        {fila.nombre}
                      </button>
                    </td>
                    <td className="px-2.5 py-1.5 text-left text-2">{fila.tipo}</td>
                    <td className="px-2.5 py-1.5 text-left">
                      {comuna ? (
                        <span className="text-2">{fila.comuna}</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => onFiltrarComuna(fila.comuna_codigo)}
                          className="min-h-6 text-left text-2 hover:text-(--ink) hover:underline"
                          aria-label={`Ver solo los establecimientos de ${fila.comuna}`}
                        >
                          {fila.comuna}
                        </button>
                      )}
                    </td>
                    <td className="px-2.5 py-1.5 text-right">{fmtCifra(o?.promedio_ultimas_semanas)}</td>
                    <td className="px-2.5 py-1.5 text-right">
                      {o?.incluido && o.pronostico_promedio != null
                        ? fmtCifra(o.pronostico_promedio)
                        : <span className="text-3">—</span>}
                    </td>
                    <td className="px-2.5 py-1.5 text-left">
                      <span className="inline-flex items-center gap-2">
                        <BadgeCambio
                          cambio={cambio}
                          fueraDelIntervalo={fuera}
                          compacto
                          titulo={o?.incluido ? undefined : (o?.motivo_sin_pronostico ?? undefined)}
                        />
                        {o?.incluido && <span className="text-[12px] text-3">{fmtPct(o.variacion_pct)}</span>}
                      </span>
                    </td>
                    <td className="px-2.5 py-1.5 text-right">
                      {fila.camas_psiquiatria == null ? <span className="text-3">—</span> : fmtEntero(fila.camas_psiquiatria)}
                    </td>
                    <td className="px-2.5 py-1.5 text-left">
                      {fila.colapso_psiquiatria ? (
                        <Tip texto={`Ocupación de camas de psiquiatría, ${fmtMesCorto(fila.colapso_psiquiatria.desde)} a ${fmtMesCorto(fila.colapso_psiquiatria.hasta)} (${fila.colapso_psiquiatria.meses} meses con camas habilitadas)`} lado="derecha">
                          <span className="inline-flex items-center gap-1.5 whitespace-nowrap" tabIndex={0}>
                            <span className={NIVELES[fila.colapso_psiquiatria.nivel].orden >= 2 ? "font-medium" : "text-2"}>
                              {NIVELES[fila.colapso_psiquiatria.nivel].etiqueta}
                            </span>
                            <span className="text-[12px] text-3 num">{fmtDecimal(fila.colapso_psiquiatria.indice_ocupacional)}%</span>
                          </span>
                        </Tip>
                      ) : (
                        <span className="text-3">—</span>
                      )}
                    </td>
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
