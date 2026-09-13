# Diccionario de datos: `dim_oferta_urgencia_rm`

- **Ruta:** `data/processed/geo/dim_oferta_urgencia_rm.parquet`
- **Constructor:** `src/data/build_dim_oferta_urgencia_rm.py` (`build_dim_oferta_urgencia_rm`), stage `build_dim_oferta_urgencia_rm` en `PIPELINE.md`.
- **Grano:** una fila = un establecimiento de salud (`establecimiento_codigo`), único.
- **Dos temporalidades distintas, no una:**
  1. **Snapshot ACTUAL de oferta (universo y criterio de inclusión):** qué establecimientos vigentes constituyen hoy la oferta de atención de urgencia, según el maestro DEIS actual (`establecimientos_rm_clean.parquet`). No debe interpretarse como la oferta vigente en 2020, 2021 ni ningún año pasado.
  2. **Evidencia de reporte, período canónico CERRADO 2021-2025** (`reporto_id1_periodo`, `reporto_id36_periodo`, `ultimo_ano_reporte_id36`, `tipo_urgencia_reportado`): información temporal complementaria, no la definición de oferta. Excluye 2020 (discontinuidad metodológica no resuelta en el registro de salud mental, ver `reports/eda/eda_demanda_urgencias_rm.md`) y 2026 (año parcial y mutable). 2020/2026 solo se mencionan como contexto adicional en el EDA, nunca mezclados con estas columnas.
- **Fuentes:**
  - `data/processed/establecimientos_rm_clean.parquet` (universo base y atributos territoriales, snapshot actual).
  - `data/processed/urgencias/urgencias_rm_2021..2025.parquet` (evidencia de reporte, período canónico cerrado; solo columnas `ano`, `establecimiento_codigo`, `id_causa`, `total`, `tipo_establecimiento_urgencia`).

## Criterio de inclusión (`criterio_inclusion_oferta`)

- **`catalogo_core`:** `tipo_establecimiento` es exactamente `"Hospital"` o termina en el acrónimo DEIS `"(SAPU)"`, `"(SAR)"` o `"(SUR)"`, y `estado_funcionamiento` normalizado (recortado y en minúsculas) es `"vigente en operación habitual"`. La normalización de minúsculas es necesaria porque la fuente contiene ambas grafías `"Vigente en Operación Habitual"` y `"Vigente en operación habitual"` para el mismo estado.
- **`excepcion_cear_documentada`:** establecimientos vigentes que no cumplen el criterio anterior pero reportan, en al menos un año del período canónico 2021-2025, `tipo_establecimiento_urgencia = "CEAR"` en los Parquet de Urgencias. Es una excepción **detectada dinámicamente contra la fuente**, no un código fijo en el módulo: si la fuente deja de respaldarla, deja de incluirse automáticamente. En el snapshot vigente corresponde a un único establecimiento (CESFAM Juan Pablo II, La Reina, código `112320`).

**Explícitamente NO se usan** `tiene_servicio_urgencia` ni `tipo_urgencia` del maestro como criterio: se comprobó que son poco confiables para esta decisión (ver EDA, sección "Instituto Psiquiátrico Horwitz Barak"). **Tampoco se exige `ID36 > 0`** para pertenecer a la oferta: un establecimiento del tipo correcto pertenece a la oferta aunque nunca haya reportado actividad de salud mental en el período observado.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `establecimiento_codigo` | int64 | Código DEIS del establecimiento. Normalizado explícitamente a entero (el maestro lo publica como string de 6 dígitos sin ceros a la izquierda; Urgencias lo publica como int64) para permitir el join sin pérdida silenciosa. |
| `establecimiento_nombre` | string | `establecimiento_glosa` del maestro. |
| `comuna_codigo` | string | CUT de 5 dígitos (`13xxx`), del maestro. |
| `comuna_glosa` | string | Nombre de comuna, del maestro. |
| `tipo_establecimiento` | string | `tipo_establecimiento_glosa` del maestro (Hospital / SAPU / SAR / SUR / CESFAM en el caso de la excepción documentada). |
| `estado_funcionamiento` | string | `estado_funcionamiento` normalizado (recortado, minúsculas). Constante `"vigente en operación habitual"` en todas las filas, porque es también el filtro de inclusión. |
| `latitud`, `longitud` | float64 | Coordenadas del maestro, sin imputar. Ambas nulas o ambas válidas (nunca una sola). |
| `criterio_inclusion_oferta` | string | `"catalogo_core"` o `"excepcion_cear_documentada"` (ver arriba). |
| `reporto_id1_periodo` | bool | `True` si existe al menos una fila `id_causa=1` para este establecimiento en `urgencias_rm_2021..2025` (período canónico cerrado; 2020/2026 no se leen). |
| `reporto_id36_periodo` | bool | `True` si existe al menos una fila `id_causa=36` **con `total > 0`** (atención de salud mental efectivamente registrada, no solo la fila-cero de reporte) para este establecimiento en 2021-2025. |
| `ultimo_ano_reporte_id36` | Int32 (nulo si no aplica) | Año máximo dentro de 2021-2025 con `id_causa=36` y `total > 0`. Nulo si y solo si `reporto_id36_periodo` es `False`. |
| `tipo_urgencia_reportado` | string (nulo si no aplica) | `tipo_establecimiento_urgencia` observado en el año más reciente dentro de 2021-2025 en que el establecimiento aparece en Urgencias (regla determinista: algunos códigos cambian de tipo reportado entre años; se documenta el más reciente del período canónico, no el histórico completo). Nulo si y solo si `reporto_id1_periodo` es `False`. |

## Excluidos y por qué (evidencia, no intuición)

- **COSAM:** 100% con `tiene_servicio_urgencia = "NO"` y `tipo_urgencia` nulo en el maestro; 0 de los códigos COSAM aparecen jamás en Urgencias 2021-2025. Es un dispositivo ambulatorio especializado de salud mental, no de urgencia.
- **CESFAM/CECOSF/PSR (fuera de la excepción documentada):** 0 de 299 códigos de este tipo reportan actividad en Urgencias 2021-2025, salvo la única excepción CEAR ya incluida.
- **SAMU (Centro de Regulación Médica de las Urgencias):** no forma parte del universo `Hospital/SAPU/SAR/SUR`; es un nodo de regulación/despacho prehospitalario, no un punto de atención presencial, y queda fuera de esta oferta territorial.

## Advertencias e interpretación

- **No es una capa de accesibilidad ni de isócronas.** Es únicamente el insumo de oferta (establecimientos + criterio de inclusión) para esa capa futura (`src/geo/`, aún no implementada).
- **Hallazgo relevante para la interpretación de `tiene_servicio_urgencia`/`tipo_urgencia` del maestro:** el Instituto Psiquiátrico Dr. José Horwitz Barak (`109102`) tiene `tiene_servicio_urgencia = "NO"` en el maestro, pero reporta entre ~16.600 y ~21.800 atenciones de urgencia por año en 2021-2025 (Urgencias), de las cuales entre 89% y 100% son `ID36`. Por eso este stage no usa esos campos del maestro como criterio.
- Un establecimiento puede pertenecer a la oferta sin haber reportado nunca actividad en 2021-2025 (`reporto_id1_periodo = False`); eso es evidencia de ausencia de reporte en el período canónico, no evidencia de que el dispositivo no exista.
- `ultimo_ano_reporte_id36` no implica que el establecimiento siga reportando salud mental hoy; es el último año observado dentro de 2021-2025. 2020 y 2026 quedan fuera de esta columna por diseño (ver arriba); si se cita actividad de esos años, debe hacerse por separado como contexto EDA.
- Esta dimensión no reemplaza el maestro completo (`establecimientos_rm_clean.parquet`); es un subconjunto filtrado y enriquecido para el propósito específico de accesibilidad de urgencia.

Ver `reports/eda/eda_dim_oferta_urgencia_rm.md` para el detalle reproducible (conteos por tipo, cobertura de coordenadas, evidencia ID1/ID36, casos anómalos).
