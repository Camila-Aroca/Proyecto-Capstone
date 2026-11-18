# SAAD: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana

> **Corte de estado: 18 de noviembre de 2026 (UTC), ciclo 17.** La predefensa de Fase 2.2 es el 19 de noviembre y la entrega de programa y documentos es antes del 3 de diciembre. El estado de implementación, el despliegue en AWS y la validación con usuarios se respaldan con evidencias distintas.

## Descripción y problema

SAAD es una plataforma analítica para apoyar la planificación de la red pública de urgencia en salud mental en la Región Metropolitana de Chile, a partir de fuentes oficiales como DEIS/MINSAL. Su objetivo es facilitar el análisis territorial de la demanda, la anticipación de presión asistencial y el estudio de hospitalizaciones psiquiátricas y de cobertura territorial.

Los datos disponibles se encuentran distribuidos en distintas fuentes y requieren procesamiento y análisis para convertirse en indicadores útiles para la planificación. SAAD es una herramienta de apoyo analítico: no toma decisiones clínicas, diagnostica personas ni gestiona pacientes.

## Demostración de la plataforma

**Plataforma desplegada en AWS** (la URL pública no se publica en el repositorio; el equipo la tiene registrada). La portada respondió HTTP 200 y la API informó datos y pronóstico listos en la comprobación del 18 de noviembre (UTC). La aplicación sirve datos con corte observado 2026-S45. Ver [despliegue y evidencias](#despliegue-en-aws).

Video demostrativo del proyecto APT y su plataforma SAAD.

**[Ver video en OneDrive](https://1drv.ms/v/c/1077fd38eb2f231f/IQA5SVAjl34GRL9JrJROFFDaAb8jY5uxFC5eg_6YipsMxDo?e=nSg4S3)**

Alternativa: [descargar el MP4 desde GitHub](https://github.com/Camila-Aroca/Proyecto-Capstone/releases/download/demo-saad-2026-10-14/VideoDemo.mp4) · MP4 · 2 min 21 s · 71,74 MiB.

El video está disponible como archivo adjunto en la [Release de demostración de SAAD](https://github.com/Camila-Aroca/Proyecto-Capstone/releases/tag/demo-saad-2026-10-14). **Corresponde a la versión del 14 de octubre**: no muestra los cambios posteriores. Su actualización para la predefensa está pendiente (issue C-09).

## Componentes y alcance

«Implementado» significa que la función existe en la API o la interfaz del repositorio. La tabla de AWS indica qué se comprobó en la plataforma desplegada y la sección de usuarios recoge el estado de la validación piloto.

| Componente | Estado | Detalle y límites |
|---|---|---|
| **Pronóstico semanal de demanda (urgencias ID36)** | Implementado | Proyecciones de 4 a 8 semanas con intervalos, por RM y por comuna. Los horizontes 1 a 3 son operativos y no reemplazan el compromiso de 4 a 8. ID36 incluye ideación suicida y no equivale estrictamente a F00–F99. Modelo seleccionado: `hibrido_glm_region_lgbm_comuna_conformal`. Ver [`reports/modeling/`](reports/modeling/) |
| **Pronóstico por establecimiento** | Implementado | Atenciones de salud mental (ID36) y hospitalizaciones derivadas desde Urgencias (ID42, solo hospitales). ID42 cuenta dónde ocurrió la urgencia; no identifica el hospital de destino ni mide ocupación. Un pronóstico ausente no implica demanda cero |
| **Suicidios semanales por comuna de residencia** | Implementado | Observaciones y pronóstico X60–X84 para la región y comunas. Las semanas finales pueden tener registro incompleto por rezago de inscripción; la alerta no certifica completitud. Su relación con Urgencias es territorial, sin enlace individual |
| **Hospitalización psiquiátrica (Egresos F00–F99)** | Parcial | Existen análisis descriptivos de duración de estadía y un perfil anual por comuna de residencia (tasa, mediana y percentil 90 de estadía, sexo, edad, diagnóstico, previsión y proporción SNSS), además de dotación y ocupación de camas. **Sigue pendiente estudiar diferencias de duración de estadía según sexo, previsión y pertenencia SNSS**, más allá de los desgloses descriptivos existentes. Ver [EDA nacional](reports/hospitalization/eda_egresos_f00_f99.md) y [EDA territorial](reports/eda/eda_mart_egresos_f00_f99_rm.md) |
| **Ocupación y escenario anual de camas** | Implementado como escenario | REM-20 muestra ocupación promedio mensual por hospital y área; dotación es capacidad anual declarada. La propuesta usa el pico de 12 meses con supuestos de ocupación, prioriza habilitar camas existentes y señala subtotales parciales. No es ocupación en tiempo real, pronóstico anual validado ni factibilidad de inversión. Ver [`PIPELINE.md`](PIPELINE.md) y [EDA de ocupación](reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm.md) |
| **Cobertura territorial** | Parcial | Cobertura simple por comuna: distancia en línea recta de la población censal 2024 a la oferta de urgencia. Mide proximidad, **no accesibilidad**: no usa red vial, transporte público ni tiempos de viaje |
| **Isócronas OSM/GTFS** | **No implementadas** | La [evaluación territorial](reports/geo/evaluacion_osm_gtfs_isocronas.md) propuso OSM para automóvil y excluyó GTFS. La adenda de alcance C-02 sigue abierta; no se presenta la propuesta como decisión contractual cerrada |
| **Pronóstico de todos los egresos F00–F99 y de defunciones por todas las causas** | **No implementado** | Los pronósticos existentes cubren solo hospitalizaciones derivadas desde Urgencias (ID42) y suicidios (X60–X84), no esos universos completos. Ver [factibilidad](reports/modeling/factibilidad_pronosticos_hospitalizaciones_defunciones.md) |
| **Caracterización de series** | Implementada | Edad observada de Urgencias y sexo/edad observados de suicidios según lo publicado. Urgencias no registra sexo: el reparto opcional usa egresos nacionales por intento suicida como escenario hipotético no validado, no como conteo observado |
| **Calendario de contexto (festividades y estaciones)** | Implementado | Contexto visual. No son variables del modelo ni explicaciones causales |
| **Autenticación de usuarios** | **No implementada** | No hay referencias a autenticación en `src/api/` |
| **API de consulta** | Implementada | FastAPI de solo lectura en `src/api/`. Contrato en [`docs/06-requisitos/contrato_api/`](docs/06-requisitos/contrato_api/README.md) |
| **Interfaz web** | Implementada | React en `frontend/`, con el branding del proyecto aplicado según el issue #100. Defectos de interfaz DEF-12 a DEF-14 cerrados en el ciclo 15 |
| **Pipeline y datos** | Revalidación parcial ejecutada | Corrida forzada local del 15-11 con evaluaciones omitidas; ver «Evidencia técnica» |

El control de cambios del **alcance contractual** (ERF y ERNF) está pendiente en el issue C-02. No se debe leer este README como una adenda aprobada.

**Fuera de alcance:** gestión de pacientes, cupos/camas en tiempo real, integración clínica en tiempo real, diagnóstico, triage, predicción de riesgo individual y decisiones sobre pacientes concretos. El trabajo se centra en la Región Metropolitana y en fuentes agregadas o disociadas. Urgencias y Egresos no se enlazan por paciente: toda relación entre ellas es territorial.

## Despliegue en AWS

| Elemento | Estado y fecha de comprobación | Evidencia |
|---|---|---|
| **Plataforma desplegada** | **Sí.** CloudFront → ALB → ECS Fargate (API) y S3 privado (frontend y datos), región `us-east-1`, definida con AWS CDK en [`infra/aws/`](infra/aws/) | [Informe E2E del 12-11](reports/validation/e2e_local_aws/20261112T131720Z/informe.md) |
| **URL funcional** | Portada y API operativas en la comprobación del 18-11 (UTC). Los datos y el pronóstico estaban listos | [Resultados de compatibilidad en AWS](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_compatibilidad/resultados.md) |
| **Prueba E2E local–AWS** | El reintento del 17-11 registró 13 endpoints equivalentes, 24 comprobaciones aprobadas, 0 fallidas y 7 sin ejecutar en esa corrida | [Paridad SAAD-CP-068](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/EVIDENCIA/SAAD-CP-068.md) |
| **Interfaz en AWS** | La corrida de interfaz registró 48 aprobados y 0 fallidos. SAAD-CP-074 comprobó además el mismo recorrido en Chromium, Firefox y WebKit | [Corrida de interfaz](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_manual_aws/resultados.md) · [Compatibilidad](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_compatibilidad/EVIDENCIA/SAAD-CP-074.md) |
| **Actualización de datos** | El pipeline **se ejecuta en el equipo** y sus outputs se publican con `infra/aws/scripts/subir_datos.sh`. No se ejecuta en Fargate ni está programado con EventBridge (cambio de alcance, issue C-42 abierto) | [Plan de despliegue](docs/08-arquitectura/plan_despliegue_aws.md) |
| **CI/CD (CodePipeline y CodeBuild)** | **Operativa.** La conexión con GitHub está `AVAILABLE`; `saad-pr` se ejecutó con éxito el 17-11 y `saad-despliegue` terminó en `Succeeded` el 18-11 (Fuente, Verificar y Desplegar). Tras el despliegue la API, el sitio y las 7 alarmas respondieron sano | [Retest SAAD-CP-066](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/resultados.md) |
| **Versión y datos desplegados** | La lectura de ECS del ciclo 17 identificó la imagen `saad-api:95d00f8` y su digest. Tras publicar los datos, la primera semana pronosticada para RM fue **2026-S46** en ambos entornos. La comprobación del 18-11 (UTC) encontró en AWS el corte observado **2026-S45** y el pronóstico persistido del 17-11 | [Lectura de ECS](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_lectura/resultados.md) · [Evidencia de paridad](reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/EVIDENCIA/SAAD-CP-068.md) |
| **Seguridad, costos, observabilidad y manual operacional** | Parcialmente documentados; la consolidación (C-45) está pendiente | [Costos](docs/08-arquitectura/costos_aws_verificacion.md) |

AWS **no sustituye** la contingencia local: si el despliegue no estuviera disponible en una presentación, la plataforma se demuestra con Docker Compose.

## Evidencia técnica disponible

- [Resultados de modelamiento](reports/modeling/): benchmark, holdout y selección del modelo.
- **Holdout de demanda 2026** (snapshot con fecha máxima 2 de octubre): MASE regional **0,5096** y comunal **0,6587**; cobertura de intervalos regional **69,68 %** y comunal **76,84 %** frente a **80 % nominal**, sin calibración en ninguno de los dos niveles. El informe concluye que la selección **se sostiene solo parcialmente**. Estas cifras corresponden a ese snapshot: **los datos se actualizaron después y el holdout no se ha vuelto a ejecutar**. Los intervalos deben leerse como orientativos.
- **Certificación del pipeline del 8 de octubre** ([`reports/validation/apt_certification_20261008T002147Z/`](reports/validation/apt_certification_20261008T002147Z/)): código de salida 0 y 77/77 outputs válidos **en esa versión**. Parte de las etapas reutilizó outputs existentes y no es una reconstrucción limpia. **No certifica la versión vigente.**
- **Revalidación posterior al corte de octubre** ([evidencia C-08](reports/validation/c08_revalidacion_20261115T161029Z/informe.md)): el 15-11 terminó con código 0 una corrida forzada con `--sin-evaluacion`, que regeneró datos y pronósticos. Los tres benchmarks y los tres holdouts se omitieron; la evaluación con el snapshot actualizado sigue pendiente. El [informe del 10-11](reports/validation/c08_revalidacion_20261110.md) documenta el rezago de Defunciones y una ejecución anterior.
- **Suite automatizada U-39:** 920 pruebas ordinarias y 29 de integración aprobadas por separado sobre el commit base `5c341c5`, con cambios locales; salidas y entorno en la [evidencia C-08](reports/validation/c08_revalidacion_20261115T161029Z/informe.md). No acredita instalación desde un clon limpio.
- **Pruebas de la plataforma.** Tras SAAD-CP-079, el catálogo de 200 casos consolidó **195 aprobados, 0 fallidos y 5 sin ejecutar**. Los cinco (SAAD-CP-009, 037, 046, 078 y 080) son pruebas de comprensión que requieren un usuario piloto. SAAD-CP-079 se ejecutó como barrido automatizado de 1,5 minutos, no como la sesión humana de 30 minutos que describe el caso. El registro de defectos mantiene DEF-01 a DEF-16 cerrados, incluidos DEF-11 a DEF-14 y sus retests. [Registro principal de pruebas](reports/validation/registro_principal_pruebas.md) · [Registro de defectos](reports/validation/ciclos_pruebas/registro_defectos.md)
- **Instalación limpia en un segundo computador:** el equipo la confirmó el 8 de octubre, pero **no hay evidencia archivada** en el repositorio (comandos, versiones, logs). El [manual de implementación](docs/10-manual-implementacion/README.md) registra qué instalaciones tienen evidencia y cuáles no.

La existencia de código, la certificación de outputs, la instalación limpia, el despliegue y la validación con usuarios son evidencias distintas.

## Estado del proyecto

| Área | Estado | Próximo cierre |
|---|---|---|
| Modelo de demanda | Implementado; holdout con datos de octubre | Consolidar métricas, cobertura de intervalos y limitaciones (C-14) |
| Datos y pipeline | Corrida forzada del 15-11 con evaluaciones omitidas; pronósticos regenerados y procedencia registrada | Revalidar benchmarks y holdouts con los datos actuales |
| API y frontend | Implementados y verificados en AWS en los recorridos del ciclo 17 | Validación con usuario piloto |
| Despliegue en AWS | Operativo con publicación manual de datos; CI y despliegue por CodePipeline verificados el 18-11 | Completar C-36, C-42 y C-45 |
| Documentación técnica | [Manual de implementación en Word](docs/10-manual-implementacion/Manual_Implementacion_SAAD.docx) y [manual de usuario en Word](docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx) disponibles | Revisión de entrega de C-15 y anexos operacionales de C-45 |
| Pruebas | [Registro principal](reports/validation/registro_principal_pruebas.md) con los 200 casos y evidencia por ciclo | Seis casos de aceptación y sesión con cliente pendientes |
| Validación con cliente o experto | **Sin cliente piloto institucional confirmado.** No hay registro de validación de la muestra funcional con cliente (issue #90 sin cerrar) | Registrar feedback clínico (C-19) y validación (#90) |
| Presentación y video | En preparación | PPT, ensayos y video actualizado (C-09 a C-12) |

## Stack tecnológico

**Implementado:** frontend React, API Python/FastAPI, procesamiento y modelamiento de datos en Python (pandas, GLM de Poisson, LightGBM), Docker Compose, AWS CDK y gestión de código en GitHub. El modelo físico PostgreSQL/PostGIS se documentó en [`docs/07-diagramas/15-modelo-base-datos/`](docs/07-diagramas/15-modelo-base-datos/modelo_datos_fisico_postgresql.png), pero **la plataforma no usa base de datos**: la API lee archivos Parquet y reportes. No se despliega Aurora ni PostGIS.

## Ejecución local

El procedimiento completo, con versiones, variables, permisos y estado de validación, está en el [manual de implementación](docs/10-manual-implementacion/README.md). Active primero el entorno virtual Python según el manual. Ejecute la API y el frontend en terminales separadas.

```bash
python -m pip install -r requirements.txt
python scripts/run_pipeline.py                 # genera data/processed y reports/ (descarga el RAW la primera vez)
python -m uvicorn src.api.main:app --reload    # API en http://127.0.0.1:8000 (documentación en /docs)
```

```bash
cd frontend
npm ci
npm run dev                                  # frontend en http://localhost:5173
```

Las fuentes oficiales, URLs, períodos, el manifest con hashes y la política de no versionar datos RAW están en [`docs/09-fuentes-de-datos`](docs/09-fuentes-de-datos/README.md). Los detalles del DAG están en [`PIPELINE.md`](PIPELINE.md).

### Docker Compose

Requiere Docker con Compose v2 y los outputs del pipeline en `data/` y `reports/`, que se montan en solo lectura en la API.

```bash
docker compose up -d --build                                       # frontend :8080, API :8000/docs
docker compose --profile pipeline run --rm pipeline                # pipeline completo, escribe en data/ y reports/
docker compose --profile pipeline run --rm pipeline python -m src.cloud.pipeline_task --modo semanal
```

- Puertos configurables con `SAAD_WEB_PORT` y `SAAD_API_PORT`.
- La API **lee sus datos solo al arrancar**: tras regenerar outputs hay que reiniciarla (`docker compose restart api`).
- El pronóstico comunal de demanda se recalcula si el guardado falta o no está vigente; durante el cálculo responde `503` con `Retry-After`. Con `SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1` puede servir el guardado con advertencia. Los pronósticos de establecimientos y suicidios se sirven desde archivos persistidos y tienen reglas de vigencia distintas: consultar el [manual](docs/10-manual-implementacion/README.md) y `PIPELINE.md`.
- `docker-compose.yml` incluye el servicio `pipeline` para ejecución local. `src/cloud/pipeline_task.py` también admite trabajar contra S3 con `SAAD_S3_BUCKET`, pero **esa modalidad no está desplegada**: el pipeline no corre en Fargate.

## Usuarios y validaciones

Entre los usuarios potenciales están las unidades de planificación sanitaria, los Servicios de Salud Metropolitanos, hospitales públicos y equipos de análisis territorial. **No hay cliente piloto institucional confirmado ni adopción institucional.** Belén Guzmán participa como experta de dominio y contacto inicial, no como cliente institucional. La consulta clínica y su registro están pendientes (C-19). No se declaran aprobaciones ni validaciones que no estén documentadas.

## Metodología y seguimiento

El equipo trabaja con una metodología ágil apoyada en el [GitHub Project #12](https://github.com/users/Camila-Aroca/projects/12), backlog, asignación de responsables, reuniones de seguimiento y control de versiones. El estado del tablero y el avance documental deben verificarse contra el repositorio: un issue abierto o un archivo todavía no publicado no es, por sí solo, evidencia de trabajo sin realizar.

## Hitos académicos

| Hito | Fecha | Estado |
|---|---|---|
| Fase 1: presentación del proyecto | 3 de septiembre de 2026 | Realizada |
| Fase 2.1: avance y documentación | 15 de octubre de 2026 | Realizada |
| **Fase 2.2: predefensa** | **19 de noviembre de 2026** | Próxima |
| **Fase 2.3: presentación y entrega final** | **26 de noviembre de 2026** (fecha del tablero del proyecto) | Pendiente |
| **Entrega de programa y documentos en GitHub y OneDrive** | **antes del 3 de diciembre de 2026** (issue C-27) | Pendiente |
| Fase 3: comisión final | 30 de noviembre al 4 de diciembre de 2026 | Por confirmar |

## Documentación y código

- [Contexto del proyecto](PROJECT_CONTEXT.md)
- [Guía del pipeline](PIPELINE.md)
- Manual de implementación reproducible [Word](docs/10-manual-implementacion/Manual_Implementacion_SAAD.docx) · [Markdown](docs/10-manual-implementacion/README.md)
- Manual de usuario [Word](docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx) · [Markdown](docs/11-manual-usuario/README.md)
- [Fuentes de datos y procedimiento de obtención](docs/09-fuentes-de-datos/README.md)
- [Plan de despliegue en AWS](docs/08-arquitectura/plan_despliegue_aws.md) · [Infraestructura como código](infra/aws/cdk/README.md)
- [Definición del proyecto APT - Fase 1](docs/01-definicion-proyecto/Definicion_Proyecto_APT_Fase_1.docx)
- [Bitácora de entrevista con Belén Guzmán](docs/02-entrevistas/Bitacora_Entrevista_Belen_Guzman.docx)
- [Bitácora de reunión de definición y alcance](docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx)
- [Especificación de Requisitos Funcionales](docs/06-requisitos/Especificacion_Requisitos_Funcionales.docx)
- [Especificación de Requisitos No Funcionales](docs/06-requisitos/Especificacion_Requisitos_No_Funcionales.docx)
- [UML casos de uso](docs/07-diagramas/casos_de_uso_saad.png) · [Fuente PlantUML](docs/07-diagramas/casos_de_uso_saad.puml)
- [UML componentes](docs/07-diagramas/componentes_saad.png) · [Fuente PlantUML](docs/07-diagramas/componentes_saad.puml)
- [UML clases](docs/07-diagramas/clases_saad.png) · [Fuente PlantUML](docs/07-diagramas/clases_saad.puml)
- [Modelo físico PostgreSQL/PostGIS](docs/07-diagramas/15-modelo-base-datos/modelo_datos_fisico_postgresql.png)
- [Modelo predictivo](src/models/) · [API](src/api/) · [Frontend](frontend/)
- [Resultados](reports/modeling/) · [Validación y pruebas](reports/validation/)

## Equipo

| Integrante | Rol | Responsabilidades principales |
|---|---|---|
| Camila A. | Jefatura de Proyecto (PM) | Coordinación, gestión ágil, documentación y relación con expertos o futuros usuarios |
| Felipe R. | Data Engineer | Ingesta, limpieza, auditoría y gestión de datos |
| Cristopher R. | Data Scientist | Modelos predictivos, entrenamiento, benchmark y evaluación |
| Catalina | Full Stack / Geoespacial | Plataforma React, integración API y componente espacial |

## Licencia

Consultar el archivo [LICENCIA.md](LICENCIA.md).

Copyright (c) 2026 Camila Aroca, Cristopher Rojas, Felipe Rivera, Catalina Rodríguez
