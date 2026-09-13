# Diccionario de datos: `mart_urgencias_comuna_weekly`

- **Ruta:** `data/processed/marts/mart_urgencias_comuna_weekly.parquet`
- **Constructor:** `src/data/build_urgencias_comuna_marts.py` (`build_weekly_mart`), stage `build_urgencias_comuna_marts` en `PIPELINE.md`.
- **Grano:** una fila = `comuna_codigo` × `ano` × `semana`, con el calendario semanal tal como lo publica DEIS (no se convierte a semana ISO).
- **Cobertura observada:** 51 de las 52 comunas RM y 262 semanas por comuna (2021 a 2025), 13.362 filas en total. Falta la comuna Vitacura (`13132`); ver limitaciones.
- **Fuente:**
  - Atenciones: DEIS/MINSAL, Atenciones de Urgencia RM 2021-2025 (`data/processed/urgencias/urgencias_rm_<año>.parquet`, producidos por `clean_urgencias`).
  - Denominador poblacional: `data/processed/censo/dim_poblacion_comuna_anual.parquet` (INE, Estimaciones y Proyecciones de Población 2002-2035, base Censo 2017).
- **Construcción/derivación:** filtra únicamente `id_causa ∈ {1, 35, 36, 37, 38, 39, 40, 41}`; agrega, por comuna×semana×causa, la suma de `total` (atenciones) y el conteo de establecimientos distintos que reportaron (`nunique` de `establecimiento_codigo`); pivotea a columnas por causa; calcula proporciones internas y tasas por 10.000 habitantes uniendo la población anual (la misma cifra de población se reutiliza para las 52 semanas del año, sin interpolar semanal). No genera semanas ausentes ni sustituye la ausencia de una causa por cero.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `comuna_codigo` | string | Código único territorial (CUT) de la comuna RM. |
| `comuna_glosa` | string | Nombre de la comuna, tomado del origen DEIS. |
| `fecha_inicio_semana` | string (fecha ISO `YYYY-MM-DD`) | Fecha mínima observada en el origen para esa `ano`×`semana` DEIS; es un ancla informativa, no una conversión a semana ISO. |
| `ano` | int32 | Año calendario DEIS de la atención. |
| `semana` | int32 | Número de semana DEIS (1 a 53); no es la semana ISO-8601. |
| `atenciones_id1` | int32 | Suma de atenciones, causa ID1 (total de atenciones de urgencia, todas las causas). |
| `atenciones_id35` | int32 | Suma de atenciones, causa ID35 (lesiones autoinfligidas intencionalmente, X60-X84). |
| `atenciones_id36` | int32 | Suma de atenciones, causa ID36 (total trastornos mentales, F00-F99); subconjunto de ID1. |
| `atenciones_id37` | int32 | Suma de atenciones, causa ID37 (ideación suicida, R45.8); componente de ID36. |
| `atenciones_id38` | int32 | Suma de atenciones, causa ID38 (trastornos mentales/comportamiento por sustancias psicoactivas, F10-F19); componente de ID36. |
| `atenciones_id39` | int32 | Suma de atenciones, causa ID39 (trastornos del humor/afectivos, F30-F39); componente de ID36. |
| `atenciones_id40` | int32 | Suma de atenciones, causa ID40 (trastornos neuróticos, relacionados con estrés y somatomorfos, F40-F48, incluye pánico F41.0); componente de ID36. |
| `atenciones_id41` | int32 | Suma de atenciones, causa ID41 (otros trastornos mentales no contenidos en las categorías anteriores); componente de ID36. |
| `n_establecimientos_reportantes_id1` | int64 | Cantidad de establecimientos distintos que reportaron al menos una atención ID1 en esa comuna×semana. |
| `n_establecimientos_reportantes_id36` | int64 | Cantidad de establecimientos distintos que reportaron al menos una atención ID36 en esa comuna×semana. |
| `proporcion_id36_sobre_id1` | float64 | `atenciones_id36 / atenciones_id1`; nulo si `atenciones_id1` es 0. |
| `proporcion_id37_sobre_id36` … `proporcion_id41_sobre_id36` | float64 | Cada componente ID37-ID41 dividido por `atenciones_id36`; nulo si `atenciones_id36` es 0. |
| `poblacion_anual` | int64 | Población anual de la comuna (INE, proyecciones), igual para las 52 semanas del año. |
| `tasa_atenciones_id1_por_10000` | float64 | `atenciones_id1 / poblacion_anual × 10.000`. |
| `tasa_atenciones_id35_por_10000` | float64 | `atenciones_id35 / poblacion_anual × 10.000`. |
| `tasa_atenciones_id36_por_10000` | float64 | `atenciones_id36 / poblacion_anual × 10.000`. |

## Advertencias e interpretación

- **Las tasas son intensidad territorial de atenciones (evento), no prevalencia/incidencia ni personas únicas atendidas.** Una misma persona puede generar varias atenciones en la misma comuna×semana; la tasa no debe leerse como "% de población afectada".
- Los ratios (`proporcion_*`) quedan explícitamente nulos cuando su denominador es 0 o está ausente; nunca se sustituyen por 0.
- `n_establecimientos_reportantes_id1` y `n_establecimientos_reportantes_id36` son idénticos en el 100% de las filas observadas (ver EDA): los establecimientos que reportan ID1 son los mismos que reportan ID36 en la misma comuna×semana.
- La comuna Vitacura (`13132`) no tiene ninguna fila en este mart porque no registra atenciones para ninguna de las causas del contrato en `urgencias_rm_2021..2025`; no se imputó ni se completó con ceros. Ver `reports/eda/eda_mart_urgencias_comuna.md` para el detalle y la distinción entre hecho observado e hipótesis no confirmada.
- El calendario semanal es el publicado por DEIS (incluye semana 53 en años con 53 semanas DEIS); no coincide necesariamente con la semana ISO-8601.
- Este mart reconcilia exactamente con `mart_urgencias_comuna_monthly` al agregar por comuna×año (ver EDA); ambos comparten fuente y filtros de causa.
