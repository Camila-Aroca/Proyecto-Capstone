# Evaluacion en holdout del modelo de demanda de urgencia en salud mental

Reproducible mediante `python -m scripts.evaluate_holdout_demanda_sm`. Metricas
por serie y horizonte en
[`holdout_demanda_sm_resumen.csv`](holdout_demanda_sm_resumen.csv).

Corresponde a la fase de *Evaluation* (CRISP-DM). Evalua el modelo que eligio
[`benchmark_demanda_sm.md`](benchmark_demanda_sm.md) en un periodo que esa
seleccion nunca vio.

## 1. Veredicto

**La seleccion se sostiene solo parcialmente.** `hibrido_glm_region_lgbm_comuna_conformal` cumple: supera al baseline con diferencia significativa en ambos niveles; conserva ventaja sobre el baseline respecto del backtest. No cumple: intervalos calibrados en ambos niveles; ninguna alternativa es significativamente mejor. Ver secciones 6 a 9.

## 2. Protocolo

| Parametro | Valor |
|---|---|
| Modelo evaluado (seleccion congelada) | `hibrido_glm_region_lgbm_comuna_conformal` |
| Periodo de seleccion (backtest) | 2021-2025 |
| Periodo holdout | 2026 |
| Origenes | 31 (paso 1), t=259 a t=289 |
| Horizontes | 4, 5, 6, 7, 8 semanas |
| Evaluaciones por modelo | 155 en la region, 7,750 en comunas |
| Semanas holdout evaluadas | 35 (semanas 4 a 38 de 2026) |
| Modelos comparados | `baseline_estacional`, `poisson_glm_global_conformal`, `lightgbm_global_conformal`, `hibrido_glm_region_lgbm_comuna_conformal` |

En cada origen el modelo se reentrena con todo lo observado hasta ese momento,
como operaria en produccion. Ninguna cifra de esta evaluacion se uso para elegir
el modelo. MASE usa la misma escala que el benchmark (historia previa a su primer
origen), de modo que ambos informes son comparables.

## 3. Snapshot evaluado

La fuente del anio en curso es mutable: DEIS la sobrescribe sin versionarla. Este
resultado corresponde exactamente a los archivos siguientes.

| ano | raw_path | raw_bytes | raw_sha256 | procesado_sha256 | estado_procedencia |
|---|---|---|---|---|---|
| 2026 | data/raw/urgencias/AtencionesUrgencia2026.csv | 1512588051 | 73f6480f16d299efb80f37fa94cb7d136b15efaca7dec8a05e08edf8502b9f11 | 4bc66d82ed7032e24cb47734109ca556f45601fc54cff985f070666b8f8e8547 | difiere_del_registrado |

Fecha maxima observada en la fuente: **2026-10-02**.

- **2026**: estado de procedencia `difiere_del_registrado`; el RAW en disco no coincide con el ultimo snapshot registrado.

## 4. Preparacion de los datos del holdout

El semanal comunal del holdout se construye con la misma carga y agregacion que
el mart de entrenamiento, y la poblacion con el mismo cuadro oficial INE.

**Semanas truncadas excluidas** (menos de 7 dias; tratadas como completas
parecerian una caida de demanda):

| ano | semana | dias | atenciones_id36 |
|---|---|---|---|
| 2026 | 39 | 6 | 1581 |

**Comunas sin historia de entrenamiento excluidas** (no son pronosticables: no
tienen rezagos ni identidad aprendida):

| comuna_codigo | comuna_glosa | semanas | atenciones_id36 | share_holdout_pct |
|---|---|---|---|---|
| 13132 | Vitacura | 39 | 70 | 0.084 |

**Comunas con historia pero cobertura incompleta en el holdout** (dejan de
tener filas para todas las causas: es ausencia de dato, no demanda cero, y no se
rellena):

| comuna_codigo | semanas_con_datos | semanas_esperadas | ultima_semana_con_datos | share_referencia_pct |
|---|---|---|---|---|
| 13504 | 18 | 38 | 18 | 0.246 |

**Universo evaluado:** 50 comunas con historia y cobertura completa. El total regional se define como la suma de ese mismo universo en todo el periodo, entrenamiento incluido, para que el target no cambie de definicion a mitad de la serie. El benchmark usaba 51 comunas; las excluidas aqui representaban 0.25% del volumen del ultimo anio de entrenamiento. Las cifras regionales de ambos informes son comparables con esa salvedad; las comunales se comparan sobre las mismas comunas.

## 5. Resultados

| modelo | mase_region | mase_comuna | cobertura_region | cobertura_comuna | amplitud_comuna | calibrado_region | calibrado_comuna |
|---|---|---|---|---|---|---|---|
| hibrido_glm_region_lgbm_comuna_conformal | 0.5096 | 0.6587 | 0.6968 | 0.7684 | 19.21 | False | False |
| poisson_glm_global_conformal | 0.5096 | 0.69 | 0.6968 | 0.7745 | 22.61 | False | False |
| lightgbm_global_conformal | 0.5774 | 0.6396 | 0.8194 | 0.7724 | 19.49 | True | False |
| baseline_estacional | 0.6658 | 0.9164 | 0.7677 | 0.7865 | 31.8 | True | False |

## 6. Supera al baseline fuera de muestra?

- **region**: -23.47% de error frente al baseline (mejor en 65.2% de 155 pronosticos, Wilcoxon p = 0.0001) -> mejora significativa.
- **comuna**: -26.77% de error frente al baseline (mejor en 65.1% de 7,750 pronosticos, Wilcoxon p = 0.0000) -> mejora significativa.

**Inferencia:** `hibrido_glm_region_lgbm_comuna_conformal` supera al baseline estacional fuera de muestra en ambos niveles, con diferencias que no son atribuibles al azar.

## 7. Se sostiene la calibracion?

Cobertura observada: region 0.697 (155 evaluaciones, tolerancia +/-0.063); comunas 0.768 (7,750 evaluaciones, tolerancia +/-0.009). Nominal 0.80.

**Hecho observado:** la cobertura se aleja del nominal mas de lo que el azar explica en: region, que subcubre (intervalos demasiado estrechos); comuna, que subcubre (intervalos demasiado estrechos).

## 8. Se degrado respecto del backtest?

| nivel | mase_backtest | mase_holdout | mase_baseline_backtest | mase_baseline_holdout | habilidad_backtest_pct | habilidad_holdout_pct |
|---|---|---|---|---|---|---|
| region | 0.5953 | 0.5096 | 0.7866 | 0.6658 | 24.3 | 23.5 |
| comuna | 0.6789 | 0.6587 | 0.9204 | 0.9164 | 26.2 | 28.1 |

**Hecho observado:** `hibrido_glm_region_lgbm_comuna_conformal` conserva ventaja sobre el baseline en ambos niveles fuera de muestra. Cambio de habilidad respecto del backtest: region: -0.8 puntos; comuna: +1.9 puntos.

La habilidad se mide contra el baseline **dentro del mismo periodo**, de modo que un anio mas facil o mas dificil de pronosticar no se confunde con una mejora o un deterioro del modelo.

## 9. Habria ganado otro candidato?

Comparacion pareada de cada alternativa contra `hibrido_glm_region_lgbm_comuna_conformal`
(`error_a` es el del recomendado, `error_b` el de la alternativa):

| alternativa | nivel | n | error_a | error_b | cambio_pct | proporcion_b_mejor | p_valor |
|---|---|---|---|---|---|---|---|
| poisson_glm_global_conformal | region | 155 | 0.5096 | 0.5096 | 0.0 | 0.2581 | 1.0 |
| poisson_glm_global_conformal | comuna | 7750 | 0.7198 | 0.8104 | 12.59 | 0.4446 | 0.0 |
| lightgbm_global_conformal | region | 155 | 0.5096 | 0.5774 | 13.32 | 0.4516 | 0.0903 |
| lightgbm_global_conformal | comuna | 7750 | 0.7198 | 0.7111 | -1.2 | 0.5368 | 0.0 |

**Hecho observado:** alternativas significativamente mejores fuera de muestra: `lightgbm_global_conformal` en comuna (-1.20%, p = 0.0000). La seleccion no se revisa aqui --el holdout no alimenta la seleccion--, pero el resultado debe considerarse en la proxima iteracion del benchmark.

## 10. Detalle por horizonte del modelo evaluado

| nivel | horizonte | mae_medio | mase_mediano | cobertura_media | amplitud_media |
|---|---|---|---|---|---|
| comuna | 4 | 7.0224 | 0.6648 | 0.7748 | 19.1171 |
| comuna | 5 | 7.0603 | 0.6476 | 0.7794 | 19.4197 |
| comuna | 6 | 7.1117 | 0.6458 | 0.7716 | 19.2776 |
| comuna | 7 | 7.3408 | 0.6834 | 0.7587 | 19.1916 |
| comuna | 8 | 7.4944 | 0.6519 | 0.7574 | 19.0204 |
| region | 4 | 108.583 | 0.4891 | 0.7419 | 343.343 |
| region | 5 | 105.668 | 0.476 | 0.7742 | 344.856 |
| region | 6 | 111.366 | 0.5016 | 0.7097 | 347.801 |
| region | 7 | 117.787 | 0.5306 | 0.7097 | 368.417 |
| region | 8 | 122.238 | 0.5506 | 0.5484 | 325.478 |

## 11. Limitaciones

- El holdout cubre 35 (semanas 4 a 38 de 2026) semanas de un solo anio: evidencia
  valida pero acotada, y sin un ciclo estacional completo.
- El snapshot del anio en curso puede cambiar retroactivamente; el resultado vale
  para los hashes de la seccion 3 y debe regenerarse si cambian.
- La comuna excluida por falta de historia no recibe pronostico: el producto debe
  mostrarla como "sin pronostico", nunca con cero.
- El target son **atenciones (eventos), no personas unicas**, y la demanda
  observada refleja utilizacion y oferta, no prevalencia.
