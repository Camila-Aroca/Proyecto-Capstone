"""Calendario de festividades de reunión y estaciones del año en Chile, por regla.

Sirve como **contexto temporal** del gráfico de suicidios: marca fechas en las que
suele haber reuniones (feriados y celebraciones familiares) y el inicio y fin de
cada estación. Son marcas de contexto, no explicaciones: que una variación coincida
con una fecha no dice que la fecha la cause.

Nada se escribe a mano: cada fecha sale de una regla verificable.

- **Fechas fijas:** Año Nuevo (31 dic - 1 ene, víspera y feriado), Fiestas Patrias
  (18 y 19 sep, feriados legales; los años en que la ley agrega días no se incluyen)
  y Navidad (24 - 25 dic, víspera y feriado).
- **Semana Santa:** de Viernes Santo a Domingo de Resurrección; la Pascua se calcula
  con el algoritmo gregoriano anónimo (Meeus, *Astronomical Algorithms*, cap. 8).
- **Día de la Madre y del Padre:** segundo domingo de mayo y tercer domingo de junio.
- **Estaciones (hemisferio sur):** empiezan en el equinoccio o solsticio y terminan
  el día anterior al siguiente. El instante se calcula con Meeus, cap. 27 (series
  periódicas, error del orden de un minuto), se pasa de tiempo dinámico a UTC con
  ΔT y se lleva a la fecha **local de Chile** (`America/Santiago`, con horario de
  verano): el equinoccio de septiembre de 2026 ocurre el 23 a las 00:05 UTC, que en
  Chile es el 22.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
from typing import Final
from zoneinfo import ZoneInfo

ZONA_CHILE: Final[ZoneInfo] = ZoneInfo("America/Santiago")
FESTIVIDAD: Final[str] = "festividad"
ESTACION: Final[str] = "estacion"

# Meeus, cap. 27: JDE medio de cada equinoccio/solsticio para 2000-3000, Y = (año - 2000) / 1000.
_JDE0: Final[dict[str, tuple[float, ...]]] = {
    "marzo": (2451623.80984, 365242.37404, 0.05169, -0.00411, -0.00057),
    "junio": (2451716.56767, 365241.62603, 0.00325, 0.00888, -0.00030),
    "septiembre": (2451810.21715, 365242.01767, -0.11575, 0.00337, 0.00078),
    "diciembre": (2451900.05952, 365242.74049, -0.06223, -0.00823, 0.00032),
}
# Meeus, tabla 27.C: 24 términos periódicos (A, B en grados, C en grados por siglo).
_TERMINOS: Final[tuple[tuple[float, float, float], ...]] = (
    (485, 324.96, 1934.136), (203, 337.23, 32964.467), (199, 342.08, 20.186), (182, 27.85, 445267.112),
    (156, 73.14, 45036.886), (136, 171.52, 22518.443), (77, 222.54, 65928.934), (74, 296.72, 3034.906),
    (70, 243.58, 9037.513), (58, 119.81, 33718.147), (52, 297.17, 150.678), (50, 21.02, 2281.226),
    (45, 247.54, 29929.562), (44, 325.15, 31555.956), (29, 60.93, 4443.417), (18, 155.12, 67555.328),
    (17, 288.79, 4562.452), (16, 198.04, 62894.029), (14, 199.76, 31436.921), (12, 95.39, 14577.848),
    (12, 287.11, 31931.756), (12, 320.81, 34777.259), (9, 227.73, 1222.114), (8, 15.45, 16859.074),
)
# Estación del hemisferio sur que comienza en cada equinoccio/solsticio.
ESTACION_QUE_INICIA: Final[dict[str, str]] = {
    "marzo": "Otoño", "junio": "Invierno", "septiembre": "Primavera", "diciembre": "Verano",
}


@dataclass(frozen=True)
class Evento:
    """Una marca del calendario: un día (inicio = fin) o un rango de días, ambos incluidos."""

    evento_id: str
    nombre: str
    categoria: str
    fecha_inicio: date
    fecha_fin: date
    detalle: str


# --------------------------------------------------------------------------
# Reglas
# --------------------------------------------------------------------------

def pascua(ano: int) -> date:
    """Domingo de Resurrección (calendario gregoriano), algoritmo anónimo de Meeus/Jones/Butcher."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def domingo_n(ano: int, mes: int, n: int) -> date:
    """El n-ésimo domingo de un mes."""
    primero = date(ano, mes, 1)
    return primero + timedelta(days=(6 - primero.weekday()) % 7 + 7 * (n - 1))


def _delta_t_segundos(ano: float) -> float:
    """ΔT = TT - UT (Espenak y Meeus, polinomio para 2005-2050); ~69-75 s en la década de 2020."""
    t = ano - 2000
    return 62.92 + 0.32217 * t + 0.005589 * t * t


def instante_estacion(ano: int, mes: str) -> datetime:
    """Instante UTC del equinoccio o solsticio de `mes` (marzo, junio, septiembre, diciembre) de `ano`."""
    if not 2000 <= ano <= 3000:
        raise ValueError("Las series de Meeus usadas valen para los años 2000 a 3000.")
    y = (ano - 2000) / 1000
    c = _JDE0[mes]
    jde0 = c[0] + c[1] * y + c[2] * y ** 2 + c[3] * y ** 3 + c[4] * y ** 4
    t = (jde0 - 2451545.0) / 36525
    w = math.radians(35999.373 * t - 2.47)
    delta_lambda = 1 + 0.0334 * math.cos(w) + 0.0007 * math.cos(2 * w)
    s = sum(a * math.cos(math.radians(b + cc * t)) for a, b, cc in _TERMINOS)
    jde = jde0 + 0.00001 * s / delta_lambda
    tt = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jde - 2451545.0)
    return tt - timedelta(seconds=_delta_t_segundos(ano + 0.5))


def fecha_en_chile(instante: datetime) -> date:
    return instante.astimezone(ZONA_CHILE).date()


# --------------------------------------------------------------------------
# Calendario
# --------------------------------------------------------------------------

def _festividades(ano: int) -> list[Evento]:
    domingo = pascua(ano)
    return [
        Evento(f"ano_nuevo_{ano}", "Año Nuevo", FESTIVIDAD, date(ano - 1, 12, 31), date(ano, 1, 1),
               "Víspera (31 de diciembre) y feriado del 1 de enero."),
        Evento(f"semana_santa_{ano}", "Semana Santa", FESTIVIDAD, domingo - timedelta(days=2), domingo,
               "De Viernes Santo a Domingo de Resurrección; viernes y sábado son feriados."),
        Evento(f"dia_madre_{ano}", "Día de la Madre", FESTIVIDAD, domingo_n(ano, 5, 2), domingo_n(ano, 5, 2),
               "Segundo domingo de mayo; no es feriado."),
        Evento(f"dia_padre_{ano}", "Día del Padre", FESTIVIDAD, domingo_n(ano, 6, 3), domingo_n(ano, 6, 3),
               "Tercer domingo de junio; no es feriado."),
        Evento(f"fiestas_patrias_{ano}", "Fiestas Patrias", FESTIVIDAD, date(ano, 9, 18), date(ano, 9, 19),
               "18 y 19 de septiembre, feriados legales (los días que la ley agrega algunos años no se incluyen)."),
        Evento(f"navidad_{ano}", "Navidad", FESTIVIDAD, date(ano, 12, 24), date(ano, 12, 25),
               "Nochebuena (24 de diciembre) y feriado del 25."),
    ]


def _inicios_estaciones(ano: int) -> list[tuple[date, str, datetime]]:
    return [(fecha_en_chile(i := instante_estacion(ano, mes)), mes, i) for mes in ESTACION_QUE_INICIA]


def _estaciones(desde: date, hasta: date) -> list[Evento]:
    """Estaciones que tocan el período; cada una va desde su inicio hasta el día antes de la siguiente."""
    inicios = sorted(x for ano in range(desde.year - 1, hasta.year + 2) for x in _inicios_estaciones(ano))
    eventos = []
    for (inicio, mes, instante), (siguiente, _, _) in zip(inicios, inicios[1:]):
        nombre = ESTACION_QUE_INICIA[mes]
        hora = instante.astimezone(ZONA_CHILE).strftime("%H:%M")
        eventos.append(Evento(
            f"{nombre.lower().replace('ñ', 'n')}_{inicio.year}", nombre, ESTACION, inicio, siguiente - timedelta(days=1),
            f"{'Solsticio' if mes in ('junio', 'diciembre') else 'Equinoccio'} de {mes}: {inicio.strftime('%d-%m-%Y')} "
            f"a las {hora} (hora de Chile). Termina el día antes de la estación siguiente.",
        ))
    return eventos


def eventos(desde: date, hasta: date) -> list[Evento]:
    """Festividades y estaciones que se superponen con [desde, hasta], ordenadas por inicio."""
    if hasta < desde:
        raise ValueError("`hasta` es anterior a `desde`.")
    candidatos = [e for ano in range(desde.year, hasta.year + 2) for e in _festividades(ano)]
    candidatos += _estaciones(desde, hasta)
    return sorted((e for e in candidatos if e.fecha_inicio <= hasta and e.fecha_fin >= desde),
                  key=lambda e: (e.fecha_inicio, e.categoria))
