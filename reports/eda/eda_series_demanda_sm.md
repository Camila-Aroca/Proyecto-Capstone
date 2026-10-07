# EDA de series temporales: demanda de urgencia en salud mental (RM)

Reproducible mediante `python -m scripts.eda_series_demanda_sm` (script de solo
lectura). Resumen de apoyo en
[`eda_series_demanda_sm_resumen.csv`](eda_series_demanda_sm_resumen.csv).

Este informe corresponde a la fase de *Data Understanding* (CRISP-DM) previa al
modelo de demanda. Complementa --sin repetir-- los EDA descriptivos existentes
(`eda_mart_urgencias_comuna.md`, `eda_demanda_urgencias_rm.md`), que cubren
volumen, territorio y causas pero no las propiedades de serie temporal.

## 0. Contrato analitico

| Decision | Valor | Motivo |
|---|---|---|
| Grano | Jerarquico: RM agregada + 51 comunas | Responde "cuanta demanda" y "donde"; permite prestar fuerza a comunas de bajo volumen |
| Target | `atenciones_id36` (conteo) | Es la cantidad que genera el proceso; las tasas se derivan dividiendo por poblacion |
| ID37 | Incluido | Se usa el agregado ID36 oficial de DEIS |
| Periodo | 2021-2025 | 2020 excluido por discontinuidad documentada de captura en salud mental |
| Estacionalidad | 52 semanas | Calendario semanal DEIS |

**ID36 no equivale a F00-F99 estricto.** En el periodo analizado, ID37 (ideacion
suicida, R45.8 -- fuera del capitulo F) aporta 5.62% del total
ID36. Toda comparacion futura con el F00-F99 de Egresos debe descontar
explicitamente esa fraccion.

## 1. Integridad del calendario

El calendario semanal DEIS no es ISO-8601. Se observan 2 combinaciones
anio x semana con `semana = 53`, que **no son semanas completas** sino fragmentos
de pocos dias en el limite entre anios:

| ano | semana | fecha_min | atenciones | comunas |
|---|---|---|---|---|
| 2021 | 53 | 2021-01-01 | 236 | 51 |
| 2025 | 53 | 2025-12-28 | 1220 | 51 |

**Hecho observado:** estos fragmentos concentran 0.29% de las
atenciones del periodo pero se presentan como si fueran semanas completas. Si
entran crudos a un modelo semanal aparecen como caidas severas que no
corresponden a baja demanda, sino a semanas truncadas.

**Regla aplicada en este EDA:** se excluyen de todos los analisis estacionales,
dejando una grilla regular de 52 semanas por anio
(260 periodos, 2021-2025). La exclusion se
cuantifica arriba; no se imputan ni se fusionan con semanas vecinas.

## 2. Estacionariedad

| serie | adf_estadistico | adf_p_valor | adf_rechaza_raiz_unitaria | kpss_estadistico | kpss_p_valor | kpss_p_truncado_en_tabla | kpss_rechaza_estacionariedad |
|---|---|---|---|---|---|---|---|
| nivel | -4.0038 | 0.0014 | True | 1.8625 | 0.01 | True | True |
| primera_diferencia | -10.0127 | 0.0 | True | 0.3909 | 0.0811 | False | False |

**Lectura conjunta (alfa = 0.05):** en nivel, ADF rechaza la raiz
unitaria (p = 0.0014) y KPSS rechaza la estacionariedad
(p = 0.01). Sobre la primera diferencia, ADF p =
0.0 y KPSS p = 0.0811.

**Inferencia:** la serie en nivel no es estacionaria y una diferencia regular basta para estabilizarla. Un modelo ARIMA/SARIMA debe incluir `d = 1`; los modelos de machine learning deben recibir la serie diferenciada o incorporar rezagos suficientes para absorber la tendencia.

## 3. Autocorrelacion y estacionalidad

- ACF en rezago 1: **0.7979** (banda de significancia +/-0.1216).
- ACF en rezago 52: **0.264** -- significativa.
- Rezagos con ACF significativa entre 1 y 60: 60.

Descomposicion STL (periodo 52, robusta):

| Componente | Fuerza |
|---|---|
| Tendencia | 0.62 |
| Estacionalidad | 0.2308 |
| Amplitud estacional (atenciones) | 1915.1 |

**Observacion:** la evidencia de estacionalidad anual es intermedia. Conviene probar el componente estacional contra su ausencia durante el backtesting en vez de asumirlo.

## 4. Estabilidad de regimen

Media semanal del target y de establecimientos reportantes, por anio x trimestre
DEIS:

| ano | trimestre | atenciones_media_semanal | reportantes_media_semanal |
|---|---|---|---|
| 2021 | 1 | 1131.9 | 145.8 |
| 2021 | 2 | 1543.2 | 147.0 |
| 2021 | 3 | 1714.6 | 147.0 |
| 2021 | 4 | 1832.9 | 146.6 |
| 2022 | 1 | 1772.5 | 147.0 |
| 2022 | 2 | 1715.2 | 147.0 |
| 2022 | 3 | 1885.5 | 147.0 |
| 2022 | 4 | 1949.3 | 146.9 |
| 2023 | 1 | 2027.8 | 148.0 |
| 2023 | 2 | 1877.1 | 148.0 |
| 2023 | 3 | 2073.4 | 147.7 |
| 2023 | 4 | 2092.5 | 146.5 |
| 2024 | 1 | 2236.8 | 147.2 |
| 2024 | 2 | 1927.8 | 146.3 |
| 2024 | 3 | 1994.1 | 146.6 |
| 2024 | 4 | 2122.0 | 146.8 |
| 2025 | 1 | 2207.2 | 149.0 |
| 2025 | 2 | 2053.0 | 149.4 |
| 2025 | 3 | 2105.1 | 149.8 |
| 2025 | 4 | 2195.0 | 150.0 |

**Hecho observado:** el primer trimestre del periodo promedia 1,132 atenciones semanales, 42.4% por debajo de la media de los trimestres posteriores (1,964). En el mismo lapso, los establecimientos reportantes varian solo 2.9% entre su minimo y su maximo (146 a 150).

**Inferencia:** la cobertura de reporte queda descartada como explicacion de esa diferencia de nivel, porque se mantiene practicamente constante. **La causa efectiva no es determinable con los datos disponibles.**

**Implicancia para el modelado:** los primeros trimestres de la serie pertenecen a un regimen de nivel distinto. Entrenar sobre ellos sin marcarlos arrastra ese regimen al pronostico. Opciones a evaluar en backtesting: excluirlos, incorporar una variable indicadora de regimen, o ponderar las observaciones por antiguedad.

## 5. Heterogeneidad territorial

51 series comunales. Distribucion del volumen total del periodo:

| Estadistico | Atenciones ID36 |
|---|---|
| Minimo | 427 |
| Mediana | 7689 |
| Maximo | 92875 |
| Razon max/min | 217.5x |

- 24 comunas concentran el 80% de la demanda RM.
- Comunas con al menos una semana en cero: 24.
- Coeficiente de variacion semanal: mediana 0.337, maximo 1.183.

Cinco comunas de mayor y menor volumen:

| comuna_glosa | total | media_semanal | coef_variacion | share_demanda_rm |
|---|---|---|---|---|
| Recoleta | 92875 | 357.21 | 0.24 | 0.19 |
| Puente Alto | 28743 | 110.55 | 0.26 | 0.06 |
| San Miguel | 23323 | 89.7 | 0.24 | 0.05 |
| San Bernardo | 22106 | 85.02 | 0.2 | 0.04 |
| Maipú | 19116 | 73.52 | 0.24 | 0.04 |
| Pirque | 1285 | 4.94 | 0.55 | 0.0 |
| Calera de Tango | 886 | 3.41 | 0.65 | 0.0 |
| San Pedro | 762 | 2.93 | 0.91 | 0.0 |
| Alhué | 439 | 1.69 | 0.98 | 0.0 |
| Lo Barnechea | 427 | 1.64 | 1.18 | 0.0 |

## 6. Baseline estacional ingenuo (referencia)

Predice `y[t] = y[t-52]`. Es la referencia obligatoria del alcance
del proyecto. Como el periodo estacional (52) supera el horizonte
maximo (8), el valor usado siempre esta observado al momento del
pronostico: el baseline no usa informacion futura.

**Serie RM agregada:**

| horizonte_semanas | n_evaluaciones | mae | rmse | mape_pct |
|---|---|---|---|---|
| 4 | 204 | 193.04 | 252.59 | 9.87 |
| 5 | 203 | 191.97 | 251.56 | 9.79 |
| 6 | 202 | 190.11 | 249.02 | 9.67 |
| 7 | 201 | 188.17 | 246.26 | 9.56 |
| 8 | 200 | 187.07 | 245.18 | 9.49 |

**Por comuna** (mismo baseline aplicado a cada serie comunal):

| Estadistico | MAPE (%) |
|---|---|
| Minimo | 18.66 |
| Mediana | 34.34 |
| Maximo | 148.29 |

**Hecho observado:** el baseline alcanza 9.68% de MAPE medio sobre la serie RM agregada (MAE entre 187 y 193 atenciones segun horizonte), pero 34.34% de MAPE mediano a nivel comunal: 3.5x peor.

**Inferencia:** la agregacion regional cancela ruido idiosincratico comunal. Esto sustenta cuantitativamente el enfoque jerarquico elegido: pronosticar el agregado RM (donde la senal es mas limpia) y repartirlo hacia las comunas con reconciliacion, en vez de tratar cada comuna como un problema independiente.

**Umbral de exito:** cualquier modelo propuesto debe superar estas cifras en el mismo backtesting. Un modelo que no las supere no justifica su complejidad.

## 7. Implicancias para el modelado

1. **Grilla temporal.** Excluir las 2 semanas fragmentarias (`semana = 53`) o tratarlas explicitamente; nunca mezclarlas con semanas completas. La grilla modelable queda en 260 periodos regulares.
2. **Features de rezago.** Incluir al menos los rezagos 1 a 4 y el rezago 52, mas medias moviles cortas. El horizonte de 4 a 8 semanas exige que todo rezago usado sea mayor o igual al horizonte, o construir el pronostico de forma recursiva.
3. **Regimen inicial.** Marcar o excluir el tramo de nivel distinto descrito en la seccion 4; decidirlo por backtesting, no por supuesto.
4. **Estructura jerarquica.** Modelar el agregado RM y reconciliar hacia las 51 comunas. Las 24 comunas que concentran el 80% del volumen admiten modelado individual; el resto depende de la reconciliacion.
5. **Holdout 2026.** El snapshot del anio en curso es mutable y ya cambio entre corridas del pipeline. Fijar su SHA256 desde `data/raw/provenance_manifest.json` y reportar contra que version se evaluo.
6. **Distribucion del target.** El target es un conteo no negativo; preferir perdidas adecuadas a conteos (Poisson/Tweedie) o modelar en escala logaritmica antes que asumir errores gaussianos sobre el nivel.

## 8. Limitaciones

- El target es **atenciones (eventos), no personas unicas**: una misma persona
  puede generar varias atenciones en la misma comuna x semana.
- Vitacura (`13132`) no tiene ninguna fila en el mart para
  2021-2025; no se imputa. El modelo cubre
  51 de las 52 comunas RM.
- La demanda observada refleja utilizacion y oferta instalada, no prevalencia ni
  necesidad sanitaria de la poblacion residente.
- Este EDA no ajusta modelos ni produce pronosticos: solo caracteriza la serie y
  establece la referencia del baseline.
- Las causas de los cambios de nivel descritos en la seccion 4 no son
  determinables con los datos disponibles.
