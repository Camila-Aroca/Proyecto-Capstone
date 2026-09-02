# Informe de Auditoría del Maestro de Establecimientos y Relaciones de Red Asistencial (RM)
## Diagnóstico de Variables, Identificadores, Cobertura Territorial y Enlaces con Urgencias y Egresos

**Fecha de ejecución:** 2026-08-26  
**Fuentes analizadas:**
- `data/processed/establecimientos_rm_clean.csv` (1,172 establecimientos)
- `data/processed/establecimientos_salud_clean.parquet` (5,717 establecimientos nacionales)
- `data/raw/deis/establecimientos_salud_actualizado.csv` (Fuente cruda DEIS)
- `data/processed/urgencias/urgencias_rm_[2020-2026].parquet`
- `data/raw/egresos/` (Bases 2020–2025)

---

## 1. Qué Contiene Actualmente el Maestro de Establecimientos RM

El archivo `data/processed/establecimientos_rm_clean.csv` contiene **1,172 establecimientos de salud** de la Región Metropolitana caracterizados mediante **33 variables normalizadas**:

| Variable | Tipo de Dato | Nulos en RM | Valores Únicos | Descripción Observada / Evidencia |
|---|---|---:|---:|---|
| `establecimiento_codigo` | `string` / `int` | 0 | 1,172 | Código nuevo unívoco DEIS (6 dígitos). Llave primaria. |
| `establecimiento_codigo_antiguo` | `string` | 264 | 908 | Código antiguo DEIS con guion (formato `XX-XXX`). |
| `establecimiento_codigo_madre_nuevo` | `string` | 479 | 390 | Código nuevo del establecimiento del cual depende administrativamente (ej. CESFAM base). |
| `establecimiento_codigo_madre_antiguo` | `string` | 557 | 358 | Código antiguo del establecimiento madre. |
| `establecimiento_glosa` | `string` | 0 | 1,154 | Nombre oficial del establecimiento. |
| `region_codigo` | `int32` | 0 | 1 | Código de región (`13` para RM). |
| `region_glosa` | `string` | 0 | 1 | Nombre de región (`Metropolitana de Santiago`). |
| `comuna_codigo` | `string` | 0 | 52 | Código CUT oficial de 5 dígitos (Censo / SUBDERE). |
| `comuna_glosa` | `string` | 0 | 52 | Nombre oficial de la comuna. |
| `seremi_salud_codigo_servicio_de_salud_codigo` | `string` | 0 | 7 | Código del Servicio de Salud o SEREMI (`09` a `14`, `RM`). |
| `seremi_salud_glosa_servicio_de_salud_glosa` | `string` | 0 | 8 | Servicio de Salud Metropolitano (Central, Norte, Occidente, Oriente, Sur, Sur Oriente, SEREMI). |
| `tipo_establecimiento_glosa` | `string` | 0 | 27 | Tipología funcional (Hospital, CESFAM, SAPU, SAR, COSAM, etc.). |
| `tipo_pertenencia_estab_glosa` | `string` | 0 | 3 | Pertenencia al SNSS o extra-sistema. |
| `ambito_funcionamiento` | `string` | 0 | 3 | Ámbito asistencial (`Establecimiento de Salud`, `Unidad de Atención`, `Programa`). |
| `dependencia_administrativa` | `string` | 0 | 7 | Tipo de administración (`Municipal`, `Servicio de Salud`, `Privado`, `FFAA`, etc.). |
| `nivel_atencion_estabglosa` | `string` | 46 | 3 | Nivel asistencial (`Primer Nivel`, `Segundo Nivel`, `Tercer Nivel`). |
| `nivel_complejidad_estab_glosa` | `string` | 46 | 3 | Complejidad técnica (`Baja`, `Mediana`, `Alta Complejidad`). |
| `tipo_atencion_estab_glosa` | `string` | 46 | 2 | Modalidad (`Atención Abierta-Ambulatoria`, `Atención Cerrada-Hospitalaria`). |
| `tiene_servicio_urgencia` | `string` | 0 | 3 | Indicador binario de dispositivo de urgencia (`SI`, `NO`, `No Aplica`). |
| `tipo_urgencia` | `string` | 988 | 5 | Tipo de urgencia ambulatoria/hospitalaria. |
| `clasificacion_tipo_sapu` | `string` | 1,067 | 3 | Categorización horaria SAPU (`Largo`, `Corto`). |
| `latitud` | `float64` | 96 | 1,049 | Coordenada geográfica decimal (WGS84 / SIRGAS 2000). |
| `longitud` | `float64` | 96 | 1,049 | Coordenada geográfica decimal (WGS84 / SIRGAS 2000). |
| `tipo_sistema_salud_glosa` | `string` | 0 | 3 | Sector sanitario (`Público`, `Privado`, `FFAA`). |
| `estado_funcionamiento` | `string` | 0 | 3 | Estado operativo (`Vigente en Operación Habitual`, `Cerrado`). |
| `tipo_via_glosa`, `nombre_via`, `numero` | `string` | <10% | Varios | Dirección física del centro de salud. |

---

## 2. Qué NO Contiene el Maestro

1. **Hospital de Referencia / Red de Derivación Asistencial:** El maestro **no contiene ninguna columna que indique a qué hospital deriva o pertenece cada centro de atención primaria o de urgencia**.
2. **Capacidad de Camas / Cupos Psiquiátricos:** No contiene dotación de camas hospitalarias ni camas de corta estadía de salud mental.
3. **Dotación de Personal:** No incluye número de médicos, psiquiatras ni personal de urgencia.

---

## 3. Identificadores Disponibles y Llaves de Enlace

- **`establecimiento_codigo`:** Identificador numérico estándar de 6 dígitos (código nuevo DEIS). Es la llave primaria del maestro.
- **`establecimiento_codigo_antiguo`:** Código histórico con guion (`XX-XXX`). Permite el enlace directo 1:1 con las series históricas de Urgencias (2020–2022).
- **`comuna_codigo`:** Código CUT de 5 dígitos. Permite el enlace con la cartografía comunal del Censo 2024.
- **`seremi_salud_codigo_servicio_de_salud_codigo`:** Permite agrupar los centros según la jurisdicción de los 6 Servicios de Salud de la RM.

---

## 4. Cobertura Territorial y Geográfica

- **Total establecimientos RM:** 1,172.
- **Cobertura comunal:** 100% de las 52 comunas de la RM poseen establecimientos registrados.
- **Cobertura de coordenadas:** **1,076 establecimientos georreferenciados (91.81%)**.
- **Establecimientos sin coordenadas:** 96 centros (correspondientes a programas móviles, unidades administrativas o centros cerrados).
- **Duplicidad de coordenadas:** 27 establecimientos comparten coordenadas exactas con otro centro (ej. un SAPU o COSAM ubicado físicamente en el mismo predio de un CESFAM).

---

## 5. Tipos de Establecimientos y Dispositivos de Urgencia

Desglose de los 1,172 establecimientos según tipología DEIS:

| Categoría Funcional (`tipo_establecimiento_glosa`) | Cantidad en RM | Ejemplos |
|---|---:|---|
| **Centro de Salud Privado / Consultas** | 262 | Centros médicos ambulatorios, Integramédica, RedSalud. |
| **Centro de Salud Familiar (CESFAM)** | 174 | CESFAM Recoleta, CESFAM Lucas Sierra, CESFAM Colina. |
| **Clínica Privada** | 108 | Clínica Alemana, Clínica Santa María, Clínica Dávila. |
| **Servicio de Atención Primaria de Urgencia (SAPU)** | 105 | SAPU Lucas Sierra, SAPU Valdivieso, SAPU Esmeralda. |
| **Centro Comunitario de Salud Familiar (CECOSF)** | 74 | CECOSF El Bosque, CECOSF Villa Sur. |
| **Clínica Dental / Laboratorio Clínico** | 130 | Laboratorio Blanco, Laboratorio Austral. |
| **Posta de Salud Rural (PSR)** | 51 | Posta Rungue, Posta Polpaico, Posta El Principal. |
| **Centro Comunitario de Salud Mental (COSAM)** | 47 | COSAM Peñalolén, COSAM San Bernardo, COSAM Recoleta. |
| **Hospital** | 47 | Hospital del Salvador, Hospital San Juan de Dios, Hospital Barros Luco. |
| **Vacunatorio / Toma de Muestras / Otros** | 99 | Puntos de apoyo diagnóstico. |
| **Servicio de Atención Primaria de Urgencia de Alta Resolutividad (SAR)** | 26 | SAR Recoleta, SAR La Pincoya, SAR Conchalí, SAR Colina. |
| **Servicio de Urgencia Rural (SUR)** | 11 | SUR Batuco, SUR Huertos Familiares, SUR Alhué. |
| **Centro de Especialidades / Diálisis / Otros** | 38 | Centros de especialidades ambulatorias. |

---

## 6. Hospitales y Servicios de Salud Identificables

### 6.1 Servicios de Salud Metropolitanos (Sector Público)
El maestro identifica los 6 Servicios de Salud que componen la red asistencial pública de la RM:
1. **Servicio de Salud Metropolitano Occidente:** 145 establecimientos.
2. **Servicio de Salud Metropolitano Sur:** 117 establecimientos.
3. **Servicio de Salud Metropolitano Sur Oriente:** 99 establecimientos.
4. **Servicio de Salud Metropolitano Norte:** 88 establecimientos.
5. **Servicio de Salud Metropolitano Oriente:** 70 establecimientos.
6. **Servicio de Salud Metropolitano Central:** 60 establecimientos.
*(Más 589 centros privados y extra-sistema bajo supervisión de la SEREMI RM).*

### 6.2 Hospitales en la RM
Existen **47 establecimientos categorizados formalmente como `Hospital`**, entre ellos los principales centros de alta complejidad con Unidades de Emergencia Hospitalaria (UEH) de adultos y psiquiatría (ej. Hospital del Salvador / Instituto Psiquiátrico Dr. José Horwitz Barak, Hospital Barros Luco Trudeau, Hospital San Juan de Dios, Hospital Clínico San Borja Arriarán, Hospital Dr. Sótero del Río, Hospital San José).

---

## 7. Relación Demostrable Establecimiento $\rightarrow$ Hospital

- **Hecho Observado:** De los 142 dispositivos de urgencia APS (SAPU, SAR, SUR), 124 poseen un código madre registrado (`establecimiento_codigo_madre_nuevo`).
- **Análisis de la Relación Madre:** En **122 de los 124 casos (98.4%)**, el código madre apunta a un **CESFAM base** (su centro de salud familiar de adscripción comunal), y en **0 casos apunta a un Hospital**.
- **Conclusión Metodológica Rigurosa:**
  > **El maestro actual permite identificar territorialmente los establecimientos y su pertenencia al Servicio de Salud y Municipio, pero no permite determinar de manera demostrable a qué hospital pertenece o deriva cada establecimiento.**

---

## 8. Relación Demostrable Maestro $\rightarrow$ Atenciones de Urgencia

Se verificó el cruce entre los 1,172 establecimientos del maestro y los centros reportantes en los Parquet procesados de Urgencias (2020–2026):

| Año | Centros Únicos en Urgencias | Encontrados en Maestro | No Encontrados | % Cobertura Maestro | Centros con Coordenadas | Centros sin Coordenadas |
|---:|---:|---:|---:|---:|---:|---:|
| **2020** | 142 | 142 | 0 | 100.0% | 140 | 2 |
| **2021** | 148 | 148 | 0 | 100.0% | 146 | 2 |
| **2022** | 147 | 147 | 0 | 100.0% | 145 | 2 |
| **2023** | 148 | 148 | 0 | 100.0% | 146 | 2 |
| **2024** | 149 | 149 | 0 | 100.0% | 147 | 2 |
| **2025** | 152 | 152 | 0 | 100.0% | 150 | 2 |
| **2026** | 156 | 156 | 0 | 100.0% | 153 | 3 |

- **Resultado:** **100.0% de los centros reportantes en urgencias existen en el maestro**.
- **Georreferenciación en Urgencias:** Más del **98% de los centros de urgencia activos cuentan con coordenadas geográficas exactas**.

---

## 9. Relación Potencial con Egresos Hospitalarios

- **Auditoría de Fuentes de Egresos:** Se inspeccionaron los archivos RAW de Egresos Hospitalarios 2020 a 2025 (`data/raw/egresos/`).
- **Hallazgo Crítico:** Las bases abiertas de egresos del DEIS **no incluyen el código ni el nombre del hospital específico donde ocurrió el egreso** por razones de protección y anonimización de datos de pacientes individuales.
- **Variables institucionales disponibles en Egresos:** Únicamente `PERTENENCIA_ESTABLECIMIENTO_SALUD` (`'Pertenecientes al SNSS'` vs `'No Pertenecientes'`) y la procedencia geográfica del paciente (`COMUNA_RESIDENCIA` / `REGION_RESIDENCIA`).
- **Conclusión:** **No es posible realizar un join directo establecimiento-a-establecimiento entre atenciones de urgencia y egresos hospitalarios**. La vinculación analítica entre urgencias y hospitalizaciones debe formularse a nivel **ecológico-territorial** (agrupación por comuna / Servicio de Salud y grupos etarios).

---

## 10. Respuestas a las Preguntas de Control

1. **¿Tenemos un maestro único de establecimientos de la RM?:** Sí, `data/processed/establecimientos_rm_clean.csv` (y `.parquet`).
2. **¿Cuántos establecimientos contiene?:** **1,172 establecimientos**.
3. **¿Qué variables tiene?:** **33 variables** (códigos DEIS, nombre, comuna, región, Servicio de Salud, tipo de centro, dependencia, complejidad, coordenadas, etc.).
4. **¿Cuántos tienen coordenadas?:** **1,076 establecimientos (91.81%)**.
5. **¿Cuántos son establecimientos de urgencia?:** 142 dispositivos de urgencia APS (SAPU, SAR, SUR) y 47 hospitales en el maestro; entre 142 y 156 centros reportan actividad anual continua en las bases de urgencia.
6. **¿Cuántos son hospitales?:** **47 hospitales** registrados en la RM.
7. **¿Tenemos Servicio de Salud?:** Sí, identificado en la variable `seremi_salud_glosa_servicio_de_salud_glosa` (6 Servicios de Salud públicos metropolitanos).
8. **¿Tenemos una relación explícita establecimiento $\rightarrow$ hospital?:** **No.** Los dispositivos de urgencia primaria enlazan a su CESFAM base mediante `establecimiento_codigo_madre`, pero no existe una variable de hospital de referencia.
9. **¿Podemos vincular urgencias 2020–2026 con este maestro?:** **Sí, con 100.0% de cobertura** mediante `establecimiento_codigo`.
10. **¿Podemos vincular egresos hospitalarios con este maestro?:** **No a nivel de establecimiento individual** (Egresos no publica código de centro); solo a nivel ecológico comunal/regional.
11. **¿Qué relaciones todavía requieren una fuente adicional?:** Las redes de derivación asistencial formales (definidas por decretos o carteras de Servicios de Salud) y las isócronas de viaje geoespaciales (OSM/GTFS) para conectar la demanda comunal con la oferta hospitalaria.
