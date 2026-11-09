// Vista por establecimiento: el nivel mas fino del mismo modelo territorial. Se
// llega desde una comuna del tablero (o directo) y muestra el pronostico de
// atenciones de salud mental (ID36) y de hospitalizaciones indicadas desde la
// urgencia (ID42, solo hospitales). La cifra regional no se muestra aqui: la
// entrega el modelo comunal, que reconcilia.
//
// Este componente solo coordina el estado (objetivo, comuna, seleccion, ventana)
// y lo refleja en la URL; el detalle y la tabla viven en ./establecimientos.
import { useEffect, useMemo, useState } from "react";
import {
  api,
  type EstablecimientoDetalle,
  type EstablecimientoResumen,
  type EstadoProceso,
  type MetaEstablecimientos,
  type ObjetivoEstablecimiento,
} from "../api";
import { fmtFechaLarga } from "../format";
import { parametros, reflejar, RUTA_ESTABLECIMIENTOS } from "../ruta";
import { useTokens } from "../tokens";
import { Alcance } from "./Alcance";
import { AvisoLectura } from "./AvisoLectura";
import { BarraSuperior } from "./BarraSuperior";
import { AvisoDesactualizado } from "./establecimientos/AvisoDesactualizado";
import { esObjetivo, OBJETIVOS } from "./establecimientos/comun";
import { DetalleEstablecimiento } from "./establecimientos/DetalleEstablecimiento";
import { TablaEstablecimientos } from "./establecimientos/TablaEstablecimientos";

const VENTANAS = [26, 52, 104] as const;

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
  const [seleccion, setSeleccion] = useState<number | null>(() => {
    const id = Number(inicial.get("id"));
    return Number.isFinite(id) && id > 0 ? id : null;
  });
  // Si la seleccion la hizo la vista (y no la persona), se dice por que.
  const [automatica, setAutomatica] = useState(false);
  const [semanas, setSemanas] = useState<number>(VENTANAS[1]);
  const [detalle, setDetalle] = useState<EstablecimientoDetalle | null>(null);

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

  const metaObjetivo = meta?.objetivos.find((o) => o.objetivo === objetivo) ?? null;
  const umbral = meta?.umbral_cambio_pct ?? null;
  const estado: EstadoProceso = error ? "error" : meta && lista.length ? "listo" : "calculando";
  const resumen = lista.find((f) => f.establecimiento_codigo === seleccion);
  const ultima = meta ? { ...meta.ultima_semana_observada, fecha_inicio: meta.ultima_semana_fecha_inicio } : null;

  return (
    <>
      <BarraSuperior
        ultima={ultima}
        estadoPronostico={estado}
        vista="establecimientos"
        desactualizado={meta != null && !meta.vigente}
      />

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

        {meta && !meta.vigente && <AvisoDesactualizado motivo={meta.motivo_desactualizacion} />}
        {meta && <AvisoLectura advertencias={meta.advertencias} />}

        <DetalleEstablecimiento
          seleccion={seleccion}
          resumen={resumen}
          detalle={detalle}
          objetivo={objetivo}
          metaObjetivo={metaObjetivo}
          umbral={umbral}
          automatica={automatica}
          comuna={comuna}
          tokens={tokens}
        />

        <TablaEstablecimientos
          establecimientos={deLaComuna}
          cargada={lista.length > 0}
          objetivo={objetivo}
          umbral={umbral}
          seleccion={seleccion}
          onElegir={elegir}
          comuna={comuna}
          nombreComuna={nombreComuna}
          onFiltrarComuna={setComuna}
        />

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
