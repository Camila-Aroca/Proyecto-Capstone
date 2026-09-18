# Diccionario de datos: `mart_urgencias_establecimiento_monthly`

- **Ruta:** `data/processed/marts/mart_urgencias_establecimiento_monthly.parquet`
- **Constructor:** `src/data/build_urgencias_establecimiento_mart.py` (`build_establecimiento_monthly_mart`), stage `build_urgencias_establecimiento_mart` en `PIPELINE.md`.
- **Grano:** una fila = `establecimiento_codigo` × `ano` × `mes` (mes calendario derivado de la `fecha` diaria del origen, igual convención que `mart_urgencias_comuna_monthly`).
- **Cobertura observada:** 152 establecimientos, 51 de las 52 comunas RM, período 2021-2025, 8.857 filas en total. No todos los establecimientos reportan los 60 meses posibles (139 de 152 sí; el resto reporta un subconjunto, sin imputar los meses ausentes con cero). Ver limitaciones.
- **Fuente:** DEIS/MINSAL, Atenciones de Urgencia RM 2021-2025 (`data/processed/urgencias/urgencias_rm_<año>.parquet`, producidos por `clean_urgencias`). No usa ninguna dimensión poblacional.
- **Construcción/derivación:** filtra únicamente `id_causa ∈ {1, 35, 36, 37, 38, 39, 40, 41}`; agrega, por establecimiento×mes×causa, la suma de `total` (atenciones); pivotea a columnas por causa; calcula proporciones internas. No genera meses ausentes ni sustituye la ausencia de una causa por cero. Reutiliza `load_urgencias_source`, `aggregate_grain`, `add_ratios` y las validaciones de jerarquía causal de `src/data/build_urgencias_comuna_marts.py`.
- **Atributos de establecimiento:** `comuna_codigo`, `comuna_glosa`, `establecimiento_glosa` y `tipo_establecimiento_urgencia` se incorporan como atributos del grano porque se verificó (2021-2025, sobre las 8 causas del contrato) que cada `establecimiento_codigo` reporta un único valor de cada uno — 152 de 152 establecimientos con exactamente 1 valor distinto por atributo, sin excepciones. Es una regla determinista respaldada por evidencia, no un supuesto.
- **Sin población ni tasas:** este mart deliberadamente no incorpora `poblacion_anual` ni tasas por 10.000 habitantes. La población comunal (`dim_poblacion_comuna_anual`) es un denominador territorial, no la población atendida por un establecimiento individual (varios establecimientos comparten comuna; un establecimiento puede atender residentes de otras comunas). Calcular una tasa por establecimiento con ese denominador sería un supuesto no respaldado por los datos disponibles.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `ano` | int32 | Año calendario. |
| `mes` | int32 | Mes calendario (1 a 12), derivado de `fecha`. |
| `fecha_mes` | string (fecha ISO `YYYY-MM-DD`) | Primer día del mes calendario (`ano`-`mes`-01). |
| `establecimiento_codigo` | int64 | Código DEIS del establecimiento (llave de grano junto con `fecha_mes`). |
| `comuna_codigo` | string | Código único territorial (CUT) de la comuna donde se ubica el establecimiento. |
| `comuna_glosa` | string | Nombre de la comuna, tomado del origen DEIS. |
| `establecimiento_glosa` | string | Nombre del establecimiento, tomado del origen DEIS. |
| `tipo_establecimiento_urgencia` | string | Tipo de establecimiento tal como lo reporta Urgencias (`Hospital`, `SAPU`, `SAR`, `SUR`, `CEAR`); no es el `tipo_establecimiento_glosa` del maestro de establecimientos. |
| `atenciones_id1` | int32 | Suma de atenciones, causa ID1 (total de atenciones de urgencia, todas las causas). |
| `atenciones_id35` | int32 | Suma de atenciones, causa ID35 (lesiones autoinfligidas intencionalmente, X60-X84). |
| `atenciones_id36` | int32 | Suma de atenciones, causa ID36 (agregado DEIS de salud mental); **no equivale al capítulo CIE-10 F00-F99 estricto** porque incluye ID37 (Ideación Suicida, R45.8). Subconjunto de ID1. |
| `atenciones_id37` | int32 | Suma de atenciones, causa ID37 (ideación suicida, R45.8); componente de ID36, formalmente fuera de F00-F99. |
| `atenciones_id38` | int32 | Suma de atenciones, causa ID38 (trastornos mentales/comportamiento por sustancias psicoactivas, F10-F19); componente de ID36. |
| `atenciones_id39` | int32 | Suma de atenciones, causa ID39 (trastornos del humor/afectivos, F30-F39); componente de ID36. |
| `atenciones_id40` | int32 | Suma de atenciones, causa ID40 (trastornos neuróticos, relacionados con estrés y somatomorfos, F40-F48, incluye pánico F41.0); componente de ID36. |
| `atenciones_id41` | int32 | Suma de atenciones, causa ID41 (otros trastornos mentales no contenidos en las categorías anteriores); componente de ID36. |
| `proporcion_id36_sobre_id1` | float64 | `atenciones_id36 / atenciones_id1`; nulo si `atenciones_id1` es 0. |
| `proporcion_id37_sobre_id36` … `proporcion_id41_sobre_id36` | float64 | Cada componente ID37-ID41 dividido por `atenciones_id36`; nulo si `atenciones_id36` es 0. |

## Advertencias e interpretación

- **ID36 ≠ F00-F99 estricto.** ID36 es la suma DEIS de ID37+38+39+40+41; ID37 es formalmente R45.8 (Ideación Suicida), no un código F. Cualquier comparación con el F00-F99 de Egresos debe decidir explícitamente si excluye ID37.
- Los ratios (`proporcion_*`) quedan explícitamente nulos cuando su denominador es 0 o está ausente; nunca se sustituyen por 0. En este mart, `proporcion_id36_sobre_id1` es nulo en 14 de 8.857 filas y cada `proporcion_id37..41_sobre_id36` es nulo en 497 filas (establecimiento×mes sin ninguna atención ID36 en ese período).
- No hay nulos en ninguna columna `atenciones_id*`: cuando una causa no tuvo atenciones en un establecimiento×mes presente, el pivot produce 0 (no fila ausente).
- No todos los establecimientos reportan los 60 meses posibles del período 2021-2025 (139 de 152 sí); los meses sin fila para un establecimiento no fueron imputados con cero, simplemente no existe fila (ver `reports/eda/eda_mart_urgencias_establecimiento.md`).
- Este mart reconcilia **exactamente** con `mart_urgencias_comuna_monthly` al sumar por `comuna_codigo`×`fecha_mes` para las 8 causas del contrato (verificado por código, `DataFrame.equals` = `True` en las 3.060 combinaciones comuna×mes).
- No incluye datos de Egresos ni cruces a nivel de paciente/establecimiento entre Urgencias y Egresos (restricción invariante del proyecto).
