# C-08: revalidación parcial del pipeline y procedencia (15 de noviembre de 2026)

Esta evidencia responde al [issue #108](https://github.com/Camila-Aroca/Proyecto-Capstone/issues/108). Registra una ejecución local sobre el commit base `5c341c513329838bcd837c6143ab286fde08f292`, con árbol Git limpio antes de comenzar. Los outputs generados y esta evidencia constituyen cambios posteriores a ese commit. No es una ejecución desde un clon limpio ni demuestra despliegue.

La dependencia U-39 corresponde al [issue #39](https://github.com/Camila-Aroca/Proyecto-Capstone/issues/39), sobre la ejecución de la suite completa y el registro separado de las pruebas de integración. La sección «Entorno y pruebas» documenta ambas ejecuciones y sus resultados. El issue #39 seguía abierto al consultarlo el 15-11; este informe no acredita su aceptación ni su cierre. C-08 también menciona las brechas GAP-004 y GAP-020, cuyo estado no se verificó aquí.

## Ejecución y alcance

El comando `.venv\Scripts\python.exe -B scripts\run_pipeline.py --sin-evaluacion --force` se inició el 15-11 a las 16:10:32 UTC y terminó a las 17:19:51 UTC con código 0: [metadatos](pipeline_meta.txt), [registro completo](pipeline.txt) y [estado previo](preflight.txt). El registro indica 53 etapas ejecutadas y exitosas; dentro de la descarga de Defunciones se reutilizó el paquete oficial 1990-2023. Se consultaron fuentes externas, se regeneraron datos, marts, EDA y los tres pronósticos. Hubo dos advertencias por el hospital 200063 repetido en 2024 y 2025 en el libro no SNSS; se conservaron todas las filas.

Se omitieron `benchmark_demanda_sm`, `benchmark_establecimientos_sm`, `benchmark_suicidios` y sus tres `evaluate_holdout_*`. Los pronósticos ajustan los modelos con las selecciones congeladas existentes, pero esta corrida no revalida su selección ni sus métricas. La evaluación con los datos actualizados sigue pendiente. Los resultados de octubre no deben presentarse como métricas del snapshot nuevo.

## Snapshots y outputs

| Fuente | Identificación de la ejecución | SHA256 del CSV RAW |
|---|---|---|
| Urgencias 2026 | Descargado el 15-11 a las 16:38 UTC. Fecha máxima observada en el Parquet RM: 14-11; no implica que ese día esté completo. | `7ee500a2999aa6d7a80f88bcb07db7d2fa25c4dd00f146a79c19381075a9d27c` |
| Defunciones preliminares 2024-2026 | Paquete `2024_2026_10112026`; fecha máxima de defunción 07-11. Los últimos días tienen rezago; el mart marca la semana 2026-S44. | `51bf6485bbc475fc122d36f78cda122be16cdc849c3f819681287b5d03f167d3` |

Ambos hashes se calcularon sobre los archivos locales. El historial de URL, fechas, hashes y otros snapshots está en `data/raw/provenance_manifest.json`; el detalle del rezago y sus límites está en la [evidencia del 10-11](../c08_revalidacion_20261110.md). Un hash identifica bytes, pero no garantiza la recuperación de un snapshot mutable desde su URL.

El [inventario](output_inventory.json) registra existencia y tamaño de los 144 outputs declarados al revisarlos; los 144 existían. Es una comprobación de presencia, no una validación de contenido ni de vigencia; 16 outputs corresponden a evaluaciones omitidas. Los [hashes](hashes.csv) identifican 101 archivos, incluidos los outputs procesados y reports declarados disponibles, el manifiesto de procedencia y los dos CSV indicados arriba. Los manifiestos de pronóstico identifican sus modelos, entradas y semanas observadas. La [comparación con octubre](processed_comparison.txt) es de hashes, no de filas ni equivalencia semántica: varios archivos son distintos y el holdout de demanda conserva los bytes de octubre.

## Entorno y pruebas

Python 3.12.6; las versiones instaladas están en [environment_freeze.txt](environment_freeze.txt). La suite ordinaria se ejecutó con `SAAD_QA_DATOS=1` y `--basetemp=.cache/c08_pytest_ordinary`: **920 aprobadas**, 29 de integración deseleccionadas, una advertencia de deprecación de Starlette. [Salida](tests_full.txt).

La integración se ejecutó con `python -B -m pytest tests/ -m data_integration --basetemp=.cache/c08_pytest_integration`, con acceso a los snapshots locales: **29 aprobadas**, 920 deseleccionadas y la misma advertencia. [Salida](tests_integration.txt). Entre ambas corridas se ejecutaron las 949 pruebas seleccionadas por sus respectivas marcas.

Para U-39 se repitieron ambas suites el 15-11 sobre el mismo commit base y árbol de trabajo con cambios sin commit. La suite ordinaria, con `SAAD_QA_DATOS=1` y `--basetemp=.cache/u39_pytest_ordinaria`, terminó con **920 aprobadas**, 29 deseleccionadas y una advertencia en 123,08 s ([salida](u39_tests_ordinarios.txt)). La integración, con `-m data_integration` y `--basetemp=.cache/u39_pytest_integracion`, terminó con **29 aprobadas**, 920 deseleccionadas y una advertencia en 384,89 s ([salida](u39_tests_integracion.txt)). La advertencia es la misma de deprecación de Starlette. Estas ejecuciones no equivalen a un clon limpio ni cierran por sí solas el issue #39.

El primer intento de la suite ordinaria se interrumpió tras errores de inicialización porque el sandbox denegó acceso al directorio temporal predeterminado de pytest. La repetición usó un directorio temporal dentro del proyecto; las pruebas que antes fallaban en esa fase pasaron. Los archivos de salida de pruebas y del pipeline se copiaron a texto UTF-8 y se reemplazaron rutas locales por referencias portables; los `.log` originales están ignorados por Git.

`git diff --check` señala dos espacios al final de una línea de `reports/eda/eda_mart_contexto_genero_indicador_sexo.md`, usados como salto de línea Markdown por su generador. Se conserva el output del pipeline sin editarlo manualmente. La comprobación de los cambios en README y el manual no encontró errores de whitespace.

La [certificación del 8 de octubre](../apt_certification_20261008T002147Z/pipeline_meta.txt) corresponde a otra versión y no certifica la versión de esta corrida. Tampoco debe entenderse esta evidencia como una validación integral del modelo ni como evidencia de instalación limpia o de despliegue.
