// Tablero: la vista de analisis. Vive separado de la pagina de entrada para
// que la landing no cargue ni el mapa ni los datos del pronostico.
import { useEffect, useMemo, useState } from "react";
import { api, type CamasPsiquiatria, type EstablecimientoResumen, type EstadoProceso, type EventoCalendario, type Meta, type ResumenComuna, type SerieConPronostico, type SerieSuicidios, type Territorio } from "../api";
import { enlace, parametros, reflejar, RUTA_ESTABLECIMIENTOS, RUTA_TABLERO } from "../ruta";
import { Alcance } from "./Alcance";
import { AvisoLectura } from "./AvisoLectura";
import { BarraSuperior } from "./BarraSuperior";
import { MapaComunal } from "./MapaComunal";
import { PanelHospitalizaciones } from "./PanelHospitalizaciones";
import { PanelSerie } from "./PanelSerie";
import { TablaComunal } from "./TablaComunal";
import { useTokens } from "../tokens";

const REGION = "RM";
const VENTANAS = [26, 52, 104] as const;
// Semanas extra de historia de suicidios: sus datos se publican con otro desfase que los
// de atenciones, y el grafico se recorta al eje de atenciones. Con margen, su primera
// semana siempre tiene dato.
const MARGEN_SUICIDIOS = 26;

export function Tablero() {
  const tokens = useTokens();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [territorios, setTerritorios] = useState<Territorio[]>([]);
  const [resumen, setResumen] = useState<ResumenComuna[]>([]);
  const [geo, setGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  // El territorio viaja en la URL: un enlace desde la vista por establecimiento
  // abre directamente su comuna.
  const [seleccion, setSeleccion] = useState(() => parametros().get("territorio") ?? REGION);
  // Misma ventana por defecto que la vista por establecimiento: un ano completo
  // muestra la estacionalidad.
  const [semanas, setSemanas] = useState<number>(VENTANAS[1]);
  const [establecimientos, setEstablecimientos] = useState<EstablecimientoResumen[]>([]);
  const [serie, setSerie] = useState<SerieConPronostico | null>(null);
  const [camas, setCamas] = useState<CamasPsiquiatria | null>(null);
  const [suicidios, setSuicidios] = useState<SerieSuicidios | null>(null);
  const [errorSuicidios, setErrorSuicidios] = useState<string | null>(null);
  const [eventos, setEventos] = useState<EventoCalendario[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Carga inicial. Cada recurso se pinta apenas llega; el pronostico puede
  // tardar unos segundos mas si el backend recien arranco (el cliente reintenta).
  useEffect(() => {
    const fallo = (e: unknown) => setError(e instanceof Error ? e.message : String(e));
    api.meta().then(setMeta).catch(fallo);
    api.territorios().then(setTerritorios).catch(fallo);
    api.geoComunas().then(setGeo).catch(fallo);
    api.resumenComunal().then(setResumen).catch(fallo);
    // Solo alimenta el enlace a la vista por establecimiento: si falta, el
    // tablero sigue igual, sin el enlace.
    api.establecimientos().then(setEstablecimientos).catch(() => undefined);
    // Marcas de contexto del grafico de suicidios: una sola consulta que cubre la
    // ventana mas larga (104 semanas) y el pronostico. Si falla, el grafico sale sin marcas.
    const ano = new Date().getFullYear();
    api.calendarioEventos(`${ano - 3}-01-01`, `${ano + 1}-12-31`).then(setEventos).catch(() => undefined);
  }, []);

  useEffect(() => {
    reflejar(RUTA_TABLERO, { territorio: seleccion === REGION ? null : seleccion });
  }, [seleccion]);

  // El resumen llega cuando el pronostico esta listo: entonces la meta ya tiene
  // la hora de calculo y la serie seleccionada puede traer su pronostico.
  const pronosticoListo = resumen.length > 0;
  const estadoPronostico: EstadoProceso = error ? "error" : pronosticoListo ? "listo" : "calculando";

  useEffect(() => {
    const control = new AbortController();
    setSerie(null);
    api.serie(seleccion, semanas, control.signal)
      .then(setSerie)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => control.abort();
  }, [seleccion, semanas, pronosticoListo]);

  // Capa de contexto: si falta (la API responde 404), el tablero sigue sin la linea
  // de camas en vez de mostrar un error.
  useEffect(() => {
    const control = new AbortController();
    setCamas(null);
    api.camasPsiquiatria(seleccion, control.signal)
      .then(setCamas)
      .catch(() => undefined);
    return () => control.abort();
  }, [seleccion]);

  // Suicidios del mismo territorio y la misma ventana. Es un output persistido e
  // independiente del pronostico de atenciones: su falla no afecta al resto del tablero.
  useEffect(() => {
    const control = new AbortController();
    setSuicidios(null);
    setErrorSuicidios(null);
    api.suicidios(seleccion, semanas + MARGEN_SUICIDIOS, control.signal)
      .then(setSuicidios)
      .catch((e) => e.name !== "AbortError" && setErrorSuicidios(e instanceof Error ? e.message : String(e)));
    return () => control.abort();
  }, [seleccion, semanas]);

  useEffect(() => {
    if (pronosticoListo) api.meta().then(setMeta).catch(() => undefined);
  }, [pronosticoListo]);

  const resumenPorId = useMemo(() => new Map(resumen.map((r) => [r.series_id, r])), [resumen]);
  const seleccionables = territorios.filter((t) => t.tiene_pronostico);
  const region = seleccionables.find((t) => t.nivel === "region");
  const comunas = seleccionables.filter((t) => t.nivel === "comuna");

  const enlaceEstablecimientos = useMemo(() => {
    const propios = seleccion === REGION ? establecimientos : establecimientos.filter((e) => e.comuna_codigo === seleccion);
    if (!propios.length) return null;
    const n = propios.length;
    const nombre = seleccion === REGION ? "de la región" : `de ${propios[0].comuna}`;
    return {
      href: enlace(RUTA_ESTABLECIMIENTOS, { comuna: seleccion === REGION ? null : seleccion }),
      texto: `Ver ${n === 1 ? "su establecimiento" : `los ${n} establecimientos ${nombre}`} →`,
    };
  }, [establecimientos, seleccion]);
  const establecimientosPorComuna = useMemo(() => {
    const conteo = new Map<string, number>();
    for (const e of establecimientos) conteo.set(e.comuna_codigo, (conteo.get(e.comuna_codigo) ?? 0) + 1);
    return conteo;
  }, [establecimientos]);

  return (
    <>
      <BarraSuperior ultima={meta?.ultima_semana_observada ?? null} estadoPronostico={estadoPronostico} vista="comunas" />

      <main id="contenido" tabIndex={-1} className="mx-auto max-w-7xl space-y-5 px-4 py-5 outline-none sm:px-6">
        {error && (
          <div role="alert" className="panel px-4 py-3 text-[13px]" style={{ borderColor: "var(--alza)" }}>
            <p className="font-semibold">No se pudo consultar la API.</p>
            <p className="text-2">
              {error}. Verifique que el backend esté corriendo (<code>uvicorn src.api.main:app</code>) y que el
              pipeline haya generado sus outputs.
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div className="flex items-center gap-2">
            <label htmlFor="territorio" className="text-[13px] font-medium text-2">Territorio</label>
            <select id="territorio" value={seleccion} onChange={(e) => setSeleccion(e.target.value)} className="select">
              {region && <option value={region.series_id}>{region.nombre}</option>}
              <optgroup label="Comunas">
                {comunas.map((t) => (
                  <option key={t.series_id} value={t.series_id}>{t.nombre}</option>
                ))}
              </optgroup>
            </select>
            {seleccion !== REGION && (
              <button type="button" onClick={() => setSeleccion(REGION)} className="link-button">
                Volver a la región
              </button>
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

        <PanelSerie
          serie={serie}
          tokens={tokens}
          nivelIntervalo={meta?.nivel_intervalo ?? null}
          cobertura={meta?.cobertura_holdout ?? null}
          umbralCambioPct={meta?.umbral_cambio_pct ?? null}
          semanaParcial={meta?.semana_en_curso ?? null}
          camas={camas}
          establecimientos={enlaceEstablecimientos}
          suicidios={suicidios}
          errorSuicidios={errorSuicidios}
          eventos={eventos}
        />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] [&>*]:min-w-0">
          <MapaComunal
            geo={geo}
            resumen={resumenPorId}
            seleccion={seleccion}
            onSeleccionar={setSeleccion}
            tokens={tokens}
            establecimientos={establecimientos}
          />
          <TablaComunal
            filas={resumen}
            seleccion={seleccion}
            onSeleccionar={setSeleccion}
            establecimientosPorComuna={establecimientosPorComuna}
          />
        </div>

        {/* Despues de donde se atiende la gente (urgencias), quien se hospitaliza segun donde vive. */}
        <PanelHospitalizaciones seriesId={seleccion} />

        <Alcance />

        <footer className="border-t pb-6 pt-4 text-[12px] text-3" style={{ borderColor: "var(--border)" }}>
          <p className="max-w-[90ch]">
            Fuente: DEIS/MINSAL, atenciones de urgencia por causas de salud mental (ID36, incluye ideación suicida,
            ID37). Suicidios: DEIS, defunciones por lesiones autoinfligidas (X60–X84) según comuna de
            residencia. Población: INE, proyecciones comunales. Pobreza: MDS, Casen 2022. Límites comunales: INE, Censo 2024.
          </p>
          <p className="mt-1">
            Modelo: <span className="font-mono text-[11px]">{meta?.modelo ?? "—"}</span>. Las cifras son atenciones
            (eventos), no personas, y reflejan utilización y oferta, no prevalencia.
          </p>
        </footer>
      </main>
    </>
  );
}
