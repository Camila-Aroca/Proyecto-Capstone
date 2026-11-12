# Contrato de datos API / frontend: comparación (#61)

- **Fecha (UTC):** 2026-11-12T15:27:52+00:00 · **Commit:** `95d00f8`
- **Contrato de la API:** [`docs/06-requisitos/contrato_api/openapi.json`](../../../docs/06-requisitos/contrato_api/openapi.json) (OpenAPI 3.1.0, 15 rutas, 38 esquemas), generado desde `src/api/schemas.py`.
- **Tipos del frontend:** `frontend/src/api.ts` (33 interfaces, 14 llamadas).
- **Ejecutado con:** `scripts/qa_contrato_api.py`

**Resultado:** 0 errores · 12 advertencias · 9 observaciones.

- **ERROR:** el frontend puede fallar o mostrar datos incorrectos (campo esperado que no llega, null no admitido, tipo distinto).
- **ADVERTENCIA:** diferencia sin falla inmediata en la app, pero que deja el contrato incompleto (p. ej. errores no declarados en el OpenAPI).
- **INFO:** diferencia inocua (campos que el frontend ignora, valores o nulos admitidos de forma defensiva, rutas sin uso).

Criterio: la API serializa todos los campos de cada modelo, incluidos los que tienen valor por defecto (no usa `exclude_none` ni `exclude_unset`), así que un campo "opcional" en el esquema siempre llega, con su valor o `null`.

## Endpoints, filtros y errores

| Llamada del frontend | Ruta | Respuesta (API → frontend) | Filtros (obligatorio) | Errores posibles | Manejo en el frontend |
|---|---|---|---|---|---|
| `api.caracterizacion` | `GET /api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` | `Caracterizacion` → `Caracterizacion` | `semanas` * | 404, 409, 422, 503 | Caracterizacion.tsx: muestra el mensaje de error |
| `api.salud` | `GET /api/v1/salud` | `Salud` → `Salud` | — | — | — |
| `api.meta` | `GET /api/v1/meta` | `Meta` → `Meta` | — | 503 (503 con Retry-After: se reintenta) | Landing.tsx: se ignora (la vista sigue sin ese dato); Tablero.tsx: muestra el mensaje de error; Tablero.tsx: se ignora (la vista sigue sin ese dato) |
| `api.territorios` | `GET /api/v1/territorios` | `Territorio[]` → `Territorio[]` | — | 503 (503 con Retry-After: se reintenta) | Tablero.tsx: muestra el mensaje de error |
| `api.serie` | `GET /api/v1/series/{series_id}` | `SerieConPronostico` → `SerieConPronostico` | `semanas` | 404, 422, 503 (503 con Retry-After: se reintenta) | Tablero.tsx: muestra el mensaje de error |
| `api.camasPsiquiatria` | `GET /api/v1/camas-psiquiatria/{series_id}` | `CamasPsiquiatriaTerritorio` → `CamasPsiquiatria` | — | 404, 422, 503 (503 con Retry-After: se reintenta) | Tablero.tsx: se ignora (la vista sigue sin ese dato) |
| `api.resumenComunal` | `GET /api/v1/resumen-comunal` | `ResumenComuna[]` → `ResumenComuna[]` | — | 503 (503 con Retry-After: se reintenta) | Tablero.tsx: muestra el mensaje de error |
| `api.geoComunas` | `GET /api/v1/geo/comunas` | `GeoJSON (sin esquema)` → `GeoJSON.FeatureCollection` | — | 503 (503 con Retry-After: se reintenta) | Tablero.tsx: muestra el mensaje de error |
| `api.hospitalizacionesResidentes` | `GET /api/v1/hospitalizaciones-residentes/{series_id}` | `HospitalizacionesResidentes` → `HospitalizacionesResidentes` | `ano` | 404, 422, 503 | PanelHospitalizaciones.tsx: muestra el mensaje de error |
| `api.suicidios` | `GET /api/v1/suicidios/{series_id}` | `SerieSuicidios` → `SerieSuicidios` | `semanas` | 404, 422, 503 (503 con Retry-After: se reintenta) | Tablero.tsx: muestra el mensaje de error |
| `api.calendarioEventos` | `GET /api/v1/calendario-eventos` | `EventoCalendario[]` → `EventoCalendario[]` | `desde` *, `hasta` * | 422 | Tablero.tsx: se ignora (la vista sigue sin ese dato) |
| `api.establecimientos` | `GET /api/v1/establecimientos` | `EstablecimientoResumen[]` → `EstablecimientoResumen[]` | — | 503 (503 con Retry-After: se reintenta) | Tablero.tsx: se ignora (la vista sigue sin ese dato); VistaEstablecimientos.tsx: muestra el mensaje de error |
| `api.metaEstablecimientos` | `GET /api/v1/establecimientos-meta` | `MetaEstablecimientos` → `MetaEstablecimientos` | — | 503 (503 con Retry-After: se reintenta) | Landing.tsx: se ignora (la vista sigue sin ese dato); VistaEstablecimientos.tsx: muestra el mensaje de error |
| `api.establecimiento` | `GET /api/v1/establecimientos/{codigo}` | `EstablecimientoDetalle` → `EstablecimientoDetalle` | `semanas` | 404, 422, 503 (503 con Retry-After: se reintenta) | VistaEstablecimientos.tsx: muestra el mensaje de error |

**Manejo común de errores del cliente** (`obtener` en `frontend/src/api.ts`):
- Un 503 con `Retry-After` significa "calculando": el cliente espera y reintenta (hasta 30 veces).
- Cualquier otro error se convierte en `ErrorApi` con el `detail` de la API. Cada vista decide si lo muestra o lo ignora (columna anterior).

## Errores (0)

- Ninguno.

## Advertencias (12)

- `/api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` · `(errores)`: Lanza 404, 409, 503 y el OpenAPI no lo declara (solo 200, 422).
- `/api/v1/meta` · `(errores)`: Lanza 503 y el OpenAPI no lo declara (solo 200).
- `/api/v1/territorios` · `(errores)`: Lanza 503 y el OpenAPI no lo declara (solo 200).
- `/api/v1/series/{series_id}` · `(errores)`: Lanza 404, 503 y el OpenAPI no lo declara (solo 200, 422).
- `/api/v1/camas-psiquiatria/{series_id}` · `(errores)`: Lanza 404, 503 y el OpenAPI no lo declara (solo 200, 422).
- `/api/v1/resumen-comunal` · `(errores)`: Lanza 503 y el OpenAPI no lo declara (solo 200).
- `/api/v1/geo/comunas` · `(errores)`: Lanza 503 y el OpenAPI no lo declara (solo 200).
- `/api/v1/hospitalizaciones-residentes/{series_id}` · `(errores)`: Lanza 404, 503 y el OpenAPI no lo declara (solo 200, 422).
- `/api/v1/suicidios/{series_id}` · `(errores)`: Lanza 404, 503 y el OpenAPI no lo declara (solo 200, 422).
- `/api/v1/establecimientos` · `(errores)`: Lanza 503 y el OpenAPI no lo declara (solo 200).
- `/api/v1/establecimientos-meta` · `(errores)`: Lanza 503 y el OpenAPI no lo declara (solo 200).
- `/api/v1/establecimientos/{codigo}` · `(errores)`: Lanza 404, 503 y el OpenAPI no lo declara (solo 200, 422).

## Observaciones (9)

- `/api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` · `codigo`: La API lo envía y el frontend no lo tipa (lo ignora).
- `/api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` · `fuente`: La API lo envía y el frontend no lo tipa (lo ignora).
- `/api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` · `nivel`: La API lo envía y el frontend no lo tipa (lo ignora).
- `/api/v1/meta` · `cobertura_holdout[].nivel`: Valores distintos: solo en API —, solo en frontend ['establecimiento'].
- `/api/v1/territorios` · `[].nivel`: Valores distintos: solo en API —, solo en frontend ['establecimiento'].
- `/api/v1/series/{series_id}` · `nivel`: Valores distintos: solo en API —, solo en frontend ['establecimiento'].
- `/api/v1/suicidios/{series_id}` · `nivel`: Valores distintos: solo en API —, solo en frontend ['establecimiento'].
- `/api/v1/suicidios/{series_id}` · `pronostico[].cobertura_esperada`: La API lo envía y el frontend no lo tipa (lo ignora).
- `/api/v1/pronosticos` · `(ruta)`: La API expone la ruta y el frontend no la usa.
