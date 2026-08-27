# SAAD: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana

## Descripción del proyecto

Este proyecto propone desarrollar una plataforma analítica que integre fuentes oficiales del DEIS/MINSAL para caracterizar, proyectar y territorializar la presión sobre la red pública de urgencia en salud mental de la Región Metropolitana.

La plataforma busca responder:

- ¿Dónde se concentra la demanda de urgencia en salud mental?
- ¿Cuándo podría aumentar la presión sobre la red?
- ¿Qué territorios presentan menor accesibilidad?
- ¿Qué factores se relacionan con la duración de las hospitalizaciones psiquiátricas?

## Problema

La planificación de la red de urgencia en salud mental es principalmente reactiva. Aunque existen datos públicos oficiales, estos se encuentran fragmentados y requieren procesamiento para transformarse en evidencia útil para la toma de decisiones.

Actualmente, la demanda y la accesibilidad territorial no se analizan de manera integrada. Esto dificulta observar brechas territoriales que no son visibles mediante indicadores descriptivos aislados. Además, es necesario auditar la calidad de los datos y evaluar posibles problemas de subregistro antes de comparar territorios o establecimientos.

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

- Cliente piloto: profesional o institución accesible vinculada con salud mental, atención primaria, urgencias, planificación sanitaria, salud pública o gestión territorial. Su identificación está en proceso.
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

## Equipo

| Integrante | Rol | Responsabilidades |
|---|---|---|
| Camila A. | Jefa de Proyecto (PM) | Gestión ágil en Kanban, coordinación con cliente piloto/expertos y documentación. |
| Felipe R. | Data Engineer | Extracción, limpieza y auditoría de datos del DEIS, gestión de BD PostgreSQL/PostGIS. |
| Cristopher R. | Data Scientist | Desarrollo, entrenamiento y *benchmarking* de modelos predictivos de demanda. |
| Catalina | Full Stack / Geoespacial | Desarrollo de la plataforma visual en React, integración con API y análisis espacial. |

## Licencia

El uso y la licencia del repositorio están pendientes de definición por el equipo.