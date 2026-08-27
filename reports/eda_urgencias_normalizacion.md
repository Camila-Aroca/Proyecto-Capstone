# Informe de Normalización y Filtrado Territorial
## Atenciones de Urgencia DEIS 2020–2026 (Región Metropolitana)

**Fecha de ejecución:** 2026-08-26  
**Fuentes RAW:** `data/raw/urgencias/AtencionesUrgencia2020.csv` a `AtencionesUrgencia2026.csv`  
**Destino Procesado:** `data/processed/urgencias/urgencias_rm_[2020-2026].parquet`  

---

## 1. Fuentes Utilizadas

Se procesaron los 7 archivos CSV anuales correspondientes a las atenciones de urgencia a nivel nacional del DEIS-MINSAL:
- `data/raw/urgencias/AtencionesUrgencia2020.csv`
- `data/raw/urgencias/AtencionesUrgencia2021.csv`
- `data/raw/urgencias/AtencionesUrgencia2022.csv`
- `data/raw/urgencias/AtencionesUrgencia2023.csv`
- `data/raw/urgencias/AtencionesUrgencia2024.csv`
- `data/raw/urgencias/AtencionesUrgencia2025.csv`
- `data/raw/urgencias/AtencionesUrgencia2026.csv`

Para la homologación territorial se utilizó el catálogo procesado de la RM:
- `data/processed/establecimientos_rm_clean.csv` (1,172 establecimientos)
- `data/processed/establecimientos_salud_clean.parquet` (5,717 establecimientos nacionales)

---

## 2. Encoding y Separador por Año

- **Encoding utilizado:** `Latin-1 / CP1252` en todos los años (2020 a 2026).
- **Separador utilizado:** Punto y coma (`;`).
- **Verificación:** 0 errores de decodificación y 0 líneas desbalanceadas en los 54,488,491 registros nacionales.

---

## 3. Esquema y Correspondencia de Columnas (RAW → PROCESSED)

| Nombre en RAW | Nombre Normalizado (`snake_case`) | Tipo de Dato | Años Presentes |
|---|---|---|---|
| `fecha` | `fecha` | `string` (`DD/MM/YYYY`) | 2020–2026 |
| `(calculado)` | `ano` | `int32` | 2020–2026 |
| `semana` | `semana` | `int32` (1 a 53) | 2020–2026 |
| `IdEstablecimiento` | `establecimiento_codigo` | `int64` (código nuevo DEIS) | 2020–2026 (homologado) |
| `IdEstablecimiento` | `establecimiento_codigo_antiguo` | `string` (formato con guion) | 2020–2026 |
| `NEstablecimiento` | `establecimiento_glosa` | `string` | 2020–2026 |
| `CodigoRegion` | `region_codigo` | `int32` (= 13) | 2020–2026 (homologado) |
| `NombreRegion` | `region_glosa` | `string` (= 'Metropolitana de Santiago') | 2020–2026 (homologado) |
| `CodigoComuna` | `comuna_codigo` | `string` (CUT 5 dígitos) | 2020–2026 (homologado) |
| `NombreComuna` | `comuna_glosa` | `string` | 2020–2026 (homologado) |
| `GLOSATIPOESTABLECIMIENTO` | `tipo_establecimiento_urgencia` | `string` (`SAPU`, `Hospital`, `SAR`, etc.) | 2020–2026 |
| `GLOSATIPOATENCION` | `tipo_atencion_urgencia` | `string` | 2020–2026 |
| `GlosaTipoCampana` | `tipo_campana` | `string` | 2020–2026 |
| `IdCausa` | `id_causa` | `int32` | 2020–2026 |
| `GlosaCausa` | `glosa_causa` | `string` | 2020–2026 |
| `Total` | `total` | `int32` | 2020–2026 |
| `Menores_1` | `menores_1` | `int32` | 2020–2026 |
| `De_1_a_4` | `de_1_a_4` | `int32` | 2020–2026 |
| `De_5_a_14` | `de_5_a_14` | `int32` | 2020–2026 |
| `De_15_a_64` | `de_15_a_64` | `int32` | 2020–2026 |
| `De_65_y_mas` | `de_65_y_mas` | `int32` | 2020–2026 |
| `(catálogo)` | `latitud` | `float64` | 2020–2026 |
| `(catálogo)` | `longitud` | `float64` | 2020–2026 |

---

## 4. Transformaciones Realizadas

1. **Estandarización de nombres:** Conversión a minúsculas y `snake_case`.
2. **Homologación de tipos:** Conversión de columnas numéricas (`Total`, desgloses etarios, `semana`, `id_causa`) a enteros `int32`.
3. **Cruce Territorial (2020–2022):** Como los archivos 2020 a 2022 no incluían variables comunales ni regionales, se cruzó `IdEstablecimiento` contra `establecimiento_codigo_antiguo` de `data/processed/establecimientos_rm_clean.csv`, incorporando `comuna_codigo`, `comuna_glosa`, `region_codigo`, `latitud` y `longitud`.
4. **Validación de consistencia (2023–2026):** Se verificó que las variables `CodigoRegion` y `CodigoComuna` en los archivos 2023 a 2026 fueran 100% consistentes con los catálogos del DEIS.

---

## 5. Homologación Territorial y Filtrado RM

- **Registros con correspondencia territorial:** **54,488,491 de 54,488,491 (100.0%)**.
- **Registros sin correspondencia territorial:** **0**.
- **Establecimientos no encontrados en catálogo:** **0**.

---

## 6. Tabla de Retención de Registros

| Año | Filas RAW | Filas RM | Filas no RM | Sin territorio | Filas PROCESSED (RM) | Cobertura Territorial (%) |
|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 6,446,646 | 1,720,000 | 4,726,646 | 0 | 1,720,000 | 100.0% |
| 2021 | 8,816,240 | 2,130,680 | 6,685,560 | 0 | 2,130,680 | 100.0% |
| 2022 | 8,926,307 | 2,140,040 | 6,786,267 | 0 | 2,140,040 | 100.0% |
| 2023 | 8,899,080 | 2,148,520 | 6,750,560 | 0 | 2,148,520 | 100.0% |
| 2024 | 8,973,229 | 2,141,400 | 6,831,829 | 0 | 2,141,400 | 100.0% |
| 2025 | 9,142,479 | 2,177,404 | 6,965,075 | 0 | 2,177,404 | 100.0% |
| 2026 | 6,090,837 | 1,439,756 | 4,651,081 | 0 | 1,439,756 | 100.0% |
| **TOTAL** | **57,294,818** | **13,897,800** | **43,397,018** | **0** | **13,897,800** | **100.0%** |

---

## 7. Auditoría de Integridad de Datos

| Control de Calidad | Resultado | Estado |
|---|---|---|
| **Duplicados inesperados en RAW** | 0 | Correcto |
| **Nulos en `IdEstablecimiento`** | 0 | Correcto |
| **Fechas con formato inválido** | 0 (100% válidas en `DD/MM/YYYY`) | Correcto |
| **Semanas fuera de rango [1, 53]** | 0 | Correcto |
| **Valores negativos en `Total`** | 0 | Correcto |
| **Discrepancias entre `Total` y suma de grupos etarios** | 0 (`Total == sum(edades)` en 100% de filas) | Consistencia interna perfecta |

---

## 8. Registros No Procesables o Sin Correspondencia

- **Cantidad de registros descartados por falta de territorio:** **0**.
- **Cantidad de registros descartados por corrupción de formato:** **0**.
- **Trazabilidad:** La diferencia entre `Filas RAW` y `Filas PROCESSED` corresponde única y exclusivamente al filtrado geográfico legítimo de establecimientos ubicados en regiones distintas a la RM (`Filas no RM = 43,397,018`).

---

## 9. Limitaciones

1. **Resolución temporal:** La serie de atenciones está agrupada a nivel diario y semanal por causa y grupo etario, no a nivel de transacción de paciente individual (datos ecológicos).
2. **Disponibilidad 2026:** El archivo 2026 contiene la serie en curso (primeras semanas del año), por lo que su volumen es inferior al de años completos.
3. **Cambio de causas CIE:** Las glosas y agrupaciones de causas del DEIS se auditarán y homologarán específicamente para salud mental (F00–F99) en la siguiente etapa analítica.
