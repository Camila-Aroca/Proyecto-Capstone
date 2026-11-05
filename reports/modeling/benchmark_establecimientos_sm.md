# Benchmark del pronóstico por establecimiento

Generado por `scripts/run_benchmark_establecimientos.py` (stage `benchmark_establecimientos_sm`). No editar a mano. Insumo: `mart_urgencias_establecimiento_weekly`; su EDA está en `reports/eda/eda_mart_urgencias_establecimiento_weekly.md`.

## Diseño

- Ventana: semanas regulares desde 2022. Se excluye 2021 porque el Instituto Horwitz, el establecimiento de mayor volumen, no reporta sus primeras semanas, y porque la razón ID42/ID36 cambia de nivel entre 2021 y 2023.
- Universo: establecimientos con todas las semanas de la ventana reportadas y un promedio semanal del objetivo de al menos 1, y de al menos 0.5 en cada año de la ventana (una serie que empieza a registrar a mitad de ventana no tiene historia comparable y su escala MASE no es interpretable). Una semana sin reporte no se imputa; el detalle por establecimiento está en `reports/modeling/benchmark_establecimientos_sm_universo.csv`.
- Backtesting: 13 orígenes cada 4 semanas (t = 151 a 199), horizontes 1 a 8. Los modelos son los del registro único (`src/models/registry.py`), con la misma configuración del modelo comunal.
- Jerarquía: total de los establecimientos → establecimientos. Los modelos híbridos pronostican el total con el GLM y lo reparten según el boosting (top-down).

## 1. Atenciones de urgencia en salud mental (ID36)

### 1.1 Universo

- **133 establecimientos** entran al panel de un total de 152. Exclusiones: semanas sin reporte en la ventana (12), volumen medio menor a 0.5 por semana en algún año de la ventana (5), volumen medio menor a 1 por semana (2).
- Covariables, siempre rezagadas al menos un horizonte: `atenciones_id1`.
- La serie total es la suma de los establecimientos incluidos, no el total regional publicado.

### 1.2 Comparación de modelos

MASE mediano por nivel, promedio de los horizontes (menor es mejor; bajo 1 supera al baseline ingenuo en su propia escala). Calibrado = cobertura dentro de la tolerancia muestral alrededor del 80%.

| modelo | MASE total | cobertura total | calibrado total | MASE establecimientos | cobertura establecimientos | calibrado establecimientos | MASE promedio |
|---|---|---|---|---|---|---|---|
| hibrido_glm_region_lgbm_comuna_conformal | 0.908 | 0.8654 | True | 0.7 | 0.8112 | False | 0.804 |
| hibrido_glm_region_lgbm_comuna | 0.908 | 0.875 | True | 0.7 | 0.7282 | False | 0.804 |
| poisson_glm_global | 0.908 | 0.875 | True | 0.7212 | 0.8436 | False | 0.8146 |
| poisson_glm_global_conformal | 0.908 | 0.8654 | True | 0.7212 | 0.8037 | True | 0.8146 |
| lightgbm_global | 1.0611 | 0.7308 | True | 0.6949 | 0.732 | False | 0.878 |
| lightgbm_global_conformal | 1.0611 | 0.7885 | True | 0.6949 | 0.804 | True | 0.878 |
| baseline_estacional | 0.9684 | 0.7596 | True | 0.9712 | 0.7927 | False | 0.9698 |
| baseline_estacional_drift | 1.0104 | 0.7596 | True | 0.9869 | 0.7902 | False | 0.9987 |

### 1.3 Selección

**Elegido: `poisson_glm_global_conformal`** — menor MASE promedio entre los modelos que superan al baseline con cobertura calibrada en el total y en los establecimientos.

Contraste pareado contra el baseline sobre los mismos pronósticos (Wilcoxon):

| nivel | evaluaciones | error baseline | error elegido | cambio (%) | pronósticos en que mejora | p-valor |
|---|---|---|---|---|---|---|
| total | 104 | 0.9684 | 0.908 | -6.24 | 51.9% | 0.3973 |
| establecimientos | 13832 | 1.0226 | 0.7696 | -24.74 | 62.3% | 0.0 |

### 1.4 Desde qué volumen conviene el modelo

MASE mediano por establecimiento según su volumen semanal medio en la ventana, y porcentaje de establecimientos donde el elegido tiene menor MASE que el baseline.

| promedio semanal | establecimientos | MASE elegido | MASE baseline | % que supera al baseline |
|---|---|---|---|---|
| 1 a 5 | 15 | 0.7634 | 1.1206 | 100.0 |
| 5 a 10 | 61 | 0.7056 | 0.9908 | 93.4 |
| 10 a 25 | 47 | 0.7116 | 0.9761 | 93.6 |
| 25 o más | 10 | 0.7594 | 1.0348 | 100.0 |

## 2. Hospitalizaciones derivadas desde la urgencia por F00-F99 (ID42)

### 2.1 Universo

- **12 establecimientos** entran al panel de un total de 152. Exclusiones: no es hospital (126), volumen medio menor a 1 por semana (13), volumen medio menor a 0.5 por semana en algún año de la ventana (1).
- Covariables, siempre rezagadas al menos un horizonte: `atenciones_id1`, `atenciones_id36`.
- La serie total es la suma de los establecimientos incluidos, no el total regional publicado.

### 2.2 Comparación de modelos

MASE mediano por nivel, promedio de los horizontes (menor es mejor; bajo 1 supera al baseline ingenuo en su propia escala). Calibrado = cobertura dentro de la tolerancia muestral alrededor del 80%.

| modelo | MASE total | cobertura total | calibrado total | MASE establecimientos | cobertura establecimientos | calibrado establecimientos | MASE promedio |
|---|---|---|---|---|---|---|---|
| lightgbm_global | 0.4477 | 0.7596 | True | 0.7918 | 0.7436 | False | 0.6198 |
| lightgbm_global_conformal | 0.4477 | 0.8558 | True | 0.7918 | 0.8101 | True | 0.6198 |
| poisson_glm_global_conformal | 0.4864 | 0.8846 | False | 0.7774 | 0.8181 | True | 0.6319 |
| poisson_glm_global | 0.4864 | 0.8654 | True | 0.7774 | 0.8702 | False | 0.6319 |
| hibrido_glm_region_lgbm_comuna | 0.4864 | 0.8654 | True | 0.8298 | 0.7292 | False | 0.6581 |
| hibrido_glm_region_lgbm_comuna_conformal | 0.4864 | 0.8846 | False | 0.8298 | 0.7941 | True | 0.6581 |
| baseline_estacional_drift | 0.4687 | 0.8942 | False | 1.0246 | 0.7436 | False | 0.7467 |
| baseline_estacional | 0.491 | 0.8942 | False | 1.0501 | 0.746 | False | 0.7706 |

### 2.3 Selección

**Elegido: `lightgbm_global_conformal`** — menor MASE promedio entre los modelos que superan al baseline con cobertura calibrada en el total y en los establecimientos.

Contraste pareado contra el baseline sobre los mismos pronósticos (Wilcoxon):

| nivel | evaluaciones | error baseline | error elegido | cambio (%) | pronósticos en que mejora | p-valor |
|---|---|---|---|---|---|---|
| total | 104 | 0.491 | 0.4477 | -8.81 | 61.5% | 0.0494 |
| establecimientos | 1248 | 1.0489 | 0.7719 | -26.41 | 64.7% | 0.0 |

### 2.4 Desde qué volumen conviene el modelo

MASE mediano por establecimiento según su volumen semanal medio en la ventana, y porcentaje de establecimientos donde el elegido tiene menor MASE que el baseline.

| promedio semanal | establecimientos | MASE elegido | MASE baseline | % que supera al baseline |
|---|---|---|---|---|
| 1 a 5 | 3 | 0.8222 | 1.2047 | 100.0 |
| 5 a 10 | 6 | 0.8101 | 1.0788 | 100.0 |
| 10 a 25 | 2 | 0.74 | 1.0582 | 100.0 |
| 25 o más | 1 | 0.8059 | 1.033 | 100.0 |

## 3. Limitaciones

- Las cifras son atenciones u hospitalizaciones (eventos), no personas.
- ID42 se registra donde ocurrió la urgencia, no donde quedó hospitalizado el paciente: no mide la ocupación de camas del establecimiento.
- Con 13 orígenes, la serie total aporta pocas evaluaciones: el contraste detecta diferencias grandes, no pequeñas.
- El universo exige cobertura completa: un establecimiento nuevo (por ejemplo, un SAR abierto en la ventana) no se pronostica hasta acumular historia.
- No se evalúa todavía sobre el año en curso; esa evaluación corresponde a una etapa de holdout.
