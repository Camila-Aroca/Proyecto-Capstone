# Diccionario de datos: `mart_urgencias_comuna_etario_monthly`

- **Ruta:** `data/processed/marts/mart_urgencias_comuna_etario_monthly.parquet`
- **Constructor:** `src/data/build_urgencias_comuna_etario_mart.py` (`build_comuna_etario_monthly_mart`), stage `build_urgencias_comuna_etario_mart` en `PIPELINE.md`.
- **Grano:** una fila = `comuna_codigo` × `ano` × `mes` × `grupo_etario_urgencia` (formato largo). Mismo mes calendario que `mart_urgencias_comuna_monthly`.
- **Cobertura observada:** 51 de las 52 comunas RM (falta Vitacura, `13132`, igual que los demás marts comunales de Urgencias), 2021-2025, 5 grupos etarios × 3.060 combinaciones comuna×mes = 15.300 filas en total.
- **Fuente:** DEIS/MINSAL, Atenciones de Urgencia RM 2021-2025 (`data/processed/urgencias/urgencias_rm_<año>.parquet`, producidos por `clean_urgencias`), usando los cinco desgloses etarios publicados por causa (`menores_1`, `de_1_a_4`, `de_5_a_14`, `de_15_a_64`, `de_65_y_mas`). No usa ninguna dimensión poblacional ni de sexo/género (Urgencias no contiene esa variable).
- **Construcción/derivación:** filtra únicamente `id_causa ∈ {1, 35, 36, 37, 38, 39, 40, 41}`; convierte los cinco grupos etarios (columnas anchas del origen) a formato largo (`grupo_etario_urgencia`), usando cada grupo como valor a sumar en lugar de `total`; agrega por comuna×mes×grupo_etario×causa; pivotea a columnas por causa. No genera meses ni grupos etarios ausentes, ni sustituye la ausencia de una causa por cero. Reutiliza `load_urgencias_source`, `aggregate_grain` y las validaciones de jerarquía causal de `src/data/build_urgencias_comuna_marts.py`.
- **No incluye `total` junto a los grupos etarios:** se verificó sobre 2021-2025 (todas las causas del contrato) que `total = menores_1 + de_1_a_4 + de_5_a_14 + de_15_a_64 + de_65_y_mas` en el 100% de los registros, sin nulos; mantener ambos duplicaría la misma cifra bajo dos nombres.
- **Sin reportantes ni tasas:** no incorpora `n_establecimientos_reportantes_*` (no aplica a este grano) ni población/tasas por 10.000 habitantes (esas tasas son territoriales, no etarias; extenderlas exigiría un denominador poblacional por grupo etario que no se construye aquí).

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `ano` | int32 | Año calendario. |
| `mes` | int32 | Mes calendario (1 a 12), derivado de `fecha`. |
| `fecha_mes` | string (fecha ISO `YYYY-MM-DD`) | Primer día del mes calendario (`ano`-`mes`-01). |
| `grupo_etario_urgencia` | string | Uno de los cinco grupos etarios publicados por DEIS en Urgencias: `menores_1`, `de_1_a_4`, `de_5_a_14`, `de_15_a_64`, `de_65_y_mas`. |
| `comuna_codigo` | string | Código único territorial (CUT) de la comuna RM. |
| `comuna_glosa` | string | Nombre de la comuna, tomado del origen DEIS. |
| `atenciones_id1` | int32 | Suma de atenciones del grupo etario, causa ID1 (total de atenciones de urgencia, todas las causas). |
| `atenciones_id35` | int32 | Suma de atenciones del grupo etario, causa ID35 (lesiones autoinfligidas intencionalmente, X60-X84). |
| `atenciones_id36` | int32 | Suma de atenciones del grupo etario, causa ID36 (agregado DEIS de salud mental); **no equivale al capítulo CIE-10 F00-F99 estricto** porque incluye ID37 (Ideación Suicida, R45.8). Subconjunto de ID1 dentro del mismo grupo etario. |
| `atenciones_id37` | int32 | Suma de atenciones del grupo etario, causa ID37 (ideación suicida, R45.8); componente de ID36, formalmente fuera de F00-F99. |
| `atenciones_id38` | int32 | Suma de atenciones del grupo etario, causa ID38 (trastornos mentales/comportamiento por sustancias psicoactivas, F10-F19); componente de ID36. |
| `atenciones_id39` | int32 | Suma de atenciones del grupo etario, causa ID39 (trastornos del humor/afectivos, F30-F39); componente de ID36. |
| `atenciones_id40` | int32 | Suma de atenciones del grupo etario, causa ID40 (trastornos neuróticos, relacionados con estrés y somatomorfos, F40-F48, incluye pánico F41.0); componente de ID36. |
| `atenciones_id41` | int32 | Suma de atenciones del grupo etario, causa ID41 (otros trastornos mentales no contenidos en las categorías anteriores); componente de ID36. |

## Advertencias e interpretación

- **ID36 ≠ F00-F99 estricto.** Igual advertencia que en los demás marts de Urgencias: ID36 incluye ID37 (R45.8), formalmente fuera del capítulo F00-F99.
- **Sin sexo/género.** Urgencias DEIS no contiene esta variable; este mart no la incorpora ni la infiere.
- No hay nulos en ninguna columna `atenciones_id*`: cuando una causa no tuvo atenciones en una comuna×mes×grupo etario, el pivot produce 0 (no fila ausente).
- La identidad `atenciones_id36 = atenciones_id37 + ... + atenciones_id41` se cumple **exactamente en el 100% de las 15.300 filas** (verificado por código); es la misma jerarquía DEIS que en los marts comunales, ahora confirmada también a nivel de grupo etario.
- Este mart reconcilia **exactamente** con `mart_urgencias_comuna_monthly` al sumar los 5 grupos etarios por `comuna_codigo`×`fecha_mes` para las 8 causas del contrato (verificado por código, `DataFrame.equals` = `True` en las 3.060 combinaciones comuna×mes).
- La distribución de ID36 por grupo etario (2021-2025) está fuertemente concentrada en adultos: `de_15_a_64` concentra ~82,7% del total ID36, seguido de `de_65_y_mas` (~9,9%) y `de_5_a_14` (~7,0%); `de_1_a_4` y `menores_1` son marginales (<0,4% cada uno). Ver `reports/eda/eda_mart_urgencias_comuna_etario.md`.
- No incluye datos de Egresos ni cruces a nivel de paciente/establecimiento entre Urgencias y Egresos (restricción invariante del proyecto).
