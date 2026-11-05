import type { EstadoProceso } from "../api";
import { fmtFechaLarga } from "../format";
import { RUTA_ESTABLECIMIENTOS, RUTA_TABLERO } from "../ruta";

export type Vista = "comunas" | "establecimientos";

interface Props {
  /** Ultima semana completa con datos; la fecha es opcional mientras carga. */
  ultima: { ano: number; semana: number; fecha_inicio?: string | null } | null;
  estadoPronostico: EstadoProceso;
  vista: Vista;
}

const ESTADO: Record<EstadoProceso, string> = {
  pendiente: "Pronóstico en espera",
  calculando: "Calculando pronóstico…",
  listo: "Pronóstico al día",
  error: "Pronóstico no disponible",
};

// Dos niveles del mismo modelo, no dos productos: el territorio (region y
// comunas) y, dentro de el, cada establecimiento de urgencia.
const VISTAS: { vista: Vista; etiqueta: string; href: string }[] = [
  { vista: "comunas", etiqueta: "Por comuna", href: RUTA_TABLERO },
  { vista: "establecimientos", etiqueta: "Por establecimiento", href: RUTA_ESTABLECIMIENTOS },
];

// Identidad del producto y frescura del dato: lo primero que un planificador
// necesita saber es hasta cuando llegan los datos. Ambas vistas la muestran igual.
export function BarraSuperior({ ultima, estadoPronostico, vista }: Props) {
  return (
    <header className="border-b" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2.5 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          {/* El logo vuelve a la pagina de entrada: es el camino de regreso esperado. */}
          <a href="#/" aria-label="Ir al inicio" className="shrink-0">
            <img src="/marca/saad-logo.svg" alt="SAAD" className="h-6 w-auto" />
          </a>
          <h1 className="min-w-0 text-[17px] font-semibold tracking-tight">
            Red de urgencia en salud mental
            <span className="text-2 hidden font-normal sm:inline"> · Región Metropolitana</span>
          </h1>
        </div>
        <nav aria-label="Vistas" className="segmented order-last w-full sm:order-none sm:w-auto">
          {VISTAS.map((v) => (
            <a
              key={v.vista}
              href={v.href}
              aria-current={vista === v.vista ? "page" : undefined}
              className="flex-1 text-center sm:flex-none"
            >
              {v.etiqueta}
            </a>
          ))}
        </nav>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] num text-2 sm:ml-auto">
          {ultima ? (
            <span>
              Datos hasta la semana {ultima.semana} de {ultima.ano}
              {ultima.fecha_inicio && (
                <span className="text-3"> (desde el {fmtFechaLarga(ultima.fecha_inicio)})</span>
              )}
            </span>
          ) : (
            <span className="skeleton inline-block h-4 w-56" aria-hidden />
          )}
          <span className="inline-flex items-center gap-1.5" role="status">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{
                background:
                  estadoPronostico === "listo" ? "var(--accent)"
                    : estadoPronostico === "error" ? "var(--alza)" : "var(--muted)",
              }}
            />
            {ESTADO[estadoPronostico]}
          </span>
        </div>
      </div>
    </header>
  );
}
