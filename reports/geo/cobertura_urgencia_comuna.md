# Cobertura territorial simple de la oferta de urgencia (RM)

Generado por el stage `build_cobertura_urgencia_comuna` (`src/geo/build_cobertura_urgencia_comuna.py`).
Dataset: `data/processed/geo/cobertura_urgencia_comuna.parquet`; diccionario en
[`reports/dictionary/diccionario_cobertura_urgencia_comuna.md`](../dictionary/diccionario_cobertura_urgencia_comuna.md).

## Método

- **Población:** manzanas (urbano) y entidades (rural) del Censo 2024, cada una representada por un punto interior (`point_on_surface`) y ponderada por su población censada (`n_per`).
- **Oferta:** los 175 establecimientos de `capa_oferta_urgencia_rm` (hospitales, SAPU, SAR, SUR y la excepción CEAR documentada). La variante `_id36` usa solo los 145 que reportaron atenciones de salud mental (ID36) en 2021-2025.
- **Distancia:** línea recta (haversine, radio medio terrestre) desde cada unidad censal al establecimiento más cercano, esté o no en la misma comuna.
- **Agregación:** por comuna de la unidad censal; la mediana, el percentil 90 y las proporciones están ponderados por población. Los umbrales de 2, 5, 10 km son descriptivos, no estándares normativos.

## Resultados RM

| Indicador | Valor |
|---|---|
| Población representada por las unidades censales | 7.291.744 de 7.400.741 (98,5%) |
| Población a ≤ 2 km en línea recta de un establecimiento | 6.269.853 (86,0%) |
| Población a ≤ 5 km en línea recta de un establecimiento | 7.049.387 (96,7%) |
| Población a ≤ 10 km en línea recta de un establecimiento | 7.235.888 (99,2%) |
| Comunas sin establecimiento de la oferta en su territorio | 0 |

Comunas con mayor distancia mediana: María Pinto (6,23 km); San Pedro (6,12 km); San José de Maipo (5,77 km); Isla de Maipo (3,29 km); Curacaví (2,64 km).

## Tabla comunal

| Comuna | Población 2024 | Establecimientos | Hab./establecimiento | Mediana km | P90 km | ≤ 2 km | ≤ 5 km | ≤ 10 km | Mediana km ID36 | ≤ 5 km ID36 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| María Pinto (13504) | 15.352 | 1 | 15.352 | 6,23 | 12,82 | 13,2% | 34,8% | 80,2% | 6,23 | 34,8% |
| San Pedro (13505) | 11.108 | 1 | 11.108 | 6,12 | 13,99 | 11,6% | 35,7% | 72,4% | 6,12 | 35,7% |
| San José de Maipo (13203) | 17.441 | 1 | 17.441 | 5,77 | 15,46 | 36,8% | 45,2% | 72,6% | 6,98 | 42,0% |
| Isla de Maipo (13603) | 39.274 | 2 | 19.637 | 3,29 | 5,21 | 33,5% | 87,5% | 99,9% | 3,29 | 87,5% |
| Curacaví (13503) | 35.165 | 1 | 35.165 | 2,64 | 11,73 | 32,8% | 66,2% | 79,4% | 2,64 | 66,2% |
| Calera de Tango (13403) | 25.491 | 1 | 25.491 | 2,41 | 3,98 | 34,2% | 96,5% | 100,0% | 2,41 | 96,5% |
| Paine (13404) | 78.828 | 2 | 39.414 | 2,33 | 10,12 | 46,0% | 69,0% | 89,3% | 2,33 | 69,0% |
| Pirque (13202) | 29.060 | 2 | 14.530 | 2,32 | 5,25 | 38,5% | 88,3% | 100,0% | 6,85 | 36,9% |
| Melipilla (13501) | 136.325 | 4 | 34.081 | 2,26 | 10,86 | 47,3% | 61,3% | 84,6% | 2,26 | 61,3% |
| Padre Hurtado (13604) | 81.243 | 1 | 81.243 | 2,18 | 3,78 | 45,0% | 94,5% | 100,0% | 2,18 | 94,5% |
| El Monte (13602) | 37.497 | 1 | 37.497 | 1,99 | 6,15 | 50,2% | 84,6% | 97,3% | 1,99 | 84,6% |
| Lo Barnechea (13115) | 112.620 | 1 | 112.620 | 1,97 | 4,49 | 50,4% | 94,1% | 99,5% | 1,97 | 94,0% |
| Vitacura (13132) | 86.420 | 1 | 86.420 | 1,96 | 3,07 | 51,6% | 100,0% | 100,0% | 4,32 | 83,7% |
| Lampa (13302) | 145.160 | 3 | 48.387 | 1,84 | 4,07 | 52,4% | 97,0% | 100,0% | 2,14 | 87,8% |
| Alhué (13502) | 7.768 | 1 | 7.768 | 1,83 | 12,04 | 51,8% | 58,4% | 72,0% | 1,83 | 58,4% |
| Las Condes (13114) | 296.134 | 4 | 74.034 | 1,81 | 2,78 | 57,6% | 100,0% | 100,0% | 2,75 | 100,0% |
| Colina (13301) | 173.293 | 2 | 86.646 | 1,72 | 7,48 | 57,5% | 70,7% | 97,3% | 1,72 | 67,6% |
| Buin (13402) | 116.969 | 4 | 29.242 | 1,51 | 4,76 | 66,1% | 90,7% | 100,0% | 1,51 | 90,7% |
| Tiltil (13303) | 19.742 | 2 | 9.871 | 1,23 | 9,76 | 54,4% | 75,7% | 92,5% | 1,23 | 75,7% |
| Maipú (13119) | 503.635 | 5 | 100.727 | 1,23 | 2,23 | 83,8% | 100,0% | 100,0% | 1,23 | 100,0% |
| Talagante (13601) | 76.429 | 4 | 19.107 | 1,16 | 4,74 | 76,0% | 90,4% | 100,0% | 1,16 | 90,4% |
| Macul (13118) | 123.800 | 1 | 123.800 | 1,10 | 1,65 | 98,5% | 100,0% | 100,0% | 1,10 | 100,0% |
| La Reina (13113) | 89.870 | 3 | 29.957 | 1,04 | 1,97 | 90,6% | 100,0% | 100,0% | 1,84 | 100,0% |
| San Miguel (13130) | 150.829 | 4 | 37.707 | 1,00 | 1,55 | 100,0% | 100,0% | 100,0% | 1,02 | 100,0% |
| Renca (13128) | 143.622 | 3 | 47.874 | 1,00 | 1,85 | 93,7% | 100,0% | 100,0% | 1,00 | 100,0% |
| Huechuraba (13107) | 101.808 | 2 | 50.904 | 0,98 | 2,14 | 87,4% | 100,0% | 100,0% | 0,98 | 100,0% |
| Quinta Normal (13126) | 129.351 | 2 | 64.676 | 0,97 | 1,36 | 100,0% | 100,0% | 100,0% | 0,97 | 100,0% |
| La Florida (13110) | 374.836 | 8 | 46.854 | 0,97 | 2,72 | 81,3% | 99,9% | 100,0% | 0,99 | 99,7% |
| Puente Alto (13201) | 568.086 | 11 | 51.644 | 0,94 | 1,72 | 95,3% | 100,0% | 100,0% | 1,12 | 99,3% |
| Cerrillos (13102) | 85.041 | 2 | 42.520 | 0,93 | 1,42 | 100,0% | 100,0% | 100,0% | 0,93 | 100,0% |
| Ñuñoa (13120) | 241.467 | 3 | 80.489 | 0,92 | 1,62 | 99,3% | 100,0% | 100,0% | 1,43 | 100,0% |
| Peñaflor (13605) | 94.402 | 3 | 31.467 | 0,91 | 2,06 | 89,4% | 100,0% | 100,0% | 0,91 | 100,0% |
| Quilicura (13125) | 205.624 | 3 | 68.541 | 0,88 | 1,79 | 95,6% | 100,0% | 100,0% | 0,88 | 100,0% |
| La Cisterna (13109) | 103.157 | 2 | 51.578 | 0,84 | 1,67 | 100,0% | 100,0% | 100,0% | 1,04 | 100,0% |
| San Bernardo (13401) | 306.371 | 8 | 38.296 | 0,83 | 2,06 | 89,5% | 97,7% | 100,0% | 0,83 | 97,7% |
| Peñalolén (13122) | 236.478 | 6 | 39.413 | 0,82 | 1,80 | 92,5% | 100,0% | 100,0% | 0,85 | 100,0% |
| La Pintana (13112) | 175.421 | 4 | 43.855 | 0,80 | 1,61 | 97,4% | 100,0% | 100,0% | 0,80 | 100,0% |
| Conchalí (13104) | 121.587 | 3 | 40.529 | 0,79 | 1,34 | 100,0% | 100,0% | 100,0% | 0,79 | 100,0% |
| San Joaquín (13129) | 95.602 | 2 | 47.801 | 0,79 | 1,16 | 100,0% | 100,0% | 100,0% | 0,79 | 100,0% |
| Recoleta (13127) | 154.615 | 4 | 38.654 | 0,77 | 1,26 | 100,0% | 100,0% | 100,0% | 0,77 | 100,0% |
| Pudahuel (13124) | 227.820 | 6 | 37.970 | 0,74 | 1,91 | 90,4% | 92,4% | 100,0% | 0,74 | 92,4% |
| El Bosque (13105) | 155.257 | 4 | 38.814 | 0,71 | 1,18 | 100,0% | 100,0% | 100,0% | 0,71 | 100,0% |
| Providencia (13123) | 143.974 | 8 | 17.997 | 0,71 | 1,28 | 100,0% | 100,0% | 100,0% | 0,90 | 100,0% |
| Estación Central (13106) | 181.049 | 3 | 60.350 | 0,71 | 1,21 | 99,9% | 100,0% | 100,0% | 1,25 | 100,0% |
| Santiago (13101) | 438.856 | 8 | 54.857 | 0,69 | 1,22 | 99,9% | 100,0% | 100,0% | 0,87 | 100,0% |
| Cerro Navia (13103) | 127.250 | 4 | 31.812 | 0,68 | 1,37 | 100,0% | 100,0% | 100,0% | 0,68 | 100,0% |
| La Granja (13111) | 112.022 | 3 | 37.341 | 0,67 | 1,07 | 100,0% | 100,0% | 100,0% | 0,67 | 100,0% |
| Pedro Aguirre Cerda (13121) | 96.062 | 3 | 32.021 | 0,67 | 1,06 | 100,0% | 100,0% | 100,0% | 0,67 | 100,0% |
| Lo Espejo (13116) | 87.295 | 4 | 21.824 | 0,64 | 1,00 | 100,0% | 100,0% | 100,0% | 0,65 | 100,0% |
| Independencia (13108) | 116.943 | 6 | 19.490 | 0,63 | 1,20 | 100,0% | 100,0% | 100,0% | 0,66 | 100,0% |
| Lo Prado (13117) | 91.290 | 4 | 22.822 | 0,53 | 0,90 | 100,0% | 100,0% | 100,0% | 0,53 | 100,0% |
| San Ramón (13131) | 76.002 | 4 | 19.000 | 0,52 | 1,27 | 100,0% | 100,0% | 100,0% | 0,52 | 100,0% |

## Limitaciones

- **Proximidad, no accesibilidad.** La distancia en línea recta subestima el recorrido real y no considera red vial, relieve, transporte público, horarios ni tiempos de viaje. Esa evaluación corresponde a OSM/GTFS e isócronas (NEXT-033/NEXT-034).
- **Disponibilidad, no capacidad.** Un establecimiento cuenta igual sin importar su tipo, horario, dotación o resolutividad en salud mental; no es una medida de capacidad ni de cupos.
- **Denominador poblacional.** Las unidades censales suman 98,5% de la población censada oficial; la brecha ya documentada en `clean_censo` no se imputa. Las proporciones de cobertura usan como denominador la población de las unidades, y `habitantes_por_establecimiento` usa la población oficial.
- **Unidades sin población y geometrías inválidas.** Se descartan 16.476 manzanas y 115 entidades con `n_per` = 0 (no pesan). 4 unidades pobladas tienen geometría inválida en la fuente; no se reparan y se representan por su centroide.
- **Efecto borde.** Solo se considera la oferta de la RM: la población cercana al límite regional podría tener un establecimiento más próximo en otra región.
- **Temporalidades distintas.** La población es el Censo 2024 y la oferta es el snapshot actual del catálogo DEIS; no representan el mismo instante.
- **Lectura ecológica.** Son métricas territoriales agregadas: no describen el acceso de ninguna persona ni se cruzan con Urgencias o Egresos a nivel de registro.
