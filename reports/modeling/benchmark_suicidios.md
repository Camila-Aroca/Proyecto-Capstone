# Benchmark del pronóstico semanal de suicidios (RM)

Generado por `scripts/run_benchmark_suicidios.py` (stage `benchmark_suicidios`). Cifras calculadas desde `data/processed/marts/mart_suicidios_comuna_weekly.parquet`; ver el EDA del mart en `reports/eda/eda_mart_suicidios_comuna_weekly.md`.

## 1. Qué se pronostica y cómo se evalúa

- **Objetivo:** defunciones por lesiones autoinfligidas intencionalmente (CIE-10 X60-X84 en la causa externa) por semana DEIS, de residentes de la RM (región) y de cada una de sus 52 comunas de residencia.
- **Ventana:** semanas regulares desde 2022 hasta 2025 (años cerrados); 2026 queda para el holdout. La semana 53 (fragmento de calendario) no entra.
- **Backtesting:** 13 orígenes cada 4 semanas (t = 151 a 199), horizontes 1-8; cada modelo se reajusta en cada origen solo con lo observado hasta él.
- **Escala:** 104 pronósticos regionales y 5408 comunales por modelo.

**Métrica de selección: RMSSE.** Cuatro de cada cinco comuna-semanas son cero. El error absoluto lo minimiza la mediana, que en una comuna es 0: la referencia que pronostica siempre cero obtiene el menor MASE comunal de la tabla (0.503) y el menor error absoluto (0.2097 frente a 0.3159 del elegido), aunque no anticipa nada. El error cuadrático lo minimiza la media, que es lo que se quiere estimar; RMSSE lo escala por el error cuadrático del baseline estacional en la historia previa al primer origen (como MASE). RMSSE < 1 significa superar al baseline. MASE se informa solo para leer la tabla igual que la del modelo de demanda.

**Calibración de intervalos de conteos.** Un intervalo de enteros no cubre exactamente 80%: con una media de 0,2 semanal, el intervalo [0, 1] ya cubre ~98%. Se compara la cobertura observada con la que el propio modelo declara para cada intervalo (`cobertura_esperada`); los modelos sin distribución declarada se comparan con el 80% nominal. Tolerancia: 1,96 errores estándar binomiales.

## 2. Resultados

| modelo | rmsse_region | rmsse_comuna | rmsse_promedio | mase_region | mase_comuna | cobertura_region | cobertura_esperada_region | calibrado_region | cobertura_comuna | cobertura_esperada_comuna | calibrado_comuna | puntaje_intervalo_region | puntaje_intervalo_comuna | dispersion_pearson_region | dispersion_pearson_comuna |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| poisson_estacional_eb_vm52 | 0.7548 | 0.5942 | 0.6745 | 0.6907 | 0.8621 | 0.8462 | 0.8462 | True | 0.9663 | 0.9642 | True | 15.0192 | 1.2016 | 1.1817 | 0.9592 |
| poisson_estacional_eb_vm26 | 0.7579 | 0.5945 | 0.6762 | 0.6975 | 0.8821 | 0.8462 | 0.8461 | True | 0.9658 | 0.9637 | True | 14.8077 | 1.2112 | 1.2018 | 0.9846 |
| poisson_estacional_eb_vm104 | 0.7569 | 0.5955 | 0.6762 | 0.6856 | 0.8671 | 0.8365 | 0.8447 | True | 0.9663 | 0.9636 | True | 15.0865 | 1.1897 | 1.1847 | 0.9474 |
| poisson_estacional_poblacion_vm52 | 0.7548 | 0.6073 | 0.681 | 0.6907 | 0.8729 | 0.8462 | 0.8462 | True | 0.9675 | 0.9619 | True | 15.0192 | 1.2143 | 1.1817 | 1.0339 |
| poisson_glm_global | 0.8363 | 0.5977 | 0.717 | 0.7683 | 0.8645 | 0.8365 | 0.8 | True | 0.9604 | 0.8 | False | 16.1346 | 1.2073 | 1.3488 | 2.0299 |
| poisson_glm_global_conformal | 0.8363 | 0.5977 | 0.717 | 0.7683 | 0.8645 | 0.8077 | 0.8 | True | 0.7959 | 0.8 | True | 16.1018 | 1.4586 | 1.3488 | 2.0299 |
| lightgbm_global | 0.838 | 0.6108 | 0.7244 | 0.8007 | 0.8653 | 0.7019 | 0.8 | False | 0.9114 | 0.8 | False | 20.1577 | 1.5386 | 1.581 | 1.1935 |
| lightgbm_global_conformal | 0.838 | 0.6108 | 0.7244 | 0.8007 | 0.8653 | 0.8077 | 0.8 | True | 0.7923 | 0.8 | True | 17.993 | 1.5234 | 1.581 | 1.1935 |
| baseline_estacional | 0.961 | 0.9441 | 0.9526 | 1.0032 | 0.9646 | 0.8462 | 0.8 | True | 0.9209 | 0.8 | False | 15.199 | 1.769 | 1.6816 |  |
| baseline_estacional_drift | 0.9815 | 0.9402 | 0.9608 | 0.987 | 1.0797 | 0.8173 | 0.8 | True | 0.8641 | 0.8 | False | 15.199 | 1.8512 | 1.8661 |  |
| referencia_cero | 2.3638 | 0.6529 | 1.5084 | 2.7816 | 0.503 | 0.0 | 0.8 | False | 0.823 | 0.8 | False | 109.0385 | 2.0969 |  |  |

`referencia_cero` y `baseline_estacional_drift` son referencias, no candidatos. El puntaje de intervalo (Gneiting y Raftery, 2007) suma el ancho y una penalización de 2/0,2 por cada unidad fuera; menor es mejor. La dispersión de Pearson es el error cuadrático dividido por la media pronosticada: ~1 indica que el error que queda es el azar propio de un conteo de Poisson.

## 3. Selección

- **Modelo elegido:** `poisson_estacional_eb_vm52`.
- **Criterio:** menor RMSSE promedio entre los modelos que superan al baseline estacional en ambos niveles con cobertura compatible con la declarada en la región y en las comunas.
- **Habilidad frente al baseline estacional (RMSSE):** 21.5% en la región y 37.1% en las comunas.
- **Error cuadrático medio del elegido frente al baseline** (negativo = el elegido se equivoca menos; Diebold-Mariano por origen con Newey-West y corrección HLN): región -35.57%, p = 0.192; comunas -51.21%, p = 1.29e-05 (13 orígenes).
- **Pronóstico típico (Wilcoxon):** región p = 1.52e-06; comunas p = 0.278. En las comunas el baseline acierta exactamente más semanas (el elegido tiene menor error solo en una proporción 0.2927 de los pronósticos: en las semanas en cero el baseline acierta exactamente) y falla fuerte en las demás; por eso la prueba de la mediana no refleja la diferencia de la media, que es lo que mide la regla de selección.
- **Cobertura:** región 0.8462 (declarada 0.8462), comunas 0.9663 (declarada 0.9642).
- **Error restante:** dispersión de Pearson fuera de muestra 1.1817 en la región y 0.9592 en las comunas.

Parámetros del modelo elegido ajustado en el último origen (lectura descriptiva):

- Nivel regional de una semana de 7 días en la media estacional: 11.765.
- Estacionalidad: máximo en la semana 51, mínimo en la 25, razón máximo/mínimo 1.604.
- Forma de la distribución Gamma de las tasas relativas comunales: a = 13.211 (casos efectivos que equivalen a la tasa regional; una comuna con E casos esperados conserva E/(E+a) de su desviación propia).
- Dispersión estimada en el entrenamiento: región 1.14, comunas 1.046 (1 = Poisson).

## 4. Contraste del elegido frente a cada alternativa

Cambio porcentual del error cuadrático escalado medio de la alternativa respecto del elegido (positivo = la alternativa es peor). `p_valor`: Diebold-Mariano sobre la pérdida media por origen; `p_holm`: su ajuste de Holm dentro de cada nivel; `p_wilcoxon`: prueba de rangos sobre cada pronóstico (pronóstico típico, informativa). Con 13 orígenes la potencia es baja: un p alto no prueba equivalencia.

| alternativa | nivel | n | cambio del error frente al elegido (%) | proporción en que la alternativa es mejor | p_valor | p_wilcoxon | p_holm |
|---|---|---|---|---|---|---|---|
| baseline_estacional | region | 104 | 55.2 | 0.2404 | 0.192 | 1.52e-06 | 1.0 |
| baseline_estacional | comuna | 5408 | 104.97 | 0.7073 | 1.29e-05 | 0.278 | 0.000116 |
| baseline_estacional_drift | region | 104 | 67.0 | 0.3269 | 0.319 | 0.000251 | 1.0 |
| baseline_estacional_drift | comuna | 5408 | 104.15 | 0.6335 | 2.03e-05 | 0.000611 | 0.000162 |
| poisson_glm_global | region | 104 | 20.96 | 0.4327 | 0.0104 | 0.0123 | 0.0936 |
| poisson_glm_global | comuna | 5408 | 0.62 | 0.4915 | 0.00185 | 0.823 | 0.00739 |
| lightgbm_global | region | 104 | 22.2 | 0.4327 | 0.151 | 0.0505 | 1.0 |
| lightgbm_global | comuna | 5408 | 3.73 | 0.549 | 2.61e-05 | 0.302 | 0.000182 |
| poisson_glm_global_conformal | region | 104 | 20.96 | 0.4327 | 0.0104 | 0.0123 | 0.0936 |
| poisson_glm_global_conformal | comuna | 5408 | 0.62 | 0.4915 | 0.00185 | 0.823 | 0.00739 |
| lightgbm_global_conformal | region | 104 | 22.2 | 0.4327 | 0.151 | 0.0505 | 1.0 |
| lightgbm_global_conformal | comuna | 5408 | 3.73 | 0.549 | 2.61e-05 | 0.302 | 0.000182 |
| poisson_estacional_eb_vm26 | region | 104 | 1.31 | 0.4231 | 0.539 | 0.195 | 1.0 |
| poisson_estacional_eb_vm26 | comuna | 5408 | 0.53 | 0.6045 | 0.0121 | 0.000133 | 0.0242 |
| poisson_estacional_eb_vm104 | region | 104 | 0.47 | 0.5769 | 0.799 | 0.192 | 1.0 |
| poisson_estacional_eb_vm104 | comuna | 5408 | -0.13 | 0.3717 | 0.142 | 7.68e-09 | 0.142 |
| poisson_estacional_poblacion_vm52 | region | 104 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 |
| poisson_estacional_poblacion_vm52 | comuna | 5408 | 2.44 | 0.5812 | 0.000147 | 0.00192 | 0.000733 |
| referencia_cero | region | 104 | 826.57 | 0.125 | 8.24e-06 | 2.32e-16 | 8.24e-05 |
| referencia_cero | comuna | 5408 | 18.83 | 0.823 | 8.57e-06 | 8.83e-114 | 8.57e-05 |

## 5. RMSSE por horizonte (mediana entre series)

| nivel | horizonte | poisson_estacional_eb_vm52 | baseline_estacional |
|---|---|---|---|
| comuna | 1 | 0.5936 | 0.948 |
| comuna | 2 | 0.5491 | 0.9348 |
| comuna | 3 | 0.6442 | 0.9746 |
| comuna | 4 | 0.6243 | 0.9086 |
| comuna | 5 | 0.5778 | 0.9227 |
| comuna | 6 | 0.5257 | 0.9548 |
| comuna | 7 | 0.6456 | 0.9858 |
| comuna | 8 | 0.5936 | 0.9232 |
| region | 1 | 0.7283 | 1.194 |
| region | 2 | 0.6434 | 0.9457 |
| region | 3 | 0.4357 | 0.811 |
| region | 4 | 1.0315 | 0.8347 |
| region | 5 | 0.917 | 1.2314 |
| region | 6 | 0.6774 | 0.9196 |
| region | 7 | 0.5863 | 0.9018 |
| region | 8 | 1.0186 | 0.85 |

## 6. Lectura y límites

- **Hecho observado:** el modelo elegido tiene menor RMSSE que el baseline estacional en ambos niveles, sus intervalos cubren lo que declaran y su error restante es del orden de la varianza de Poisson de su propio pronóstico (dispersión de Pearson cercana a 1). La significancia de cada diferencia está en la sección 4.
- Los RMSSE por horizonte se calculan con 13 pronósticos cada uno: su variación entre horizontes es ruido muestral y no se interpreta horizonte a horizonte.
- **Inferencia:** a escala comunal y semanal, la mayor parte de la variación es azar de conteos pequeños; ningún modelo de esta tabla la reduce de forma significativa. El pronóstico comunal es la **tasa esperada** de la semana, no una predicción de casos individuales.
- El territorio es la comuna de **residencia** del fallecido: no es el lugar del suicidio ni un establecimiento, y no se cruza con Urgencias por persona.
- Los conteos son defunciones registradas; las semanas finales con inscripción incompleta se excluyen (regla y evidencia en el EDA del mart). Con un único snapshot no es posible medir revisiones posteriores de la causa de muerte.
