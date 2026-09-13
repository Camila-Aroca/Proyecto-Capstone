# EDA: Dimensión canónica de oferta de urgencia (RM) — `dim_oferta_urgencia_rm`

**Fecha de ejecución:** 2026-09-13
**Fuentes:** `data/processed/establecimientos_rm_clean.parquet` (1.172 establecimientos RM, snapshot actual), `data/processed/urgencias/urgencias_rm_2021..2025.parquet` (período canónico cerrado, evidencia de reporte). `urgencias_rm_2020.parquet` y `urgencias_rm_2026.parquet` se citan únicamente como contexto EDA en la sección 6, nunca como insumo de las columnas de evidencia del output.
**Output evaluado:** `data/processed/geo/dim_oferta_urgencia_rm.parquet` (174 filas), generado por `python scripts/run_pipeline.py --stage build_dim_oferta_urgencia_rm`.

Este EDA documenta el bloque de accesibilidad territorial en su primera etapa (definición de oferta), sin implementar todavía OSM/GTFS ni isócronas.

**Dos temporalidades, no confundir:**
1. **Universo y criterio de inclusión → snapshot ACTUAL** del maestro DEIS (`establecimientos_rm_clean.parquet`).
2. **Evidencia de reporte (`reporto_id1_periodo`, `reporto_id36_periodo`, `ultimo_ano_reporte_id36`, `tipo_urgencia_reportado`) → período canónico CERRADO 2021-2025.** Se excluye 2020 por la discontinuidad metodológica de salud mental documentada en `reports/eda/eda_demanda_urgencias_rm.md` (DEIS incorporó la obligatoriedad/desglose de ID36 recién a fines de 2020) y 2026 por ser un año parcial y mutable.

## 1. Universo base en el maestro (hecho observado, snapshot actual)

Sobre las 1.172 filas de `establecimientos_rm_clean.parquet`:

| `tipo_establecimiento_glosa` | Total en maestro | Vigentes | Cerrados |
|---|---:|---:|---:|
| Hospital | 47 | 45 | 2 |
| SAPU | 105 | 91 | 14 |
| SAR | 26 | 26 | 0 |
| SUR | 11 | 11 | 0 |
| **Total core (Hospital+SAPU+SAR+SUR)** | **189** | **173** | **16** |

El estado `estado_funcionamiento` presenta dos grafías equivalentes en la fuente: `"Vigente en Operación Habitual"` (1.059 filas) y `"Vigente en operación habitual"` (15 filas). El filtro de vigencia normaliza a minúsculas antes de comparar; sin esa normalización se pierden 15 establecimientos vigentes en silencio.

Esta sección no depende de ningún año de Urgencias: es puramente snapshot actual del maestro.

## 2. Excluidos y evidencia de por qué (hecho observado, período 2021-2025)

| Tipo excluido | Total en maestro | Reportan alguna vez en Urgencias 2021-2025 |
|---|---:|---:|
| COSAM | 47 | **0** |
| CESFAM + CECOSF + PSR | 299 | **1** (excepción CEAR, ver sección 3) |

100% de los 47 COSAM tienen `tiene_servicio_urgencia = "NO"` y `tipo_urgencia` nulo en el maestro, y 0 aparecen en los Parquet de Urgencias 2021-2025. Es evidencia consistente (maestro + reporte real) de que no son dispositivos de urgencia.

## 3. Excepción CEAR (hecho observado, período 2021-2025)

Los Parquet de Urgencias publican `tipo_establecimiento_urgencia` con dominio cerrado de 5 valores: `{SAPU, Hospital, SAR, SUR, CEAR}`. Dentro de 2021-2025, `CEAR` aparece asociado a un único `establecimiento_codigo`: `112320` (CESFAM Juan Pablo II, La Reina), cuyo `tipo_establecimiento_glosa` en el maestro es `"Centro de Salud Familiar (CESFAM)"`, vigente.

Detalle anual dentro del período canónico:

| Año | ID1 (total) | ID36 (total) |
|---:|---:|---:|
| 2021 | 4.552 | 10 |
| 2022 | 10.438 | 1 |
| 2023 | 4.090 | 1 |
| 2024 | *(sin fila reportada)* | *(sin fila reportada)* |
| 2025 | 0 | 0 |

`reporto_id1_periodo=True`, `reporto_id36_periodo=True`, `ultimo_ano_reporte_id36=2023` (último año dentro de 2021-2025 con `ID36>0`; 2025 tiene fila pero con total 0, por lo que no cuenta). La excepción sigue respaldada por evidencia dentro del período canónico cerrado.

La detección se hace dinámicamente contra la fuente (no hay un código hardcodeado como excepción fija); si en una ejecución futura este establecimiento deja de reportar `CEAR` en 2021-2025, deja de incluirse como excepción automáticamente.

## 4. Instituto Psiquiátrico Horwitz Barak: por qué no se usan los flags del maestro (hecho observado, período 2021-2025)

El maestro marca el Instituto Psiquiátrico Dr. José Horwitz Barak (`109102`, tipo `Hospital`, vigente) con `tiene_servicio_urgencia = "NO"` y `tipo_urgencia = "Hospitalaria Especializada"`. Sin embargo, en Urgencias 2021-2025 reporta:

| Año | Atenciones ID1 | Atenciones ID36 | % ID36/ID1 |
|---:|---:|---:|---:|
| 2021 | 17.107 | 15.557 | 90,9% |
| 2022 | 21.848 | 19.544 | 89,5% |
| 2023 | 16.615 | 15.808 | 95,1% |
| 2024 | 18.024 | 18.024 | 100,0% |
| 2025 | 18.537 | 18.537 | 100,0% |

En contraste, el Hospital Psiquiátrico El Peral (`113170`), también con `tiene_servicio_urgencia = "NO"`, tiene 0 registros en Urgencias en todos los años del período. Ambos comparten el mismo flag en el maestro pero tienen comportamiento de reporte opuesto: el flag del maestro no es un predictor confiable de si el establecimiento reporta actividad de urgencia. Por eso el criterio de inclusión de esta dimensión ignora `tiene_servicio_urgencia`/`tipo_urgencia` del maestro y se basa en `tipo_establecimiento_glosa` + `estado_funcionamiento`, complementado con evidencia de reporte real cuando corresponde (excepción CEAR).

## 5. Resultado final: `dim_oferta_urgencia_rm` (174 filas)

| `tipo_establecimiento` | Filas | `criterio_inclusion_oferta` |
|---|---:|---|
| Hospital | 45 | catalogo_core |
| SAPU | 91 | catalogo_core |
| SAR | 26 | catalogo_core |
| SUR | 11 | catalogo_core |
| CESFAM (Juan Pablo II, La Reina) | 1 | excepcion_cear_documentada |
| **Total** | **174** | |

- **Unicidad:** 0 `establecimiento_codigo` duplicados.
- **Cobertura comunal:** 52/52 comunas RM tienen al menos un establecimiento de oferta.
- **Cobertura de coordenadas:** 173/174 (99,4%) con `latitud`/`longitud` válidas. El único sin coordenadas es `202306` (SUR Juan Pablo II, Lampa) — mismo caso ya identificado en `reports/eda/eda_establecimientos_rm.md` como el único dispositivo de urgencia vigente sin georreferenciar. No se imputó. Sin cambios respecto a la ventana 2020-2026 evaluada previamente: el conteo de establecimientos y su cobertura de coordenadas dependen del maestro (snapshot actual), no de la ventana de evidencia.
- **Evidencia de reporte, período canónico 2021-2025:** 149/174 (85,6%) reportaron `ID1` alguna vez; 148/174 (85,1%) reportaron `ID36>0` alguna vez. 25 establecimientos del tipo correcto nunca reportaron actividad en el período — pertenecen a la oferta por tipo/vigencia, no por evidencia de reporte (por diseño: no se exige `ID36>0` para pertenecer a la oferta).
- **Coherencia de flags:** en el 100% de los casos, `reporto_id36_periodo=True` implica `reporto_id1_periodo=True` (validado también como regla dura en `validate_dim_oferta`).

## 6. Contexto EDA: 2020 y 2026 (fuera del período canónico, no alimentan el output)

Se citan aquí únicamente como contexto adicional, claramente separados de las columnas de evidencia del output:

- **2020:** el Instituto Psiquiátrico Horwitz Barak (`109102`) tiene **0 filas** en `urgencias_rm_2020.parquet`; consistente con la discontinuidad metodológica general de salud mental ya documentada para ese año.
- **2026 (parcial):** el mismo establecimiento reporta 12.498 atenciones ID1, de las cuales 12.498 (100%) son ID36, en línea con la tendencia 2024-2025. No se usa para `ultimo_ano_reporte_id36` porque el año está en curso y el RAW es mutable.
- El CESFAM Juan Pablo II (excepción CEAR) no tiene actividad `CEAR` verificada fuera de 2021-2025 en esta revisión; no cambia la excepción documentada.

## 7. Limitaciones

- El período de evidencia (2021-2025) es una ventana empírica cerrada, no un atributo permanente: un establecimiento sin reporte en este período podría reportar en años futuros, y esta dimensión no se actualiza automáticamente para eso; requiere regenerarse.
- No es posible determinar, únicamente con estos datos, qué proporción de la actividad `ID36` de un establecimiento corresponde específicamente a psiquiatría de urgencia vs. otras causas de salud mental agregadas (`ID36` incluye `ID37` R45.8 junto con `ID38-ID41`, F-chapter).
- La excepción CEAR es un caso único observado en el snapshot actual dentro de 2021-2025; no se puede descartar que existan otros casos de establecimientos "mal tipificados" en el maestro para años fuera de este período.
- Esta dimensión no incorpora capacidad, dotación ni red de derivación (ya documentado como ausente en `reports/eda/eda_maestro_establecimientos_y_red.md`).

## 8. Decisión recomendada

Usar `dim_oferta_urgencia_rm.parquet` como el insumo de establecimientos para la futura capa de accesibilidad territorial (OSM/GTFS, isócronas), sin mezclar en esta etapa el criterio de inclusión (snapshot actual) con la evidencia temporal de reporte (período canónico 2021-2025), que queda disponible como atributo descriptivo, no como filtro.
