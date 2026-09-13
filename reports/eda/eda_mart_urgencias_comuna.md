# EDA: `mart_urgencias_comuna_weekly` y `mart_urgencias_comuna_monthly`

Reproducible mediante `python -m scripts.eda_mart_urgencias_comuna` (script de
solo lectura; no modifica los marts). Resumen de apoyo en
[`eda_mart_urgencias_comuna_resumen.csv`](eda_mart_urgencias_comuna_resumen.csv).
Complementa los diccionarios en `reports/dictionary/diccionario_mart_urgencias_comuna_weekly.md`
y `reports/dictionary/diccionario_mart_urgencias_comuna_monthly.md`.

## 1. Grano y cobertura

| | `mart_urgencias_comuna_weekly` | `mart_urgencias_comuna_monthly` |
|---|---|---|
| Grano | comuna × año × semana DEIS | comuna × año × mes calendario |
| Filas | 13,362 | 3,060 |
| Columnas | 25 | 25 |
| Comunas RM cubiertas | 51 / 52 | 51 / 52 |
| Periodos por comuna | 262 semanas (uniforme, 2021-2025) | 60 meses (uniforme, 2021-2025) |

Ambos marts tienen exactamente el mismo número de periodos para cada una de
las 51 comunas presentes (262 semanas y 60 meses respectivamente): no hay
huecos de semanas/meses para las comunas que sí están representadas.

**Comuna faltante: Vitacura (`13132`).** No aparece en ninguno de los dos
marts (0 filas en todo 2021-2025).

- **Hecho observado (2021-2025):** `urgencias_rm_2021..2025.parquet` no
  contiene ninguna fila con `comuna_codigo = "13132"` para ninguna causa (no
  solo para ID1/ID35/ID36-41). La ausencia se origina en
  `clean_urgencias`/el RAW DEIS de ese periodo histórico, no en la agregación
  del mart. No se imputó ni se completó con ceros.
- **Contexto no histórico (catálogo actual):** `establecimientos_rm_clean.parquet`
  es un snapshot vigente del maestro DEIS de establecimientos, no una
  fotografía de 2021-2025; registra hoy 29 establecimientos en Vitacura
  (mayoritariamente clínicas y centros de salud privados, más un SAPU). Este
  dato describe el presente, no el periodo histórico auditado, y **no se usa
  aquí como explicación de la ausencia observada en 2021-2025**.
- **Hipótesis no confirmada** (no verificable con los datos disponibles):
  que los establecimientos de Vitacura no reportan al sistema REM/Urgencias
  DEIS. Se deja explícitamente como hipótesis, no como causa establecida.

## 2. Temporalidad DEIS

- Calendario semanal DEIS, no ISO-8601: `semana` va de 1 a 53; hay 102 filas
  con `semana = 53` (semanas 53 observadas en el calendario DEIS de algunos
  años), no es un error de agregación.
- El mensual usa mes calendario estándar derivado de `fecha` diaria (1 a 12),
  independiente del calendario semanal DEIS; por eso ambos marts no
  reconcilian fila a fila, solo al agregar por comuna×año (sección 4).

## 3. Causas DEIS (ID1, ID35, ID36-41)

Glosas observadas directamente en `glosa_causa` del origen limpio
(`urgencias_rm_2021..2025`; varían levemente en formato/capitalización entre
años para el mismo `id_causa`, el `id_causa` numérico es la llave estable):

| ID causa | Glosa observada (ejemplo) | Rol |
|---|---|---|
| 1 | Sección 1. Total atenciones de urgencia | Universo total de atenciones de urgencia (todas las causas). |
| 35 | Lesiones autoinfligidas intencionalmente (X60-X84) | Causa externa, no forma parte de la jerarquía ID36. |
| 36 | Total causas de trastornos mentales (F00-F99) | Subconjunto de ID1; agregado de salud mental. |
| 37 | Ideación suicida (R45.8) | Componente de ID36. |
| 38 | Trastornos mentales y del comportamiento por sustancias psicoactivas (F10-F19) | Componente de ID36. |
| 39 | Trastornos del humor (afectivos) (F30-F39) | Componente de ID36. |
| 40 | Trastornos neuróticos, relacionados con el estrés y somatomorfos (F40-F48), incluye pánico (F41.0) | Componente de ID36. |
| 41 | Otros trastornos mentales no contenidos en las categorías anteriores | Componente de ID36 (residual). |

Totales de atenciones 2021-2025 (suma `mart_urgencias_comuna_weekly`, 51 comunas):

| Causa | Atenciones totales 2021-2025 |
|---|---|
| ID1 | 28,840,470 |
| ID35 | 12,685 |
| ID36 | 501,395 |
| ID37 | 28,197 |
| ID38 | 49,666 |
| ID39 | 42,520 |
| ID40 | 270,349 |
| ID41 | 110,663 |

Sin nulos en ninguna columna `atenciones_id*` en ambos marts: cuando una
causa no tuvo atenciones en una comuna×periodo, el pivot produce la fila con
0 (no fila ausente), salvo cuando *ninguna* causa del contrato tuvo
atenciones en toda la comuna en todo el periodo (caso Vitacura, sección 1).

## 4. Reportantes y reconciliación semanal↔mensual

- `n_establecimientos_reportantes_id1` y `n_establecimientos_reportantes_id36`
  son **idénticos en el 100% de las 13,362 filas** del mart semanal: los
  establecimientos que reportan ID1 en una comuna×semana son exactamente los
  mismos que reportan ID36 en esa misma comuna×semana.
- Reconciliación anual ID1/ID36, semanal vs. mensual (ambos agregados a
  comuna×año): **coincide exactamente** para los 5 años 2021-2025 (verificado
  por código, `DataFrame.equals` = `True`). Ejemplo (suma RM, ambos marts):

| Año | Atenciones ID1 | Atenciones ID36 |
|---|---|---|
| 2021 | 4,476,342 | 81,130 |
| 2022 | 6,120,119 | 95,194 |
| 2023 | 6,037,435 | 104,919 |
| 2024 | 6,135,659 | 107,648 |
| 2025 | 6,070,915 | 112,504 |

## 5. Ratios internos

Los ratios `proporcion_id36_sobre_id1` y `proporcion_id37..41_sobre_id36`
quedan nulos (no 0) cuando su denominador es 0. En el mart semanal:
`proporcion_id36_sobre_id1` tiene 5 filas nulas; cada `proporcion_id37..41_sobre_id36`
tiene 412 filas nulas (semanas/comunas sin ninguna atención ID36 en ese
periodo). Todos los valores no nulos observados están en el dominio [0, 1]
(validado también en `build_urgencias_comuna_marts.validate_mart`).

## 6. Tasas por 10.000 habitantes

Distribución de `tasa_atenciones_id36_por_10000` (mart semanal, 13,362 filas):
media 2.64; desviación estándar 2.82; mínimo 0; mediana 2.04; máximo 24.59.

**Advertencia de interpretación (obligatoria):** estas tasas cuantifican
**intensidad territorial de atenciones (evento)** respecto de la población
comunal —no personas únicas atendidas—, usando como denominador una
población anual fija para todas las semanas/meses del año (INE, proyecciones,
sin interpolar). No son prevalencia ni incidencia poblacional y no deben
leerse como "porcentaje de población afectada"; una misma persona puede
generar múltiples atenciones contabilizadas en la misma tasa.

## 7. Limitaciones

- Cobertura de 51/52 comunas RM (falta Vitacura, `13132`; sección 1); no
  imputada.
- El origen DEIS puede tener subregistro no cuantificado en este EDA (fuera
  de alcance: auditoría de subregistro ya cubierta en reports de Urgencias
  existentes, p. ej. `eda_demanda_urgencias_rm.md`).
- Semana DEIS ≠ semana ISO-8601; comparaciones con series ISO externas deben
  normalizarse primero.
- Esta dimensión de vulnerabilidad/demanda es territorial y agregada: no
  permite trazabilidad a nivel de paciente ni de establecimiento individual.
