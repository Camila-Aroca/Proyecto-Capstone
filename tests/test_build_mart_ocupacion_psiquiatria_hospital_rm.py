"""Pruebas del mart mensual de ocupación de camas de psiquiatría y de su EDA."""

import pandas as pd
import pyarrow.parquet as pq
import pytest

import scripts.eda_mart_ocupacion_psiquiatria_hospital_rm as eda
import src.data.build_mart_ocupacion_psiquiatria_hospital_rm as module

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PSIQ_ADULTO = "418 - Área Psiquiatría Adulto Corta estadía"
PSIQ_INFANTO = "421 - Área Psiquiatría Infanto-adolescente corta estadía"
SOCIOSANITARIA = "427 - Área Sociosanitaria Adulto"
MEDICA = "401 - Área Médica Adulto Cuidados Básicos"


def _area(codigo, nivel_codigo, nivel, ocupados, disponibles, *, ano=2024, promedio=None):
    """Tres filas de indicador para un área: ene y feb publicados, el resto no publicado."""
    dias = {1: 31, 2: 29 if ano == 2024 else 28}
    filas = []
    for indicador, valores in (
        (module.OCUPADOS, ocupados),
        (module.DISPONIBLES, disponibles),
        (module.PROMEDIO_DISPONIBLES, promedio or [round(v / dias[i + 1], 2) for i, v in enumerate(disponibles)]),
    ):
        meses = {m: None for m in MESES}
        meses.update({"ene": valores[0], "feb": valores[1]})
        filas.append({"ano": ano, "servicio_salud_codigo": 1, "establecimiento_codigo": codigo,
                      "nivel_cuidado_codigo": nivel_codigo, "nivel_cuidado": nivel, "indicador": indicador, **meses})
    return filas


def _oferta(*codigos_tipo):
    return pd.DataFrame([{"establecimiento_codigo": c, "tipo_establecimiento": t,
                          "establecimiento_nombre": f"Est {c}"} for c, t in codigos_tipo])


def _indicadores():
    return pd.DataFrame([
        *_area(101100, 418, PSIQ_ADULTO, [558.0, 551.0], [620.0, 580.0]),
        *_area(101100, 421, PSIQ_INFANTO, [279.0, 261.0], [310.0, 290.0]),
        *_area(101100, 427, SOCIOSANITARIA, [300.0, 300.0], [310.0, 290.0]),
        *_area(101100, 401, MEDICA, [900.0, 900.0], [930.0, 870.0]),
        *_area(202200, 418, PSIQ_ADULTO, [31.0, 29.0], [31.0, 29.0]),
    ])


def _mart():
    return module.build(_oferta((101100, "Hospital")), _indicadores())


def test_grano_area_mes_solo_areas_de_psiquiatria():
    mart = _mart()
    # 418 y 421, sin el área sociosanitaria ni la médica.
    assert sorted(mart.nivel_cuidado_codigo.unique()) == [418, 421]
    assert len(mart) == 4 and not mart.duplicated(list(module.KEY)).any()
    assert set(mart.nivel_cuidado) == {PSIQ_ADULTO, PSIQ_INFANTO}


def test_promedio_diario_es_dias_cama_sobre_dias_del_mes():
    area = _mart().set_index(["nivel_cuidado_codigo", "mes"])
    assert area.loc[(418, 1), "camas_ocupadas_promedio"] == pytest.approx(558 / 31)
    assert area.loc[(418, 2), "dias_mes"] == 29  # 2024 es bisiesto
    assert area.loc[(418, 2), "camas_disponibles_promedio"] == pytest.approx(580 / 29)


def test_brecha_es_camas_libres_por_dia():
    area = _mart().set_index(["nivel_cuidado_codigo", "mes"])
    assert area.loc[(418, 1), "camas_libres_promedio"] == pytest.approx((620 - 558) / 31)
    filas = pd.DataFrame(_area(101100, 418, PSIQ_ADULTO, [640.0, 580.0], [620.0, 580.0]))
    sobre = module.build(_oferta((101100, "Hospital")), filas).set_index("mes")
    assert sobre.loc[1, "camas_libres_promedio"] == pytest.approx(-20 / 31)  # sobre la capacidad
    assert sobre.loc[2, "camas_libres_promedio"] == 0


def test_total_del_hospital_suma_dias_cama_no_indices():
    filas = _indicadores()
    filas.loc[(filas.nivel_cuidado_codigo == 421) & (filas.indicador == module.OCUPADOS), "ene"] = 155.0
    total = module.por_hospital(module.build(_oferta((101100, "Hospital")), filas)).set_index("mes")
    assert total.loc[1, "dias_cama_ocupados"] == 558 + 155 and total.loc[1, "n_areas_psiquiatria"] == 2
    assert total.loc[1, "indice_ocupacional"] == pytest.approx(100 * (558 + 155) / 930)
    assert total.loc[1, "indice_ocupacional"] != pytest.approx((100 * 558 / 620 + 100 * 155 / 310) / 2)
    assert total.loc[1, "camas_libres_promedio"] == pytest.approx((930 - 713) / 31)


def test_solo_hospitales_de_la_oferta():
    mart = module.build(_oferta((101100, "Hospital"), (202200, "SAPU")), _indicadores())
    assert set(mart.establecimiento_codigo) == {101100}


def test_meses_no_publicados_no_generan_filas_ni_ceros():
    assert sorted(_mart().mes.unique()) == [1, 2]


def test_mes_publicado_a_medias_detiene_la_etapa():
    filas = _indicadores()
    filas.loc[(filas.nivel_cuidado_codigo == 418) & (filas.indicador == module.DISPONIBLES), "feb"] = None
    with pytest.raises(ValueError, match="a medias"):
        module.build(_oferta((101100, "Hospital")), filas)


def test_identidad_con_el_promedio_publicado_es_obligatoria():
    filas = _indicadores()
    filas.loc[(filas.nivel_cuidado_codigo == 418) & (filas.indicador == module.PROMEDIO_DISPONIBLES), "ene"] = 25.0
    with pytest.raises(ValueError, match="días disponibles / días del mes"):
        module.build(_oferta((101100, "Hospital")), filas)


def test_indice_nulo_sin_camas_disponibles():
    filas = pd.DataFrame(_area(101100, 418, PSIQ_ADULTO, [0.0, 0.0], [0.0, 0.0]))
    mart = module.build(_oferta((101100, "Hospital")), filas)
    assert mart.indice_ocupacional.isna().all() and (mart.camas_ocupadas_promedio == 0).all()


def test_validacion_y_escritura(tmp_path):
    mart = _mart()
    module.validate_mart(mart)
    with pytest.raises(ValueError, match="duplicada"):
        module.validate_mart(pd.concat([mart, mart.iloc[:1]]))
    destino = tmp_path / "mart.parquet"
    module._atomic_write(mart, destino)
    assert pq.read_schema(destino).remove_metadata() == module.SCHEMA.remove_metadata()


def test_saturacion_cuenta_meses_sin_holgura_y_sobre_capacidad():
    filas = pd.DataFrame([
        *_area(101100, 418, PSIQ_ADULTO, [620.0, 600.0], [620.0, 580.0]),   # 0 libres; luego sobre la capacidad
        *_area(101100, 421, PSIQ_INFANTO, [279.0, 261.0], [310.0, 290.0]),  # 1 cama libre por día: con holgura
    ])
    sat = eda.saturacion_por_area(module.build(_oferta((101100, "Hospital")), filas)).set_index("nivel_cuidado_codigo")
    assert sat.loc[418, "meses_sin_holgura"] == 2 and sat.loc[418, "meses_sobre_capacidad"] == 1
    assert sat.loc[421, "meses_sin_holgura"] == 0 and sat.loc[421, "meses_sobre_capacidad"] == 0
    assert sat.loc[418, "indice_ocupacional"] == pytest.approx(100 * 1220 / 1200)


def test_area_sin_camas_habilitadas_no_cuenta_como_saturada():
    filas = pd.DataFrame(_area(101100, 420, PSIQ_ADULTO, [300.0, 0.0], [310.0, 0.0]))
    resumen = module.resumen_areas(module.build(_oferta((101100, "Hospital")), filas)).iloc[0]
    # Enero: (310 - 300) / 31 = 0,32 camas libres por día, sin holgura. Febrero: 0 disponibles, cerrada.
    assert resumen.meses == 1 and resumen.meses_sin_holgura == 1 and resumen.meses_sobre_capacidad == 0
    assert resumen.ultimo_camas_disponibles_promedio == 0


def test_eda_verifica_identidad_y_detecta_ocupacion_sin_dotacion():
    oferta = _oferta((101100, "Hospital"), (303300, "Hospital"))
    indicadores = _indicadores()
    mart = module.build(oferta, indicadores)
    camas = pd.DataFrame({"establecimiento_codigo": [101100, 303300], "camas_psiquiatria": [None, 10.0]})
    resultado = eda.calcular(mart, indicadores, oferta, camas, {101100, 404400})
    assert resultado["identidad"]["area_mes"] == 4 and resultado["identidad"]["fuera_de_tolerancia"] == 0
    assert resultado["con_ocupacion_sin_dotacion"] == [101100]
    assert resultado["hospitales_oferta_sin_psiquiatria_rem20"] == 1
    assert resultado["pronostico_hospitalizaciones"] == {"hospitales": 2, "con_ocupacion": 1, "sin_ocupacion": [404400]}
    assert resultado["hospitales_detalle"][0]["huecos"] == 0
    assert len(resultado["saturacion_ultimos_meses"]["areas"]) == 2
    texto = eda.informe(resultado)
    assert texto.startswith(eda.TITULO) and "razón de sumas" in texto.lower() and "piso" in texto


@pytest.mark.parametrize("indice, sobre, nivel", [
    (84.99, 0, "holgura"), (85.0, 0, "presion"), (89.99, 0, "presion"), (90.0, 0, "saturacion"),
    (60.0, 1, "sobre_capacidad"), (None, 0, None),
])
def test_clasificacion_de_colapso_en_los_umbrales(indice, sobre, nivel):
    assert module.clasificar_colapso(indice, sobre) == nivel


def _mes(codigo, area, ano, mes, ocupados, disponibles):
    return {"establecimiento_codigo": codigo, "nivel_cuidado_codigo": area, "nivel_cuidado": f"{area} - Psiq",
            "ano": ano, "mes": mes, "dias_cama_ocupados": ocupados, "dias_cama_disponibles": disponibles}


def test_nivel_colapso_razon_de_sumas_en_ventana_comun():
    filas = [
        _mes(1, 418, 2025, 1, 990.0, 1000.0),   # fuera de la ventana de 12 meses
        *[_mes(1, 418, 2025, m, 270.0, 300.0) for m in range(3, 13)],
        _mes(1, 418, 2026, 1, 270.0, 300.0), _mes(1, 418, 2026, 2, 270.0, 300.0),
        _mes(1, 421, 2026, 2, 0.0, 0.0),        # área sin camas: no entra al índice
        _mes(2, 418, 2026, 2, 31.0, 30.0),      # sobre la capacidad
    ]
    nivel = module.nivel_colapso(module._derivar(pd.DataFrame(filas))).set_index("establecimiento_codigo")
    assert nivel.loc[1, "indice_ocupacional"] == pytest.approx(90.0) and nivel.loc[1, "nivel"] == "saturacion"
    assert nivel.loc[1, "meses"] == 12 and str(nivel.loc[1, "desde"]) == "2025-03-01"
    assert str(nivel.loc[1, "hasta"]) == "2026-02-01"
    assert nivel.loc[2, "nivel"] == "sobre_capacidad" and nivel.loc[2, "area_mes_sobre_capacidad"] == 1


def _dotacion(**camas_por_area):
    filas = [{"establecimiento_codigo": 101100, "area_funcional_codigo": 100, "area_funcional": "Total", "camas_2024": 99}]
    nombres = {418: "Área Psiquiatría Adulto", 421: "Área Psiquiatría Infanto", 401: "Área Médica"}
    for area, camas in camas_por_area.items():
        codigo = int(area.removeprefix("a"))
        filas.append({"establecimiento_codigo": 101100, "area_funcional_codigo": codigo,
                      "area_funcional": nombres[codigo], "camas_2024": camas})
    return pd.DataFrame(filas)


def test_backtest_dotacion_mide_acierto_del_estimador():
    # 418: disponibles 620/31 = 20 y 580/29 = 20 camas -> estima 20; 421: 10 y 10 -> estima 10.
    resultado = eda.backtest_dotacion(_indicadores(), _dotacion(a418=20, a421=12))
    mediana = resultado["mediana"]["psiquiatría"]
    assert mediana["areas_ano"] == 2 and mediana["exacto"] == 0.5 and mediana["a_1_cama"] == 0.5
    assert mediana["error_absoluto_medio"] == 1.0


def test_sin_dotacion_explica_la_causa_por_area():
    mart = _mart()
    causas = {x["nivel_cuidado_codigo"]: x["motivo"] for x in eda.sin_dotacion(mart, _dotacion(a418=20, a421=None))}
    assert 418 not in causas and "sin cifra" in causas[421]
    solo_418 = eda.sin_dotacion(mart, _dotacion(a418=20))
    assert "no es determinable" in solo_418[0]["motivo"]  # 421 existe desde 2024 = año del libro


def test_huecos_cuenta_meses_faltantes():
    assert eda.huecos(pd.DataFrame({"ano": [2025, 2025, 2026], "mes": [11, 12, 2]})) == 1
