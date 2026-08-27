# Informe de Validación Post-Normalización
## Atenciones de Urgencia DEIS 2020–2026 (Región Metropolitana)

**Fecha de ejecución:** 2026-08-26  
**Fuentes auditadas:**
- RAW: `data/raw/urgencias/AtencionesUrgencia[2020-2026].csv`
- PROCESSED: `data/processed/urgencias/urgencias_rm_[2020-2026].parquet`
- Catálogo de Establecimientos: `data/processed/establecimientos_rm_clean.csv`

---

## 1. Resumen Ejecutivo y Veredicto de Aptitud

Se realizó una auditoría técnica integral e independiente sobre los 7 datasets procesados de Atenciones de Urgencia para la Región Metropolitana (`data/processed/urgencias/`), validando conteos, integridad referencial, consistencia de esquemas y ausencia de duplicados:

- **Total de registros nacionales RAW (2020–2026):** **57,294,818 filas**.
- **Total de registros filtrados y procesados para la RM:** **13,897,800 filas**.
- **Registros perdidos por errores técnicos o falta de correspondencia:** **0**.
- **Duplicados introducidos en joins:** **0**.
- **Consistencia interna (Suma de grupos etarios vs Total):** **100.0% perfecta (0 discrepancias)**.
- **Consistencia de esquemas:** **100.0% homogéneo (24 columnas idénticas en tipo y orden)**.

### Veredicto: **APTO**
El dataset procesado de Atenciones de Urgencia de la Región Metropolitana cumple con todos los estándares de rigor técnico, trazabilidad y consistencia para iniciar la fase de perfilado y análisis de causas de salud mental (F00–F99).

---

## 2. Validación de Conteos y Aclaración de Discrepancias

### 2.1 Tabla de Conteos Reales vs Declarados

| Año | RAW Real (Disco) | RAW Reportado (Auditoría RAW) | RAW Reportado (Normalización) | PROCESSED Real (RM) | RM Reportado | Diferencia |
|---:|---:|---:|---:|---:|---:|---:|
| **2020** | 6,446,646 | 6,446,646 | 6,446,646 | 1,720,000 | 1,720,000 | 0 |
| **2021** | 8,816,240 | 8,816,240 | 8,816,240 | 2,130,680 | 2,130,680 | 0 |
| **2022** | 8,926,307 | 8,926,307 | 8,926,307 | 2,140,040 | 2,140,040 | 0 |
| **2023** | 8,899,080 | 8,899,080 | 8,899,080 | 2,148,520 | 2,148,520 | 0 |
| **2024** | 8,973,229 | 8,973,229 | 8,973,229 | 2,141,400 | 2,141,400 | 0 |
| **2025** | 9,142,479 | 9,142,479 | 9,142,479 | 2,177,404 | 2,177,404 | 0 |
| **2026** | 6,090,837 | 6,090,837 | 6,090,837 | 1,439,756 | 1,439,756 | 0 |
| **TOTAL** | **57,294,818** | **57,294,818 (Tabla)** / *54,488,491 (Texto)* | **57,294,818** | **13,897,800** | **13,897,800** | **0** |

### 2.2 Diagnóstico de la Discrepancia Observada
- **Hecho Observado:** El archivo `reports/eda_auditoria_formato_raw.md` presentaba en la tabla de la Sección 2.1 exactamente los mismos conteos anuales cuya suma aritmética da **57,294,818**. Sin embargo, en el texto introductorio de la Sección 1 figuraba la cifra `54,488,491` producto de un error tipográfico en la redacción del resumen.
- **Conclusión:** La cifra real, verificada directamente mediante conteo de líneas de los 7 archivos CSV en disco, es **57,294,818 registros RAW nacionales**.

---

## 3. Trazabilidad y Homologación Territorial (Join 1:1)

### 3.1 Auditoría del Cruce en Series Históricas (2020–2022)
En los años 2020, 2021 y 2022, los datos RAW no incluían columnas comunales ni regionales directas. El cruce territorial se realizó mediante `IdEstablecimiento` $\rightarrow$ `establecimiento_codigo_antiguo`:

- **Unicidad en catálogo RM:** Se auditó `data/processed/establecimientos_rm_clean.csv` verificando que existen 908 códigos antiguos no nulos y **0 códigos antiguos duplicados**.
- **Cardinalidad del Join:** El cruce es **estrictamente 1:1**.
- **Duplicación inducida por join:** **0 registros**.
- **Establecimientos RAW sin correspondencia:** **0**.
- **Registros RAW con pérdida territorial:** **0**.

### 3.2 Consistencia Territorial en Series Recientes (2023–2026)
- El 100% de los registros filtrados en 2023–2026 contienen `CodigoRegion == '13'`, correspondiente a la Región Metropolitana de Santiago.
- La variable `CodigoComuna` coincide exactamente con los códigos CUT del Censo 2024 y con la comuna de procedencia del establecimiento en el catálogo DEIS.

---

## 4. Auditoría de Calidad y Validación de Valores

Se ejecutaron pruebas exhaustivas sobre las **13,897,800 filas** procesadas en Parquet:

| Control de Calidad | Resultado | Estado |
|---|---:|---|
| **Nulos en `establecimiento_codigo`** | 0 | Conforme |
| **Nulos en `comuna_codigo`** | 0 | Conforme |
| **Nulos en `region_codigo`** | 0 | Conforme |
| **Nulos en `fecha`** | 0 | Conforme |
| **Nulos en `id_causa`** | 0 | Conforme |
| **Valores negativos en `total`** | 0 | Conforme |
| **Valores negativos en grupos etarios** | 0 | Conforme |
| **Semanas fuera de rango [1, 53]** | 0 | Conforme |
| **Fechas con formato inválido (distinto a `DD/MM/YYYY`)** | 0 | Conforme |
| **Discrepancias entre `total` y suma de edades** | 0 | Conforme (100% de filas consistentes) |

---

## 5. Granularidad Natural y Validación de Duplicados

- **Granularidad natural de la fuente:** La combinación de las variables:
  `[fecha, establecimiento_codigo, id_causa, tipo_atencion_urgencia, tipo_campana, tipo_establecimiento_urgencia]`
  constituye la llave natural unívoca del registro diario agregado de urgencias.
- **Duplicados exactos en todas las columnas:** **0 registros**.
- **Duplicados en llave natural:** **0 registros**.

---

## 6. Homogeneidad del Esquema Parquet (2020–2026)

Los 7 archivos Parquet generados en `data/processed/urgencias/` presentan una estructura 100% idéntica:

| # | Nombre de Columna | Tipo PyArrow | Años Presentes |
|---:|---|---|---|
| 1 | `fecha` | `string` (`DD/MM/YYYY`) | 2020–2026 |
| 2 | `ano` | `int32` | 2020–2026 |
| 3 | `semana` | `int32` | 2020–2026 |
| 4 | `establecimiento_codigo` | `int64` | 2020–2026 |
| 5 | `establecimiento_codigo_antiguo` | `string` | 2020–2026 |
| 6 | `establecimiento_glosa` | `string` | 2020–2026 |
| 7 | `region_codigo` | `int32` (= 13) | 2020–2026 |
| 8 | `region_glosa` | `string` (= 'Metropolitana de Santiago') | 2020–2026 |
| 9 | `comuna_codigo` | `string` (CUT 5 dígitos) | 2020–2026 |
| 10 | `comuna_glosa` | `string` | 2020–2026 |
| 11 | `tipo_establecimiento_glosa` | `string` | 2020–2026 |
| 12 | `tipo_establecimiento_urgencia` | `string` | 2020–2026 |
| 13 | `tipo_atencion_urgencia` | `string` | 2020–2026 |
| 14 | `tipo_campana` | `string` | 2020–2026 |
| 15 | `id_causa` | `int32` | 2020–2026 |
| 16 | `glosa_causa` | `string` | 2020–2026 |
| 17 | `total` | `int32` | 2020–2026 |
| 18 | `menores_1` | `int32` | 2020–2026 |
| 19 | `de_1_a_4` | `int32` | 2020–2026 |
| 20 | `de_5_a_14` | `int32` | 2020–2026 |
| 21 | `de_15_a_64` | `int32` | 2020–2026 |
| 22 | `de_65_y_mas` | `int32` | 2020–2026 |
| 23 | `latitud` | `float64` | 2020–2026 |
| 24 | `longitud` | `float64` | 2020–2026 |

---

## 7. Tabla de Correspondencia y Justificación de Transformaciones

| Variable RAW | Variable Normalizada | Transformación Aplicada | Justificación y Evidencia |
|---|---|---|---|
| `IdEstablecimiento` | `establecimiento_codigo` | Mapeo al código nuevo único DEIS vía catálogo oficial | Permite enlazar con capas geoespaciales y egresos hospitalarios. |
| `IdEstablecimiento` | `establecimiento_codigo_antiguo` | Conservación del código con guion original | Preserva la trazabilidad directa con la fuente RAW. |
| `NEstablecimiento` | `establecimiento_glosa` | Limpieza de espacios y estandarización | Unifica nombres descriptivos del centro de salud. |
| `(no existía 2020–2022)` | `comuna_codigo` / `region_codigo` | Asignación desde catálogo DEIS validado | Homogeneiza la serie territorial transversal 2020–2026. |
| `Total`, `Menores_1`, etc. | `total`, `menores_1`, ... | Conversión a `int32` | Optimiza memoria y almacenamiento, garantizando operaciones aritméticas exactas. |
| `semana` | `semana` | Conversión a `int32` | Normaliza el índice de semana epidemiológica. |
| `(calculado)` | `ano` | Extracción del año del dataset | Facilita particionamiento y consultas temporales eficientes. |

---

## 8. Respuestas a las Preguntas de Control

1. **¿Los conteos RAW son correctos?:** Sí, el volumen nacional verificado en disco es de **57,294,818 registros**.
2. **¿Existe alguna discrepancia con informes anteriores?:** Sí. Se detectó y aclaró una discrepancia de redacción en el texto de `reports/eda_auditoria_formato_raw.md` (que citaba 54,488,491 pero cuya tabla detallada sumaba 57,294,818).
3. **¿La cantidad de registros RM es reproducible?:** Sí, exactamente **13,897,800 registros**.
4. **¿El join territorial es 1:1 donde corresponde?:** Sí, 1:1 exacto sin colisiones ni multiplicaciones.
5. **¿Se introdujeron duplicados?:** No (0 duplicados).
6. **¿Se perdió algún registro por problemas técnicos?:** No (0 registros perdidos).
7. **¿Los datasets procesados tienen esquema consistente?:** Sí, 100% consistente y tipado en 24 columnas.
8. **¿Qué anomalías permanecen?:** Ninguna anomalía estructural ni de formato en las series de urgencia procesadas.
9. **¿El dataset está listo para comenzar el análisis F00–F99?:** **SÍ, ESTADO APTO**.
