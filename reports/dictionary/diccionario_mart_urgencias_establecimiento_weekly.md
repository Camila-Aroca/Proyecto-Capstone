# Diccionario de datos: `mart_urgencias_establecimiento_weekly`

- **Ruta:** `data/processed/marts/mart_urgencias_establecimiento_weekly.parquet`
- **Constructor:** `src/data/build_urgencias_establecimiento_weekly_mart.py` (`build_establecimiento_weekly_mart`), stage `build_urgencias_establecimiento_weekly_mart` en `PIPELINE.md`.
- **Grano:** una fila = `establecimiento_codigo` × `ano` × `semana`, con la semana publicada por DEIS (la misma de `mart_urgencias_comuna_weekly`). Llave verificada sin duplicados ni nulos.
- **Propósito:** insumo semanal del pronóstico por establecimiento: atenciones de urgencia en salud mental (ID36) y hospitalizaciones derivadas desde la urgencia por trastornos mentales (ID42).
- **Cobertura observada:** 152 establecimientos, 2021-2025, 38.641 filas (295 de semana 53). Las cifras vigentes están en `reports/eda/eda_mart_urgencias_establecimiento_weekly.md`, generado desde el mart.
- **Fuente:** DEIS/MINSAL, Atenciones de Urgencia RM 2021-2025 (`data/processed/urgencias/urgencias_rm_<año>.parquet`, producidos por `clean_urgencias`). No usa dimensiones poblacionales.
- **Construcción/derivación:** filtra `id_causa ∈ {1, 35, 36, 37, 38, 39, 40, 41, 42}`; suma `total` por establecimiento × semana × causa y pivotea a una columna por causa. `fecha_inicio_semana` es la fecha mínima observada de cada semana en todo el origen, la misma regla del mart comunal semanal. Los atributos del establecimiento forman parte de la llave de agregación: si variaran dentro de una semana, el grano quedaría duplicado y la validación fallaría.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `establecimiento_codigo` | int64 | Código DEIS del establecimiento. Llave junto con `ano` y `semana`. |
| `ano` | int32 | Año de la semana DEIS. |
| `semana` | int32 | Semana DEIS (1 a 52; la 53 es un fragmento de pocos días y se conserva). |
| `comuna_codigo` | string | CUT de la comuna donde se ubica el establecimiento. |
| `comuna_glosa` | string | Nombre de la comuna, tomado del origen DEIS. |
| `establecimiento_glosa` | string | Nombre del establecimiento, tomado del origen DEIS. |
| `tipo_establecimiento_urgencia` | string | Tipo según Urgencias (`Hospital`, `SAPU`, `SAR`, `SUR`, `CEAR`). |
| `fecha_inicio_semana` | string (ISO `YYYY-MM-DD`) | Primera fecha observada de la semana en el origen. |
| `atenciones_id1` | int64 | Atenciones de urgencia de todas las causas (ID1). |
| `atenciones_id35` | int64 | Lesiones autoinfligidas intencionalmente (ID35, X60-X84). Fuera de ID36. |
| `atenciones_id36` | int64 | Agregado DEIS de salud mental (ID36 = ID37 + … + ID41); **no equivale a F00-F99 estricto** porque incluye ideación suicida (ID37, R45.8). |
| `atenciones_id37` … `atenciones_id41` | int64 | Componentes de ID36, con la misma semántica que en `mart_urgencias_establecimiento_monthly`. |
| `atenciones_id42` | int64 | **Hospitalizaciones derivadas desde la urgencia por trastornos mentales (F00-F99)**, sección 2 del archivo DEIS. No es componente de ID36 ni está contenida en él. |
| `proporcion_id36_sobre_id1`, `proporcion_id37_sobre_id36` … `proporcion_id41_sobre_id36` | float64 | Razones internas; nulas si el denominador es 0. |

## Validaciones antes de publicar

Grano único y sin llaves nulas; conteos no negativos; ID36 igual a la suma de ID37 a ID41; razones en [0, 1]; período 2021-2025; y **reconciliación exacta con `mart_urgencias_comuna_weekly`**: sumar los establecimientos por comuna × semana da los mismos valores de ID1 y ID35 a ID41, con el mismo universo de comuna × semana. ID42 no tiene equivalente comunal y no entra en esa comparación.

## Advertencias e interpretación

- **Cero no es ausencia.** Cuando un establecimiento reporta una semana publica todas las causas del contrato, con cero si corresponde; por eso el mart no tiene conteos nulos. Una semana sin fila es ausencia de reporte y **no se imputa**. Su causa (apertura, cierre o interrupción del reporte) no es determinable con este mart.
- **ID42 lo informan solo hospitales.** Los demás establecimientos publican la fila con cero; es un hecho observado en 2021-2025, no una regla que se valide, para no rechazar datos futuros legítimos.
- **ID42 se registra donde ocurrió la urgencia**, no donde quedó hospitalizado el paciente: un hospital sin camas de psiquiatría puede derivar pacientes a otro. No mide la ocupación de camas del establecimiento.
- **Cambio de nivel de ID42.** La razón ID42 / ID36 sube entre 2021 y 2023 y luego se estabiliza. No es posible determinar con estos datos si es maduración del registro o un cambio real.
- **Ubicación, no residencia.** La comuna es la del establecimiento, igual que en todos los marts de Urgencias.
- No incluye población ni tasas, ni datos de Egresos, y no permite cruces a nivel de paciente (invariantes del proyecto).
