# Evaluación OSM/GTFS e isócronas (NEXT-033)

**Fecha:** 2026-10-12 · **Issue:** #59 · **Desbloquea:** #60 (NEXT-034)

**Decisión:** para el MVP se implementan **tiempos de viaje en automóvil sobre la red vial OSM**, calculados localmente con un snapshot versionado de OpenStreetMap y un Dijkstra multi-origen de `scipy` (ya declarado en `requirements.txt`). **GTFS (transporte público) queda fuera del MVP.** El detalle y la justificación siguen.

---

## 1. Punto de partida

El MVP de cobertura simple (`build_cobertura_urgencia_comuna`, NEXT-032) ya mide la distancia en línea recta de la población censal 2024 a los 175 establecimientos de la oferta de urgencia. Para la RM completa:

| Indicador (línea recta) | Valor |
|---|---|
| Población a ≤ 2 km | 86,0 % |
| Población a ≤ 5 km | 96,7 % |
| Población a ≤ 10 km | 99,2 % |
| Costo de cálculo | ~1 s, 52.354 unidades censales × 175 establecimientos, sin dependencias nuevas |

Fuente: [`cobertura_urgencia_comuna.md`](cobertura_urgencia_comuna.md).

En las comunas urbanas del Gran Santiago, la mediana es de 0,5 a 1,2 km y prácticamente toda la población está a menos de 5 km. Las brechas se concentran en comunas rurales y de cordillera, como María Pinto, San Pedro, San José de Maipo, Curacaví, Alhué, Melipilla y Paine, con medianas de 1,8 a 6,2 km y percentiles 90 de 10 a 15 km.

Ahí es donde la línea recta se aleja más del recorrido real: hay valles, cerros y pocos caminos. Ese es el único lugar donde una métrica de red cambia la lectura del producto. Es una **inferencia**: se confirmará al comparar ambas métricas en #60.

## 2. Fuentes de datos evaluadas

| Fuente | Qué aporta | Tamaño | Licencia | Cobertura RM | Observaciones |
|---|---|---|---|---|---|
| OpenStreetMap, extracto Chile de Geofabrik (`chile-latest.osm.pbf`) | Red vial (calles, tipo de vía, sentido, `maxspeed` cuando existe) | 333 MB (snapshot 2026-10-11) | ODbL 1.0 (atribución requerida) | Toda la región, urbana y rural | Se actualiza a diario: hay que fijar el snapshot por SHA256 en `data/raw/`, igual que las demás fuentes |
| GTFS DTPM, vía MobilityDatabase `mdb-3357` | Horarios y paradas de Red Metropolitana de Movilidad, Metro, EFE y bus al aeropuerto | 10,25 MB comprimido, 66,41 MB descomprimido; 427 rutas | Términos en dtpm.cl | Solo los operadores listados | Vigencia 2026-07-04 a 2026-12-31: el feed se reemplaza cada pocos meses. No incluye buses rurales ni interurbanos, que son justamente los de las comunas con brecha |

## 3. Alternativas técnicas y costo computacional

Las cifras de terceros se citan como reportadas. Las marcadas como **estimación** son órdenes de magnitud por medir en #60, no mediciones de este proyecto.

| Opción | Modo | Dependencias | Costo computacional | Reproducibilidad | Veredicto |
|---|---|---|---|---|---|
| **A. Red OSM local + Dijkstra multi-origen (`pyosmium` + `scipy.sparse.csgraph`)** | Auto | `osmium` (pyosmium, wheel de pip); `scipy` ya está | Parseo del PBF: minutos. Red RM: del orden de 10⁵–10⁶ nodos (**estimación**). Un único Dijkstra desde los 175 establecimientos a la vez da el tiempo al más cercano para todos los nodos: segundos. RAM < 4 GB (**estimación**) | Alta: snapshot PBF con SHA256 y velocidades por tipo de vía versionadas en código | **Elegida** |
| B. OSMnx (descarga por Overpass API) | Auto / caminata | `osmnx` (+ geopandas, pyproj, networkx) | Viable para la RM, pero `networkx` es más lento que `scipy` | Baja: Overpass devuelve el estado actual de OSM, sin snapshot fijo | Descartada por reproducibilidad y dependencias |
| C. openrouteservice API | Auto / caminata | Cliente HTTP + API key | 175 establecimientos ≈ 175 solicitudes; el plan gratuito permite 500 isócronas/día y 20/min (2.500/día en plan colaborativo académico) | Baja: grafo del proveedor no versionado; requiere secreto | Solo como validación cruzada opcional |
| D. OSRM / Valhalla autoalojado | Auto | Docker + servicio de ruteo | `osrm-extract` usa ~7 GB RAM para Gran Bretaña (reportado); Chile es menor, pero exige un servicio extra en la nube | Media | Desproporcionado para 175 orígenes |
| E. r5py (R5, multimodal con GTFS) | Transporte público + caminata | `r5py` + **JDK ≥ 21** | Matriz 52 mil orígenes × 175 destinos por cada hora de salida evaluada; cómputo de minutos a horas y varios GB de RAM (**estimación**). Agrega Java a la imagen del pipeline | Media: GTFS mutable cada pocos meses | Fuera del MVP |

### Por qué A y no un servicio de ruteo

El problema del MVP es "tiempo de cada unidad censal al establecimiento más cercano", no "ruta entre dos puntos arbitrarios". Eso es un **camino mínimo multi-origen**: se agrega un nodo virtual unido a los 175 establecimientos y se corre un Dijkstra una sola vez sobre la red, en vez de 175 isócronas o 9 millones de pares origen-destino.

`scipy.sparse.csgraph.dijkstra(..., indices=establecimientos, min_only=True)` lo hace sin servicios externos. Los polígonos de isócrona para el mapa salen después de los mismos tiempos por nodo, umbralizándolos.

## 4. Alcance MVP propuesto para #60

**Incluye:**

1. **Ingesta OSM.** Un stage `download_osm` descarga el PBF de Chile de Geofabrik a staging, lo valida, registra URL, timestamp, tamaño y SHA256 en `provenance_manifest.json` y lo publica en `data/raw/osm/`. Se trata como fuente mutable sin versionado: `--force` pide un snapshot nuevo.
2. **Red vial RM en automóvil.**
   - Se recorta la red a la RM con el bbox de la capa comunal más un margen, para no cortar rutas que salen de la región.
   - Los tipos de vía conducibles (`highway`) y sus velocidades por defecto quedan como tabla versionada en código.
   - Se respeta `oneway` y se usa `maxspeed` solo cuando el tag está.
3. **Tiempo al establecimiento más cercano.**
   - Dijkstra multi-origen desde los 175 establecimientos.
   - Variante solo con los 145 que reportaron ID36, igual que en la cobertura simple.
   - Cada unidad censal se ancla a su nodo vial más cercano y se registra la distancia del anclaje como control de calidad.
4. **Salidas.**
   - Por comuna: tiempo mediano y p90 ponderados por población, y proporción de población a ≤ 10, 20 y 30 min.
   - Polígonos de isócrona por establecimiento priorizado para el mapa. Proponemos los de comunas con brecha y los que reportan ID36. La priorización se fija en #60.
   - Reporte con comparación línea recta vs red y limitaciones.

**No incluye:**

- GTFS ni transporte público.
- Tiempos con congestión u horario.
- Rutas de ambulancia.
- Oferta de otras regiones (el efecto borde se mantiene documentado).

**Criterio de aceptación sugerido para #60:**

- Isócronas reproducibles desde un snapshot OSM identificado por SHA256.
- Ninguna unidad censal sin nodo alcanzable, o las que queden se informan sin imputarlas.
- Tiempos y RAM reales medidos y reportados (reemplazan las estimaciones de la sección 3).

## 5. Por qué GTFS queda fuera del MVP

1. **No cubre las comunas con brecha.** El feed DTPM no incluye buses rurales ni interurbanos, que son los relevantes en María Pinto, San Pedro, Alhué o Curacaví. En el Gran Santiago, donde sí hay GTFS, la línea recta ya muestra cobertura casi total a ≤ 5 km.
2. **Costo desproporcionado.** Requiere JDK 21 en el pipeline y en la imagen `saad-pipeline`, y un cómputo por hora de salida mucho mayor que el Dijkstra en automóvil.
3. **Fuente mutable de corta vigencia.** El feed actual vence el 2026-12-31; habría que versionar y refrescar otro snapshot.
4. **Encaje en el alcance.** La consulta de urgencia en salud mental suele ocurrir en crisis, donde el traslado en vehículo es al menos tan relevante como el transporte público. Esto es una **hipótesis de uso**, no un dato del proyecto, y se puede revisar con el usuario piloto.

GTFS puede retomarse post-MVP con r5py si la validación con usuario muestra que el tiempo en transporte público en el Gran Santiago es una pregunta que el producto debe responder.

## 6. Limitaciones que persistirán con la red vial

- Velocidades nominales por tipo de vía, sin congestión: el tiempo real será mayor en horas punta.
- Calidad desigual de OSM en caminos rurales: tags incompletos o vías no mapeadas. Se puede medir con la distancia de anclaje de las unidades censales.
- Accesibilidad física al establecimiento, no capacidad ni disponibilidad de atención en salud mental.
- Métricas ecológicas por comuna, sin cruce con Urgencias ni Egresos a nivel de registro.

## Fuentes

- [Geofabrik, extracto Chile de OpenStreetMap](https://download.geofabrik.de/south-america/chile.html): tamaño, fecha y licencia ODbL.
- [MobilityDatabase, feed GTFS DTPM `mdb-3357`](https://mobilitydatabase.org/feeds/gtfs/mdb-3357): operadores, vigencia, tamaño y rutas. Licencia en [dtpm.cl](https://www.dtpm.cl/index.php/gtfs-vigente).
- [r5py, instalación](https://r5py.readthedocs.io/stable/user-guide/installation/installation.html): requiere JDK ≥ 21.
- [openrouteservice, planes](https://openrouteservice.org/plans/): cuotas de isócronas.
- [Uso de memoria de OSRM con extractos grandes](https://datawookie.dev/blog/2017/11/using-large-maps-with-osrm/).
- [OSMnx, isócronas (G. Boeing)](https://geoffboeing.com/2017/08/isochrone-maps-osmnx-python/).
