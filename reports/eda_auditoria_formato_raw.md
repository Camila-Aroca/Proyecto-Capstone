# Informe de Auditoría Técnica de Formato y Calidad RAW
## Fuentes DEIS-MINSAL (Urgencias 2020–2026, Egresos 2020–2025) y Censo 2024

**Fecha de ejecución:** 2026-08-26  
**Fuentes auditadas:**
- Atenciones de Urgencia (7 CSVs): `data/raw/urgencias/`
- Egresos Hospitalarios (6 CSVs): `data/raw/egresos/`
- Cartografía Censo 2024 (GeoParquet): `data/raw/censo/Cartografia_censo2024_Pais_Comunal.parquet`

---

## 1. Resumen Ejecutivo

Se realizó una auditoría técnica profunda y a nivel de bytes sobre los 14 archivos de datos crudos (RAW) incorporados al proyecto, totalizando **66,674,950 registros**:
- **Atenciones de Urgencia:** 57,294,818 registros en 7 archivos anuales (2020–2026).
- **Egresos Hospitalarios:** 9,379,787 registros en 6 archivos anuales (2020–2025).
- **Censo 2024 (Comunal):** 345 registros vectoriales en formato GeoParquet.

### Principales Conclusiones:
1. **Integridad de Delimitadores:** El 100% de los CSV de Urgencias y Egresos utilizan delimitador punto y coma (`;`). **No se detectó ninguna fila desbalanceada ni con número incorrecto de campos** (0 filas erróneas en casi 64 millones de registros).
2. **Codificación Real:** 
   - En **Urgencias (2020–2026)**, todos los archivos están codificados legítimamente en `Latin-1 / CP1252` sin corrupción en bytes.
   - En **Egresos (2020–2023)**, están codificados en `Latin-1 / CP1252`.
   - En **Egresos (2024–2025)**, están codificados en `UTF-8`, pero presentan secuencias aisladas de mojibake preexistente de origen en glosas territoriales.
3. **Evolución Estructural:**
   - Urgencias cambió de 15 columnas (2020–2022) a 21 columnas (2023–2026), incorporando atributos territoriales explícitos en los datos recientes.
   - Egresos presenta variaciones de nombres de columnas y esquemas entre años (15 a 18 columnas).

---

## 2. Atenciones de Urgencia (2020–2026)

### 2.1 Tabla de Auditoría Técnica
| Año | Archivo | Tamaño (MB) | Registros | Cols | Encoding Real | Separador | Líneas Erradas | Mojibake Real |
|---:|---|---:|---:|---:|---|---|---:|---|
| 2020 | `AtencionesUrgencia2020.csv` | 759.34 | 6,446,646 | 15 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |
| 2021 | `AtencionesUrgencia2021.csv` | 1,078.45 | 8,816,240 | 15 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |
| 2022 | `AtencionesUrgencia2022.csv` | 1,091.74 | 8,926,307 | 15 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |
| 2023 | `AtencionesUrgencia2023.csv` | 1,524.77 | 8,899,080 | 21 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |
| 2024 | `AtencionesUrgencia2024.csv` | 1,534.38 | 8,973,229 | 21 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |
| 2025 | `AtencionesUrgencia2025.csv` | 1,865.79 | 9,142,479 | 21 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |
| 2026 | `AtencionesUrgencia2026.csv` | 1,251.03 | 6,090,837 | 21 | Latin-1 / CP1252 | `;` | 0 | No (Lectura limpia en Latin-1) |

### 2.2 Diagnóstico Estructural y Variables:
- **Columnas Comunes (15 columnas base):** `IdEstablecimiento`, `NEstablecimiento`, `IdCausa`, `GlosaCausa`, `Total`, `Menores_1`, `De_1_a_4`, `De_5_a_14`, `De_15_a_64`, `De_65_y_mas`, `fecha`, `semana`, `GLOSATIPOESTABLECIMIENTO`, `GLOSATIPOATENCION`, `GlosaTipoCampana`.
- **Columnas Incorporadas a partir de 2023 (+6 columnas):** `CodigoRegion`, `NombreRegion`, `CodigoDependencia`, `NombreDependencia`, `CodigoComuna`, `NombreComuna`.
- **Formato de Fechas:** Variable `fecha` estructurada como `DD/MM/YYYY` (ej. `01/01/2024`), y `semana` epidemiológica como entero (1 a 53).

---

## 3. Egresos Hospitalarios (2020–2025)

### 3.1 Tabla de Auditoría Técnica
| Año | Archivo | Tamaño (MB) | Registros | Cols | Encoding Real | Separador | Líneas Erradas | Mojibake Real |
|---:|---|---:|---:|---:|---|---|---:|---|
| 2020 | `EGRE_DATOS_ABIERTOS_2020.csv` | 234.58 | 1,330,477 | 18 | Latin-1 / CP1252 | `;` | 0 | No |
| 2021 | `EGR_DATOS_ABIERTO_2021.csv` | 209.33 | 1,467,062 | 15 | Latin-1 / CP1252 | `;` | 0 | No |
| 2022 | `EGRE_DATOS_ABIERTOS_2022.csv` | 341.36 | 1,597,118 | 18 | Latin-1 / CP1252 | `;` | 0 | No |
| 2023 | `EGRESOS_2023.csv` | 265.42 | 1,612,267 | 16 | Latin-1 / CP1252 | `;` | 0 | No |
| 2024 | `EGR_DATOS_ABIERTO_2024.csv` | 277.69 | 1,667,349 | 16 | UTF-8 | `;` | 0 | Sí (secuencias residuales de origen) |
| 2025 | `EGR_DATOS_ABIERTO_2025.csv` | 288.65 | 1,705,514 | 17 | UTF-8 | `;` | 0 | Sí (secuencias residuales de origen) |

### 3.2 Diagnóstico Estructural y Variables:
- **Variables Clave Presentes en Todos los Años:** `PERTENENCIA_ESTABLECIMIENTO_SALUD` (o `PERTENENCIA_ESTABLECIMIENTO_SALU`), `SEXO`, `GRUPO_EDAD`, `COMUNA_RESIDENCIA`, `GLOSA_COMUNA_RESIDENCIA`, `REGION_RESIDENCIA`, `GLOSA_REGION_RESIDENCIA`, `PREVISION`, `GLOSA_PREVISION`, `ANO_EGRESO`, `DIAG1`, `DIAG2`, `DIAS_ESTADA`, `CONDICION_EGRESO`.
- **Divergencias Observadas:**
  - Nombres de archivo no estandarizados en origen por DEIS.
  - Nombre truncado de columna: `PERTENENCIA_ESTABLECIMIENTO_SALU` en 2023, 2024 y 2025 vs `PERTENENCIA_ESTABLECIMIENTO_SALUD` en 2020, 2021 y 2022.
  - Variable `SEXO`: Codificada como entero (`1`, `2`) en 2021 vs texto (`'HOMBRE'`, `'MUJER'`) en los demás años.
  - Columnas quirúrgicas: `INTERV_Q` y `PROCED` en 2020; `GLOSA_INTERV_Q_PPAL` y `GLOSA_PROCED_PPAL` en 2022; ausentes en 2021, 2023, 2024 y 2025.
  - Columna adicional `ERROR` presente exclusivamente en 2025.

---

## 4. Cartografía Censo 2024

| Archivo | Registros | Columnas | CRS | Geometría | Nulos / Inválidos | Texto / Encoding |
|---|---:|---:|---|---|---|---|
| `Cartografia_censo2024_Pais_Comunal.parquet` | 345 | 11 | SIRGAS 2000 (`EPSG:4674`) | `MultiPolygon` (WKB) | 0 nulos / 0 inválidos | UTF-8 nativo limpio (sin mojibake) |

---

## 5. Comparación Transversal Entre Años

### Atenciones de Urgencia
| Año | Filas | Columnas | Encoding | Separador | Mojibake | Problemas |
|---|---:|---:|---|---|---|---|
| 2020 | 6,446,646 | 15 | Latin-1 | `;` | No | Sin columnas comunales directas (requiere cruce con DEIS) |
| 2021 | 8,816,240 | 15 | Latin-1 | `;` | No | Sin columnas comunales directas (requiere cruce con DEIS) |
| 2022 | 8,926,307 | 15 | Latin-1 | `;` | No | Sin columnas comunales directas (requiere cruce con DEIS) |
| 2023 | 8,899,080 | 21 | Latin-1 | `;` | No | Ninguno |
| 2024 | 8,973,229 | 21 | Latin-1 | `;` | No | Ninguno |
| 2025 | 9,142,479 | 21 | Latin-1 | `;` | No | Ninguno |
| 2026 | 6,090,837 | 21 | Latin-1 | `;` | No | Ninguno |

### Egresos Hospitalarios
| Año | Filas | Columnas | Encoding | Separador | Mojibake | Problemas |
|---|---:|---:|---|---|---|---|
| 2020 | 1,330,477 | 18 | Latin-1 | `;` | No | Contiene columnas de procedimientos específicas |
| 2021 | 1,467,062 | 15 | Latin-1 | `;` | No | `SEXO` codificado como 1/2 en vez de texto; sin etnia |
| 2022 | 1,597,118 | 18 | Latin-1 | `;` | No | Columnas de procedimientos con nombres glosados |
| 2023 | 1,612,267 | 16 | Latin-1 | `;` | No | Columna de pertenencia truncada a 32 caracteres |
| 2024 | 1,667,349 | 16 | UTF-8 | `;` | Sí (residual) | Cambio de encoding a UTF-8 y glosas con mojibake de origen |
| 2025 | 1,705,514 | 17 | UTF-8 | `;` | Sí (residual) | Cambio de encoding a UTF-8 y columna `ERROR` adicional |

---

## 6. Problemas Reales Encontrados

1. **Heterogeneidad de Encoding en Egresos:** Egresos 2020–2023 utiliza Latin-1, mientras que 2024–2025 utiliza UTF-8. El pipeline de lectura en `src/data/` debe aplicar el encoding de forma dinámica según el año.
2. **Mojibake Residual en Egresos 2024–2025:** Ciertas glosas de comunas (ej. comunas con tildes como *Hualaihué* o *Conchalí*) fueron grabadas con caracteres corruptos en las bases de datos abiertas del MINSAL antes de exportar el CSV.
3. **Discrepancia Estructural en Urgencias (2020–2022 vs 2023–2026):** Los primeros 3 años no contienen las columnas `CodigoComuna`, `NombreComuna`, `CodigoRegion`. Deben enlazarse con el catálogo de establecimientos mediante `IdEstablecimiento` para filtrar la RM.
4. **Nombres de Columnas No Estandarizados en Egresos:** Nombres truncados (`PERTENENCIA_ESTABLECIMIENTO_SALU`) y cambios de tipado en `SEXO` (numérico vs string).

---

## 7. Problemas que son Únicamente de Visualización

1. **Mojibake en Terminales / Visores de Urgencias:** Al visualizar los archivos de Urgencias en terminales configuradas en UTF-8 o editores que asumen UTF-8 por defecto, aparecen caracteres como `AtenciÃ³n` o `SecciÃ³n`. **El archivo no está corrupto**: al leer con `encoding='latin-1'` (o `'cp1252'`), todos los textos se decodifican de forma 100% limpia.
2. **Visualización de Separadores:** Al abrir los CSV con delimitador `;` en herramientas que asumen comas por defecto, los datos se despliegan como una sola columna. Especificando `sep=';'`, la matriz de datos se interpreta perfectamente.

---

## 8. Recomendaciones para la Etapa de Limpieza y Procesamiento (`src/data/`)

1. **Estandarización de Nombres (`snake_case`):** Normalizar nombres de columnas a minúsculas y unificar nombres truncados (ej. `pertenencia_establecimiento_salud`).
2. **Mapeo Territorial de Urgencias 2020–2022:** Usar `data/processed/establecimientos_rm_clean.csv` para homologar `IdEstablecimiento` y asignar comuna y región a las series históricas de urgencia.
3. **Unificación de Egresos:** Estandarizar la columna `sexo` a formato categórico uniforme y seleccionar el subconjunto común de variables clínicas y de estadía para el análisis de salud mental (F00–F99).
