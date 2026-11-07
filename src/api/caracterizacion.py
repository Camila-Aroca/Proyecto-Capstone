"""Vistas de solo lectura sobre outputs del pipeline, sin artefactos ni modelos nuevos.

Las semanas son las claves DEIS observadas del gráfico, no un rango aproximado
de fechas. El escenario contextual es una hipótesis explícita, nunca sexo observado.
"""
from __future__ import annotations

from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as ds
from fastapi import APIRouter, HTTPException, Query, Request

from src.data.build_mart_suicidios_comuna_weekly import calendario_deis, semana_deis
from src.data.clean_censo_comunas import EXPECTED_RM_CUTS
from src.api.schemas import Caracterizacion

router = APIRouter(prefix='/api/v1')
BASE = Path('data/processed')
ETARIOS = ['menores_1', 'de_1_a_4', 'de_5_a_14', 'de_15_a_64', 'de_65_y_mas']
ETIQUETAS = ['Menores de 1 año', '1–4 años', '5–14 años', '15–64 años', '65 años y más']


def _barras(etiquetas, valores) -> list[dict]:
    return [dict(etiqueta=e, valor=int(v)) for e, v in zip(etiquetas, valores, strict=True)]


def caracterizar_urgencias(ruta: Path, semanas: set[tuple[int, int]], nivel: str,
                          codigo: str, causa: int, comunas: set[str] | None = None) -> dict:
    """Suma exacta de las columnas etarias publicadas; sexo no disponible."""
    frames = []
    for ano in sorted({a for a, _ in semanas}):
        archivo = ruta / f'urgencias_rm_{ano}.parquet'
        filtro = (ds.field('id_causa') == causa) & ds.field('semana').isin(
            [s for a, s in semanas if a == ano])
        if nivel == 'comuna':
            filtro &= ds.field('comuna_codigo') == codigo
        elif nivel == 'establecimiento':
            filtro &= ds.field('establecimiento_codigo') == int(codigo)
        elif comunas is not None:
            filtro &= ds.field('comuna_codigo').isin(sorted(comunas))
        frames.append(ds.dataset(archivo).to_table(columns=['total', *ETARIOS], filter=filtro).to_pandas())
    frame = pd.concat(frames, ignore_index=True)
    if frame.empty:
        raise LookupError('Sin registros de Urgencias para las semanas seleccionadas.')
    if frame.isna().any().any() or (frame < 0).any().any():
        raise ValueError('Valores etarios ausentes o negativos: no se imputan.')
    if not frame[ETARIOS].sum(axis=1).eq(frame['total']).all():
        raise ValueError('La conciliación etaria no coincide con el total publicado.')
    return dict(total=int(frame['total'].sum()), sexo=None,
                edad=_barras(ETIQUETAS, frame[ETARIOS].sum()))


def _edad(tipo, cantidad) -> str:
    if pd.isna(tipo) or pd.isna(cantidad) or cantidad < 0:
        return 'Sin dato'
    if tipo in (2, 3, 4) and cantidad < {2: 12, 3: 366, 4: 8784}[tipo]:
        return ETIQUETAS[0]
    if tipo != 1:
        return 'Sin dato'
    for limite, etiqueta in zip([1, 5, 15, 65], ETIQUETAS, strict=False):
        if cantidad < limite:
            return etiqueta
    return ETIQUETAS[-1]


def caracterizar_suicidios(ruta: Path, semanas: set[tuple[int, int]], codigo: str) -> dict:
    """Misma definición X60–X84 y calendario que el mart semanal; residencia."""
    filtro = pc.starts_with(ds.field('comuna_codigo'), '13')
    if codigo != 'RM':
        filtro &= ds.field('comuna_codigo') == codigo
    filtro &= ds.field('codigo_categoria_diag2').isin([f'X{i}' for i in range(60, 85)])
    filtro &= (ds.field('fecha_defuncion') >= date(min(a for a, _ in semanas), 1, 1))
    filtro &= (ds.field('fecha_defuncion') <= date(max(a for a, _ in semanas), 12, 31))
    frame = ds.dataset(ruta).to_table(
        columns=['fecha_defuncion', 'sexo', 'edad_tipo', 'edad_cantidad'], filter=filtro).to_pandas()
    frame = frame.loc[frame['fecha_defuncion'].map(lambda f: semana_deis(pd.Timestamp(f).date()) in semanas)]
    sexo = frame['sexo'].fillna('Sin dato').replace('', 'Sin dato').value_counts().sort_index()
    edades = pd.Series([_edad(t, c) for t, c in zip(frame['edad_tipo'], frame['edad_cantidad'])], dtype='str')
    valores = edades.value_counts().reindex([*ETIQUETAS, 'Sin dato'], fill_value=0)
    return dict(total=len(frame), sexo=_barras(sexo.index, sexo.values),
                edad=_barras(valores.index, valores.values))


def escenario_contextual(ruta: Path, total: int, ano: int) -> dict | None:
    """Reparto contrafactual por restos mayores. No estima una precisión clínica.

    Hipótesis: las urgencias tendrían la distribución nacional por sexo de los
    egresos por intento suicida. No se afirma transportabilidad ni se usa como feature.
    Se usa el último año publicado no posterior al inicio de la ventana.
    """
    if not ruta.exists():
        return None
    frame = ds.dataset(ruta).to_table().to_pandas()
    frame = frame[(frame['indicator'] == 'egresos_hospitalarios_intento_suicida')
                  & (frame['unit'] == 'N') & frame['sex'].isin(['Hombres', 'Mujeres'])
                  & (frame['year'] <= ano)]
    if frame.empty:
        return None
    referencia = int(frame['year'].max())
    seleccion = frame[frame['year'] == referencia]
    if len(seleccion) != 2 or seleccion['sex'].nunique() != 2:
        return None
    pesos = seleccion.set_index('sex')['value'].reindex(['Hombres', 'Mujeres'])
    if pesos.isna().any() or (pesos < 0).any() or pesos.sum() <= 0:
        return None
    fracciones = [Fraction(str(v)) for v in pesos]
    cuotas = [total * p / sum(fracciones) for p in fracciones]
    enteros = [q.numerator // q.denominator for q in cuotas]
    orden = sorted(range(2), key=lambda i: cuotas[i] - enteros[i], reverse=True)
    for i in orden[:total - sum(enteros)]:
        enteros[i] += 1
    return dict(ano_referencia=referencia, sexo=_barras(['Hombres', 'Mujeres'], enteros),
                referencia=_barras(['Hombres', 'Mujeres'], pesos),
                fuente='Egresos hospitalarios por intento suicida · nacional',
                metodo='Total observado × proporción de referencia; redondeo por restos mayores.',
                advertencia='Supone el mismo reparto que los egresos nacionales por intento suicida. '
                'No es sexo observado ni un reparto validado de estas urgencias.')


@router.get('/caracterizacion/{fuente}/{nivel}/{codigo}', response_model=Caracterizacion)
def caracterizacion(
    fuente: Literal['urgencias', 'hospitalizaciones', 'suicidios'],
    nivel: Literal['region', 'comuna', 'establecimiento'], codigo: str,
    request: Request,
    semanas: Annotated[str, Query(max_length=5000, pattern=r'^\d{4}-\d{1,2}(,\d{4}-\d{1,2})*$')],
) -> dict:
    claves = {tuple(map(int, s.split('-'))) for s in semanas.split(',')}
    if len(claves) > 520 or any(a < 2020 or a > date.today().year or not 1 <= s <= 53 for a, s in claves):
        raise HTTPException(422, 'Semanas DEIS fuera de rango.')
    if (nivel == 'region' and codigo != 'RM') or (nivel != 'region' and not codigo.isdecimal()):
        raise HTTPException(422, 'Código territorial inválido.')
    if fuente == 'suicidios' and nivel == 'establecimiento':
        raise HTTPException(422, 'Defunciones no identifica el establecimiento.')
    if nivel == 'comuna' and codigo not in {str(c) for c in EXPECTED_RM_CUTS}:
        raise HTTPException(404, 'La comuna no pertenece a la Región Metropolitana.')
    calendario = calendario_deis(date(min(a for a, _ in claves), 1, 1),
                                 date(max(a for a, _ in claves), 12, 31))
    seleccionadas = calendario.loc[[tuple(k) in claves for k in calendario[['ano', 'semana']].to_numpy()]]
    if len(seleccionadas) != len(claves):
        raise HTTPException(422, 'Una semana solicitada no existe en el calendario DEIS.')
    try:
        if fuente == 'suicidios':
            salida = caracterizar_suicidios(BASE / 'defunciones/defunciones_nacional.parquet', claves, codigo)
            salida['escenario'] = None
        else:
            comunas = None
            if nivel == 'region':
                panel = request.app.state.servicio.datos
                if panel is None:
                    raise HTTPException(503, 'El panel regional aún no está disponible.')
                comunas = set(panel.panel.loc[panel.panel['nivel'] == 'comuna', 'series_id'].astype(str))
            salida = caracterizar_urgencias(BASE / 'urgencias', claves, nivel, codigo,
                                           36 if fuente == 'urgencias' else 42, comunas=comunas)
            salida['escenario'] = escenario_contextual(
                BASE / 'contexto_genero/egresos_intento_suicida_sexo_anio.parquet',
                salida['total'], min(a for a, _ in claves))
    except FileNotFoundError as exc:
        raise HTTPException(503, 'Faltan fuentes processed del pipeline para la caracterización.') from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    salida.update(fuente=fuente, nivel=nivel, codigo=codigo, semanas=len(claves))
    salida.update(desde=seleccionadas['fecha_inicio_semana'].min(),
                  hasta=seleccionadas['fecha_fin_semana'].max())
    return salida
