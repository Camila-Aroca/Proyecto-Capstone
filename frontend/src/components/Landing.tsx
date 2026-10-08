import { useEffect, useState } from "react";
import { api, type Meta } from "../api";
import { fmtEntero } from "../format";
import { Alcance } from "./Alcance";

// Pagina de entrada. Explica que es la herramienta, para quien, y con que
// evidencia trabaja, antes de llevar al tablero. Las cifras no son adorno: se
// leen de la API en vivo, y si no responde la pagina se muestra igual sin ellas,
// en vez de inventar un numero de ejemplo.

interface Props {
  onEntrar: () => void;
}

const PREGUNTAS = [
  {
    titulo: "¿Dónde se concentra la demanda?",
    detalle:
      "Atenciones de urgencia por salud mental en cada una de las 52 comunas de la región, con su tasa por habitante.",
  },
  {
    titulo: "¿Cuándo podría aumentar la presión?",
    detalle:
      "Proyección semanal con intervalo de predicción, para anticipar refuerzos antes de que la presión ocurra.",
  },
  {
    titulo: "¿Qué territorios exigen atención?",
    detalle:
      "Variación esperada por comuna, cruzada con la oferta de urgencia vigente y la vulnerabilidad socioeconómica.",
  },
];

const PASOS = [
  {
    numero: "1",
    titulo: "Fuentes oficiales",
    detalle:
      "Atenciones de urgencia y egresos del DEIS/MINSAL, población del INE, pobreza comunal Casen y cartografía del Censo 2024. Cada descarga queda registrada con su fecha y su hash.",
  },
  {
    numero: "2",
    titulo: "Pipeline reproducible",
    detalle:
      "Un solo comando normaliza, valida y publica los datos. Ninguna cifra se calcula a mano: si un control de calidad falla, el dato no se publica.",
  },
  {
    numero: "3",
    titulo: "Modelo evaluado, no supuesto",
    detalle:
      "El pronóstico se compara contra un baseline estacional mediante backtesting, y sus intervalos se contrastan con lo que realmente ocurrió fuera de muestra.",
  },
];

function Cifra({ valor, etiqueta, nota }: { valor: string; etiqueta: string; nota?: string }) {
  return (
    <div className="min-w-0">
      {/* Figuras proporcionales: tabular-nums se reserva para columnas que se alinean. */}
      <p className="cifra text-2xl font-extrabold tracking-tight">{valor}</p>
      <p className="mt-0.5 text-[13px] font-medium text-2">{etiqueta}</p>
      {nota && <p className="text-[12px] text-3">{nota}</p>}
    </div>
  );
}

export function Landing({ onEntrar }: Props) {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    // Sin reintentos ni estado de error: la landing debe servir aunque la API
    // no responda; las cifras en vivo son un complemento, no su contenido.
    api.meta().then(setMeta).catch(() => undefined);
  }, []);

  const ultima = meta?.ultima_semana_observada;
  const horizontes = meta?.horizontes ?? [];
  const rango = horizontes.length
    ? `${horizontes[0]} a ${horizontes[horizontes.length - 1]} semanas`
    : "4 a 8 semanas";

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3 py-5">
        <div className="flex items-center gap-2.5">
          <img src="/marca/saad-logo.svg" alt="SAAD" className="h-7 w-auto" />
          <span className="text-[13px] text-3">Región Metropolitana</span>
        </div>
        <button type="button" onClick={onEntrar} className="link-button">
          Ir al tablero
        </button>
      </header>

      <main>
        <section className="border-b py-10 sm:py-14" style={{ borderColor: "var(--border)" }}>
          <p className="text-[13px] font-medium" style={{ color: "var(--accent-ink)" }}>
            Sistema de Análisis y Anticipación de Demanda
          </p>
          <h1 className="mt-2 max-w-[22ch] text-3xl font-semibold tracking-tight sm:text-4xl">
            Anticipar la presión sobre la red de urgencia en salud mental
          </h1>
          <p className="mt-4 max-w-[62ch] text-[15px] text-2">
            La planificación de la red responde cuando la presión ya ocurrió. SAAD proyecta las atenciones
            de urgencia por salud mental de las próximas {rango} en cada comuna de la Región Metropolitana,
            a partir de datos públicos oficiales, para que el refuerzo se decida antes y con evidencia.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button type="button" onClick={onEntrar} className="boton-primario">
              Ver el tablero
            </button>
            <a href="#alcance" className="link-button">
              Qué incluye y qué no
            </a>
          </div>
        </section>

        {ultima && (
          <section
            aria-label="Estado actual de los datos"
            className="grid gap-6 border-b py-7 sm:grid-cols-2 lg:grid-cols-4"
            style={{ borderColor: "var(--border)" }}
          >
            <Cifra
              valor={fmtEntero(ultima.atenciones)}
              etiqueta="Atenciones la última semana observada"
              nota={`Semana ${ultima.semana} de ${ultima.ano}, región completa`}
            />
            <Cifra
              valor={String(meta?.comunas_con_pronostico ?? "—")}
              etiqueta="Comunas con pronóstico"
              nota="De 52; el resto se informa como sin dato, nunca como cero"
            />
            <Cifra
              valor={rango}
              etiqueta="Horizonte de proyección"
              nota={meta?.nivel_intervalo ? `Con intervalo de ${Math.round(meta.nivel_intervalo * 100)}%` : undefined}
            />
            <Cifra
              valor="100%"
              etiqueta="Cifras reproducibles desde código"
              nota="Ningún valor se calcula ni corrige a mano"
            />
          </section>
        )}

        <section aria-labelledby="preguntas-titulo" className="border-b py-10" style={{ borderColor: "var(--border)" }}>
          <h2 id="preguntas-titulo" className="text-xl font-semibold tracking-tight">
            Qué responde
          </h2>
          <div className="mt-6 grid gap-6 md:grid-cols-3">
            {PREGUNTAS.map((p) => (
              <article key={p.titulo}>
                <h3 className="text-[15px] font-semibold">{p.titulo}</h3>
                <p className="mt-1.5 text-[14px] text-2">{p.detalle}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="como-titulo" className="border-b py-10" style={{ borderColor: "var(--border)" }}>
          <h2 id="como-titulo" className="text-xl font-semibold tracking-tight">
            Cómo se construye
          </h2>
          <p className="mt-2 max-w-[62ch] text-[14px] text-2">
            La utilidad de una proyección depende de que se pueda auditar. Estos tres pasos son verificables
            en el repositorio del proyecto.
          </p>
          <ol className="mt-6 grid gap-6 md:grid-cols-3">
            {PASOS.map((paso) => (
              <li key={paso.numero}>
                <span
                  aria-hidden
                  className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[13px] font-semibold"
                  style={{ background: "var(--accent-weak)", color: "var(--accent-ink)" }}
                >
                  {paso.numero}
                </span>
                <h3 className="mt-2.5 text-[15px] font-semibold">{paso.titulo}</h3>
                <p className="mt-1.5 text-[14px] text-2">{paso.detalle}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="alcance" className="py-10">
          <Alcance />
        </section>

        <section className="border-t py-8" style={{ borderColor: "var(--border)" }}>
          <h2 className="text-[15px] font-semibold">Para quién es</h2>
          <p className="mt-2 max-w-[70ch] text-[14px] text-2">
            Equipos de planificación de la red, referentes comunales de salud mental, analistas de servicios
            de salud y jefaturas de urgencia de la Región Metropolitana. No es una herramienta clínica: no
            registra pacientes, no gestiona cupos y no apoya decisiones sobre personas.
          </p>
          <div className="mt-5">
            <button type="button" onClick={onEntrar} className="boton-primario">
              Ver el tablero
            </button>
          </div>
        </section>
      </main>

      <footer className="border-t py-6 text-[12px] text-3" style={{ borderColor: "var(--border)" }}>
        <p className="max-w-[90ch]">
          Fuentes: DEIS/MINSAL (atenciones de urgencia y egresos hospitalarios), INE (proyecciones de población
          y Censo 2024), Ministerio de Desarrollo Social (Casen 2022). Las cifras son atenciones, es decir
          eventos, no personas únicas, y reflejan utilización y oferta instalada, no prevalencia.
        </p>
        <p className="mt-1.5">
          Proyecto de título, Ingeniería en Informática, Duoc UC. Apoyo a la planificación sanitaria
          territorial; no sustituye el juicio profesional.
        </p>
      </footer>
    </div>
  );
}
