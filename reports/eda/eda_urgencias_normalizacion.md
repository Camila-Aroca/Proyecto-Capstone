# Informe de Normalización y Filtrado Territorial
## Atenciones de Urgencia DEIS 2020–2026 (Región Metropolitana)

**Fuentes RAW:** `data/raw/urgencias/AtencionesUrgencia2020.csv` a `AtencionesUrgencia2026.csv`
**Destino Procesado:** `data/processed/urgencias/urgencias_rm_[2020-2026].parquet`
**Identificación del snapshot:** cada Parquet declara en su metadato `raw_sha256` el SHA256 del RAW procesado (resumen en la sección 2).

---

## 1. Fuentes Utilizadas

Se procesaron 7 archivos CSV anuales de atenciones de urgencia a nivel nacional del DEIS-MINSAL:
- `data/raw/urgencias/AtencionesUrgencia2020.csv`
- `data/raw/urgencias/AtencionesUrgencia2021.csv`
- `data/raw/urgencias/AtencionesUrgencia2022.csv`
- `data/raw/urgencias/AtencionesUrgencia2023.csv`
- `data/raw/urgencias/AtencionesUrgencia2024.csv`
- `data/raw/urgencias/AtencionesUrgencia2025.csv`
- `data/raw/urgencias/AtencionesUrgencia2026.csv`

Para la homologación territorial se utilizó el catálogo procesado de la RM:
- `data/processed/establecimientos_rm_clean.csv` (1,187 códigos de establecimiento únicos)
- `data/processed/establecimientos_salud_clean.parquet` (5,782 códigos de establecimiento únicos nacionales)

---

## 2. Encoding, Separador y Cobertura Temporal

- **Lectura:** `latin-1` con `errors="replace"` y separador punto y coma (`;`), según la configuración de la etapa.
- **Columna `CodigoRegion` en el RAW:** presente en [2023, 2024, 2025, 2026]; ausente en [2020, 2021, 2022] (en ese caso el territorio se obtiene del catálogo de establecimientos).

| Año | Fecha mínima (filas RM) | Fecha máxima (filas RM) | SHA256 del RAW |
|---:|---|---|---|
| 2020 | 01/01/2020 | 31/12/2020 | `51781f3fe2ef…` |
| 2021 | 01/01/2021 | 31/12/2021 | `c5fcdf2ad67a…` |
| 2022 | 01/01/2022 | 31/12/2022 | `e57c23479067…` |
| 2023 | 01/01/2023 | 31/12/2023 | `3f11f21f4d07…` |
| 2024 | 01/01/2024 | 31/12/2024 | `d6c93e7de79a…` |
| 2025 | 01/01/2025 | 31/12/2025 | `e37f91f02d55…` |
| 2026 | 01/01/2026 | 06/10/2026 | `c26ddb054460…` |

---

## 3. Esquema y Correspondencia de Columnas (RAW → PROCESSED)

| Nombre en RAW | Nombre Normalizado (`snake_case`) | Tipo de Dato |
|---|---|---|
| `fecha` | `fecha` | `string` (`DD/MM/YYYY`) |
| `(calculado)` | `ano` | `int32` |
| `semana` | `semana` | `int32` |
| `IdEstablecimiento` | `establecimiento_codigo` | `int64` (código nuevo DEIS, homologado con el catálogo) |
| `IdEstablecimiento` | `establecimiento_codigo_antiguo` | `string` |
| `NEstablecimiento` | `establecimiento_glosa` | `string` |
| `CodigoRegion` | `region_codigo` | `int32` (= 13) |
| `NombreRegion` | `region_glosa` | `string` (= 'Metropolitana de Santiago') |
| `CodigoComuna` | `comuna_codigo` | `string` |
| `NombreComuna` | `comuna_glosa` | `string` |
| `GLOSATIPOESTABLECIMIENTO` | `tipo_establecimiento_urgencia` | `string` |
| `GLOSATIPOATENCION` | `tipo_atencion_urgencia` | `string` |
| `GlosaTipoCampana` | `tipo_campana` | `string` |
| `IdCausa` | `id_causa` | `int32` |
| `GlosaCausa` | `glosa_causa` | `string` |
| `Total` | `total` | `int32` |
| `Menores_1` | `menores_1` | `int32` |
| `De_1_a_4` | `de_1_a_4` | `int32` |
| `De_5_a_14` | `de_5_a_14` | `int32` |
| `De_15_a_64` | `de_15_a_64` | `int32` |
| `De_65_y_mas` | `de_65_y_mas` | `int32` |
| `(catálogo)` | `latitud` | `float64` |
| `(catálogo)` | `longitud` | `float64` |

---

## 4. Transformaciones Realizadas

1. **Estandarización de nombres:** conversión a `snake_case`.
2. **Homologación de tipos:** columnas numéricas (`Total`, desgloses etarios, `semana`, `id_causa`) a `int32`; un valor vacío en esas columnas se lee como 0.
3. **Cruce territorial:** `IdEstablecimiento` se cruza contra `establecimiento_codigo_antiguo` y `establecimiento_codigo` de `data/processed/establecimientos_rm_clean.csv`; si no hay coincidencia se usa `CodigoRegion` del RAW cuando existe, y luego el catálogo nacional para descartar lo que no es RM.
4. **Filtro RM:** se conservan solo las filas con territorio RM.

---

## 5. Homologación Territorial y Filtrado RM

- **Registros con territorio determinado (RM o no RM):** 58,325,987 de 58,366,995 (99.9%).
- **Registros sin territorio determinado:** 41,008.

---

## 6. Tabla de Retención de Registros

| Año | Filas RAW | Filas RM | Filas no RM | Sin territorio | Filas PROCESSED (RM) | Territorio determinado (%) |
|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 6,446,646 | 1,720,000 | 4,714,838 | 11,808 | 1,720,000 | 99.8% |
| 2021 | 8,816,240 | 2,130,680 | 6,670,960 | 14,600 | 2,130,680 | 99.8% |
| 2022 | 8,926,307 | 2,140,040 | 6,771,667 | 14,600 | 2,140,040 | 99.8% |
| 2023 | 8,899,080 | 2,148,520 | 6,750,560 | 0 | 2,148,520 | 100.0% |
| 2024 | 8,973,229 | 2,141,400 | 6,831,829 | 0 | 2,141,400 | 100.0% |
| 2025 | 9,127,869 | 2,177,404 | 6,950,465 | 0 | 2,177,404 | 100.0% |
| 2026 | 7,177,624 | 1,704,042 | 5,473,582 | 0 | 1,704,042 | 100.0% |
| **TOTAL** | **58,366,995** | **14,162,086** | **44,163,901** | **41,008** | **14,162,086** | **99.9%** |

---

## 7. Controles Observados

Conteos calculados en esta ejecución. Esta etapa no verifica duplicados en el RAW ni la existencia de causas faltantes.

| Control | Registros |
|---|---:|
| Registros RAW sin `IdEstablecimiento` | 0 |
| Fechas distintas con formato distinto de `DD/MM/YYYY` (filas RM) | 0 |
| Filas RM con `semana` fuera de [1, 53] | 0 |
| Filas RM con `Total` negativo | 0 |
| Filas RM con `Total` distinto de la suma de grupos etarios | 0 |

---

## 8. Registros No Procesables o Sin Correspondencia

- **Registros sin territorio determinado:** 41,008.
- **Trazabilidad:** la diferencia entre `Filas RAW` y `Filas PROCESSED` (44,204,909) corresponde a los registros no RM (44,163,901) y a los sin territorio determinado (41,008).

---

## 9. Limitaciones

1. **Resolución temporal:** la serie de atenciones está agrupada a nivel diario y semanal por causa y grupo etario, no a nivel de transacción de paciente individual (datos ecológicos).
2. **Año en curso (2026):** el RAW es una fuente mutable; el último dato observado en este procesamiento es 06/10/2026 (ver sección 2). Su volumen no es comparable con el de años completos.
3. **Cambio de causas CIE:** las glosas y agrupaciones de causas del DEIS se auditarán y homologarán específicamente para salud mental (F00–F99) en la siguiente etapa analítica.
