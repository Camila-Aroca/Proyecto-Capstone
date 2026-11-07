# EDA del mart semanal de suicidios por comuna de residencia (RM)

Generado por `scripts/eda_mart_suicidios_comuna_weekly.py` (stage `eda_mart_suicidios_comuna_weekly`) desde `data/processed/marts/mart_suicidios_comuna_weekly.parquet` (SHA256 `7d103046636fc5d8743fb88ac933841e1d6dbcdc17b94f4c32c713193c593b8e`), `data/processed/defunciones/defunciones_nacional.parquet` y los Parquet anuales de Urgencias. Diccionario: `reports/dictionary/diccionario_mart_suicidios_comuna_weekly.md`.

## 1. Cobertura y conciliación

- 18616 filas = 52 comunas x 358 semanas DEIS (incluidos los fragmentos `semana = 53`), desde 2020-01-01 hasta 2026-10-24. Última fecha de defunción del archivo nacional: 2026-10-24.
- Suicidios en el mart: 3943; defunciones X60-X84 de residentes RM en la fuente para el mismo período: 3943 (diferencia 0).
- La categoría X60-X84 de `codigo_categoria_diag2` coincide registro a registro con el grupo publicado `codigo_grupo_diag2 = X60-X84` (la etapa falla si no). Categorías más frecuentes: X70 3694 (93.7%), X80 98 (2.5%), X74 36 (0.9%), X69 25 (0.6%).

| ano | dias | suicidios | por_dia | tasa_100mil_ano | defunciones | pct_de_defunciones |
|---|---|---|---|---|---|---|
| 2020 | 366 | 469 | 1.281 | 5.76 | 51600 | 0.91 |
| 2021 | 365 | 496 | 1.359 | 6.02 | 51532 | 0.96 |
| 2022 | 365 | 693 | 1.899 | 8.34 | 49967 | 1.39 |
| 2023 | 365 | 615 | 1.685 | 7.35 | 44633 | 1.38 |
| 2024 | 366 | 662 | 1.809 | 7.85 | 46872 | 1.41 |
| 2025 | 365 | 573 | 1.57 | 6.77 | 46548 | 1.23 |
| 2026 | 297 | 435 | 1.465 | 6.28 | 38547 | 1.13 |

2026 es parcial (297 días): sus totales no se comparan con años completos; su ritmo diario sí.

## 2. Calendario DEIS

- `semana_deis` reproduce la codificación (año, semana) publicada por Urgencias en 2467 fechas de 2020 a 2026, con 0 discrepancias.
- Semanas con un número de días distinto de 7 (el modelo usa `dias_semana` como exposición):

| ano | semana | fecha_inicio_semana | dias_semana |
|---|---|---|---|
| 2020 | 1 | 2020-01-01 | 4 |
| 2020 | 53 | 2020-12-27 | 5 |
| 2021 | 53 | 2021-01-01 | 2 |
| 2021 | 52 | 2021-12-26 | 6 |
| 2022 | 52 | 2022-01-01 | 8 |
| 2023 | 1 | 2023-01-01 | 8 |
| 2024 | 1 | 2024-01-01 | 9 |
| 2025 | 1 | 2025-01-01 | 4 |
| 2025 | 53 | 2025-12-28 | 4 |
| 2026 | 53 | 2026-01-01 | 3 |

## 3. Registro de las semanas finales

Razón = defunciones diarias por todas las causas de la semana / mediana de las 8 semanas previas. Mínimo en semanas interiores de 2021 en adelante: 0.787; umbral de registro incompleto: 0.75.

| ano | semana | inicio | dias | defunciones | suicidios | razon_registro | registro_completo |
|---|---|---|---|---|---|---|---|
| 2026 | 35 | 2026-08-30 | 7 | 886 | 11 | 0.894 | True |
| 2026 | 36 | 2026-09-06 | 7 | 904 | 10 | 0.927 | True |
| 2026 | 37 | 2026-09-13 | 7 | 978 | 13 | 1.028 | True |
| 2026 | 38 | 2026-09-20 | 7 | 941 | 13 | 0.989 | True |
| 2026 | 39 | 2026-09-27 | 7 | 909 | 11 | 0.966 | True |
| 2026 | 40 | 2026-10-04 | 7 | 886 | 10 | 0.942 | True |
| 2026 | 41 | 2026-10-11 | 7 | 883 | 11 | 0.955 | True |
| 2026 | 42 | 2026-10-18 | 7 | 655 | 8 | 0.723 | False |

- Semanas marcadas con registro incompleto: 2026-S42.
- Suicidios en las últimas 6 semanas completas: 11.33 por semana de 7 días, frente a 10.05 en el conjunto de semanas completas del mismo año: no se observa un déficit que indique rezago propio de esta causa en esas semanas.
- **Límite:** con un único snapshot no es posible medir cuántas defunciones recientes se inscribirán o recodificarán después; la regla solo detecta el rezago visible en el total de defunciones.

## 4. Cambio de nivel 2020-2021

- Suicidios por día: 1.3201 en 2020-2021 frente a 1.7406 en 2022-2025 (razón 1.3185; prueba binomial exacta condicionada a los días, p = 9.97e-14).
- Dentro de 2022-2025 los años tampoco son homogéneos (chi-cuadrado 12.98, gl 3, p = 0.00469).
- **Hipótesis, no verificada:** 2020-2021 coinciden con la pandemia; no es posible determinar la causa con los datos disponibles. **Decisión:** la ventana del modelo empieza en 2022 y su nivel se pondera hacia los años recientes.

## 5. Serie regional 2022-2025: estacionalidad, dispersión y autocorrelación

GLM de Poisson con efecto de año, exposición `log(dias / 7)` y k armónicos anuales:

| armonicos | LR | gl | p_valor |
|---|---|---|---|
| 1 frente a 0 | 33.43 | 2 | 5.49e-08 |
| 2 frente a 1 | 1.58 | 2 | 0.453 |
| 3 frente a 2 | 4.05 | 2 | 0.132 |

- Un armónico: máximo en la semana 52, mínimo en la 26, razón máximo/mínimo 1.385.
- Dispersión de Pearson: 1.154 sin estacionalidad y 1.006 con un armónico (1 = Poisson).
- Autocorrelación de los residuos de Pearson (208 semanas; banda ±0.139): rezago 1: -0.031, rezago 2: 0.04, rezago 3: 0.065, rezago 4: -0.04, rezago 8: -0.106, rezago 13: 0.049, rezago 26: -0.01.
- **Lectura:** una vez descontados nivel y estación, la serie se comporta como Poisson y las semanas recientes no aportan información adicional; esto orienta a un modelo estructural de conteos y no a uno de rezagos.

## 6. Comunas 2022-2025: escasez, ceros y heterogeneidad

- Media semanal por comuna: mínimo 0.019, mediana 0.192, máximo 0.99.
- Comuna-semanas en cero: 80.3% observado frente a 80.3% esperado si cada comuna fuera Poisson con su media: no hay exceso de ceros que justifique un modelo inflado en cero. Mediana de varianza/media por comuna: 0.971.
- Tasa anual por 100.000 habitantes: región 7.53, comunas entre 2.57 y 19.22. Prueba de homogeneidad frente a la población (chi-cuadrado 328.2, gl 51, p = 3.83e-42): las comunas difieren más de lo que explica el azar.

Cinco comunas de menor y cinco de mayor tasa (residencia; pocos casos implican tasas inestables):

| comuna_glosa | suicidios | media_semanal | tasa_100mil_ano |
|---|---|---|---|
| Vitacura | 10 | 0.048 | 2.572 |
| La Reina | 11 | 0.053 | 2.766 |
| Las Condes | 43 | 0.207 | 3.14 |
| Providencia | 26 | 0.125 | 3.978 |
| Santiago | 88 | 0.423 | 4.075 |
| Cerro Navia | 74 | 0.356 | 13.205 |
| Melipilla | 81 | 0.389 | 13.677 |
| Curacaví | 21 | 0.101 | 13.763 |
| San José de Maipo | 11 | 0.053 | 14.161 |
| Alhué | 6 | 0.029 | 19.222 |

- **Lectura:** con tan pocos casos, la tasa propia de una comuna es ruidosa pero informativa; por eso el modelo contrae cada tasa comunal hacia la regional (Bayes empírico) según los casos que aporta.

## 7. Advertencias

- El territorio es la comuna de residencia, no el lugar del suicidio ni un establecimiento; la relación con Urgencias es solo ecológica.
- Son defunciones registradas con causa externa X60-X84; los eventos de intención no determinada (Y10-Y34) no se incluyen.
