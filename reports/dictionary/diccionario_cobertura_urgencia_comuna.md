# Diccionario de datos: `cobertura_urgencia_comuna`

- **Ruta:** `data/processed/geo/cobertura_urgencia_comuna.parquet`
- **Constructor:** `src/geo/build_cobertura_urgencia_comuna.py` (`build_cobertura_urgencia_comuna`), stage `build_cobertura_urgencia_comuna` en `PIPELINE.md`.
- **Reporte con resultados y limitaciones:** [`reports/geo/cobertura_urgencia_comuna.md`](../geo/cobertura_urgencia_comuna.md), generado por el mismo stage.
- **Grano:** una fila = una comuna de la Región Metropolitana. **52 filas, 52 `comuna_codigo` únicos.** El universo es `dim_poblacion_comuna_censo2024`.
- **Qué mide:** proximidad en línea recta de la población censada 2024 a la oferta de urgencia actual (`capa_oferta_urgencia_rm`). **No es accesibilidad**: no usa red vial, transporte público ni tiempos de viaje (eso corresponde a OSM/GTFS e isócronas).

## Construcción

- **Población:** manzanas y entidades de `Cartografia_censo2024_RM_Manzanas/Entidades.parquet` con `n_per > 0`, cada una como un punto interior (`shapely.point_on_surface`) con peso `n_per`. Ambas capas no comparten `MANZENT`, así que la población no se cuenta dos veces. Las unidades con geometría inválida en la fuente no se reparan: se representan por su centroide.
- **Asignación a comuna:** por el `CUT` de la unidad censal, no por un join espacial.
- **Distancia:** haversine (radio medio terrestre 6.371,0088 km) desde cada unidad al establecimiento más cercano de la oferta, esté en la misma comuna o en otra. Solo se consideran establecimientos de la RM.
- **Variante ID36:** igual, pero solo con los establecimientos de `dim_oferta_urgencia_rm` con `reporto_id36_periodo = True` (reportaron atenciones de salud mental en 2021-2025).
- **Cuantiles ponderados:** menor distancia cuya población acumulada alcanza la fracción pedida (0,5 o 0,9) del total de la comuna.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `comuna_codigo` | string | CUT de 5 dígitos (`13xxx`). |
| `comuna_glosa` | string | Nombre de la comuna, desde `dim_poblacion_comuna_censo2024`. |
| `poblacion_censada_2024` | int64 | Población censada oficial de la comuna (INE, Censo 2024). |
| `poblacion_unidades_censales` | int64 | Suma de `n_per` de las manzanas y entidades pobladas de la comuna. Es el denominador de todas las proporciones. |
| `proporcion_poblacion_representada` | float64 | `poblacion_unidades_censales / poblacion_censada_2024`. Mide la brecha entre la cartografía y la población oficial (documentada en `clean_censo`); no se corrige. |
| `n_unidades_censales_pobladas` | int64 | Manzanas + entidades con `n_per > 0`. |
| `n_oferta_urgencia_en_comuna` | int64 | Establecimientos de la oferta con `comuna_codigo` en la comuna. 0 es un hecho observado, no un dato faltante. |
| `habitantes_por_establecimiento` | float64 (nulable) | `poblacion_censada_2024 / n_oferta_urgencia_en_comuna`. NULL si la comuna no tiene establecimientos. No pondera por tipo ni capacidad. |
| `distancia_media_km` | float64 | Distancia media ponderada por población al establecimiento más cercano. |
| `distancia_mediana_km` | float64 | Mediana ponderada: la mitad de la población vive a esta distancia o menos. |
| `distancia_p90_km` | float64 | Percentil 90 ponderado: distancia de la población más alejada. |
| `proporcion_poblacion_a_2km` | float64 | Fracción de `poblacion_unidades_censales` a ≤ 2 km en línea recta. |
| `proporcion_poblacion_a_5km` | float64 | Ídem a ≤ 5 km. |
| `proporcion_poblacion_a_10km` | float64 | Ídem a ≤ 10 km. |
| `distancia_mediana_id36_km` | float64 | Mediana ponderada respecto de la oferta que reportó ID36. Siempre ≥ `distancia_mediana_km`. |
| `proporcion_poblacion_a_5km_id36` | float64 | Fracción a ≤ 5 km de un establecimiento que reportó ID36. |

## Validaciones antes de publicar

52 comunas únicas; ninguna sin unidades censales pobladas; distancias no negativas; proporciones en [0, 1] y crecientes con el umbral; mediana ≤ p90; mediana ID36 ≥ mediana general; suma de `n_oferta_urgencia_en_comuna` igual al número de establecimientos de la oferta.

## Advertencias de interpretación

- Los umbrales de 2, 5 y 10 km son descriptivos, no estándares normativos de acceso.
- La línea recta subestima el recorrido real, sobre todo en comunas rurales, de cordillera o con barreras (ríos, autopistas, cerros).
- Un establecimiento cuenta igual sin importar tipo, horario, dotación o resolutividad en salud mental.
- Efecto borde: la población cerca del límite regional podría tener un establecimiento más próximo en otra región, que no se considera.
- La población (Censo 2024) y la oferta (snapshot actual del catálogo DEIS) tienen temporalidades distintas.
- Son métricas ecológicas: no describen el acceso de personas ni se cruzan con Urgencias o Egresos a nivel de registro.
