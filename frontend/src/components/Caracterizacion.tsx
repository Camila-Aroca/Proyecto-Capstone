import { useEffect, useState } from "react";
import { api, type BarraCaracterizacion, type Caracterizacion as Datos, type SerieConPronostico } from "../api";
import { fmtEntero, fmtFechaLarga } from "../format";

function colorSexo(etiqueta: string) {
  const sexo = etiqueta.toLocaleLowerCase("es");
  return sexo.startsWith("mujer") ? "var(--sexo-mujer)"
    : sexo.startsWith("hombre") ? "var(--sexo-hombre)" : "var(--muted)";
}

export function TortaSexo({ titulo, datos, total }: {
  titulo: string; datos: BarraCaracterizacion[]; total: number;
}) {
  // Porcion bajo el mouse: su detalle se lee en el centro del donut (sin tooltip nativo).
  const [activa, setActiva] = useState<string | null>(null);
  let acumulado = 0;
  const porciones = datos.map((dato) => {
    const fraccion = total > 0 ? dato.valor / total : 0;
    const inicio = acumulado * 2 * Math.PI - Math.PI / 2;
    acumulado += fraccion;
    const fin = acumulado * 2 * Math.PI - Math.PI / 2;
    const medio = (inicio + fin) / 2;
    return {
      ...dato, fraccion, inicio, fin,
      etiquetaX: 140 + 85 * Math.cos(medio),
      etiquetaY: 130 + 85 * Math.sin(medio),
    };
  });
  const porcentaje = (valor: number) => `${(total > 0 ? valor / total * 100 : 0).toLocaleString("es-CL", { maximumFractionDigits: 1 })}%`;
  const elegida = porciones.find((p) => p.etiqueta === activa && p.valor > 0);
  return <figure className="min-w-0">
    <figcaption className="mb-3 text-[13px] font-medium">{titulo}</figcaption>
    <ul className="mb-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-2" aria-label={`${titulo}: leyenda y valores`}>
      {porciones.map((p) => <li key={p.etiqueta} className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: colorSexo(p.etiqueta) }} aria-hidden />
        <span>{p.etiqueta}<span className={p.fraccion >= 0.08 ? "sr-only" : "num text-3"}>: {fmtEntero(p.valor)} ({porcentaje(p.valor)})</span></span>
      </li>)}
    </ul>
    {total > 0 ? <svg viewBox="0 0 280 260" className="mx-auto block w-full max-w-[224px]" role="img" aria-label={`${titulo}. ${datos.map((p) => `${p.etiqueta}: ${fmtEntero(p.valor)}, ${porcentaje(p.valor)}`).join("; ")}`}>
      <circle cx="140" cy="130" r="116" fill="none" stroke="var(--border)" strokeWidth="1" />
      {porciones.filter((p) => p.valor > 0).map((p) => <g key={p.etiqueta} onMouseEnter={() => setActiva(p.etiqueta)} onMouseLeave={() => setActiva(null)}
        opacity={activa && activa !== p.etiqueta ? 0.5 : 1} style={{ transition: "opacity 150ms var(--ease-out)" }}>
        {p.fraccion === 1 ? <circle cx="140" cy="130" r="116" fill={colorSexo(p.etiqueta)} />
          : <path d={`M 140 130 L ${140 + 116 * Math.cos(p.inicio)} ${130 + 116 * Math.sin(p.inicio)} A 116 116 0 ${p.fraccion > 0.5 ? 1 : 0} 1 ${140 + 116 * Math.cos(p.fin)} ${130 + 116 * Math.sin(p.fin)} Z`} fill={colorSexo(p.etiqueta)} stroke="var(--surface)" strokeWidth="2" />}
        {p.fraccion >= 0.08 && <text x={p.etiquetaX} y={p.etiquetaY} textAnchor="middle" className="num" fontFamily="monospace" fill="var(--sexo-etiqueta)" fontSize="14" fontWeight="400">
          <tspan x={p.etiquetaX} dy="-2">{porcentaje(p.valor)}</tspan>
          <tspan x={p.etiquetaX} dy="16" fontSize="11" fillOpacity="0.8">{fmtEntero(p.valor)}</tspan>
        </text>}
      </g>)}
      <circle cx="140" cy="130" r="54" fill="var(--surface)" />
      {elegida ? <>
        <text x="140" y="114" textAnchor="middle" fill="var(--ink-3)" fontSize="11">{elegida.etiqueta}</text>
        <text x="140" y="136" textAnchor="middle" fill="var(--ink)" className="num" fontFamily="monospace" fontSize="23" fontWeight="300">{fmtEntero(elegida.valor)}</text>
        <text x="140" y="153" textAnchor="middle" fill="var(--ink-3)" fontSize="11">{porcentaje(elegida.valor)} del total</text>
      </> : <>
        <text x="140" y="128" textAnchor="middle" fill="var(--ink)" className="num" fontFamily="monospace" fontSize="23" fontWeight="300">{fmtEntero(total)}</text>
        <text x="140" y="147" textAnchor="middle" fill="var(--ink-3)" fontSize="11">eventos</text>
      </>}
    </svg> : <p className="py-6 text-[12px] text-3">Sin eventos para representar.</p>}
  </figure>;
}

/** Barras desde cero con etiquetas persistentes: también constituyen la tabla accesible. */
function Barras({ titulo, datos, total, sexo = false }: {
  titulo: string; datos: BarraCaracterizacion[]; total: number; sexo?: boolean;
}) {
  return <figure className="min-w-0">
    <figcaption className="mb-3 text-[13px] font-medium">{titulo}</figcaption>
    <table className="w-full table-fixed text-[12px] num">
      <caption className="sr-only">{titulo}: número de eventos y porcentaje del total</caption>
      <colgroup><col className="w-28" /><col /><col className="w-28" /></colgroup>
      <thead className="sr-only"><tr><th scope="col">Grupo</th><th scope="col">Distribución</th><th scope="col">Eventos y porcentaje</th></tr></thead>
      <tbody>{datos.map((d) => <tr key={d.etiqueta}>
        <th scope="row" className="py-2 pr-2 text-left font-normal text-2">
          <span className="mr-1.5 inline-block h-2 w-2 rounded-sm" style={{ background: sexo ? colorSexo(d.etiqueta) : "var(--series-1)" }} aria-hidden />
          {d.etiqueta}
        </th>
        <td aria-hidden><div className="h-3 overflow-hidden rounded-sm bg-[var(--surface-2)]">
          <div className="h-full rounded-sm" style={{ width: `${total ? d.valor / total * 100 : 0}%`, background: sexo ? colorSexo(d.etiqueta) : "var(--series-1)" }} />
        </div></td>
        <td className="whitespace-nowrap py-2 pl-3 text-right">
          {fmtEntero(d.valor)} <span className="text-3">({total ? (100 * d.valor / total).toLocaleString("es-CL", { maximumFractionDigits: 1 }) : "0"}%)</span>
        </td>
      </tr>)}</tbody>
    </table>
    <p className="mt-2 text-[11px] text-3">Barras: porcentaje del total · etiquetas: eventos y %</p>
  </figure>;
}

export function Caracterizacion({ serie, fuente = "urgencias" }: {
  serie: SerieConPronostico; fuente?: "urgencias" | "hospitalizaciones" | "suicidios";
}) {
  const [abierto, setAbierto] = useState(false);
  const [explorar, setExplorar] = useState(false);
  const [respuesta, setRespuesta] = useState<{ clave: string; datos?: Datos; error?: string } | null>(null);
  const semanas = serie.historico.map((p) => `${p.ano}-${p.semana}`).join(",");
  const clave = `${fuente}/${serie.nivel}/${serie.series_id}/${semanas}`;
  const total = serie.historico.reduce((s, p) => s + p.atenciones, 0);
  useEffect(() => {
    setExplorar(false);
    if (!abierto || !semanas) return;
    const control = new AbortController();
    api.caracterizacion(fuente, serie.nivel, serie.series_id, semanas, control.signal)
      .then((datos) => setRespuesta({ clave, datos }))
      .catch((e) => { if (!control.signal.aborted) setRespuesta({ clave, error: e.message }); });
    return () => control.abort();
  }, [abierto, clave, fuente, serie.nivel, serie.series_id, semanas]);
  const datos = respuesta?.clave === clave ? respuesta.datos : undefined;
  const error = respuesta?.clave === clave ? respuesta.error : undefined;
  const concilia = datos && datos.total === total
    && datos.edad.reduce((s, p) => s + p.valor, 0) === total
    && (datos.sexo == null || datos.sexo.reduce((s, p) => s + p.valor, 0) === total)
    && (datos.escenario == null || datos.escenario.sexo.reduce((s, p) => s + p.valor, 0) === total);
  return <details className="mt-2 border-t border-[var(--border)] pt-3" onToggle={(e) => setAbierto(e.currentTarget.open)}>
    <summary className="cursor-pointer text-[13px] text-2 select-none">Ver caracterización por género y edad</summary>
    {abierto && <div className="mt-4">
      {!semanas ? <p className="text-[13px] text-3">Sin semanas observadas en esta ventana.</p>
        : error ? <p role="status" className="text-[13px] text-3">No se pudo cargar la caracterización: {error}</p>
        : !datos ? <p role="status" className="text-[13px] text-3">Cargando caracterización…</p>
        : !concilia ? <p role="status" className="text-[13px] text-3">La fuente y el gráfico no coinciden. Actualice los datos antes de consultar el desglose.</p>
        : <>
          <p className="mb-4 text-[12px] text-3">{serie.nombre} · {fmtFechaLarga(datos.desde)} al {fmtFechaLarga(datos.hasta)} · <strong className="text-2">{fmtEntero(total)} eventos observados</strong></p>
          {total === 0 && <p className="mb-3 text-[13px] text-3">Sin eventos registrados en estas semanas.</p>}
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              {datos.sexo ? <TortaSexo titulo="Sexo registrado" datos={datos.sexo} total={total} /> : <>
                <h4 className="text-[13px] font-medium">Sexo</h4>
                <p className="mt-2 text-[12px] text-3">Urgencias no registra sexo. Los datos disponibles no miden identidad de género.</p>
                {datos.escenario && <>
                  <label className="mt-3 flex cursor-pointer items-start gap-2 text-[12px] text-2">
                    <input type="checkbox" checked={explorar} onChange={(e) => setExplorar(e.target.checked)} className="mt-0.5 accent-[var(--accent)]" />
                    Explorar un reparto hipotético con referencia nacional
                  </label>
                  {explorar && <div className="mt-4 border-l-2 border-[var(--border)] pl-3">
                    <TortaSexo titulo="Escenario por sexo · no observado" datos={datos.escenario.sexo} total={total} />
                    <p className="mt-3 text-[12px] text-3">{datos.escenario.fuente}, {datos.escenario.ano_referencia}: {datos.escenario.referencia.map((d) => `${d.etiqueta}: ${fmtEntero(d.valor)}`).join(" · ")}.</p>
                    <p className="mt-1 text-[12px] text-3">{datos.escenario.metodo} {datos.escenario.advertencia}</p>
                  </div>}
                </>}
              </>}
            </div>
            <Barras titulo="Edad registrada · grupos publicados" datos={datos.edad} total={total} />
          </div>
          {datos.sexo && <p className="mt-3 text-[11px] text-3">La fuente registra sexo, no identidad de género. «Sin dato» conserva los registros sin edad o sexo interpretable.</p>}
        </>}
    </div>}
  </details>;
}
