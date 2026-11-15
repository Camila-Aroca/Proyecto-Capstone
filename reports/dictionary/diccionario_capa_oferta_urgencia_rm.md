# Diccionario de datos: `capa_oferta_urgencia_rm`

- **Ruta:** `data/processed/geo/capa_oferta_urgencia_rm.parquet` (GeoParquet, puntos, EPSG:4674 SIRGAS 2000).
- **Constructor:** `src/geo/build_capa_oferta_urgencia_rm.py`, stage `build_capa_oferta_urgencia_rm` (upstream: `clean_censo`, `build_dim_oferta_urgencia_rm`). Downstream: `build_cobertura_urgencia_comuna`.
- **Propósito:** oferta de urgencia como puntos georreferenciados, base geoespacial de la cobertura territorial simple. No calcula distancias, cobertura ni isócronas.
- **Fuente:** `dim_oferta_urgencia_rm` (coordenadas del maestro de establecimientos) y la capa comunal del Censo 2024.

**Grano:** una fila por establecimiento de `dim_oferta_urgencia_rm` (174 filas en el snapshot vigente). **Llave lógica verificada:** `establecimiento_codigo` (1 a 1 con la oferta).

| Columna | Tipo | Semántica |
|---|---|---|
| `establecimiento_codigo` | int64 | Código DEIS del establecimiento. |
| `comuna_codigo` | string | Comuna declarada en la oferta (5 dígitos). Copia, no se corrige. |
| `comuna_codigo_espacial` | string | Comuna de la capa comunal que contiene el punto (join punto-en-comuna). Nula sin coordenadas. |
| `resultado_join_comuna` | string | `coincide`, `difiere`, `fuera_de_rm`, `limite_ambiguo` o `sin_coordenadas`. Marca la discrepancia; no la corrige. |
| `geometry` | binary (WKB) | Punto del establecimiento. Nulo si `resultado_join_comuna = sin_coordenadas`; no se imputan ni geocodifican coordenadas. |

## Construcción y validación

1. Se toman los establecimientos de la oferta con longitud y latitud y se construye el punto sin reproyectar.
2. El join punto-en-comuna asigna `comuna_codigo_espacial`; `coincide` exige igualdad con `comuna_codigo` (la etapa falla si no se cumple) y el resultado debe pertenecer al dominio declarado.
3. En el snapshot vigente: 173 `coincide` y 1 `sin_coordenadas`.

## Advertencias de interpretación

- Un punto sin coordenadas queda fuera de las distancias de cobertura; la lista de casos está en `data/processed/geo/establecimientos_coordenadas_resolucion.csv`.
- Es un snapshot actual de la oferta, no un histórico.
