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

## 3. Ejecución por Etapa

Para ejecutar únicamente una fase específica (por ejemplo, limpiar las atenciones de urgencia):

```bash
python scripts/run_pipeline.py --stage clean_urgencias
```

## 4. Forzar Regeneración (Force)

Si deseas forzar la ejecución de una etapa (o de todo el pipeline) ignorando la regla de salto, añade el flag `--force`:

```bash
python scripts/run_pipeline.py --stage download_censo --force
```

## 5. Orden de Ejecución (DAG)

Se han dispuesto los scripts en `src/data/` para encapsular la ingesta y descarga.

> [!WARNING]
> La serie de atenciones del año en curso (2026) es una fuente mutable. El DEIS sobrescribe periódicamente el archivo ZIP sin versionado. Por lo tanto, ejecutar el mismo pipeline en fechas distintas descargará snapshots diferentes. Para mitigar esto, los scripts de descarga generan y actualizan un registro ligero de auditoría en `data/raw/provenance_manifest.json` con el SHA256 de lo descargado.

El orquestador ejecutará las etapas estrictamente en este orden:

1. `download_censo` → (Descarga Censo a RAW)
2. `download_deis` → (Descarga Urgencias y Egresos a RAW)
3. `download_establishments` → (Descarga Maestro Establecimientos a RAW)
4. `clean_establishments` → (Limpieza y filtrado RM)
5. `clean_censo` → (Filtro espacial RM para Censo)
6. `build_catalogs` → (Creación de catálogo F00-F99)
7. `clean_urgencias` → (Limpieza de Urgencias 2020-2026 y unión territorial)
8. `clean_egresos` → (Normalización reproducible de Egresos Hospitalarios 2020-2025)
9. `eda_establishments` → (Validación EDA de Establecimientos)
10. `eda_urgencias` → (Generación de tablas base del EDA de Urgencias)

## 6. Lógica de Idempotencia (Skip)

El orquestador no sobrescribe ciegamente. Antes de lanzar cada módulo, `run_pipeline.py` verifica la existencia de archivos clave (outputs) de esa etapa (y que su tamaño sea > 0 bytes). Si todos los outputs esperados existen, el script asume que la etapa ya fue ejecutada y la salta automáticamente, ahorrando tiempo y peticiones a la red.

## 7. Informes Históricos y Protegidos

Los reportes en Markdown dentro de la carpeta `reports/` (ej: `eda_demanda_urgencias_rm.md`) contienen correcciones cualitativas y manuales, por lo que **no son sobreescritos automáticamente por el orquestador**. El script de EDA genera únicamente las tablas (`.csv`) asociadas que sustentan los reportes.

## 8. Ejecutar Pruebas (Tests)

Para ejecutar las pruebas unitarias y de validación de arquitectura:

```bash
pytest tests/
```
