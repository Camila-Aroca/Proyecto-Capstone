# EDA — fuentes contextuales de Estadísticas de Género

## Alcance

Este reporte perfila cuatro XLSX oficiales como fuentes contextuales para el análisis de hospitalización por sexo. No realiza cruces, uniones ni inferencias respecto de Egresos DEIS o Urgencias.

## Hechos observados

### `egresos_intento_suicida_sexo_anio`

- Estructura RAW: PRESENTACIÓN (14 filas × 3 columnas), NACIONAL (26 filas × 15 columnas).
- Encabezados y grano: NACIONAL: fila 3; datos desde fila 4. Grano normalizado: año nacional × medida/sexo.
- Títulos/notas: Título en fila 1; fuente y notas al final de la hoja NACIONAL. PRESENTACIÓN contiene texto metodológico.
- Output: `data/processed/contexto_genero/egresos_intento_suicida_sexo_anio.parquet`; 120 filas; columnas: `source_id, source_sheet, geography_level, geography, region_code, period, year, sex, indicator, value, value_text, unit`.
- Cobertura temporal: años 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025; períodos sin año único: No aplica.
- Cobertura geográfica: niveles nacional; geografías Nacional.
- Categorías de sexo: Hombres, Mujeres, Mujeres/Hombres, Total. Indicadores: distribucion_egresos_intento_suicida, egresos_hospitalarios_intento_suicida, razon_egresos_intento_suicida. Unidades: %, N, razon.
- Calidad: missing numérico 0; valores textuales publicados `{}`; duplicados por clave natural 0; rango numérico [2.3333333333333335, 7889.0].

### `suicidio_ratio_hm_tasas_nacional_regional`

- Estructura RAW: PRESENTACIÓN (16 filas × 3 columnas), NACIONAL (47 filas × 11 columnas), REGIONAL (386 filas × 13 columnas).
- Encabezados y grano: NACIONAL y REGIONAL: fila 3; datos desde fila 4. Grano normalizado: año × nivel geográfico (nacional o región) × medida/sexo.
- Títulos/notas: Título en fila 1; notas de cobertura y tasas al final de cada cuadro. PRESENTACIÓN contiene texto metodológico.
- Output: `data/processed/contexto_genero/suicidio_ratio_hm_tasas_nacional_regional.parquet`; 3790 filas; columnas: `source_id, source_sheet, geography_level, geography, region_code, period, year, sex, indicator, value, value_text, unit`.
- Cobertura temporal: años 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023; períodos sin año único: No aplica.
- Cobertura geográfica: niveles nacional, regional; geografías Antofagasta, Arica y Parinacota, Atacama, Aysén, Biobío, Coquimbo, La Araucanía, Los Lagos, Los Ríos, Magallanes, Maule, Metropolitana, Nacional, O'Higgins, Tarapacá, Valparaíso, Ñuble.
- Categorías de sexo: Hombres, Hombres/Mujeres, Mujeres, Total. Indicadores: defunciones_suicidio, poblacion, ratio_defunciones_suicidio, tasa_mortalidad_suicidio. Unidades: N, por_100000, razon.
- Calidad: missing numérico 7; valores textuales publicados `{'-': 7}`; duplicados por clave natural 0; rango numérico [0.0, 19960889.0].

### `ansiedad_depresion_sintomas_18_mas_sexo`

- Estructura RAW: PRESENTACIÓN (16 filas × 3 columnas), NACIONAL (47 filas × 16380 columnas).
- Encabezados y grano: NACIONAL: encabezado multinivel en filas 3–4; datos desde fila 5. Grano normalizado: período nacional × medida/sexo.
- Títulos/notas: Título en fila 1; fuente y notas 1–3 al final. PRESENTACIÓN contiene texto metodológico.
- Output: `data/processed/contexto_genero/ansiedad_depresion_sintomas_18_mas_sexo.parquet`; 40 filas; columnas: `source_id, source_sheet, geography_level, geography, region_code, period, year, sex, indicator, value, value_text, unit`.
- Cobertura temporal: años No aplica; períodos sin año único: Julio 2020, Junio - Julio 2021, Noviembre - Diciembre 2020, Noviembre 2021.
- Cobertura geográfica: niveles nacional; geografías Nacional.
- Categorías de sexo: Hombres, Mujeres, Mujeres-Hombres, Total. Indicadores: brecha_genero_sintomas_moderados_severos_ansiedad_depresion, personas_18_mas, personas_18_mas_sintomas_moderados_severos_ansiedad_depresion, porcentaje_sintomas_moderados_severos_ansiedad_depresion. Unidades: %, N, pp.
- Calidad: missing numérico 0; valores textuales publicados `{}`; duplicados por clave natural 0; rango numérico [9.542735197662076, 15259069.0].

### `prevalencia_sintomas_depresivos_sexo`

- Estructura RAW: PRESENTACIÓN (16 filas × 3 columnas), NACIONAL (16 filas × 5 columnas).
- Encabezados y grano: NACIONAL: encabezado multinivel en filas 4–5; datos desde fila 6. Grano normalizado: período nacional × sexo.
- Títulos/notas: Título en fila 1; fuente y notas 1–2 al final. PRESENTACIÓN contiene texto metodológico.
- Output: `data/processed/contexto_genero/prevalencia_sintomas_depresivos_sexo.parquet`; 6 filas; columnas: `source_id, source_sheet, geography_level, geography, region_code, period, year, sex, indicator, value, value_text, unit`.
- Cobertura temporal: años 2003; períodos sin año único: 2009-10, 2016-17.
- Cobertura geográfica: niveles nacional; geografías Nacional.
- Categorías de sexo: Hombres, Mujeres. Indicadores: prevalencia_sintomas_depresivos_ultimo_ano. Unidades: %.
- Calidad: missing numérico 0; valores textuales publicados `{}`; duplicados por clave natural 0; rango numérico [9.10564014773908, 26.276993881646].

## Anomalías y limitaciones observadas

- El cuadro PHQ-4 declara 16.380 columnas en `NACIONAL`, aunque la tabla con contenido usa las columnas A:T; las columnas adicionales son una anomalía de estructura/formatación del XLSX. La normalización usa explícitamente A:T y no modifica el RAW.
- El título del cuadro de egresos por intentos suicidas declara años 2006–2024, pero sus filas de datos incluyen 2025. El EDA y el Parquet conservan la fila observada y documentan la discrepancia.
- En el cuadro regional de suicidio existe al menos un ratio publicado como símbolo `-`; se conserva en `value_text` y no se transforma en cero ni se imputa.
- Los cuadros nacionales no proporcionan desagregación regional; los períodos `2009-10`, `2016-17` y las rondas de Encuesta Social Covid-19 no se convierten a un año artificial.
- Las categorías `Total`, razones y brechas son medidas publicadas, no categorías de personas. Los indicadores se mantienen separados por fuente y no deben interpretarse como observaciones individuales ni vincularse a Egresos DEIS.

## Interpretación acotada

Los cuatro cuadros permiten contextualizar diferencias publicadas por sexo, con cobertura temporal y geográfica heterogénea. No es posible determinar asociaciones con duración de estadía ni con egresos individuales usando estos datos disponibles.
