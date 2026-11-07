// Vista por establecimiento: el nivel mas fino del mismo modelo territorial. Se
// llega desde una comuna del tablero (o directo) y muestra el pronostico de
// atenciones de salud mental (ID36) y de hospitalizaciones indicadas desde la
// urgencia (ID42, solo hospitales). La cifra regional no se muestra aqui: la
// entrega el modelo comunal, que reconcilia.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type EstablecimientoDetalle,
  type EstablecimientoResumen,
  type EstadoProceso,
  type NivelColapso,
  type MetaEstablecimientos,
  type ObjetivoEstablecimiento,
  type SerieConPronostico,
} from "../api";
import { clasificar, fueraDelIntervalo } from "../cambio";
import { fmtDecimal, fmtEntero, fmtFechaLarga, fmtMesCorto, fmtPct, SIN_DATO } from "../format";
import { enlace, parametros, reflejar, RUTA_ESTABLECIMIENTOS, RUTA_TABLERO } from "../ruta";
import { useTokens } from "../tokens";
import { Alcance } from "./Alcance";
import { AvisoLectura } from "./AvisoLectura";
import { BadgeCambio } from "./BadgeCambio";
import { BarraSuperior } from "./BarraSuperior";
import { GraficoSerie, LeyendaSerie, TablaSerie } from "./GraficoSerie";
import { PanelOcupacion } from "./PanelOcupacion";

const VENTANAS = [26, 52, 104] as const;
const TODOS = "todos";

const OBJETIVOS: Record<ObjetivoEstablecimiento, { etiqueta: string; unidad: string; subtitulo: string }> = {
  atenciones_sm: {
    etiqueta: "Atenciones",
    unidad: "atenciones",
    subtitulo: "Atenciones semanales de urgencia en salud mental",
  },
  hospitalizaciones_sm: {
    etiqueta: "Hospitalizaciones",
    unidad: "hospitalizaciones",
    subtitulo: "Hospitalizaciones semanales indicadas desde la urgencia por trastornos mentales (F00-F99)",
  },
};

const esObjetivo = (v: string | null): v is ObjetivoEstablecimiento => v === "atenciones_sm" || v === "hospitalizaciones_sm";

// Volumenes de un digito pierden casi toda su informacion redondeados a entero.
const fmtCifra = (v: number | null | undefined) => (v != null && Math.abs(v) < 10 ? fmtDecimal(v) : fmtEntero(v));

function aSerie(detalle: EstablecimientoDetalle, objetivo: ObjetivoEstablecimiento): SerieConPronostico | null {
  const serie = detalle.series.find((s) => s.objetivo === objetivo);
  if (!serie) return null;
  return {
    series_id: String(detalle.establecimiento_codigo),
    nombre: detalle.nombre,
    nivel: "establecimiento",
    historico: serie.historico.map((p) => ({
      ano: p.ano, semana: p.semana, fecha_inicio: p.fecha_inicio, atenciones: p.valor,
    })),
    pronostico: serie.pronostico,
    estado_pronostico: "listo",
  };
}

type Clave = "nombre" | "tipo" | "comuna" | "reciente" | "pronostico" | "cambio" | "camas" | "colapso";

// Nivel de colapso: ocupacion de las camas de psiquiatria del hospital en los ultimos 12
// meses publicados (REM-20). Umbrales de la literatura, los mismos de la API y del EDA.
const NIVELES: Record<NivelColapso, { etiqueta: string; orden: number }> = {
  holgura: { etiqueta: "Holgura", orden: 0 },
  presion: { etiqueta: "Presión", orden: 1 },
  saturacion: { etiqueta: "Saturación", orden: 2 },
  sobre_capacidad: { etiqueta: "Sobre la capacidad", orden: 3 },
};
// Formula, clasificacion y fuentes del nivel de colapso: tooltip con el estilo de los
// tooltips de los graficos (panel, 12 px), visible al pasar el mouse o al enfocar.
function AyudaColapso() {
  return (
    <span
      id="ayuda-colapso"
      role="tooltip"
      className="panel pointer-events-none invisible absolute right-0 top-full z-20 mt-1 w-80 whitespace-normal px-3 py-2 text-left text-[12px] font-normal text-(--ink) opacity-0 shadow-sm transition-opacity duration-150 group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
    >
      <span className="block font-semibold">Nivel de colapso</span>
      <span className="mt-0.5 block num">Ocupación = Σ días‑cama ocupados ÷ Σ días‑cama disponibles</span>
      <span className="block text-2">Camas de psiquiatría del hospital, últimos 12 meses publicados.</span>
      <span className="mt-1.5 block">Holgura &lt; 85 % · Presión 85–90 % · Saturación ≥ 90 %</span>
      <span className="block">Sobre la capacidad: un área con más camas ocupadas que disponibles.</span>
      <span className="mt-1.5 block text-3">
        Fuentes: DEIS, REM-20. Umbrales: Royal College of Psychiatrists (85 %) y Bagust et al., BMJ 1999 (90 %).
      </span>
    </span>
  );
}

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

export function VistaEstablecimientos() {
  const tokens = useTokens();
  const inicial = useMemo(parametros, []);
  const [meta, setMeta] = useState<MetaEstablecimientos | null>(null);
  const [lista, setLista] = useState<EstablecimientoResumen[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [objetivo, setObjetivo] = useState<ObjetivoEstablecimiento>(() => {
    const o = inicial.get("objetivo");
    return esObjetivo(o) ? o : "atenciones_sm";
  });
  const [comuna, setComuna] = useState<string | null>(() => inicial.get("comuna"));
  const [tipo, setTipo] = useState<string>(TODOS);
  const [busqueda, setBusqueda] = useState("");
  const [seleccion, setSeleccion] = useState<number | null>(() => {
    const id = Number(inicial.get("id"));
    return Number.isFinite(id) && id > 0 ? id : null;
  });
  // Si la seleccion la hizo la vista (y no la persona), se dice por que.
  const [automatica, setAutomatica] = useState(false);
  const [semanas, setSemanas] = useState<number>(VENTANAS[1]);
  const [detalle, setDetalle] = useState<EstablecimientoDetalle | null>(null);
  const [orden, setOrden] = useState<{ clave: Clave; asc: boolean }>({ clave: "pronostico", asc: false });

  useEffect(() => {
    const fallo = (e: unknown) => setError(e instanceof Error ? e.message : String(e));
    api.metaEstablecimientos().then(setMeta).catch(fallo);
    api.establecimientos().then(setLista).catch(fallo);
  }, []);

  useEffect(() => {
    reflejar(RUTA_ESTABLECIMIENTOS, {
      comuna,
      id: seleccion,
      objetivo: objetivo === "atenciones_sm" ? null : objetivo,
    });
  }, [comuna, seleccion, objetivo]);

  // Las hospitalizaciones solo se modelan en hospitales: el resto no aporta filas.
  const delObjetivo = useMemo(
    () => (objetivo === "hospitalizaciones_sm" ? lista.filter((f) => f.tipo === "Hospital") : lista),
    [lista, objetivo],
  );
  const deLaComuna = useMemo(
    () => (comuna ? delObjetivo.filter((f) => f.comuna_codigo === comuna) : delObjetivo),
    [delObjetivo, comuna],
  );
  const nombreComuna = lista.find((f) => f.comuna_codigo === comuna)?.comuna ?? null;
  const tipos = useMemo(() => [...new Set(deLaComuna.map((f) => f.tipo))].sort((a, b) => a.localeCompare(b, "es")), [deLaComuna]);
  const conPronostico = deLaComuna.filter((f) => f.objetivos[objetivo]?.incluido).length;

  const umbral = meta?.umbral_cambio_pct ?? null;
  const cambioDe = (fila: EstablecimientoResumen) => {
    const o = fila.objetivos[objetivo];
    if (!o?.incluido) return { cambio: "sin_pronostico" as const, fuera: null };
    return {
      cambio: clasificar(o.variacion_pct, umbral),
      fuera: fueraDelIntervalo(o.promedio_ultimas_semanas, o.limite_inferior_promedio, o.limite_superior_promedio),
    };
  };

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLocaleLowerCase("es");
    const filtradas = deLaComuna.filter((f) =>
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
  }, [deLaComuna, tipo, busqueda, orden, objetivo]);

  // Si no hay seleccion valida para el filtro actual, se abre el establecimiento
  // de mayor pronostico: la pantalla nunca queda vacia, y se dice por que es ese.
  useEffect(() => {
    if (!deLaComuna.length) return;
    if (seleccion != null && deLaComuna.some((f) => f.establecimiento_codigo === seleccion)) return;
    const mayor = [...deLaComuna].sort(
      (a, b) => (b.objetivos[objetivo]?.pronostico_promedio ?? -1) - (a.objetivos[objetivo]?.pronostico_promedio ?? -1),
    )[0];
    setSeleccion(mayor.establecimiento_codigo);
    setAutomatica(true);
  }, [deLaComuna, objetivo, seleccion]);

  useEffect(() => {
    if (seleccion == null) return;
    const control = new AbortController();
    setDetalle(null);
    api.establecimiento(seleccion, semanas, control.signal)
      .then(setDetalle)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => control.abort();
  }, [seleccion, semanas]);

  const elegir = (codigo: number) => {
    setSeleccion(codigo);
    setAutomatica(false);
  };
  const filtrarComuna = (codigo: string | null) => {
    setComuna(codigo);
    setBusqueda("");
    setTipo(TODOS);
  };
  const alternar = (clave: Clave) =>
    setOrden((o) => ({ clave, asc: o.clave === clave ? !o.asc : ["nombre", "tipo", "comuna"].includes(clave) }));

  const metaObjetivo = meta?.objetivos.find((o) => o.objetivo === objetivo) ?? null;
  const intervalo = metaObjetivo ? `${Math.round(metaObjetivo.nivel_intervalo * 100)}%` : "";
  const horizontes = metaObjetivo?.horizontes ?? [];
  const rango = horizontes.length ? `${horizontes[0]} a ${horizontes[horizontes.length - 1]} semanas` : "";
  const estado: EstadoProceso = error ? "error" : meta && lista.length ? "listo" : "calculando";
  const resumen = lista.find((f) => f.establecimiento_codigo === seleccion);
  const resumenObjetivo = resumen?.objetivos[objetivo];
  const cambioSeleccion = resumen ? cambioDe(resumen) : null;
  const serie = detalle && detalle.establecimiento_codigo === seleccion ? aSerie(detalle, objetivo) : null;
  const motivo = detalle?.series.find((s) => s.objetivo === objetivo)?.motivo_sin_pronostico ?? resumenObjetivo?.motivo_sin_pronostico;
  const primero = serie?.pronostico?.[0];
  const { unidad, subtitulo } = OBJETIVOS[objetivo];
  // Al cambiar de establecimiento el detalle se reemplaza por un esqueleto; si fuera
  // mas bajo, la pagina se acortaria y el navegador moveria el scroll al final.
  const cuerpoDetalle = useRef<HTMLDivElement>(null);
  const alturaDetalle = useRef(0);
  useLayoutEffect(() => {
    if (serie && cuerpoDetalle.current) alturaDetalle.current = cuerpoDetalle.current.offsetHeight;
  });
  const ultima = meta ? { ...meta.ultima_semana_observada, fecha_inicio: meta.ultima_semana_fecha_inicio } : null;

  return (
    <>
      <BarraSuperior ultima={ultima} estadoPronostico={estado} vista="establecimientos" />

      <main id="contenido" tabIndex={-1} className="mx-auto max-w-7xl space-y-5 px-4 py-5 outline-none sm:px-6">
        {error && (
          <div role="alert" className="panel px-4 py-3 text-[13px]" style={{ borderColor: "var(--alza)" }}>
            <p className="font-semibold">No se pudo consultar el pronóstico por establecimiento.</p>
            <p className="text-2">{error}</p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-medium text-2" id="objetivo-label">Pronosticar</span>
            <div className="segmented" role="group" aria-labelledby="objetivo-label">
              {(Object.keys(OBJETIVOS) as ObjetivoEstablecimiento[]).map((o) => (
                <button key={o} type="button" onClick={() => setObjetivo(o)} aria-pressed={objetivo === o}>
                  {OBJETIVOS[o].etiqueta}
                </button>
              ))}
            </div>
            {objetivo === "hospitalizaciones_sm" && (
              <span className="text-[12px] text-3">solo hospitales</span>
            )}
          </div>
          <div className="flex items-center gap-2 sm:ml-auto">
            <span className="text-[13px] font-medium text-2" id="historia-label">Historia</span>
            <div className="segmented" role="group" aria-labelledby="historia-label">
              {VENTANAS.map((v) => (
                <button key={v} type="button" onClick={() => setSemanas(v)} aria-pressed={semanas === v}>
                  {v} semanas
                </button>
              ))}
            </div>
          </div>
        </div>

        {meta && <AvisoLectura advertencias={meta.advertencias} />}

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
              </div>

              {objetivo === "hospitalizaciones_sm" && detalle?.ocupacion_psiquiatria?.length ? (
                <PanelOcupacion
                  key={detalle.establecimiento_codigo}
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

        <section className="panel flex flex-col" aria-labelledby="tabla-estab-titulo">
          <div className="panel-header gap-y-3">
            <div>
              <h2 id="tabla-estab-titulo" className="panel-title">
                {nombreComuna ? `Establecimientos de ${nombreComuna}` : "Establecimientos de la región"}
              </h2>
              <p className="text-[12px] text-3">
                {lista.length
                  ? `${conPronostico} de ${deLaComuna.length} con pronóstico${filas.length !== deLaComuna.length ? ` · ${filas.length} con el filtro` : ""} · clic en el nombre para ver su serie`
                  : ""}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {comuna && (
                <span className="inline-flex items-center gap-2 text-[13px]">
                  <a href={enlace(RUTA_TABLERO, { territorio: comuna })} className="link-button">
                    Ver {nombreComuna ?? "la comuna"} en el tablero
                  </a>
                  <button type="button" onClick={() => filtrarComuna(null)} className="link-button">
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
            {!lista.length ? (
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
                        title={c.ayuda}
                        className={`whitespace-nowrap px-2.5 py-1.5 text-[12px] font-semibold text-2 ${c.texto ? "text-left" : "text-right"} ${c.clave === "colapso" ? "group relative" : ""}`}
                        aria-sort={orden.clave === c.clave ? (orden.asc ? "ascending" : "descending") : "none"}
                      >
                        <button
                          type="button"
                          onClick={() => alternar(c.clave)}
                          aria-describedby={c.clave === "colapso" ? "ayuda-colapso" : undefined}
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
                        {c.clave === "colapso" && <AyudaColapso />}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filas.map((fila) => {
                    const o = fila.objetivos[objetivo];
                    const activa = fila.establecimiento_codigo === seleccion;
                    const { cambio, fuera } = cambioDe(fila);
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
                            onClick={() => elegir(fila.establecimiento_codigo)}
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
                              onClick={() => filtrarComuna(fila.comuna_codigo)}
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
                            <span
                              className="inline-flex items-center gap-1.5 whitespace-nowrap"
                              title={`Ocupación de camas de psiquiatría, ${fmtMesCorto(fila.colapso_psiquiatria.desde)} a ${fmtMesCorto(fila.colapso_psiquiatria.hasta)} (${fila.colapso_psiquiatria.meses} meses con camas habilitadas)`}
                            >
                              <span className={NIVELES[fila.colapso_psiquiatria.nivel].orden >= 2 ? "font-medium" : "text-2"}>
                                {NIVELES[fila.colapso_psiquiatria.nivel].etiqueta}
                              </span>
                              <span className="text-[12px] text-3 num">{fmtDecimal(fila.colapso_psiquiatria.indice_ocupacional)}%</span>
                            </span>
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

        <Alcance />

        <footer className="border-t pb-6 pt-4 text-[12px] text-3" style={{ borderColor: "var(--border)" }}>
          <p className="max-w-[90ch]">
            Fuente: DEIS/MINSAL, atenciones de urgencia por causas de salud mental (ID36) y hospitalizaciones indicadas
            desde la urgencia por trastornos mentales (ID42, F00-F99). Camas: DEIS/DIGERA, dotación del SNSS;
            ocupación: DEIS, estadísticas hospitalarias REM-20 (promedio mensual). Nivel de colapso: ocupación de las
            camas de psiquiatría en los últimos 12 meses publicados, con los umbrales de 85 % (Royal College of
            Psychiatrists) y 90 % (Bagust et al., BMJ 1999). La cifra regional se lee en la vista por comuna.
          </p>
          <p className="mt-1">
            Modelo: <span className="font-mono text-[11px]">{metaObjetivo?.modelo ?? "—"}</span>
            {meta && <> · generado el {fmtFechaLarga(meta.pronostico_generado_en)}</>}. Las cifras son eventos, no
            personas, y reflejan utilización y oferta, no prevalencia.
          </p>
        </footer>
      </main>
    </>
  );
}
