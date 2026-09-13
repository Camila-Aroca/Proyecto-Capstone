# EDA — `mart_mvp_territorial_comuna`

**Script reproducible:** `scripts/eda_mart_mvp_territorial_comuna.py`
**Tabla de apoyo:** [`eda_mart_mvp_territorial_comuna_resumen.csv`](eda_mart_mvp_territorial_comuna_resumen.csv)
**Archivo analizado:** `data/processed/marts/mart_mvp_territorial_comuna.parquet`

Este informe es descriptivo y de control de calidad (QA): reporta valores observados y sus reconciliaciones contra las fuentes de origen. No contiene conclusiones causales ni hipótesis sobre por qué una comuna tiene mayor o menor demanda/vulnerabilidad/oferta.

## 1. Forma y grano

- **52 filas × 32 columnas.**
- `comuna_codigo` único en las 52 filas (0 duplicados).
- El universo de comunas proviene de `dim_poblacion_comuna_censo2024` (validada contra el CUT oficial RM), no de Urgencias.

## 2. Cobertura de reporte de Urgencias 2025

- **51 de 52 comunas** tienen al menos una fila en `mart_urgencias_comuna_monthly` para `ano=2025`.
- **Vitacura (`13132`) es la única comuna sin reporte** de Urgencias 2025 (hecho observado, consistente con `diccionario_mart_urgencias_comuna_monthly.md`, que documenta la misma ausencia para el período 2021-2025 completo).
- En esa fila, **todas** las columnas de demanda (`atenciones_id1_2025`, `atenciones_id35_2025`, `atenciones_id36_2025`, ambas tasas y ambos conteos de reportantes) son NULL, verificado explícitamente (`isna().all()` = `True` para las 8 columnas). No se sustituyó por 0.
- Vitacura sí tiene valores válidos en población (`poblacion_2025=96.671`, `poblacion_censada_2024=86.420`), vulnerabilidad (`indicador_vulnerabilidad=0,00891`, la más baja de las 52 comunas) y oferta (`n_oferta_urgencia_actual=1`, un SAPU), porque esas tres fuentes no dependen del reporte de Urgencias.

## 3. Constantes de temporalidad

Verificadas como valor único en las 52 filas:

| Columna | Valor único observado |
|---|---|
| `ano_demanda` | `2025` |
| `ano_poblacion` | `2025` |
| `ano_censo` | `2024` |
| `ano_vulnerabilidad` | `2022` |
| `oferta_temporalidad` | `"snapshot_actual"` |

Ninguna fila mezcla un período con la etiqueta de otro.

## 4. Población

| Métrica | `poblacion_2025` (INE, proyección) | `poblacion_censada_2024` (Censo) |
|---|---|---|
| Mínimo | 7.954 | 7.768 |
| Mediana | 126.067 | 114.782 |
| Máximo | 671.142 | 568.086 |

Ambas columnas son positivas en las 52 comunas. Se observa una diferencia sistemática entre proyección INE y censo efectivo (esperable dado que son dos mediciones metodológicamente distintas, ver `PROJECT_CONTEXT.md`); el mart no corrige ni reconcilia esta diferencia, solo la mantiene visible en columnas separadas.

## 5. Vulnerabilidad (Casen 2022)

- `indicador_vulnerabilidad` completo en **52/52** comunas.
- Rango observado: 0,0089 (Vitacura) a 0,1410.
- `tipo_estimacion_sae`: 47 comunas con estimación "Directa y Sintética (Fay-Herriot)" y 5 con estimación "Sintética" (coincide exactamente con lo documentado en `PIPELINE.md` para `dim_vulnerabilidad_comuna`).

## 6. Oferta de urgencia (snapshot actual)

- Suma de `n_oferta_urgencia_actual` sobre las 52 comunas: **174**, idéntica al total de filas de `dim_oferta_urgencia_rm.parquet` (**reconciliación exacta**).
- Suma por tipo: `n_hospitales=45`, `n_sapu=91`, `n_sar=26`, `n_sur=11`, `n_otras_excepciones=1` (la excepción CESFAM documentada); la suma de los cinco (174) coincide exactamente con el total agregado.
- Todas las 52 comunas RM tienen al menos un establecimiento de oferta de urgencia en el snapshot vigente (no se observó ninguna comuna con `n_oferta_urgencia_actual=0`).

## 7. Reconciliación de demanda 2025 contra `mart_urgencias_comuna_monthly`

Para las 51 comunas con reporte, la suma anual de `atenciones_id1_2025`/`atenciones_id35_2025`/`atenciones_id36_2025` calculada en este mart **reconcilia exactamente** con la suma de los 12 meses de 2025 del mart mensual de origen.

## 8. Recálculo de tasas

Las tres tasas (`tasa_atenciones_id{1,35,36}_2025_por_10000`) se verificaron recalculando `atenciones_2025 / poblacion_2025 × 10.000` de forma independiente sobre el mart ya publicado: **las tres reconcilian exactamente** con los valores almacenados. Esto confirma que las tasas no son un promedio ni una suma de tasas mensuales ya calculadas, sino un recálculo desde el conteo anual agregado y la población 2025.

## 9. Distribución descriptiva de tasas (solo comunas con reporte, n=51)

| Tasa | Media | Mediana | Máximo |
|---|---|---|---|
| ID1 por 10.000 hab. | 8.591,7 | 7.663,0 | 30.525,9 |
| ID36 por 10.000 hab. | 155,5 | 122,4 | 996,0 |

Estas cifras describen intensidad de atenciones (evento), no personas únicas atendidas ni prevalencia — misma advertencia que en `diccionario_mart_urgencias_comuna_monthly.md`. No se interpreta aquí ninguna causa de la dispersión observada.

## 10. Conclusión de QA

- Grano correcto: 52 filas, 52 CUT únicos.
- Joins many-to-one/one-to-one sin pérdida ni duplicación de comunas.
- Cobertura completa de población y vulnerabilidad (52/52); cobertura de demanda 51/52 con NULL explícito (no cero) en la comuna faltante.
- Oferta agregada reconciliada exactamente contra los 174 establecimientos de `dim_oferta_urgencia_rm`; suma de tipos reconciliada contra el total.
- Demanda agregada 2025 reconciliada exactamente contra `mart_urgencias_comuna_monthly`.
- Tasas anuales recalculadas correctamente desde conteos/población, no agregadas desde tasas mensuales.
- Ningún campo estático (vulnerabilidad, oferta) se presenta con la temporalidad de 2025.
