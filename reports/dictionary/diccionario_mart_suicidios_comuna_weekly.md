# Diccionario de datos: `mart_suicidios_comuna_weekly`

- **Ruta:** `data/processed/marts/mart_suicidios_comuna_weekly.parquet`.
- **Constructor:** `src/data/build_mart_suicidios_comuna_weekly.py`, stage `build_mart_suicidios_comuna_weekly` (upstream: `clean_defunciones`, `clean_censo_poblacion`, `clean_poblacion_proyecciones`). EDA: `reports/eda/eda_mart_suicidios_comuna_weekly.md`.
- **Propósito:** serie semanal de suicidios de residentes de cada comuna RM, insumo del pronóstico de suicidios (`benchmark_suicidios`, `evaluate_holdout_suicidios`, `forecast_suicidios`) que el tablero muestra junto al de atenciones de urgencia, en su propio gráfico.
- **Fuente:** `data/processed/defunciones/defunciones_nacional.parquet` (DEIS, defunciones 2020 en adelante); población INE proyectada por comuna y año; universo y glosas de comunas de `dim_poblacion_comuna_censo2024`.

**Grano:** una fila por comuna de residencia RM y semana DEIS (`ano`, `semana`). **Llave lógica verificada:** `comuna_codigo, ano, semana`. Grilla completa: las 52 comunas en todas las semanas publicadas, incluidos los fragmentos `semana = 53`.

| Columna | Tipo | Semántica |
|---|---|---|
| `comuna_codigo` | string | Código CUT de la comuna de **residencia** declarada en la defunción (5 dígitos). No es el lugar del hecho ni de la defunción. |
| `comuna_glosa` | string | Nombre de la comuna (`dim_poblacion_comuna_censo2024`). |
| `ano` | int16 | Año **calendario** de la fecha de defunción (codificación DEIS). |
| `semana` | int16 | Semana epidemiológica de la fecha (domingo a sábado; la 1 contiene el 4 de enero). `53` = fragmento de comienzo o fin de año. |
| `fecha_inicio_semana`, `fecha_fin_semana` | date32 | Primer y último día de la semana dentro del año calendario. |
| `dias_semana` | int8 | Días de la semana (1 a 10). Las semanas regulares tienen 7 salvo en los bordes de año, donde DEIS suma o resta días (p. ej. 2025-S01 tiene 4 y 2024-S01 tiene 9). |
| `suicidios` | int32 | Defunciones con causa externa CIE-10 **X60-X84** (lesiones autoinfligidas intencionalmente). Cero = cero registrado. |
| `defunciones_total` | int32 | Defunciones por todas las causas de residentes de la comuna en la semana. Denominador de la regla de registro. |
| `poblacion_anual` | int64 | Población proyectada INE de la comuna en `ano` (no la censada 2024). |
| `registro_completo` | bool | False en semanas finales con alerta de rezago (reglas abajo); True en el resto, incluidos los fragmentos. True no certifica completitud. |

## Construcción

1. **Caso:** `codigo_categoria_diag2` entre X60 y X84. Se verifica en cada ejecución que coincida registro a registro con `codigo_grupo_diag2 = "X60-X84"`; si no, la etapa falla. `DIAG1` no sirve para esto: trae la naturaleza de la lesión (capítulos S/T).
2. **Territorio:** residentes RM (`comuna_codigo` con prefijo 13, idéntico a `region_glosa` RM en la fuente). Un residente RM con comuna fuera de las 52 hace fallar la etapa en vez de descartarse (en el snapshot vigente: 0).
3. **Calendario:** `semana_deis(fecha)` = (año calendario, semana epidemiológica), la regla con que DEIS codifica Urgencias. El EDA la verifica en todas las fechas de Urgencias 2020-2026 (2.467 fechas, 0 discrepancias).
4. **Corte:** solo semanas con todos sus días observados, hasta la última fecha de defunción del archivo nacional. Una semana que el corte deja truncada no se publica.
5. **Alerta de rezago:** desde la última semana hacia atrás, se marca `registro_completo = False` si el promedio diario semanal de defunciones por todas las causas de la RM cae bajo 0,75 veces la mediana de las 8 semanas anteriores, o si el último día de la semana cae bajo 0,5 veces la mediana de los 8 mismos días de semana anteriores. Cada regla deja de recorrer al encontrar una semana que supera su umbral. Sin ocho semanas de referencia no se aplica la alerta diaria. La regla no prueba que los datos restantes estén completos y puede no detectar rezagos en días interiores; ver la evaluación retrospectiva en `reports/validation/c08_revalidacion_20261110.md`.
6. **Ceros:** la base de defunciones es un registro censal; una comuna-semana sin defunciones registradas es cero, no ausencia de reporte (a diferencia de Urgencias, donde una semana sin fila no se imputa).
7. **Conciliación:** la suma de `suicidios` debe igualar las defunciones X60-X84 de residentes RM de la fuente en el período publicado (en el snapshot vigente, 3.943 = 3.943).

## Advertencias de interpretación

- Comuna de residencia: la relación con las atenciones de Urgencias (comuna del establecimiento) es solo ecológica; no hay cruce por persona.
- Son defunciones **registradas** con esa causa. Los eventos de intención no determinada (Y10-Y34) no se incluyen. Con un único snapshot no es posible medir revisiones posteriores de causa o inscripciones tardías más allá de la regla de registro.
- 2020-2021 tienen un nivel ~25% menor que 2022-2025 (ver EDA); la causa no es determinable con estos datos y el modelo empieza en 2022.
- Algunas semanas regulares no tienen 7 días: cualquier comparación entre semanas debe usar `dias_semana` (o tasas por día).
- Con pocos casos por comuna, las tasas comunales son inestables; el pronóstico las contrae hacia la tasa regional.
