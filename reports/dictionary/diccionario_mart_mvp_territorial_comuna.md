# Diccionario de datos: `mart_mvp_territorial_comuna`

- **Ruta:** `data/processed/marts/mart_mvp_territorial_comuna.parquet`
- **Constructor:** `src/data/build_mart_mvp_territorial_comuna.py` (`build_mart_mvp_territorial_comuna`), stage `build_mart_mvp_territorial_comuna` en `PIPELINE.md`.
- **Grano:** una fila = una comuna de la Región Metropolitana. **52 filas, 52 `comuna_codigo` únicos.**
- **Universo:** `dim_poblacion_comuna_censo2024.parquet` (dimensión ya validada contra el CUT oficial RM), **no** Urgencias. Por eso una comuna sin ninguna atención reportada en 2025 permanece en el mart, con sus métricas de demanda en NULL.
- **No es un mart de accesibilidad territorial**: no calcula centroides, distancias, isócronas, cobertura poblacional ni scores/rankings compuestos. Es exclusivamente la integración tabular comunal de cinco fuentes ya construidas y validadas.

## Cinco temporalidades distintas, nunca mezcladas

| Bloque | Corte/período | Constante en el mart | Fuente |
|---|---|---|---|
| Demanda de Urgencia | Año cerrado 2025 | `ano_demanda=2025` | `mart_urgencias_comuna_monthly.parquet`, `urgencias_rm_2025.parquet` |
| Población proyectada | 2025 | `ano_poblacion=2025` | `dim_poblacion_comuna_anual.parquet` (INE, proyección base Censo 2017) |
| Población censada | 2024 | `ano_censo=2024` | `dim_poblacion_comuna_censo2024.parquet` |
| Vulnerabilidad socioeconómica | 2022 (único período) | `ano_vulnerabilidad=2022` | `dim_vulnerabilidad_comuna.parquet` (Casen 2022, SAE) |
| Oferta de urgencia | Snapshot ACTUAL (no 2025) | `oferta_temporalidad="snapshot_actual"` | `dim_oferta_urgencia_rm.parquet` (174 establecimientos vigentes) |

## Construcción/derivación

- **Demanda 2025:** se agregan `atenciones_id1`, `atenciones_id35`, `atenciones_id36` sumando los 12 meses de `mart_urgencias_comuna_monthly` para `ano=2025` (nunca sumando ni promediando tasas ya calculadas). Las tasas por 10.000 habitantes se **recalculan** aquí como `atenciones_2025 / poblacion_2025 × 10.000`, no se reutilizan ni agregan las tasas mensuales del mart de origen.
- **Establecimientos reportantes únicos anuales:** se derivan directamente de `urgencias_rm_2025.parquet` (`nunique` de `establecimiento_codigo` por comuna×`id_causa` sobre el año completo), no sumando los conteos mensuales de `n_establecimientos_reportantes_id1`/`id36` del mart de origen, porque un mismo establecimiento que reporta en varios meses se duplicaría.
- **Cobertura territorial:** las 52 comunas están presentes siempre. `tiene_reporte_urgencias=False` identifica una comuna sin ninguna fila de Urgencias 2025; en ese caso, todas las columnas de demanda (conteos, tasas y reportantes) quedan en NULL, nunca en 0.
- **Población:** `poblacion_2025` (proyección INE) y `poblacion_censada_2024` (Censo) se mantienen como columnas separadas; no se sustituye una por otra.
- **Vulnerabilidad:** join `one_to_one` por `comuna_codigo` contra `dim_vulnerabilidad_comuna` (52/52). Columnas renombradas con sufijo `_vulnerabilidad` para evitar ambigüedad con las demás columnas `ano_*`/`indicador_*` del mart (p. ej. `ano_referencia` → `ano_vulnerabilidad`, `intervalo_confianza_inferior` → `intervalo_confianza_inferior_vulnerabilidad`).
- **Oferta:** se agrega `dim_oferta_urgencia_rm` por `comuna_codigo`. Los conteos por tipo (`n_hospitales`, `n_sapu`, `n_sar`, `n_sur`, `n_otras_excepciones`) son mutuamente excluyentes y suman exactamente `n_oferta_urgencia_actual`; el total agregado sobre las 52 comunas reconcilia exactamente con los 174 establecimientos de `dim_oferta_urgencia_rm`. Una comuna sin ningún establecimiento tendría `n_oferta_urgencia_actual=0` (hecho observado, no ausencia de dato); en el snapshot vigente las 52 comunas RM tienen al menos un establecimiento.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `comuna_codigo` | string | CUT de 5 dígitos (`13xxx`), del universo comunal validado. |
| `comuna_glosa` | string | Nombre de la comuna. |
| `ano_demanda` | int32 | Constante `2025`. Año cerrado de corte de la demanda de Urgencia. |
| `tiene_reporte_urgencias` | bool | `True` si la comuna tiene al menos una fila en `mart_urgencias_comuna_monthly` para `ano=2025`. `False` implica todas las columnas de demanda en NULL (Vitacura, `13132`, en el snapshot vigente). |
| `atenciones_id1_2025` | Int64 (nulable) | Suma anual 2025 de atenciones ID1 (total urgencia, todas las causas). NULL si `tiene_reporte_urgencias=False`. |
| `atenciones_id35_2025` | Int64 (nulable) | Suma anual 2025 de atenciones ID35 (lesiones autoinfligidas intencionalmente, X60-X84). |
| `atenciones_id36_2025` | Int64 (nulable) | Suma anual 2025 de atenciones ID36 (trastornos mentales, F00-F99); subconjunto de ID1. |
| `n_establecimientos_reportantes_id1_2025` | Int64 (nulable) | Establecimientos distintos que reportaron al menos una atención ID1 en 2025 (derivado del año completo, no sumado desde meses). |
| `n_establecimientos_reportantes_id36_2025` | Int64 (nulable) | Ídem para ID36. |
| `tasa_atenciones_id1_2025_por_10000` | float64 (nulable) | `atenciones_id1_2025 / poblacion_2025 × 10.000`. Recalculada, no agregada desde tasas mensuales. |
| `tasa_atenciones_id35_2025_por_10000` | float64 (nulable) | Ídem, causa ID35. |
| `tasa_atenciones_id36_2025_por_10000` | float64 (nulable) | Ídem, causa ID36. |
| `ano_poblacion` | int32 | Constante `2025`. |
| `poblacion_2025` | int64 | Población proyectada INE 2025 (base Censo 2017), denominador de las tasas de este mart. Siempre > 0. |
| `ano_censo` | int32 | Constante `2024`. |
| `poblacion_censada_2024` | int64 | Población efectivamente censada en 2024. **No** es intercambiable con `poblacion_2025`: son dos semánticas poblacionales distintas y la diferencia observada entre ambas no se corrige ni se fuerza a coincidir. Siempre > 0. |
| `ano_vulnerabilidad` | int32 | Constante `2022`. |
| `indicador_vulnerabilidad` | float64 | Tasa de pobreza por ingresos 2022 (proporción 0-1, estimación SAE). Completa 52/52. |
| `nombre_indicador_vulnerabilidad` | string | Glosa del indicador. |
| `direccion_indicador_vulnerabilidad` | string | Constante `"mayor_valor_mayor_vulnerabilidad"`. |
| `intervalo_confianza_inferior_vulnerabilidad` | float64 | Límite inferior del intervalo de confianza SAE. |
| `intervalo_confianza_superior_vulnerabilidad` | float64 | Límite superior del intervalo de confianza SAE. |
| `tipo_estimacion_sae` | string | `"Directa y Sintética (Fay-Herriot)"` o `"Sintética"` según la comuna (ver `diccionario`/EDA de `dim_vulnerabilidad_comuna`). |
| `oferta_temporalidad` | string | Constante `"snapshot_actual"`. La oferta describe el catálogo vigente hoy, no la oferta de 2025. |
| `n_oferta_urgencia_actual` | int64 | Establecimientos de oferta de urgencia vigentes en la comuna (snapshot actual). |
| `n_hospitales` | int64 | Subconjunto de `n_oferta_urgencia_actual` con `tipo_establecimiento="Hospital"`. |
| `n_sapu` | int64 | Subconjunto con acrónimo `(SAPU)`. |
| `n_sar` | int64 | Subconjunto con acrónimo `(SAR)`. |
| `n_sur` | int64 | Subconjunto con acrónimo `(SUR)`. |
| `n_otras_excepciones` | int64 | Subconjunto con `criterio_inclusion_oferta="excepcion_cear_documentada"` (excepción CESFAM documentada en `dim_oferta_urgencia_rm`). |
| `n_oferta_con_coordenadas` | int64 | Subconjunto de `n_oferta_urgencia_actual` con `latitud`/`longitud` no nulas. |
| `proporcion_oferta_con_coordenadas` | float64 (nulable) | `n_oferta_con_coordenadas / n_oferta_urgencia_actual`. NULL si `n_oferta_urgencia_actual=0` (denominador cero, nunca se sustituye por 0/1). |

## Advertencias e interpretación

- **Las tasas de demanda son intensidad territorial de atenciones (evento), no prevalencia/incidencia ni personas únicas atendidas** (ver advertencia equivalente en `diccionario_mart_urgencias_comuna_monthly.md`).
- **NULL ≠ 0** en las columnas de demanda: `tiene_reporte_urgencias=False` es la señal explícita de ausencia de reporte, no de actividad nula confirmada.
- La vulnerabilidad (2022) y la oferta (snapshot actual) **no describen 2025**; sus columnas de temporalidad (`ano_vulnerabilidad`, `oferta_temporalidad`) existen precisamente para evitar esa lectura errónea.
- Este mart no reemplaza a `mart_urgencias_comuna_monthly`/`weekly` (series temporales) ni a `dim_oferta_urgencia_rm` (grano establecimiento); es una integración comunal de corte único pensada como insumo MVP, no un mega-mart histórico.
- No contiene ninguna medida de accesibilidad territorial (tiempos de viaje, cobertura poblacional por isócrona, distancias): esa capa aún no está implementada (ver `PROJECT_CONTEXT.md`).

Ver `reports/eda/eda_mart_mvp_territorial_comuna.md` para el detalle reproducible (cobertura, reconciliaciones y distribución descriptiva).
