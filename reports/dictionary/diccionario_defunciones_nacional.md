# Diccionario de Defunciones consolidadas

Grano: una fila por registro publicado, nacional, sin llave natural. `fuente_id` + `fuente_fila` identifica una fila dentro del snapshot RAW cuyo hash figura en el footer. No es una llave de paciente. Todas las 27 variables se conservan semánticamente.

| Columna RAW | Columna Parquet | Tipo Arrow |
| --- | --- | --- |
| AÑO | ano_defuncion | int16 |
| FECHA_DEF | fecha_defuncion | date32[day] |
| SEXO_NOMBRE | sexo | string |
| EDAD_TIPO | edad_tipo | int8 |
| EDAD_CANT | edad_cantidad | int32 |
| COD_COMUNA | comuna_codigo_original | string |
| COMUNA | comuna_glosa | string |
| NOMBRE_REGION | region_glosa | string |
| DIAG1 | diag1 | string |
| CAPITULO_DIAG1 | capitulo_diag1 | string |
| GLOSA_CAPITULO_DIAG1 | glosa_capitulo_diag1 | string |
| CODIGO_GRUPO_DIAG1 | codigo_grupo_diag1 | string |
| GLOSA_GRUPO_DIAG1 | glosa_grupo_diag1 | string |
| CODIGO_CATEGORIA_DIAG1 | codigo_categoria_diag1 | string |
| GLOSA_CATEGORIA_DIAG1 | glosa_categoria_diag1 | string |
| CODIGO_SUBCATEGORIA_DIAG1 | codigo_subcategoria_diag1 | string |
| GLOSA_SUBCATEGORIA_DIAG1 | glosa_subcategoria_diag1 | string |
| DIAG2 | diag2 | string |
| CAPITULO_DIAG2 | capitulo_diag2 | string |
| GLOSA_CAPITULO_DIAG2 | glosa_capitulo_diag2 | string |
| CODIGO_GRUPO_DIAG2 | codigo_grupo_diag2 | string |
| GLOSA_GRUPO_DIAG2 | glosa_grupo_diag2 | string |
| CODIGO_CATEGORIA_DIAG2 | codigo_categoria_diag2 | string |
| GLOSA_CATEGORIA_DIAG2 | glosa_categoria_diag2 | string |
| CODIGO_SUBCATEGORIA_DIAG2 | codigo_subcategoria_diag2 | string |
| GLOSA_SUBCATEGORIA_DIAG2 | glosa_subcategoria_diag2 | string |
| LUGAR_DEFUNCION | lugar_defuncion | string |

| Columna adicional | Significado |
| --- | --- |
| comuna_codigo | Dígitos ASCII de ancho 4/5 → cinco dígitos con cero inicial; valor entero invariable. Otros formatos → nulo con excepción. No certifica pertenencia a un catálogo CUT; 99999 permanece 99999. |
| fecha_defuncion_original, edad_tipo_original, edad_cantidad_original | Texto publicado intacto para auditar conversiones; un valor no interpretable queda nulo solo en su columna tipada. |
| fuente_id, fuente_archivo, fuente_fila | Identificador de procedencia, ruta relativa y ordinal CSV (desde 1, excluye cabecera; no es número de línea física si hay campos multilínea). |
| registro_raw_sha256 | SHA256 de la lista de las 27 celdas originales serializada JSON UTF-8 compacto. |
| excepciones | Lista de incidencias conservadas; puede contener más de una por fila. |

Reglas: espacios exteriores retirados en textos analíticos; blanco → nulo excepto columnas originales de auditoría (conservan texto exacto). No se interpreta `*`, 0, 99 ni 999 como ausente. Año obligatorio entero válido; fecha según formatos configurados, sin inferir día/mes desde el año. Edades enteras anulables y unidad separada: 0 ignorado, 1 años, 2 meses, 3 días, 4 horas, según diccionario RAW. No se calcula edad equivalente ni se corrigen edades extremas.

DIAG1 conserva causa básica y DIAG2 causa externa; ambos con capítulo, grupo, categoría, subcategoría y glosas originales normalizadas solo en espacios. No se completan jerarquías faltantes. Territorio representa residencia según diccionario fuente, cuyo título y algunos nombres son anteriores al esquema actual; no se interpreta como establecimiento hospitalario.

El periodo, encoding, formatos, tamaño de bloque y rutas están en `src/data/defunciones_config.json`; fin nulo toma toda la información disponible desde el inicio configurado. Años de lotes distintos no pueden solaparse dentro del periodo: se falla para revisar la fuente, nunca se elige una en silencio. Los registros sin fecha se incluyen por el año declarado; discrepancias fecha/año se marcan. No se selecciona por región ni diagnóstico.

Ejecución: `python scripts/run_pipeline.py --stage clean_defunciones`. `--force` regenera únicamente esta consolidación. Reutilización valida esquema, compresión, conteos del footer, configuración, código y hashes de los RAW; sin coincidencia se reconstruye. La publicación de los cuatro outputs tiene temporales y rollback conjunto; no se escribe en RAW.
