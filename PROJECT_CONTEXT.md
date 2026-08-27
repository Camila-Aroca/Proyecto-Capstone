# Contexto del Proyecto: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental (RM)

## 1. Resumen y Propósito
- **Objetivo:** Plataforma analítica para la Región Metropolitana que anticipa demanda de urgencia en salud mental a corto plazo (4-8 semanas), identifica brechas de accesibilidad territorial y caracteriza determinantes de hospitalización psiquiátrica (F00-F99).
- **Institución:** Duoc UC Antonio Varas | Asignatura: Capstone APT (Fase 1 a 3).
- **Stack Tecnológico:** Python 3.x, Pandas, Geopandas/OSM/GTFS, Scikit-learn / Statsmodels / Prophet (series de tiempo), FastAPI/Flask, Pytest.

## 2. Componentes del Sistema
1. **Demanda (Series de Tiempo):**
   - *Insumo:* Atenciones de urgencia semanales por establecimiento (DEIS 2021+).
   - *Salida:* Proyección a 4-8 semanas con intervalos de predicción y backtesting vs. baseline estacional ingenuo.
2. **Accesibilidad (Geoespacial):**
   - *Insumo:* Georreferenciación de urgencias (SAPU, SAR, UEH), red vial OSM, transporte público GTFS, población y vulnerabilidad comunal.
   - *Salida:* Isócronas de viaje, cobertura por comuna y cruce accesibilidad-demanda.
3. **Hospitalización (Analítica de Estadía):**
   - *Insumo:* Egresos hospitalarios individuales disociados (F00-F99).
   - *Salida:* Modelado de determinantes de duración de estadía según edad, previsión, SNSS y condición de egreso.

## 3. Decisiones y Supuestos Clave
- **Exclusión explícita:** Fuera de alcance la gestión de vacantes/cupos en tiempo real.
- **Enlace de datos:** El cruce entre urgencias y egresos es exclusivamente ecológico (datos no unibles por individuo).
- **Limitación temporal:** Serie de urgencias parte en 2021; estacionalidad evaluada con cautela.
- **Metodología:** Ágil / CRISP-DM iterativo, gestionado con GitHub Projects y tableros Kanban.
- **Fuente DEIS Establecimientos:** Descargada y procesada. Archivo crudo en `data/raw/deis/establecimientos_salud_actualizado.csv` (UTF-8, separador `;`). Caracteres con acentos preservados mediante decodificación UTF-8 pura. Coordenadas tipadas a `float64` numérico sin manipulación destructiva. Salidas generadas en `data/processed/establecimientos_rm_clean.csv`, `data/processed/establecimientos_rm_clean.parquet` y `data/processed/establecimientos_salud_clean.parquet`.
- **Auditoría e Integridad de Establecimientos:** Validada retención del 100% de registros de la RM (1,172 filas RAW-RM vs 1,172 CLEAN, 0 duplicados, 0 registros perdidos). Cobertura geoespacial del 91.8% (1,076 centros con coordenadas válidas). Reporte generado en `reports/eda_establecimientos_rm.md` mediante script reproducible `scripts/eda_establecimientos_rm.py`.
- **Cartografía Censo 2024 (GeoParquet):** Ingesta oficial de 10 capas vectoriales en `data/raw/censo/` en formato GeoParquet con CRS `SIRGAS 2000` (`EPSG:4674`). Procesamiento y validación de la capa comunal de la Región Metropolitana (`data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet`) con cobertura 100% de las 52 comunas oficiales (0 nulos, 0 duplicados en `CUT`, geometrías `MultiPolygon` íntegras), documentado en `reports/eda_censo_comunal.md`.
- **Ingesta RAW de Atenciones de Urgencia (2020–2026):** Descarga y descompresión íntegra en `data/raw/urgencias/` (7 ZIPs y 7 CSVs anuales). Diccionario incluido en origen únicamente para 2020–2022 (`DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx`), ausente en ZIPs de 2023–2026.
- **Ingesta RAW de Egresos Hospitalarios (2020–2025):** Descarga y descompresión íntegra en `data/raw/egresos/` (6 ZIPs y 6 CSVs anuales). Diccionario incluido en todos los años (`Diccionario BD egresos hospitalario.xlsx`). Egresos 2026: no disponible por no encontrarse publicado por el DEIS.
- **Auditoría Técnica de Formato y Encoding RAW:** Inspección a nivel de bytes sobre 66,674,950 registros nacionales (14 archivos RAW). Se verificó delimitador punto y coma (`;`) y 0 líneas desbalanceadas. Urgencias (2020–2026) y Egresos (2020–2023) codificados en `Latin-1 / CP1252`. Egresos (2024–2025) codificados en `UTF-8` pero con caracteres de reemplazo `\xef\xbf\xbd` (`U+FFFD`) preexistentes de origen en 3 columnas de glosas (`GLOSA_COMUNA_RESIDENCIA`, `GLOSA_REGION_RESIDENCIA`, `GRUPO_EDAD`), manteniendo 100% íntegros los códigos numéricos territoriales y diagnósticos (`reports/eda_auditoria_formato_raw.md`, `reports/eda_egresos_encoding_detalle.md`).
- **Normalización y Filtrado de Atenciones de Urgencia RM (2020–2026):** Pipeline reproducible en `src/data/clean_urgencias.py` con suite de tests unitarios (`tests/test_clean_urgencias.py`). Procesó 57,294,818 registros RAW nacionales, homologando tipos a `int32`, `int64`, `float64` y generando 13,897,800 registros de la RM en 7 archivos Parquet (`data/processed/urgencias/urgencias_rm_[2020-2026].parquet`). Cruce territorial 1:1 vía catálogo DEIS (`reports/eda_urgencias_normalizacion.md`).
- **Validación Post-Normalización de Urgencias RM:** Auditoría independiente en `reports/eda_urgencias_validacion_post_normalizacion.md`. Veredicto: **APTO** (0 nulos en identificadores, 0 negativos, 0 fechas/semanas inválidas, 0 discrepancias entre `total` y suma de edades, 0 duplicados exactos o en llave natural, esquema 100% homogéneo en 24 columnas).
- **Auditoría y Homologación de Causas de Urgencia (F00–F99):** Validación con diccionario oficial DEIS (`DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx`). Demostrada la equivalencia formal con CIE-10 para el macro-agregador `ID 36` (Total F00–F99, 575,523 atenciones RM) y subcausas `ID 38` (Sustancias F10–F19), `ID 39` (Ánimo F30–F39), `ID 40` (Ansiedad/Estrés F40–F48), `ID 41` (Otros F), `ID 37` (Ideación suicida R45.8), `ID 35` (Lesiones autoinfligidas X60–X84) e `ID 42` (Hospitalizaciones). Verificada la igualdad matemática exacta `ID 36 == ID 37 + ID 38 + ID 39 + ID 40 + ID 41`. Generados catálogos maestros `data/processed/urgencias/catalogo_causas_urgencias.csv`, `data/processed/urgencias/catalogo_f00_f99.csv` e informe `reports/eda_urgencias_causas_2020_2026.md`.
- **Auditoría del Maestro de Establecimientos y Relaciones de Red:** Caracterización de 1,172 establecimientos en la RM (33 variables, 91.81% georreferenciados, 47 hospitales, 142 dispositivos de urgencia APS y 6 Servicios de Salud públicos). Constatación demostrable de que `establecimiento_codigo_madre` apunta al CESFAM base (en 122 de 124 casos) y no a un hospital, determinando que el maestro no contiene relación explícita a hospital de referencia. Se verificó que Egresos no incluye código de establecimiento individual por anonimización, ratificando la necesidad de vinculación ecológico-territorial (`reports/eda_maestro_establecimientos_y_red.md`).
- **Perfilado Descriptivo de la Demanda de Urgencias RM (2020–2026):** Validación de métodos de conteo (`id_causa == 1` para demanda general y `id_causa == 36` para salud mental F00–F99) con control de doble conteo y 0 discrepancia. Demanda general acumulada 2021–2026: 32,663,717 atenciones (73.72% en APS: SAPU/SAR/SUR; 26.23% en Hospitales). Demanda de salud mental acumulada: 574,257 atenciones (1.76% promedio regional), con crecimiento sostenido de 81,130 (2021) a 112,504 (2025) (+38.7%). Causa clínica predominante: Trastornos neuróticos y de estrés (`ID 40`, 54.21%). Alta concentración institucional en el Instituto Psiquiátrico Dr. José Horwitz Barak (99,802 consultas, 17.38% regional). Generados `scripts/eda_demanda_urgencias_rm.py`, tablas `data/processed/urgencias/tabla[1-12]_*.csv` e informe `reports/eda_demanda_urgencias_rm.md`.
- **Auditoría de Calidad y Corrección Documental (Urgencias RM):** Auditoría metodológica rigurosa de los resultados del perfilado descriptivo. Se validó matemáticamente el anidamiento exacto de subcausas en `ID 36` y el uso correcto de `ID 1` contra doble conteo. Se corrigió quirúrgicamente el informe `reports/eda_demanda_urgencias_rm.md` para reflejar la temporalidad exacta de 2026 (237 días, hasta el 25 de agosto, 35 semanas observadas en lugar de "primer semestre"), advertir sobre 3 establecimientos de urgencia (SAPU Ñuñoa, SAPU La Reina, SUR Juan Pablo II) que carecen de coordenadas (pese al 100% de match de ID en el maestro), y documentar explícitamente la anomalía de 2020 en atenciones de salud mental como una discontinuidad de captura.
- **Portabilidad y Seguridad:** Todas las referencias en informes, scripts y documentación emplean exclusivamente rutas relativas al proyecto, aptas para publicación en GitHub.

## 4. Estructura del Código Planificada
- `data/raw/`: Fuentes crudas DEIS/MINSAL (`urgencias/`, `egresos/`, `deis/`) y Censo 2024 (`censo/`). Solo lectura.
- `data/processed/`: Tablas y capas espaciales limpias y agregadas (`deis/`, `censo/`, `urgencias/`).
- `src/data/`: Pipelines de ingesta, limpieza, perfilado y validación.
- `src/models/`: Módulos de proyección de series temporales (4-8 semanas).
- `src/geo/`: Isócronas y accesibilidad espacial.
- `src/hospitalization/`: Análisis de estadía hospitalaria.
- `src/api/`: Servicios y endpoints.
- `scripts/`: Scripts ejecutables de análisis, auditoría y reportes.
- `reports/`: Informes técnicos y resultados de EDA.
- `tests/`: Pruebas automatizadas (`pytest`).

## 5. Estado Actual (Fase 1)
- [x] Definición de alcance y componentes acordada.
- [x] Configuración de entorno virtual `.venv` y repositorio base.
- [x] Ingesta, diagnóstico y limpieza de establecimientos DEIS (`src/data/`).
- [x] Auditoría de integridad y EDA reproducible de establecimientos RM (`reports/eda_establecimientos_rm.md`).
- [x] Ingesta y validación de cartografía Censo 2024 en GeoParquet (`data/raw/censo/`).
- [x] Procesamiento y validación de cartografía comunal RM Censo 2024 (`data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet`, `reports/eda_censo_comunal.md`).
- [x] Ingesta y organización de fuentes RAW DEIS: urgencias 2020–2026 (`data/raw/urgencias/`) y egresos 2020–2025 (`data/raw/egresos/`).
- [x] Auditoría técnica de formato, delimitadores y encoding RAW (`reports/eda_auditoria_formato_raw.md`, `reports/eda_egresos_encoding_detalle.md`).
- [x] Normalización y filtrado territorial de Atenciones de Urgencia DEIS 2020–2026 RM (`src/data/clean_urgencias.py`, `data/processed/urgencias/urgencias_rm_[2020-2026].parquet`, `reports/eda_urgencias_normalizacion.md`).
- [x] Validación técnica post-normalización de Urgencias RM (estado: APTO, `reports/eda_urgencias_validacion_post_normalizacion.md`).
- [x] Auditoría y homologación de causas de urgencia DEIS y catálogo dimensional F00–F99 (`data/processed/urgencias/catalogo_f00_f99.csv`, `reports/eda_urgencias_causas_2020_2026.md`).
- [x] Auditoría del maestro de establecimientos y relaciones de red asistencial/territorial (`reports/eda_maestro_establecimientos_y_red.md`).
- [x] Perfilado descriptivo de la demanda de urgencias general y de salud mental en la RM (`scripts/eda_demanda_urgencias_rm.py`, `reports/eda_demanda_urgencias_rm.md`).
- [ ] Normalización, perfilado y auditoría de Egresos Hospitalarios F00-F99 (2020–2025).
- [ ] Prototipo y diseño de arquitectura técnica de datos.