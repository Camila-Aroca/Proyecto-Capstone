# Contrato de datos de la API

[`openapi.json`](openapi.json) es el contrato versionado de la API del SAAD (OpenAPI 3.1). No se escribe a mano: lo genera FastAPI desde los modelos Pydantic de [`src/api/schemas.py`](../../../src/api/schemas.py), así que describe exactamente las rutas, los parámetros (filtros) y los campos de cada respuesta que la API implementa.

El frontend consume la API con los tipos de [`frontend/src/api.ts`](../../../frontend/src/api.ts), escritos a mano. La correspondencia entre ambos lados, los errores que lanza cada ruta y cómo los maneja el frontend están en [`reports/validation/contrato_api/comparacion_api_frontend.md`](../../../reports/validation/contrato_api/comparacion_api_frontend.md).

Regenerar el contrato y la comparación después de cambiar la API o el frontend:

```bash
.venv/bin/python scripts/qa_contrato_api.py
```

El script termina con código distinto de cero si encuentra errores de contrato: campos que el frontend espera y la API no envía, valores nulos no admitidos, tipos distintos o rutas inexistentes.

Reglas del contrato que no expresa el OpenAPI:

- **Todos los campos llegan siempre.** La API serializa cada campo del modelo, también los que tienen valor por defecto. Un dato ausente llega como `null` y el frontend lo muestra como "sin dato", nunca como 0.
- **503 con `Retry-After` significa "calculando".** El cliente espera y reintenta. Un 503 sin ese encabezado significa que falta un output del pipeline, y su `detail` indica qué stage ejecutar.
- **404** indica un territorio o establecimiento inexistente. **422** indica parámetros fuera de rango.

## Errores por ruta

**Decisión del equipo (issue #61):** los errores 404, 409 y 503 no se declaran en el OpenAPI. FastAPI solo publica en él las respuestas 200 y 422; el resto se documenta en esta tabla, que se obtiene del código de `src/api/` con `scripts/qa_contrato_api.py`. El comportamiento está implementado y el frontend lo maneja; lo único que no hace el OpenAPI es enumerarlo.

| Ruta | Errores posibles |
|---|---|
| `GET /api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` | 404, 409, 422, 503 |
| `GET /api/v1/salud` | — |
| `GET /api/v1/meta` | 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/territorios` | 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/series/{series_id}` | 404, 422, 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/camas-psiquiatria/{series_id}` | 404, 422, 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/resumen-comunal` | 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/geo/comunas` | 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/hospitalizaciones-residentes/{series_id}` | 404, 422, 503 |
| `GET /api/v1/suicidios/{series_id}` | 404, 422, 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/calendario-eventos` | 422 |
| `GET /api/v1/establecimientos` | 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/establecimientos-meta` | 503 (503 con `Retry-After` mientras calcula) |
| `GET /api/v1/establecimientos/{codigo}` | 404, 422, 503 (503 con `Retry-After` mientras calcula) |

Significado de cada código:
- **404:** el territorio, la serie o el establecimiento no existe.
- **409:** la combinación pedida existe, pero sus datos no superan las validaciones del cálculo de caracterización; el `detail` explica cuál.
- **422:** parámetros fuera de rango o con formato inválido.
- **503:** sin `Retry-After`, falta un output del pipeline y el `detail` indica qué stage ejecutar. Con `Retry-After`, la API está calculando y el cliente reintenta.

`/api/v1/salud` no devuelve errores: informa el estado de carga de los datos y del pronóstico.

