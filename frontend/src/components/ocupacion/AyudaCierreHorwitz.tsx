// Contexto puntual: cierre de la unidad de larga estadia del Instituto Horwitz
// (area 420) en abril de 2026, que explica el cero de REM-20 desde mayo.
export const HORWITZ = 109102;
export const AREA_LARGA_ESTADIA = 420;

export function AyudaCierreHorwitz() {
  return (
    <>
      <button type="button" aria-label="Información sobre el cierre de larga estadía del Horwitz"
        aria-describedby="ayuda-cierre-larga-estadia-horwitz" className="ml-1 cursor-help text-3">
        <span aria-hidden>ⓘ</span>
      </button>
      <span id="ayuda-cierre-larga-estadia-horwitz" role="tooltip"
        className="invisible absolute left-0 top-full z-20 w-72 max-w-[calc(100vw-3rem)] pt-1 text-left text-[12px] font-normal opacity-0 transition-opacity duration-150 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        <span className="panel block whitespace-normal px-3 py-2.5 text-(--ink) shadow-sm">
          <span className="block font-semibold">Cierre de larga estadía del Horwitz</span>
          <span className="mt-1.5 block">El 20 de abril de 2026 salieron los últimos cuatro pacientes hacia
            una residencia de alta complejidad, culminando el cierre de la unidad.</span>
          <span className="mt-1.5 block">Desde mayo de 2026, REM-20 registra cero días cama disponibles,
            ocupados y egresos en esta área. Las 29 camas declaradas corresponden al libro de 2025, anterior al cierre.</span>
          <a className="mt-2 block text-3 underline" target="_blank" rel="noopener noreferrer"
            href="https://psiquiatrico.cl/video-luego-de-174-anos-el-instituto-psiquiatrico-deja-de-tener-pacientes-de-larga-estadia/">
            Fuente: comunicado del Horwitz, 23 de abril de 2026 (abre en otra pestaña).
          </a>
        </span>
      </span>
    </>
  );
}
