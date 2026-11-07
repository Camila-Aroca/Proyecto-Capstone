from datetime import date, datetime, timezone

import pytest

from src.data import calendario_eventos as c

# Instantes UTC publicados por el U.S. Naval Observatory ("Earth's Seasons"), redondeados al minuto.
REFERENCIA_USNO = [
    (2024, "marzo", datetime(2024, 3, 20, 3, 6)), (2024, "junio", datetime(2024, 6, 20, 20, 51)),
    (2024, "septiembre", datetime(2024, 9, 22, 12, 44)), (2024, "diciembre", datetime(2024, 12, 21, 9, 20)),
    (2025, "marzo", datetime(2025, 3, 20, 9, 1)), (2025, "junio", datetime(2025, 6, 21, 2, 42)),
    (2025, "septiembre", datetime(2025, 9, 22, 18, 19)), (2025, "diciembre", datetime(2025, 12, 21, 15, 3)),
    (2026, "marzo", datetime(2026, 3, 20, 14, 46)), (2026, "junio", datetime(2026, 6, 21, 8, 24)),
    (2026, "septiembre", datetime(2026, 9, 23, 0, 5)), (2026, "diciembre", datetime(2026, 12, 21, 20, 50)),
]


@pytest.mark.parametrize("ano, mes, publicado", REFERENCIA_USNO)
def test_equinoccios_y_solsticios_coinciden_con_lo_publicado(ano, mes, publicado):
    calculado = c.instante_estacion(ano, mes)
    assert abs((calculado - publicado.replace(tzinfo=timezone.utc)).total_seconds()) <= 120


def test_la_fecha_de_inicio_es_la_de_chile_con_horario_de_verano():
    # 23-09-2026 00:05 UTC es 22-09 21:05 en Chile (UTC-3); 21-06-2025 02:42 UTC es 20-06 22:42 (UTC-4).
    assert c.fecha_en_chile(c.instante_estacion(2026, "septiembre")) == date(2026, 9, 22)
    assert c.fecha_en_chile(c.instante_estacion(2025, "junio")) == date(2025, 6, 20)


@pytest.mark.parametrize("ano, esperado", [
    (2019, date(2019, 4, 21)), (2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28)), (2038, date(2038, 4, 25)),
])
def test_pascua(ano, esperado):
    assert c.pascua(ano) == esperado


def test_domingos_de_la_madre_y_del_padre():
    assert c.domingo_n(2026, 5, 2) == date(2026, 5, 10)
    assert c.domingo_n(2026, 6, 3) == date(2026, 6, 21)
    assert c.domingo_n(2025, 6, 1) == date(2025, 6, 1)  # el 1 de junio de 2025 es domingo


def test_estaciones_cubren_el_periodo_sin_huecos_ni_solapes():
    estaciones = [e for e in c.eventos(date(2024, 1, 1), date(2026, 12, 31)) if e.categoria == c.ESTACION]
    for actual, siguiente in zip(estaciones, estaciones[1:]):
        assert (siguiente.fecha_inicio - actual.fecha_fin).days == 1
    assert estaciones[0].fecha_inicio <= date(2024, 1, 1) and estaciones[-1].fecha_fin >= date(2026, 12, 31)
    assert [e.nombre for e in estaciones[:5]] == ["Verano", "Otoño", "Invierno", "Primavera", "Verano"]


def test_festividades_del_periodo_y_rango_que_cruza_el_ano():
    nombres = {(e.nombre, e.fecha_inicio, e.fecha_fin)
               for e in c.eventos(date(2025, 12, 1), date(2026, 1, 15)) if e.categoria == c.FESTIVIDAD}
    assert nombres == {("Navidad", date(2025, 12, 24), date(2025, 12, 25)),
                       ("Año Nuevo", date(2025, 12, 31), date(2026, 1, 1))}
    ids = [e.evento_id for e in c.eventos(date(2020, 1, 1), date(2030, 12, 31))]
    assert len(ids) == len(set(ids))


def test_halloween_y_todos_los_santos_cubren_31_oct_y_1_nov():
    marcas = [e for e in c.eventos(date(2025, 10, 1), date(2025, 11, 30)) if e.categoria == c.FESTIVIDAD]
    assert [(e.nombre, e.fecha_inicio, e.fecha_fin) for e in marcas] == [
        ("Halloween y Todos los Santos", date(2025, 10, 31), date(2025, 11, 1))]


def test_fuera_de_rango_falla():
    with pytest.raises(ValueError):
        c.eventos(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(ValueError):
        c.instante_estacion(1999, "marzo")
