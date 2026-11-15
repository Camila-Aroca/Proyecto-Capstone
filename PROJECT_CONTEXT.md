# Contexto operativo del proyecto APT

## 1. Alcance y restricciones

La Definición Proyecto APT aprobada es la autoridad sobre los objetivos; el código, los datos, las pruebas y los informes son la evidencia de la implementación. El proyecto desarrolla una plataforma analítica web/API para la Región Metropolitana que integra:

- Pronóstico semanal de demanda de urgencias de salud mental, con horizontes comprometidos de 4 a 8 semanas, intervalos, backtesting y comparación con un baseline estacional. Los horizontes 1 a 3 cubren el tramo operativo anterior.
- Análisis territorial de oferta, población, vulnerabilidad y proximidad, con el alcance de accesibilidad sujeto a la decisión documentada del equipo.
- Hospitalización psiquiátrica F00-F99: duración de estadía y diferencias o factores asociados a sexo, previsión y pertenencia al SNSS.
- Una plataforma reproducible, probada, desplegada, documentada y validada en utilidad y comprensión con docente o cliente piloto.

**Invariantes:**

- No gestionar pacientes ni camas o cupos en tiempo real; el producto no se limita a un dashboard descriptivo.
- No enlazar Urgencias y Egresos por paciente ni por establecimiento: la relación entre ambas fuentes es ecológica/territorial y conserva sus distintos granos. Urgencias identifica el establecimiento de atención; Egresos no identifica el hospital y su comuna/región corresponde a residencia.
- No procesar datos personales identificables ni inventar, corregir o imputar valores sin evidencia y una regla reproducible. Egresos cuenta registros publicados, no pacientes únicos.
- Las estadísticas externas de género son contexto interpretativo: no se cruzan automáticamente con Urgencias/Egresos ni se usan automáticamente como features. Preservar `period` y `year = null` para PHQ-4, los períodos publicados de síntomas depresivos y el texto `-` de ratios regionales.
- `DIAG1` es diagnóstico principal, `DIAG2` causa externa; el análisis hospitalario se restringe a F00-F99. ID36 de Urgencias no equivale estrictamente a F00-F99: incluye ID37, ideación suicida.

## 2. Reproducibilidad y decisiones estables

- `scripts/run_pipeline.py` es la entrada oficial para outputs permanentes; `PIPELINE.md` describe el DAG, contratos, dependencias y ejecución. `data/raw/` es snapshot/procedencia, no espacio de trabajo downstream.
- Las fuentes del año en curso pueden cambiar. El manifiesto de procedencia identifica snapshots, pero una URL y un hash no permiten recuperar una versión anterior que el proveedor haya reemplazado. El refresh de Urgencias se solicita con `--refresh-current-urgencias`.
- El código, pruebas, diccionarios y reports son la fuente para detalles y resultados cuantitativos. Este contexto es un índice: no sustituye evidencia ni copia métricas volátiles o logs.
- El código de Servicio de Salud `13` no es único: se debe usar la glosa. El maestro asigna establecimientos a Servicios, no comunas; `src/models/features.py` aproxima comuna → Servicio por mayoría de establecimientos, excluye SEREMI y «No Aplica», y falla ante empates.
- Egresos conserva sus variables originales y agrega columnas armonizadas: los códigos de sexo de 2021 se interpretan con la convención DEIS de Defunciones y la distribución como respaldo; las edades se agrupan con `80 y más`. El diccionario de Egresos no trae una tabla de códigos de sexo. La estadía se limita a 365 días solo para estimaciones anuales, no para la mediana o el percentil de estadía.

## 3. Estado de datos y análisis

- **Datos y marts:** hay ingesta y normalización de establecimientos, Censo, población proyectada, Casen, Urgencias, Egresos, Defunciones, camas, REM-20 y cuatro indicadores de contexto de género. Los marts comunales de Urgencias integran tasas con población proyectada; también existen marts mensuales por establecimiento y edad y un mart semanal por establecimiento. Ver `PIPELINE.md` y `reports/dictionary/`.
- **Territorio:** `mart_mvp_territorial_comuna` integra demanda anual cerrada, población proyectada y censal en columnas distintas, vulnerabilidad Casen y oferta como snapshot actual. Su universo incluye las 52 comunas; ausencia de reporte de Urgencias se conserva como nulo, no como cero. `src/geo/` publica la capa de oferta y proximidad por distancia recta ponderada por población censal: no son tiempos de viaje ni accesibilidad por red. Los resultados y sus límites están en `reports/geo/cobertura_urgencia_comuna.md`.
- **Alcance OSM/GTFS:** no hay isócronas ni tiempos por red implementados. La evaluación `reports/geo/evaluacion_osm_gtfs_isocronas.md` propuso OSM para automóvil y excluyó GTFS; el README vigente indica que las isócronas no se implementarán en esta entrega. La adenda de alcance C-02 sigue abierta: no presentar ninguna de las formulaciones como cierre contractual sin esa decisión.
- **Egresos y hospitalizaciones:** el dataset nacional F00-F99 conserva los registros disociados y el indicador de residencia RM. Los marts de residentes RM ofrecen tasas anuales, mediana y percentil 90 de estadía, proporción SNSS y conteos por sexo, edad, diagnóstico y previsión; la API y el tablero los exponen. El contraste con REM-20 es agregado: Egresos refiere a residencia y REM-20 a hospitales. Existe perfilado descriptivo de estadía; falta estudiar diferencias de duración según sexo, previsión y pertenencia SNSS. Fuentes: `reports/hospitalization/eda_egresos_f00_f99.md`, `reports/eda/eda_mart_egresos_f00_f99_rm.md` y diccionarios de Egresos.
- **Camas:** la dotación anual declarada y los indicadores mensuales REM-20 alimentan los marts y la API de psiquiatría. El mart de ocupación conserva el grano hospital × área × mes; una métrica de flujo semanal no se equipara al stock mensual. El escenario anual por área usa el pico de 12 meses y supuestos de ocupación, prioriza habilitar camas existentes y señala subtotales incompletos. Es una referencia condicionada, no una predicción anual validada ni disponibilidad en tiempo real. Método, supuestos y QA en `PIPELINE.md` y `reports/eda/`.
- **Defunciones y suicidios:** la ingesta conserva CSV y diccionarios originales por paquete, registra procedencia y usa el preliminar más reciente registrado sin sumar cortes superpuestos. El consolidado nacional y el mart semanal X60-X84 de residentes RM son ramas independientes de Urgencias/Egresos. Las marcas de rezago de semanas finales son alertas, no certifican completitud. Hay benchmark, holdout y pronóstico regional/comunal de suicidios; la API sirve el pronóstico persistido y responde 503 si falta o vence. Ver `PIPELINE.md` y `reports/modeling/`.

## 4. Modelos, plataforma y validación

- **Demanda:** `src/models/` implementa panel jerárquico, baseline estacional, GLM de Poisson, LightGBM, reconciliación e intervalos conformes. Los benchmarks seleccionan el modelo y los holdouts evalúan la selección congelada; configuración y métricas están en `reports/modeling/`. Persisten pronósticos y manifiestos con procedencia y vigencia, no estimadores entrenados reutilizables.
- **Establecimientos:** se pronostican ID36 y, para hospitales, ID42. ID42 registra hospitalizaciones derivadas desde la urgencia donde ocurrió la atención, no el destino de hospitalización ni la ocupación. La API sirve outputs persistidos; si falta el pronóstico responde 503 y, si venció, lo marca como desactualizado y excluye horizontes ya observados.
- **Pronóstico de demanda en la API:** reutiliza el persistido vigente y puede recalcularlo si falta o vence. Con `SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1` puede servir el persistido desactualizado con advertencia. La caracterización usa edad observada y sexo solo donde la fuente lo registra; el reparto opcional por sexo de Urgencias es un escenario hipotético, no un conteo observado. El calendario de eventos es contexto visual, no causal ni feature.
- **Despliegue:** existe una aplicación AWS con CloudFront, S3 y API en ECS Fargate; la actualización de datos se ejecuta localmente y se publica por separado. No se despliega PostgreSQL/PostGIS ni está implementado el pipeline programado en Fargate/EventBridge. La versión y los datos desplegados no deben suponerse iguales a los locales: consultar el estado y la evidencia en `README.md` y `docs/10-manual-implementacion/README.md`. La contingencia local usa Docker Compose.
- **Revalidación:** la ejecución C-08 regeneró datos y pronósticos con `--sin-evaluacion --force`; omitió benchmarks y holdouts. La evidencia, snapshots y resultados de pruebas están en `reports/validation/c08_revalidacion_20261115T161029Z/informe.md`. La certificación de octubre corresponde a otra versión y no certifica el estado actual. Los benchmarks y holdouts no se deben presentar como reevaluados con el snapshot nuevo.
- **Pendientes:** análisis de estadía por los factores requeridos; evaluación actualizada de modelos e intervalos; validación de utilidad con usuario o experto; documentación final y pendientes de despliegue y operación AWS. Consultar el README y los issues para alcance, responsables y estado vigente; no asumir adopción institucional ni operación de producción validada.

## 5. Mantenimiento

Actualizar este archivo cuando cambien el alcance formal, decisiones metodológicas o estado estable. Mantenerlo breve y remitir al pipeline, código, diccionarios y reports para contratos, métricas y evidencia detallada.
