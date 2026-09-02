# Auditoría Integral de Estado del Proyecto
## Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana

**Fecha del reporte:** 2026-08-31

**Repositorio auditado:** `proyecto-capstone`

**Alcance de la auditoría:** revisión documental, código, scripts, pruebas, reportes, datos versionados, reglas del agente, historial reciente de Git y estado de trabajo local.

**Restricción aplicada:** no se modificó código, datos, pruebas ni documentación existente; este archivo es el único artefacto creado.

---

## 1. Resumen ejecutivo

El proyecto busca desarrollar una plataforma analítica para apoyar la planificación de la red pública de urgencia en salud mental de la Región Metropolitana. Según `README.md`, `PROJECT_CONTEXT.md` y los documentos en `docs/`, el alcance vigente incluye tres componentes analíticos: proyección de demanda de urgencias en salud mental a 4-8 semanas, accesibilidad territorial mediante red vial/transporte y caracterización de egresos hospitalarios F00-F99. El proyecto excluye explícitamente una plataforma de cupos en tiempo real por inviabilidad de acceso y coordinación institucional.

**Estado general estimado:** parcialmente implementado, con avance sólido en ingeniería de datos y EDA descriptivo de urgencias/establecimientos/censo, pero sin evidencia de implementación de modelo predictivo, módulo geoespacial avanzado, API, frontend, base de datos, despliegue ni validación de usuario/cliente piloto.

**Principales avances comprobados:**

| Avance | Evidencia comprobada |
|---|---|
| Definición preliminar del problema y alcance | `README.md`, `PROJECT_CONTEXT.md`, `docs/01-definicion-proyecto/Definicion_Proyecto_APT_Fase_1.docx`, `docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx` |
| Pipeline Python con DAG básico | `scripts/run_pipeline.py`, `PIPELINE.md`, commit `624db63 feat: implementa pipeline reproducible e idempotente` |
| Módulos de descarga/limpieza para DEIS, Censo y establecimientos | `src/data/download_*.py`, `src/data/clean_*.py` |
| Normalización de urgencias RM 2020-2026 documentada | `src/data/clean_urgencias.py`, `reports/eda/eda_urgencias_normalizacion.md`, `reports/eda/eda_urgencias_validacion_post_normalizacion.md` |
| Normalización de egresos 2020-2025 implementada | `src/data/clean_egresos.py`, `tests/test_clean_egresos.py`, commit `d6c317b feat: normaliza egresos hospitalarios 2020-2025` |
| Reportes EDA y auditorías de calidad | `reports/*.md`, `reports/eda/*.csv` |
| Pruebas unitarias y de orquestación existentes | `tests/` |

**Principales vacíos y riesgos:**

| Vacío o riesgo | Evidencia |
|---|---|
| No hay datos RAW ni processed canónicos versionados, salvo `.gitkeep`; los reportes dicen haberlos usado, pero no pueden verificarse directamente desde el repositorio actual | `find data -maxdepth 4 -type f` solo muestra `data/processed/.gitkeep`; `.gitignore` excluye `data/raw/*` y `data/processed/*` |
| Las pruebas no pudieron ejecutarse en este entorno porque falta `pytest` | `python3 -m pytest tests/` falla con `No module named pytest` |
| `requirements.txt` está en UTF-16 little-endian con CRLF; puede fallar con flujos estándar si se espera UTF-8 | `file requirements.txt` |
| La documentación describe stack futuro amplio, pero no hay carpetas `src/models/`, `src/geo/`, `src/api/`, frontend, Docker ni DB | `rg --files`, `README.md`, `.agent/rules.md` |
| `PIPELINE.md` promete validaciones, provenance e idempotencia más estrictas que lo observado en código | comparación entre `PIPELINE.md` y `scripts/run_pipeline.py` |
| `scratch/` contiene lógica y resultados temporales relevantes, aunque `.gitignore` indica que no debería ser fuente oficial | `scratch/` existe en el árbol local y aparece en historial, pero está ignorado por `.gitignore` |

---

## 2. Inventario del repositorio

### Componentes encontrados

| Ruta | Función observada | Estado inventario |
|---|---|---|
| `README.md` | Presenta propósito, alcance, stack propuesto, hitos, equipo y próximos pasos | Documento base vigente, pero mezcla estado inicial con avances posteriores |
| `PROJECT_CONTEXT.md` | Índice estable de decisiones, supuestos, estado actual y reproducibilidad | Útil como mapa de estado, requiere contraste con implementación |
| `PIPELINE.md` | Guía de ejecución y DAG oficial | Parcialmente consistente con `scripts/run_pipeline.py` |
| `.agent/rules.md` | Reglas operativas de alcance, privacidad, reproducibilidad, datos RAW y estándares técnicos | Muy detallado; no todo está cumplido por la implementación actual |
| `.gitignore` | Excluye entornos, cachés, `data/raw/*`, `data/processed/*` y `scratch/` | Adecuado para datos grandes/sensibles, pero limita verificación desde Git |
| `requirements.txt` | Dependencias Python declaradas | Existe, pero codificación UTF-16 puede ser fricción técnica |
| `src/data/` | Módulos permanentes de descarga, limpieza, normalización y catálogo | Principal área implementada |
| `scripts/` | Orquestador y scripts EDA | Implementado parcialmente; EDA de urgencias y establecimientos |
| `tests/` | Pruebas unitarias y de orquestación | Existen, pero algunas dependen de datos locales no versionados |
| `reports/` | Informes EDA, auditorías y CSV auxiliares | Amplia evidencia documental de análisis previos |
| `docs/` | DOCX de definición, entrevista y bitácora | Evidencia de levantamiento y decisiones de alcance |
| `data/processed/.gitkeep` | Placeholder de datos procesados | No hay datasets procesados versionados |
| `scratch/` | Auditorías, exploraciones y JSON temporales | Posiblemente temporal; contiene evidencia auxiliar no oficial |

### Artefactos o datasets disponibles

| Artefacto | Disponible en Git | Observación |
|---|---:|---|
| RAW DEIS urgencias 2020-2026 | No | Documentado en reportes y scripts, excluido por `.gitignore` |
| RAW DEIS egresos 2020-2025 | No | Documentado en reportes y scripts, excluido por `.gitignore` |
| RAW Censo 2024 comunal | No | Documentado en reportes y scripts, excluido por `.gitignore` |
| Datasets processed Parquet/CSV canónicos | No | Solo `data/processed/.gitkeep` está versionado |
| CSV auxiliares EDA | Sí | `reports/eda/comunas_rm_censo2024.csv`, `reports/eda/registros_sin_coordenadas.csv` |
| Reportes Markdown EDA | Sí | 9 informes en `reports/eda/*.md` |
| DOCX académicos | Sí | 3 documentos en `docs/` |

### Elementos posiblemente temporales, generados o desactualizados

| Elemento | Motivo |
|---|---|
| `scratch/` | `.gitignore` lo excluye, pero el directorio existe localmente y contiene scripts/JSON de auditoría; no debe tratarse como pipeline oficial |
| `reports/*.md` | Algunos informes contienen resultados de ejecuciones anteriores no reproducibles directamente sin datos RAW locales |
| `reports/eda/eda_urgencias_normalizacion.md` vs `reports/eda/eda_urgencias_validacion_post_normalizacion.md` | Presentan diferencias históricas en conteos 2026 y totales; el segundo informe documenta corrección de una discrepancia |
| `requirements.txt` | Codificación UTF-16 inusual para ecosistema Python |
| `README.md` | Estado actual más atrasado que `PROJECT_CONTEXT.md` y el código |

---

## 3. Inventario granular de trabajo ya realizado

Este bloque separa tareas históricas que ya tienen entregables observables en el repositorio. El estado `Terminado` significa que el entregable existe y su criterio retrospectivo se puede comprobar directamente. El estado `Requiere verificación` significa que existe implementación o reporte, pero su resultado operativo depende de datos ausentes, pruebas no ejecutadas o artefactos no reproducibles en el entorno auditado.

| ID | Título breve apto para Issue | Estado propuesto | Evidencia concreta | Área | Fase | Criterios de aceptación retrospectivos | Observación o limitación |
|---|---|---|---|---|---|---|---|
| DONE-001 | Crear definición preliminar del proyecto | Terminado | `README.md`, `PROJECT_CONTEXT.md`, `docs/01-definicion-proyecto/Definicion_Proyecto_APT_Fase_1.docx`, commit `278edf9` | Gestión | Fase 1 | Existe documento con nombre, problema, objetivos, alcance y metodología preliminar | Falta validación formal con profesora como tarea futura |
| DONE-002 | Documentar entrevista con Belén Guzmán | Terminado | `docs/02-entrevistas/Bitacora_Entrevista_Belen_Guzman.docx`, commit `e08dfc3` | Gestión | Fase 1 | Existe bitácora con fecha, entrevistada, hallazgos, flujo actual, preguntas pendientes y próximos pasos | Belén queda como experta/contacto, no como clienta confirmada |
| DONE-003 | Documentar reunión de definición de alcance | Terminado | `docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx`, commit `e08dfc3` | Gestión | Fase 1 | Existe bitácora con acuerdo central, componentes, límites, riesgos y tareas pendientes | El alcance se declara preliminar hasta validación docente |
| DONE-004 | Crear estructura inicial del repositorio | Terminado | `src/`, `scripts/`, `tests/`, `docs/`, `reports/`, `data/processed/.gitkeep`, `.gitignore`, commits `278edf9` y `e08dfc3` | Gestión | Fase 1 | Existen carpetas base para código, scripts, pruebas, documentación, reportes y datos regenerables | No existe aún estructura para `src/models/`, `src/geo/` ni `src/api/` |
| DONE-005 | Crear README inicial del proyecto | Terminado | `README.md`, commits `278edf9`, `9fbf5c5` | Documentación | Fase 1 | README describe propósito, problema, componentes propuestos, stack, alcance, hitos y equipo | Está desactualizado respecto del avance de datos |
| DONE-006 | Crear contexto estable del proyecto | Terminado | `PROJECT_CONTEXT.md`, commits `e08dfc3`, `624db63`, `d6c317b`, `085f78e`, `f816151` | Documentación | Fase 1 | Documento centraliza propósito, componentes, decisiones, supuestos y estado actual | Sus estados deben contrastarse siempre con archivos y ejecución real |
| DONE-007 | Implementar descarga de fuentes DEIS | Requiere verificación | `src/data/download_deis_sources.py`, stage `download_deis` en `scripts/run_pipeline.py`, commit `624db63` | Datos | Fase 1 | Código define URLs de urgencias 2020-2026 y egresos 2020-2025, descarga, extracción y manifest básico | No se verificó ejecución; `data/raw/` no está disponible y no se ejecutaron descargas |
| DONE-008 | Implementar descarga de establecimientos DEIS | Requiere verificación | `src/data/download_establishments.py`, stage `download_establishments` en `scripts/run_pipeline.py`, `tests/test_download_establishments.py`, commit `e08dfc3` | Datos | Fase 1 | Código descarga CSV, detecta formato y valida preview; tests de funciones existen | No se verificó descarga real; URL apunta a snapshot fechado |
| DONE-009 | Implementar limpieza de establecimientos | Requiere verificación | `src/data/clean_establishments.py`, `tests/test_clean_establishments.py`, `reports/eda/eda_establecimientos_rm.md`, commit `e08dfc3` | Datos | Fase 1 | Código normaliza columnas, coordenadas, filtro RM y guarda CSV/Parquet; reporte EDA existe | Requiere RAW/processed local y suite pytest no ejecutada |
| DONE-010 | Crear EDA de establecimientos | Terminado | `scripts/eda_establecimientos_rm.py`, `reports/eda/eda_establecimientos_rm.md`, `reports/eda/registros_sin_coordenadas.csv`, commit `e08dfc3` | Datos | Fase 1 | Existen script, informe Markdown y CSV auxiliar de coordenadas faltantes | Los resultados no se recalcularon en esta auditoría |
| DONE-011 | Implementar descarga de Censo 2024 | Requiere verificación | `src/data/download_censo.py`, stage `download_censo` en `scripts/run_pipeline.py`, commit `624db63` | Datos | Fase 1 | Código descarga ZIP de cartografía comunal y extrae GeoParquet objetivo | No se verificó descarga real ni disponibilidad de RAW |
| DONE-012 | Implementar limpieza de Censo RM | Requiere verificación | `src/data/clean_censo_comunas.py`, `tests/test_clean_censo_comunas.py`, `reports/eda/eda_censo_comunal.md`, commit `e08dfc3` | Geoespacial | Fase 1 | Código filtra 52 comunas RM y valida geometrías; test y reporte existen | Requiere RAW Censo local y suite pytest no ejecutada |
| DONE-013 | Crear EDA de Censo comunal | Terminado | `reports/eda/eda_censo_comunal.md`, `reports/eda/comunas_rm_censo2024.csv`, commit `e08dfc3` | Geoespacial | Fase 1 | Existen informe y CSV auxiliar con comunas RM | Es insumo geoespacial, no implementación OSM/GTFS/isócronas |
| DONE-014 | Implementar normalización de urgencias | Requiere verificación | `src/data/clean_urgencias.py`, stage `clean_urgencias`, `tests/test_clean_urgencias.py`, `reports/eda/eda_urgencias_normalizacion.md`, `reports/eda/eda_urgencias_validacion_post_normalizacion.md`, commit `e08dfc3` | Datos | Fase 1 | Código procesa urgencias RM 2020-2026, homologa territorio y genera Parquet por año | Depende de RAW/processed ausentes y tests no ejecutados |
| DONE-015 | Construir catálogo F00-F99 de urgencias | Terminado | `src/data/build_catalogs.py`, stage `build_catalogs`, `reports/eda/eda_urgencias_causas_2020_2026.md`, commit `624db63` | Datos | Fase 1 | Existe catálogo codificado con IDs, glosas, clasificación CIE-10 y regla de doble conteo | El CSV generado no está versionado en `data/processed/` |
| DONE-016 | Crear EDA de urgencias | Terminado | `scripts/eda_demanda_urgencias_rm.py`, `reports/eda/eda_demanda_urgencias_rm.md`, commit `e08dfc3` | Datos | Fase 1 | Existen script e informe descriptivo con reglas de conteo, demanda, territorio y salud mental | No es modelo predictivo; resultados no se recalcularon durante esta auditoría |
| DONE-017 | Implementar orquestador del pipeline | Terminado | `scripts/run_pipeline.py`, `PIPELINE.md`, `tests/test_pipeline_orchestration.py`, commit `624db63` | Datos | Fase 1 | Existe CLI con `--stage`, `--force`, stages, dependencias y validación mínima de outputs | El comando `python3 scripts/run_pipeline.py --help` fue verificado; ejecución completa no |
| DONE-018 | Crear pruebas de módulos de datos | Terminado | `tests/test_clean_censo_comunas.py`, `tests/test_clean_egresos.py`, `tests/test_clean_establishments.py`, `tests/test_clean_urgencias.py`, `tests/test_download_establishments.py`, `tests/test_pipeline_orchestration.py` | QA | Fase 1 | Existen archivos de prueba para descarga, limpieza, egresos, urgencias, censo y orquestación | La creación de tests está comprobada; que todos pasen es tarea NEXT independiente |
| DONE-019 | Implementar normalización de egresos | Requiere verificación | `src/data/clean_egresos.py`, `tests/test_clean_egresos.py`, stage `clean_egresos`, commit `d6c317b` | Datos | Fase 1 | Código normaliza egresos 2020-2025, homologa esquema y usa escritura temporal | No se verificó contra RAW local ni con pytest; falta perfilado F00-F99 |
| DONE-020 | Crear documentación de pipeline | Terminado | `PIPELINE.md`, commits `624db63`, `085f78e`, `f816151` | Documentación | Fase 1 | Existe guía con requisitos, ejecución, DAG, idempotencia, force y tests | Contiene garantías que requieren alineación con el código |
| DONE-021 | Crear reglas de reproducibilidad y manejo de datos | Terminado | `.agent/rules.md`, commits `ddb22d5`, `4c99b2a`, `085f78e`, `f816151` | Documentación | Fase 1 | Existen reglas sobre privacidad, rutas, RAW, pipeline, formatos, evidencia y reproducibilidad | No todas las reglas están implementadas en el código actual |
| DONE-022 | Configurar exclusiones de datos y entornos | Terminado | `.gitignore`, commit `1df370d` | Gestión | Fase 1 | `.gitignore` excluye entornos, cachés, secretos, logs, `data/raw/*`, `data/processed/*` y `scratch/` | La exclusión de datos exige provenance/descarga reproducible |

---

## 4. Estado por componente

| Componente | Estado | Evidencia | Comentario |
|---|---|---|---|
| Definición preliminar de problema y alcance | Terminado | `README.md`, `PROJECT_CONTEXT.md`, documentos en `docs/` | Existe documentación de base; la validación docente es un componente separado pendiente |
| Validación de alcance con profesora | Por hacer | `README.md` y `docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx` la indican como pendiente | Imprescindible para Fase 1 |
| Cliente piloto o perfil de usuario validador | Por hacer | `README.md`, `PROJECT_CONTEXT.md`, documentos en `docs/` | Belén Guzmán está documentada como experta/contacto, no como clienta confirmada |
| Gestión ágil/backlog/Kanban | En curso | GitHub Project 12 `Tablero Kanban Capstone` público y abierto; URL: `https://github.com/users/Camila-Aroca/projects/12`; esta auditoría | El Project ya contiene campos base y un issue; backlog/configuración se está trabajando a partir de esta auditoría |
| Descarga/ingesta DEIS urgencias y egresos | Requiere verificación | `src/data/download_deis_sources.py`, `scripts/run_pipeline.py` | Código existe; falta verificar ejecución y snapshots RAW |
| Descarga/ingesta establecimientos DEIS | Requiere verificación | `src/data/download_establishments.py`, tests asociados | Código existe; no se verificó descarga real |
| Descarga/ingesta Censo 2024 | Requiere verificación | `src/data/download_censo.py`, stage en pipeline | Código existe; no se verificó descarga real |
| Limpieza establecimientos | Requiere verificación | `src/data/clean_establishments.py`, `tests/test_clean_establishments.py`, `reports/eda/eda_establecimientos_rm.md` | Depende de datos locales y pytest no ejecutado |
| Limpieza Censo RM | Requiere verificación | `src/data/clean_censo_comunas.py`, `tests/test_clean_censo_comunas.py`, `reports/eda/eda_censo_comunal.md` | Depende de RAW Censo ausente y pytest no ejecutado |
| Limpieza urgencias RM 2020-2026 | Requiere verificación | `src/data/clean_urgencias.py`, reportes de normalización y validación | No reproducible desde el repo actual sin datos RAW |
| Catálogo F00-F99 urgencias | Terminado | `src/data/build_catalogs.py`, `reports/eda/eda_urgencias_causas_2020_2026.md` | La definición existe en código y reporte |
| EDA demanda urgencias | Terminado | `scripts/eda_demanda_urgencias_rm.py`, `reports/eda/eda_demanda_urgencias_rm.md` | Entregable descriptivo creado; no equivale a modelo predictivo |
| EDA establecimientos y Censo | Terminado | `scripts/eda_establecimientos_rm.py`, `reports/eda/eda_establecimientos_rm.md`, `reports/eda/eda_censo_comunal.md` | Entregables documentales creados |
| Normalización egresos | Requiere verificación | `src/data/clean_egresos.py`, `tests/test_clean_egresos.py`, commit `d6c317b` | Implementada, no validada en entorno actual |
| Perfilado F00-F99 egresos | Por hacer | `PROJECT_CONTEXT.md` lo marca pendiente; no hay script/reporte específico | Necesario para hospitalización |
| Modelo demanda 4-8 semanas | Por hacer | No existen `src/models/`, scripts de entrenamiento, backtesting ni tests de modelo | Solo está planificado |
| Insumos geoespaciales base | Requiere verificación | Limpieza Censo/establecimientos y reportes EDA | Hay insumos preparados, pero dependen de datos no disponibles para reproducir |
| OSM/GTFS/isócronas y accesibilidad avanzada | Por hacer | No existe `src/geo/`; no hay red vial, GTFS ni isócronas | No debe confundirse con limpieza de Censo/establecimientos |
| Plataforma web/API | Por hacer | No existen `src/api/`, frontend, FastAPI, React, Docker, PostGIS | Stack propuesto no implementado |
| Automatización/reproducibilidad | Requiere verificación | `scripts/run_pipeline.py`, `PIPELINE.md`, tests de orquestación | DAG existe; falta ejecución completa y alinear garantías |
| Validación de pruebas | Requiere verificación | `tests/` existe, pero `python3 -m pytest tests/` falla por falta de `pytest` | La existencia de tests está terminada; su resultado no |
| Licencia | Por hacer | `README.md` indica licencia pendiente | Riesgo menor de gobernanza |

---

## 5. Evidencia

### Evidencia comprobada directamente

| Clasificación | Evidencia directa |
|---|---|
| Código permanente implementado | 8 módulos en `src/data/`, 3 scripts en `scripts/` |
| DAG declarado | `scripts/run_pipeline.py` define 10 stages: `download_censo`, `download_deis`, `download_establishments`, `clean_establishments`, `clean_censo`, `build_catalogs`, `clean_urgencias`, `clean_egresos`, `eda_establishments`, `eda_urgencias` |
| Pruebas presentes | `tests/test_clean_censo_comunas.py`, `tests/test_clean_egresos.py`, `tests/test_clean_establishments.py`, `tests/test_clean_urgencias.py`, `tests/test_download_establishments.py`, `tests/test_pipeline_orchestration.py` |
| Reportes EDA presentes | 9 Markdown en `reports/` y 2 CSV auxiliares en `reports/eda/` |
| Documentación de alcance | `docs/01-definicion-proyecto/Definicion_Proyecto_APT_Fase_1.docx`, `docs/02-entrevistas/Bitacora_Entrevista_Belen_Guzman.docx`, `docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx` |
| Historial reciente | Commits `624db63`, `d6c317b`, `1df370d`, `4c99b2a`, `085f78e`, `f816151` |
| Estado Git inicial | `git status --short` no mostró cambios antes de crear este reporte |
| Rama actual | `docs/project-status-audit` |

### Commits relacionados

| Commit | Evidencia |
|---|---|
| `f816151 docs: optimiza reglas de reproducibilidad y manejo de datos` | Cambios recientes en reglas/documentación |
| `085f78e docs: refuerza reglas de reproducibilidad y manejo de datos raw` | Cambios en `.agent/rules.md`, `PIPELINE.md`, `PROJECT_CONTEXT.md` |
| `4c99b2a docs: refuerza reglas de reproducibilidad y manejo de datos raw` | Cambios similares de refuerzo documental |
| `1df370d chore: actualiza gitignore y dependencias` | Cambios en `.gitignore` y `requirements.txt` |
| `d6c317b feat: normaliza egresos hospitalarios 2020-2025` | Agrega `src/data/clean_egresos.py`, tests y stage |
| `624db63 feat: implementa pipeline reproducible e idempotente` | Agrega `scripts/run_pipeline.py`, stages de descarga/catálogo/censo/DEIS y tests |
| `e08dfc3 Merge branch 'main'...` | Incorpora reportes EDA, scratch, módulos iniciales y tests |

### Diferencia entre evidencia e inferencia

| Afirmación | Tipo |
|---|---|
| Existen módulos de descarga, limpieza, EDA y tests en el repositorio | Hecho observado |
| El pipeline puede mostrar ayuda con `python3 scripts/run_pipeline.py --help` | Hecho observado |
| Los datos RAW/procesados no están versionados actualmente | Hecho observado |
| Los reportes EDA se basan en ejecuciones previas con datos locales | Inferencia fundada en reportes y ausencia de datasets versionados |
| La ingeniería de datos está más avanzada que modelos/plataforma | Inferencia basada en estructura de archivos y código disponible |
| El modelo predictivo, API y frontend están pendientes | Hecho observado respecto a ausencia de código; también coincide con `PROJECT_CONTEXT.md` |

---

## 6. Estado del pipeline de datos

| Etapa | Estado | Evidencia | Brecha |
|---|---|---|---|
| Fuentes implementadas | Requiere verificación | URLs y configs en `src/data/download_deis_sources.py`, `src/data/download_censo.py`, `src/data/download_establishments.py` | URLs hardcodeadas; establecimientos apunta a archivo fechado `establecimientos_20260825.csv` |
| Descarga o ingesta | Requiere verificación | Stages `download_*` en `scripts/run_pipeline.py` | No se verificó descarga por restricción de no ejecutar procesos costosos/red; `data/raw/` no está disponible |
| Limpieza y transformación | Requiere verificación | `clean_establishments.py`, `clean_censo_comunas.py`, `clean_urgencias.py`, `clean_egresos.py` | Verificación local bloqueada por datos y pytest faltante |
| Calidad de datos | Requiere verificación | Reportes `eda_auditoria_formato_raw.md`, `eda_urgencias_validacion_post_normalizacion.md`, `eda_establecimientos_rm.md`, `eda_censo_comunal.md` | Resultados no recalculados en esta auditoría |
| Análisis exploratorio de urgencias/establecimientos/censo | Terminado | `scripts/eda_demanda_urgencias_rm.py`, `scripts/eda_establecimientos_rm.py`, reportes EDA | Entregables creados; EDA de egresos F00-F99 falta |
| Modelamiento | Por hacer | No hay `src/models/`, notebooks/scripts de entrenamiento, métricas, baseline ni backtesting | Necesario para objetivo central de anticipación |
| Insumos geoespaciales base | Requiere verificación | Censo comunal y establecimientos georreferenciados en scripts/reportes | No se recalcularon por ausencia de datos |
| OSM/GTFS/isócronas | Por hacer | No hay `src/geo/`, red vial, GTFS ni outputs de accesibilidad | Componente geoespacial avanzado aún no existe |
| Plataforma o visualización | Por hacer | No hay frontend, API, mapas, dashboard ni despliegue | Stack descrito en README no implementado |
| Automatización y reproducibilidad | Requiere verificación | Orquestador DAG y tests de orquestación | `PIPELINE.md` promete validación/provenance más robusta que el código; no hay CI visible |

### Observaciones específicas del DAG

`scripts/run_pipeline.py` implementa un DAG lineal con dependencias explícitas y validación mínima de outputs por existencia, tamaño y legibilidad de cabecera/esquema. La documentación en `PIPELINE.md` indica comportamientos más completos: provenance con historial, descarga temporal fuera de `data/raw/`, reemplazo seguro, distinción dinámica de año en curso y validaciones por metadata/esquema mínimo. Parte de esto no se observa plenamente en el código actual.

Ejemplos:

| Tema | Documentado | Observado en código |
|---|---|---|
| Descarga temporal fuera de RAW | `.cache/downloads/` u otra ubicación temporal | `download_deis_sources.py` descarga ZIP directo en `data/raw/urgencias` y `data/raw/egresos`; `download_censo.py` usa ZIP temporal dentro de `data/raw/censo` |
| Provenance histórico | Conservar historial de snapshots/hashes | `update_manifest` reemplaza entrada si coincide filename |
| Año en curso dinámico | No hardcodear 2026 | `URGENCIAS_CONFIG` incluye años explícitos hasta 2026 |
| Validación idempotente robusta | Esquema mínimo/metadatos apropiados | `check_outputs_exist` revisa existencia, tamaño y lectura básica |

---

## 7. Estado de las pruebas

### Pruebas disponibles

| Archivo | Cobertura observada |
|---|---|
| `tests/test_download_establishments.py` | Directorios, detección CSV, preview y archivo vacío |
| `tests/test_clean_establishments.py` | Normalización de columnas, coordenadas, filtro RM, procesamiento end-to-end con fixture temporal |
| `tests/test_clean_censo_comunas.py` | Existencia de RAW Censo y procesamiento de 52 comunas RM |
| `tests/test_clean_urgencias.py` | Carga de catálogos y procesamiento de urgencias 2020 con conteos esperados |
| `tests/test_clean_egresos.py` | Conversión numérica, esquemas homogéneos, columna truncada, escritura atómica |
| `tests/test_pipeline_orchestration.py` | `--help`, stage inválido, skip/idempotencia y `--force` |

### Pruebas ejecutadas

| Comando | Resultado |
|---|---|
| `python scripts/run_pipeline.py --help` | No ejecutado exitosamente: `python` no existe en el entorno |
| `pytest tests/` | No ejecutado exitosamente: `pytest` no existe como comando |
| `python3 scripts/run_pipeline.py --help` | Exitoso; muestra opciones `--stage` y `--force` |
| `python3 -m pytest tests/` | Falló antes de correr tests: `No module named pytest` |
| `python3 --version` | Exitoso: Python 3.11.4 |

### Pruebas faltantes o insuficientes

| Área | Prueba faltante |
|---|---|
| Descarga DEIS | Tests unitarios para ZIP corrupto, extracción segura, manifest y no sobrescritura de RAW válido |
| Provenance | Tests de historial de snapshots y SHA256 de ZIP/RAW extraído |
| EDA demanda | Tests de generación de tablas y reglas de no doble conteo |
| Egresos F00-F99 | Tests de filtrado diagnóstico, duración de estadía, valores anómalos y segmentación |
| Modelo | Tests de baseline, backtesting, ventanas 4-8 semanas, métricas e intervalos |
| Geoespacial | Tests de CRS, reproyección, isócronas, joins y cobertura |
| API/frontend | No aplica aún; componentes no implementados |
| CI | No se observó configuración de GitHub Actions u otro CI |

### Aspectos no verificados

No se verificó la ejecución completa del pipeline porque implicaría descargas/procesamiento de gran volumen y porque los datos RAW/procesados no están disponibles en el repositorio actual. Tampoco se ejecutó la suite de pruebas porque falta `pytest` instalado en el entorno y no se autorizó instalación de dependencias.

---

## 8. Consistencia documental

| Tema | Documentación | Implementación observada | Diagnóstico |
|---|---|---|---|
| Estado del proyecto | `README.md` mantiene varios puntos como pendientes; `PROJECT_CONTEXT.md` declara múltiples etapas de datos completadas | Código y reportes muestran más avance que `README.md` | `README.md` está desactualizado respecto de ingeniería de datos |
| Pipeline reproducible | `PIPELINE.md` describe DAG, idempotencia, provenance y ejecución | Existe DAG básico, pero no todas las garantías descritas están implementadas | Parcialmente consistente |
| Arquitectura esperada | `.agent/rules.md` define `src/models/`, `src/geo/`, `src/api/` | Solo existe `src/data/` | Componentes futuros aún no creados |
| Stack propuesto | `README.md` menciona React, Tailwind, Recharts, React Leaflet, FastAPI, LightGBM, TensorFlow, Prophet/SARIMAX, PostgreSQL/PostGIS, Docker | `requirements.txt` solo contiene dependencias Python de datos/tests; no hay frontend/API/DB/Docker | Stack de producto aún planificado |
| Cliente piloto | `README.md` y DOCX indican cliente en proceso; Belén Guzmán experta, no clienta confirmada | No hay evidencia de confirmación posterior | Por hacer crítico de Fase 1 |
| Cifras de urgencias | Reportes históricos muestran discrepancias corregidas | `eda_urgencias_validacion_post_normalizacion.md` documenta conteos reales y error tipográfico previo | Usar informe de validación post-normalización como referencia más confiable |
| Licencia | `README.md` indica pendiente | No se observa archivo `LICENSE` | Por hacer |

### Decisiones o requisitos que necesitan confirmación

| Decisión pendiente | Evidencia |
|---|---|
| Validación final del alcance con la profesora | `README.md`, `docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx` |
| Confirmación de cliente piloto o usuario clave | `README.md`, `PROJECT_CONTEXT.md`, DOCX de reunión |
| Prioridad real entre modelo, geoespacial, egresos y plataforma para Fase 1 | Hitos en `README.md`; falta roadmap detallado |
| Nombre de la plataforma | DOCX de definición y reunión indica pendiente |
| Licencia del repositorio | `README.md` |

---

## 9. Riesgos y bloqueos

| Riesgo | Impacto | Evidencia | Acción recomendada |
|---|---|---|---|
| Datos no versionados/no disponibles en clon limpio | Alto: impide reproducir reportes y correr pruebas dependientes de datos | `data/processed/.gitkeep` es único archivo bajo `data`; `.gitignore` excluye RAW/processed | Documentar procedimiento de obtención, manifest, tamaños/hashes y fixtures mínimos de prueba |
| Falta de `pytest` en entorno | Medio: no se puede validar regresión | `python3 -m pytest tests/` falla con `No module named pytest` | Crear/usar entorno virtual e instalar desde `requirements.txt` |
| `requirements.txt` en UTF-16 | Medio: puede romper `pip install -r requirements.txt` según herramienta/entorno | `file requirements.txt`: UTF-16 little-endian | Convertir a UTF-8 en tarea separada y verificar instalación |
| Brecha entre `PIPELINE.md` y código | Alto: falsa confianza en reproducibilidad | Ver tabla de observaciones del DAG | Alinear implementación o ajustar documentación con evidencia real |
| Modelo predictivo ausente | Alto: objetivo central no implementado | No hay `src/models/` ni scripts de entrenamiento | Priorizar baseline estacional ingenuo y dataset semanal modelable |
| Geoespacial avanzado ausente | Alto: segundo componente analítico no implementado | No hay `src/geo/`, OSM, GTFS ni isócronas | Definir MVP geoespacial mínimo para Fase 2.1 |
| Plataforma/API ausente | Alto para producto final | No hay frontend, FastAPI ni Docker | Postergar hasta tener outputs analíticos mínimos o construir prototipo muy acotado |
| Cliente piloto sin confirmar | Alto académico: afecta validación de utilidad | `README.md` y docs lo marcan pendiente | Resolver antes de Fase 1 del 3 de septiembre de 2026 |
| `scratch/` con evidencia no oficial | Medio: riesgo de depender de lógica no mantenida | Directorio existe con muchos scripts/JSON; reglas dicen que `scratch/` es temporal | Migrar solo lo necesario a `src/`, `scripts/` o `tests/`; archivar/eliminar lo demás en tarea controlada |
| Coordenadas faltantes/anómalas | Medio para accesibilidad | `reports/eda/eda_establecimientos_rm.md` reporta 96 sin coordenadas y una coordenada fuera de rango | Crear tarea específica de geocodificación/criterio de exclusión |

---

## 10. Inventario de trabajo actual y futuro

Este bloque está preparado para convertirse en issues futuros. Las tareas están divididas en unidades normalmente abordables en uno a cinco días.

| ID | Tarea | Estado propuesto | Evidencia | Área | Prioridad | Fase sugerida | Dependencias | Criterio de aceptación resumido |
|---|---|---|---|---|---|---|---|---|
| NEXT-001 | Validar alcance con profesora | Por hacer | `README.md`, `docs/03-bitacoras/Bitacora_Reunion_Definicion_Alcance.docx` | Gestión | Alta | Fase 1 | Ninguna | Acta o nota con alcance validado, componentes aceptados y ajustes documentados |
| NEXT-002 | Confirmar cliente piloto o perfil de usuario validador | Por hacer | `README.md`, `PROJECT_CONTEXT.md`, documentos en `docs/` | Gestión | Alta | Fase 1 | Ninguna | Contacto o perfil priorizado con rol, disponibilidad y tipo de validación |
| NEXT-003 | Actualizar README con estado real del proyecto | Por hacer | README mantiene backlog, roadmap y exploración inicial como pendientes | Documentación | Alta | Fase 1 | Esta auditoría | README distingue trabajo realizado, pendientes, riesgos e hitos |
| NEXT-004 | Actualizar documento de contexto con decisiones de Fase 1 | Por hacer | `PROJECT_CONTEXT.md` centraliza decisiones y estado | Documentación | Alta | Fase 1 | NEXT-001, NEXT-002 | Contexto refleja alcance validado, cliente/perfil y prioridades |
| NEXT-005 | Preparar presentación de Fase 1 | Por hacer | Hito del 3 de septiembre de 2026 en `README.md` | Presentación | Alta | Fase 1 | Puede iniciar en paralelo; incorporar NEXT-001, NEXT-002 y NEXT-003 antes de cerrar versión final | Presentación completa, guion distribuido entre cuatro integrantes, duración máxima de 10 minutos, cobertura de problema, alcance, usuario/cliente, evidencia de avance, riesgos y plan |
| NEXT-006 | Ensayar presentación de Fase 1 y ajustar narrativa | Por hacer | No hay evidencia de ensayo o retroalimentación | Presentación | Alta | Fase 1 | NEXT-005 | Checklist de tiempos, roles, mensajes clave y preguntas esperadas |
| NEXT-007 | Crear backlog inicial desde DONE/NEXT | En curso | Auditoría creada y revisión manual en desarrollo | Gestión | Alta | Fase 1 | Esta auditoría | Inventario aprobado y convertido en issues sin duplicados |
| NEXT-008 | Configurar tablero Kanban en GitHub Projects | En curso | Project 12 existente con campos base y un issue | Gestión | Alta | Fase 1 | NEXT-007 | Campos, estados, vistas y tareas configurados y verificados |
| NEXT-009 | Definir responsables iniciales por área | Por hacer | `README.md` contiene roles nominales; docs indican división pendiente | Gestión | Media | Fase 1 | NEXT-007 | Cada tarea prioritaria tiene responsable o dupla asignada |
| NEXT-010 | Definir nombre de plataforma | Por hacer | DOCX de definición y reunión indican nombre pendiente | Presentación | Media | Fase 1 | NEXT-001 | Nombre acordado y usado consistentemente en presentación/documentos |
| NEXT-011 | Corregir codificación de `requirements.txt` a UTF-8 | Por hacer | `file requirements.txt` indica UTF-16 little-endian | QA | Media | Fase 1 si alcanza | Autorización de modificación | Archivo legible como UTF-8 y usable por `pip install -r requirements.txt` |
| NEXT-012 | Crear entorno virtual e instalar dependencias | Por hacer | `python3 -m pytest tests/` falla por falta de `pytest`; la restricción de instalación aplicó solo durante la auditoría | QA | Media | Fase 1 si alcanza | NEXT-011 | Entorno reproduce dependencias declaradas sin errores |
| NEXT-013 | Ejecutar suite completa `pytest tests/` | Por hacer | Tests existen; ejecución futura aún no iniciada | QA | Media | Fase 1 si alcanza | NEXT-012 | Resultado de tests registrado y fallos triageados |
| NEXT-014 | Crear fixtures mínimos versionados para tests de datos | Por hacer | Tests de Censo/Urgencias dependen de RAW local | QA | Alta | Fase 2.1 | Definir esquemas mínimos | Tests críticos corren sin datasets masivos |
| NEXT-015 | Verificar stages de limpieza con datos locales | Por hacer | Módulos de limpieza existen; validación futura aún no iniciada | Datos | Alta | Fase 2.1 | NEXT-012 y snapshots RAW | Cada stage produce outputs esperados con conteos documentados |
| NEXT-016 | Alinear `PIPELINE.md` con `scripts/run_pipeline.py` | Por hacer | Brechas detectadas entre documentación y código | Documentación | Alta | Fase 2.1 | Decisión técnica sobre alcance de pipeline | Documentación no promete garantías no implementadas o referencia issues técnicos explícitos |
| NEXT-017 | Implementar descarga temporal fuera de `data/raw/` | Por hacer | `download_deis_sources.py` y `download_censo.py` usan RAW como destino temporal | Datos | Alta | Fase 2.1 | NEXT-016 | ZIPs se descargan a temporal/cache y solo RAW validado entra a `data/raw/` |
| NEXT-018 | Implementar provenance histórico de snapshots | Por hacer | `update_manifest` reemplaza entradas por filename | Datos | Alta | Fase 2.1 | NEXT-017 | Manifest conserva historial con URL, fecha, tamaño y SHA256 por snapshot |
| NEXT-019 | Agregar validaciones de output por esquema esperado | Por hacer | `check_outputs_exist` valida legibilidad mínima | Datos | Media | Fase 2.1 | NEXT-016 | Stages validan columnas/tipos mínimos antes de hacer SKIP |
| NEXT-020 | Validar ejecución completa del pipeline | Por hacer | Orquestador existe; ejecución completa futura aún no iniciada | Datos | Alta | Fase 2.1 | NEXT-012, NEXT-017, NEXT-018 | Pipeline termina con outputs esperados y provenance actualizado |
| NEXT-021 | Inventariar scripts útiles de `scratch/` | Por hacer | `scratch/` contiene scripts/JSON de auditoría y está ignorado | Datos | Media | Fase 2.1 | Ninguna | Lista clasifica qué migrar, archivar o descartar |
| NEXT-022 | Migrar lógica reutilizable de `scratch/` a código oficial | Por hacer | Reglas indican que `scratch/` no debe contener lógica indispensable | Datos | Media | Fase 2.1 | NEXT-021 | Lógica necesaria vive en `src/`, `scripts/` o `tests/` |
| NEXT-023 | Implementar EDA F00-F99 de egresos | Por hacer | `PROJECT_CONTEXT.md` lo marca pendiente; no hay reporte/script específico | Datos | Alta | Fase 2.1 | NEXT-015 | Reporte y tablas con filtro `DIAG1` F00-F99, calidad y universo RM/residencia |
| NEXT-024 | Auditar duración de estadía en egresos F00-F99 | Por hacer | `src/data/clean_egresos.py` expone `dias_estada`; no hay análisis | Datos | Alta | Fase 2.1 | NEXT-023 | Distribución, outliers, nulos y reglas de tratamiento documentadas |
| NEXT-025 | Construir dataset semanal de demanda salud mental | Por hacer | EDA demanda existe, pero no tabla modelable versionada | Modelo | Alta | Fase 2.1 | NEXT-015 | Tabla semanal por establecimiento/comuna con `id_causa=36` y metadata |
| NEXT-026 | Definir regla de uso para 2020 y snapshot 2026 | Por hacer | `PROJECT_CONTEXT.md` advierte discontinuidad 2020 y mutabilidad 2026 | Modelo | Alta | Fase 2.1 | NEXT-025 | Regla documentada y aplicada en dataset de modelamiento |
| NEXT-027 | Implementar baseline estacional ingenuo | Por hacer | Requisito en README/PROJECT_CONTEXT; no hay `src/models/` | Modelo | Alta | Fase 2.1 | NEXT-025, NEXT-026 | Baseline genera pronóstico 4-8 semanas y métricas |
| NEXT-028 | Implementar backtesting temporal | Por hacer | Requisito documentado; no hay evaluación | Modelo | Alta | Fase 2.1 | NEXT-027 | Cortes temporales, métricas y comparación reproducible |
| NEXT-029 | Implementar primer modelo predictivo candidato | Por hacer | No existe código de modelo | Modelo | Media | Fase 2.3 | NEXT-027, NEXT-028 | Modelo comparado contra baseline con resultados documentados |
| NEXT-030 | Resolver coordenadas faltantes/anómalas para accesibilidad | Por hacer | `reports/eda/eda_establecimientos_rm.md` reporta 96 sin coordenadas y anomalía | Geoespacial | Alta | Fase 2.1 | DONE-010 | Lista final con geocodificación, exclusión o imputación justificada |
| NEXT-031 | Crear módulo base `src/geo/` para capas comunales y establecimientos | Por hacer | No existe `src/geo/` | Geoespacial | Alta | Fase 2.1 | NEXT-030, NEXT-015 | Módulo prepara capas limpias con CRS y joins territoriales |
| NEXT-032 | Implementar MVP de cobertura territorial simple | Por hacer | Accesibilidad avanzada ausente | Geoespacial | Media | Fase 2.3 | NEXT-031 | Cobertura por comuna documentada con limitaciones explícitas |
| NEXT-033 | Evaluar OSM/GTFS e isócronas | Por hacer | Requisito de alcance; no hay implementación | Geoespacial | Media | Fase 2.3 | NEXT-031 | Decisión técnica con fuente, costo computacional y alcance MVP |
| NEXT-034 | Implementar isócronas OSM/GTFS si el MVP lo justifica | Por hacer | No existe red vial/GTFS ni outputs | Geoespacial | Media | Fase 2.3 | NEXT-033 | Isócronas reproducibles para establecimientos priorizados |
| NEXT-035 | Diseñar contrato de datos para API/frontend | Por hacer | No hay `src/api/` ni frontend | Plataforma | Media | Fase 2.1 | NEXT-025, NEXT-031 | Especificación de endpoints/datasets, campos y filtros |
| NEXT-036 | Crear API mínima para outputs analíticos | Por hacer | FastAPI solo aparece en stack propuesto | Plataforma | Media | Fase 2.3 | NEXT-035 | Endpoints sirven demanda, forecast y capas territoriales |
| NEXT-037 | Crear frontend exploratorio mínimo | Por hacer | No hay React ni UI | Plataforma | Media | Fase 2.3 | NEXT-035 | Vista usable con serie, mapa o tabla y filtros mínimos |
| NEXT-038 | Agregar verificación automatizada o CI básico | Por hacer | No se observó GitHub Actions u otro CI | QA | Media | Fase 2.3 | NEXT-013 | CI ejecuta tests rápidos en cada PR |
| NEXT-039 | Documentar diccionario de datos procesados | Por hacer | Esquemas repartidos en código/reportes | Documentación | Alta | Fase 2.1 | NEXT-015 | Diccionario con columnas, tipos, unidades y reglas de conteo |
| NEXT-040 | Definir licencia del repositorio | Por hacer | `README.md` indica licencia pendiente | Gestión | Baja | Fase 2.1 | Acuerdo equipo | Licencia definida en README o archivo `LICENSE` |

### Estado del GitHub Project

Antecedente verificado posteriormente a la auditoría: existe el GitHub Project número 12, llamado `Tablero Kanban Capstone`, disponible en `https://github.com/users/Camila-Aroca/projects/12`. El Project está abierto y es público. Ya contiene campos de `Status`, `Priority`, `Size`, `Estimate`, `Start date` y `Target date`. Actualmente contiene el issue `Camila-Aroca/Proyecto-Capstone#1`, titulado `Agregar datasets utilizados al repositorio`.

La creación del backlog y la configuración del Kanban están en curso a partir de esta auditoría. Por eso, las tareas NEXT-007 y NEXT-008 se clasifican como `En curso`.

### Tratamiento del issue existente #1

No se debe crear un duplicado del issue `Camila-Aroca/Proyecto-Capstone#1`. Antes de incorporarlo al backlog definitivo, se recomienda revisar su título y alcance, porque `Agregar datasets utilizados al repositorio` podría contradecir `.gitignore` y las reglas del proyecto sobre no versionar RAW ni datasets procesados pesados.

La reformulación recomendada es: `Documentar fuentes de datos y procedimiento reproducible de obtención`. Esta reformulación debe conservar el issue existente y ajustar su contenido, en vez de crear un issue nuevo.

### Mapeo de estados al GitHub Project

| Estado del reporte | Estado Kanban |
|---|---|
| Terminado | Done |
| Requiere verificación | In review |
| En curso | In progress |
| Por hacer prioritario para Fase 1 | Ready |
| Por hacer posterior | Backlog |
| Bloqueado | Blocked si se agrega ese estado; en caso contrario, Backlog con etiqueta blocked |

---

## 11. Próximos pasos recomendados

### Orden lógico de ejecución

1. Cerrar decisiones de Fase 1: validar alcance con profesora, confirmar cliente piloto o perfil de usuario, definir nombre de plataforma y actualizar README al estado real.
2. Actualizar documentación de Fase 1: README, contexto, backlog inicial y presentación.
3. Ensayar presentación y ajustar narrativa académica con foco en problema, factibilidad, evidencia y plan.
4. Si queda tiempo antes del 3 de septiembre de 2026, preparar entorno mínimo y ejecutar pruebas.
5. Para Fase 2.1, cerrar reproducibilidad del pipeline: requirements, fixtures, provenance, validaciones y ejecución completa.
6. Completar egresos: perfilado F00-F99, calidad diagnóstica, duración de estadía y tabla analítica para hospitalización.
7. Preparar modelamiento: dataset semanal, reglas de conteo, tratamiento de 2020/2026, baseline estacional ingenuo y backtesting.
8. Preparar geoespacial: depuración de coordenadas, capas base y MVP de cobertura antes de OSM/GTFS avanzado.
9. Construir plataforma solo cuando existan outputs estables de modelo/geoespacial o, para demostración temprana, un prototipo acotado con datos curados.

### Dependencias entre tareas

| Dependencia | Bloquea |
|---|---|
| Cliente/alcance validado | Cierre de presentación Fase 1, priorización definitiva del backlog y criterios de éxito |
| Entorno y tests ejecutables | Verificación real de pipeline y cambios futuros |
| RAW/provenance disponible | Reproducción de EDA, validación de normalizaciones, modelamiento |
| Dataset semanal validado | Baseline, backtesting y modelo |
| Coordenadas depuradas | Isócronas, cobertura territorial y mapa |
| Outputs analíticos estables | API/frontend y narrativa final |

### Prioridad antes de Fase 1 - 3 de septiembre de 2026

Antes de la entrega de Fase 1 conviene priorizar entregables académicos de definición, validación, narrativa y organización. Las correcciones técnicas de entorno, `requirements.txt` y `pytest` son recomendadas si alcanza el tiempo, pero no deberían desplazar los entregables centrales de Fase 1.

| Prioridad | Entregable |
|---|---|
| 1 | Alcance validado con profesora y decisión explícita de excluir cupos en tiempo real |
| 2 | Cliente piloto o perfil de usuario validador identificado |
| 3 | README y contexto actualizados con estado real, riesgos y próximos hitos |
| 4 | Presentación de Fase 1 preparada |
| 5 | Ensayo de presentación y ajuste de relato |
| 6 | Backlog/Kanban inicial organizado desde DONE/NEXT |
| 7 | Verificación de entorno, `requirements.txt` y tests solo si alcanza el tiempo |

### Fase 2.1

Debe concentrarse en consolidar base técnica: reproducibilidad, tests, datos, diccionario, egresos F00-F99, dataset semanal, baseline y primer MVP geoespacial.

### Fase 2.3

Debe concentrarse en integrar resultados: modelo evaluado, accesibilidad territorial, análisis de hospitalización, API/frontend o prototipo funcional y documentación de QA.

### Fase 3

Debe concentrarse en cierre: validación con usuario/cliente piloto, refinamiento de presentación, despliegue o demo reproducible, informe final, limitaciones, backlog futuro y defensa ante comisión.

---

## Apéndice A. Verificaciones realizadas durante la auditoría

| Comando | Resultado resumido |
|---|---|
| `git status --short` | Sin cambios antes de crear este reporte |
| `git branch --show-current` | `docs/project-status-audit` |
| `git log --oneline --decorate -n 20` | 11 commits visibles; HEAD en `f816151` |
| `git show --stat --oneline -n 8` | Evidencia de commits de pipeline, egresos, gitignore/dependencias y reglas |
| `rg --files` | Confirmó ausencia de `src/models/`, `src/geo/`, `src/api/`, frontend, Docker |
| `find data -maxdepth 4 -type f` | Solo `data/processed/.gitkeep` |
| `file requirements.txt` | UTF-16 little-endian con CRLF |
| `python scripts/run_pipeline.py --help` | Falló: `python` no existe |
| `python3 scripts/run_pipeline.py --help` | Exitoso |
| `pytest tests/` | Falló: `pytest` no existe como comando |
| `python3 -m pytest tests/` | Falló: `No module named pytest` |
| `python3 --version` | Python 3.11.4 |

## Apéndice B. Conclusión de auditoría

El repositorio está en una etapa de transición entre definición académica y construcción técnica. La capa de datos tiene avances importantes y evidencia documental abundante, pero la reproducibilidad completa no queda demostrada desde el estado actual del repositorio porque los datasets canónicos no están presentes y la suite de pruebas no pudo ejecutarse sin instalar dependencias. Para convertir el avance en producto Capstone verificable, primero conviene cerrar alcance, cliente/perfil validador y organización de Fase 1; luego estabilizar entorno/pipeline y construir los componentes centrales todavía ausentes: baseline/modelo, accesibilidad y plataforma.
