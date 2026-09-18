# EDA — `mart_contexto_genero_indicador_sexo`

**Script reproducible:** `scripts/eda_mart_contexto_genero_indicador_sexo.py`
**Archivo analizado:** `data/processed/marts/mart_contexto_genero_indicador_sexo.parquet`

## 1. Forma y grano

- **3956 filas × 12 columnas.**
- Grano: una observación publicada de un indicador de contexto de salud mental por sexo, fuente, ámbito geográfico y período.
- La clave lógica `source_id, source_sheet, geography_level, geography, region_code, period, sex, indicator, unit` tiene 0 duplicados.

## 2. Reconciliación contra inputs processed

| `source_id` | Filas input | Filas mart | ¿Reconcilia? |
|---|---:|---:|---|
| `egresos_intento_suicida_sexo_anio` | 120 | 120 | Sí |
| `suicidio_ratio_hm_tasas_nacional_regional` | 3790 | 3790 | Sí |
| `ansiedad_depresion_sintomas_18_mas_sexo` | 40 | 40 | Sí |
| `prevalencia_sintomas_depresivos_sexo` | 6 | 6 | Sí |

- Reconciliación por fuente: **exacta**.
- Los cuatro `source_id` esperados están presentes; el mart no agrega ni elimina observaciones.

## 3. Temporalidad, ámbito y valores publicados

- Años numéricos observados: 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025.
- Fuentes con `year=NULL` preservado: `ansiedad_depresion_sintomas_18_mas_sexo`, `prevalencia_sintomas_depresivos_sexo`.
- `period` se conserva como texto publicado, incluidos `2009-10`, `2016-17` y las rondas PHQ-4; no se reconstruye una periodicidad común.
- Valores textuales publicados: `{'-': 7}`; el símbolo `-` permanece en `value_text`.
- Ámbitos geográficos observados: nacional, regional; no se fuerza cobertura comunal ni exclusiva RM.

## 4. Límites de uso

Este mart es **contexto interpretativo** para serving del MVP. No contiene FK, joins ni enriquecimiento con Urgencias o Egresos; coincidencias de sexo, año, período o territorio no habilitan relaciones automáticas. No se usa automáticamente como feature y no representa personas, pacientes ni episodios individuales.

## 5. Conclusión QA

El mart conserva el contrato normalizado de las cuatro fuentes y sus valores publicados, manteniendo sus diferencias semánticas en `source_id`, `period`, `year`, geografía, sexo, indicador y unidad.
