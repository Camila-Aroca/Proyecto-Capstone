# EDA de Defunciones consolidadas

Una fila por registro publicado. Alcance nacional y todas las causas; no se deduplica, imputa ni enlaza con otras fuentes. EDA de staging normalizado, no certificación clínica.

Filas: **884580**. Fechas observadas: 2020-01-01 a 2026-11-07. El último año puede ser parcial; el nombre/fecha del paquete no demuestra consolidación anual.

| Año | Filas |
| --- | ---: |
| 2020 | 126169 |
| 2021 | 137629 |
| 2022 | 136972 |
| 2023 | 122218 |
| 2024 | 126928 |
| 2025 | 126466 |
| 2026 | 108198 |

| Fuente | Leídas | Incluidas | Excluidas por periodo | SHA256 RAW |
| --- | ---: | ---: | ---: | --- |
| data/raw/defunciones/1990_2023/DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.csv | 3182446 | 522988 | 2659458 | b763f5be857edbef5d06dc2da9437d7be8640f76719b5a0bb75b276282553ebb |
| data/raw/defunciones/2024_2026_10112026/DEFUNCIONES_FUENTE_DEIS_2024_2026_10112026.csv | 361592 | 361592 | 0 | 51bf6485bbc475fc122d36f78cda122be16cdc849c3f819681287b5d03f167d3 |

Repeticiones adicionales de filas originales completas, por SHA256: **524**. Repeticiones de las 27 variables normalizadas: **549**. Se conservan todas: ausencia de identificador único de evento/paciente. Los hashes son comprobaciones criptográficas, no evidencia de identidad personal.

| Excepción conservada | Filas |
| --- | ---: |
| comuna_ausente | 65 |
| diag1_jerarquia_incompleta | 2 |
| edad_cantidad_ausente | 9 |
| edad_ignorada_segun_unidad | 11 |
| edad_tipo_ausente | 9 |
| fecha_ausente | 10 |

| Columna | Nulos |
| --- | ---: |
| ano_defuncion | 0 |
| fecha_defuncion | 10 |
| sexo | 0 |
| edad_tipo | 9 |
| edad_cantidad | 9 |
| comuna_codigo_original | 0 |
| comuna_glosa | 65 |
| region_glosa | 65 |
| diag1 | 0 |
| capitulo_diag1 | 2 |
| glosa_capitulo_diag1 | 2 |
| codigo_grupo_diag1 | 2 |
| glosa_grupo_diag1 | 2 |
| codigo_categoria_diag1 | 2 |
| glosa_categoria_diag1 | 2 |
| codigo_subcategoria_diag1 | 2 |
| glosa_subcategoria_diag1 | 2 |
| diag2 | 829524 |
| capitulo_diag2 | 829524 |
| glosa_capitulo_diag2 | 829524 |
| codigo_grupo_diag2 | 829524 |
| glosa_grupo_diag2 | 829524 |
| codigo_categoria_diag2 | 829524 |
| glosa_categoria_diag2 | 829524 |
| codigo_subcategoria_diag2 | 829524 |
| glosa_subcategoria_diag2 | 829524 |
| lugar_defuncion | 0 |
| comuna_codigo | 65 |
| fecha_defuncion_original | 0 |
| edad_tipo_original | 0 |
| edad_cantidad_original | 0 |
| fuente_id | 0 |
| fuente_archivo | 0 |
| fuente_fila | 0 |
| registro_raw_sha256 | 0 |
| excepciones | 0 |

Validación completa tras escribir: esquema, Zstandard, conteos por fuente/año, nulos, excepciones, multiplicidad de hashes RAW y normalizados y SHA256 de la secuencia de todas las columnas. Los SHA256 de los RAW se comprueban antes y después; ninguna fila se pierde por fechas/edades ausentes. Los tests de integración contrastan además las 27 variables directamente contra los CSV.

El resumen JSON asociado incluye configuración efectiva, hashes de código/RAW, conteos por fuente y año y hashes de los artefactos. No se infieren tasas, causalidad, ausencia clínica por DIAG2 vacío ni validez territorial por la forma del código. No es posible determinarlo con los datos disponibles.
