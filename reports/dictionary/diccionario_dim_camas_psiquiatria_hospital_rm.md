# Diccionario de datos: `dim_camas_psiquiatria_hospital_rm`

- **Ruta:** `data/processed/camas/dim_camas_psiquiatria_hospital_rm.parquet`
- **Constructor:** `src/data/build_dim_camas_psiquiatria_hospital_rm.py` (`build_dim_camas_psiquiatria_hospital_rm`), stage `build_dim_camas_psiquiatria_hospital_rm` en `PIPELINE.md`.
- **Grano:** una fila = un hospital de `dim_oferta_urgencia_rm` (`tipo_establecimiento = "Hospital"`), `establecimiento_codigo` único. Conserva todos los hospitales de la oferta, con o sin dotación SNSS, para que el vínculo sea auditable.
- **Propósito:** ligar cada hospital que atiende urgencias con sus camas de psiquiatría, de modo que la API pueda mostrar, por territorio, la dotación psiquiátrica de los hospitales que alimentan el modelo de demanda. Es dotación anual declarada, **no** ocupación ni disponibilidad en tiempo real.
- **Fuentes:**
  - `data/processed/geo/dim_oferta_urgencia_rm.parquet` (universo de hospitales, comuna y `reporto_id36_periodo`).
  - `data/processed/camas/dotacion_camas_snss.parquet` (camas por área funcional y año; solo establecimientos del SNSS).

## Regla de unión

Por la llave `establecimiento_codigo` (código DEIS de 6 dígitos, entero en ambas fuentes). No se une por nombre (los nombres difieren entre fuentes, p. ej. «Hospital Comunitario de Til Til» frente a «Hospital de Til Til») ni por el código textual `NN-NNN` de Urgencias, que en el RAW trae un espacio final.

## Qué cuenta como «camas de psiquiatría»

Suma de las áreas funcionales cuyo nombre contiene «Psiquiatr» (adulto corta, mediana y larga estadía; infanto-adolescente; forense; cuidados intensivos en psiquiatría), excluida la fila `Total` (área 100). El área sociosanitaria no es psiquiatría y no se suma. El stage falla si un establecimiento repite un área de psiquiatría.

## Año de referencia

El último año con columna `camas_AAAA` en `dotacion_camas_snss.parquet`, detectado en cada ejecución (nunca fijo en el código). Es el mismo para todas las filas (`ano_camas`).

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `establecimiento_codigo` | int64 | Código DEIS del hospital. PK; FK a `dim_oferta_urgencia_rm`. |
| `establecimiento_nombre` | string | Nombre del hospital según `dim_oferta_urgencia_rm` (maestro DEIS). |
| `comuna_codigo` | string | CUT de 5 dígitos (`13xxx`) de la comuna del establecimiento, copiada de la oferta. Es la misma regla territorial con que Urgencias asigna sus atenciones. |
| `en_dotacion_snss` | bool | `True` si el código figura en `dotacion_camas_snss`. `False` para hospitales fuera del SNSS (la dotación no SNSS es otro libro, «dato referencial», y no se mezcla aquí). |
| `reporto_id36_periodo` | bool | Heredado de la oferta: `True` si el hospital reportó ID36 > 0 al menos una vez en 2021-2025. Marca los hospitales que alimentaron el modelo de demanda (target `atenciones_id36`). Es «alguna vez», no «todos los años». |
| `ano_camas` | int32 | Último año de la dotación usado para `camas_psiquiatria`. |
| `camas_psiquiatria` | float64 (nulo) | Suma de camas de las áreas de psiquiatría en `ano_camas`. **Nulo** si el hospital no está en la dotación SNSS o no declara cifra en ninguna área de psiquiatría (sin área, o celdas en blanco). Nulo no equivale a cero; un cero declarado en el origen se conserva como 0. |
| `n_areas_psiquiatria` | int32 | Cantidad de áreas de psiquiatría con cifra declarada en `ano_camas`. `camas_psiquiatria` es nula si y solo si es 0. |

## Validaciones previas a publicar

Un hospital por cada uno de la oferta (ninguno descartado), `establecimiento_codigo` único, `comuna_codigo` con formato `13xxx`, `reporto_id36_periodo` sin nulos, un solo `ano_camas`, camas no negativas, hospitales fuera de la dotación SNSS sin camas y coherencia entre `camas_psiquiatria` y `n_areas_psiquiatria`.

## Advertencias e interpretación

- **Los totales territoriales deben sumar solo `reporto_id36_periodo = True`.** Un hospital con camas que nunca aportó ID36 (en el snapshot vigente, el Hospital Psiquiátrico El Peral) no es parte de la demanda modelada. La API (`/api/v1/camas-psiquiatria/{series_id}`) aplica ese filtro.
- **La comuna es la del hospital, no la de residencia de sus pacientes.** Hospitales como el Instituto Psiquiátrico Horwitz Barak atienden a pacientes de toda la región; sumar sus camas en la comuna donde están ubicados describe dotación instalada allí, no cobertura de su población.
- **Dotación (stock) frente a atenciones por semana (flujo):** no son la misma magnitud y su comparación directa no mide saturación.
- **Cobertura parcial del libro:** hospitales de la oferta que no están en la dotación SNSS quedan con `en_dotacion_snss = False` y camas nulas; no se completan con la dotación no SNSS ni con estimaciones.
- **Sin relación con Egresos:** Egresos no identifica el establecimiento; cualquier lectura conjunta con hospitalización es ecológica/territorial.
- **Cifras vigentes:** los conteos (hospitales en la oferta, en dotación SNSS, con cifra, que reportaron ID36) se calculan al ejecutar el stage y cambian con la fuente; se obtienen directamente del Parquet.
