// Suicidios semanales del territorio seleccionado, dentro del mismo panel que las
// atenciones: misma anatomia (frase, cifras clave, grafico, tabla) y las mismas semanas
// en el eje x, pero su propio eje y (nunca en el de las atenciones). Burdeos y no rojo:
// el rojo ya significa "alza".
import { useMemo, useState } from "react";
import type { CategoriaEvento, EventoCalendario, SerieConPronostico, SerieSuicidios } from "../api";
import { fmtDecimal, fmtEntero, fmtFechaLarga, fmtMedia, fmtPct } from "../format";
import type { Token, Tokens } from "../tokens";
import { fechasMarca, type MarcaTemporal } from "./MarcasTemporales";
import { GraficoSerie, LeyendaSerie, TablaSerie, type SemanaEje } from "./GraficoSerie";
import { Caracterizacion } from "./Caracterizacion";

interface Props {
  suicidios: SerieSuicidios | null;
  /** Mensaje si la API no pudo entregar el pronostico (p. ej., desactualizado). */
  error: string | null;
  tokens: Tokens;
  /**
   * Semanas del grafico de atenciones: este grafico usa exactamente ese eje x. Null
   * mientras ese grafico carga (para no saltar de eje); undefined, eje propio.
   */
  eje?: SemanaEje[] | null;
  /** Festividades y estaciones del calendario de contexto (ya filtradas por fecha en la API). */
  eventos?: EventoCalendario[];
}

// Color de cada marca: las estaciones por nombre, las festividades con un solo tono neutro.
const TOKEN_ESTACION: Record<string, Token> = {
  Verano: "marca-verano", "Otoño": "marca-otono", Invierno: "marca-invierno", Primavera: "marca-primavera",
};
const CATEGORIAS: { id: CategoriaEvento; etiqueta: string }[] = [
  { id: "festividad", etiqueta: "Festividades" },
  { id: "estacion", etiqueta: "Estaciones" },
];
const ORDEN_ESTACIONES = ["Verano", "Otoño", "Invierno", "Primavera"];

const SEMANAS_ANO = 52;

const promedio = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);

// El grafico y la tabla son genericos sobre la forma de la serie de atenciones. Con
// eje, la serie se recorta a sus semanas: grafico, tabla y cifras muestran lo mismo.
function comoSerie(s: SerieSuicidios, eje?: SemanaEje[] | null): SerieConPronostico {
  const fechas = eje ? new Set(eje.map((e) => e.fecha)) : null;
  const dentro = (fecha: string | null) => !fechas || (fecha != null && fechas.has(fecha));
  return {
    series_id: s.series_id,
    nombre: s.nombre,
    nivel: s.nivel,
    historico: s.historico
      .filter((p) => dentro(p.fecha_inicio))
      .map((p) => ({ ano: p.ano, semana: p.semana, fecha_inicio: p.fecha_inicio, atenciones: p.suicidios })),
    pronostico: s.pronostico.filter((p) => dentro(p.fecha_inicio)),
    estado_pronostico: "listo",
  };
}

export function BloqueSuicidios({ suicidios, error, tokens, eje, eventos = [] }: Props) {
  const [categoriasVisibles, setCategoriasVisibles] = useState<Record<CategoriaEvento, boolean>>({ festividad: true, estacion: true });
  const color = tokens.suicidios;
  const banda = tokens["band-suicidios"];
  const intervalo = suicidios ? `${Math.round(suicidios.nivel_intervalo * 100)}%` : "";
  const alineada = useMemo(
    () => (suicidios && eje !== null ? comoSerie(suicidios, eje) : null),
    [suicidios, eje],
  );
  // Los puntos originales (con su cobertura declarada) de los horizontes que caben en el eje.
  const visibles = new Set((alineada?.pronostico ?? []).map((p) => p.horizonte));
  const pronostico = (suicidios?.pronostico ?? []).filter((p) => visibles.has(p.horizonte));
  // Marcas del periodo del eje (desde su primera semana hasta el fin de la ultima).
  const marcasPeriodo = useMemo<MarcaTemporal[]>(() => {
    const fechas = (eje ?? []).map((e) => e.fecha).filter(Boolean).sort();
    if (!fechas.length) return [];
    const desde = fechas[0];
    const hasta = new Date(new Date(fechas[fechas.length - 1]).getTime() + 6 * 86_400_000).toISOString().slice(0, 10);
    return eventos
      .filter((e) => e.fecha_inicio <= hasta && e.fecha_fin >= desde)
      .map((e) => ({
        id: e.evento_id, nombre: e.nombre, categoria: e.categoria, inicio: e.fecha_inicio, fin: e.fecha_fin,
        detalle: e.detalle,
        color: tokens[e.categoria === "estacion" ? TOKEN_ESTACION[e.nombre] ?? "marca-festividad" : "marca-festividad"],
      }));
  }, [eventos, eje, tokens]);
  const marcas = marcasPeriodo.filter((m) => categoriasVisibles[m.categoria]);
  const primero = pronostico[0];
  const anual = suicidios ? suicidios.suicidios_ultimas_52_semanas / SEMANAS_ANO : null;
  const medio = promedio(pronostico.map((p) => p.pronostico));
  const variacion = anual && medio != null ? (medio / anual - 1) * 100 : null;
  const cobertura = suicidios?.cobertura_holdout;
  const territorio = suicidios ? (suicidios.nivel === "region" ? "la región" : suicidios.nombre) : "";

  return (
    <section className="mt-6 border-t pt-5" style={{ borderColor: "var(--border)" }} aria-labelledby="suicidios-titulo">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <div>
          <h3 id="suicidios-titulo" className="panel-title">Suicidios semanales</h3>
          <p className="text-[13px] text-3">
            Defunciones por lesiones autoinfligidas (CIE-10 X60–X84) de residentes de {territorio || "…"}
          </p>
        </div>
        <LeyendaSerie tokens={tokens} intervalo={intervalo} conParcial={false} color={color} banda={banda} />
      </div>
      {marcasPeriodo.length > 0 && (
        <fieldset className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-2">
          <legend className="sr-only">Marcas de contexto en el gráfico</legend>
          <span className="text-3">Marcas:</span>
          {CATEGORIAS.map((c) => (
            <label key={c.id} className="inline-flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                checked={categoriasVisibles[c.id]}
                onChange={() => setCategoriasVisibles((v) => ({ ...v, [c.id]: !v[c.id] }))}
                className="accent-[var(--accent)]"
              />
              {c.id === "festividad" ? (
                <svg width="14" height="10" aria-hidden>
                  <line x1="7" y1="0" x2="7" y2="10" stroke={tokens["marca-festividad"]} strokeWidth="2" strokeDasharray="3 2" />
                </svg>
              ) : (
                <svg width="34" height="10" aria-hidden>
                  {ORDEN_ESTACIONES.map((nombre, i) => (
                    <rect key={nombre} x={i * 8.5} width="8" height="10" rx="1.5" fill={tokens[TOKEN_ESTACION[nombre]]} fillOpacity="0.55" />
                  ))}
                </svg>
              )}
              {c.etiqueta}
            </label>
          ))}
        </fieldset>
      )}

      {error ? (
        <p role="status" className="mt-3 text-[13px] text-2">El pronóstico de suicidios no está disponible: {error}</p>
      ) : !suicidios || !alineada ? (
        <div className="mt-4 space-y-4" aria-busy="true" aria-label="Cargando suicidios">
          <div className="skeleton h-5 w-2/3" />
          <div className="skeleton h-64 w-full" />
        </div>
      ) : (
        <>
          {primero && (
            <p className="mt-3 max-w-[75ch] text-[15px] leading-relaxed">
              Para la semana del <strong>{fmtFechaLarga(primero.fecha_inicio)}</strong> se esperan en promedio{" "}
              <strong className="num">{fmtMedia(primero.pronostico)} suicidios</strong>
              {primero.limite_inferior === primero.limite_superior ? (
                <>
                  ; el intervalo de {intervalo} es <span className="num">{fmtEntero(primero.limite_inferior)}</span>
                  {primero.cobertura_esperada != null &&
                    ` (el modelo le asigna ${Math.round(primero.cobertura_esperada * 100)}%)`}
                  .
                </>
              ) : (
                <>
                  , entre <span className="num">{fmtEntero(primero.limite_inferior)}</span> y{" "}
                  <span className="num">{fmtEntero(primero.limite_superior)}</span> con un intervalo de {intervalo}.
                </>
              )}
            </p>
          )}

          <dl className="cifras-clave mt-4">
            <div>
              <dt className="text-[12px] text-3">Últimas 52 semanas</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">
                {fmtEntero(suicidios.suicidios_ultimas_52_semanas)}
              </dd>
              <dd className="text-[12px] text-3">
                {suicidios.tasa_anual_por_100000 == null
                  ? "sin población para la tasa"
                  : `${fmtDecimal(suicidios.tasa_anual_por_100000)} por 100.000 hab. al año`}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] text-3">Promedio semanal del último año</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtMedia(anual)}</dd>
              <dd className="text-[12px] text-3">suicidios por semana</dd>
            </div>
            <div>
              <dt className="text-[12px] text-3">
                Pronóstico medio, {pronostico.length ? `${pronostico[0].horizonte} a ${pronostico[pronostico.length - 1].horizonte} semanas` : ""}
              </dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtMedia(medio)}</dd>
              <dd className="text-[12px] text-3 num">
                {suicidios.nivel === "region"
                  ? `${fmtPct(variacion)} frente al promedio del último año`
                  : "suicidios por semana (tasa esperada)"}
              </dd>
            </div>
            {cobertura && (
              <div>
                <dt className="text-[12px] text-3">Confiabilidad del intervalo</dt>
                <dd className="mt-0.5 text-xl font-semibold tracking-tight">{Math.round(cobertura.observada * 100)}%</dd>
                <dd className="text-[12px] text-3">
                  {suicidios.nivel === "region" ? "cubrió" : "cubrió en las comunas"} fuera de muestra (el modelo
                  declaró {Math.round(cobertura.esperada * 100)}%)
                </dd>
              </div>
            )}
          </dl>

          <div className="mt-5">
            <GraficoSerie
              serie={alineada}
              tokens={tokens}
              intervalo={intervalo}
              unidad="suicidios"
              color={color}
              banda={banda}
              decimales
              eje={eje}
              marcas={marcas}
            />
            <TablaSerie serie={alineada} intervalo={intervalo} unidad="suicidios" decimales />
            <Caracterizacion serie={alineada} fuente="suicidios" />
            {marcasPeriodo.length > 0 && (
              <details className="mt-2 border-t border-[var(--border)] pt-3">
                <summary className="cursor-pointer text-[13px] text-2 select-none">Ver las fechas marcadas</summary>
                <ul className="mt-2 max-h-60 space-y-1 overflow-auto text-[12px] text-2 num">
                  {marcasPeriodo.map((m) => (
                    <li key={m.id} className="flex items-start gap-2">
                      <svg width="10" height="14" className="mt-0.5 shrink-0" aria-hidden>
                        <line x1="5" y1="0" x2="5" y2="14" stroke={m.color} strokeWidth="2"
                          strokeDasharray={m.categoria === "festividad" ? "3 2" : undefined} />
                      </svg>
                      <span>
                        <span className="font-medium text-[var(--ink)]">{m.nombre}</span> ({fechasMarca(m)}). {m.detalle}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-[12px] text-3">
                  Son contexto para leer la serie: que una variación coincida con una fecha no indica que la cause.
                  Las estaciones se calculan desde el equinoccio o solsticio en hora de Chile.
                </p>
              </details>
            )}
          </div>

          <div className="mt-3 max-w-[90ch] space-y-1 text-[12px] text-3">
            <p>
              Si usted o alguien cercano está en riesgo, llame a la línea de prevención del suicidio{" "}
              <strong className="text-2">*4141</strong>, gratuita y disponible las 24 horas.
            </p>
          </div>
        </>
      )}
    </section>
  );
}
