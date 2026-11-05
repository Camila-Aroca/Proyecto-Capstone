"""Pruebas de los cálculos del EDA de Estadísticas Hospitalarias REM-20."""

import numpy as np
import pandas as pd

import scripts.eda_estadisticas_hospitalarias as module

LLAVE = module.LLAVE


def _ancho(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas).set_index(LLAVE)


def _area(ano: int, nivel: int, **valores) -> dict:
    return {"ano": ano, "servicio_salud_codigo": 1, "establecimiento_codigo": 101100,
            "nivel_cuidado_codigo": nivel, **valores}


def _conteos(ano, nivel, estada, egresos, traslados, fallecidos, promedio_publicado, letalidad_publicada):
    return _area(ano, nivel, **{
        "Dias Cama Ocupados": 80.0, "Dias Cama Disponibles": 100.0, "Indice Ocupacional": 80.0,
        "Dias de Estada": estada, "Numero de Egresos": egresos, "Traslados": traslados,
        "Egresos Fallecidos": fallecidos, "Promedio Días de Estada": promedio_publicado,
        "Letalidad": letalidad_publicada, "Promedio Cama Disponibles": 10.0,
        "Indice de Rotación": round((egresos + traslados) / 10.0, 2),
    })


def test_definicion_razones_detecta_cambio_de_formula():
    filas = [
        _conteos(2024, 401, 100.0, 15.0, 5.0, 2.0, 5.0, 10.0),      # / (egresos + traslados)
        _conteos(2025, 401, 100.0, 15.0, 5.0, 3.0, 6.67, 20.0),     # / egresos
    ]
    definiciones = module.definicion_razones(_ancho(filas))
    estada = definiciones["Promedio Días de Estada"]
    assert estada[2024]["estada / (egresos + traslados)"] == 1.0 and estada[2024]["estada / egresos"] == 0.0
    assert estada[2025]["estada / egresos"] == 1.0
    tramos = module.cambios_de_definicion(definiciones)["Letalidad"]
    assert [(t["desde"], t["hasta"], t["formula"]) for t in tramos] == [
        (2024, 2024, "100 * fallecidos / (egresos + traslados)"), (2025, 2025, "100 * fallecidos / egresos")]
    assert module.cambios_de_definicion(definiciones)["Indice Ocupacional"] == [
        {"formula": "100 * ocupados / disponibles", "desde": 2024, "hasta": 2025}]


def test_sobreocupacion_compara_mes_a_mes_y_omite_meses_no_publicados():
    base = {"ano": 2026, "servicio_salud_codigo": 1, "servicio_salud": "Arica", "establecimiento_codigo": 101100,
            "establecimiento_nombre": "H", "nivel_cuidado_codigo": 418, "nivel_cuidado": "418 - Psiq",
            "acumulado": None}
    meses_nulos = {m: None for m in module.MESES}
    detalle = pd.DataFrame([
        {**base, **meses_nulos, "indicador": "Dias Cama Ocupados", "ene": 31.0, "feb": 20.0},
        {**base, **meses_nulos, "indicador": "Dias Cama Disponibles", "ene": 30.0, "feb": 28.0},
    ])
    largo = module.sobreocupacion(detalle)
    assert len(largo) == 2
    assert int((largo.ocupados > largo.disponibles).sum()) == 1


def test_coherencia_dotacion_une_por_codigo_de_establecimiento_y_area():
    w = _ancho([_area(2024, 418, **{"Promedio Cama Disponibles": 19.6}),
                _area(2024, 401, **{"Promedio Cama Disponibles": 5.0})])
    dotacion = pd.DataFrame({"establecimiento_codigo": [101100, 101100], "area_funcional_codigo": [418, 401],
                             "camas_2024": [20, 10]})
    resultado = module.coherencia_dotacion(w, dotacion)
    assert resultado["areas_ano_comparadas"] == 2
    assert resultado["a_1_cama_o_menos"] == 0.5
    assert resultado["psiquiatria_a_1_cama_o_menos"] == 1.0
    assert module.coherencia_dotacion(w, None) == {"disponible": False}


def test_formato_de_numeros_en_espanol():
    assert module._n(1234567) == "1.234.567"
    assert module._n(91.234, 1) == "91,2"
    assert module._pct(0.971) == "97,1 %"
    assert module._n(np.nan) == "—"
