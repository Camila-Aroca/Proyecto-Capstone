# Diccionario de datos: `mart_egresos_f00_f99_rm_anual` y `mart_egresos_f00_f99_rm_desglose`

- **Rutas:** `data/processed/marts/mart_egresos_f00_f99_rm_anual.parquet` y `data/processed/marts/mart_egresos_f00_f99_rm_desglose.parquet`.
- **Constructor:** `src/data/build_mart_egresos_f00_f99_rm.py`, stage `build_mart_egresos_f00_f99_rm` (upstream: `build_egresos_f00_f99`, `clean_poblacion_proyecciones`). Pruebas: `tests/test_mart_egresos_f00_f99_rm.py`.
- **Propósito:** perfil anual de las hospitalizaciones por salud mental (diagnóstico principal F00-F99) de los residentes de la RM, por comuna de residencia y para la región. Lo sirve la API en `/api/v1/hospitalizaciones-residentes/{series_id}` y el tablero comunal. Complementa a Urgencias, no la reemplaza: Urgencias cuenta dónde se atendió la persona y Egresos dónde vive.
- **Fuente:** `data/processed/egresos/egresos_f00_f99_nacional_2020_2025.parquet` filtrado a `residente_rm` (DEIS, egresos hospitalarios 2020-2025) y la proyección INE por comuna y año (`dim_poblacion_comuna_anual`), que fija el universo de 52 comunas.

## `mart_egresos_f00_f99_rm_anual`

**Grano:** una fila por territorio de residencia y año. **Llave lógica verificada:** `series_id, ano`. Son 318 filas (53 territorios × 6 años, 2020-2025): las 52 comunas y la región (`series_id = RM`).

| Columna | Tipo | Semántica |
|---|---|---|
| `series_id` | string | Código CUT de 5 dígitos de la comuna de **residencia** del paciente, o `RM` para la región completa. Las 52 comunas coinciden con `cartografia_comunal`; la fila `RM` no es una comuna. |
| `nivel` | string | `comuna` o `region`. `region` solo con `series_id = RM`. |
| `nombre` | string | Glosa de la comuna (`dim_poblacion_comuna_anual`) o `Región Metropolitana`. |
| `ano` | int32 | Año del egreso. |
| `egresos` | int64 | Registros de egreso publicados con residente en el territorio. **No son pacientes únicos**: una persona puede egresar varias veces. Cero = cero registrado (el registro es exhaustivo). |
| `poblacion` | int64 | Proyección INE del territorio y año. Nula en 2020: la proyección comunal parte en 2021. |
| `tasa_por_10000` | float64 | `egresos / poblacion × 10.000`. Nula cuando `poblacion` es nula (sin denominador, no cero). |
| `dias_estada_mediana`, `dias_estada_p90` | float64 | Mediana y percentil 90 de `dias_estada` de los egresos del territorio y año. Nulas si no hay egresos. |
| `proporcion_snss` | float64 | Proporción de egresos en establecimientos del SNSS. Egresos no identifica el establecimiento: se sabe la pertenencia, no cuál ni dónde. |
| `proporcion_estadia_mayor_a_un_ano` | float64 | Proporción de egresos con estadía de más de un año. |

## `mart_egresos_f00_f99_rm_desglose`

**Grano:** una fila por territorio × año × dimensión × categoría (7.399 filas). **Llave lógica verificada:** `series_id, ano, dimension, categoria`. `(series_id, ano)` existe siempre en el anual.

| Columna | Tipo | Semántica |
|---|---|---|
| `series_id`, `ano` | string, int32 | Igual que en el anual. |
| `dimension` | string | `sexo`, `grupo_edad`, `grupo_diagnostico` o `prevision`. |
| `categoria` | string | Categoría armonizada entre años (columnas `sexo_armonizado` y `grupo_edad_armonizado` de Egresos). Sexo: Mujer, Hombre, Intersex o indeterminado. Edad: tramos decenales con `Menor de 1 año` y `80 y más`. Diagnóstico: bloques CIE-10 F00-F09 a F99. Previsión: FONASA, ISAPRE, Fuerzas Armadas y de Orden, Ninguna, Sin dato. |
| `orden` | int32 | Posición de presentación de la categoría dentro de su dimensión. |
| `egresos` | int64 | Egresos de la categoría. |

## Construcción

1. Se filtran los egresos con `residente_rm` verdadero. Un residente RM sin comuna de residencia, o con una comuna fuera de las 52, hace fallar la etapa en vez de descartarse.
2. El anual usa la grilla completa de 52 comunas × años; una comuna sin egresos queda con `egresos = 0` y estadía nula.
3. La región se calcula sobre los mismos registros, no sumando comunas, y la etapa verifica que las comunas la sumen y que reconcilie con los egresos de residentes RM.
4. Cada dimensión del desglose debe sumar el total de su territorio y año (la etapa lo valida; en el snapshot vigente, 1.272 combinaciones sin diferencias).

## Advertencias de interpretación

- El territorio es la **residencia** del paciente, no el hospital: la relación con Urgencias (establecimiento) es solo ecológica y no hay enlace por paciente ni por establecimiento.
- Egresos son eventos publicados, no pacientes únicos.
- Con pocos egresos por comuna la tasa es inestable; la tasa de 2020 es nula por falta de población.
- Los códigos de sexo y los tramos de edad de 2021 usan un esquema distinto al resto; las columnas armonizadas no reconstruyen información que la fuente no trae (ver `reports/dictionary/diccionario_egresos_f00_f99_nacional.md`).
