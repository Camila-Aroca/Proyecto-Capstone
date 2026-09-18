# Informe de Auditoría y EDA — Cartografía Subcomunal Censo 2024 (RM)

**Fecha de ejecución:** 2026-09-18
**Fuente:** `https://storage.googleapis.com/bktdescargascenso2024/Cartografia/GEOPARQUET/Cartografia_censo2024_Pais.zip`
**RAW publicado:** `data/raw/censo/` (5 GeoParquet + 1 diccionario XLSX)
**Processed publicado:** `data/processed/censo/Cartografia_censo2024_RM_<Capa>.parquet`
**Auxiliar generado:** [`reconciliacion_poblacion_censo2024_subcomunal_rm.csv`](reconciliacion_poblacion_censo2024_subcomunal_rm.csv)

---

## 1. Miembros reales del ZIP (inspección directa, no asumida)

El ZIP (794.658.978 bytes, íntegro, sin miembros corruptos) contiene 11 archivos:

| Miembro | Tamaño (bytes) | ¿Publicado como RAW? |
|---|---:|---|
| `Cartografia_censo2024_Pais_Comunal.parquet` | 125.790.972 | Sí (ya existía) |
| `Cartografia_censo2024_Pais_Distrital.parquet` | 165.576.123 | Sí (nuevo) |
| `Cartografia_censo2024_Pais_Zonal.parquet` | 24.235.286 | Sí (nuevo) |
| `Cartografia_censo2024_Pais_Entidades.parquet` | 110.063.816 | Sí (nuevo) |
| `Cartografia_censo2024_Pais_Manzanas.parquet` | 203.341.665 | Sí (nuevo) |
| `Diccionario_variables_geograficas_CPV24.xlsx` | 23.553 | Sí (nuevo) |
| `Cartografia_censo2024_Pais_Aldeas.parquet` | 3.404.638 | No (fuera de alcance; ver §7) |
| `Cartografia_censo2024_Pais_Limite_Urbano.parquet` | 13.347.331 | No |
| `Cartografia_censo2024_Pais_Localidades.parquet` | 96.404.790 | No |
| `Cartografia_censo2024_Pais_Provincial.parquet` | 109.536.423 | No |
| `Cartografia_censo2024_Pais_Regional.parquet` | 104.798.617 | No |

Los 6 nombres solicitados en la tarea coinciden exactamente con los nombres reales observados; no hubo diferencias de nomenclatura que documentar.

---

## 2. Contratos por capa (grano, llaves, CRS, cobertura)

Todas las capas comparten CRS **SIRGAS 2000 (`EPSG:4674`)**, geometría `MultiPolygon` en WKB (columna `SHAPE`) y jerarquía territorial `CUT` (comuna) → `ID_DISTRITO` → `ID_ZONA` (urbano) / `MANZENT` (Entidades, Manzanas).

| Capa | Grano | Llave del grano | Filas nacional | Filas RM | Comunas RM cubiertas | Variables demográficas |
|---|---|---|---:|---:|---:|---|
| Comunal | comuna | `CUT` | 345 | 52 | 52/52 | No |
| Distrital | distrito censal | `ID_DISTRITO` | 2.762 | 451 | 52/52 | No |
| Zonal | zona urbana | `ID_ZONA` | 4.911 | 1.865 | 51/52 | Sí (n_per y ~150 más) |
| Entidades | entidad poblada rural | `MANZENT` | 28.415 | 2.072 | 26/52 | Sí (n_per y ~150 más) |
| Manzanas | manzana (urbana + Aldea rural) | `MANZENT` | 216.341 | 66.873 | 52/52 | Sí (n_per y ~150 más) |

- **Llave sin nulos ni duplicados:** verificado en las 5 capas, a nivel nacional y RM.
- **Dominio territorial:** el `CUT` de cada capa RM es subconjunto exacto de las 52 comunas oficiales (sin códigos espurios).
- **Jerarquía `ID_DISTRITO`:** en Zonal, Entidades y Manzanas, el 100% de los `ID_DISTRITO` usados existe en la capa Distrital RM (0 huérfanos).
- **Cobertura parcial de Zonal y Entidades no es un error de filtrado**, es un hecho de la fuente:
  - Zonal es exclusivamente urbana (`AREA_C='URBANO'`); falta San Pedro (`13505`), comuna sin zonas urbanas.
  - Entidades es exclusivamente rural dispersa (`AREA_C='RURAL'`, categorías "Parcela de Agrado", "Parcela-Hijuela", "Caserío", "Fundo-Estancia-Hacienda", etc.); está ausente en las 26 comunas más urbanizadas de la RM.
- **Geometrías:** 0 nulas en las 5 capas. Topológicamente inválidas (autointersección de anillo, según `shapely.is_valid`): 0 en Comunal/Distrital/Zonal/Entidades; **6 de 66.873 en Manzanas** (0,009%), en comunas Huechuraba, Colina, Peñalolén, Lo Barnechea, Peñaflor y Pirque (identificadas por `MANZENT` en el log de ejecución). No se corrigieron ni se descartaron: se documentan como limitación observada de la fuente.

### Diccionario oficial

`Diccionario_variables_geograficas_CPV24.xlsx` documenta **únicamente las variables geográficas y llaves** (una hoja por capa: `Comunal_CPV24`, `Distrital_CPV24`, `Zonal_CPV24`, `Entidades_CPV24`, `Manzanas_CPV24`, más Regional/Provincial/Limite_Urbano/Localidades/Aldeas). **No documenta las ~150 variables demográficas/socioeconómicas `n_*` ni `prom_*`** presentes en Zonal, Entidades y Manzanas (población, sexo, edad, discapacidad, vivienda, servicios básicos, etc.); su semántica se infiere del nombre de columna (autoexplicativo en la mayoría de los casos) pero no está definida formalmente en ningún artefacto de la fuente disponible. Se documenta como limitación, no se completa por inferencia.

`MZ_BASE_CENSO` (Manzanas y Entidades) sí está documentado: `1: con información, 0: sin información`. En RM, 16.352 de 66.873 manzanas (24,5%) tienen `MZ_BASE_CENSO=0` con `n_per=0` (no nulo) para esas filas. **No es posible determinar con esta fuente** si corresponden a manzanas efectivamente deshabitadas (industriales, áreas verdes, etc.) o a supresión estadística de conteos bajos; no se imputan.

---

## 3. Consistencia interna de variables demográficas

- `n_hombres + n_mujeres = n_per`: se cumple en el 100% de las filas RM de Zonal y Manzanas. **No se cumple en 2 de 2.072 filas de Entidades** (comunas 13201 y 13110): `n_per` está informado (18 y 123) pero `n_hombres`/`n_mujeres` son nulos. Se reporta, no se corrige ni se asume la igualdad como regla general.
- No negatividad: verificado, 0 valores negativos en `n_per`, `n_hombres`, `n_mujeres` en ninguna de las 3 capas con demografía.

---

## 4. Reconciliación poblacional subcomunal RM (cálculo reproducible)

Metodología: suma de `n_per` por capa/subconjunto en RM, contrastada contra `poblacion_censada` oficial por comuna (`data/processed/censo/dim_poblacion_comuna_censo2024.parquet`, tabulado INE D1, ya validado en `reports/eda/eda_censo_comunal.md`).

| Combinación | Suma `n_per` RM | % de 7.400.741 (población oficial RM) |
|---|---:|---:|
| Zonal (urbano) | 7.013.927 | 94,78% |
| Manzanas, `TIPO_MZ='ALDEA'` (rural nucleado) | 45.113 | 0,61% |
| Manzanas (total: urbano + Aldea) | 7.059.040 | 95,39% |
| Entidades (rural disperso, sin Aldeas) | 232.704 | 3,15% |
| **Manzanas + Entidades** | **7.291.744** | **98,53%** |

Hallazgos de la reconciliación (calculados por código sobre los Parquet RM publicados, no citados de un análisis previo):

1. **Manzanas urbanas (`TIPO_MZ='URBANO'`) coincide exactamente con Zonal** (7.013.927 = 7.013.927) en las 52 comunas. Esto confirma que Zonal es una agregación 1:1 de las manzanas urbanas y no una fuente poblacional independiente.
2. **Entidades y Manzanas-Aldea son conjuntos disjuntos**: 0 de 79 `ID_ENTIDAD` de manzanas tipo Aldea en RM coinciden con los 2.056 `ID_ENTIDAD` de la capa Entidades (verificado por intersección de identificadores, no por categoría). Ningún registro de Entidades RM tiene `CATEGORIA='Aldea'`. Por lo tanto, sumar Manzanas + Entidades **no duplica población** para RM según esta evidencia — aunque la instrucción de la tarea de no combinarlas automáticamente sigue siendo la política correcta por defecto, ya que esta verificación es específica de RM y no se extendió a nivel nacional.
3. **Brecha residual reproducible: 108.997 personas** (7.400.741 − 7.291.744), equivalente a 1,47% de la población oficial RM. Esta cifra se recalculó de forma independiente en esta sesión, no se citó de un análisis anterior.
4. **La brecha está distribuida de forma aproximadamente uniforme entre las 52 comunas** (rango 0,37%–6,22%, mediana ≈1,4%; ver CSV adjunto), sin concentrarse en outliers. Este patrón es más consistente con una diferencia sistemática de método/momento de tabulación entre el tabulado comunal oficial (D1, hoja "2") y las capas cartográficas (`n_per` embebido en el GeoParquet) que con supresión estadística localizada — pero **no es posible determinar la causa exacta con los datos disponibles**. Hipótesis no verificadas (se etiquetan explícitamente como tales, no como hechos):
   - Distinta fecha de corte/consolidación entre el tabulado poblacional D1 y la cartografía GEOPARQUET.
   - Personas censadas sin asignación geográfica subcomunal completa (p. ej. población en tránsito, colectivos, or errores de geocodificación al granular por manzana/entidad) que sí se contabilizan en el total comunal.
   - Redondeo o reglas de perturbación estadística aplicadas de forma diferente entre productos INE.

---

## 5. Recomendación para la futura capa de cobertura poblacional de isócronas

**No se implementa en esta tarea** (fuera de alcance explícito). Como insumo para esa decisión futura:

- **Manzanas** es la única capa que (a) cubre las 52 comunas, (b) tiene el grano más fino disponible (66.873 polígonos en RM) y (c) por sí sola ya captura el 95,39% de la población oficial (urbano + Aldea). Es la base más natural para un futuro cálculo de cobertura poblacional por isócrona.
- **Entidades** aporta un 3,15% adicional (rural disperso) pero solo cubre 26/52 comunas y con un grano de polígono más grande (entidad, no manzana) — su incorporación mejora cobertura poblacional pero a costa de granularidad espacial heterogénea dentro de una misma comuna.
- Ninguna combinación de capas disponibles alcanza el 100% de `poblacion_censada_2024`; cualquier cálculo de cobertura poblacional que use esta cartografía subcomunal deberá declarar explícitamente el denominador poblacional usado (p. ej. suma de `n_per` de las capas efectivamente utilizadas) en vez de asumir equivalencia con `poblacion_censada_2024` comunal.
- Esta recomendación es un insumo para una decisión posterior, no una implementación: no se calculan centroides, uniones espaciales con isócronas ni cobertura poblacional en esta tarea.

---

## 6. Limitaciones

1. El diccionario oficial no define las variables demográficas/socioeconómicas (§2); su interpretación por nombre de columna es razonable pero no está confirmada por la fuente.
2. La causa de la brecha de 108.997 personas (§4.3) no es determinable con los datos disponibles.
3. No es posible determinar si `MZ_BASE_CENSO=0` representa manzanas deshabitadas o supresión estadística.
4. 6 geometrías de Manzanas RM son topológicamente inválidas (autointersección); no afectan el conteo de filas ni las variables demográficas, pero podrían afectar operaciones geométricas exactas (área, intersección espacial) sobre esos 6 polígonos específicos.
5. Este informe cubre exclusivamente RM; los hallazgos de disyunción Entidades/Manzanas-Aldea (§4.2) y de brecha poblacional (§4.3) no se verificaron a nivel nacional.

---

## 7. Alcance no cubierto (documentado, no implementado)

El ZIP incluye además `Aldeas`, `Limite_Urbano`, `Localidades`, `Provincial` y `Regional`, no solicitados ni necesarios para el alcance actual (población subcomunal RM); no se publicaron como RAW. La capa Aldeas en particular sería redundante con la información ya presente en Manzanas (`TIPO_MZ='ALDEA'`) para el propósito de este informe.
