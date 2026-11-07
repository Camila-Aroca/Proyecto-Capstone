"""QA opt-in contra los outputs reales; no descarga ni modifica artefactos.

Ejecutar con SAAD_QA_DATOS=1 después del pipeline. Contrasta las respuestas con
los marts canónicos por semanas exactas, incluyendo fragmentos de año.
"""
import os
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.api.caracterizacion import caracterizar_suicidios, caracterizar_urgencias

BASE = Path('data/processed')
pytestmark = pytest.mark.skipif(os.environ.get('SAAD_QA_DATOS') != '1', reason='QA de outputs reales opt-in')


@pytest.mark.parametrize('nivel,causa', [('region', 36), ('comuna', 36),
                                       ('establecimiento', 36), ('establecimiento', 42)])
def test_urgencias_concilia_con_mart_canonico(nivel, causa):
    grano = 'establecimiento' if nivel == 'establecimiento' else 'comuna'
    ruta = BASE / f'marts/mart_urgencias_{grano}_weekly.parquet'
    frame = pq.read_table(ruta, columns=[f'{grano}_codigo', 'ano', 'semana', f'atenciones_id{causa}']).to_pandas()
    # Últimas 52 claves publicadas, no rango de 364 días ni suma de promedios.
    claves = set(map(tuple, frame[['ano', 'semana']].drop_duplicates().sort_values(['ano', 'semana']).tail(52).to_numpy()))
    ventana = frame.loc[[tuple(k) in claves for k in frame[['ano', 'semana']].to_numpy()]]
    codigo = 'RM'
    if nivel != 'region':
        codigo = str(ventana.groupby(f'{grano}_codigo')[f'atenciones_id{causa}'].sum().idxmax())
        ventana = ventana[ventana[f'{grano}_codigo'].astype(str) == codigo]
    resultado = caracterizar_urgencias(BASE / 'urgencias', claves, nivel, codigo, causa)
    assert resultado['total'] == int(ventana[f'atenciones_id{causa}'].sum())
    assert sum(b['valor'] for b in resultado['edad']) == resultado['total']


@pytest.mark.parametrize('nivel', ['region', 'comuna'])
def test_suicidios_concilia_con_mart_canonico(nivel):
    frame = pq.read_table(BASE / 'marts/mart_suicidios_comuna_weekly.parquet').to_pandas()
    claves = set(map(tuple, frame[['ano', 'semana']].drop_duplicates().sort_values(['ano', 'semana']).tail(52).to_numpy()))
    ventana = frame.loc[[tuple(k) in claves for k in frame[['ano', 'semana']].to_numpy()]]
    codigo = 'RM'
    if nivel == 'comuna':
        codigo = str(ventana.groupby('comuna_codigo')['suicidios'].sum().idxmax())
        ventana = ventana[ventana['comuna_codigo'] == codigo]
    resultado = caracterizar_suicidios(BASE / 'defunciones/defunciones_nacional.parquet', claves, codigo)
    assert resultado['total'] == int(ventana['suicidios'].sum())
    assert sum(b['valor'] for b in resultado['edad']) == resultado['total']
    assert sum(b['valor'] for b in resultado['sexo']) == resultado['total']


def test_region_ventana_actual_respeta_panel_modelado():
    from src.models.forecast import load_current_panel
    datos = load_current_panel()
    region = datos.panel[datos.panel['series_id'] == 'RM'].sort_values('t').tail(52)
    claves = set(map(tuple, region[['ano', 'semana']].to_numpy()))
    comunas = set(datos.panel.loc[datos.panel['nivel'] == 'comuna', 'series_id'].astype(str))
    resultado = caracterizar_urgencias(BASE / 'urgencias', claves, 'region', 'RM', 36, comunas=comunas)
    assert resultado['total'] == int(region['y'].sum())
    assert sum(b['valor'] for b in resultado['edad']) == resultado['total']
