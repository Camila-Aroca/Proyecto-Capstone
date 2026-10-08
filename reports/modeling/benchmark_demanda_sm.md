# Benchmark de modelos de demanda de urgencia en salud mental (RM)

Reproducible mediante `python -m scripts.run_demand_benchmark`. Metricas por
serie y horizonte en
[`benchmark_demanda_sm_resumen.csv`](benchmark_demanda_sm_resumen.csv).

Corresponde a las fases de *Modeling* y *Evaluation* (CRISP-DM). El
entendimiento de los datos que lo sustenta esta en
[`../eda/eda_series_demanda_sm.md`](../eda/eda_series_demanda_sm.md).

## 1. Diseno experimental

| Parametro | Valor |
|---|---|
| Panel de dos niveles | 52 series (51 comunas + agregado RM) |
| Panel de tres niveles | 58 series (agrega 6 Servicios de Salud) |
| Periodos | 260 semanas regulares, 2021-2025 |
| Target | `atenciones_id36` (conteo, ID37 incluido) |
| Horizontes | 4, 5, 6, 7, 8 semanas |
| Origenes de pronostico | 13 (paso 4), de t=203 a t=251 |
| Evaluaciones por modelo | 65 en la region, 3,315 en comunas |
| Nivel de los intervalos | 80% |
| Semilla | 42 |

**Estrategia directa, sin fuga temporal.** Para pronosticar `y[t]` a horizonte
`h`, la matriz de features solo contiene valores observados hasta `t - h`. El
modelo se reentrena en cada origen usando exclusivamente `t <= origen`.

**MASE** es la metrica principal: escala el error por el del baseline
estacional calculado sobre la historia previa al primer origen. MASE < 1
significa superar a esa referencia. Se prefiere sobre MAPE porque hay comunas
con semanas en cero, donde MAPE es indefinido.

**Calibracion.** Un nivel se marca calibrado si su cobertura observada cae a
menos de 0.0972 del nominal en la region (65
evaluaciones) y a menos de 0.0136 en comunas
(3,315): la distancia que el azar explica al 95%. La tolerancia
supone evaluaciones independientes; como las comunas comparten origenes, la
real es algo mayor y la marca de comunas es por lo tanto exigente.

## 2. Resultados por modelo

Promedio de los 5 horizontes. Ordenado por MASE promedio entre
region y comunas.

| modelo | niveles | mase_region | mase_servicio | mase_comuna | cobertura_region | cobertura_comuna | amplitud_comuna | calibrado_region | calibrado_comuna |
|---|---|---|---|---|---|---|---|---|---|
| hibrido_3niveles_wls_structural | 3 | 0.555 | 0.5987 | 0.6776 | 0.9692 | 0.6959 | 19.74 | False | False |
| hibrido_3niveles_middle_out | 3 | 0.5848 | 0.6312 | 0.6734 | 0.9231 | 0.7294 | 19.83 | False | False |
| hibrido_glm_region_lgbm_comuna_conformal | 2 | 0.5953 |  | 0.6755 | 0.8769 | 0.8087 | 20.48 | True | True |
| hibrido_glm_region_lgbm_comuna | 2 | 0.5953 |  | 0.6755 | 0.8769 | 0.7339 | 21.01 | True | False |
| lightgbm_global_bottom_up | 2 | 0.6086 |  | 0.6721 | 0.9846 | 0.7345 | 19.94 | False | False |
| poisson_glm_global | 2 | 0.5953 |  | 0.6965 | 0.8769 | 0.8332 | 24.66 | True | False |
| poisson_glm_global_conformal | 2 | 0.5953 |  | 0.6965 | 0.8769 | 0.8 | 22.48 | True | True |
| hibrido_3niveles_top_down | 3 | 0.6634 | 0.639 | 0.6813 | 0.8769 | 0.7222 | 21.13 | True | False |
| lightgbm_global_conformal | 2 | 0.7001 |  | 0.6721 | 0.7846 | 0.809 | 20.41 | True | True |
| lightgbm_global | 2 | 0.7001 |  | 0.6721 | 0.6769 | 0.7345 | 19.94 | False | False |
| lightgbm_global_top_down | 2 | 0.7001 |  | 0.6794 | 0.6769 | 0.7285 | 20.09 | False | False |
| baseline_estacional | 2 | 0.7866 |  | 0.9218 | 0.8923 | 0.8087 | 31.7 | True | True |
| baseline_estacional_drift | 2 | 0.7856 |  | 0.926 | 0.8923 | 0.8075 | 31.71 | True | True |

## 3. Lectura

**Mejor en la region:** `hibrido_3niveles_wls_structural`, MASE 0.5550 frente a 0.7866 del baseline (29.4% menos error).

**Mejor en comunas:** `lightgbm_global`, `lightgbm_global_bottom_up`, `lightgbm_global_conformal` (empatados: mismo pronostico), MASE 0.6721 frente a 0.9218 del baseline (27.1% menos error).

Todos ellos tienen MASE mediano menor que 1 en todos los horizontes y niveles evaluados. Que un modelo gane en un nivel no implica que la diferencia con el segundo sea significativa: eso se prueba en las secciones 4 y 5.

## 4. Prediccion conforme frente a jerarquia por Servicio de Salud

Las dos propuestas atacan problemas distintos: la prediccion conforme apunta a
la **calibracion de los intervalos**; la jerarquia por Servicio apunta a la
**precision del pronostico puntual** via una reconciliacion con un nivel
intermedio. Se evalua cada una contra su propio objetivo.

### 4.1 Prediccion conforme

Cada modelo contra su version conforme, que conserva el pronostico puntual y
reemplaza el intervalo:

| modelo | nivel | cobertura_propia | cobertura_conforme | amplitud_propia | amplitud_conforme | cambio_amplitud_pct | max_dif_pronostico |
|---|---|---|---|---|---|---|---|
| poisson_glm_global | region | 0.8769 | 0.8769 | 516.37 | 504.57 | -2.3 | 0.0 |
| poisson_glm_global | comuna | 0.8332 | 0.8 | 24.66 | 22.48 | -8.8 | 0.0 |
| lightgbm_global | region | 0.6769 | 0.7846 | 466.35 | 602.86 | 29.3 | 0.0 |
| lightgbm_global | comuna | 0.7345 | 0.809 | 19.94 | 20.41 | 2.3 | 0.0 |
| hibrido_glm_region_lgbm_comuna | region | 0.8769 | 0.8769 | 516.37 | 504.57 | -2.3 | 0.0 |
| hibrido_glm_region_lgbm_comuna | comuna | 0.7339 | 0.8087 | 21.01 | 20.48 | -2.6 | 0.0 |

**Hecho observado:** a nivel comunal, la prediccion conforme acerca la cobertura al nominal en 3 de 3 modelos (error medio de cobertura 0.0549 -> 0.0059) y produce intervalos mas angostos en 2 de 3. El pronostico puntual es identico al del modelo base en todos los casos (diferencia maxima 0), de modo que el efecto se debe exclusivamente al intervalo.

**Inferencia:** los intervalos propios de cada modelo fallaban por la forma, no solo por el ancho: repartian mal la amplitud entre comunas de distinta escala. La normalizacion conforme corrige esa reparticion y por eso puede mejorar la cobertura sin ensanchar el intervalo.

### 4.2 Jerarquia por Servicio de Salud

Cada comuna se asigna al Servicio con mas establecimientos del maestro ubicados
en ella (el maestro no trae la pertenencia de la comuna, solo la de cada
establecimiento). Comunas por Servicio:

| servicio_id | servicio_glosa | comunas |
|---|---|---|
| SS_OCCIDENTE | Servicio de Salud Metropolitano Occidente | 15 |
| SS_SUR | Servicio de Salud Metropolitano Sur | 10 |
| SS_NORTE | Servicio de Salud Metropolitano Norte | 8 |
| SS_ORIENTE | Servicio de Salud Metropolitano Oriente | 7 |
| SS_SUR_ORIENTE | Servicio de Salud Metropolitano Sur Oriente | 7 |
| SS_CENTRAL | Servicio de Salud Metropolitano Central | 4 |

Comunas con establecimientos de mas de un Servicio (se asignan al mayoritario):

| comuna_codigo | servicio_id | participacion | servicios_en_comuna |
|---|---|---|---|
| 13101 | SS_CENTRAL | 0.783 | 2 |
| 13120 | SS_ORIENTE | 0.9 | 2 |
| 13123 | SS_ORIENTE | 0.944 | 2 |
| 13201 | SS_SUR_ORIENTE | 0.966 | 2 |

Comparacion pareada de cada hibrido de tres niveles contra el hibrido de dos
niveles (`hibrido_glm_region_lgbm_comuna`), sobre los mismos pronosticos. `error_a` es el de dos
niveles, `error_b` el de tres; `proporcion_b_mejor` es la fraccion de
pronosticos en que tres niveles tiene menor error; prueba de Wilcoxon pareada.

| reconciliacion | nivel | n | error_a | error_b | cambio_pct | proporcion_b_mejor | p_valor |
|---|---|---|---|---|---|---|---|
| top_down | region | 65 | 0.5953 | 0.6634 | 11.44 | 0.3385 | 0.002 |
| top_down | comuna | 3315 | 0.7003 | 0.7078 | 1.07 | 0.4724 | 0.0 |
| middle_out | region | 65 | 0.5953 | 0.5848 | -1.76 | 0.3692 | 0.683 |
| middle_out | comuna | 3315 | 0.7003 | 0.6898 | -1.5 | 0.5128 | 0.034 |
| wls_structural | region | 65 | 0.5953 | 0.555 | -6.77 | 0.4 | 0.8779 |
| wls_structural | comuna | 3315 | 0.7003 | 0.7111 | 1.54 | 0.5041 | 0.8306 |

**Hecho observado:** mejoras significativas (p < 0.05): `middle_out` en comuna (-1.50%, p = 0.034, mejor en 51.3% de los pronosticos). Todas las demas diferencias son compatibles con el azar. Empeoramientos significativos: `top_down` en region (+11.44%); `top_down` en comuna (+1.07%).

**Por que la media y la proporcion pueden discrepar:** una reconciliacion puede bajar el error **promedio** y aun asi ser peor en la mayoria de los pronosticos, si corrige unos pocos errores grandes. Por eso se reporta la proporcion de pronosticos en que gana y una prueba sobre rangos, no solo el promedio.

## 5. Seleccion del modelo

**Recomendacion:** `hibrido_glm_region_lgbm_comuna_conformal`. De los 11 modelos que superan al baseline, 3 tienen cobertura compatible con el nominal en ambos niveles, y este es el de menor MASE promedio (0.6354; region 0.5953, comunas 0.6755; cobertura region 0.877, comunas 0.809).

`hibrido_3niveles_wls_structural` tiene menor MASE promedio (0.6163) pero sus intervalos no estan calibrados. Frente al recomendado: region: -6.77% de error, p = 0.878; comuna: +1.54% de error, p = 0.831. Su ventaja de precision no es estadisticamente distinguible del azar en ningun nivel, de modo que no compensa la perdida de calibracion.

## 6. Coherencia jerarquica

Sin reconciliar, el pronostico regional de `lightgbm_global` y la suma de sus
pronosticos comunales no coinciden:

| horizonte | pronosticos | brecha_absoluta_media | brecha_relativa_media_pct | brecha_relativa_max_pct |
|---|---|---|---|---|
| 4 | 13 | 49.3208 | 2.4076 | 8.0611 |
| 5 | 13 | 67.7377 | 3.1469 | 10.0478 |
| 6 | 13 | 80.7336 | 3.8977 | 13.0024 |
| 7 | 13 | 82.6082 | 4.0673 | 9.0485 |
| 8 | 13 | 85.8957 | 3.9573 | 8.0584 |

Publicar ambos niveles sin reconciliar mostraria cifras que no cuadran entre el
indicador regional y el mapa comunal; por eso todos los hibridos reconcilian.

## 7. Que pesa en el modelo global

Importancia por ganancia del ultimo ajuste de `lightgbm_global`:

| feature | ganancia |
|---|---|
| series_code | 6067678.0 |
| y_lag_8 | 4683051.0 |
| y_lag_9 | 3588005.0 |
| y_media_13 | 2676105.0 |
| y_lag_10 | 2187789.0 |
| y_lag_52 | 1546532.0 |
| y_media_4 | 743564.0 |
| y_lag_11 | 197191.0 |
| atenciones_id1_lag_8 | 177066.0 |
| cos_1 | 16686.0 |

**Observacion:** la feature con mas ganancia es `series_code`. El modelo se apoya sobre todo en la identidad y el nivel de cada territorio, y despues en la inercia reciente de la serie.

## 8. Limitaciones

- El target son **atenciones (eventos), no personas unicas**.
- Cobertura de 51 de las 52 comunas RM: Vitacura (`13132`) no
  tiene registros en el mart y no se imputa.
- La pertenencia de cada comuna a un Servicio de Salud se **aproxima** por la
  mayoria de sus establecimientos; no es un dato explicito de la fuente.
- La garantia de la prediccion conforme supone intercambiabilidad entre la
  ventana de calibracion y el pronostico; con tendencia se cumple solo
  aproximadamente, por eso la cobertura se mide y no se da por garantizada.
- Los hiperparametros no se optimizaron por busqueda automatica: las cifras son
  un piso del desempeno alcanzable, no un techo.
- 13 origenes dan 65 evaluaciones de la serie
  regional: suficientes para detectar diferencias grandes, no pequenas.
- No se evalua todavia contra 2026: ese holdout requiere fijar el snapshot
  mutable del anio en curso por SHA256 antes de usarlo.
- No se implementa MinT con covarianza completa: con 13 origenes
  la matriz de covarianza entre 58 series seria inestable. La
  reconciliacion WLS estructural es la variante que no la requiere.
- La demanda observada refleja utilizacion y oferta instalada, no prevalencia ni
  necesidad sanitaria de la poblacion residente.
