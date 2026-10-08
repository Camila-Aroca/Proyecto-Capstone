// Tablero: la vista de analisis. Vive separado de la pagina de entrada para
// que la landing no cargue ni el mapa ni los datos del pronostico.
import { useEffect, useMemo, useState } from "react";
import { api, type EstadoProceso, type Meta, type ResumenComuna, type SerieConPronostico, type Territorio } from "../api";
import { Alcance } from "./Alcance";
import { AvisoLectura } from "./AvisoLectura";
import { BarraSuperior } from "./BarraSuperior";
import { MapaComunal } from "./MapaComunal";
import { PanelSerie } from "./PanelSerie";
import { TablaComunal } from "./TablaComunal";
import { useTokens } from "../tokens";

const REGION = "RM";
const VENTANAS = [26, 52, 104] as const;

export function Tablero() {
  const tokens = useTokens();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [territorios, setTerritorios] = useState<Territorio[]>([]);
  const [resumen, setResumen] = useState<ResumenComuna[]>([]);
  const [geo, setGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  const [seleccion, setSeleccion] = useState(REGION);
  const [semanas, setSemanas] = useState<number>(VENTANAS[0]);
  const [serie, setSerie] = useState<SerieConPronostico | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Carga inicial. Cada recurso se pinta apenas llega; el pronostico puede
  // tardar unos segundos mas si el backend recien arranco (el cliente reintenta).
  useEffect(() => {
    const fallo = (e: unknown) => setError(e instanceof Error ? e.message : String(e));
    api.meta().then(setMeta).catch(fallo);
    api.territorios().then(setTerritorios).catch(fallo);
    api.geoComunas().then(setGeo).catch(fallo);
    api.resumenComunal().then(setResumen).catch(fallo);
  }, []);

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

  useEffect(() => {
    if (pronosticoListo) api.meta().then(setMeta).catch(() => undefined);
  }, [pronosticoListo]);

  const resumenPorId = useMemo(() => new Map(resumen.map((r) => [r.series_id, r])), [resumen]);
  const seleccionables = territorios.filter((t) => t.tiene_pronostico);
  const region = seleccionables.find((t) => t.nivel === "region");
  const comunas = seleccionables.filter((t) => t.nivel === "comuna");

  return (
    <>
      <BarraSuperior meta={meta} estadoPronostico={estadoPronostico} />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-5 sm:px-6">
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
        />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] [&>*]:min-w-0">
          <MapaComunal geo={geo} resumen={resumenPorId} seleccion={seleccion} onSeleccionar={setSeleccion} tokens={tokens} />
          <TablaComunal filas={resumen} seleccion={seleccion} onSeleccionar={setSeleccion} />
        </div>

        <Alcance />

        <footer className="border-t pb-6 pt-4 text-[12px] text-3" style={{ borderColor: "var(--border)" }}>
          <p className="max-w-[90ch]">
            Fuente: DEIS/MINSAL, atenciones de urgencia por causas de salud mental (ID36, incluye ideación suicida,
            ID37). Población: INE, proyecciones comunales. Pobreza: MDS, Casen 2022. Límites comunales: INE, Censo 2024.
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
