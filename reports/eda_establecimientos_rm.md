# Informe de Validación de Integridad y Análisis Exploratorio (EDA)
## Dataset de Establecimientos de Salud - Región Metropolitana (DEIS)

**Fecha de ejecución:** 2026-08-26  
**Fuentes analizadas:**
- **RAW:** `data/raw/deis/establecimientos_salud_actualizado.csv`
- **CLEAN:** `data/processed/establecimientos_rm_clean.csv`
- **Auxiliar Coordenadas Faltantes:** `reports/eda/registros_sin_coordenadas.csv`

---

## 1. Resumen Ejecutivo

El presente informe audita y valida la integridad de la transformación del dataset crudo nacional del DEIS (`establecimientos_salud_actualizado.csv`) hacia el dataset procesado de la Región Metropolitana (`establecimientos_rm_clean.csv`).

- **Total registros RAW:** 5,717 filas y 33 columnas.
- **Total registros RAW pertenecientes a RM:** 1,172 filas.
- **Total registros en CLEAN:** 1,172 filas y 33 columnas.
- **Registros de RM perdidos:** **0** (100% de retención).
- **Pureza territorial:** **100.0%** de los registros en CLEAN pertenecen unívocamente a la Región Metropolitana (`region_codigo = 13`).
- **Integridad de Clave Primaria:** **0** duplicados en `establecimiento_codigo`.

---

## 2. Comparativa RAW vs. RAW-RM vs. CLEAN

| Métrica | RAW Nacional | RAW Región Metropolitana | CLEAN Procesado | Diferencia (RAW-RM vs CLEAN) |
|---|---|---|---|---|
| **Número de filas** | 5,717 | 1,172 | 1,172 | 0 |
| **Número de columnas** | 33 | 33 | 33 | 0 (nombres normalizados a `snake_case`) |
| **Claves únicas (`establecimiento_codigo`)** | 5,717 | 1,172 | 1,172 | 0 |
| **Registros RM omitidos** | - | - | **0** | - |
| **Registros externos incorporados** | - | - | **0** | - |

**Conclusión de Integridad:** Se comprueba matemáticamente que no hubo pérdida ni inserción espuria de registros durante el proceso de extracción, tipado y limpieza.

---

## 3. Validación Territorial

- **Valores únicos de `region_codigo` en CLEAN:** `[13]` (100% = 13).
- **Valores únicos de `region_glosa` en CLEAN:** `['Metropolitana de Santiago']` (100% = "Metropolitana de Santiago").
- **Comprobación de correspondencia:** En el archivo RAW, la correspondencia entre `RegionCodigo == '13'` y `RegionGlosa == 'Metropolitana de Santiago'` es perfecta (0 discrepancias).

> **Dictamen Territorial:** **El 100% del archivo CLEAN corresponde exclusivamente a la Región Metropolitana.**

---

## 4. Análisis Exploratorio de Datos (EDA)

### 4.1 Distribución Comunal (Top 10 Comunas)
| Comuna | Cantidad Establecimientos | Porcentaje (%) |
|---|---|---|
| Providencia | 126 | 10.75% |
| Santiago | 111 | 9.47% |
| Las Condes | 63 | 5.38% |
| Maipú | 53 | 4.52% |
| Puente Alto | 51 | 4.35% |
| La Florida | 46 | 3.92% |
| San Bernardo | 44 | 3.75% |
| Ñuñoa | 41 | 3.50% |
| San Miguel | 33 | 2.82% |
| Pudahuel | 30 | 2.56% |

### 4.2 Tipo de Establecimiento
| Tipo de Establecimiento | Frecuencia | Porcentaje (%) |
|---|---|---|
| Centro de Salud Privado | 262 | 22.35% |
| Centro de Salud Familiar (CESFAM) | 174 | 14.85% |
| Clínica | 108 | 9.22% |
| Servicio de Atención Primaria de Urgencia (SAPU) | 105 | 8.96% |
| Centro Comunitario de Salud Familiar (CECOSF) | 74 | 6.31% |
| Clínica Dental | 66 | 5.63% |
| Laboratorio Clínico | 64 | 5.46% |
| Posta de Salud Rural (PSR) | 51 | 4.35% |

### 4.3 Tipo de Sistema de Salud y Complejidad
| Sistema de Salud | Frecuencia | Porcentaje (%) |
|---|---|---|
| Público | 567 | 48.38% |
| Privado | 561 | 47.87% |
| Fuerzas Armadas y de Orden | 25 | 2.13% |
| nan | 19 | 1.62% |

| Nivel de Complejidad | Frecuencia | Porcentaje (%) |
|---|---|---|
| Baja Complejidad | 578 | 49.32% |
| Mediana Complejidad | 364 | 31.06% |
| Nulo / No informado | 173 | 14.76% |
| Alta Complejidad | 57 | 4.86% |

### 4.4 Servicios de Urgencia en RM
- **Establecimientos con Servicio de Urgencia (`tiene_servicio_urgencia = 'SI'`):** 197 (16.8%)
- **Establecimientos sin Urgencia (`tiene_servicio_urgencia = 'NO'`):** 943 (80.5%)

---

## 5. Calidad de Datos y Diagnóstico de Georreferenciación

### 5.1 Controles Generales de Integridad
| Control de Calidad | Resultado | Estado |
|---|---|---|
| **Filas duplicadas exactas** | 0 | Correcto |
| **Duplicados en `establecimiento_codigo`** | 0 | Correcto |
| **Nulos en `establecimiento_codigo`** | 0 | Correcto |
| **Inconsistencias `comuna_codigo` vs `comuna_glosa`** | 0 | Consistente (1 a 1) |
| **Coordenadas válidas (`latitud`, `longitud`)** | 1076 (91.8%) | Cobertura geoespacial alta |
| **Total registros con coordenadas faltantes** | **96** (8.2%) | Auditado detalladamente abajo |

### 5.2 Desglose Específico de Coordenadas Faltantes
- **Total de registros afectados:** **96**
- **Registros con ambas coordenadas faltantes (`latitud` y `longitud` nulas):** **96**
- **Registros con solo `latitud` faltante:** **0**
- **Registros con solo `longitud` faltante:** **0**
- **Archivo exportado con el detalle completo:** [`registros_sin_coordenadas.csv`](eda/registros_sin_coordenadas.csv) (ruta relativa: `reports/eda/registros_sin_coordenadas.csv`)

#### Desglose por Estado de Funcionamiento:
- **Cerrado:** 87 registros (90.6% de los que carecen de coordenadas).
  - *Posible explicación:* Los recintos históricos o que cesaron funciones previamente podrían no haber sido incluidos en los programas de georreferenciación digital contemporáneos del DEIS.
- **Vigente en Operación Habitual:** 9 registros (9.4% de los que carecen de coordenadas).
  - *Posible explicación:* Centros de incorporación reciente (códigos de serie `202xxx`), dependencias universitarias o Salas Externas de Toma de Muestras (SETM) cuyos puntos geográficos podrían encontrarse aún en proceso de levantamiento catastral.

#### Detalle de los 9 Establecimientos Vigentes sin Coordenadas:
| Código | Establecimiento | Tipo | Comuna | Ámbito |
|---|---|---|---|---|
| `202293` | INTEGRAMEDICA SUCURSAL MALL VESPUCIO | Centro de Salud Privado | La Florida | Establecimiento de Salud |
| `202296` | SALA EXTERNA DE TOMA DE MUESTRAS_PRINCIPE DE GALES | Sala Externa de Toma de Muestras (SETM) | La Reina | Establecimiento de Salud |
| `202297` | CET ALAMEDA_SANTIAGO | Centro de Salud Privado | Santiago | Establecimiento de Salud |
| `202301` | SALA EXTERNA DE TOMA DE MUESTRAS_TALAGANTE | Sala Externa de Toma de Muestras (SETM) | Talagante | Establecimiento de Salud |
| `202306` | SUR Juan Pablo II | Servicio de Urgencia Rural (SUR) | Lampa | Establecimiento de Salud |
| `202307` | CENTRO ODONTOLOGICO UNIVERSIDAD MAYOR | Clínica Dental | Santiago | Establecimiento de Salud |
| `202368` | UNO SALUD DENTAL SILVA CARVALLO | Clínica Dental | Maipú | Establecimiento de Salud |
| `202369` | UNO SALUD DENTAL SAN RAMON - LIDER SANTA ROSA | Clínica Dental | San Ramón | Establecimiento de Salud |
| `202370` | SALA EXTERNA DE TOMA DE MUESTRAS REDSALUD PEDRO FONTOVA | Sala Externa de Toma de Muestras (SETM) | Huechuraba | Establecimiento de Salud |

*(Para revisar los 87 establecimientos cerrados restantes, consultar el archivo [`registros_sin_coordenadas.csv`](eda/registros_sin_coordenadas.csv)).*

---

## 6. Anomalías y Aspectos a Considerar

1. **Georreferenciación anómala de Clínica Los Maitenes (Melipilla, RM):**
   - Código establecimiento: `110270`
   - Coordenadas en origen DEIS: Lat `-39.295060`, Lon `-72.211826` (posicionadas en la Región de La Araucanía).
   - *Posible explicación:* Error de digitación en la fuente DEIS de origen donde se ingresó una coordenada de otra comuna.
   - *Recomendación:* Geocodificar la dirección de la clínica o imputar mediante el centroide de la comuna de Melipilla durante la etapa de accesibilidad territorial (`src/geo/`).
2. **Tratamiento de Centros sin Coordenadas en Modelos Territoriales:**
   - De los 96 establecimientos sin coordenadas, solo 1 corresponde a un servicio de urgencia activo (*SUR Juan Pablo II* en Lampa, código `202306`).
   - *Recomendación:* Asignar coordenadas a través de geocodificación de dirección para este SUR antes de calcular las isócronas de viaje.

---

## 7. Conclusión y Recomendación

1. **¿CLEAN contiene solamente RM?** **SÍ**, el 100% de los registros pertenecen al código de región 13.
2. **¿Se perdió algún registro de RM?** **NO**, se conservaron los 1,172 establecimientos identificados en el RAW.
3. **¿Cuántos registros tiene finalmente CLEAN?** **1,172 filas** y **33 columnas**.
4. **¿El dataset está suficientemente validado para continuar?** **SÍ**, el dataset posee integridad relacional, tipado robusto, texto limpio y está listo para alimentar el componente geoespacial (`src/geo/`) y las series de tiempo (`src/models/`).
