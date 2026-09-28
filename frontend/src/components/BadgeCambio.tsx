import type { CambioEsperado } from "../api";
import { CAMBIO } from "../tokens";

interface Props {
  cambio: CambioEsperado;
  titulo?: string;
  /** Etiqueta corta para columnas estrechas. */
  compacto?: boolean;
}

// Etiquetas cortas para columnas estrechas (la tabla comunal).
const CORTA: Partial<Record<CambioEsperado, string>> = { estable: "Estable", sin_pronostico: "Sin dato" };

// Distintivo del cambio esperado: el icono y la palabra cargan el significado,
// el color solo lo refuerza.
export function BadgeCambio({ cambio, titulo, compacto = false }: Props) {
  const { icono } = CAMBIO[cambio];
  const etiqueta = (compacto && CORTA[cambio]) || CAMBIO[cambio].etiqueta;
  return (
    <span className={`badge badge-${cambio}`} title={titulo}>
      <span className="badge-icon" aria-hidden>{icono}</span>
      {etiqueta}
    </span>
  );
}
