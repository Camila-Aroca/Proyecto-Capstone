# SAAD: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana

> **Corte de estado: sábado 14 de noviembre de 2026**, a cinco días de la predefensa de Fase 2.2 (jueves 19 de noviembre). Este README distingue lo **implementado y con evidencia en el repositorio**, lo **parcial**, lo **no implementado** y lo **pendiente de validación**. Donde no hay evidencia se dice expresamente. El corte anterior (8 de octubre) quedó superado por el trabajo de octubre y noviembre.

## Descripción y problema

SAAD es una plataforma analítica para apoyar la planificación de la red pública de urgencia en salud mental en la Región Metropolitana de Chile, a partir de fuentes oficiales como DEIS/MINSAL. Su objetivo es facilitar el análisis territorial de la demanda, la anticipación de presión asistencial y el estudio de hospitalizaciones psiquiátricas y de cobertura territorial.

Los datos disponibles se encuentran distribuidos en distintas fuentes y requieren procesamiento y análisis para convertirse en indicadores útiles para la planificación. SAAD es una herramienta de apoyo analítico: no toma decisiones clínicas, diagnostica personas ni gestiona pacientes.

## Demostración de la plataforma

Video demostrativo del proyecto APT y su plataforma SAAD.

**[Ver video en OneDrive](https://1drv.ms/v/c/1077fd38eb2f231f/IQA5SVAjl34GRL9JrJROFFDaAb8jY5uxFC5eg_6YipsMxDo?e=nSg4S3)**

Alternativa: [descargar el MP4 desde GitHub](https://github.com/Camila-Aroca/Proyecto-Capstone/releases/download/demo-saad-2026-10-14/VideoDemo.mp4) · MP4 · 2 min 21 s · 71,74 MiB.

El video está disponible como archivo adjunto en la [Release de demostración de SAAD](https://github.com/Camila-Aroca/Proyecto-Capstone/releases/tag/demo-saad-2026-10-14). **Corresponde a la versión del 14 de octubre**: no muestra los cambios posteriores. Su actualización para la predefensa está pendiente (issue C-09).

## Componentes y alcance

Estado al 14 de noviembre de 2026. «Implementado» significa que existe código y es accesible desde la API o la interfaz; no significa validado con usuarios.

| Componente | Estado | Detalle y límites |
|---|---|---|
| **Pronóstico semanal de demanda (urgencias ID36)** | Implementado | Proyecciones de 4 a 8 semanas con intervalos, por RM y por comuna. Los horizontes 1 a 3 son operativos y no reemplazan el compromiso de 4 a 8. Modelo seleccionado: `hibrido_glm_region_lgbm_comuna_conformal`. Ver [`reports/modeling/`](reports/modeling/) |
| **Pronóstico por establecimiento** | Implementado | Atenciones de salud mental (ID36) y hospitalizaciones derivadas desde urgencia (ID42, solo hospitales), con la misma regla de selección del modelo comunal |
| **Suicidios semanales por comuna de residencia** | Implementado | Mart, benchmark y pronóstico. Las semanas finales pueden tener registro incompleto por rezago de inscripción y se marcan; la marca no certifica completitud |
| **Hospitalización psiquiátrica (Egresos F00–F99)** | Parcial | Perfil por comuna de residencia (tasa, estadía, sexo, edad, diagnóstico, previsión), dotación y ocupación de camas de psiquiatría. **El análisis de duración de estadía y de factores asociados más allá del perfilado descriptivo sigue pendiente** según [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) |
| **Cobertura territorial** | Parcial | Cobertura simple por comuna: distancia en línea recta de la población censal 2024 a la oferta de urgencia. Mide proximidad, **no accesibilidad**: no usa red vial, transporte público ni tiempos de viaje |
| **Isócronas OSM/GTFS** | **No implementadas** | El equipo decidió no implementarlas en esta entrega. Justificación en [`reports/geo/evaluacion_osm_gtfs_isocronas.md`](reports/geo/evaluacion_osm_gtfs_isocronas.md) |
| **Pronóstico de hospitalizaciones por F00–F99 y de defunciones generales** | **No implementado** | No hay modelo ni endpoint |
| **Calendario de contexto (festividades y estaciones)** | Implementado | Contexto visual. No son variables del modelo ni explicaciones causales |
| **Autenticación de usuarios** | **No implementada** | No hay referencias a autenticación en `src/api/` |
| **API de consulta** | Implementada | FastAPI de solo lectura en `src/api/`. Contrato en [`docs/06-requisitos/contrato_api/`](docs/06-requisitos/contrato_api/README.md) |
| **Interfaz web** | Implementada | React en `frontend/`, con el branding del proyecto aplicado según el issue #100. Hay defectos de interfaz abiertos en AWS (DEF-12 a DEF-14) |
| **Pipeline y datos** | Implementado, con revalidación pendiente | Ver «Evidencia técnica» |

El **alcance contractual** (ERF y ERNF) y los cambios decididos se registran en el control de cambios del issue C-02, aún abierto. No se debe leer este README como una adenda de alcance.

**Fuera de alcance:** gestión de pacientes, cupos/camas en tiempo real, integración clínica en tiempo real, diagnóstico, triage, predicción de riesgo individual y decisiones sobre pacientes concretos. El trabajo se centra en la Región Metropolitana y en fuentes agregadas o disociadas. Urgencias y Egresos no se enlazan por paciente: toda relación entre ellas es territorial.

## Despliegue en AWS

| Elemento | Estado al 12–14 de noviembre | Evidencia |
|---|---|---|
| **Plataforma desplegada** | **Sí.** CloudFront → ALB → ECS Fargate (API) y S3 privado (frontend y datos), región `us-east-1`, definida con AWS CDK en [`infra/aws/`](infra/aws/) | [Informe E2E del 12-11](reports/validation/e2e_local_aws/20261112T131720Z/informe.md) |
| **URL funcional** | **Existe**, pero no se publica en este repositorio; el equipo la tiene registrada | Informe E2E |
| **Resultado de la prueba E2E** | 21 casos aprobados, 4 fallidos, 6 no ejecutados. Los 4 fallidos eran outputs de datos que faltaban y se cerraron después (DEF-01 a DEF-03) | [Registro de defectos](reports/validation/ciclos_pruebas/registro_defectos.md) |
| **Actualización de datos** | El pipeline **se ejecuta en el equipo** y sus outputs se publican con `infra/aws/scripts/subir_datos.sh`. No se ejecuta en Fargate ni está programado con EventBridge (cambio de alcance, issue C-42 abierto) | [Plan de despliegue](docs/08-arquitectura/plan_despliegue_aws.md) |
| **CI/CD (CodePipeline y CodeBuild)** | **Bloqueada:** la conexión con GitHub está pendiente de aprobación | Registro de defectos |
| **Versión desplegada** | La versión en AWS **no se puede confirmar desde la API**: `/api/v1/meta` no expone el SHA ni el digest de la imagen | Registro de defectos |
| **Seguridad, costos, observabilidad y manual operacional** | Parcialmente documentados; la consolidación (C-45) está pendiente | [Costos](docs/08-arquitectura/costos_aws_verificacion.md) |

AWS **no sustituye** la contingencia local: si el despliegue no estuviera disponible en una presentación, la plataforma se demuestra con Docker Compose.

## Evidencia técnica disponible

- [Resultados de modelamiento](reports/modeling/): benchmark, holdout y selección del modelo.
- **Holdout de demanda 2026** (snapshot con fecha máxima 2 de octubre): MASE regional **0,5096** y comunal **0,6587**; cobertura de intervalos regional **69,68 %** y comunal **76,84 %** frente a **80 % nominal**, sin calibración en ninguno de los dos niveles. El informe concluye que la selección **se sostiene solo parcialmente**. Estas cifras corresponden a ese snapshot: **los datos se actualizaron después y el holdout no se ha vuelto a ejecutar**. Los intervalos deben leerse como orientativos.
- **Certificación del pipeline del 8 de octubre** ([`reports/validation/apt_certification_20261008T002147Z/`](reports/validation/apt_certification_20261008T002147Z/)): código de salida 0 y 77/77 outputs válidos **en esa versión**. Parte de las etapas reutilizó outputs existentes y no es una reconstrucción limpia. **No certifica la versión vigente.**
- **Revalidación posterior al corte de octubre** ([evidencia C-08](reports/validation/c08_revalidacion_20261115T161029Z/informe.md)): el 15-11 terminó con código 0 una corrida forzada con `--sin-evaluacion`, que regeneró datos y pronósticos. Los tres benchmarks y los tres holdouts se omitieron; la evaluación con el snapshot actualizado sigue pendiente. El [informe del 10-11](reports/validation/c08_revalidacion_20261110.md) documenta el rezago de Defunciones y una ejecución anterior.
- **Pruebas de la plataforma:** línea base local ([`baseline_local`](reports/validation/baseline_local/20261112T135538Z/informe.md)), prueba E2E local contra AWS, ciclos de prueba y registro de defectos en [`reports/validation/`](reports/validation/). Abiertos al 14-11: DEF-11 (`subir_datos.sh` no valida outputs completos) y DEF-12 a DEF-14 (interfaz).
- **Instalación limpia en un segundo computador:** el equipo la confirmó el 8 de octubre, pero **no hay evidencia archivada** en el repositorio (comandos, versiones, logs). El [manual de implementación](docs/10-manual-implementacion/README.md) registra qué instalaciones tienen evidencia y cuáles no.

La existencia de código, la certificación de outputs, la instalación limpia, el despliegue y la validación con usuarios son evidencias distintas.

## Estado del proyecto

| Área | Estado | Próximo cierre |
|---|---|---|
| Modelo de demanda | Implementado; holdout con datos de octubre | Consolidar métricas, cobertura de intervalos y limitaciones (C-14) |
| Datos y pipeline | Corrida forzada del 15-11 con evaluaciones omitidas; pronósticos regenerados y procedencia registrada | Revalidar benchmarks y holdouts con los datos actuales |
| API y frontend | Funcionales en local y en AWS; defectos de interfaz abiertos | Corregir DEF-12 a DEF-14 y revisar los resultados de los ciclos |
| Despliegue en AWS | Operativo con datos publicados manualmente; CI/CD bloqueada | C-36, C-42 y C-45 |
| Documentación técnica | [Manual de implementación](docs/10-manual-implementacion/README.md) en su primera versión; manual de usuario pendiente | C-15 y anexos operacionales de C-45 |
| Pruebas | Campañas de 70 y 200 casos con registro de defectos | Cerrar defectos abiertos y repetir el ciclo |
| Validación con cliente o experto | **Sin cliente piloto institucional confirmado.** No hay registro de validación de la muestra funcional con cliente (issue #90 sin cerrar) | Registrar feedback clínico (C-19) y validación (#90) |
| Presentación y video | En preparación | PPT, ensayos y video actualizado (C-09 a C-12) |

## Stack tecnológico

**Implementado:** frontend React, API Python/FastAPI, procesamiento y modelamiento de datos en Python (pandas, GLM de Poisson, LightGBM), Docker Compose, AWS CDK y gestión de código en GitHub. El modelo físico PostgreSQL/PostGIS se documentó en [`docs/07-diagramas/15-modelo-base-datos/`](docs/07-diagramas/15-modelo-base-datos/modelo_datos_fisico_postgresql.png), pero **la plataforma no usa base de datos**: la API lee archivos Parquet y reportes. No se despliega Aurora ni PostGIS.

## Ejecución local

El procedimiento completo, con versiones, variables, permisos y estado de validación de cada paso, está en el [manual de implementación](docs/10-manual-implementacion/README.md). Resumen:

```bash
python -m pip install -r requirements.txt
python scripts/run_pipeline.py                 # genera data/processed y reports/ (descarga el RAW la primera vez)
uvicorn src.api.main:app --reload              # API en http://127.0.0.1:8000 (documentación en /docs)
cd frontend && npm install && npm run dev      # frontend en http://localhost:5173
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
- Si el pronóstico guardado no está vigente, la API lo recalcula al arrancar y mientras tanto responde `503` con `Retry-After`. Con `SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1` sirve el guardado con una advertencia visible; sus cifras pueden no corresponder al modelo seleccionado.
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
- [Manual de implementación reproducible](docs/10-manual-implementacion/README.md)
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
