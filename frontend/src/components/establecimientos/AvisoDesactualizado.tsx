// Aviso de pronostico vencido: se sigue mostrando, pero nunca en silencio.
export function AvisoDesactualizado({ motivo }: { motivo: string | null }) {
  return (
    <div
      role="status"
      className="rounded-lg border px-4 py-3 text-[13px]"
      style={{ background: "var(--notice-bg)", borderColor: "var(--notice-border)", color: "var(--notice-ink)" }}
    >
      <p className="font-semibold">Pronóstico desactualizado</p>
      <p className="mt-0.5 max-w-[90ch]">
        Se generó antes de la última actualización de los datos de Urgencias. Se muestran solo las semanas que
        todavía no se observan; las cifras pueden diferir de un pronóstico recalculado.
      </p>
      {motivo && <p className="mt-1 max-w-[90ch] opacity-80">Detalle: {motivo}</p>}
    </div>
  );
}
