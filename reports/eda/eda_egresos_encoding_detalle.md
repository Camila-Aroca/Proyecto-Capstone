# Auditoría Técnica de Encoding y Mojibake en Egresos Hospitalarios 2024 y 2025

**Fecha de ejecución:** 2026-08-26  
**Archivos analizados:**
- `data/raw/egresos/EGR_DATOS_ABIERTO_2024.csv`
- `data/raw/egresos/EGR_DATOS_ABIERTO_2025.csv`

---

## 1. Resumen

Se llevó a cabo una auditoría a nivel de bytes sobre los archivos RAW de Egresos Hospitalarios 2024 y 2025 para determinar la naturaleza exacta de las anomalías de caracteres reportadas previamente:

- **Egresos 2024:** 1,667,349 registros totales. 746,224 registros (44.76%) contienen caracteres corruptos en al menos un campo de texto.
- **Egresos 2025:** 1,705,514 registros totales. 763,636 registros (44.77%) contienen caracteres corruptos en al menos un campo de texto.
- **Naturaleza del defecto:** El problema **no es un error de lectura o decodificación local**, sino que corresponde a texto grabado físicamente en origen con la secuencia UTF-8 `\xef\xbf\xbd` (el carácter Unicode de reemplazo `U+FFFD` / ``) por el DEIS/MINSAL antes de la publicación de los datos abiertos.
- **Alcance del impacto:** La corrupción se restringe estrictamente a **3 columnas de glosas de texto** (`GLOSA_COMUNA_RESIDENCIA`, `GLOSA_REGION_RESIDENCIA` y `GRUPO_EDAD`). Las variables críticas del sistema (códigos numéricos de comuna `COMUNA_RESIDENCIA`, códigos de región `REGION_RESIDENCIA`, diagnósticos CIE-10 `DIAG1`/`DIAG2` y `DIAS_ESTADA`) se encuentran **100% íntegras y no presentan alteración alguna**.

---

## 2. Egresos 2024 (`EGR_DATOS_ABIERTO_2024.csv`)

- **Encoding físico del archivo:** `UTF-8` (sin BOM).
- **Delimitador:** Punto y coma (`;`).
- **Total de registros (filas):** 1,667,349.
- **Total de columnas:** 16.
- **Registros afectados:** 746,224 filas (44.76%).
- **Columnas afectadas (3 de 16):**
  1. `GLOSA_COMUNA_RESIDENCIA`: 393,067 valores afectados en 80 comunas distintas.
  2. `GLOSA_REGION_RESIDENCIA`: 518,500 valores afectados en 8 regiones distintas.
  3. `GRUPO_EDAD`: 62,886 valores afectados en 2 categorías (`'menor de un ao'` y `'90 y ms'`).

---

## 3. Egresos 2025 (`EGR_DATOS_ABIERTO_2025.csv`)

- **Encoding físico del archivo:** `UTF-8` (sin BOM).
- **Delimitador:** Punto y coma (`;`).
- **Total de registros (filas):** 1,705,514.
- **Total de columnas:** 17 (incluye columna `ERROR`).
- **Registros afectados:** 763,636 filas (44.77%).
- **Columnas afectadas (3 de 17):**
  1. `GLOSA_COMUNA_RESIDENCIA`: 400,569 valores afectados en 79 comunas distintas.
  2. `GLOSA_REGION_RESIDENCIA`: 530,319 valores afectados en 8 regiones distintas.
  3. `GRUPO_EDAD`: 63,876 valores afectados en 2 categorías (`'menor de un ao'` y `'90 y ms'`).

---

## 4. Valores y Columnas Afectadas

A continuación se detallan los valores observados con mayor frecuencia en las 3 columnas afectadas:

| Columna | Valor Observado en RAW (2024–2025) | Valor Real / Oficial (Censo / SUBDERE) | Frecuencia 2024 | Frecuencia 2025 |
|---|---|---|---:|---:|
| `GLOSA_COMUNA_RESIDENCIA` | `'Maip'` | Maipú | 52,654 | 55,274 |
| `GLOSA_COMUNA_RESIDENCIA` | `'Via del Mar'` | Viña del Mar | 39,788 | 38,764 |
| `GLOSA_COMUNA_RESIDENCIA` | `'Valparaso'` | Valparaíso | 37,270 | 39,267 |
| `GLOSA_COMUNA_RESIDENCIA` | `'Concepcin'` | Concepción | 28,683 | 27,624 |
| `GLOSA_COMUNA_RESIDENCIA` | `'uoa'` | Ñuñoa | 18,310 | 18,041 |
| `GLOSA_COMUNA_RESIDENCIA` | `'Pealoln'` | Peñalolén | 17,914 | 18,228 |
| `GLOSA_COMUNA_RESIDENCIA` | `'Conchal'` | Conchalí | 16,846 | 17,046 |
| `GLOSA_REGION_RESIDENCIA` | `'Del Bobo'` | De Biobío | 180,683 | 184,817 |
| `GLOSA_REGION_RESIDENCIA` | `'De Valparaso'` | De Valparaíso | 170,165 | 173,174 |
| `GLOSA_REGION_RESIDENCIA` | `'De La Araucana'` | De La Araucanía | 81,993 | 84,334 |
| `GLOSA_REGION_RESIDENCIA` | `'De uble'` | De Ñuble | 46,903 | 47,816 |
| `GLOSA_REGION_RESIDENCIA` | `'De Los Ros'` | De Los Ríos | 38,409 | 40,178 |
| `GRUPO_EDAD` | `'menor de un ao'` | menor de un año | 36,013 | 36,547 |
| `GRUPO_EDAD` | `'90 y ms'` | 90 y más | 26,873 | 27,329 |

---

## 5. Registros Afectados e Identificadores Disponibles

Debido a que las bases de egresos hospitalarios se encuentran disociadas y anonimizadas por normativa de protección de datos personales, los registros se identifican unívocamente mediante la combinación de sus variables clínicas, temporales y de procedencia:

### Ejemplos Observados en 2024:
1. **Fila 2 (Maipú):**  
   - `ANO_EGRESO`: `2024`
   - `COMUNA_RESIDENCIA`: `'13119'` (Código CUT intacto)
   - `GLOSA_COMUNA_RESIDENCIA`: `'Maip'`
   - `REGION_RESIDENCIA`: `'13'`
   - `GLOSA_REGION_RESIDENCIA`: `'Metropolitana de Santiago'` (intacta)
   - `DIAG1`: `'I619'` | `DIAS_ESTADA`: `19` | `CONDICION_EGRESO`: `1`
2. **Fila 6 (Ñuñoa):**  
   - `ANO_EGRESO`: `2024`
   - `COMUNA_RESIDENCIA`: `'13120'` (Código CUT intacto)
   - `GLOSA_COMUNA_RESIDENCIA`: `'uoa'`
   - `REGION_RESIDENCIA`: `'13'`
   - `DIAG1`: `'C509'` | `DIAS_ESTADA`: `1` | `CONDICION_EGRESO`: `1`

---

## 6. Evidencia Encontrada

1. **Inspección de Bytes Crudos:**
   - La lectura en modo binario de las líneas correspondientes revela la secuencia literal:  
     `b'...;13119;Maip\xef\xbf\xbd;13;Metropolitana de Santiago;...'`
   - Los bytes `\xef\xbf\xbd` constituyen la representación exacta del carácter Unicode `U+FFFD` (*Replacement Character*).
2. **Validación Cruzada con Egresos 2020–2023:**
   - En los archivos RAW de 2020, 2021, 2022 y 2023 (codificados en `Latin-1`), las mismas comunas y grupos etarios contienen los bytes legítimos de tildes y eñes:
     - `Maipú` codificado con byte `0xFA` (`ú`).
     - `Ñuñoa` codificado con bytes `0xD1` (`Ñ`) y `0xF1` (`ñ`).
     - `'menor de un año'` codificado con `0xF1` (`ñ`).
3. **Consistencia de Identificadores Numéricos:**
   - El 100% de los registros con glosas corruptas conservan su código `COMUNA_RESIDENCIA` numérico válido (ej. `'13119'` para Maipú, `'13120'` para Ñuñoa).

---

## 7. Qué Puede Afirmarse con Certeza

1. **Hecho Observado 1:** El mojibake en Egresos 2024 y 2025 es **realmente observable y físico en los bytes de los archivos RAW descargados**, afectando al 44.76% (2024) y 44.77% (2025) de los registros.
2. **Hecho Observado 2:** El problema afecta exclusivamente a caracteres especiales (vocales con tilde y eñes) en 3 columnas descriptivas (`GLOSA_COMUNA_RESIDENCIA`, `GLOSA_REGION_RESIDENCIA`, `GRUPO_EDAD`).
3. **Hecho Observado 3:** Las columnas clínicas (`DIAG1`, `DIAG2`), de estadía (`DIAS_ESTADA`), previsión (`PREVISION`) y de localización numérica (`COMUNA_RESIDENCIA`, `REGION_RESIDENCIA`) **no tienen ninguna corrupción ni caracteres de reemplazo**.

---

## 8. Qué NO Puede Determinarse con los Datos Disponibles

1. **Causa del defecto en origen:** No es posible determinar con los datos disponibles qué software, base de datos o script ETL específico del MINSAL/DEIS generó la conversión destructiva a `\xef\xbf\xbd` al exportar los archivos de 2024 y 2025.
2. **Reversibilidad directa del byte:** Debido a que el carácter `\xef\xbf\xbd` es un reemplazo destructivo en el texto, no es posible reconstruir la letra original a partir del byte aislado sin recurrir a una tabla de homologación externa (como el código `COMUNA_RESIDENCIA`).

---

## 9. Recomendaciones para el Futuro Pipeline de Limpieza (`src/data/`)

1. **Filtrado Territorial Robusto por Código Numérico:** Para filtrar los egresos correspondientes a la Región Metropolitana o a comunas específicas, **utilizar siempre `REGION_RESIDENCIA == '13'` y `COMUNA_RESIDENCIA` (códigos CUT)**, evitando filtrar por las columnas de texto `GLOSA_...`.
2. **Homologación de Glosas desde Fuentes Oficiales:** Si se requiere visualizar o exportar los nombres de comunas en tablas procesadas, asignar la glosa correcta mediante un join con la cartografía comunal validada (`data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet`) a través del código `COMUNA_RESIDENCIA == CUT`.
3. **Estandarización de `GRUPO_EDAD`:** Normalizar las dos cadenas afectadas (`'menor de un ao'` $\rightarrow$ `'menor de 1 año'`, `'90 y ms'` $\rightarrow$ `'90 años o más'`) mediante reglas explícitas y documentadas durante la fase de transformación.
