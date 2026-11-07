"""Desgloses observados: semanas exactas, territorios y conciliación sin imputación."""
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.service import ServicioDemanda


def test_endpoint_existe_y_rechaza_semanas_invalidas():
    with TestClient(create_app(iniciar_calculos=False)) as client:
        assert client.get('/api/v1/caracterizacion/urgencias/comuna/13101?semanas=mal').status_code == 422


def test_urgencias_filtra_semanas_territorio_y_causa(tmp_path):
    from src.api.caracterizacion import caracterizar_urgencias
    ruta = tmp_path / 'urgencias'
    ruta.mkdir()
    base = dict(ano=2025, semana=38, comuna_codigo='13101', establecimiento_codigo=1,
                id_causa=36, total=10, menores_1=1, de_1_a_4=2, de_5_a_14=3,
                de_15_a_64=4, de_65_y_mas=0)
    rows = [base, dict(base, semana=39), dict(base, comuna_codigo='13102'),
            dict(base, id_causa=42), dict(base, establecimiento_codigo=2)]
    pq.write_table(pa.Table.from_pylist(rows), ruta / 'urgencias_rm_2025.parquet')
    salida = caracterizar_urgencias(ruta, {(2025, 38)}, 'comuna', '13101', 36)
    assert salida['total'] == 20
    assert [x['valor'] for x in salida['edad']] == [2, 4, 6, 8, 0]
    assert salida['sexo'] is None
    # La línea regional solo suma el universo comunal del panel servido.
    assert caracterizar_urgencias(ruta, {(2025, 38)}, 'region', 'RM', 36,
                                   comunas={'13102'})['total'] == 10
    assert caracterizar_urgencias(ruta, {(2025, 38)}, 'establecimiento', '1', 42)['total'] == 10
    # Una desagregación inconsistente no puede publicarse como si cuadrara.
    rows[0]['total'] = 11
    pq.write_table(pa.Table.from_pylist(rows), ruta / 'urgencias_rm_2025.parquet')
    with pytest.raises(ValueError, match='concili'):
        caracterizar_urgencias(ruta, {(2025, 38)}, 'comuna', '13101', 36)


def test_suicidios_residencia_unidades_edad_y_faltantes(tmp_path):
    from src.api.caracterizacion import caracterizar_suicidios
    base = dict(fecha_defuncion=date(2025, 9, 21), comuna_codigo='13101',
                codigo_categoria_diag2='X60', sexo='Hombre', edad_tipo=1, edad_cantidad=30)
    rows = [base, dict(base, sexo='Mujer', edad_tipo=2, edad_cantidad=6),
            dict(base, sexo=None, edad_tipo=0, edad_cantidad=99),
            dict(base, comuna_codigo='13102'), dict(base, codigo_categoria_diag2='X85'),
            dict(base, fecha_defuncion=date(2025, 9, 28))]
    ruta = tmp_path / 'def.parquet'
    pq.write_table(pa.Table.from_pylist(rows), ruta)
    s = caracterizar_suicidios(ruta, {(2025, 39)}, '13101')
    assert s['total'] == 3
    assert {x['etiqueta']: x['valor'] for x in s['sexo']} == {'Hombre': 1, 'Mujer': 1, 'Sin dato': 1}
    assert sum(x['valor'] for x in s['edad']) == 3
    assert s['edad'][0]['valor'] == 1
    assert s['edad'][-1] == {'etiqueta': 'Sin dato', 'valor': 1}


def test_escenario_conserva_total_y_no_usa_anios_futuros(tmp_path):
    from src.api.caracterizacion import escenario_contextual
    ruta = tmp_path / 'contexto.parquet'
    rows = [dict(year=y, sex=s, indicator='egresos_hospitalarios_intento_suicida',
                 value=v, unit='N') for y, h, m in [(2024, 1, 2), (2025, 9, 1)]
            for s, v in [('Hombres', h), ('Mujeres', m)]]
    pq.write_table(pa.Table.from_pylist(rows), ruta)
    resultado = escenario_contextual(ruta, 10, 2024)
    assert resultado['ano_referencia'] == 2024
    assert [x['valor'] for x in resultado['sexo']] == [3, 7]
    assert escenario_contextual(ruta, 10, 2023) is None


def test_http_contrato_y_limites_deis(tmp_path, monkeypatch):
    from src.api import caracterizacion as modulo
    monkeypatch.setattr(modulo, 'BASE', tmp_path)
    ruta = tmp_path / 'urgencias'
    ruta.mkdir()
    fila = dict(ano=2025, semana=1, comuna_codigo='13101', establecimiento_codigo=1,
                id_causa=36, total=3, menores_1=0, de_1_a_4=0, de_5_a_14=1,
                de_15_a_64=2, de_65_y_mas=0)
    pq.write_table(pa.Table.from_pylist([fila]), ruta / 'urgencias_rm_2025.parquet')
    with TestClient(create_app(iniciar_calculos=False)) as client:
        r = client.get('/api/v1/caracterizacion/urgencias/comuna/13101?semanas=2025-1')
        assert r.status_code == 200, r.text
        assert r.json()['desde'] == '2025-01-01'
        assert r.json()['hasta'] == '2025-01-04'
        assert r.json()['total'] == 3
        assert r.json()['escenario'] is None
        assert client.get('/api/v1/caracterizacion/suicidios/comuna/99999?semanas=2025-1').status_code == 404
        assert client.get('/api/v1/caracterizacion/urgencias/region/RM?semanas=2023-53').status_code == 422
        assert client.get('/api/v1/caracterizacion/suicidios/establecimiento/1?semanas=2025-1').status_code == 422
        assert client.get('/api/v1/caracterizacion/urgencias/comuna/13101?semanas=2024-1').status_code == 503


@pytest.mark.parametrize('total', [0, 1, 2, 7, 100001])
def test_redondeo_escenario_no_pierde_eventos(tmp_path, total):
    from src.api.caracterizacion import escenario_contextual
    ruta = tmp_path / 'contexto.parquet'
    pq.write_table(pa.Table.from_pylist([
        dict(year=2025, sex=s, indicator='egresos_hospitalarios_intento_suicida', value=v, unit='N')
        for s, v in [('Hombres', 2127), ('Mujeres', 5762)]
    ]), ruta)
    assert sum(x['valor'] for x in escenario_contextual(ruta, total, 2026)['sexo']) == total


def test_region_respeta_universo_del_grafico_http(tmp_path, monkeypatch):
    from src.api import caracterizacion as modulo
    monkeypatch.setattr(modulo, 'BASE', tmp_path)
    ruta = tmp_path / 'urgencias'
    ruta.mkdir()
    base = dict(ano=2025, semana=38, comuna_codigo='13101', establecimiento_codigo=1,
                id_causa=36, total=10, menores_1=0, de_1_a_4=0, de_5_a_14=0,
                de_15_a_64=10, de_65_y_mas=0)
    pq.write_table(pa.Table.from_pylist([base, dict(base, comuna_codigo='13102')]),
                   ruta / 'urgencias_rm_2025.parquet')
    servicio = ServicioDemanda()
    servicio.datos = SimpleNamespace(panel=pd.DataFrame([
        {'series_id': '13101', 'nivel': 'comuna'}, {'series_id': 'RM', 'nivel': 'region'}]))
    with TestClient(create_app(lambda: servicio, iniciar_calculos=False)) as client:
        r = client.get('/api/v1/caracterizacion/urgencias/region/RM?semanas=2025-38')
        assert r.status_code == 200, r.text
        assert r.json()['total'] == 10
        assert sum(b['valor'] for b in r.json()['edad']) == 10
