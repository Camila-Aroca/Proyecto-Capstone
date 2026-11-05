# Diccionario de datos: Estadísticas Hospitalarias REM-20

- **Rutas:** `data/processed/estadisticas_hospitalarias/indicadores_hospitalarios_snss.parquet` y `data/processed/estadisticas_hospitalarias/categorizacion_riesgo_dependencia.parquet`, uno por familia de libros de origen.
- **Constructor:** `src/data/clean_estadisticas_hospitalarias.py` (`build_estadisticas_hospitalarias`), stage `clean_estadisticas_hospitalarias` de `PIPELINE.md` (upstream: `download_estadisticas_hospitalarias`). EDA: `reports/eda/eda_estadisticas_hospitalarias.md`.
- **Fuente:** libros XLSX oficiales del DEIS, repositorio REM-20, en `data/raw/estadisticas_hospitalarias/`: «Indicadores Hospitalarios según Servicio de Salud» (SNSS; consolidado 2014-2023, 2024, 2025 y el año en curso, que el DEIS reemplaza cada mes con el último corte) y «Categorización de Pacientes Hospitalizados Según Riesgo Dependencia» (un libro por trimestre, 2024-2025). URL, fecha, tamaño, SHA256 y corte en `data/raw/provenance_manifest.json`. El diccionario oficial de los campos, `diccionario_rem20.xlsx` (datos.gob.cl), está en la misma carpeta RAW.
- **Qué es:** actividad hospitalaria mensual por establecimiento y nivel de cuidado (días cama disponibles y ocupados, egresos y sus razones) y la categorización trimestral de los pacientes con el instrumento CUDYR. Son estadísticas consolidadas: **no** son ocupación en tiempo real ni sirven para gestionar cupos.
- **Qué contiene cada Parquet:** las columnas de su libro con tipos y nombres válidos. Cada familia apila sus libros con el año (y el trimestre en la categorización), porque comparten columnas.

## `indicadores_hospitalarios_snss`

**Grano:** un indicador de un nivel de cuidado (área funcional) de un establecimiento en un año, con el acumulado y un valor por mes. **Solo filas de detalle.** 160.974 filas en el snapshot vigente (2014-2026), 208 establecimientos, 29 Servicios de Salud y 29 niveles de cuidado. **Llave lógica verificada** (sin duplicados ni nulos): `ano, servicio_salud_codigo, establecimiento_codigo, nivel_cuidado_codigo, indicador`.

| Columna | Tipo | Columna del libro | Semántica |
|---|---|---|---|
| `ano` | int32 | Título de la hoja (`Período: AAAA`) | Año, leído del título y no del nombre de la hoja (que varía: `Año 2024`, `Corte Septiembre`). |
| `servicio_salud_codigo` | int32 | Cód. SS/SEREMI | Código del Servicio de Salud. Los `Metropolitano *` (9 a 14) son la Región Metropolitana. |
| `servicio_salud` | string | Nombre SS/SEREMI | Con espacios colapsados. |
| `establecimiento_codigo` | int64 | Cód. Estab. | Código DEIS: la misma llave entera que `dotacion_camas_snss.establecimiento_codigo` y `dim_oferta_urgencia_rm.establecimiento_codigo`. |
| `establecimiento_nombre` | string | Nombre Establecimiento | Tal como lo publica cada año (puede cambiar de un año a otro). |
| `nivel_cuidado_codigo` | int32 | Cód. Nivel Cuidado | Mismo catálogo que `area_funcional_codigo` de la dotación de camas. Psiquiatría: 418-426, 428 y 429; `427` es el área sociosanitaria adulto (no es psiquiatría). |
| `nivel_cuidado` | string | Nombre Nivel Cuidado | Glosa tal como la publica cada año (en 2014 sin el prefijo `NNN - `; hasta 3 glosas por código). Agrupar por código. |
| `indicador` | string | Glosa | Uno de los 11 indicadores de la tabla siguiente. |
| `acumulado` | float64 | Acum | Valor del período: suma de los meses en los conteos; razón o promedio del período en el resto. Nulo si el origen no lo publica (índice de rotación en 2025-2026). |
| `ene` … `dic` | float64 | Ene … Dic | Valor del mes. **Nulo = mes aún no publicado (año en curso) o celda en blanco, no cero.** |

Los 11 indicadores y cómo se pueden combinar. Las definiciones oficiales están en `data/raw/estadisticas_hospitalarias/diccionario_rem20.xlsx`, que describe el conjunto en formato largo de datos.gob.cl con nombres de campo propios (`DIAS_CAMAS_OCUPADAS`, `TRASLADOS`, …); la correspondencia con cada glosa es por nombre. El EDA las reproduce junto a la fórmula observada. Según ese diccionario, un **traslado** es el paso del paciente a otra área funcional del mismo establecimiento y **no constituye egreso**, y la **letalidad** es el porcentaje de egresos fallecidos sobre el total de egresos (lo que coincide con lo publicado desde 2025, no antes).

| `indicador` | Naturaleza | Se suma entre áreas y meses | Definición observada (EDA, sección 4) |
|---|---|---|---|
| `Dias Cama Disponibles` | conteo | sí | Días cama habilitados en el período. |
| `Dias Cama Ocupados` | conteo | sí | Días cama con paciente. Puede superar los disponibles (EDA, sección 5). |
| `Dias de Estada` | conteo | sí | Días de estada de los egresos del período. |
| `Numero de Egresos` | conteo | sí | Egresos del período. |
| `Egresos Fallecidos` | conteo | sí | Egresos por fallecimiento. |
| `Traslados` | conteo | sí | Solo existe en el detalle: ningún nivel agregado del libro lo publica. |
| `Promedio Cama Disponibles` | promedio | por mes, sí; el `acumulado`, **no** | Mes: días cama disponibles / días del mes. Acumulado: en el 97 % de las áreas, días disponibles del año / días del año; en el resto, sobre los días de los meses en que el área funcionó. |
| `Indice Ocupacional` | razón (%) | **no** | `100 · ocupados / disponibles`, todos los años. |
| `Promedio Días de Estada` | razón | **no** | `estada / (egresos + traslados)` hasta 2024; `estada / egresos` desde 2025. |
| `Letalidad` | razón (%) | **no** | `100 · fallecidos / (egresos + traslados)` hasta 2024; `100 · fallecidos / egresos` desde 2025. |
| `Indice de Rotación` | razón | **no** | Cercana a `(egresos + traslados) / promedio de camas`, sin coincidir exacto. Acumulado no publicado en 2025-2026. |

## `categorizacion_riesgo_dependencia`

**Grano:** un nivel de cuidado de un establecimiento en un trimestre, con su total de categorizaciones y las 12 categorías CUDYR. 8.834 filas (2024-T1 a 2025-T4), unos 191 establecimientos por trimestre. **Llave lógica verificada:** `ano, trimestre, servicio_salud, establecimiento_nombre, nivel_cuidado_codigo`.

| Columna | Tipo | Origen | Semántica |
|---|---|---|---|
| `ano` | int32 | Título del libro (`Período: AAAA`) | Año, validado contra la configuración. |
| `trimestre` | int32 | Nombre de la publicación | 1 a 4. **El libro no lo declara**: viene del nombre del archivo publicado por el DEIS (configuración de la descarga). |
| `region` | string | Fila de región de la jerarquía | Glosa del origen (`Metropolitana de Santiago`, `de Arica y Parinacota`, …). |
| `servicio_salud` | string | Fila `SS …` de la jerarquía | Con el prefijo `SS ` del origen. |
| `establecimiento_nombre` | string | Fila de establecimiento | **El libro no trae código de establecimiento.** En el snapshot vigente, los 384 pares año-establecimiento coinciden exactamente por año, Servicio de Salud y nombre con los indicadores, sin ambigüedad (EDA, sección 8). |
| `nivel_cuidado_codigo` | int32 | Prefijo `NNN` de la fila de nivel | Mismo catálogo que los indicadores. |
| `nivel_cuidado` | string | Fila de nivel | Glosa completa del origen (`401 - Área Médica Adulto Cuidados Básicos`). |
| `total` | int64 | Total | Igual a la suma de las 12 categorías en todas las filas (se valida). |
| `a1` … `d3` | int64 | A1 … D3 | Categorizaciones en cada categoría. |

**Lectura de las categorías.** CUDYR combina **riesgo** (A máximo, B alto, C mediano, D bajo) y **dependencia** (1 total, 2 parcial, 3 autosuficiencia parcial), y se aplica a quien ocupa una cama más de 8 horas. La agrupación usada en el EDA, tomada de González P, Kappes M, Gallardo-Vargas C. *Cuidados según dependencia y riesgo en hospitales de baja complejidad del Servicio de Salud Reloncaví, Chile*. Ciencia y Enfermería. 2024;30:31 ([doi:10.29393/CE30-31CSPC30031](https://doi.org/10.29393/CE30-31CSPC30031)), es: **críticos** A1, A2, A3, B1, B2; **cuidados medios** B3, C1, C2; **cuidados básicos** C3, D1, D2, D3. El artículo se cita como referencia de definición; no forma parte del RAW.

**Unidad del conteo.** El libro no define si cuenta pacientes o categorizaciones diarias. Que las categorizaciones de un trimestre se acerquen a los días cama ocupados del mismo trimestre (mediana 0,93 en áreas no psiquiátricas; 0,70 en psiquiatría) es coherente con paciente-días categorizados, pero es una inferencia, no una definición de la fuente.

## Qué no contienen los Parquet

- **Las filas agregadas del libro de indicadores.** Cada hoja intercala con el detalle filas `Datos País` (códigos 0), `Datos Servicio Salud` (código de establecimiento 0) y `Datos Establecimiento` (código de nivel 0), en las mismas columnas. Sumarlas junto al detalle contaría lo mismo dos o tres veces, así que quedan solo en el RAW. Se usan para validar: el detalle reconstruye **exactamente** los 17.478 agregados publicados en conteos y en cada mes (0 discrepancias en el snapshot vigente). La única diferencia es el acumulado anual del promedio de camas (415 agregados), que no es aditivo entre áreas por definición.
- Títulos y encabezados. La categorización no trae filas de totales ni notas.

## Construcción

1. Se valida cada libro con los validadores de la descarga: el año del título, el encabezado exacto, los meses esperados (12 en años cerrados; los del corte en el año en curso) y un mínimo de filas.
2. **Indicadores:** cada fila se clasifica por sus códigos y etiquetas (país, servicio, establecimiento o detalle). La etapa **falla** si una fila no responde a ningún patrón, si el indicador no es uno de los 11 conocidos, si un valor no es numérico o si hay datos fuera de las columnas contempladas.
3. **Categorización:** se aplana la jerarquía. Una fila con valores debe ser un nivel de cuidado (`NNN - nombre`). Sin valores, es un Servicio de Salud si empieza con `SS `, una región si la sigue un Servicio de Salud y, si no, un establecimiento. Un nivel sin establecimiento previo o un conteo que no sea entero no negativo detienen la etapa.
4. Falla si dos filas repiten la llave lógica o si dos libros declaran el mismo año.
5. Se concilia el detalle con los agregados y el acumulado con sus meses, y el total de cada fila de categorización con sus 12 categorías. Las discrepancias se informan en el log y nunca se corrigen.
6. Se escriben ambos Parquet de forma atómica (temporales, relectura y reemplazo conjunto con rollback), con `zstd`. El footer registra `raw_sha256_por_archivo`, un JSON con la ruta relativa y el SHA256 de cada RAW de origen. El contrato de `SKIP` exige que coincida con los RAW vigentes: un nuevo corte mensual invalida el Parquet.

## Advertencias de interpretación

- **Sumar solo conteos.** Las razones y el acumulado del promedio de camas no se suman ni se promedian entre áreas o meses. Un índice de varias áreas se recalcula desde los conteos sumados (p. ej., `100 · Σ ocupados / Σ disponibles`).
- **Cambio de definición en 2025.** El promedio de días de estada y la letalidad publicados dejan de descontar los traslados del denominador desde 2025. Para series de varios años, recalcularlos desde los conteos con una definición fija.
- **Año en curso parcial y mutable.** En el snapshot vigente, 2026 trae 9 meses (enero a septiembre). El DEIS reemplaza el libro con cada corte; los meses siguientes son nulos, no cero.
- **Días cama ocupados por sobre los disponibles.** Ocurre en 1.955 de 172.317 área-meses (233 en psiquiatría). La fuente no permite saber si son camas supletorias, pacientes en camillas, traslados internos o errores de registro.
- **No mide la espera en la urgencia.** Un paciente que espera cama en la urgencia no es un día cama ocupado de un área de hospitalización. Estos datos no cuantifican hospitalizaciones en camillas o sillas fuera de esas áreas.
- **Disponibles no es dotación.** El promedio de camas disponibles descuenta las camas no habilitadas; difiere de la dotación declarada (`dotacion_camas_snss`) en más del 10 % en el 21 % de las áreas-año comparables.
- **Relación con Urgencias.** Comparten `establecimiento_codigo`, pero el ID42 de Urgencias cuenta indicaciones de hospitalización en la urgencia de origen, no ingresos al área de ese hospital. Cualquier comparación es ecológica. Egresos no identifica el establecimiento y no se enlaza.
- **Solo SNSS.** Los libros cubren establecimientos públicos del SNSS; los privados no están.
