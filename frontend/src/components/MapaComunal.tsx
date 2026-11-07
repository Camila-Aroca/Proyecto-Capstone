import { geoJSON, type Layer, type LeafletMouseEvent, type PathOptions } from "leaflet";
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import type { ResumenComuna } from "../api";
import { fmtDecimal, fmtEntero, fmtPct } from "../format";
import { Tip } from "./Tip";
import {
  CAMBIO,
  CLASES_SECUENCIALES,
  claseSecuencial,
  cortesQuintiles,
  type Tokens,
} from "../tokens";

type Metrica = "concentracion" | "cambio";

interface Props {
  geo: GeoJSON.FeatureCollection | null;
  resumen: Map<string, ResumenComuna>;
  seleccion: string;
  onSeleccionar: (seriesId: string) => void;
  tokens: Tokens;
}

// Mapa base de CARTO: solo si hay clave (frontend/.env.local). Sin clave, el
// mapa se dibuja con los limites comunales sobre el fondo del panel.
const CARTO_KEY = import.meta.env.VITE_CARTO_API_KEY?.trim();
const CARTO_ATRIBUCION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>';

function urlCarto(oscuro: boolean): string {
  const estilo = oscuro ? "dark_all" : "light_all";
  return `https://basemaps.cartocdn.com/rastertiles/${estilo}/{z}/{x}/{y}.png?key=${encodeURIComponent(CARTO_KEY ?? "")}`;
}

// Tooltip de la comuna: un panel propio en un portal sobre el body, no el de Leaflet. El de
// Leaflet vive dentro del mapa (overflow oculto) y se cortaba en cuanto la comuna quedaba cerca
// de un borde. Este se abre hacia el lado con mas espacio dentro del mapa (a la derecha si el
// cursor esta en su mitad izquierda, a la izquierda si esta en la derecha; igual arriba y
// abajo), y despues se ajusta a la ventana para no salirse nunca.
const DESPLAZAMIENTO = 16;
const MARGEN = 12;

function posicionar(el: HTMLElement, x: number, y: number, mapa: DOMRect | undefined) {
  const { offsetWidth: ancho, offsetHeight: alto } = el;
  const haciaDerecha = mapa ? mapa.right - x >= x - mapa.left : true;
  const haciaAbajo = mapa ? mapa.bottom - y >= y - mapa.top : true;
  let izquierda = haciaDerecha ? x + DESPLAZAMIENTO : x - DESPLAZAMIENTO - ancho;
  let arriba = haciaAbajo ? y + DESPLAZAMIENTO : y - DESPLAZAMIENTO - alto;
  // Respaldo: si el lado elegido no cabe en la ventana, se usa el opuesto.
  if (izquierda < MARGEN || izquierda + ancho > window.innerWidth - MARGEN) {
    izquierda = haciaDerecha ? x - DESPLAZAMIENTO - ancho : x + DESPLAZAMIENTO;
  }
  if (arriba < MARGEN || arriba + alto > window.innerHeight - MARGEN) {
    arriba = haciaAbajo ? y - DESPLAZAMIENTO - alto : y + DESPLAZAMIENTO;
  }
  const dentro = (v: number, tam: number, max: number) => Math.min(Math.max(MARGEN, v), Math.max(MARGEN, max - MARGEN - tam));
  el.style.transform = `translate(${dentro(izquierda, ancho, window.innerWidth)}px, ${dentro(arriba, alto, window.innerHeight)}px)`;
}

export function MapaComunal({ geo, resumen, seleccion, onSeleccionar, tokens }: Props) {
  const [metrica, setMetrica] = useState<Metrica>("concentracion");
  // Comuna bajo el puntero. La posicion no es estado: se escribe directo en el elemento en cada
  // movimiento para seguir al cursor sin renderizar de nuevo.
  const [bajoPuntero, setBajoPuntero] = useState<{ id: string; nombre: string } | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<HTMLDivElement>(null);
  const punteroRef = useRef({ x: 0, y: 0 });
  const ocultarRef = useRef(0);
  useLayoutEffect(() => {
    if (bajoPuntero && panelRef.current) {
      posicionar(panelRef.current, punteroRef.current.x, punteroRef.current.y, mapaRef.current?.getBoundingClientRect());
    }
  }, [bajoPuntero]);
  const limites = useMemo(() => (geo ? geoJSON(geo).getBounds() : null), [geo]);
  const conMapaBase = Boolean(CARTO_KEY);

  const cortes = useMemo(
    () =>
      cortesQuintiles(
        [...resumen.values()]
          .map((r) => r.tasa_pronostico_por_10000)
          .filter((v): v is number => v != null),
      ),
    [resumen],
  );

  const colorDe = (fila: ResumenComuna | undefined): string => {
    if (!fila?.tiene_pronostico) return tokens["sin-dato"];
    if (metrica === "cambio") return tokens[CAMBIO[fila.cambio_esperado].token];
    const tasa = fila.tasa_pronostico_por_10000;
    return tasa == null ? tokens["sin-dato"] : tokens[CLASES_SECUENCIALES[claseSecuencial(tasa, cortes)]];
  };

  const estilo = (feature?: GeoJSON.Feature): PathOptions => {
    const id = String(feature?.properties?.series_id ?? "");
    const fila = resumen.get(id);
    const seleccionada = id === seleccion;
    const conPronostico = Boolean(fila?.tiene_pronostico);
    return {
      fillColor: colorDe(fila),
      fillOpacity: conMapaBase ? (conPronostico ? 0.78 : 0.45) : conPronostico ? 0.92 : 0.6,
      // Codificacion secundaria: sin pronostico lleva borde punteado.
      color: seleccionada ? tokens.ink : conPronostico ? tokens.surface : tokens["ink-3"],
      dashArray: conPronostico ? undefined : "3 3",
      weight: seleccionada ? 2.5 : 0.8,
    };
  };

  const alCrear = (feature: GeoJSON.Feature, capa: Layer) => {
    const id = String(feature.properties?.series_id ?? "");
    const fila = resumen.get(id);
    const nombre = fila?.nombre ?? String(feature.properties?.nombre ?? id);
    capa.on({
      click: () => fila?.tiene_pronostico && onSeleccionar(id),
      mouseover: (e: LeafletMouseEvent) => {
        e.target.setStyle({ weight: 2.5 });
        cancelAnimationFrame(ocultarRef.current);
        punteroRef.current = { x: e.originalEvent.clientX, y: e.originalEvent.clientY };
        setBajoPuntero({ id, nombre });
      },
      mousemove: (e: LeafletMouseEvent) => {
        punteroRef.current = { x: e.originalEvent.clientX, y: e.originalEvent.clientY };
        if (panelRef.current) {
          posicionar(panelRef.current, punteroRef.current.x, punteroRef.current.y, mapaRef.current?.getBoundingClientRect());
        }
      },
      mouseout: (e: LeafletMouseEvent) => {
        e.target.setStyle({ weight: id === seleccion ? 2.5 : 0.8 });
        // Un cuadro de espera: al pasar a la comuna vecina el mouseover siguiente cancela el
        // cierre y el panel no parpadea.
        ocultarRef.current = requestAnimationFrame(() => setBajoPuntero(null));
      },
    });
  };

  const leyendaConcentracion = cortes.length
    ? CLASES_SECUENCIALES.map((token, i) => {
        const desde = i === 0 ? null : cortes[i - 1];
        const hasta = i < cortes.length ? cortes[i] : null;
        const texto =
          desde == null ? `≤ ${fmtDecimal(hasta)}` : hasta == null ? `> ${fmtDecimal(desde)}` : `${fmtDecimal(desde)}–${fmtDecimal(hasta)}`;
        return { token, texto };
      })
    : [];

  const filaBajoPuntero = bajoPuntero ? resumen.get(bajoPuntero.id) : undefined;
  const alzas = [...resumen.values()].filter((r) => r.cambio_esperado === "alza").length;
  const bajas = [...resumen.values()].filter((r) => r.cambio_esperado === "baja").length;

  return (
    <section className="panel flex flex-col" aria-labelledby="mapa-titulo">
      <div className="panel-header">
        <h2 id="mapa-titulo" className="panel-title">Mapa comunal</h2>
        <div className="segmented" role="group" aria-label="Métrica del mapa">
          <button type="button" aria-pressed={metrica === "concentracion"} onClick={() => setMetrica("concentracion")}>
            Concentración
          </button>
          <button type="button" aria-pressed={metrica === "cambio"} onClick={() => setMetrica("cambio")}>
            Cambio esperado
          </button>
        </div>
      </div>

      <div ref={mapaRef} className="relative isolate mx-5 h-104 overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
        {geo && limites ? (
          <MapContainer
            bounds={limites}
            boundsOptions={{ padding: [8, 8] }}
            zoomSnap={0.25}
            scrollWheelZoom={false}
            attributionControl={conMapaBase}
            className="h-full w-full"
          >
            {conMapaBase && (
              // La atribucion visible es condicion del plan gratuito de CARTO.
              <TileLayer key={tokens.oscuro ? "oscuro" : "claro"} url={urlCarto(tokens.oscuro)} attribution={CARTO_ATRIBUCION} />
            )}
            {/* La key fuerza a repintar estilos al cambiar seleccion, metrica, datos o tema. */}
            <GeoJSON
              key={`${seleccion}-${metrica}-${resumen.size}-${tokens.oscuro}`}
              data={geo}
              style={estilo}
              onEachFeature={alCrear}
            />
          </MapContainer>
        ) : (
          <div className="skeleton h-full w-full rounded-none" aria-busy="true" aria-label="Cargando mapa" />
        )}
      </div>

      {bajoPuntero && createPortal(
        <div ref={panelRef} role="tooltip" style={{ willChange: "transform" }}
          className="panel pointer-events-none fixed left-0 top-0 z-50 max-w-64 px-3 py-2 text-[12px] leading-snug text-(--ink) shadow-sm">
          <p className="font-semibold">{bajoPuntero.nombre}</p>
          {filaBajoPuntero?.tiene_pronostico ? (
            <div className="num text-2">
              <p>{fmtDecimal(filaBajoPuntero.tasa_pronostico_por_10000)} atenciones por 10.000 hab. a la semana</p>
              <p>Pronóstico: {fmtEntero(filaBajoPuntero.pronostico_promedio)} por semana ({fmtPct(filaBajoPuntero.variacion_pct)})</p>
              <p>Cambio esperado: {CAMBIO[filaBajoPuntero.cambio_esperado].etiqueta.toLowerCase()}</p>
            </div>
          ) : (
            <p className="text-2">
              Sin pronóstico{filaBajoPuntero?.motivo_sin_pronostico ? `: ${filaBajoPuntero.motivo_sin_pronostico}` : ""}
            </p>
          )}
        </div>,
        document.body,
      )}

      <div className="space-y-2 px-5 pb-5 pt-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-2" aria-label="Leyenda del mapa">
          {metrica === "concentracion"
            ? leyendaConcentracion.map(({ token, texto }) => (
                <li key={token} className="inline-flex items-center gap-1.5 num">
                  <span className="inline-block h-3 w-3 rounded-sm" style={{ background: tokens[token] }} />
                  {texto}
                </li>
              ))
            : (["alza", "baja", "estable"] as const).map((c) => (
                <li key={c} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-3 w-3 rounded-sm" style={{ background: tokens[CAMBIO[c].token] }} />
                  <span aria-hidden>{CAMBIO[c].icono}</span> {CAMBIO[c].etiqueta}
                </li>
              ))}
          <li className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ background: tokens["sin-dato"], outline: `1px dashed ${tokens["ink-3"]}`, outlineOffset: -1 }}
            />
            Sin pronóstico
          </li>
          {/* Solo desarrollo: quien usa el producto no necesita saber de la clave del mapa base. */}
          {!conMapaBase && import.meta.env.DEV && (
            <li className="sm:ml-auto">
              <Tip texto="Defina VITE_CARTO_API_KEY en frontend/.env.local para dibujar el mapa base." lado="derecha">
                <span tabIndex={0} className="badge badge-sin_pronostico">
                  <span className="badge-icon" aria-hidden>∅</span>
                  Sin mapa base
                </span>
              </Tip>
            </li>
          )}
        </ul>
        <p className="max-w-[75ch] text-[12px] text-3">
          {metrica === "concentracion"
            ? "Atenciones pronosticadas por 10.000 habitantes a la semana, en quintiles. Cada atención se asigna a la comuna del establecimiento que la registra, no a la de residencia: una comuna con un centro de referencia regional, como Recoleta con el Instituto Horwitz, concentra atenciones de toda la región."
            : `Alza o baja solo cuando el nivel reciente queda fuera del intervalo del pronóstico; el resto cabe en el ruido semanal. Hoy: ${alzas} en alza y ${bajas} en baja.`}
          {" "}Clic en una comuna para ver su serie.
        </p>
      </div>
    </section>
  );
}
