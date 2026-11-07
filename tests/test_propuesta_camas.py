"""Escenario anual: identidades, cobertura y abstención, sin imputaciones."""
from datetime import date

import pandas as pd
import pytest

from src.data.build_mart_ocupacion_psiquiatria_hospital_rm import propuesta_camas


def serie():
    fechas = pd.date_range('2025-10-01', periods=12, freq='MS')
    return pd.DataFrame({
        'ano': fechas.year, 'mes': fechas.month, 'dias_mes': fechas.days_in_month,
        'dias_cama_ocupados': fechas.days_in_month * 18,
        'dias_cama_disponibles': fechas.days_in_month * 20,
    })


def calcular(frame=None, dotacion=21, codigo=418):
    return propuesta_camas(serie() if frame is None else frame, dotacion, codigo, date(2026, 11, 7))


def test_identidades_y_habilitar_antes_de_ampliar():
    p = calcular()
    assert p['ano_objetivo'] == 2027
    assert p['camas_objetivo'] == 22  # ceil(18 / .85)
    assert p['aumento_dotacion'] == 1
    assert p['habilitar_existentes'] == pytest.approx(1)
    assert p['brecha_habilitacion'] == pytest.approx(2)
    assert p['ocupacion_resultante_pct'] <= 85
    assert p['camas_objetivo_90'] == 20


def test_dotacion_suficiente_no_propone_ampliacion():
    p = calcular(dotacion=24)
    assert p['aumento_dotacion'] == 0
    assert p['habilitar_existentes'] == 2


def test_umbral_exacto_no_agrega_cama_por_error_flotante():
    frame = serie()
    frame['dias_cama_ocupados'] = frame.dias_mes * 17
    assert calcular(frame)['camas_objetivo'] == 20


@pytest.mark.parametrize('frame,codigo,motivo', [
    (serie().iloc[1:], 418, '12 meses'),
    (pd.concat([serie(), serie().iloc[:1]]), 418, 'duplicados'),
    (serie(), 427, 'psiquiatría'),
])
def test_abstencion(frame, codigo, motivo):
    p = calcular(frame, codigo=codigo)
    assert p['camas_objetivo'] is None
    assert motivo in p['motivo']


def test_nulos_cierres_y_dato_antiguo_no_son_ceros():
    for columna, valor in [('dias_cama_ocupados', None), ('dias_cama_disponibles', 0)]:
        frame = serie()
        frame.loc[3, columna] = valor
        assert calcular(frame)['camas_objetivo'] is None
    sin_declarada = calcular(dotacion=None)
    assert sin_declarada['aumento_dotacion'] == 2
    assert sin_declarada['base_capacidad'] == 20
    assert sin_declarada['fuente_base'] == 'disponibles_rem20'
    assert propuesta_camas(serie(), 21, 418, date(2028, 1, 1))['camas_objetivo'] is None


def test_pico_mensual_no_promedio_que_oculta_estacionalidad():
    frame = serie()
    frame.loc[0, 'dias_cama_ocupados'] = 31 * 25
    p = calcular(frame)
    assert p['camas_objetivo'] == 30
    assert p['aumento_dotacion'] == 9


@pytest.mark.parametrize('codigo', [418, 419, 420, 421, 422, 423, 424, 425, 426, 428, 429])
def test_cada_area_psiquiatrica_tiene_escenario_con_sus_propios_datos(codigo):
    p = calcular(codigo=codigo)
    assert p['camas_objetivo'] == 22
    assert p['aumento_dotacion'] == 1
    assert p['referencia_aguda'] == (codigo in (418, 421))


def test_qa_retrospectivo_usa_solo_historia_y_no_silencia_incumplimiento():
    from scripts.eda_mart_ocupacion_psiquiatria_hospital_rm import auditar_propuestas
    fechas = pd.date_range('2024-01-01', periods=24, freq='MS')
    frame = pd.DataFrame({
        'establecimiento_codigo': 10, 'nivel_cuidado_codigo': 418,
        'ano': fechas.year, 'mes': fechas.month, 'dias_mes': fechas.days_in_month,
        'dias_cama_ocupados': fechas.days_in_month * [18] * 24,
        'dias_cama_disponibles': fechas.days_in_month * 30,
    })
    frame.loc[frame.ano == 2025, 'dias_cama_ocupados'] *= 1.5
    qa = auditar_propuestas(frame, None, date(2026, 1, 1))
    assert qa['cortes_retrospectivos'] == 1
    assert qa['meses_evaluados'] == 12
    assert qa['meses_bajo_objetivo'] == 0  # ningún acceso al futuro para dimensionar


def test_api_ventana_grafica_no_recorta_calculo_anual(monkeypatch):
    import src.api.establecimientos as api
    from src.data.build_mart_ocupacion_psiquiatria_hospital_rm import _derivar
    from src.api.schemas import AreaPsiquiatria

    class Corte(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 7)

    monkeypatch.setattr(api, 'date', Corte)
    frame = serie().assign(establecimiento_codigo=10, nivel_cuidado_codigo=418,
                           nivel_cuidado='Psiquiatría Adulto')
    frame = _derivar(frame)
    corta = api.areas_en_ventana(frame, 10, '2026-09-01')[0]
    larga = api.areas_en_ventana(frame, 10, '2025-10-01')[0]
    assert len(corta['serie']) == 1
    assert corta['propuesta_camas'] == larga['propuesta_camas']
    # Sin libro de dotación: la API conserva las camas calculadas de REM-20.
    contrato = AreaPsiquiatria.model_validate(corta)
    assert contrato.propuesta_camas.aumento_dotacion == 2
    assert contrato.propuesta_camas.fuente_base == 'disponibles_rem20'
