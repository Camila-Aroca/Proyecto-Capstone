// Tooltip propio de la pagina. Reemplaza el atributo `title` del navegador, cuyo recuadro
// no se puede estilar y rompe la estetica: mismo panel (12 px) que los tooltips de los
// graficos. Muestra lo mismo con el mouse encima que con foco de teclado (:focus-visible,
// de modo que el foco que deja un clic no lo mantiene abierto). Sin texto, deja pasar a su
// hijo tal cual.
//
// Fluidez: entra con un fundido y un desplazamiento de 2 px. Con mouse espera 75 ms para no
// parpadear al barrer una fila de encabezados; con teclado aparece sin espera. Con
// "reducir movimiento" no hay transicion. No captura el puntero, asi que nunca tapa un clic.
import { useId, type ReactNode } from "react";

interface Props {
  texto?: string | null;
  /** Borde del hijo al que se ancla el panel: "derecha" en columnas pegadas al borde derecho. */
  lado?: "izquierda" | "derecha";
  children: ReactNode;
}

const PANEL = "panel pointer-events-none absolute top-full z-20 mt-1 w-max max-w-64 whitespace-normal px-3 py-2 text-left text-[12px] font-normal leading-snug text-(--ink) shadow-sm";
// Oculto con display:none y no con visibility: un panel invisible igual ensancha la pagina
// cuando su ancla esta cerca del borde derecho (desborde horizontal en pantallas angostas).
const OCULTO = "hidden translate-y-0.5 opacity-0 transition-[opacity,translate,display] transition-discrete duration-150 ease-out motion-reduce:transition-none";
const ABIERTO_MOUSE = "group-hover/tip:block group-hover/tip:translate-y-0 group-hover/tip:opacity-100 group-hover/tip:delay-75 group-hover/tip:starting:translate-y-0.5 group-hover/tip:starting:opacity-0";
const ABIERTO_TECLADO = "group-has-focus-visible/tip:block group-has-focus-visible/tip:translate-y-0 group-has-focus-visible/tip:opacity-100 group-has-focus-visible/tip:starting:translate-y-0.5 group-has-focus-visible/tip:starting:opacity-0";

export function Tip({ texto, lado = "izquierda", children }: Props) {
  const id = useId();
  if (!texto) return <>{children}</>;
  return (
    <span className="group/tip relative inline-flex" aria-describedby={id}>
      {children}
      <span id={id} role="tooltip"
        className={`${PANEL} ${OCULTO} ${ABIERTO_MOUSE} ${ABIERTO_TECLADO} ${lado === "derecha" ? "right-0" : "left-0"}`}>
        {texto}
      </span>
    </span>
  );
}
