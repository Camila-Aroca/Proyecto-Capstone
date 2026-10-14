# Cierre técnico #40: fixtures mínimos de tests de datos

Fecha: 14 de octubre de 2026. Criterio: los tests críticos corren sin datasets
masivos. Evidencia asociada a los cambios de esta tarea sobre `63b8010`.

## Implementación

- `tests/conftest.py` contiene generadores sintéticos versionados: cartografía
  comunal de 53 filas (52 CUT RM y una comuna externa), catálogos de
  establecimientos de 1/2 filas y CSV antiguos de Urgencias de 6 filas para
  2020 y 2022. Se materializan exclusivamente en `tmp_path`.
- Los tests de Censo verifican filtrado, cobertura de 52 comunas, geometrías,
  CRS, conservación de metadata y rechazo de cobertura incompleta.
- Urgencias prueba códigos antiguos/nuevos, clasificación RM/no RM/sin
  territorio, formatos sin región y con región, esquema, conteos, escritura
  por bloques y SHA256 de origen. Se conservan íntegros los cuerpos de los
  tests sobre el maestro vigente y Urgencias 2020 ajustados por el equipo.
- Los dos tests del mart contextual que leían procesados locales usan ahora
  6 observaciones sintéticas; mantienen sus comprobaciones de reconciliación,
  períodos publicados, PHQ-4 con año nulo y símbolo `-`.
- `pytest.ini` identifica 17 comprobaciones de snapshots oficiales como
  `data_integration`. La ejecución habitual las excluye explícitamente; se
  mantienen disponibles, sin convertir faltantes de datos en éxitos. Se
  incluyen las comprobaciones de existencia de RAW/output y reconciliación
  real de Egresos detectadas al ejecutar sin `data/`.

Los valores de los fixtures son ejemplos de prueba, no resultados analíticos
ni reemplazos de fuentes oficiales. No se modificaron código productivo,
datos, dependencias, DAG, contratos de salida ni diagramas.

## Ejecución

Desde la raíz, con el entorno del proyecto activado:

```powershell
# Suite habitual, independiente de datasets locales
python -B -m pytest tests/ -q -p no:cacheprovider --basetemp=.cache/pytest-unit

# Solo integración, con snapshots locales disponibles
python -B -m pytest tests/ -m data_integration -q -p no:cacheprovider --basetemp=.cache/pytest-integration

# Toda la suite, incluyendo integración
python -B -m pytest tests/ -o addopts= -q -p no:cacheprovider --basetemp=.cache/pytest-all

python -B scripts/run_pipeline.py --help
git diff --check
```

`--basetemp` debe apuntar a una carpeta dedicada a tests: pytest puede
reemplazar su contenido. `.cache/` está ignorada por Git.

## Prueba aislada sin datasets

Se ejecutó toda la suite habitual en una copia temporal que contiene solo
`src/`, `scripts/`, `tests/`, `infra/`, `pytest.ini` y dos textos versionados:
la auditoría usada por el importador de GitHub y la selección del benchmark
usada por un test de persistencia. No se copió `data/` ni ningún resultado
tabular o geoespacial. El proceso usa la misma instalación de dependencias;
no es una prueba de reinstalación del entorno.

Código para reproducir desde Python, situado en la raíz del proyecto:

```python
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path.cwd()
python = Path(sys.executable).resolve()
cache = root / ".cache"
cache.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="issue40-without-data-", dir=cache) as directory:
    isolated = Path(directory)
    assert isolated.resolve().is_relative_to(cache.resolve())
    for name in ("src", "scripts", "tests", "infra"):
        shutil.copytree(root / name, isolated / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in (
        "pytest.ini",
        "reports/project/PROJECT_STATUS_AUDIT_2026-08-31.md",
        "reports/modeling/benchmark_demanda_sm_seleccion.json",
    ):
        target = isolated / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    assert not (isolated / "data").exists()
    temporary = isolated / ".tmp"
    temporary.mkdir()
    env = dict(os.environ, PYTHONPATH=str(isolated), PYTHONDONTWRITEBYTECODE="1",
               TMP=str(temporary), TEMP=str(temporary))
    result = subprocess.run(
        [str(python), "-B", "-m", "pytest", "tests/", "-q",
         "-p", "no:cacheprovider", "--basetemp=.tmp/pytest"],
        cwd=isolated, env=env,
    )
    code = result.returncode
raise SystemExit(code)
```

Salida observada:

```text
451 passed, 17 deselected, 1 warning in 69.07s
ISOLATED exit_code=0
```

La advertencia corresponde a la deprecación de `httpx` en el TestClient de
Starlette/FastAPI. Las 17 pruebas excluidas requieren snapshots oficiales;
no forman parte de la demostración sin datasets.

## Controles adicionales

La suite completa, incluidas las 17 integraciones, se ejecutó con:

```powershell
python -B -m pytest tests/ -o addopts= -q -p no:cacheprovider --basetemp=.cache/pytest-issue40-all --junitxml=.cache/issue40-all.xml
```

Salida final:

```text
468 passed, 1 warning in 165.63s (0:02:45)
exit_code=0
```

Los reportes JUnit locales están en `.cache/issue40-directed.xml`,
`.cache/issue40-isolated.xml` y `.cache/issue40-all.xml`; `.cache/` no se
versiona. Esta nota conserva los comandos y resultados de cierre.

La primera ejecución con el temporal predeterminado de pytest falló por
permisos del entorno; se resolvió usando `.cache/`. La primera ejecución de
integración tuvo 7 aprobadas y 4 fallidas por `PermissionError` al leer la
cartografía distrital dentro del sandbox; la ejecución completa posterior,
con acceso de lectura habilitado, aprobó las 468 pruebas. No se relajaron
sus validaciones y no quedan fallos pendientes en esas ejecuciones finales.

`python -B scripts/run_pipeline.py --help` terminó con código 0. No se
ejecutó el pipeline de datos: los fixtures son insumos de tests y no producen
outputs canónicos.
