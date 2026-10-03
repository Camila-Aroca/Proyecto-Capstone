"""Fechas de ejecución según el calendario civil de Chile continental."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

CHILE_TZ = ZoneInfo("America/Santiago")


def run_datetime_chile(now: datetime | None = None) -> datetime:
    """Instante actual (o inyectado) convertido a America/Santiago."""
    if now is None:
        return datetime.now(CHILE_TZ)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("El reloj inyectado debe incluir zona horaria.")
    return now.astimezone(CHILE_TZ)


def run_date_chile(now: datetime | None = None) -> date:
    return run_datetime_chile(now).date()


def current_year_chile(now: datetime | None = None) -> int:
    return run_date_chile(now).year
