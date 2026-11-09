// Hospitalizaciones por salud mental de quienes viven en el territorio (egresos
// F00-F99, anual). Complementa la serie de urgencias: aquella cuenta donde se
// atiende la persona; esta, donde vive. Para la region suma el contraste de camas
// entre dos fuentes independientes (Egresos y REM-20).
import { useEffect, useState } from "react";
import { api, type CategoriaEgresos, type HospitalizacionesResidentes } from "../api";
import { fmtDecimal, fmtEntero } from "../format";
import { Tip } from "./Tip";

const DIMENSIONES: { clave: "grupo_diagnostico" | "grupo_edad" | "sexo" | "prevision"; titulo: string }[] = [
  { clave: "grupo_diagnostico", titulo: "Diagnóstico principal" },
  { clave: "grupo_edad", titulo: "Edad" },
  { clave: "sexo", titulo: "Sexo" },
  { clave: "prevision", titulo: "Previsión" },
];

const fmtProporcion = (v: number | null | undefined) => (v == null ? "—" : `${fmtDecimal(v * 100)}%`);
// La razon entre fuentes vive cerca de 1: con un decimal 0,95 y 1,04 se verian iguales.
const fmtRazon = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Una serie, un tono: la tasa anual en columnas finas. Un año sin poblacion se
// marca "sin dato" en lugar de dibujar una columna en cero.
function SerieAnual({ datos }: { datos: HospitalizacionesResidentes["anual"] }) {
  const maximo = Math.max(...datos.map((d) => d.tasa_por_10000 ?? 0), 1);
  return (
    <div>
      <p className="text-[12px] text-3">Egresos por 10.000 habitantes, por año</p>
      <div className="mt-2 flex h-36 items-end gap-2" role="img"
        aria-label={`Tasa anual: ${datos.map((d) => `${d.ano} ${d.tasa_por_10000 == null ? "sin dato" : fmtDecimal(d.tasa_por_10000)}`).join(", ")}`}>
        {datos.map((d) => (
          <Tip key={d.ano} texto={`${d.ano}: ${fmtEntero(d.egresos)} egresos${d.tasa_por_10000 == null ? "; sin población proyectada para la tasa" : `, ${fmtDecimal(d.tasa_por_10000)} por 10.000 hab.`}`}>
            <div tabIndex={0} className="flex h-36 w-10 flex-col items-center justify-end gap-1 sm:w-12">
              <span className="text-[11px] num text-2">{d.tasa_por_10000 == null ? "s/d" : fmtDecimal(d.tasa_por_10000)}</span>
              {d.tasa_por_10000 == null ? (
                <span className="h-1 w-full rounded-sm border border-dashed" style={{ borderColor: "var(--border-strong)" }} />
              ) : (
                <span
                  className="w-full rounded-t"
                  style={{ height: `${Math.max((d.tasa_por_10000 / maximo) * 100, 2)}px`, background: "var(--series-1)" }}
                />
              )}
              <span className="text-[11px] num text-3">{d.ano}</span>
            </div>
          </Tip>
        ))}
      </div>
    </div>
  );
}

function Barras({ titulo, categorias }: { titulo: string; categorias: CategoriaEgresos[] }) {
  const maximo = Math.max(...categorias.map((c) => c.proporcion ?? 0), 0.0001);
  return (
    <div>
      <h4 className="text-[13px] font-semibold">{titulo}</h4>
      <ul className="mt-2 space-y-1.5">
        {categorias.map((c) => (
          <li key={c.categoria} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 text-[12px]">
            <span className="min-w-0 text-2">{c.categoria}</span>
            <span className="num text-2">{fmtProporcion(c.proporcion)}</span>
            <span className="col-span-2 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--grid)" }} aria-hidden>
              <span
                className="block h-full rounded-full"
                style={{ width: `${((c.proporcion ?? 0) / maximo) * 100}%`, background: "var(--series-1)" }}
              />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ContrasteCamas({ filas }: { filas: NonNullable<HospitalizacionesResidentes["contraste_camas"]> }) {
  const ultima = filas[filas.length - 1];
  return (
    <div className="mt-6 border-t pt-5" style={{ borderColor: "var(--border)" }}>
      <h3 className="text-[15px] font-semibold">Camas de psiquiatría ocupadas: dos fuentes, la misma escala</h3>
      <p className="mt-1 max-w-[80ch] text-[13px] text-2">
        Los días de estada de estos egresos equivalen, en {ultima.ano}, a{" "}
        <strong className="num">{fmtEntero(ultima.camas_equivalentes_egresos_snss)} camas ocupadas</strong> en
        hospitales del SNSS; la estadística hospitalaria (REM-20) registra{" "}
        <strong className="num">{fmtEntero(ultima.camas_ocupadas_rem20_sin_forense)}</strong> en las áreas de
        psiquiatría sin contar las forenses. Dos fuentes independientes llegan a la misma escala, lo que respalda la
        base de la propuesta de camas por área.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-[13px] num">
          <caption className="sr-only">Camas ocupadas en promedio por año según Egresos y según REM-20</caption>
          <thead>
            <tr className="text-left text-[12px] text-3">
              <th scope="col" className="px-2.5 py-1.5 font-medium">Año</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Egresos, SNSS</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">REM-20 sin forense</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Razón</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">Egresos, todos</th>
              <th scope="col" className="px-2.5 py-1.5 text-right font-medium">REM-20, todas</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.ano} className="border-t" style={{ borderColor: "var(--grid)" }}>
                <td className="px-2.5 py-1.5">{f.ano}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtEntero(f.camas_equivalentes_egresos_snss)}</td>
                <td className="px-2.5 py-1.5 text-right">{fmtEntero(f.camas_ocupadas_rem20_sin_forense)}</td>
                <td className="px-2.5 py-1.5 text-right font-medium">{fmtRazon.format(f.razon_egresos_snss_rem20_sin_forense)}</td>
                <td className="px-2.5 py-1.5 text-right text-3">{fmtEntero(f.camas_equivalentes_egresos)}</td>
                <td className="px-2.5 py-1.5 text-right text-3">{fmtEntero(f.camas_ocupadas_rem20)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="mt-2 text-[12px] text-3">
        <summary className="cursor-pointer">Por qué no coinciden exactamente</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Egresos solo publica el año: cada estadía aporta como máximo 365 días al año del egreso (cota superior).</li>
          <li>Egresos incluye diagnósticos psiquiátricos atendidos en camas no psiquiátricas (por ejemplo, delirium en medicina) y, en la columna «todos», hospitales privados.</li>
          <li>REM-20 incluye las áreas forenses, cuyos pacientes rara vez egresan dentro del año; por eso se compara sin ellas.</li>
          <li>Egresos ubica al paciente por residencia y REM-20 por hospital: la RM recibe pacientes de otras regiones.</li>
        </ul>
      </details>
    </div>
  );
}

export function PanelHospitalizaciones({ seriesId }: { seriesId: string }) {
  const [datos, setDatos] = useState<HospitalizacionesResidentes | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const control = new AbortController();
    setDatos(null);
    setError(null);
    api.hospitalizacionesResidentes(seriesId, control.signal)
      .then(setDatos)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => control.abort();
  }, [seriesId]);

  // Capa de contexto: si falta el output, el tablero sigue sin este panel.
  if (error) return null;

  const ultimo = datos?.anual.find((a) => a.ano === datos.ano_desglose);
  const previo = datos?.anual.find((a) => a.ano === (datos?.ano_desglose ?? 0) - 1);
  const cambio = ultimo?.tasa_por_10000 != null && previo?.tasa_por_10000
    ? (ultimo.tasa_por_10000 / previo.tasa_por_10000 - 1) * 100 : null;

  return (
    <section className="panel" aria-labelledby="hosp-titulo">
      <div className="panel-header">
        <div>
          <h2 id="hosp-titulo" className="panel-title">
            Hospitalizaciones de quienes viven en {datos ? (datos.nivel === "region" ? `la ${datos.nombre}` : datos.nombre) : "…"}
          </h2>
          <p className="text-[13px] text-3">
            Egresos con diagnóstico principal de salud mental (F00-F99), por comuna de residencia y año · DEIS, Egresos hospitalarios
          </p>
        </div>
      </div>

      {!datos || !ultimo ? (
        <div className="space-y-3 px-5 pb-5" aria-busy="true" aria-label="Cargando hospitalizaciones">
          <div className="skeleton h-12 w-2/3" />
          <div className="skeleton h-36 w-full" />
        </div>
      ) : (
        <div className="px-5 pb-5">
          <dl className="cifras-clave">
            <div>
              <dt className="text-[12px] text-3">Egresos, {ultimo.ano}</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtEntero(ultimo.egresos)}</dd>
              <dd className="text-[12px] text-3">eventos, no personas</dd>
            </div>
            <div>
              <dt className="text-[12px] text-3">Por 10.000 habitantes</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtDecimal(ultimo.tasa_por_10000)}</dd>
              <dd className="text-[12px] text-3 num">
                {cambio == null ? "sin año previo comparable" : `${cambio > 0 ? "+" : ""}${fmtDecimal(cambio)}% frente a ${ultimo.ano - 1}`}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] text-3">Días de estada</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtDecimal(ultimo.dias_estada_mediana)}</dd>
              <dd className="text-[12px] text-3 num">mediana; 1 de cada 10 supera {fmtEntero(ultimo.dias_estada_p90)}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-3">En hospitales del SNSS</dt>
              <dd className="mt-0.5 text-xl font-semibold tracking-tight num">{fmtProporcion(ultimo.proporcion_snss)}</dd>
              <dd className="text-[12px] text-3">el resto, en clínicas y hospitales privados</dd>
            </div>
          </dl>

          <div className="mt-5 grid gap-x-10 gap-y-6 lg:grid-cols-[auto_minmax(0,1fr)]">
            <SerieAnual datos={datos.anual} />
            <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
              {DIMENSIONES.map(({ clave, titulo }) => {
                const categorias = datos.desglose[clave];
                return categorias?.length
                  ? <Barras key={clave} titulo={`${titulo}, ${datos.ano_desglose}`} categorias={categorias} />
                  : null;
              })}
            </div>
          </div>

          <details className="mt-4 text-[12px] text-3">
            <summary className="cursor-pointer text-2">Cómo leer estas cifras</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {datos.advertencias.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </details>

          {datos.contraste_camas && datos.contraste_camas.length > 0 && <ContrasteCamas filas={datos.contraste_camas} />}
        </div>
      )}
    </section>
  );
}
