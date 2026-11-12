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
