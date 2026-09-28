interface Props {
  advertencias: string[];
}

// Advertencias de interpretacion como aviso plegable: siempre visible su
// existencia, sin ocupar media pantalla en cada visita. Se abre por defecto
// porque la primera lectura es la que mas lo necesita.
export function AvisoLectura({ advertencias }: Props) {
  if (!advertencias.length) return null;
  return (
    <details
      open
      className="group rounded-lg border text-[13px]"
      style={{ background: "var(--notice-bg)", borderColor: "var(--notice-border)", color: "var(--notice-ink)" }}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 font-semibold [&::-webkit-details-marker]:hidden">
        <svg aria-hidden width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 7v4.5M8 4.6v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        Cómo leer estas cifras
        <span className="font-normal opacity-80">· {advertencias.length} advertencias</span>
        <svg aria-hidden className="ml-auto transition-transform duration-150 group-open:rotate-180" width="12" height="12" viewBox="0 0 12 12">
          <path d="M2.5 4.5 6 8l3.5-3.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
      </summary>
      <ul className="list-disc space-y-1 px-4 pb-3 pl-10">
        {advertencias.map((a) => (
          <li key={a} className="max-w-[80ch]">{a}</li>
        ))}
      </ul>
    </details>
  );
}
