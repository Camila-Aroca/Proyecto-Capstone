# Diccionario de datos: dotación de camas hospitalarias

- **Rutas:** `data/processed/camas/dotacion_camas_snss.parquet` y `data/processed/camas/dotacion_camas_no_snss.parquet`, uno por libro de origen.
- **Constructor:** `src/data/clean_dotacion_camas.py` (`build_dotacion_camas`), stage `clean_dotacion_camas` de `PIPELINE.md` (upstream: `download_dotacion_camas`).
- **Fuente:** dos libros XLSX oficiales del DEIS y la División de Gestión de la Red Asistencial (DIGERA), en `data/raw/camas/`: `dotacion_camas_snss_2010_2025.xlsx` (establecimientos del SNSS, públicos) y `dotacion_camas_no_snss_2019_2025.xlsx` (no pertenecientes al SNSS, privados; la propia fuente los rotula "dato referencial" y cita también a la Superintendencia de Salud). Procedencia (URL, fecha, tamaño, SHA256) en `data/raw/provenance_manifest.json`.
- **Qué es:** dotación anual de camas declarada por hospital y área funcional, más el total por hospital. **No** es ocupación, disponibilidad ni camas en tiempo real; no sirve para gestionar cupos.
- **Qué contiene cada Parquet:** las mismas columnas y filas que su libro, con tipos y con los datos del hospital (código, tipo, nombre) repetidos en cada una de sus filas, que en el Excel solo figuran en la fila de total. Pesan 40 KB (SNSS) y 13 KB (no SNSS) frente a unos 179 KB de cada Excel.

## `dotacion_camas_snss`

**Grano:** una fila por fila del libro: cada área funcional de cada hospital, más su fila `Total` (área `100`). 1.694 filas = 197 filas de total + 1.497 de área; 196 códigos de establecimiento (el `114104` figura bajo dos Servicios de Salud). **Llave lógica verificada** (sin duplicados ni nulos): `servicio_salud, establecimiento_codigo, area_funcional_codigo`.

| Columna | Tipo | Columna del libro | Semántica |
|---|---|---|---|
| `servicio_salud` | string | Nombre Servicio de Salud | Con espacios sobrantes retirados. 29 valores. |
| `establecimiento_codigo` | int64 | Código Establecimiento | Código DEIS; mismo tipo y valores que `dim_oferta_urgencia_rm.establecimiento_codigo`. |
| `tipo_establecimiento` | string | Tipo de Establecimiento | Se repite en las filas de área de cada hospital. Valores del origen sin unificar: `Alta complejidad`, `Mediana complejidad`, `Baja complejidad`, `Hospital Alta Complejidad`. |
| `establecimiento_nombre` | string | Nombre Establecimiento | Sin espacios sobrantes ni asteriscos finales. Es el de la fila de total del hospital. |
| `area_funcional_codigo` | int32 | Cod. Área Funcional | `100` es el total del hospital. |
| `area_funcional` | string | Área Funcional | Tal como la publica el origen, con espacios colapsados. `Total` en la fila `100`. |
| `camas_2010` … `camas_2025` | int32 | 2010 … 2025 (`2014*` es `camas_2014`) | Camas declaradas ese año. **Nulo = celda en blanco o sin cifra en el origen, no cero**; `0` = cero explícito del origen. |

## `dotacion_camas_no_snss`

**Grano:** una fila por fila de cada hoja anual del libro, con las hojas apiladas: cada área funcional de cada establecimiento y su fila de total, por año. 4.631 filas = 911 de total + 3.720 de área; 144 códigos de establecimiento; 2019-2025. Sin llave lógica sin nulos: `area_funcional_codigo` es nulo en la fila de total (el libro no trae área ahí); la llave sería `ano, seremi, establecimiento_codigo, area_funcional_codigo`, verificada sin duplicados, y el modelo físico usa una clave técnica.

| Columna | Tipo | Columna del libro | Semántica |
|---|---|---|---|
| `ano` | int32 | Nombre de la hoja (`Total <año>`) | Año de la hoja, validado contra el encabezado. |
| `seremi` | string | Nombre SEREMI | Con espacios sobrantes retirados. La grafía del origen se conserva: `Metropolitana` y `Metropolitano` coexisten. |
| `establecimiento_codigo` | int64 | Código establecimiento | Código DEIS. |
| `establecimiento_nombre` | string | Nombre establecimiento | Sin espacios sobrantes ni asteriscos finales. Es el de la fila del establecimiento en esa hoja. |
| `area_funcional_codigo` | int32 | Código área | **Nulo en la fila de total del establecimiento.** |
| `area_funcional` | string | Area | Glosa tal como la publica el origen, con espacios colapsados. Nula en la fila de total. |
| `camas` | int32 | Total `<año>` | Camas declaradas en ese año. **Nulo = celda en blanco, no cero**; `0` = cero explícito. |

## Qué no contienen los Parquet

Quedan fuera, y siguen intactos en el RAW: las **notas al pie**, las **marcas que remiten a ellas** (asteriscos en nombres y en el encabezado `2014*`, `*******` en celdas de valor, `ok` en una columna adicional) y los **totales nacionales** publicados por año. Los totales nacionales se usan para validar: al construir, la suma de los totales de los hospitales debe coincidir con el total nacional del libro; una discrepancia se informa en el log y nunca se corrige (en el snapshot vigente coinciden los 23). Una celda con `*******` en lugar de una cifra queda nula (la nota del libro indica, para ese hospital, que no declara dotación).

## Construcción

1. Se valida la estructura de cada libro (hojas, encabezados, años y mínimo de filas) con los mismos validadores de la descarga.
2. Cada fila del libro se clasifica por patrón: total nacional, total de hospital, área funcional, nota al pie o en blanco. **Si una fila no responde a un patrón conocido, si hay datos fuera de las columnas contempladas o si un valor no es un entero no negativo, la etapa falla** en vez de descartarlo.
3. Las filas de área se asocian a su hospital por **contigüidad** (siguen a su fila de total hasta la siguiente), no por nombre, porque el nombre difiere entre filas en algunos casos. En el libro SNSS se exige además que el Servicio de Salud coincida.
4. Una nota al pie es texto solo en la columna A **después de la última fila de datos**; un texto suelto entre filas de datos es un error.
5. La etapa falla si dos filas repiten la llave lógica, porque no se puede elegir cuál vale.
6. Se escriben ambos Parquet de forma atómica (temporales, validación y reemplazo conjunto con rollback), con compresión `zstd`. El footer registra solo la procedencia: `raw_sha256`, el SHA256 del libro de origen.

## Advertencias de interpretación

- **Un blanco no es un cero.** `camas_AAAA` y `camas` nulos significan que el origen no informa el dato.
- **El total del hospital es una fila más.** Para sumar áreas hay que excluir la fila de total (`area_funcional_codigo = 100` en el SNSS; nulo en el no SNSS), o se duplican las camas.
- **Quiebre de serie en 2014 (SNSS).** Dos notas del propio libro, que están en el RAW, lo indican: desde 2014 la agrupación de camas es por áreas funcionales y no se reconocen las camas de las Unidades de Emergencia Hospitalaria, y hasta 2013 se trabajaba con servicios clínicos homologados a áreas funcionales por los establecimientos. Comparar 2010-2013 con 2014-2025 requiere esa cautela.
- **Cobertura temporal distinta:** SNSS 2010-2025, no SNSS 2019-2025. El libro privado es "dato referencial" según la fuente.
- **La glosa de área no siempre es 1:1 con el código.** En el SNSS, 1 de los 28 códigos de área tiene más de una glosa; en el no SNSS, 11 de 23 (diferencias de mayúsculas, tildes o redacción). Se conservan tal cual vienen; unir y agrupar por código.
- **Hospital repetido en una hoja (no SNSS).** El código `200063` (Clínica Alemana de La Dehesa) figura dos veces en 2024 y 2025, bajo `Metropolitana` y `Metropolitano`, y el total nacional del libro ya lo cuenta dos veces. Se conservan ambas filas y la etapa lo informa en el log. Cuál es la correcta no es determinable con los datos disponibles.
- **Un código bajo dos Servicios de Salud (SNSS).** El `114104` (Hospital Metropolitano, Ex Militar) aparece bajo dos Servicios; una nota del libro describe sus cambios de dependencia. Son dos filas de llave distinta.
- **Un código en ambos libros.** El `124210` es el Hospital San José (Puerto Varas) en el SNSS y la Clínica de Puerto Varas SpA. en el no SNSS; una nota del libro SNSS indica que desde 2012 es un establecimiento no perteneciente al SNSS.
- **Dos hospitales con nombre distinto en sus filas de área (SNSS):** el `117108` y el `120104`. Se asocian por contigüidad y el Parquet usa el nombre de la fila de total.
- **Totales sin desglose en 2025 (no SNSS).** Tres clínicas (códigos 102200, 104200 y 106214) traen el total del establecimiento pero sus filas de área vienen en blanco ese año, mientras que en 2024 sí traían valores.
- **Totales en blanco.** 15 hospitales del SNSS tienen el total nulo en algún año; los blancos no se explican ni se completan.

## Relación con otros datasets

- `establecimiento_codigo` existe en el maestro de establecimientos para los 196 códigos del SNSS y los 144 del no SNSS. Con `dim_oferta_urgencia_rm` solo coincide para 44 de sus 174 establecimientos (34 SNSS y 10 no SNSS), porque esa dimensión es únicamente la oferta de urgencia: es un vínculo lógico, no una FK.
- **No se enlaza con Egresos.** Egresos no identifica el establecimiento; cualquier relación entre camas y egresos sería territorial/ecológica. Tampoco habilita gestión de cupos ni camas en tiempo real.

## Reproducibilidad y verificación

- Se genera solo con `python scripts/run_pipeline.py --stage clean_dotacion_camas` (o el pipeline completo). `SKIP` si las dos salidas existen y cumplen el contrato de esquema; `--force` las regenera.
- Pruebas unitarias con libros sintéticos que reproducen las rarezas del origen: `tests/test_clean_dotacion_camas.py`.
- Verificación contra los libros reales, con una lectura independiente del parser: `tests/test_dotacion_camas_integridad.py` (`pytest -m data_integration`). Comprueba que cada fila del libro está en el Parquet con las mismas etiquetas y camas, y que el Parquet no tiene filas de más; que toda celda con contenido del libro queda explicada; y que conteos, sumas, códigos, totales nacionales y procedencia coinciden con lo calculado desde el libro.
