"""Endpoint del calendario de contexto: festividades de reunión y estaciones del año en Chile.

Sin estado ni archivos: las fechas salen de reglas (`src/data/calendario_eventos.py`),
de modo que no hay output que pueda quedar desactualizado. Son marcas de contexto
para leer el gráfico, no explicaciones de sus variaciones.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated, Any, Final

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import EventoCalendario
from src.data.calendario_eventos import eventos

# Tope del período por consulta: el tablero pide a lo sumo unos tres años.
MAX_DIAS: Final[int] = 366 * 12

router = APIRouter(prefix="/api/v1")


@router.get("/calendario-eventos", response_model=list[EventoCalendario])
def calendario_eventos(
    desde: Annotated[date, Query(description="Primer día del período (AAAA-MM-DD).")],
    hasta: Annotated[date, Query(description="Último día del período (AAAA-MM-DD).")],
) -> list[dict[str, Any]]:
    """Festividades y estaciones que se superponen con el período, ordenadas por inicio."""
    if hasta < desde:
        raise HTTPException(status_code=422, detail="`hasta` es anterior a `desde`.")
    if (hasta - desde).days > MAX_DIAS:
        raise HTTPException(status_code=422, detail=f"El período no puede superar {MAX_DIAS} días.")
    if desde.year < 2001 or hasta.year > 2999:
        raise HTTPException(status_code=422, detail="Período fuera de 2001-2999, donde valen las reglas astronómicas.")
    return [asdict(e) for e in eventos(desde, hasta)]
