# SAAD: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana

> **Corte de estado: jueves 8 de octubre de 2026.** Este README describe el avance **a una semana de la entrega de Fase 2.1, programada para el jueves 15 de octubre de 2026**. La plataforma ya está funcional y cuenta con modelo predictivo, API y frontend. Los entregables documentales bajo responsabilidad de la jefatura de proyecto están creados y en revisión final antes de subirse al repositorio. Quedan por completar los ajustes visuales según los lineamientos de identidad del proyecto y el cierre de las evidencias de evaluación.

## Descripción y problema

SAAD es una plataforma analítica para apoyar la planificación de la red pública de urgencia en salud mental en la Región Metropolitana de Chile, a partir de fuentes oficiales como DEIS/MINSAL. Su objetivo es facilitar el análisis territorial de la demanda, la anticipación de presión asistencial y, en el alcance previsto, el estudio de accesibilidad y hospitalizaciones psiquiátricas.

Los datos disponibles se encuentran distribuidos en distintas fuentes y requieren procesamiento y análisis para convertirse en indicadores útiles para la planificación. SAAD es una herramienta de apoyo analítico: no toma decisiones clínicas, diagnostica personas ni gestiona pacientes.

## Componentes y alcance

| Componente | Estado al 8 de octubre de 2026 |
|---|---|
| **Pronóstico semanal de demanda** | Modelo implementado; benchmark y holdout publicados. Permite trabajar con proyecciones de 4 a 8 semanas y sus intervalos. |
| **API de consulta** | Código disponible en `src/api/` y plataforma funcional según el equipo. |
| **Interfaz web** | Código en `frontend/`; plataforma funcional. **Pendiente adecuación estética al logo, paleta y demás lineamientos visuales del proyecto.** |
| **Pipeline y datos** | Certificación documentada en un entorno, con 77/77 outputs reportados como válidos; el equipo confirma además una **instalación limpia en otro computador**. |
| **Accesibilidad geoespacial avanzada** | Objetivo del alcance posterior: análisis por red vial/transporte público, isócronas, cobertura y vulnerabilidad. No se presenta como módulo completamente demostrado. |
| **Caracterización de hospitalización psiquiátrica** | Objetivo del alcance posterior: análisis de estadía y factores asociados a egresos F00–F99. No se presenta como módulo completamente demostrado. |

El **alcance objetivo para el 26 de noviembre de 2026** incluye progresivamente los componentes territoriales y de hospitalización consignados en los requisitos funcionales. Se distingue de las capacidades efectivamente implementadas y demostrables en Fase 2.1.

**Fuera de alcance:** gestión de pacientes, cupos/camas en tiempo real, integración clínica en tiempo real, diagnóstico, triage, predicción de riesgo individual y decisiones sobre pacientes concretos. El trabajo se centra en la Región Metropolitana y en fuentes agregadas o disociadas.

## Evidencia técnica disponible

- [Resultados de modelamiento](reports/modeling/): benchmark, holdout y selección del modelo.
- [Certificación del pipeline](reports/validation/apt_certification_20261008T002147Z/): registro con código de salida 0 y 77/77 outputs válidos en el entorno evaluado. Parte de las etapas reutilizaron outputs existentes; no corresponde presentar este registro como una reconstrucción limpia independiente.
- **Instalación limpia en un segundo computador:** realizada, según confirmación del equipo el 8 de octubre. Para la entrega se debe conservar evidencia del procedimiento, versiones, commit, resultados y ejecución funcional.
- **Advertencias analíticas del holdout 2026:** MASE regional **0,5096** y comunal **0,6587**; cobertura de intervalos regional **69,68 %** y comunal **76,84 %** frente a **80 % nominal**. El reporte identifica diferencias de procedencia en el RAW 2026 respecto de lo registrado anteriormente. Estas limitaciones deben exponerse junto con los resultados.

La existencia de código, la certificación de outputs, la instalación limpia y la demostración end-to-end son evidencias distintas. La publicación o producción de un servicio no se presume por la ejecución local.

## Estado del proyecto: a siete días de Fase 2.1

| Área | Estado actual | Próximo cierre |
|---|---|---|
| Definición del problema y entrevistas | Base desarrollada y entrevista inicial realizada | Confirmar el alcance y observaciones académicas |
| Modelo de demanda | Implementado, con resultados publicados | Preparar exposición y advertencias de interpretación |
| Datos y pipeline | Certificación disponible | Adjuntar evidencia y documentación técnica de la segunda instalación |
| API y frontend | **Plataforma funcional** | Registrar demostración, manejo de estados de carga y casos sin datos |
| Apariencia de la plataforma | **Por ajustar al branding** | Aplicar identidad visual a la interfaz existente, sin asumir rediseño funcional |
| Entregables bajo responsabilidad de la jefatura de proyecto | **Todos creados localmente, en revisión final** | Homologar formato y contenido, después hacer commit y push |
| Requisitos, backlog y diagramas | Existen diversos artefactos en GitHub, con revisiones pendientes | Alinear artefactos con código y demo; completar evidencias faltantes |
| Presentación y video | En preparación | Acordar alcance y formato con la profesora; grabar y revisar |
| Validación de usuario y cliente institucional | Sin confirmación institucional definitiva | Acordar procedimiento de validación; no declarar aprobaciones aún no obtenidas |

La ausencia temporal de un documento en la rama `main` **no significa que no haya sido creado**: los documentos asignados a la jefatura de proyecto ya existen localmente y se encuentran pendientes de revisión final y publicación. Los artefactos que dependan de otros integrantes deben cotejarse de manera separada con sus responsables.

### Prioridades del 8 al 15 de octubre

1. Concluir la revisión de todos los entregables propios ya elaborados, resolver inconsistencias entre documentos y preparar su publicación en GitHub.
2. Adaptar la apariencia de la plataforma funcional a los lineamientos visuales del proyecto: logo, paleta, tipografía y componentes.
3. Documentar la instalación limpia realizada en un segundo computador y respaldar el flujo ejecutable con capturas o registro técnico.
4. Verificar un recorrido demostrable: selección de RM/comuna, serie histórica, pronóstico 4–8 semanas, intervalos, fecha de corte y advertencias; incluir un caso sin datos cuando corresponda.
5. Validar API, endpoints, manejo de respuestas temporales `503` y consistencia entre selección del modelo y resultados publicados.
6. Cerrar con la profesora los requisitos de la presentación, video, validación de usuario y arquitectura/despliegue; preparar la entrega y actualizar el tablero de seguimiento.

## Stack tecnológico

**Implementación existente:** frontend React, API Python/FastAPI, procesamiento y modelamiento de datos en Python, gestión de código mediante GitHub. El proyecto contempla herramientas de visualización, análisis geoespacial y gestión de datos como Tailwind CSS, Recharts, React Leaflet y PostgreSQL/PostGIS según el alcance técnico. La sola inclusión de una tecnología en el stack previsto no implica que esté implementada o desplegada.

## Ejecución local

La solución se organiza en dos servicios: backend en `src/api/` y frontend en `frontend/`. La API necesita los outputs correspondientes del pipeline, incluidos marts, cartografía y `reports/modeling/benchmark_demanda_sm_seleccion.json`. Consultar [PIPELINE.md](PIPELINE.md) para requisitos y procedimientos de generación de los datos.

```bash
# Desde la raíz del repositorio: dependencias Python
python -m pip install -r requirements.txt

# Si faltan los outputs de datos, preparar y ejecutar el pipeline según PIPELINE.md:
python scripts/run_pipeline.py

# Terminal 1: backend, desde la raíz del repositorio
uvicorn src.api.main:app --reload

# Terminal 2: frontend
cd frontend
npm install
npm run dev
```

- API local: `http://127.0.0.1:8000`; documentación interactiva: `http://127.0.0.1:8000/docs`.
- Frontend local: `http://localhost:5173`.
- El pronóstico puede inicializarse en segundo plano. Durante ese proceso, algunos endpoints pueden responder `503` y encabezado `Retry-After`; el frontend reintenta la consulta. El tiempo de inicio depende del equipo y los outputs disponibles.

**Instalación en otro equipo:** al 8 de octubre se confirma una instalación limpia en un segundo computador. La evidencia de versiones, comandos, logs y recorrido funcional se consolidará como parte de la preparación para Fase 2.1. No se declara despliegue público.

## Usuarios y validaciones

Entre los usuarios potenciales están las unidades de planificación sanitaria, los Servicios de Salud Metropolitanos, hospitales públicos y equipos de análisis territorial. **No hay cliente piloto institucional confirmado.** Belén Guzmán participa como experta de dominio y contacto inicial, no como cliente institucional confirmada. El alcance definitivo y el procedimiento de validación deben acordarse con la profesora.

## Metodología y seguimiento

El equipo trabaja con una metodología ágil apoyada en el [GitHub Project #12](https://github.com/users/Camila-Aroca/projects/12), backlog, asignación de responsables, reuniones de seguimiento y control de versiones. El estado del tablero y el avance documental deben verificarse contra el repositorio: un issue abierto o un archivo todavía no publicado no es, por sí solo, evidencia de trabajo sin realizar.

## Hitos académicos

| Hito | Fecha |
|---|---|
| Fase 1: presentación del proyecto | 3 de septiembre de 2026 |
| **Fase 2.1: avance y documentación** | **15 de octubre de 2026** |
| Fase 2.3: presentación y entrega final | 26 de noviembre de 2026 |
| Fase 3: comisión final | 30 de noviembre al 4 de diciembre de 2026, por confirmar |

## Documentación y código

- [Contexto del proyecto](PROJECT_CONTEXT.md)
- [Guía del pipeline](PIPELINE.md)
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
- [Resultados](reports/modeling/) · [Validación de pipeline](reports/validation/)

Los enlaces a entregables adicionales en revisión se añadirán cuando se publiquen sus versiones definitivas. No se enlazan archivos locales como si ya estuvieran en `main`.

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
