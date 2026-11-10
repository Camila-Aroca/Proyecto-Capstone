# Revalidación C-08: pipeline y procedencia (10 de noviembre de 2026)

Esta evidencia corresponde a una ejecución local sobre la base Git `e7a55db0dfa5cd65dba74333b52cc85eb530002d` y los cambios sin commit de C-08. No sustituye una ejecución desde un clon limpio ni acredita despliegue. La [certificación del 8 de octubre](apt_certification_20261008T002147Z/pipeline_meta.txt) corresponde a otra versión y no certifica esta.

## Snapshots consultados

| Fuente | Corte y procedencia observados | SHA256 del CSV RAW |
|---|---|---|
| Urgencias 2026 | Descarga del 10-11; fecha máxima observada 09-11; un día hasta la fecha de ejecución. | `e58789a1ea3cbdd7d085f9d1b837933ccf6a22d0c63831b37cd2cc89e10ca5ab` |
| Defunciones preliminares 2024–2026 | Paquete publicado en el catálogo DEIS con fecha 10-11; fecha máxima en los datos 07-11. | `51bf6485bbc475fc122d36f78cda122be16cdc849c3f819681287b5d03f167d3` |
| Defunciones preliminares anterior | Paquete con fecha 27-10; fecha máxima en los datos 24-10. Se conserva localmente para comparar revisiones. | `01cd5779ede07925716c1f01561f87f0e73e3a870bf7fbdb2a217b1a0eed82ea` |

Las URL, hashes de transporte y fechas UTC están registrados en `data/raw/provenance_manifest.json`. El [catálogo DEIS](https://deis.minsal.cl/#datosabiertos) identifica el paquete reciente como preliminar y de actualización semanal. El RAW de cada corte puede no estar disponible en un clon nuevo: el hash identifica sus bytes pero no permite recuperarlos por sí solo.

## Rezago observado de Defunciones

La fecha máxima del corte 10-11 es 07-11, tres días antes; **eso no es una medición de completitud**. Contando registros nacionales por `FECHA_DEF`, el corte 10-11 tiene 313 para el 05-11, 175 para el 06-11 y 14 para el 07-11. Los conteos caen en las fechas más recientes; no hay evidencia suficiente para afirmar que el último día esté completo.

Al comparar los dos cortes disponibles por fecha de defunción, el 23-10 pasa de 151 a 334 registros y el 24-10 de 20 a 278. Son cambios netos entre publicaciones, que pueden incluir inscripciones y revisiones; el segundo corte aún es preliminar. Dos snapshots no permiten determinar el retraso definitivo de inscripción, la completitud real, ni una demora fija aplicable a cada causa. El mart de suicidios aplica su propia regla para marcar semanas finales con registro incompleto; es una detección, no una certificación de completitud.

En residentes RM, el 07-11 tiene 14 registros de todas las causas frente a una mediana de 124 para los ocho sábados anteriores. La regla semanal previa no detectaba esa caída: para 2026-S44 la razón semanal era 0,797, superior al umbral 0,75. Se añade una alerta para el último día inferior a la mitad de la mediana de los ocho días de semana equivalentes. En el corte actual, entre 01-03-2021 y 31-12-2025, el mínimo de esa razón diaria fue 0,651 y ninguno de los 1.767 días cayó por debajo de 0,5. Es una comprobación retrospectiva y la regla se eligió tras ver el corte actual: no es validación prospectiva ni detecta necesariamente retrasos en otros días de la semana.

Para reproducir estos conteos con ambos CSV locales conservados, leer `FECHA_DEF` como fecha ISO (`%Y-%m-%d`) y agrupar por fecha contando filas. No enlazar registros individuales ni sumar snapshots entre sí. Los CSV contienen el mismo período y el consolidado usa únicamente el preliminar más reciente.

```python
from pathlib import Path
import pandas as pd

root = Path("data/raw/defunciones")
for key in ("2024_2026_27102026", "2024_2026_10112026"):
    path = root / key / f"DEFUNCIONES_FUENTE_DEIS_{key}.csv"
    dates = pd.read_csv(path, sep=";", encoding="latin-1", usecols=["FECHA_DEF"])
    dates["fecha"] = pd.to_datetime(dates["FECHA_DEF"], format="%Y-%m-%d", errors="coerce")
    counts = dates.groupby("fecha").size()
    print(key, counts.loc["2026-10-23":"2026-11-07"].to_string())
```

## Entorno

Python 3.12.6; pytest 9.1.1; pandas 3.0.5; NumPy 2.5.2; PyArrow 25.0.1; scikit-learn 1.9.1; statsmodels 0.15.0; LightGBM 4.7.0. `pip check` no informó dependencias rotas.

## Ejecución y límites

- `python scripts/run_pipeline.py --refresh-current-urgencias` terminó con éxito: descargó el snapshot nuevo, regeneró `urgencias_rm_2026.parquet` y ejecutó `eda_urgencias`.
- Se ejecutaron `--stage forecast_demanda_sm --force` y `--stage forecast_establecimientos_sm --force` antes de la instrucción de detener el pipeline antes del entrenamiento. Ambos finalizaron con semana 2026-S44 como última semana observada.
- La descarga de Defunciones, EDA RAW, consolidación, mart semanal y EDA del mart terminaron; el consolidado verificó 884.580 filas. El mart marca 2026-S44 con alerta de rezago.
- **El pipeline se interrumpió a solicitud del usuario antes de completar el benchmark de suicidios.** El benchmark había iniciado dos baselines; no se completaron el benchmark, holdout ni pronóstico de suicidios posteriores al nuevo mart. No se ejecutó una evaluación final del DAG completo.
- El manifiesto del pronóstico de suicidios registra para el mart el SHA256 `7d103046636fc5d8743fb88ac933841e1d6dbcdc17b94f4c32c713193c593b8e`; el mart actual tiene `9f82ff74a16e499a7aaa9e96e0282ff97fa7ee3fdf9ed1c3e0c950acee9067bb`. El pronóstico está desactualizado y no debe presentarse como resultado del snapshot nuevo.
- Suite ordinaria con `SAAD_QA_DATOS=1`: **838 aprobadas**, incluidas las siete de caracterización; 29 pruebas de integración excluidas por `pytest.ini`. Duración 132,30 s.
- Integración real con `pytest tests/ -m data_integration`: **29 aprobadas**, 838 deseleccionadas por el filtro. Duración 264,63 s. Entre ambas ejecuciones se cubrieron las 867 pruebas, sin omisiones; una advertencia de deprecación de Starlette no hizo fallar las pruebas.

La selección de snapshots y la regla de alerta cambian inputs y clasificación de semanas, no el grano, las claves ni el esquema del mart; por ello no se requiere modificar ERD, DDL ni UML para estos cambios.
