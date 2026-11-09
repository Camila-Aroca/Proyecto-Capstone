// Ayuda de la columna "Nivel de colapso": formula de ocupacion y escala de niveles.
// Cada nivel lleva un medidor de barras que crece con la gravedad (solo intensidad,
// sin color: el rojo de la pagina ya significa "alza"). Visible al pasar el mouse o
// con foco de teclado (:focus-visible): el foco que deja un clic para ordenar no la
// mantiene abierta.
import type { NivelColapso } from "../../api";
import { NIVELES } from "./comun";

export const ID_AYUDA_COLAPSO = "ayuda-colapso";

const ESCALA_COLAPSO: { nivel: NivelColapso; rango: string }[] = [
  { nivel: "holgura", rango: "< 85 %" },
  { nivel: "presion", rango: "85–90 %" },
  { nivel: "saturacion", rango: "≥ 90 %" },
  { nivel: "sobre_capacidad", rango: "> 100 % en un área" },
];

export function AyudaColapso() {
  return (
    <span
      id={ID_AYUDA_COLAPSO}
      role="tooltip"
      className="panel pointer-events-none invisible absolute right-0 top-full z-20 mt-1 w-72 whitespace-normal px-3 py-2.5 text-left text-[12px] font-normal text-(--ink) opacity-0 shadow-sm transition-opacity duration-150 group-has-focus-visible:visible group-has-focus-visible:opacity-100 group-hover:visible group-hover:opacity-100"
    >
      <span className="block font-semibold">Ocupación de camas de psiquiatría</span>
      <span className="mt-1.5 flex items-center gap-1.5 num">
        <span aria-hidden className="flex items-center gap-1.5">
          <span>Ocupación =</span>
          <span className="inline-flex flex-col items-center text-center leading-snug">
            <span className="border-b border-current px-1 pb-px">Días cama ocupados</span>
            <span className="px-1 pt-px">Días cama disponibles</span>
          </span>
          <span>× 100</span>
        </span>
        <span className="sr-only">Ocupación igual a días cama ocupados dividido por días cama disponibles, por 100</span>
      </span>
      <span className="block text-3">Día cama: una cama durante un día. Últimos 12 meses publicados.</span>
      <span className="mt-2 grid grid-cols-[auto_1fr_auto] items-center gap-x-2.5 gap-y-1">
        {ESCALA_COLAPSO.map(({ nivel, rango }) => (
          <span key={nivel} className="contents">
            <span aria-hidden className="flex items-end gap-px text-(--ink)">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className="w-1 rounded-[1px] bg-current"
                  style={{ height: 4 + i * 2.5, opacity: i <= NIVELES[nivel].orden ? 0.85 : 0.18 }}
                />
              ))}
            </span>
            <span>{NIVELES[nivel].etiqueta}</span>
            <span className="text-right text-2 num">{rango}</span>
          </span>
        ))}
      </span>
      <span className="mt-2 block text-3">
        Fuente: DEIS, REM-20. Umbrales: Royal College of Psychiatrists (85 %) y Bagust et al., BMJ 1999 (90 %).
      </span>
    </span>
  );
}
