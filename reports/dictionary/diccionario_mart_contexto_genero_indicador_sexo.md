# Diccionario de datos: `mart_contexto_genero_indicador_sexo`

- **Ruta:** `data/processed/marts/mart_contexto_genero_indicador_sexo.parquet`.
- **Constructor:** `src/data/build_contexto_genero_mart.py`, stage
  `build_mart_contexto_genero_indicador_sexo` en `PIPELINE.md`.
- **Grano:** una fila = una observación publicada de un indicador de contexto
  de salud mental por sexo, fuente, ámbito geográfico y período.
- **Clave lógica verificada:** `source_id, source_sheet, geography_level,
  geography, region_code, period, sex, indicator, unit`. Tiene 0 duplicados
  sobre las 3.956 filas observadas. `region_code` puede ser nulo legítimamente
  en observaciones nacionales; el Parquet no añade una PK técnica.
- **Fuente / inputs:** los cuatro Parquet independientes de
  `data/processed/contexto_genero/`: `egresos_intento_suicida_sexo_anio`,
  `suicidio_ratio_hm_tasas_nacional_regional`,
  `ansiedad_depresion_sintomas_18_mas_sexo` y
  `prevalencia_sintomas_depresivos_sexo`.
- **Construcción:** concatenación determinista de esos cuatro contratos ya
  normalizados. No realiza joins, agregaciones, imputaciones, recodificación
  de sexo, homogeneización temporal ni enriquecimiento territorial.

## Columnas

| Columna | Tipo Parquet | Semántica |
|---|---|---|
| `source_id` | string | Identifica el contrato/fuente processed de origen; preserva sus semánticas heterogéneas. |
| `source_sheet` | string | Hoja XLSX de origen (`NACIONAL` o `REGIONAL`). |
| `geography_level` | string | Ámbito publicado: `nacional` o `regional`. |
| `geography` | string | Nombre de la geografía publicada. No equivale necesariamente a una comuna RM. |
| `region_code` | int32, nullable | Código regional publicado; nulo en filas nacionales. |
| `period` | string | Período publicado tal cual; no se fuerza a año. |
| `year` | int32, nullable | Año numérico solo cuando la fuente lo publica como año único. Es nulo para PHQ-4 y para períodos no anuales. |
| `sex` | string | Desagregación o medida publicada: puede incluir Hombres, Mujeres, Total, razón o brecha; no siempre representa una categoría de personas. |
| `indicator` | string | Nombre normalizado del indicador publicado. |
| `value` | float64, nullable | Valor numérico publicado; nulo cuando el valor publicado es texto. |
| `value_text` | string, nullable | Valor textual publicado, incluido el símbolo `-` de ratios regionales; nunca se convierte a cero o missing. |
| `unit` | string | Unidad publicada (`N`, `%`, `pp`, `razon`, `por_100000`). |

## Temporalidad y cobertura

- Egresos por intento suicida: nacional, años 2006–2025.
- Suicidio: nacional y regional, años 1997–2023.
- PHQ-4 ansiedad/depresión: nacional; rondas textuales de 2020–2021 con
  `year=NULL`.
- Síntomas depresivos: nacional; `period` conserva `2003`, `2009-10` y
  `2016-17`, con `year` únicamente para `2003`.

## Advertencias de interpretación

- Es un mart de **contexto interpretativo** para serving del MVP, no un
  mega-mart ni una tabla de features.
- No tiene FK ni join automático con Urgencias, Egresos, cartografía o el
  mart territorial. Coincidir en sexo, año, período o territorio no habilita
  una asociación automática.
- No representa personas, pacientes ni episodios individuales. Las categorías
  `Total`, razones y brechas son medidas publicadas.
- Ver `reports/eda/eda_mart_contexto_genero_indicador_sexo.md` para la
  reconciliación reproducible contra sus cuatro inputs.
