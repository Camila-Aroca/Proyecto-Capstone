# Informe de Validación y Análisis Exploratorio (EDA)
## Cartografía Comunal Censo 2024 (GeoParquet)

**Fecha de ejecución:** 2026-08-26  
**Archivo analizado:** `data/raw/censo/Cartografia_censo2024_Pais_Comunal.parquet`  
**Auxiliar generado:** `reports/eda/comunas_rm_censo2024.csv`  

---

## 1. Resumen del Archivo

El archivo `Cartografia_censo2024_Pais_Comunal.parquet` contiene la cartografía vectorial oficial a nivel comunal para todo el territorio nacional de Chile, elaborada por el Instituto Nacional de Estadísticas (INE) para el Censo de Población y Vivienda 2024 en formato GeoParquet estándar.

- **Tamaño del archivo:** 125,790,972 bytes (119.96 MB).
- **Total de registros (filas):** 345 filas a nivel país.
- **Total de columnas:** 11 columnas.
- **Formato y Geometría:** GeoParquet con geometrías `MultiPolygon` codificadas en WKB en la columna `SHAPE`.
- **Sistema de Referencia de Coordenadas (CRS):** `SIRGAS 2000` (`EPSG:4674`), geodésico elipsoidal estándar para Chile.

---

## 2. Estructura del Dataset

### Esquema y Tipos de Datos
| Columna | Tipo de Dato | Descripción / Rol | Nulos |
|---|---|---|---|
| `OBJECTID` | `int64` | Identificador interno de objeto geográfico | 0 |
| `CUT` | `int32` | Código Único Territorial (código oficial de comuna) | 0 |
| `COD_REGION` | `int32` | Código numérico de la región (ej. 13 para RM) | 0 |
| `REGION` | `string` | Nombre oficial de la región | 0 |
| `COD_PROVINCIA` | `int32` | Código numérico de la provincia | 0 |
| `PROVINCIA` | `string` | Nombre oficial de la provincia | 0 |
| `COMUNA` | `string` | Nombre oficial de la comuna | 0 |
| `SHAPE_Length` | `double` | Perímetro geométrico del polígono (grados) | 0 |
| `SHAPE_Area` | `double` | Área geométrica del polígono (grados cuadrados) | 0 |
| `SHAPE` | `binary` (WKB) | Geometría vectorial `MultiPolygon` | 0 |
| `SHAPE_bbox` | `struct` | Bounding box precalculado (`xmin`, `ymin`, `xmax`, `ymax`) | 0 |

---

## 3. Cobertura Territorial

El dataset abarca las 16 regiones político-administrativas del país y 56 provincias:

- **Total comunas nacionales:** 345 registros comunales.
- **Distribución por región:**
  - Región Metropolitana (`COD_REGION = 13`): 52 comunas (15.1% del total nacional).
  - Resto de regiones (`COD_REGION != 13`): 293 comunas (84.9% del total nacional).
- **Identificación de la Región Metropolitana en los datos:**
  - Código numérico: `COD_REGION == 13`
  - Glosa de región: `REGION == 'METROPOLITANA DE SANTIAGO'`
  - Códigos comunales `CUT`: Rango `[13101, 13605]`

---

## 4. Validación de las 52 Comunas de la Región Metropolitana

Se comparó el subconjunto de la Región Metropolitana contra la nómina oficial del Código Único Territorial (CUT) de la Subsecretaría de Desarrollo Regional y Administrativo (SUBDERE) y el INE:

| Métrica de Validación | Valor | Estado |
|---|---|---|
| **Comunas oficiales esperadas en RM** | **52** | Referencia base oficial |
| **Comunas RM encontradas en el dataset** | **52** | 100.0% de presencia |
| **Comunas RM faltantes** | **0** | Ninguna comuna ausente |
| **Comunas adicionales / espurias en RM** | **0** | Ninguna |
| **Registros geométricos por comuna** | **Exactamente 1 polígono por comuna** | Sin particiones ni duplicados |

### Desglose por Provincia (RM):
1. **Provincia de Santiago (`COD_PROVINCIA = 131`):** 32 comunas (Santiago, Cerrillos, Cerro Navia, Conchalí, El Bosque, Estación Central, Huechuraba, Independencia, La Cisterna, La Florida, La Granja, La Pintana, La Reina, Las Condes, Lo Barnechea, Lo Espejo, Lo Prado, Macul, Maipú, Ñuñoa, Pedro Aguirre Cerda, Peñalolén, Providencia, Pudahuel, Quilicura, Quinta Normal, Recoleta, Renca, San Joaquín, San Miguel, San Ramón, Vitacura).
2. **Provincia de Cordillera (`COD_PROVINCIA = 132`):** 3 comunas (Puente Alto, Pirque, San José de Maipo).
3. **Provincia de Chacabuco (`COD_PROVINCIA = 133`):** 3 comunas (Colina, Lampa, Tiltil).
4. **Provincia de Maipo (`COD_PROVINCIA = 134`):** 4 comunas (San Bernardo, Buin, Calera de Tango, Paine).
5. **Provincia de Melipilla (`COD_PROVINCIA = 135`):** 5 comunas (Melipilla, Alhué, Curacaví, María Pinto, San Pedro).
6. **Provincia de Talagante (`COD_PROVINCIA = 136`):** 5 comunas (Talagante, El Monte, Isla de Maipo, Padre Hurtado, Peñaflor).

*(El listado completo con códigos CUT, áreas y provincias se encuentra en [`reports/eda/comunas_rm_censo2024.csv`](eda/comunas_rm_censo2024.csv)).*

---

## 5. Auditoría de Calidad de Datos

| Control de Calidad | Resultado | Estado |
|---|---|---|
| **Valores nulos en cualquier columna** | **0** en las 11 columnas | Excelente |
| **Duplicados en clave `CUT` (nacional y RM)** | **0** (claves 100% únicas) | Correcto |
| **Duplicados en `OBJECTID`** | **0** | Correcto |
| **Geometrías nulas / vacías** | **0** | Correcto |
| **Geometrías topológicamente inválidas** | **0** (todas válidas según OGC/Shapely) | Correcto |
| **Consistencia CUT vs Nombre Comunal** | 100% concordante con estándar SUBDERE | Correcto |

---

## 6. Hallazgos y Limitaciones

1. **Estructura Geoespacial Limpia:** La capa comunal está lista para operaciones espaciales (joins espaciales, cálculo de centroides y agregaciones comunales de demanda).
2. **Sistema de Coordenadas:** Las geometrías están en coordenadas geográficas elipsoidales (`EPSG:4674`). Para análisis métricos de distancias euclidianas o áreas proyectadas precisas, se recomienda proyectar a `UTM Huso 19 Sur` (`EPSG:32719` o `EPSG:5361`) al cruzar con isócronas y red vial en `src/geo/`.
3. **Compatibilidad con Establecimientos DEIS:** Los códigos `CUT` de esta capa comunal coinciden exactamente con los códigos `comuna_codigo` normalizados en `data/processed/establecimientos_rm_clean.csv`.

---

## 7. Conclusión

- **¿El archivo contiene las 52 comunas de la RM?** **SÍ**, las 52 comunas de la Región Metropolitana de Santiago están presentes de manera unívoca y completa.
- **¿Existen errores de integridad o geometrías corruptas?** **NO**, la totalidad de los polígonos son válidos y no existen valores nulos ni duplicados en los identificadores territoriales.
- **Veredicto Técnico:** El archivo cumple todos los requisitos de calidad e integridad territorial para servir como capa base comunal en los módulos geoespaciales y de demanda del proyecto.
