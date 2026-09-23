# SAAD: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana

## Descripción del proyecto

Este proyecto propone desarrollar una plataforma analítica que integre fuentes oficiales del DEIS/MINSAL para caracterizar, proyectar y territorializar la presión sobre la red pública de urgencia en salud mental.

La plataforma busca responder:

- ¿Dónde se concentra la demanda de urgencia en salud mental?
- ¿Cuándo podría aumentar la presión sobre la red?
- ¿Qué territorios presentan menor accesibilidad?
- ¿Qué factores se relacionan con la duración de las hospitalizaciones psiquiátricas?

## Problema

La planificación de la red de urgencia en salud mental es principalmente reactiva. Aunque existen datos públicos oficiales, estos se encuentran fragmentados y requieren procesamiento para transformar la información en indicadores útiles para la planificación sanitaria.

Actualmente, la demanda y la accesibilidad territorial no se analizan de manera integrada. Esto dificulta observar brechas territoriales que no son visibles mediante indicadores descriptivos aislados.

## Componentes propuestos

1. Modelo de demanda
   Proyección de atenciones de urgencia por salud mental para una ventana de 4 a 8 semanas, con intervalos de predicción y evaluación mediante backtesting contra un baseline estacional.

2. Accesibilidad geoespacial
   Georreferenciación de establecimientos, cálculo de accesibilidad mediante red vial y transporte público, y estimación de cobertura territorial cruzada con vulnerabilidad socioeconómica.

3. Caracterización de la hospitalización psiquiátrica
   Análisis de los factores relacionados con la duración de estadía para diagnósticos F00-F99, considerando diagnóstico, edad, previsión, pertenencia al SNSS y condición de egreso.

Estos componentes están sujetos a validación académica y a validación con el futuro cliente piloto.

## Stack Tecnológico

El proyecto se desarrollará utilizando tecnologías modernas orientadas al análisis de datos y la escalabilidad:

- **Frontend & UI:** React, Tailwind CSS, Recharts (visualización de datos), React Leaflet (mapas espaciales).
- **Backend & API:** Python con FastAPI.
- **Modelamiento Predictivo:** LightGBM, TensorFlow, Prophet/SARIMAX (para evaluación baseline).
- **Base de Datos:** PostgreSQL con extensión PostGIS (para análisis de rutas y polígonos geoespaciales).
- **Infraestructura y Entorno:** Docker Compose (despliegue local), WSL2 (Linux), automatización con Cron.
- **Gestión y Control de Versiones:** Git, GitHub, GitHub Projects (Metodología Kanban).
- **Diseño y Prototipado:** Figma.
- **IDE:** Visual Studio Code.

## Público objetivo

- Cliente piloto: profesional o institución accesible vinculada con salud mental, atención primaria, urgencias, planificación sanitaria, salud pública o gestión territorial. Su identificación y validación deben confirmarse con la profesora.
- Usuarios potenciales futuros: Servicios de Salud Metropolitanos, hospitales públicos, municipios, corporaciones de salud y unidades de planificación.

Belén Guzmán participa como experta de dominio y contacto inicial, pero no está confirmada como clienta del proyecto.

## Alcance y limitaciones

- Territorio: Región Metropolitana.
- Foco: red pública de urgencia en salud mental.
- Uso de datos agregados o disociados, sin tratamiento de información personal.
- Proyecciones destinadas al apoyo de la planificación, no al diagnóstico clínico ni a decisiones individuales.
- El cruce entre urgencias y egresos hospitalarios será ecológico, porque las bases no se pueden unir individualmente.
- La extensión de la serie histórica y el nivel de resolución de los datos pueden limitar las conclusiones.
- El alcance definitivo debe validarse con la profesora.

## Metodología de trabajo

Se utilizará una metodología ágil basada en:

- Tablero Kanban en GitHub Projects.
- Backlog de tareas.
- Asignación de responsables y fechas.
- Revisión periódica de avances.
- Documentación y control de versiones mediante GitHub.

## Estado actual

| Actividad | Estado |
|---|---|
| Definición preliminar del problema | Completada |
| Entrevista inicial con experta de dominio | Completada |
| Definición preliminar del alcance | Completada |
| Validación del alcance con la profesora | Pendiente |
| Confirmación del cliente piloto | En proceso |
| Roadmap y carta Gantt | Pendiente |
| División de tareas y roles | Pendiente |
| Desarrollo del backlog técnico | Pendiente |

## Próximos pasos

1. Validar la definición y el alcance con la profesora.
2. Incorporar las observaciones recibidas.
3. Confirmar el perfil y representante del cliente piloto.
4. Elaborar el roadmap y la carta Gantt.
5. Dividir el proyecto en entregables y tareas.
6. Asignar responsables y fechas concretas.
7. Configurar el tablero Kanban en GitHub Projects.
8. Iniciar la exploración y auditoría de las fuentes de datos.

## Hitos académicos

- Fase 1 — Presentación del proyecto: 3 de septiembre de 2026.
- Fase 2.1 — Avance y documentación: 15 de octubre de 2026.
- Fase 2.3 — Presentación y entrega final: 26 de noviembre de 2026.
- Fase 3 — Comisión final: entre el 30 de noviembre y el 4 de diciembre de 2026, por confirmar.

## Documentación

- [Definición del proyecto APT - Fase 1](docs/01-definicion-proyecto/Definicion_Proyecto_APT_Fase_1.docx)
- [Bitácora de entrevista con Belén Guzmán](docs/02-entrevistas/Bitacora_Entrevista_Belen_Guzman.docx)
- [Bitácora de reunión de definición y alcance](docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx)
- [Especificación de Requisitos Funcionales (ERF-SAAD-2026)](docs/06-requisitos/Especificacion_Requisitos_Funcionales.docx)
- [Especificación de Requisitos No Funcionales (ERNF-SAAD-2026)](docs/06-requisitos/Especificacion_Requisitos_No_Funcionales.docx)
- [Diagrama UML de casos de uso](docs/07-diagramas/casos_de_uso_saad.png) — fuente: [`casos_de_uso_saad.puml`](docs/07-diagramas/casos_de_uso_saad.puml)
- [Diagrama UML de componentes](docs/07-diagramas/componentes_saad.png) — fuente: [`componentes_saad.puml`](docs/07-diagramas/componentes_saad.puml)
- [Diagrama UML de clases](docs/07-diagramas/clases_saad.png) — fuente: [`clases_saad.puml`](docs/07-diagramas/clases_saad.puml)
- [Diagrama ER del modelo de base de datos PostgreSQL/PostGIS](docs/07-diagramas/15-modelo-base-datos/modelo_datos_fisico_postgresql.png) — fuente: [`modelo_datos_fisico_postgresql.mmd`](docs/07-diagramas/15-modelo-base-datos/modelo_datos_fisico_postgresql.mmd)

## Equipo

| Integrante | Rol | Responsabilidades |
|---|---|---|
| Camila A. | Jefa de Proyecto (PM) | Gestión ágil en Kanban, coordinación con cliente piloto/expertos y documentación. |
| Felipe R. | Data Engineer | Extracción, limpieza y auditoría de datos del DEIS, gestión de BD PostgreSQL/PostGIS. |
| Cristopher R. | Data Scientist | Desarrollo, entrenamiento y *benchmarking* de modelos predictivos de demanda. |
| Catalina | Full Stack / Geoespacial | Desarrollo de la plataforma visual en React, integración con API y análisis espacial. |

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Puedes consultar el texto completo en [LICENSE](LICENSE).

Copyright (c) 2026 Camila Aroca y colaboradores.
