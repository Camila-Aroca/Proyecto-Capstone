import type { EstadoProceso, Meta } from "../api";
import { fmtFechaLarga } from "../format";

interface Props {
  meta: Meta | null;
  estadoPronostico: EstadoProceso;
}

const ESTADO: Record<EstadoProceso, string> = {
  pendiente: "Pronóstico en espera",
  calculando: "Calculando pronóstico…",
  listo: "Pronóstico al día",
  error: "Pronóstico no disponible",
};

// Identidad del producto y frescura del dato: lo primero que un planificador
// necesita saber es hasta cuando llegan los datos.
export function BarraSuperior({ meta, estadoPronostico }: Props) {
  const ultima = meta?.ultima_semana_observada;
  return (
    <header className="border-b" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <div className="flex items-baseline gap-3">
          <span className="text-base font-bold tracking-tight" style={{ color: "var(--accent-ink)" }}>SAAD</span>
          <h1 className="text-[15px] font-semibold tracking-tight">
            Demanda de urgencia en salud mental
            <span className="text-2 font-normal"> · Región Metropolitana</span>
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] num text-2">
          {ultima ? (
            <span>
              Datos hasta la semana {ultima.semana} de {ultima.ano}
              <span className="text-3"> (desde el {fmtFechaLarga(ultima.fecha_inicio)})</span>
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
