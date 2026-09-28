"""Aplicacion FastAPI del SAAD.

Ejecucion local, desde la raiz del repositorio:

    uvicorn src.api.main:app --reload

Documentacion interactiva en http://127.0.0.1:8000/docs.

Al arrancar carga los outputs del pipeline y, en segundo plano, calcula el
pronostico con el modelo seleccionado por el benchmark. La API queda
disponible de inmediato; los endpoints de pronostico responden `503` con
`Retry-After` hasta que el calculo termina.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.api.routes import router
from src.api.service import ServicioDemanda

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Origenes del frontend permitidos; configurable sin tocar codigo.
ORIGENES_PERMITIDOS = os.environ.get(
    "SAAD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")


def create_app(
    fabrica_servicio: Callable[[], ServicioDemanda] = ServicioDemanda,
    iniciar_calculos: bool = True,
) -> FastAPI:
    """Construye la app. Los tests inyectan un servicio ya poblado y sin calculos."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        servicio = fabrica_servicio()
        app.state.servicio = servicio
        tarea = None
        if iniciar_calculos:
            async def preparar() -> None:
                await asyncio.to_thread(servicio.cargar)
                await asyncio.to_thread(servicio.calcular_pronostico)

            # En segundo plano: el servidor acepta requests mientras carga.
            tarea = asyncio.create_task(preparar())
        yield
        if tarea is not None and not tarea.done():
            tarea.cancel()

    app = FastAPI(
        title="SAAD API",
        description=(
            "Demanda de urgencia en salud mental en la Region Metropolitana: datos "
            "observados y pronostico a 4-8 semanas del modelo seleccionado."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in ORIGENES_PERMITIDOS if o.strip()],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
