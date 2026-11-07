# Evaluación en holdout del pronóstico semanal de suicidios (RM)

Generado por `scripts/evaluate_holdout_suicidios.py` (stage `evaluate_holdout_suicidios`).

## 1. Período y datos

- Modelo evaluado (selección congelada en `reports/modeling/benchmark_suicidios_seleccion.json`): `poisson_estacional_eb_vm52`.
- Holdout: 41 semanas completas de 2026 (2026-S01 a 2026-S41); 34 orígenes semanales, horizontes 1-8, solo objetivos posteriores al entrenamiento.
- Semanas excluidas por registro incompleto: 2026-S42.
- Mart evaluado: `data/processed/marts/mart_suicidios_comuna_weekly.parquet`, SHA256 `7d103046636fc5d8743fb88ac933841e1d6dbcdc17b94f4c32c713193c593b8e`.

## 2. Resultados

| modelo | rmsse_region | rmsse_comuna | rmsse_promedio | mase_region | mase_comuna | cobertura_region | cobertura_esperada_region | calibrado_region | cobertura_comuna | cobertura_esperada_comuna | calibrado_comuna | dispersion_pearson_region | dispersion_pearson_comuna |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| poisson_estacional_eb_vm26 | 0.604 | 0.6315 | 0.6178 | 0.6094 | 0.7951 | 0.8676 | 0.8444 | True | 0.9685 | 0.9637 | True | 0.8588 | 1.0972 |
| poisson_estacional_eb_vm52 | 0.6264 | 0.6284 | 0.6274 | 0.617 | 0.8121 | 0.8787 | 0.849 | True | 0.9704 | 0.9655 | True | 0.8843 | 1.0179 |
| poisson_estacional_poblacion_vm52 | 0.6264 | 0.6415 | 0.634 | 0.617 | 0.8081 | 0.8787 | 0.849 | True | 0.9661 | 0.9604 | True | 0.8843 | 1.1116 |
| poisson_glm_global_conformal | 0.649 | 0.627 | 0.638 | 0.6399 | 0.8283 | 0.9228 | 0.8 | False | 0.8353 | 0.8 | False | 0.9593 | 0.9455 |
| poisson_estacional_eb_vm104 | 0.6564 | 0.6268 | 0.6416 | 0.6356 | 0.8299 | 0.8676 | 0.843 | True | 0.9705 | 0.9654 | True | 0.9379 | 0.967 |
| lightgbm_global_conformal | 0.6967 | 0.6334 | 0.665 | 0.704 | 0.8153 | 0.8824 | 0.8 | False | 0.8335 | 0.8 | False | 1.3852 | 1.1156 |
| baseline_estacional_drift | 0.9308 | 0.9031 | 0.9169 | 0.8971 | 0.9313 | 0.8235 | 0.8 | True | 0.8544 | 0.8 | False |  |  |
| baseline_estacional | 0.9246 | 0.9158 | 0.9202 | 0.9126 | 0.8518 | 0.8272 | 0.8 | True | 0.9313 | 0.8 | False | 2.8951 |  |
| referencia_cero | 2.0301 | 0.6735 | 1.3518 | 2.4038 | 0.4646 | 0.0 | 0.8 | False | 0.8408 | 0.8 | False |  |  |

## 3. Criterios

- Sí: supera al baseline con diferencia significativa en las comunas.
- Sí: supera al baseline en RMSSE en la región.
- Sí: conserva habilidad frente al baseline en ambos niveles.
- Sí: cobertura compatible con la declarada en ambos niveles.
- No: ninguna alternativa candidata es significativamente mejor (Holm).

Error cuadrático medio del elegido frente al baseline estacional (negativo = el elegido se equivoca menos): región -54.09% (Diebold-Mariano p = 0.0115; Wilcoxon p = 3.82e-21), comunas -48.88% (Diebold-Mariano p = 6.36e-10; Wilcoxon p = 1.99e-50). Diebold-Mariano compara la pérdida media por origen (la de la regla de selección); Wilcoxon, el pronóstico típico. Los orígenes semanales comparten semanas objetivo: la varianza usa Newey-West.

## 4. Backtest frente a holdout

La habilidad se mide contra el baseline del mismo período, para no confundir un año más fácil o más difícil con un cambio del modelo.

| nivel | RMSSE backtest | RMSSE holdout | habilidad backtest (%) | habilidad holdout (%) |
|---|---|---|---|---|
| region | 0.7548 | 0.6264 | 21.5 | 32.3 |
| comuna | 0.5942 | 0.6284 | 37.1 | 31.4 |

## 5. Alternativas

`cambio del error frente al elegido`: error cuadrático medio de la alternativa respecto del elegido (negativo = la alternativa se equivoca menos). `p_valor`: Diebold-Mariano por origen; `p_holm`: su ajuste de Holm por nivel; `p_wilcoxon`: pronóstico típico.

| alternativa | nivel | n | cambio del error frente al elegido (%) | proporción en que la alternativa es mejor | p_valor | p_wilcoxon | p_holm |
|---|---|---|---|---|---|---|---|
| baseline_estacional | region | 272 | 117.83 | 0.2169 | 0.0115 | 3.82e-21 | 0.0577 |
| baseline_estacional | comuna | 14144 | 95.63 | 0.7529 | 6.36e-10 | 1.99e-50 | 4.45e-09 |
| baseline_estacional_drift | region | 272 | 121.26 | 0.3346 | 0.0425 | 1.91e-12 | 0.17 |
| baseline_estacional_drift | comuna | 14144 | 92.47 | 0.6541 | 8.49e-11 | 0.517 | 6.79e-10 |
| poisson_glm_global_conformal | region | 272 | 7.39 | 0.4412 | 0.237 | 0.0209 | 0.475 |
| poisson_glm_global_conformal | comuna | 14144 | -0.33 | 0.4273 | 0.102 | 3.11e-09 | 0.102 |
| lightgbm_global_conformal | region | 272 | 24.27 | 0.4559 | 0.115 | 0.0184 | 0.344 |
| lightgbm_global_conformal | comuna | 14144 | 2.34 | 0.5418 | 0.00408 | 0.000161 | 0.00815 |
| poisson_estacional_eb_vm26 | region | 272 | -6.95 | 0.5625 | 0.00622 | 0.000339 | 0.0373 |
| poisson_estacional_eb_vm26 | comuna | 14144 | 0.68 | 0.6809 | 7.41e-05 | 3.31e-56 | 0.000222 |
| poisson_estacional_eb_vm104 | region | 272 | 9.79 | 0.3897 | 0.00011 | 3.06e-09 | 0.000767 |
| poisson_estacional_eb_vm104 | comuna | 14144 | -0.23 | 0.3113 | 2.08e-06 | 1.72e-75 | 8.34e-06 |
| poisson_estacional_poblacion_vm52 | region | 272 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 |
| poisson_estacional_poblacion_vm52 | comuna | 14144 | 2.8 | 0.5793 | 3.69e-09 | 0.345 | 2.22e-08 |
| referencia_cero | region | 272 | 950.65 | 0.0882 | 9.25e-10 | 2.58e-43 | 7.4e-09 |
| referencia_cero | comuna | 14144 | 15.61 | 0.8408 | 2.76e-08 | 0.0 | 1.38e-07 |

**Alternativas con menor error medio significativo en el holdout:** `poisson_estacional_eb_vm26` en la región (-6.95% de error, p Holm = 0.0373); `poisson_estacional_eb_vm104` en las comunas (-0.23% de error, p Holm = 8.34e-06).

La selección congelada (`poisson_estacional_eb_vm52`) se mantiene: cambiarla después de ver el holdout usaría el año en curso para elegir, y este dejaría de ser una evaluación fuera de muestra. Un cambio debe validarse con semanas posteriores a este snapshot. El tamaño de la diferencia se lee junto a su p: con miles de pronósticos comunales, diferencias de décimas de punto porcentual resultan significativas sin ser relevantes.

## 6. Límites

- La serie regional aporta un pronóstico por origen y horizonte; sus pruebas tienen poca potencia y los orígenes consecutivos comparten semanas objetivo (no son independientes).
- El año en curso es un snapshot: las defunciones recientes pueden recodificarse o inscribirse después de este corte, y con un único snapshot no es posible medirlo.
