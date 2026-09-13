# Guía de Ejecución del Pipeline (PIPELINE.md)

Este documento centraliza las instrucciones para ejecutar el pipeline de datos de manera reproducible, ordenada e idempotente.

## 1. Requisitos
Para preparar el entorno antes de correr el pipeline:

```bash
# 1. Crear entorno virtual
python -m venv .venv
# 2. Activar entorno virtual
.venv\Scripts\activate   # (Windows)
# source .venv/bin/activate # (Mac/Linux)
# 3. Instalar dependencias
pip install -r requirements.txt
```

## 2. Ejecución Completa

Para correr todo el pipeline (saltará automáticamente las etapas que ya tengan los datos generados):

```bash
python scripts/run_pipeline.py
```

## 3. Ejecución desde una Etapa

`--stage` define el punto de inicio de una rama del DAG.

Ejemplo:

```bash
python scripts/run_pipeline.py --stage clean_urgencias
```

Si los outputs son válidos y no existen cambios upstream relevantes, las etapas correspondientes realizan `SKIP`.

Con `--force`, la etapa seleccionada se regenera y el cambio se propaga únicamente a sus dependencias downstream, sin ejecutar ramas no relacionadas.

Por ejemplo, `--stage clean_urgencias --force` ejecuta `clean_urgencias` y posteriormente `eda_urgencias`.

## 4. Forzar Regeneración (Force)

Si deseas regenerar una etapa ignorando su condición normal de `SKIP`, utiliza `--force`.

Cuando se combina con `--stage`, se fuerza la etapa seleccionada y la regeneración se propaga únicamente a sus dependencias downstream.

Ejemplo:

```bash
python scripts/run_pipeline.py --stage clean_urgencias --force
```

Para regenerar un único Parquet anual de Urgencias sin evaluar downstream ni
reprocesar otros años, usar el contrato particionado:

```bash
python scripts/run_pipeline.py --stage clean_urgencias --year 2026
```

`--year` se valida contra los años soportados y el RAW local correspondiente.
La validación de `SKIP` se restringe a ese Parquet; `--force` conserva el mismo
alcance anual. La ejecución sin `--year` mantiene el comportamiento histórico
del stage completo y su propagación downstream.

Para forzar la evaluación completa del pipeline puede utilizarse:

```bash
python scripts/run_pipeline.py --force
```

--force debe utilizarse deliberadamente, especialmente en etapas de descarga, porque las fuentes del año en curso pueden ser mutables y producir un snapshot distinto.

## 5. Orden de Ejecución (DAG)

La lógica reutilizable de ingesta, descarga, limpieza y normalización se organiza principalmente en `src/data/`, mientras que los ejecutables de análisis y orquestación se mantienen en `scripts/`. `scripts/run_pipeline.py` coordina las dependencias entre estas etapas.

> [!WARNING]
> La serie de atenciones del año en curso (2026) es una fuente mutable. El DEIS sobrescribe periódicamente el archivo ZIP sin versionado. Por lo tanto, ejecutar el mismo pipeline en fechas distintas descargará snapshots diferentes. Para mitigar esto, los scripts de descarga generan y actualizan un registro ligero de auditoría en `data/raw/provenance_manifest.json` con el SHA256 de lo descargado.

La cartografía del Censo 2024 corresponde a un año cerrado: un RAW válido hace `SKIP` en la operación normal y `--force` constituye la solicitud explícita y registrada para sustituir ese snapshot. El maestro de establecimientos no representa un año cerrado sino el catálogo publicado como actualizado por DEIS; también hace `SKIP` mientras el RAW sea válido y `--force` solicita un nuevo snapshot. Ambas ingestas descargan y validan fuera de `data/raw/`, publican sólo candidatos validados y agregan al historial URL, timestamp UTC, hash, tamaño, ruta RAW y metadata de transporte en el mismo manifest.

`download_censo_poblacion` descarga a staging (`.cache/downloads/censo_poblacion/`) el tabulado oficial INE `D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx` (censo2024.ine.gob.cl), valida que sea un XLSX legible con las hojas "1" (regional) y "2" (comunal) antes de publicarlo en `data/raw/censo/`, y registra URL, timestamp UTC, hash y tamaño en `data/raw/provenance_manifest.json`. Es un año cerrado: RAW válido hace `SKIP`, `--force` solicita explícitamente un nuevo snapshot. `clean_censo_poblacion` depende de esta descarga, lee únicamente la hoja "2" (grano comuna) filtrando `región=13`, valida que las 52 comunas RM coincidan exactamente con el CUT oficial (sin duplicados, sin población nula o no positiva) y contrasta la suma comunal contra el total regional independiente publicado en la hoja "1" del mismo workbook antes de publicar `data/processed/censo/dim_poblacion_comuna_censo2024.parquet` (escritura atómica). Esta dimensión es un insumo poblacional estático de 2024, separado de los marts temporales de Urgencias; no se usa como proxy poblacional para otros años ni se cruza aquí con series históricas.

`download_poblacion_proyecciones` descarga a staging (`.cache/downloads/poblacion_proyecciones/`) el cuadro oficial INE "Estimaciones y Proyecciones de la Población de Chile a nivel comunal 2002-2035" (base Censo 2017, documento metodológico de noviembre 2019; `estimaciones-y-proyecciones-2002-2035-comunas.xlsx`), valida que sea un XLSX legible con la hoja "Est. y Proy. de Pob. Comunal" y dimensiones mínimas esperadas antes de publicarlo en `data/raw/poblacion/`, y registra URL, timestamp UTC, hash y tamaño en `data/raw/provenance_manifest.json`. Es un producto demográfico ya cerrado en su base (Censo 2017): RAW válido hace `SKIP`, `--force` solicita explícitamente un nuevo snapshot. El cuadro publica población residente habitual por sexo (1=Hombre, 2=Mujer), edad simple (0 a 80, top-coded "80 y más") y comuna, al 30 de junio de cada año 2002-2035; los años 2021-2025 corresponden en su totalidad al tramo de proyección (posterior al Censo 2017 usado como ancla), no al tramo de estimación intercensal 2002-2017. Las columnas de texto de región/comuna del workbook presentan corrupción de codificación irrecuperable (U+FFFD); el CUT numérico no está afectado.

`clean_poblacion_proyecciones` depende de `download_poblacion_proyecciones` y de `clean_censo_poblacion` (reutiliza sus glosas comunales validadas, ya que el texto del workbook de proyecciones está corrupto). Filtra `región=13`, valida que sexo esté en {1,2} y edad en [0,80], suma población por comuna×año sobre todas las combinaciones sexo×edad (sin fila "total" en la fuente, por lo que no hay doble conteo), valida cobertura exacta de 52 comunas × 5 años (260 filas), sin nulos ni valores no positivos, y publica `data/processed/censo/dim_poblacion_comuna_anual.parquet` (escritura atómica) con columnas `comuna_codigo`, `comuna_glosa`, `ano`, `poblacion`, `fuente`, `tipo_poblacion` (constante `"proyeccion"` para 2021-2025). Esta dimensión es independiente de `dim_poblacion_comuna_censo2024.parquet`: una es población proyectada (residente habitual, base Censo 2017) y la otra es población efectivamente censada en 2024; no deben usarse como proxy una de la otra y la diferencia observada entre ambas para 2024 no se corrige ni se fuerza a coincidir.

`download_pobreza_comunal` descarga a staging (`.cache/downloads/pobreza_comunal/`) el cuadro oficial del Ministerio de Desarrollo Social y Familia (MDS), Observatorio Social, "Estimaciones de Tasa de Pobreza por Ingresos por Comuna" (Encuesta Casen 2022, Metodología de Estimación para Áreas Pequeñas — SAE, Fay-Herriot; `Estimaciones_Tasa_Pobreza_Ingresos_Comunas_2022.xlsx`), valida que sea un XLSX legible con la hoja "Estimaciones" y dimensiones mínimas esperadas antes de publicarlo en `data/raw/pobreza/`, y registra URL, timestamp UTC, hash y tamaño en `data/raw/provenance_manifest.json`. Es un producto ya cerrado (ronda Casen 2022): RAW válido hace `SKIP`, `--force` solicita explícitamente un nuevo snapshot. El cuadro publica, para las 346 comunas del país, el porcentaje de personas en situación de pobreza por ingresos 2022 con su intervalo de confianza, la presencia de la comuna en la muestra Casen y el tipo de estimación SAE (directa+sintética Fay-Herriot, o sintética pura cuando la comuna no cumple los criterios de inclusión muestral).

`clean_pobreza_comunal` depende de `download_pobreza_comunal` y de `clean_censo_poblacion` (reutiliza sus glosas comunales validadas para mantener consistencia de nombres entre dimensiones). Filtra `región=13`, valida cobertura exacta de las 52 comunas RM contra el CUT oficial sin duplicados, exige que cada comuna RM tenga presencia en la muestra Casen, valida que la tasa esté en el dominio [0,1] y que el intervalo de confianza publicado contenga la tasa, y publica `data/processed/pobreza/dim_vulnerabilidad_comuna.parquet` (escritura atómica) con columnas `comuna_codigo`, `comuna_glosa`, `ano_referencia` (2022, constante), `indicador_vulnerabilidad` (tasa de pobreza por ingresos, proporción 0-1), `nombre_indicador`, `fuente`, `direccion_indicador` (constante `"mayor_valor_mayor_vulnerabilidad"`), `intervalo_confianza_inferior`, `intervalo_confianza_superior` y `tipo_estimacion_sae`. Es un indicador/proxy oficial de vulnerabilidad socioeconómica comunal (tasa de pobreza por ingresos), no un índice general ni compuesto de vulnerabilidad, y un indicador estático de un único período (Casen 2022): no se replica artificialmente por semana/mes ni se combina aquí con demanda de Urgencias o Egresos para construir un puntaje de riesgo compuesto.

El siguiente listado representa el orden topológico actual del DAG. El orquestador ejecuta únicamente las etapas necesarias según los outputs existentes, las dependencias, el `--stage` solicitado y el uso de `--force`

For Egresos, `download_deis` publishes the CSV in each ZIP through the
deterministic RAW contract `data/raw/egresos/egresos_<year>.csv`. The original
name of the CSV member published by DEIS is recorded in
`data/raw/provenance_manifest.json`, so `clean_egresos` does not depend on
historical filename variants.

1. `download_censo` → (Descarga Censo a RAW)
2. `download_censo_poblacion` → (Descarga a RAW el tabulado comunal oficial INE de población censada 2024)
3. `download_poblacion_proyecciones` → (Descarga a RAW el cuadro comunal oficial INE de estimaciones/proyecciones de población 2002-2035)
4. `download_pobreza_comunal` → (Descarga a RAW el cuadro comunal oficial MDS/Casen 2022 de tasa de pobreza por ingresos, SAE)
5. `download_deis` → (Descarga Urgencias y Egresos a RAW)
6. `download_establishments` → (Descarga Maestro Establecimientos a RAW)
7. `download_contexto_genero` → (Descarga RAW de cuatro cuadros XLSX de Estadísticas de Género)
8. `normalize_contexto_genero` → (Normalización independiente de los cuatro cuadros contextuales)
9. `clean_establishments` → (Limpieza y filtrado RM)
10. `clean_censo` → (Filtro espacial RM para Censo)
11. `clean_censo_poblacion` → (Dimensión de población censada 2024 por comuna RM)
12. `clean_poblacion_proyecciones` → (Dimensión anual de población comunal RM 2021-2025, INE proyecciones base Censo 2017)
13. `clean_pobreza_comunal` → (Dimensión de vulnerabilidad socioeconómica comunal RM, MDS/Casen 2022, tasa de pobreza por ingresos SAE)
14. `build_catalogs` → (Creación de catálogo F00-F99)
15. `clean_urgencias` → (Limpieza de Urgencias 2020-2026 y unión territorial)
16. `clean_egresos` → (Normalización reproducible de Egresos Hospitalarios 2020-2025)
17. `eda_establishments` → (Validación EDA de Establecimientos)
18. `eda_urgencias` → (Generación de tablas base del EDA de Urgencias)
19. `profile_urgencias_sm_coverage` → (Perfil comuna×semana ID 36 para cobertura 2021–2025)
20. `build_urgencias_comuna_marts` → (Marts históricos comunales semanal y mensual de Urgencias, 2021–2025, con tasas por 10.000 habitantes)
21. `build_dim_oferta_urgencia_rm` → (Dimensión canónica de oferta territorial de urgencia RM: snapshot actual, no serie histórica)
22. `eda_contexto_genero` → (EDA reproducible de los cuatro cuadros contextuales)

La etapa `build_dim_oferta_urgencia_rm` depende de `clean_establishments` y `clean_urgencias`, no tiene downstream por ahora y publica `data/processed/geo/dim_oferta_urgencia_rm.parquet`. Distingue dos temporalidades: el universo y criterio de inclusión son un snapshot ACTUAL del catálogo de establecimientos (no una serie histórica) — incluye establecimientos vigentes cuyo `tipo_establecimiento_glosa` es `Hospital` o termina en el acrónimo DEIS `(SAPU)`, `(SAR)` o `(SUR)`, más una excepción documentada y detectada dinámicamente contra Urgencias (establecimientos que reportan `tipo_establecimiento_urgencia="CEAR"` sin caer en el tipo anterior) —; la evidencia de reporte (`reporto_id1_periodo`, `reporto_id36_periodo`, `ultimo_ano_reporte_id36`, `tipo_urgencia_reportado`) usa en cambio el período canónico CERRADO 2021-2025, excluyendo 2020 (discontinuidad metodológica de salud mental) y 2026 (año parcial/mutable); es información temporal complementaria, no el criterio de inclusión ni un filtro. No usa `tiene_servicio_urgencia` ni `tipo_urgencia` del maestro como criterio de inclusión (se comprobó que no son confiables: ver `reports/eda/eda_dim_oferta_urgencia_rm.md`) ni exige actividad `ID36>0` para pertenecer a la oferta. Antes de publicar valida unicidad de `establecimiento_codigo`, dominio de `criterio_inclusion_oferta` + coherencia con el tipo, vigencia, formato de `comuna_codigo`, nulidad conjunta de coordenadas, bounding box geográfico de la RM y coherencia entre los flags de reporte. El orquestador valida existencia/esquema del Parquet y realiza `SKIP` cuando es válido; `--force` lo regenera. Sus pruebas están en `tests/test_build_dim_oferta_urgencia_rm.py`. No implementa OSM/GTFS ni isócronas; es únicamente el insumo de oferta para esa capa futura de accesibilidad territorial.

## 6. Idempotencia y Validación de Outputs

El orquestador evita recomputaciones innecesarias y no considera válido un output únicamente porque exista.

Antes de ejecutar una etapa, `scripts/run_pipeline.py` valida sus outputs esperados mediante controles apropiados al formato, que pueden incluir:

- existencia del archivo;
- tamaño válido;
- integridad de archivos ZIP;
- legibilidad mínima de CSV;
- legibilidad de Parquet/GeoParquet;
- metadata y esquema mínimo esperado cuando corresponda.

Si todos los outputs son válidos y ningún upstream de la etapa cambió durante la ejecución actual, la etapa realiza `SKIP`.

Si una etapa upstream genera o modifica efectivamente sus outputs, únicamente las dependencias downstream correspondientes son reevaluadas o regeneradas.

El uso de `--force` obliga a ejecutar la etapa seleccionada y propaga la regeneración por su rama downstream, sin ejecutar ramas independientes.

Los módulos de `src/data/` encapsulan la lógica de procesamiento, pero `scripts/run_pipeline.py` es el punto de entrada oficial para generar outputs canónicos del proyecto.

La rama `download_contexto_genero` → `normalize_contexto_genero` → `eda_contexto_genero` es independiente de Egresos y Urgencias: mantiene un Parquet por fuente, no realiza uniones entre ellas y tampoco las enlaza con registros DEIS. La descarga conserva cada XLSX original en `data/raw/contexto_genero/`, valida el workbook antes de publicarlo y agrega URL, fecha/hora UTC, tamaño y SHA256 al historial de `data/raw/provenance_manifest.json`. En operación normal los RAW válidos hacen `SKIP`; `--force` solicita explícitamente un snapshot nuevo.

La etapa `profile_urgencias_sm_coverage` depende de `clean_urgencias`, no tiene downstream por ahora y publica `data/processed/urgencias/perfil_cobertura_sm_comuna_semanal_2021_2025.parquet`. Lee únicamente los Parquet 2021–2025 y las columnas necesarias: usa `id_causa=1` para conservar el calendario semanal DEIS y el universo de comunas con reporte general, e `id_causa=36` como único insumo de atenciones de salud mental. Una semana con fila ID 36 y total agregado cero es observada; una semana sin fila ID 36 se reporta como ausencia, sin imputarla. El perfil no incluye 2026 ni crea `mart_urgencias_comuna_weekly`. El orquestador valida que el Parquet exista, no esté vacío y tenga esquema legible; en operación normal realiza `SKIP` cuando pasa ese control y `--force` lo regenera. Su contrato se prueba en `tests/test_profile_urgencias_sm_coverage.py` y el registro del stage en `tests/test_pipeline_orchestration.py`.

La etapa `build_urgencias_comuna_marts` depende de `clean_urgencias` y de `clean_poblacion_proyecciones`, no tiene downstream por ahora y publica `data/processed/marts/mart_urgencias_comuna_weekly.parquet` y `data/processed/marts/mart_urgencias_comuna_monthly.parquet`. Sus inputs son los Parquet de Urgencias RM 2021–2025, con filtros de columnas e IDs 1, 35, 36 y 37–41. Cada métrica es un conteo agregado de atenciones; el mensual se agrega desde `fecha` diaria y el semanal conserva `ano`, `semana` y el mínimo `fecha` publicado como `fecha_inicio_semana`, sin convertir al calendario ISO. No imputa semanas, meses ni causas ausentes. Incluye los conteos reportantes ID1 e ID36; no incorpora el catálogo de establecimientos actual porque es un snapshot no histórico. Antes de publicar, valida grano, no negatividad, jerarquía ID36, ratios, reportantes y reconciliación anual semanal→mensual; ambos Parquet se escriben con temporal y reemplazo atómico. El orquestador valida existencia, tamaño y esquema, realiza `SKIP` cuando ambos outputs son válidos y los regenera con `--force`. Las pruebas están en `tests/test_build_urgencias_comuna_marts.py`.

Ambos marts unen `data/processed/censo/dim_poblacion_comuna_anual.parquet` por `comuna_codigo`+`ano` (join `many_to_one`, 100% de cobertura exigida: cualquier comuna×año sin denominador hace fallar la etapa) y publican `poblacion_anual` junto con `tasa_atenciones_id1_por_10000`, `tasa_atenciones_id35_por_10000` y `tasa_atenciones_id36_por_10000`. Como la fuente poblacional es anual, el mart mensual reutiliza la misma `poblacion_anual` para los 12 meses del año y el semanal la reutiliza para todas las semanas del año, sin interpolar. Estas tasas cuantifican atenciones (evento) por 10.000 habitantes; no son porcentaje de población atendida ni deben interpretarse como prevalencia o incidencia de personas.

## 7. Informes Históricos y Protegidos

Los reportes en Markdown dentro de la carpeta `reports/eda/` (ej: `eda_demanda_urgencias_rm.md`) contienen correcciones cualitativas y manuales, por lo que **no son sobreescritos automáticamente por el orquestador**. La excepción es `eda_contexto_genero_estadisticas_genero.md`, que es un perfil reproducible generado por `eda_contexto_genero`; el script de EDA de Urgencias genera únicamente las tablas (`.csv`) asociadas que sustentan sus reportes curados.

## 8. Ejecutar Pruebas (Tests)

Para ejecutar las pruebas unitarias y de validación de arquitectura:

```bash
pytest tests/
```
