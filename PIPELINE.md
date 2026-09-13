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

El siguiente listado representa el orden topológico actual del DAG. El orquestador ejecuta únicamente las etapas necesarias según los outputs existentes, las dependencias, el `--stage` solicitado y el uso de `--force`

For Egresos, `download_deis` publishes the CSV in each ZIP through the
deterministic RAW contract `data/raw/egresos/egresos_<year>.csv`. The original
name of the CSV member published by DEIS is recorded in
`data/raw/provenance_manifest.json`, so `clean_egresos` does not depend on
historical filename variants.

1. `download_censo` → (Descarga Censo a RAW)
2. `download_deis` → (Descarga Urgencias y Egresos a RAW)
3. `download_establishments` → (Descarga Maestro Establecimientos a RAW)
4. `download_contexto_genero` → (Descarga RAW de cuatro cuadros XLSX de Estadísticas de Género)
5. `normalize_contexto_genero` → (Normalización independiente de los cuatro cuadros contextuales)
6. `clean_establishments` → (Limpieza y filtrado RM)
7. `clean_censo` → (Filtro espacial RM para Censo)
8. `build_catalogs` → (Creación de catálogo F00-F99)
9. `clean_urgencias` → (Limpieza de Urgencias 2020-2026 y unión territorial)
10. `clean_egresos` → (Normalización reproducible de Egresos Hospitalarios 2020-2025)
11. `eda_establishments` → (Validación EDA de Establecimientos)
12. `eda_urgencias` → (Generación de tablas base del EDA de Urgencias)
13. `profile_urgencias_sm_coverage` → (Perfil comuna×semana ID 36 para cobertura 2021–2025)
14. `build_urgencias_comuna_marts` → (Marts históricos comunales semanal y mensual de Urgencias, 2021–2025)
15. `eda_contexto_genero` → (EDA reproducible de los cuatro cuadros contextuales)

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

La etapa `build_urgencias_comuna_marts` depende de `clean_urgencias`, no tiene downstream por ahora y publica `data/processed/marts/mart_urgencias_comuna_weekly.parquet` y `data/processed/marts/mart_urgencias_comuna_monthly.parquet`. Sus inputs son los Parquet de Urgencias RM 2021–2025, con filtros de columnas e IDs 1, 35, 36 y 37–41. Cada métrica es un conteo agregado de atenciones; el mensual se agrega desde `fecha` diaria y el semanal conserva `ano`, `semana` y el mínimo `fecha` publicado como `fecha_inicio_semana`, sin convertir al calendario ISO. No imputa semanas, meses ni causas ausentes. Incluye los conteos reportantes ID1 e ID36; no incorpora el catálogo de establecimientos actual porque es un snapshot no histórico. Antes de publicar, valida grano, no negatividad, jerarquía ID36, ratios, reportantes y reconciliación anual semanal→mensual; ambos Parquet se escriben con temporal y reemplazo atómico. El orquestador valida existencia, tamaño y esquema, realiza `SKIP` cuando ambos outputs son válidos y los regenera con `--force`. Las pruebas están en `tests/test_build_urgencias_comuna_marts.py`.

## 7. Informes Históricos y Protegidos

Los reportes en Markdown dentro de la carpeta `reports/eda/` (ej: `eda_demanda_urgencias_rm.md`) contienen correcciones cualitativas y manuales, por lo que **no son sobreescritos automáticamente por el orquestador**. La excepción es `eda_contexto_genero_estadisticas_genero.md`, que es un perfil reproducible generado por `eda_contexto_genero`; el script de EDA de Urgencias genera únicamente las tablas (`.csv`) asociadas que sustentan sus reportes curados.

## 8. Ejecutar Pruebas (Tests)

Para ejecutar las pruebas unitarias y de validación de arquitectura:

```bash
pytest tests/
```
