# Factibilidad de pronósticos de hospitalizaciones y defunciones

Evaluación documental para la tarea C-20, basada en los informes y el código del repositorio al commit `e7a55db`. No es una nueva ejecución ni una validación posterior de los modelos. Los resultados citados corresponden a los snapshots de los informes enlazados.

## Decisión

| Objetivo | Decisión | Alcance y condición |
|---|---|---|
| Hospitalizaciones derivadas desde urgencia, ID42 | **Continuar con el pronóstico existente, con reservas.** | Flujo semanal por establecimiento, no todas las hospitalizaciones psiquiátricas. El holdout muestra mejora frente al baseline, pero la cobertura de intervalos por establecimiento no cumple la tolerancia. |
| Suicidios, causa externa X60–X84 | **Continuar con el pronóstico existente, con reservas.** | Defunciones por residencia, semanales, para la RM y comunas; no representa todas las causas de muerte. Mantener la selección congelada y validar cambios con datos posteriores al holdout. |
| Total de hospitalizaciones o de defunciones por todas las causas | **No aprobar un pronóstico adicional con esta evidencia.** | Los objetivos existentes no representan esos universos. Sería necesario definir fuente, población, grano, oportunidad, baseline y evaluación independiente antes de decidir su implementación. |

## Hospitalizaciones: qué se pronostica

El [benchmark por establecimiento](benchmark_establecimientos_sm.md) y el [holdout](holdout_establecimientos_sm.md) evalúan ID42, hospitalizaciones derivadas desde la urgencia por F00–F99, por establecimiento y semana. No es equivalente a todos los egresos psiquiátricos ni permite identificar el hospital de los registros de Egresos. La relación con Egresos es territorial/ecológica, sin enlace por paciente.

El holdout registra 39 semanas de 2026 y 12 establecimientos en el universo fijo para ID42. El modelo congelado `lightgbm_global_conformal` obtuvo MASE de 0,779 por establecimiento y el baseline 1,0555; la cobertura por establecimiento fue 78,55 % y el informe la marca fuera de tolerancia. El propio informe advierte que abarca parte de un solo año, que las semanas objetivo se superponen y que el RAW evaluado difiere del registrado en la procedencia. Estos resultados no demuestran desempeño para establecimientos fuera del universo ni para otros snapshots.

## Defunciones: qué se pronostica

El [benchmark de suicidios](benchmark_suicidios.md) define el objetivo como defunciones con causa externa X60–X84 por semana DEIS y comuna de residencia en la RM. La selección usa RMSSE y cobertura frente a la declarada; muchos conteos comunales son cero, por lo que el error absoluto por sí solo puede favorecer una referencia que siempre predice cero.

En el [holdout](holdout_suicidios.md), con 41 semanas completas de 2026 y 34 orígenes, el modelo congelado `poisson_estacional_eb_vm52` conserva habilidad frente al baseline y cobertura compatible con la declarada en ambos niveles. El año en curso es un snapshot y las inscripciones o causas recientes pueden cambiar; un solo corte no permite medir ese cambio. Los orígenes comparten semanas objetivo y la serie regional tiene capacidad limitada para detectar diferencias. El informe mantiene el modelo congelado para no seleccionar usando el holdout.

La [descripción del pipeline](../../PIPELINE.md) y [PROJECT_CONTEXT.md](../../PROJECT_CONTEXT.md) documentan el mart, el pronóstico, la API y la visualización de suicidios. Por tanto, la afirmación histórica de C-20 de que defunciones no integra el producto está desactualizada para este subconjunto; no implica que exista un pronóstico para todas las defunciones.

## Alcance de esta decisión

La factibilidad está sustentada por los informes existentes y se refiere a los objetivos y cortes que ellos describen. No certifica la vigencia de los outputs actuales, el despliegue, ni la utilidad clínica. Antes de ampliar los objetivos o cambiar los modelos, corresponde definir el uso y realizar una evaluación independiente con datos adecuados y posteriores a la selección.
