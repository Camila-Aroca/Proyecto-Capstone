# EDA RAW de Defunciones DEIS

## Alcance y método

Perfil exploratorio nacional de los dos paquetes publicados por DEIS. Grano: una fila del CSV de defunciones disociadas publicado; no representa personas enlazables. Escaneo completo por streaming de los archivos, sin muestreo ni carga integral en memoria. Se conserva toda la fuente, sin filtrar RM, causas ni años, sin imputar ni deduplicar. No hay joins, modelos, tasas ni outputs processed.

Generado UTC: `2026-11-03T01:14:15.891224+00:00`. Python: `3.12.6`. Parser estándar `csv`, delimitador `;`, lectura `latin-1` consistente con los bytes de la cabecera `AÑO`. No se recodifican los archivos. Límite por CSV: 2 GiB; campos categóricos y comunas: hasta 4.096 valores por agregado; caché de fechas: 65.536 valores. Los excesos detienen el proceso.

Reproducción: `python scripts/run_pipeline.py --stage download_defunciones`; para regenerar solo el perfil: `python scripts/run_pipeline.py --stage eda_defunciones --force`.

## Semántica y limitaciones de la documentación fuente

Los XLSX incluidos se conservan íntegros, uno por paquete. Su título declara 2016–2020 y sus nombres `ANO_DEF`, `GLOSA_SEXO`, `CODIGO_COMUNA_RESIDENCIA`, `GLOSA_COMUNA_RESIDENCIA` y `GLOSA_REG_RES` difieren de los nombres actuales `AÑO`, `SEXO_NOMBRE`, `COD_COMUNA`, `COMUNA` y `NOMBRE_REGION`. La correspondencia por posición/tema es una interpretación para este perfil, no una homologación oficial del esquema. El diccionario describe territorio de residencia, no ubicación de un hospital.

El manual distingue `DIAG1` (causa básica) de `DIAG2` (causa externa) y orienta a usar DIAG2 para causas externas. `EDAD_TIPO` expresa la unidad: 1 años, 2 meses, 3 días, 4 horas y 0 ignorado. Por ello `EDAD_CANT` se describe por unidad y no se mezcla en un promedio. El diccionario llama a EDAD_CANT edad al ingreso, texto que resulta discordante con el tema de defunciones y se conserva sin corregir.

La forma alfanumérica de un código no certifica pertenencia a un catálogo CIE-10. Los códigos numéricos históricos no se homologan ni se interpretan como CIE-10; no se ha verificado su clasificación con un catálogo específico. Los registros con prefijo F son únicamente un conteo textual exploratorio, no un dataset clínico F00–F99. La sección de salud mental añade reglas explícitas de forma y campo para F y suicidio.

Se distinguen celdas blancas y el marcador literal `*`; no se asume que otros códigos como 0, 99 o 999 sean ausentes. `COD_COMUNA` se audita por forma de cinco dígitos, sin certificar vigencia territorial. El prefijo 13 se cuenta como indicador de formato RM sin cruzar con el catálogo territorial.

El paquete 1990–2023 se rotula como cifras oficiales según su nombre. El paquete 2024–2026 es un snapshot fechado 27/10/2026: no se afirma que 2024 o 2025 estén consolidados y 2026 no constituye un año completo. La fecha máxima observada se calcula desde FECHA_DEF y no se deduce de la URL. No se comparan conteos parciales con años completos para inferir tendencias.

La validación estructural no acredita exhaustividad respecto del registro nacional. No se auditan duplicados exactos ni identificadores únicos; filas idénticas pueden representar defunciones distintas y no se eliminan. El subregistro y las causas de ausencia/anomalías no son determinables con estos archivos por sí solos. No es posible determinarlo con los datos disponibles.

## Observaciones: 1990_2023

Fuente: [ZIP oficial DEIS](https://repositoriodeis.minsal.cl/DatosAbiertos/VITALES/DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.zip). RAW: `data/raw/defunciones/1990_2023/DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.csv`.

Filas leídas: **3,182,446**. Columnas: **27**. Fechas válidas: `1990-01-01` a `2023-12-31`. Años esperados sin filas: `[]`.

SHA256 CSV: `b763f5be857edbef5d06dc2da9437d7be8640f76719b5a0bb75b276282553ebb`. Tamaño: 869,415,741 bytes. SHA256 diccionario: `298600901a454f91bfb5634359efdbcb163d8a61d6e1b8dcdae01768ec38c60f`. Procedencia coincide con el último snapshot registrado: **True**.

| Control | Registros |
| --- | --- |
| Fecha no interpretable con los tres formatos declarados | 323 |
| Año de FECHA_DEF distinto de AÑO | 0 |
| Fecha posterior a fecha civil de ejecución en Chile | 0 |
| COD_COMUNA sin forma de cinco dígitos (incluye blanco) | 1551470 |
| COD_COMUNA de cinco dígitos con prefijo 13 | 1191382 |
| Comunas distintas con forma de cinco dígitos | 141 |
| DIAG1 numérico | 380772 |
| DIAG1 con forma CIE-10, sin validar catálogo | 2645700 |
| DIAG1 no blanco con otra forma (incluye *) | 155973 |
| DIAG1 con prefijo textual F | 60650 |
| DIAG2 con forma CIE-10, sin validar catálogo | 212781 |

### Cobertura anual y forma diagnóstica

| AÑO publicado | Filas | DIAG1 numérico | DIAG1 forma CIE-10 | Prefijo F |
| --- | --- | --- | --- | --- |
| 1990 | 78434 | 56880 | 0 | 0 |
| 1991 | 74862 | 54340 | 0 | 0 |
| 1992 | 74090 | 52544 | 0 | 0 |
| 1993 | 76261 | 53846 | 0 | 0 |
| 1994 | 75445 | 53302 | 0 | 0 |
| 1995 | 78531 | 54684 | 0 | 0 |
| 1996 | 79123 | 55176 | 0 | 0 |
| 1997 | 78472 | 0 | 78472 | 1584 |
| 1998 | 80257 | 0 | 80257 | 869 |
| 1999 | 81984 | 0 | 81984 | 488 |
| 2000 | 78814 | 0 | 78814 | 1332 |
| 2001 | 81871 | 0 | 81871 | 2206 |
| 2002 | 81079 | 0 | 81079 | 2509 |
| 2003 | 83672 | 0 | 83672 | 2653 |
| 2004 | 86138 | 0 | 86138 | 2600 |
| 2005 | 86102 | 0 | 86102 | 2570 |
| 2006 | 85639 | 0 | 85639 | 2332 |
| 2007 | 93000 | 0 | 93000 | 2789 |
| 2008 | 90168 | 0 | 90168 | 2666 |
| 2009 | 91965 | 0 | 91965 | 2574 |
| 2010 | 97930 | 0 | 97930 | 2585 |
| 2011 | 94985 | 0 | 94985 | 2224 |
| 2012 | 98711 | 0 | 98711 | 2568 |
| 2013 | 99770 | 0 | 99770 | 2064 |
| 2014 | 101960 | 0 | 101960 | 1836 |
| 2015 | 103327 | 0 | 103327 | 1662 |
| 2016 | 104026 | 0 | 104026 | 1794 |
| 2017 | 106388 | 0 | 106388 | 1929 |
| 2018 | 106796 | 0 | 106796 | 2265 |
| 2019 | 109658 | 0 | 109658 | 2443 |
| 2020 | 126169 | 0 | 126169 | 2641 |
| 2021 | 137629 | 0 | 137629 | 3075 |
| 2022 | 136972 | 0 | 136972 | 3240 |
| 2023 | 122218 | 0 | 122218 | 3152 |

### Ausencias y marcadores, sin recodificar

| Columna | Blancos | Blancos % | Literal * |
| --- | --- | --- | --- |
| AÑO | 0 | 0.000 | 0 |
| FECHA_DEF | 323 | 0.010 | 0 |
| SEXO_NOMBRE | 0 | 0.000 | 0 |
| EDAD_TIPO | 24 | 0.001 | 0 |
| EDAD_CANT | 24 | 0.001 | 0 |
| COD_COMUNA | 0 | 0.000 | 0 |
| COMUNA | 0 | 0.000 | 0 |
| NOMBRE_REGION | 0 | 0.000 | 0 |
| DIAG1 | 1 | 0.000 | 0 |
| CAPITULO_DIAG1 | 536746 | 16.866 | 0 |
| GLOSA_CAPITULO_DIAG1 | 536746 | 16.866 | 0 |
| CODIGO_GRUPO_DIAG1 | 536746 | 16.866 | 0 |
| GLOSA_GRUPO_DIAG1 | 536746 | 16.866 | 0 |
| CODIGO_CATEGORIA_DIAG1 | 536746 | 16.866 | 0 |
| GLOSA_CATEGORIA_DIAG1 | 536746 | 16.866 | 0 |
| CODIGO_SUBCATEGORIA_DIAG1 | 536746 | 16.866 | 0 |
| GLOSA_SUBCATEGORIA_DIAG1 | 536746 | 16.866 | 0 |
| DIAG2 | 2906635 | 91.333 | 0 |
| CAPITULO_DIAG2 | 2969665 | 93.314 | 0 |
| GLOSA_CAPITULO_DIAG2 | 2969665 | 93.314 | 0 |
| CODIGO_GRUPO_DIAG2 | 2969665 | 93.314 | 0 |
| GLOSA_GRUPO_DIAG2 | 2969665 | 93.314 | 0 |
| CODIGO_CATEGORIA_DIAG2 | 2969665 | 93.314 | 0 |
| GLOSA_CATEGORIA_DIAG2 | 2969665 | 93.314 | 0 |
| CODIGO_SUBCATEGORIA_DIAG2 | 2969665 | 93.314 | 0 |
| GLOSA_SUBCATEGORIA_DIAG2 | 2969665 | 93.314 | 0 |
| LUGAR_DEFUNCION | 0 | 0.000 | 0 |

### Sexo publicado

| Valor agregado | Filas |
| --- | --- |
| Hombre | 1708226 |
| Indeterminado | 183 |
| Mujer | 1474037 |

### Región publicada

| Valor agregado | Filas |
| --- | --- |
| De Aisén del Gral. C. Ibáñez del Campo | 16241 |
| De Antofagasta | 91308 |
| De Arica y Parinacota | 36911 |
| De Atacama | 45177 |
| De Coquimbo | 123414 |
| De La Araucanía | 203951 |
| De Los Lagos | 161165 |
| De Los Ríos | 84138 |
| De Magallanes y de La Antártica Chilena | 33577 |
| De Tarapacá | 41017 |
| De Valparaíso | 374539 |
| De Ñuble | 107498 |
| Del Bíobío | 297633 |
| Del Libertador B. O'Higgins | 167438 |
| Del Maule | 206993 |
| Ignorada | 64 |
| Metropolitana de Santiago | 1191382 |

### Lugar de defunción publicado

| Valor agregado | Filas |
| --- | --- |
| Casa habitación | 1484957 |
| Hospital o Clínica | 1412177 |
| Otro | 285312 |

### Cantidad de edad por unidad publicada

| EDAD_TIPO | Filas | Mínimo | Máximo | No numérico | Negativo | Literal 999 |
| --- | --- | --- | --- | --- | --- | --- |
| (blanco) | 24 | 2 | 2 | 23 | 0 | 0 |
| 0 | 2 | 99 | 99 | 0 | 0 | 0 |
| 1 | 3105963 | 1 | 126 | 1 | 0 | 0 |
| 2 | 27740 | 1 | 11 | 0 | 0 | 0 |
| 3 | 25471 | 1 | 31 | 0 | 0 | 0 |
| 4 | 23246 | 1 | 24 | 0 | 0 | 0 |

## Observaciones: 2024_2026_27102026

Fuente: [ZIP oficial DEIS](https://repositoriodeis.minsal.cl/DatosAbiertos/VITALES/DEFUNCIONES_FUENTE_DEIS_2024_2026_27102026.zip). RAW: `data/raw/defunciones/2024_2026_27102026/DEFUNCIONES_FUENTE_DEIS_2024_2026_27102026.csv`.

Filas leídas: **356,974**. Columnas: **27**. Fechas válidas: `2024-01-01` a `2026-10-24`. Años esperados sin filas: `[]`.

SHA256 CSV: `01cd5779ede07925716c1f01561f87f0e73e3a870bf7fbdb2a217b1a0eed82ea`. Tamaño: 108,034,433 bytes. SHA256 diccionario: `298600901a454f91bfb5634359efdbcb163d8a61d6e1b8dcdae01768ec38c60f`. Procedencia coincide con el último snapshot registrado: **True**.

| Control | Registros |
| --- | --- |
| Fecha no interpretable con los tres formatos declarados | 0 |
| Año de FECHA_DEF distinto de AÑO | 0 |
| Fecha posterior a fecha civil de ejecución en Chile | 0 |
| COD_COMUNA sin forma de cinco dígitos (incluye blanco) | 176862 |
| COD_COMUNA de cinco dígitos con prefijo 13 | 131967 |
| Comunas distintas con forma de cinco dígitos | 138 |
| DIAG1 numérico | 0 |
| DIAG1 con forma CIE-10, sin validar catálogo | 356974 |
| DIAG1 no blanco con otra forma (incluye *) | 0 |
| DIAG1 con prefijo textual F | 10693 |
| DIAG2 con forma CIE-10, sin validar catálogo | 21827 |

### Cobertura anual y forma diagnóstica

| AÑO publicado | Filas | DIAG1 numérico | DIAG1 forma CIE-10 | Prefijo F |
| --- | --- | --- | --- | --- |
| 2024 | 126928 | 0 | 126928 | 3639 |
| 2025 | 126466 | 0 | 126466 | 3676 |
| 2026 | 103580 | 0 | 103580 | 3378 |

### Ausencias y marcadores, sin recodificar

| Columna | Blancos | Blancos % | Literal * |
| --- | --- | --- | --- |
| AÑO | 0 | 0.000 | 0 |
| FECHA_DEF | 0 | 0.000 | 0 |
| SEXO_NOMBRE | 0 | 0.000 | 0 |
| EDAD_TIPO | 0 | 0.000 | 0 |
| EDAD_CANT | 0 | 0.000 | 0 |
| COD_COMUNA | 64 | 0.018 | 0 |
| COMUNA | 64 | 0.018 | 0 |
| NOMBRE_REGION | 64 | 0.018 | 0 |
| DIAG1 | 0 | 0.000 | 0 |
| CAPITULO_DIAG1 | 2 | 0.001 | 0 |
| GLOSA_CAPITULO_DIAG1 | 2 | 0.001 | 0 |
| CODIGO_GRUPO_DIAG1 | 2 | 0.001 | 0 |
| GLOSA_GRUPO_DIAG1 | 2 | 0.001 | 0 |
| CODIGO_CATEGORIA_DIAG1 | 2 | 0.001 | 0 |
| GLOSA_CATEGORIA_DIAG1 | 2 | 0.001 | 0 |
| CODIGO_SUBCATEGORIA_DIAG1 | 2 | 0.001 | 0 |
| GLOSA_SUBCATEGORIA_DIAG1 | 2 | 0.001 | 0 |
| DIAG2 | 335147 | 93.886 | 0 |
| CAPITULO_DIAG2 | 335147 | 93.886 | 0 |
| GLOSA_CAPITULO_DIAG2 | 335147 | 93.886 | 0 |
| CODIGO_GRUPO_DIAG2 | 335147 | 93.886 | 0 |
| GLOSA_GRUPO_DIAG2 | 335147 | 93.886 | 0 |
| CODIGO_CATEGORIA_DIAG2 | 335147 | 93.886 | 0 |
| GLOSA_CATEGORIA_DIAG2 | 335147 | 93.886 | 0 |
| CODIGO_SUBCATEGORIA_DIAG2 | 335147 | 93.886 | 0 |
| GLOSA_SUBCATEGORIA_DIAG2 | 335147 | 93.886 | 0 |
| LUGAR_DEFUNCION | 0 | 0.000 | 0 |

### Sexo publicado

| Valor agregado | Filas |
| --- | --- |
| Hombre | 185563 |
| Indeterminado | 11 |
| Mujer | 171400 |

### Región publicada

| Valor agregado | Filas |
| --- | --- |
| (blanco) | 64 |
| De Aisén del Gral. C. Ibáñez del Campo | 1691 |
| De Antofagasta | 10118 |
| De Arica y Parinacota | 4545 |
| De Atacama | 5461 |
| De Coquimbo | 15714 |
| De La Araucanía | 21700 |
| De Los Lagos | 17741 |
| De Los Ríos | 8855 |
| De Magallanes y de La Antártica Chilena | 3425 |
| De Tarapacá | 5061 |
| De Valparaíso | 42864 |
| De Ñuble | 11858 |
| Del Bíobío | 32823 |
| Del Libertador B. O'Higgins | 19923 |
| Del Maule | 23134 |
| Ignorada | 30 |
| Metropolitana de Santiago | 131967 |

### Lugar de defunción publicado

| Valor agregado | Filas |
| --- | --- |
| Casa habitación | 178975 |
| Hospital o Clínica | 146412 |
| Otro | 31587 |

### Cantidad de edad por unidad publicada

| EDAD_TIPO | Filas | Mínimo | Máximo | No numérico | Negativo | Literal 999 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 9 | 0 | 0 | 0 | 0 | 0 |
| 1 | 354437 | 1 | 140 | 0 | 0 | 0 |
| 2 | 594 | 1 | 11 | 0 | 0 | 0 |
| 3 | 949 | 1 | 30 | 0 | 0 | 0 |
| 4 | 985 | 1 | 23 | 0 | 0 | 0 |

## Hallazgos de salud mental y suicidio

Ventana descriptiva predefinida: 2021–2025 (AÑO publicado). Se mantienen todas las causas y años en el escaneo; esta ventana solo delimita las tablas de composición. No se certifica el cierre de 2024–2025. Los conteos son registros publicados, no tasas ni estimaciones de riesgo.

### Definiciones y territorio

El manual DEIS incluido en cada paquete indica consultar DIAG1 para enfermedades y DIAG2 entre X60 y X84 para suicidio. Se cuenta F00–F99 por forma explícita en DIAG1, X60–X84 en DIAG2, Y87.0 por separado como secuelas y Y10–Y34 como intención no determinada, sin reclasificarla como suicidio. Se aceptan códigos de tres/cuatro caracteres y punto opcional, sin cambiar el RAW; no se valida cada subcategoría contra un catálogo. RM se define por NOMBRE_REGION igual a `Metropolitana de Santiago`, territorio de residencia según el diccionario; no se usa la ubicación de un hospital.

[OMS: capítulo F00–F09 y demencias](https://icd.who.int/browse10/2019/en/GetConcept?ConceptId=F00-F09). [OMS: agrupaciones de mortalidad, X60–X84 y Y87.0](https://platform.who.int/mortality/about/list-of-causes-and-corresponding-icd-10-codes).

### Conteos anuales nacionales y de residentes RM

| Año | F DIAG1 nacional | F DIAG1 RM | X60–X84 DIAG2 nacional | X60–X84 DIAG2 RM |
| --- | --- | --- | --- | --- |
| 2021 | 3075 | 1164 | 1573 | 496 |
| 2022 | 3240 | 1288 | 2099 | 693 |
| 2023 | 3152 | 1172 | 2056 | 615 |
| 2024 | 3639 | 1401 | 1984 | 662 |
| 2025 | 3676 | 1414 | 1927 | 573 |
| Total 2021–2025 | 16782 | 6439 | 9639 | 3039 |

### Composición de DIAG1 F00–F99

| Categoría | Glosa publicada (sin reconstruir) | Registros 2021–2025 |
| --- | --- | --- |
| F03 | Demencia , no especificada | 12734 |
| F01 | Demencia vascular | 1452 |
| F10 | Trastornos mentales y del comportamiento debidos al uso de alcohol | 1044 |
| F06 | Otros trastornos mentales debidos a lesión y disfunción cerebral, y a enfermedad física | 537 |
| F20 | Esquizofrenia | 205 |
| F05 | Delirio, no inducido por alcohol o por otras sustancias psicoactivas | 187 |
| F19 | Trastornos mentales y del comportamiento debidos al uso de múltiples drogas y al uso de otras sustancias psicoactivas | 172 |
| F17 | Trastornos mentales y del comportamiento debidos al uso de tabaco | 166 |
| F32 | Episodio depresivo | 104 |
| F14 | Trastornos mentales y del comportamiento debidos al uso de cocaína | 38 |
| F79 | Retraso mental, no especificado | 28 |
| F31 | Trastorno afectivo bipolar | 20 |
| F44 | Trastornos disociativos [de conversión] | 19 |
| F72 | Retraso mental grave | 15 |
| F84 | Trastornos generalizados del desarrollo | 13 |
| F48 | Neurastenia | 7 |
| F29 | Psicosis de origen no orgánico, no especificada | 4 |
| F50 | Trastornos de la ingestión de alimentos | 4 |
| F33 | Trastorno depresivo recurrente | 4 |
| F43 | Reacción al estrés grave y trastornos de adaptación | 2 |
| F25 | Trastornos esquizoafectivos | 2 |
| F34 | Trastorno del humor [afectivos] persistentes | 2 |
| F68 | Otros trastornos de la personalidad y del comportamiento en adultos | 2 |
| F16 | Trastornos mentales y del comportamiento debidos al uso de alucinógenos | 2 |
| F71 | Retraso mental moderado | 2 |
| F15 | Trastornos mentales y del comportamiento debidos al uso de otros estimilantes, incluida la cafeína | 2 |
| F91 | Trastornos de la conducta | 2 |
| F60 | Trastornos específicos de la personalidad | 1 |
| F55 | Abuso de sustancias que no producen dependencia | 1 |
| F82 | Trastorno especÍfico del desarrollo de la función motriz | 1 |
| F99 | Trastorno mental, no especificado | 1 |
| F42 | Trastorno obsesivo-compulsivo | 1 |
| F09 | Trastorno mental orgánico o sintomático, no especificado | 1 |
| F73 | Retraso mental profundo | 1 |
| F39 | Trastorno del humor [afectivo], no especificado | 1 |
| F70 | Retraso mental leve | 1 |
| F23 | Trastornos psicóticos agudos y transitorios | 1 |
| F22 | Trastornos delirantes persistentes | 1 |
| F30 | Episodio maníaco | 1 |
| F81 | Trastornos específicos del  desarrollo de las habilidades escolares | 1 |

F01 y F03 reúnen 14186 registros (84.5% del conjunto F). Las edades publicadas de 65 años o más reúnen 15486 registros (92.3%). El indicador agregado F refleja principalmente demencias en este snapshot; conviene distinguirlas de sustancias y otros trastornos. Un conteo DIAG1 F32 no equivale a todas las muertes de personas con depresión: no existe historia clínica completa en estos campos.

### Sexo y edad: conjuntos separados

| DIAG1 F: sexo publicado | Registros | % del conjunto |
| --- | --- | --- |
| Hombre | 6675 | 39.8% |
| Mujer | 10107 | 60.2% |

| DIAG1 F: edad en años | Registros |
| --- | --- |
| 0-14 | 6 |
| 15-29 | 37 |
| 30-44 | 196 |
| 45-64 | 1056 |
| 65+ | 15486 |
| otra_unidad_o_no_interpretable | 1 |

| DIAG2 X60–X84: sexo publicado | Registros | % del conjunto |
| --- | --- | --- |
| Hombre | 7775 | 80.7% |
| Mujer | 1864 | 19.3% |

| DIAG2 X60–X84: edad en años | Registros |
| --- | --- |
| 0-14 | 74 |
| 15-29 | 2326 |
| 30-44 | 3043 |
| 45-64 | 2843 |
| 65+ | 1353 |

La edad solo se agrupa cuando EDAD_TIPO=1 y EDAD_CANT contiene un entero no negativo. Otras unidades/valores no interpretables se conservan en categoría separada; no se convierten meses a años ni se imputan edades.

En 2021–2025 se observan 0 códigos X60–X84 en DIAG1 y 9639 en DIAG2. Un filtro exclusivo F00–F99 en DIAG1 deja fuera la definición de suicidio del manual. Esta separación no permite inferir antecedentes psiquiátricos.

Y87.0 en DIAG2: 0 registros nacionales y 0 RM. Y10–Y34 en DIAG2: 4 nacionales y 2 RM. No se suman los eventos de intención no determinada a suicidio.

### Comparabilidad histórica

Los códigos numéricos históricos no se interpretan como CIE-10; la ausencia de F/X con forma CIE-10 en esos años no acredita ausencia de casos. La siguiente tabla permite inspeccionar cambios en intención no determinada sin atribuirlos a cambios reales del riesgo:

| Año | X60–X84 DIAG2 nacional | X60–X84 DIAG2 RM | Y10–Y34 nacional | Y10–Y34 RM |
| --- | --- | --- | --- | --- |
| 1990 | 0 | 0 | 0 | 0 |
| 1991 | 0 | 0 | 0 | 0 |
| 1992 | 0 | 0 | 0 | 0 |
| 1993 | 0 | 0 | 0 | 0 |
| 1994 | 0 | 0 | 0 | 0 |
| 1995 | 0 | 0 | 0 | 0 |
| 1996 | 0 | 0 | 0 | 0 |
| 1997 | 910 | 31 | 2568 | 1723 |
| 1998 | 1031 | 63 | 2587 | 1736 |
| 1999 | 1041 | 35 | 2457 | 1648 |
| 2000 | 1473 | 507 | 801 | 118 |
| 2001 | 1625 | 548 | 242 | 56 |
| 2002 | 1599 | 498 | 1 | 0 |
| 2003 | 1654 | 543 | 0 | 0 |
| 2004 | 1735 | 576 | 100 | 24 |
| 2005 | 1680 | 567 | 0 | 0 |
| 2006 | 1795 | 608 | 0 | 0 |
| 2007 | 1926 | 638 | 0 | 0 |
| 2008 | 2166 | 726 | 0 | 0 |
| 2009 | 2148 | 787 | 0 | 0 |
| 2010 | 2001 | 692 | 0 | 0 |
| 2011 | 2027 | 712 | 0 | 0 |
| 2012 | 1841 | 670 | 0 | 0 |
| 2013 | 1738 | 639 | 0 | 0 |
| 2014 | 1789 | 650 | 0 | 0 |
| 2015 | 1835 | 701 | 0 | 0 |
| 2016 | 1858 | 677 | 0 | 0 |
| 2017 | 1879 | 658 | 0 | 0 |
| 2018 | 1823 | 617 | 0 | 0 |
| 2019 | 1901 | 638 | 0 | 0 |
| 2020 | 1602 | 469 | 1 | 1 |
| 2021 | 1573 | 496 | 0 | 0 |
| 2022 | 2099 | 693 | 3 | 1 |
| 2023 | 2056 | 615 | 0 | 0 |
| 2024 | 1984 | 662 | 0 | 0 |
| 2025 | 1927 | 573 | 1 | 1 |
| 2026 | 1458 | 435 | 0 | 0 |

2026 es parcial; consultar el corte observado en las secciones por paquete. No comparar directamente años parciales y completos ni inferir tendencias de riesgo desde estos conteos: se requieren denominadores y ajustes apropiados. La causa de diferencias históricas y la magnitud del subregistro no son identificables aquí. No es posible determinarlo con los datos disponibles.

### Contraste con Estadísticas de Género

Comprobación agregada opcional contra `data/processed/contexto_genero/suicidio_ratio_hm_tasas_nacional_regional.parquet` (SHA256 `2f4c107add093f1c1264874b1f8ed1ae1a7f880138c43974144298e282372c7d`). Coinciden 42 de 49 comparaciones año × ámbito disponibles. Se comparan conteos Total nacionales y RM de defunciones_suicidio con X60–X84 en DIAG2; no se enlazan personas ni se incorporan variables al modelo.

| Año | Ámbito | RAW X60–X84 | Contexto | Coincide |
| --- | --- | --- | --- | --- |
| 1997 | Nacional | 910 | 910 | True |
| 1998 | Nacional | 1031 | 1031 | True |
| 1999 | Nacional | 1041 | 1041 | True |
| 2000 | Nacional | 1473 | 1473 | True |
| 2001 | Nacional | 1625 | 1625 | True |
| 2002 | Nacional | 1599 | 1603 | False |
| 2003 | Nacional | 1654 | 1654 | True |
| 2004 | Nacional | 1735 | 1735 | True |
| 2005 | Nacional | 1680 | 1680 | True |
| 2006 | Nacional | 1795 | 1795 | True |
| 2007 | Nacional | 1926 | 1926 | True |
| 2009 | Nacional | 2148 | 2148 | True |
| 2010 | Nacional | 2001 | 2001 | True |
| 2011 | Nacional | 2027 | 2027 | True |
| 2012 | Nacional | 1841 | 1841 | True |
| 2013 | Nacional | 1738 | 1738 | True |
| 2014 | Nacional | 1789 | 1789 | True |
| 2015 | Nacional | 1835 | 1835 | True |
| 2016 | Nacional | 1858 | 1858 | True |
| 2017 | Nacional | 1879 | 1879 | True |
| 2018 | Nacional | 1823 | 1823 | True |
| 2008 | Nacional | 2166 | 2168 | False |
| 2019 | Nacional | 1901 | 1901 | True |
| 2020 | Nacional | 1602 | 1602 | True |
| 2021 | Nacional | 1573 | 1573 | True |
| 2022 | Nacional | 2099 | 2099 | True |
| 2023 | Nacional | 2056 | 2056 | True |
| 2002 | RM | 498 | 499 | False |
| 2003 | RM | 543 | 543 | True |
| 2004 | RM | 576 | 577 | False |
| 2005 | RM | 567 | 567 | True |
| 2006 | RM | 608 | 608 | True |
| 2007 | RM | 638 | 638 | True |
| 2008 | RM | 726 | 728 | False |
| 2009 | RM | 787 | 787 | True |
| 2010 | RM | 692 | 692 | True |
| 2011 | RM | 712 | 712 | True |
| 2012 | RM | 670 | 670 | True |
| 2013 | RM | 639 | 639 | True |
| 2014 | RM | 650 | 650 | True |
| 2015 | RM | 701 | 700 | False |
| 2016 | RM | 677 | 677 | True |
| 2017 | RM | 658 | 658 | True |
| 2018 | RM | 617 | 618 | False |
| 2019 | RM | 638 | 638 | True |
| 2020 | RM | 469 | 469 | True |
| 2021 | RM | 496 | 496 | True |
| 2022 | RM | 693 | 693 | True |
| 2023 | RM | 615 | 615 | True |

Las discrepancias se conservan; no se corrigen ni se atribuyen automáticamente a Y87.0, subregistro o revisiones. No es posible determinarlo con los datos disponibles.

### Alcance para el proyecto

Defunciones puede aportar resultados de mortalidad territorial complementarios a atenciones de Urgencias y hospitalizaciones de Egresos, preservando sus distintos granos. No permite concluir que quienes consultaron posteriormente fallecieron ni enlazar trayectorias individuales. No se crea integración, feature ni modelo de mortalidad con este EDA.

## Evidencia complementaria

`eda_defunciones_raw_resumen.json` contiene los mismos agregados, los conteos mensuales por fecha válida y los hashes de ambos archivos por paquete. Los agregados anuales usan AÑO; los mensuales usan FECHA_DEF válida, incluso si difiere de AÑO. No se crean tablas analíticas, integraciones con otras fuentes ni archivos processed.
