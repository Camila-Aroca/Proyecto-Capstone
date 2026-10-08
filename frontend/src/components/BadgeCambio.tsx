import type { CambioEsperado } from "../api";
import { CAMBIO } from "../tokens";

interface Props {
  cambio: CambioEsperado;
  /**
   * Si el cambio queda fuera del intervalo del pronostico. Es la segunda etiqueta:
   * `cambio` dice cuanto se mueve, esta dice si ese movimiento se distingue de la
   * fluctuacion semanal. `null` o ausente cuando no aplica.
   */
  fueraDelIntervalo?: boolean | null;
  titulo?: string;
  /** Etiqueta corta para columnas estrechas. */
  compacto?: boolean;
}

// Etiquetas cortas para columnas estrechas (la tabla comunal).
const CORTA: Partial<Record<CambioEsperado, string>> = { estable: "Estable", sin_pronostico: "Sin dato" };

const AYUDA_RUIDO =
  "El cambio es compatible con la fluctuación semanal: queda dentro del intervalo del pronóstico.";
const AYUDA_SENAL =
  "El cambio se distingue de la fluctuación semanal: queda fuera del intervalo del pronóstico.";

// Distintivo del cambio esperado: el icono y la palabra cargan el significado,
// el color solo lo refuerza. Cuando el movimiento no se distingue del ruido se
// marca con "≈" y se atenua, en vez de ocultarlo o presentarlo como senal.
export function BadgeCambio({ cambio, fueraDelIntervalo, titulo, compacto = false }: Props) {
  const { icono } = CAMBIO[cambio];
  const etiqueta = (compacto && CORTA[cambio]) || CAMBIO[cambio].etiqueta;
  const seMueve = cambio === "alza" || cambio === "baja";
  const dentroDelRuido = seMueve && fueraDelIntervalo === false;
  const ayuda = titulo ?? (seMueve && fueraDelIntervalo != null
    ? (fueraDelIntervalo ? AYUDA_SENAL : AYUDA_RUIDO)
    : undefined);

  return (
    <span className={`badge badge-${cambio}${dentroDelRuido ? " badge-ruido" : ""}`} title={ayuda}>
      <span className="badge-icon" aria-hidden>{icono}</span>
      {etiqueta}
      {dentroDelRuido && (
        <>
          <span aria-hidden className="badge-ruido-marca">≈</span>
          <span className="sr-only">, dentro de la fluctuación semanal</span>
        </>
      )}
    </span>
  );
}
