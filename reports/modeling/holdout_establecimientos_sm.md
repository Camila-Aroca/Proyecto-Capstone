# Evaluación en holdout del pronóstico por establecimiento

Generado por `scripts/evaluate_holdout_establecimientos.py` (stage `evaluate_holdout_establecimientos_sm`). No editar a mano. Evalúa la selección congelada en `reports/modeling/benchmark_establecimientos_sm_seleccion.json`.

## Snapshot evaluado

La fuente del año en curso es mutable: estas cifras valen para este snapshot.

| ano | raw_sha256 | procesado_sha256 | estado_procedencia |
|---|---|---|---|
| 2026 | faaf8af53e0cac2b68f4b6cd6eebffdb079b172a7f2784ff90d5907bad0a1fdb | 3754c5b2586508f4bea45c87f8786573ac8b71265a43e1a87f3ed2c3b64538c8 | difiere_del_registrado |

Semanas regulares excluidas por estar incompletas: 2026-S40 (2 días).

## 1. Atenciones de urgencia en salud mental (ID36)

Modelo congelado: **`poisson_glm_global_conformal`**. 39 semanas de holdout evaluadas.

### 1.1 Universo fijo

125 establecimientos con todas las semanas del holdout. Se excluyen 8 del universo del benchmark por dejar de reportar, con 1.05% del volumen del año en curso:

| establecimiento_codigo | establecimiento_glosa | tipo | semanas_reportadas | ultima_semana | volumen | semanas_esperadas | share_pct |
|---|---|---|---|---|---|---|---|
| 112820 | SAPU Centro de Urgencia Ñuñoa | SAPU | 6 | 2026-04-12 | 103 | 39 | 0.13 |
| 200124 | SAPU Dr. Gustavo Molina | SAPU | 0 |  |  | 39 | 0.0 |
| 200142 | SAPU La Reina | SAPU | 8 | 2026-04-26 | 26 | 39 | 0.03 |
| 109813 | SAPU Nº 2 Irene Frei de Cid | SAPU | 37 | 2026-09-27 | 339 | 39 | 0.43 |
| 200135 | SAPU Dr. Edelberto Elgueta | SAPU | 18 | 2026-05-03 | 92 | 39 | 0.12 |
| 200132 | SAPU María Pinto | SAPU | 18 | 2026-05-03 | 94 | 39 | 0.12 |
| 200041 | SAPU Libertadores | SAPU | 33 | 2026-09-27 | 175 | 39 | 0.22 |
| 109890 | SAPU Cristo Vive | SAPU | 11 | 2026-04-19 | 2 | 39 | 0.0 |

### 1.2 Modelos en el holdout

| modelo | MASE total | cobertura total | calibrado total | MASE establecimientos | cobertura establecimientos | calibrado establecimientos | MASE promedio |
|---|---|---|---|---|---|---|---|
| hibrido_glm_region_lgbm_comuna_conformal | 0.7922 | 0.7344 | False | 0.6968 | 0.7987 | True | 0.7445 |
| poisson_glm_global_conformal | 0.7922 | 0.7344 | False | 0.7102 | 0.7937 | False | 0.7512 |
| lightgbm_global_conformal | 0.9177 | 0.7812 | True | 0.6983 | 0.7995 | True | 0.808 |
| baseline_estacional | 0.8788 | 0.7617 | True | 0.9768 | 0.8071 | False | 0.9278 |

### 1.3 Contra el baseline

| nivel | evaluaciones | cambio (%) | pronósticos en que mejora | p-valor |
|---|---|---|---|---|
| total | 256 | -9.86 | 48.4% | 0.3368 |
| establecimientos | 32000 | -21.77 | 60.4% | 0.0 |

### 1.4 Degradación respecto del backtest

| nivel | MASE backtest | MASE holdout | habilidad backtest (%) | habilidad holdout (%) |
|---|---|---|---|---|
| total | 0.908 | 0.7922 | 6.2 | 9.9 |
| establecimientos | 0.7206 | 0.7102 | 25.2 | 27.3 |

### 1.5 Alternativas frente al elegido

Cambio del error de cada alternativa respecto del elegido (negativo: la alternativa es mejor).

| alternativa | nivel | cambio (%) | p-valor |
|---|---|---|---|
| lightgbm_global_conformal | total | 15.85 | 0.084 |
| lightgbm_global_conformal | establecimientos | -7.71 | 0.0 |
| hibrido_glm_region_lgbm_comuna_conformal | total | -0.0 | 1.0 |
| hibrido_glm_region_lgbm_comuna_conformal | establecimientos | -7.64 | 0.0 |

### 1.6 Veredicto

| criterio | se cumple |
|---|---|
| supera al baseline con diferencia significativa en los establecimientos | sí |
| conserva habilidad frente al baseline en los establecimientos | sí |
| cobertura de los establecimientos dentro de la tolerancia | no |
| ninguna alternativa es significativamente mejor en los establecimientos | no |

## 2. Hospitalizaciones derivadas desde la urgencia por F00-F99 (ID42)

Modelo congelado: **`lightgbm_global_conformal`**. 39 semanas de holdout evaluadas.

### 2.1 Universo fijo

12 establecimientos con todas las semanas del holdout. Ninguno del universo del benchmark se excluye.

### 2.2 Modelos en el holdout

| modelo | MASE total | cobertura total | calibrado total | MASE establecimientos | cobertura establecimientos | calibrado establecimientos | MASE promedio |
|---|---|---|---|---|---|---|---|
| lightgbm_global_conformal | 0.3869 | 0.9102 | False | 0.779 | 0.7855 | False | 0.583 |
| hibrido_glm_region_lgbm_comuna_conformal | 0.4503 | 0.918 | False | 0.7677 | 0.7969 | True | 0.609 |
| poisson_glm_global_conformal | 0.4503 | 0.918 | False | 0.7897 | 0.7842 | False | 0.62 |
| baseline_estacional | 0.5708 | 0.8594 | False | 1.0555 | 0.7695 | False | 0.8132 |

### 2.3 Contra el baseline

| nivel | evaluaciones | cambio (%) | pronósticos en que mejora | p-valor |
|---|---|---|---|---|
| total | 256 | -32.22 | 69.5% | 0.0 |
| establecimientos | 3072 | -28.38 | 61.8% | 0.0 |

### 2.4 Degradación respecto del backtest

| nivel | MASE backtest | MASE holdout | habilidad backtest (%) | habilidad holdout (%) |
|---|---|---|---|---|
| total | 0.4477 | 0.3869 | 8.8 | 32.2 |
| establecimientos | 0.7918 | 0.779 | 24.6 | 26.2 |

### 2.5 Alternativas frente al elegido

Cambio del error de cada alternativa respecto del elegido (negativo: la alternativa es mejor).

| alternativa | nivel | cambio (%) | p-valor |
|---|---|---|---|
| poisson_glm_global_conformal | total | 16.39 | 0.0183 |
| poisson_glm_global_conformal | establecimientos | 10.98 | 0.0 |
| hibrido_glm_region_lgbm_comuna_conformal | total | 16.39 | 0.0183 |
| hibrido_glm_region_lgbm_comuna_conformal | establecimientos | 2.56 | 0.006 |

### 2.6 Veredicto

| criterio | se cumple |
|---|---|
| supera al baseline con diferencia significativa en los establecimientos | sí |
| conserva habilidad frente al baseline en los establecimientos | sí |
| cobertura de los establecimientos dentro de la tolerancia | no |
| ninguna alternativa es significativamente mejor en los establecimientos | sí |

## 3. Limitaciones

- El holdout cubre parte de un solo año: no incluye todas las estaciones.
- Las semanas evaluadas se superponen entre horizontes y orígenes: las evaluaciones no son independientes.
- Usar este holdout para elegir otro modelo lo dejaría de ser una evaluación independiente de ese modelo.
