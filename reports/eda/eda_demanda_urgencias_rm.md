# Informe de Perfilado Descriptivo de la Demanda de Urgencias en la Región Metropolitana (2020–2026)
## Análisis Estadístico, Temporal, Territorial y Caracterización de Salud Mental (F00–F99)

**Fecha:** 2026-08-27  
**Estado:** VALIDADO / DESCRIPTIVO  
**Fuentes analizadas:**
- `data/processed/urgencias/urgencias_rm_[2020-2026].parquet` (13,897,800 registros RM)
- `data/processed/establecimientos_rm_clean.parquet` (1,172 establecimientos)
- `data/processed/urgencias/catalogo_f00_f99.csv` y `catalogo_causas_urgencias.csv`

---

## 1. Objetivo
Caracterizar y perfilar descriptivamente la demanda de atenciones de urgencia en la Región Metropolitana entre los años 2020 y 2026, estableciendo las reglas metodológicas de conteo, control de doble conteo, evolución temporal, distribución territorial (por comuna, establecimiento y tipo de dispositivo) y la caracterización específica de las consultas por trastornos mentales y del comportamiento (CIE-10 F00–F99) y causas vinculadas.

---

## 2. Fuentes Utilizadas
1. **Atenciones de Urgencia DEIS RM:** 7 archivos Parquet procesados (`data/processed/urgencias/urgencias_rm_2020.parquet` a `urgencias_rm_2026.parquet`), conteniendo 13,897,800 registros estandarizados con esquema homogéneo de 24 columnas.
2. **Maestro de Establecimientos RM:** `data/processed/establecimientos_rm_clean.parquet`, con 1,172 centros y cobertura geoespacial del 91.81%.
3. **Catálogos Dimensionales de Causas:** `data/processed/urgencias/catalogo_causas_urgencias.csv` y `data/processed/urgencias/catalogo_f00_f99.csv`.

---

## 3. Universo Territorial RM
El universo territorial corresponde estrictamente a los establecimientos de salud ubicados en las 52 comunas de la Región Metropolitana (`region_codigo == 13`), validados mediante el catálogo oficial DEIS y la cartografía comunal Censo 2024.

---

## 4. Granularidad Real de los Datos
Cada fila de los datasets procesados representa el conteo diario acumulado de atenciones para una combinación única de:
$$\text{Fila} = \text{Fecha (día)} \times \text{Establecimiento} \times \text{ID Causa} \times \text{Tipo Atención} \times \text{Tipo Campaña} \times \text{Tipo Establecimiento Urgencia}$$

- **No representa una persona individual** (los datos son agregados en origen).
- **No representa una atención aislada** (el campo `total` contiene la cantidad de consultas de ese día/causa/centro).
- En la base coexisten **registros agregadores** (macro-totales) y **registros de causas específicas**.

---

## 5. Método de Conteo de Atenciones
Para evitar sobreconteo, el cálculo de las atenciones debe regirse por las siguientes fórmulas matemáticamente demostradas:

1. **Demanda General Total de Urgencias:**
   $$\text{Atenciones Totales} = \sum_{\text{filas}} \text{total} \quad \text{donde } \mathbf{id\_causa == 1} \text{ (Sección 1. Total Atenciones de Urgencia)}$$

2. **Demanda Agregada de Salud Mental (F00–F99):**
   $$\text{Atenciones Salud Mental} = \sum_{\text{filas}} \text{total} \quad \text{donde } \mathbf{id\_causa == 36} \text{ (Total F00--F99)}$$

3. **Demanda por Subcausas Específicas de Salud Mental:**
   Filtrar por cada `id_causa` correspondiente:
   - `ID 38`: Sustancias psicoactivas (F10–F19)
   - `ID 39`: Trastornos afectivos (F30–F39)
   - `ID 40`: Trastornos neuróticos y estrés (F40–F48)
   - `ID 41`: Otros trastornos mentales
   - `ID 37`: Ideación suicida (R45.8)
   - `ID 35`: Lesiones autoinfligidas intencionalmente (X60–X84)

---

## 6. Control de Doble Conteo
Se validó formalmente que la suma de todas las filas sin filtrar genera un sobreconteo de entre 3.4 y 3.5 veces la demanda real debido a la coexistencia de categorías totales y subtotales.

### TABLA 12: Controles de Consistencia y Cero Discrepancia
| Año | Total Demanda General (`id_causa=1`) | Suma Semanal (`id_causa=1`) | Diferencia Semanal | Suma Comunal (`id_causa=1`) | Diferencia Comunal | Suma Establecimientos (`id_causa=1`) | Diferencia Establecimientos | Total F00–F99 (`id_causa=36`) | Suma Subcausas SM (`37+38+39+40+41`) | Diferencia SM |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2021** | 4,476,342 | 4,476,342 | 0 | 4,476,342 | 0 | 4,476,342 | 0 | 81,130 | 81,130 | 0 |
| **2022** | 6,120,119 | 6,120,119 | 0 | 6,120,119 | 0 | 6,120,119 | 0 | 95,194 | 95,194 | 0 |
| **2023** | 6,037,435 | 6,037,435 | 0 | 6,037,435 | 0 | 6,037,435 | 0 | 104,919 | 104,919 | 0 |
| **2024** | 6,135,659 | 6,135,659 | 0 | 6,135,659 | 0 | 6,135,659 | 0 | 107,648 | 107,648 | 0 |
| **2025** | 6,070,915 | 6,070,915 | 0 | 6,070,915 | 0 | 6,070,915 | 0 | 112,504 | 112,504 | 0 |
| **2026** | 3,823,247 | 3,823,247 | 0 | 3,823,247 | 0 | 3,823,247 | 0 | 72,862 | 72,862 | 0 |

---

## 7. Demanda General de Urgencias en la RM

### TABLA 1: Perfil Anual de Demanda General RM (`id_causa == 1`)
| Año | Atenciones Totales | Establecimientos Únicos | Comunas Únicas | Semanas Observadas | Días Observados | Período Inicio | Período Término | Promedio Semanal | Mediana Semanal | Mínimo Semanal | Máximo Semanal | Promedio Diario |
|---:|---:|---:|---:|---:|---:|:---:|:---:|---:|---:|---:|---:|---:|
| **2020** | 3,818,942 | 142 | 51 | 53 | 366 | 01/01/2020 | 31/12/2020 | 72,055.5 | 66,743.0 | 44,792 | 129,567 | 10,434.3 |
| **2021** | 4,476,342 | 148 | 51 | 53 | 365 | 01/01/2021 | 31/12/2021 | 84,459.3 | 84,651.0 | 54,923 | 113,836 | 12,264.0 |
| **2022** | 6,120,119 | 147 | 51 | 52 | 365 | 01/01/2022 | 31/12/2022 | 117,694.6 | 117,605.5 | 78,574 | 167,490 | 16,767.4 |
| **2023** | 6,037,435 | 148 | 51 | 52 | 365 | 01/01/2023 | 31/12/2023 | 116,104.5 | 115,221.0 | 80,094 | 170,166 | 16,540.9 |
| **2024** | 6,135,659 | 149 | 51 | 52 | 366 | 01/01/2024 | 31/12/2024 | 117,993.4 | 117,839.0 | 80,486 | 170,698 | 16,764.1 |
| **2025** | 6,070,915 | 152 | 51 | 53 | 365 | 01/01/2025 | 31/12/2025 | 114,545.6 | 115,532.0 | 72,130 | 155,753 | 16,632.6 |
| **2026** | 3,823,247 | 156 | 52 | 35 | 242 | 01/01/2026 | 30/08/2026 | 109,235.6 | 109,247.0 | 79,271 | 145,213 | 15,798.5 |

*(Nota metodológica: Para 2026 se dispone de un universo temporal parcial que abarca desde el 1 de enero hasta el 25 de agosto de 2026, equivalente a 237 días y 35 semanas epidemiológicas observadas. De estas, 33 corresponden a semanas completas y las semanas 1 y 35 son parciales. Por tanto, 2026 no constituye un año completo y no debe compararse directamente mediante volúmenes anuales acumulados con los años 2020–2025.)*

---

## 8. Evolución Temporal
1. **Efecto Pandemia y Normalización (2020–2022):** 2020 y 2021 registraron una caída pronunciada en el volumen total de urgencias (3.8M y 4.5M) debido a restricciones de movilidad y confinamientos. A partir de 2022 la demanda se estabilizó en una meseta de **~6.0 a 6.1 millones de atenciones anuales**.
2. **Discontinuidad Metodológica 2020 en Salud Mental:** En 2020 solo se registraron 1,266 atenciones de salud mental (promedio semanal de 23.9), debido a que el sistema DEIS incorporó la obligatoriedad y el desglose de F00–F99 en el SADU a fines de 2020. Por ende, **2020 queda excluido del análisis de series de tiempo de salud mental**, fijándose **2021 como inicio formal de la serie**.

---

## 9. Distribución Territorial por Comuna

### TABLA 3: Top 10 Comunas por Demanda General de Urgencias (2021–2026)
| Ranking | Código CUT | Comuna | Atenciones Totales (2021–2026) | % Demanda RM | Establecimientos Reportantes |
|---:|:---:|:---|---:|---:|---:|
| **1** | `13201` | Puente Alto | 2,683,161 | 8.21% | 7 |
| **2** | `13119` | Maipú | 1,811,707 | 5.55% | 9 |
| **3** | `13401` | San Bernardo | 1,631,902 | 5.00% | 8 |
| **4** | `13101` | Santiago | 1,467,235 | 4.49% | 6 |
| **5** | `13110` | La Florida | 1,291,019 | 3.95% | 5 |
| **6** | `13131` | San Ramón | 1,254,498 | 3.84% | 4 |
| **7** | `13130` | San Miguel | 1,202,305 | 3.68% | 3 |
| **8** | `13103` | Cerro Navia | 1,157,698 | 3.54% | 4 |
| **9** | `13108` | Independencia | 1,134,818 | 3.47% | 4 |
| **10** | `13122` | Peñalolén | 1,070,307 | 3.28% | 5 |

*(Total acumulado 52 comunas RM: 32,663,717 atenciones).*

---

## 10. Distribución por Establecimiento

### TABLA 4: Top 10 Establecimientos por Demanda General (2021–2026)
| Ranking | Código DEIS | Establecimiento | Tipo Establecimiento | Comuna | Total Atenciones | % Demanda RM |
|---:|:---:|:---|:---|:---|---:|---:|
| **1** | `114101` | Complejo Hospitalario Dr. Sótero del Río | Hospital | Puente Alto | 848,373 | 2.60% |
| **2** | `110120` | Hospital Félix Bulnes Cerda | Hospital | Cerro Navia | 674,907 | 2.07% |
| **3** | `114103` | Hospital Padre Alberto Hurtado | Hospital | San Ramón | 606,785 | 1.86% |
| **4** | `111101` | Hospital Clínico Metropolitano El Carmen | Hospital | Maipú | 561,533 | 1.72% |
| **5** | `110860` | SAPU Dr. José Manuel Balmaceda | SAPU | Pirque | 459,291 | 1.41% |
| **6** | `111195` | Hospital de Urgencia Asistencia Pública (HUAP) | Hospital | Santiago | 456,021 | 1.40% |
| **7** | `113130` | Hospital y C.R.S. El Pino | Hospital | San Bernardo | 453,645 | 1.39% |
| **8** | `113100` | Hospital Barros Luco Trudeau | Hospital | San Miguel | 435,622 | 1.33% |
| **9** | `109101` | Hospital San José | Hospital | Independencia | 432,571 | 1.32% |
| **10** | `110867` | SAPU Santa Rosa de Chena | SAPU | Padre Hurtado | 425,482 | 1.30% |

---

## 11. Distribución por Tipo de Establecimiento

### TABLA 5: Demanda de Urgencia según Tipología DEIS (2021–2026)
| Tipo de Establecimiento (Maestro) | Cantidad Centros | Atenciones Totales (2021–2026) | % Demanda RM | Promedio por Centro |
|:---|---:|---:|---:|---:|
| **Servicio de Atención Primaria de Urgencia (SAPU)** | 93 | 17,252,218 | 52.82% | 185,507.7 |
| **Hospital (con Urgencia/UEH)** | 26 | 8,567,023 | 26.23% | 329,500.9 |
| **SAR (Alta Resolutividad)** | 26 | 6,255,355 | 19.15% | 240,590.6 |
| **Servicio de Urgencia Rural (SUR)** | 11 | 570,041 | 1.75% | 51,821.9 |
| **Centro de Salud Familiar (CESFAM)** | 1 | 19,080 | 0.06% | 19,080.0 |

- **Hallazgo:** La Atención Primaria de Urgencia (SAPU + SAR + SUR) absorbe el **73.72% del volumen total de consultas de urgencia de la RM**, mientras que los hospitales concentran el **26.23%**, con el mayor volumen promedio por establecimiento.

---

## 12. Demanda de Salud Mental (F00–F99) y Evolución

### TABLA 6 & 7: Perfil Anual y Participación de Salud Mental (`id_causa == 36`)
| Año | Atenciones Totales Urgencia | Atenciones F00–F99 | % Salud Mental sobre Total | Promedio Semanal SM | Mediana Semanal SM | Mínimo Semanal SM | Máximo Semanal SM | Establecimientos con SM | Comunas con SM |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2020** | 3,818,942 | 1,266 | 0.03% | 23.9 | 8.0 | 0 | 345 | 69 | 37 |
| **2021** | 4,476,342 | 81,130 | 1.81% | 1,530.8 | 1,616.0 | 236 | 2,001 | 142 | 51 |
| **2022** | 6,120,119 | 95,194 | 1.56% | 1,830.7 | 1,880.5 | 1,401 | 2,230 | 144 | 51 |
| **2023** | 6,037,435 | 104,919 | 1.74% | 2,017.7 | 2,040.0 | 1,643 | 2,266 | 144 | 51 |
| **2024** | 6,135,659 | 107,648 | 1.75% | 2,070.2 | 2,095.5 | 1,647 | 2,660 | 146 | 51 |
| **2025** | 6,070,915 | 112,504 | 1.85% | 2,122.7 | 2,155.0 | 1,220 | 2,452 | 147 | 51 |
| **2026** | 3,823,247 | 72,862 | 1.91% | 2,081.8 | 2,217.0 | 551 | 2,414 | 155 | 52 |

- **Tendencia de Salud Mental:** Crecimiento sostenido desde **81,130 consultas en 2021 a 112,504 en 2025 (+38.7%)**, incrementando su participación relativa del **1.81% al 1.91%** de la demanda global de urgencias.

---

## 13. Distribución Territorial de Salud Mental

### TABLA 8: Top 10 Comunas por Demanda de Salud Mental (2021–2026)
| Ranking | Código CUT | Comuna | Atenciones F00–F99 (2021–2026) | % de Salud Mental RM | Proporción SM en Comuna (%) |
|---:|:---:|:---|---:|---:|---:|
| **1** | `13127` | Recoleta | 106,131 | 18.48% | **16.53%** |
| **2** | `13201` | Puente Alto | 33,344 | 5.81% | 1.24% |
| **3** | `13130` | San Miguel | 25,923 | 4.51% | 2.16% |
| **4** | `13401` | San Bernardo | 25,281 | 4.40% | 1.55% |
| **5** | `13119` | Maipú | 22,111 | 3.85% | 1.71% |
| **6** | `13110` | La Florida | 21,702 | 3.78% | 1.28% |
| **7** | `13103` | Cerro Navia | 18,681 | 3.25% | 1.61% |
| **8** | `13101` | Santiago | 17,757 | 3.09% | 1.21% |
| **9** | `13125` | Quilicura | 17,443 | 3.04% | 2.22% |
| **10** | `13124` | Pudahuel | 15,069 | 2.62% | 1.43% |

*(Total F00–F99 2021–2026 en RM: 574,257 atenciones).*

---

## 14. Distribución por Establecimiento en Salud Mental

### TABLA 9: Top 10 Establecimientos por Volumen de Salud Mental (2021–2026)
| Ranking | Código DEIS | Establecimiento | Tipo Establecimiento | Comuna | Atenciones F00–F99 | % SM RM | Proporción en su Demanda (%) |
|---:|:---:|:---|:---|:---|---:|---:|---:|
| **1** | `109102` | Instituto Psiquiátrico Dr. José Horwitz Barak | Hospital | Recoleta | **99,802** | **17.38%** | **95.54%** |
| **2** | `113100` | Hospital Barros Luco Trudeau | Hospital | San Miguel | 19,535 | 3.40% | 4.48% |
| **3** | `111101` | Hospital Clínico Metropolitano El Carmen | Hospital | Maipú | 13,944 | 2.43% | 2.48% |
| **4** | `111195` | Hospital de Urgencia Asistencia Pública (HUAP) | Hospital | Santiago | 13,125 | 2.29% | 2.88% |
| **5** | `110120` | Hospital Félix Bulnes Cerda | Hospital | Cerro Navia | 12,475 | 2.17% | 1.85% |
| **6** | `109815` | SAPU Nº 1 Rodrigo Rojas Denegri | SAPU | Quilicura | 11,884 | 2.07% | 2.81% |
| **7** | `114101` | Complejo Hospitalario Dr. Sótero del Río | Hospital | Puente Alto | 9,791 | 1.70% | 1.15% |
| **8** | `110867` | SAPU Santa Rosa de Chena | SAPU | Padre Hurtado | 7,657 | 1.33% | 1.80% |
| **9** | `109811` | SAPU José Bauzá Frau | SAPU | Lampa | 7,344 | 1.28% | 2.07% |
| **10** | `109805` | SAR La Pincoya | SAR | Huechuraba | 7,208 | 1.26% | 2.64% |

- **Concentración Institucional:** El **Instituto Psiquiátrico Dr. José Horwitz Barak** concentra por sí solo el **17.38% de todas las atenciones de urgencia de salud mental de la región** y el **95.54% de sus consultas** son del capítulo F00–F99.

---

## 15. Desagregación de Causas de Salud Mental

### TABLA 10: Descomposición de Causas de Salud Mental y Relacionadas (2021–2026)
| ID Causa | Glosa Estándar | Atenciones (2021–2026) | % sobre Total F00–F99 (`ID 36`) | Clasificación Clínica |
|---:|:---|---:|---:|:---|
| **36** | **TOTAL CAUSAS TRASTORNOS MENTALES (F00–F99)** | **574,257** | **100.00%** | **Macro-agregador** |
| `40` | Trastornos neuróticos, estrés y somatomorfos (F40–F48) | 311,278 | **54.21%** | Subcausa CIE-10 (Componente) |
| `41` | Otros trastornos mentales no clasificados | 125,621 | **21.88%** | Subcausa CIE-10 (Componente) |
| `38` | Trastornos por uso de sustancias psicoactivas (F10–F19) | 56,564 | **9.85%** | Subcausa CIE-10 (Componente) |
| `39` | Trastornos del humor (afectivos) (F30–F39) | 48,585 | **8.46%** | Subcausa CIE-10 (Componente) |
| `37` | Ideación suicida (R45.8) | 32,209 | **5.61%** | Síntoma / Signo (Componente) |
| `35` | Lesiones autoinfligidas intencionalmente (X60–X84) | 15,146 | *2.64%* | Causa Externa (Sección 1) |
| `42` | Hospitalizaciones derivadas por trastornos mentales | 31,460 | *5.48%* | Derivación Hospitalaria (Sección 2) |

---

## 16. Controles de Calidad y Cobertura

### TABLA 11: Cobertura de Establecimientos de Urgencias contra Maestro RM
| Año | Establecimientos Reportantes | Encontrados en Maestro | No Encontrados | % Cobertura Maestro | Con Coordenadas | Sin Coordenadas |
|---:|---:|---:|---:|---:|---:|---:|
| **2020** | 142 | 142 | 0 | 100.0% | 140 | 2 |
| **2021** | 148 | 148 | 0 | 100.0% | 146 | 2 |
| **2022** | 147 | 147 | 0 | 100.0% | 145 | 2 |
| **2023** | 148 | 148 | 0 | 100.0% | 146 | 2 |
| **2024** | 149 | 149 | 0 | 100.0% | 147 | 2 |
| **2025** | 152 | 152 | 0 | 100.0% | 150 | 2 |
| **2026** | 156 | 156 | 0 | 100.0% | 153 | 3 |

**Advertencia Metodológica sobre Coordenadas:** Es crucial distinguir que el **100% de cobertura de establecimientos contra el maestro** (157/157 encontrados) **NO equivale al 100% de disponibilidad de coordenadas geográficas**. Existen 3 establecimientos sin latitud/longitud disponibles en el maestro limpio (112820 — SAPU Centro de Urgencia Ñuñoa, 200142 — SAPU La Reina, y 202306 — SUR Juan Pablo II). Estos establecimientos no deben considerarse georreferenciados para análisis espaciales hasta resolver sus coordenadas.

---

## 17. Limitaciones Metodológicas
1. **Naturaleza Agregada:** Los datos de atenciones de urgencia son recuentos diarios agrupados por causa y centro; no constituyen historias clínicas individuales ni registros anonimizados por paciente.
2. **Demanda Observada vs. Necesidad Sanitaria:** Un alto volumen en una comuna o centro refleja la presencia de oferta física, capacidad instalada y patrones de utilización, pero no puede interpretarse como prevalencia de enfermedad ni mayor riesgo de la población residente.
3. **Discontinuidad 2020 en Salud Mental:** El año 2020 registra solamente 1.266 atenciones F00–F99. El volumen es sustancialmente inferior al observado desde 2021. Esto es consistente con la limitación ya documentada sobre la falta de desagregación/captura de salud mental en una parte importante de los centros de APS durante 2020. Por este motivo, 2020 no debe utilizarse como base comparable para analizar la evolución temporal de la demanda F00–F99.

---

## 18. Variables Faltantes para Fases Posteriores
- **A. Denominadores Demográficos:** Población comunal por grupos de edad (Censo 2024 / proyecciones INE) para calcular tasas de consulta ajustadas.
- **B. Accesibilidad Espacial:** Tiempos de viaje y distancias en red vial e isócronas de transporte público (GTFS / OSM).
- **C. Determinantes de Hospitalización:** Duración de estadía hospitalaria, previsión y condición de egreso provenientes de Egresos Hospitalarios (2020–2025).

---

## 19. Preguntas Abiertas
1. ¿Cuál es el desfase temporal (lag) entre las fluctuaciones semanales de urgencias de salud mental y los ingresos/egresos hospitalarios psiquiátricos?
2. ¿Qué proporción de la demanda atendida en el Instituto Horwitz corresponde a residentes de la comuna de Recoleta versus pacientes derivados desde el resto de la RM?

---

## 20. Recomendaciones para la Siguiente Etapa
1. **Fijar formalmente el período 2021–2025** para el entrenamiento y modelado de series de tiempo de demanda semanal en salud mental, manteniendo 2026 como conjunto de evaluación out-of-sample.
2. **Iniciar la normalización, perfilado y auditoría de Egresos Hospitalarios F00–F99 (2020–2025)** para caracterizar la estancia hospitalaria y la presión sobre camas psiquiátricas.
