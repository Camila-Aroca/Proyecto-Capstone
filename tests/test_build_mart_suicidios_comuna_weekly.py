from datetime import date

import pandas as pd
import pytest

from src.data import build_mart_suicidios_comuna_weekly as b


# Pares (fecha -> año, semana) tal como DEIS los publica en Urgencias.
@pytest.mark.parametrize("fecha, esperado", [
    (date(2020, 1, 1), (2020, 1)),
    (date(2021, 1, 1), (2021, 53)),
    (date(2022, 1, 1), (2022, 52)),
    (date(2024, 12, 29), (2024, 1)),
    (date(2025, 12, 28), (2025, 53)),
    (date(2026, 1, 1), (2026, 53)),
    (date(2026, 1, 3), (2026, 53)),
    (date(2026, 1, 4), (2026, 1)),
    (date(2026, 9, 27), (2026, 39)),
])
def test_semana_deis_reproduce_codificacion_publicada(fecha, esperado):
    assert b.semana_deis(fecha) == esperado


def test_dias_semana_en_bordes_de_ano():
    assert b.dias_semana(2025, 1) == 4
    assert b.dias_semana(2024, 1) == 9
    assert b.dias_semana(2026, 10) == 7


def test_calendario_cubre_cada_dia_una_vez():
    cal = b.calendario_deis(date(2024, 1, 1), date(2025, 12, 31))
    assert cal["dias_semana"].sum() == 731
    assert not cal.duplicated(["ano", "semana"]).any()


def test_es_suicidio_exige_coincidencia_con_el_grupo_publicado():
    ok = pd.DataFrame({"codigo_categoria_diag2": ["X70", "X84", "X85", None],
                       "codigo_grupo_diag2": ["X60-X84", "X60-X84", "X85-Y09", None]})
    assert b.es_suicidio(ok).tolist() == [True, True, False, False]
    mal = ok.assign(codigo_grupo_diag2=["X60-X84", "X58-X59", "X85-Y09", None])
    with pytest.raises(ValueError, match="difieren"):
        b.es_suicidio(mal)


def _semanal(por_dia: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"defunciones_total": [v * 7 for v in por_dia], "dias_semana": 7})


def test_registro_incompleto_solo_marca_semanas_finales():
    base = [100.0] * 10
    # Caída interior (0,6) no se marca; las dos últimas bajo el umbral sí.
    serie = base + [60.0] + base + [70.0, 50.0]
    marca = b.marcar_registro(_semanal(serie)).tolist()
    assert marca[10] is True
    assert marca[-2:] == [False, False]
    assert all(marca[:-2])


def test_registro_se_detiene_en_la_primera_semana_completa():
    serie = [100.0] * 10 + [40.0, 99.0]
    assert b.marcar_registro(_semanal(serie)).tolist() == [True] * 12


def test_registro_diario_detecta_un_ultimo_dia_rezagado_en_semana_no_detectada():
    dias = pd.date_range("2026-08-30", periods=70)
    diarios = pd.Series(100, index=dias.date)
    diarios.iloc[-1] = 14
    semanas = pd.DataFrame({"fecha_fin_semana": [dias[-8].date(), dias[-1].date()],
                            "defunciones_total": [700, 614], "dias_semana": [7, 7]})
    assert b.marcar_registro(semanas, referencia=1).tolist() == [True, True]
    assert b.marcar_registro_diario(semanas, diarios).tolist() == [True, False]


def test_registro_diario_no_marca_sin_historia_suficiente():
    dias = pd.date_range("2026-10-01", periods=7)
    semanas = pd.DataFrame({"fecha_fin_semana": [dias[-1].date()]})
    assert b.marcar_registro_diario(semanas, pd.Series(1, index=dias.date)).tolist() == [True]


def test_build_no_utiliza_semana_final_con_ultimo_dia_rezagado():
    dias = pd.date_range("2026-08-30", periods=70).date
    fechas = [dia for dia in dias for _ in range(14 if dia == dias[-1] else 100)]
    eventos = pd.DataFrame({"fecha_defuncion": fechas, "comuna_codigo": "13101",
                            "codigo_categoria_diag2": "I21", "codigo_grupo_diag2": "I20-I25"})
    comunas = pd.DataFrame({"comuna_codigo": ["13101"], "comuna_glosa": ["Santiago"]})
    poblacion = pd.DataFrame({"comuna_codigo": ["13101"], "ano": [2026], "poblacion": [500000]})
    mart = b.build(eventos, comunas, poblacion, dias[0], dias[-1]).sort_values("fecha_inicio_semana")
    assert bool(mart.iloc[-2]["registro_completo"])
    assert not bool(mart.iloc[-1]["registro_completo"])


def _insumos():
    comunas = pd.DataFrame({"comuna_codigo": ["13101", "13102"], "comuna_glosa": ["Santiago", "Cerrillos"]})
    poblacion = pd.DataFrame({"comuna_codigo": ["13101", "13102"] * 2, "ano": [2025, 2025, 2026, 2026],
                              "poblacion": [500_000, 80_000, 510_000, 81_000]})
    filas = [
        (date(2025, 12, 30), "13101", "X70", "X60-X84"),
        (date(2026, 1, 5), "13101", "X70", "X60-X84"),
        (date(2026, 1, 6), "13102", "I21", "I20-I25"),
        (date(2026, 1, 14), "13102", "X80", "X60-X84"),
        (date(2026, 1, 15), "13101", "X85", "X85-Y09"),
    ]
    defunciones = pd.DataFrame(filas, columns=["fecha_defuncion", "comuna_codigo", "codigo_categoria_diag2",
                                               "codigo_grupo_diag2"])
    return defunciones, comunas, poblacion


def test_build_grilla_completa_con_ceros_y_semana_truncada_fuera():
    defunciones, comunas, poblacion = _insumos()
    # Corte jueves 15-01-2026: la semana 2 (11-17 de enero) queda truncada y no se publica.
    mart = b.build(defunciones, comunas, poblacion, date(2025, 12, 1), date(2026, 1, 15))
    assert set(mart["comuna_codigo"]) == {"13101", "13102"}
    assert mart.groupby("comuna_codigo").size().nunique() == 1
    assert not ((mart["ano"] == 2026) & (mart["semana"] == 2)).any()
    assert int(mart["suicidios"].sum()) == 2  # el del 14-01 cae en la semana truncada
    fila = mart[(mart["comuna_codigo"] == "13102") & (mart["ano"] == 2026) & (mart["semana"] == 1)].iloc[0]
    assert (fila["suicidios"], fila["defunciones_total"]) == (0, 1)
    assert mart["poblacion_anual"].notna().all()
    fragmento = mart[(mart["ano"] == 2025) & (mart["semana"] == 53)]
    assert fragmento["dias_semana"].iloc[0] == 4 and fragmento["suicidios"].sum() == 1


def test_build_falla_con_residente_fuera_del_universo():
    defunciones, comunas, poblacion = _insumos()
    defunciones.loc[0, "comuna_codigo"] = "13999"
    with pytest.raises(ValueError, match="fuera de las 52"):
        b.build(defunciones, comunas, poblacion, date(2025, 12, 1), date(2026, 1, 15))


def test_validate_mart_exige_conciliacion():
    defunciones, comunas, poblacion = _insumos()
    mart = b.build(defunciones, comunas, poblacion, date(2025, 12, 1), date(2026, 1, 15))
    b.validate_mart(mart, 2)
    with pytest.raises(ValueError, match="no concilia"):
        b.validate_mart(mart, 3)
