# Informe de Auditoría y Homologación de Causas de Urgencia (2020–2026)
## Identificación Metodológica del Capítulo CIE-10 F00–F99 (Salud Mental) en la Región Metropolitana

**Fecha de ejecución:** 2026-08-26  
**Fuentes analizadas:**
- `data/processed/urgencias/urgencias_rm_[2020-2026].parquet` (13,897,800 filas procesadas)
- `data/raw/urgencias/DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx` (Diccionario Oficial DEIS-MINSAL)

---

## 1. Objetivo

Determinar con evidencia técnica directa cómo están estructuradas las causas de atención de urgencia en los datasets DEIS-MINSAL 2020–2026 de la Región Metropolitana, y establecer la validez metodológica para identificar y aislar las consultas correspondientes al capítulo CIE-10 **F00–F99 (Trastornos mentales y del comportamiento)** y causas clínicas asociadas.

---

## 2. Fuentes Utilizadas

1. **Bases procesadas de urgencia RM:** 7 datasets anuales en formato Parquet (`data/processed/urgencias/urgencias_rm_[2020-2026].parquet`).
2. **Diccionario Oficial DEIS:** Hoja técnica `Anexo 1 - Causas SADU` del archivo `data/raw/urgencias/DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx`.

---

## 3. Inventario de Causas por Año

A lo largo del período 2020–2026, el dataset registra **43 identificadores numéricos de causa (`id_causa`)** distribuidos en dos secciones asistenciales:
- **Sección 1 (Atenciones de Urgencia):** Macro-agregadores y causas específicas de morbilidad.
- **Sección 2 (Hospitalizaciones y Espera):** Pacientes derivados a hospitalización y tiempos de espera en Unidad de Emergencia Hospitalaria (UEH).

### 3.1 Métricas Generales por Año (Región Metropolitana)

| Año | `id_causa` Únicos | `glosa_causa` Únicas | Nulos en ID | Nulos en Glosa | Total Atenciones Sección 1 (`total`) | Atenciones Salud Mental (ID 36) | % Salud Mental |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **2020** | 35 | 35 | 0 | 0 | 3,818,942 | 1,266 | 0.03%* |
| **2021** | 36 | 36 | 0 | 0 | 4,476,342 | 81,130 | 1.81% |
| **2022** | 36 | 36 | 0 | 0 | 6,120,119 | 95,194 | 1.56% |
| **2023** | 36 | 36 | 0 | 0 | 6,037,435 | 104,919 | 1.74% |
| **2024** | 36 | 36 | 0 | 0 | 6,135,659 | 107,648 | 1.75% |
| **2025** | 36 | 36 | 0 | 0 | 6,070,915 | 112,504 | 1.85% |
| **2026** | 36 | 36 | 0 | 0 | 3,823,247 | 72,862 | 1.91% |

*\*Nota sobre 2020:* Las causas específicas de salud mental (`ID 35` a `ID 42`) fueron incorporadas por el DEIS en el sistema SADU a fines de 2020 (semanas epidemiológicas finales). Por tanto, la serie histórica continua y completa de salud mental inicia formalmente en **2021**.

---

## 4. Correspondencia `id_causa` ↔ `glosa_causa`

- **Relación 1:1 dentro de cada año:** En cada archivo anual, cada `id_causa` tiene una única `glosa_causa` asignada.
- **Variaciones de redacción entre años:** Se identificaron cambios menores de texto en algunas glosas (ej. adición o supresión de códigos CIE-10 en el texto de la glosa o inclusión de prefijos como `TOTAL ATENCIONES POR...`). Sin embargo, el código numérico `id_causa` se mantiene **100% estable y consistente** en todo el período 2020–2026.

---

## 5. Cambios Estructurales y Evolución Temporal

1. **Incorporación de COVID-19 (2020–2021):** `ID 30` (U07.1) y `ID 31` (U07.2).
2. **Incorporación del Módulo de Salud Mental (Fines de 2020 en adelante):**
   - `ID 36`: Total causas de trastornos mentales (F00-F99).
   - `ID 37`: Ideación suicida (R45.8).
   - `ID 38`: Trastornos por uso de sustancias psicoactivas (F10-F19).
   - `ID 39`: Trastornos del humor / afectivos (F30-F39).
   - `ID 40`: Trastornos neuróticos, estrés y somatomorfos (F40-F48).
   - `ID 41`: Otros trastornos mentales no contenidos en las categorías anteriores.
   - `ID 35`: Lesiones autoinfligidas intencionalmente (X60-X84).
   - `ID 42`: Hospitalizaciones por trastornos mentales (F00-F99).
3. **Nueva Causa Externa en 2026:** Se añadió `ID 43` (*Lesiones por quemaduras, exposición al humo, fuego, calor X00-X19*).

---

## 6. Evidencia Sobre CIE-10 en los Datos DEIS

Se constata evidencia documental y analítica explícita:
1. **Evidencia Documental:** En el diccionario oficial DEIS (`DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx`), la tabla de causas lista expresamente los rangos de códigos CIE-10 para cada categoría.
2. **Evidencia Aritmética Interna:** Se comprobó que el macro-agregador `ID 36` satisface la igualdad matemática exacta:
   $$\text{ID 36} = \text{ID 37} + \text{ID 38} + \text{ID 39} + \text{ID 40} + \text{ID 41}$$
   con **0 discrepancias en los 7 años analizados**.

---

## 7. Metodología de Clasificación e Identificación de F00–F99

Se establecen 4 niveles taxonómicos para evitar doble conteo y preservar la precisión metodológica:

- **Categoría A (CIE-10 F00–F99 Específico / Subcausas Disjuntas):** `ID 38` (F10–F19), `ID 39` (F30–F39), `ID 40` (F40–F48) e `ID 41` (Resto de F).
- **Categoría B (Macro-agregador de Salud Mental):** `ID 36` (Total F00–F99 + R45.8). **No debe sumarse junto con las subcausas A para no duplicar atenciones**.
- **Categoría C (Causa de Salud Mental Asociada - Síntoma / Signo R):** `ID 37` (Ideación Suicida R45.8).
- **Categoría D (Causa Externa Relacionada / Traumatismo X):** `ID 35` (Lesiones autoinfligidas X60–X84).
- **Categoría E (Resultado Asistencial / Hospitalización):** `ID 42` (Hospitalizaciones derivadas por F00–F99).

---

## 8. Tabla Oficial de Homologación de Salud Mental

| `id_causa` | Glosa Estandarizada | Código CIE-10 | Tipo de Registro | Nivel de Confianza | Atenciones Totales RM (2020–2026) |
|---:|---|---|---|---|---:|
| **36** | **TOTAL CAUSAS DE TRASTORNOS MENTALES** | **F00-F99 (Agregado)** | **Macro-agregador** | **Alto** | **575,523** |
| **38** | Trastornos por uso de sustancias psicoactivas | F10-F19 | Subcausa Específica | Alto | 56,675 |
| **39** | Trastornos del humor (afectivos) | F30-F39 | Subcausa Específica | Alto | 48,635 |
| **40** | Trastornos neuróticos, estrés y somatomorfos | F40-F48 | Subcausa Específica | Alto | 312,157 |
| **41** | Otros trastornos mentales no contenidos en anteriores | F00-F09, F20-F29, F50-F99 | Subcausa Residual | Alto | 125,836 |
| **37** | Ideación suicida | R45.8 | Síntoma / Signo | Alto | 32,220 |
| **35** | Lesiones autoinfligidas intencionalmente | X60-X84 | Causa Externa / Traumatismo | Alto | 15,388 |
| **42** | Hospitalizaciones derivadas por salud mental | F00-F99 (Hosp.) | Derivación Sección 2 | Alto | 31,478 |

---

## 9. Causas No Clasificables como Salud Mental

Las causas con `id_causa` entre `1` y `34`, `43` corresponden a otros capítulos de la CIE-10 (Respiratorio J00–J98, Circulatorio I00–I99, Diarrea A00–A09, Accidentes V01–V89, Demás causas) y quedan formalmente excluidas del universo F00–F99.

---

## 10. Limitaciones

1. **Agrupación Ecológica:** Los datos representan atenciones acumuladas a nivel de centro y día, no historias clínicas individuales.
2. **Detalle a 3 dígitos CIE-10:** El sistema de urgencias no registra el código CIE-10 a 4 caracteres (ej. no desagrega F32.0 de F31.1), sino los bloques sindrómicos oficiales (F10–F19, F30–F39, F40–F48).
3. **Inicio de serie en 2020:** Debido a la incorporación tardía del módulo de salud mental en el SADU en 2020, el modelado y series temporales deben entrenarse y proyectarse sobre el período continuo **2021–2026**.

---

## 11. Recomendaciones para la Siguiente Etapa

1. **Construcción de Series de Demanda:** Para el modelo predictivo (4–8 semanas), utilizar `id_causa == 36` para la demanda global de salud mental, y las subcausas `38`, `39`, `40`, `41` para pronósticos desagregados por grupo diagnóstico.
2. **Uso de Archivos Generados:** Emplear `data/processed/urgencias/catalogo_f00_f99.csv` como tabla dimensional maestra para joins en los pipelines analíticos.
