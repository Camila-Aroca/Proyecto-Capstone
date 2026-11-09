// Delimitacion explicita del MVP, alineada con la seccion 1.3 de la
// Especificacion de Requisitos Funcionales (ERF-SAAD-2026 v1.1).

// En el orden de la cadena que sigue la herramienta: demanda de urgencia ->
// hospitalizacion -> ocupacion de camas -> propuesta de capacidad.
const INCLUYE = [
  { titulo: "Proyección de demanda", detalle: "Atenciones semanales a 1–8 semanas, para la región y cada comuna, con intervalo de predicción.", disponible: true },
  { titulo: "Proyección por establecimiento", detalle: "Atenciones de cada urgencia con historia suficiente y hospitalizaciones indicadas desde la urgencia en hospitales.", disponible: true },
  { titulo: "Hospitalizaciones de residentes", detalle: "Egresos por salud mental según comuna de residencia: tasa, días de estada, diagnóstico, edad, sexo y previsión.", disponible: true },
  { titulo: "Ocupación de camas de psiquiatría", detalle: "Promedio diario mensual por área y hospital (REM-20), con su nivel de saturación.", disponible: true },
  { titulo: "Propuesta anual de camas", detalle: "Escenario por área: el pico mensual de ocupación frente a la dotación, con un 85% de ocupación objetivo; su escala se contrasta con los egresos.", disponible: true },
  { titulo: "Suicidios como contexto", detalle: "Defunciones X60–X84 de residentes por comuna y semana, con su pronóstico; relación solo ecológica con las urgencias.", disponible: true },
  { titulo: "Análisis territorial", detalle: "Distribución comunal, variación esperada, oferta por tipo, vulnerabilidad y proximidad en línea recta a la urgencia más cercana.", disponible: true },
  { titulo: "Accesibilidad a la red", detalle: "Tiempos de viaje por red vial y transporte público, y cobertura poblacional.", disponible: false },
];

const EXCLUYE = [
  "Gestión de pacientes: no registra, sigue ni deriva personas, ni usa datos identificables.",
  "Gestión de cupos u ocupación en tiempo real: la ocupación es el promedio mensual publicado y la dotación, la declarada en el año.",
  "Decisiones de inversión: la propuesta de camas es un escenario; no acredita personal, presupuesto, espacio ni plazos.",
  "Decisiones clínicas: no apoya diagnóstico, triage ni decisiones individuales.",
  "Predicción de riesgo de una persona.",
  "Integración en tiempo real con sistemas hospitalarios.",
  "Otras regiones y el sector privado de salud.",
];

export function Alcance() {
  return (
    <section aria-labelledby="alcance-titulo" className="panel">
      <div className="panel-header">
        <h2 id="alcance-titulo" className="panel-title">Alcance de esta herramienta</h2>
        <p className="text-[13px] text-3">Apoyo a la planificación de la red, no a la atención clínica.</p>
      </div>
      <div className="grid gap-x-10 gap-y-6 px-5 pb-5 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-[13px] font-semibold">Incluye en el MVP</h3>
          <ul className="space-y-2">
            {INCLUYE.map((item) => (
              <li key={item.titulo} className="flex gap-2.5 text-[13px]">
                <svg aria-hidden className="mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 16 16">
                  <path d="M3.5 8.5 6.5 11.5 12.5 4.5" stroke="var(--accent)" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>
                  <span className="font-medium">{item.titulo}.</span>{" "}
                  <span className="text-2">{item.detalle}</span>
                  {!item.disponible && (
                    <span className="ml-1.5 whitespace-nowrap rounded px-1.5 py-px text-[11px] font-medium text-3" style={{ background: "var(--surface-2)" }}>
                      en desarrollo
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-[13px] font-semibold">Fuera del MVP</h3>
          <ul className="space-y-2">
            {EXCLUYE.map((texto) => (
              <li key={texto} className="flex gap-2.5 text-[13px] text-2">
                <svg aria-hidden className="mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 16 16">
                  <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="var(--ink-3)" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
                {texto}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
