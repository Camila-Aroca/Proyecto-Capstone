from datetime import date
import json

import numpy as np
import pandas as pd
import pytest

from src.data.build_mart_suicidios_comuna_weekly import calendario_deis
from src.models import suicidios as su
from src.models.backtesting import prepare_supervised
from src.models.features import RM_SERIES_ID

TASAS = {"13101": 0.6, "13102": 0.2, "13103": 0.05}  # suicidios por semana de 7 días
POBLACION = {"13101": 500_000, "13102": 300_000, "13103": 200_000}


def mart_sintetico(hasta: date = date(2026, 3, 28), semilla: int = 7, incompletas: int = 1) -> pd.DataFrame:
    """Mart con la forma real: Poisson con estacionalidad anual y exposición en días."""
    rng = np.random.default_rng(semilla)
    cal = calendario_deis(date(2022, 1, 1), hasta)
    filas = []
    for codigo, tasa in TASAS.items():
        for f in cal.itertuples():
            mu = tasa * f.dias_semana / 7 * np.exp(0.2 * np.cos(2 * np.pi * f.semana / 52))
            filas.append({"comuna_codigo": codigo, "comuna_glosa": f"Comuna {codigo}", "ano": f.ano,
                          "semana": f.semana, "fecha_inicio_semana": f.fecha_inicio_semana,
                          "fecha_fin_semana": f.fecha_fin_semana, "dias_semana": f.dias_semana,
                          "suicidios": int(rng.poisson(mu)), "defunciones_total": 100,
                          "poblacion_anual": POBLACION[codigo], "registro_completo": True})
    mart = pd.DataFrame(filas)
    if incompletas:
        ultimas = mart[mart["semana"] != 53].drop_duplicates(["ano", "semana"]).sort_values("fecha_inicio_semana").tail(incompletas)
        claves = set(zip(ultimas["ano"], ultimas["semana"]))
        mart.loc[[k in claves for k in zip(mart["ano"], mart["semana"])], "registro_completo"] = False
    return mart


def test_panel_region_es_suma_y_excluye_fragmentos_e_incompletas():
    mart = mart_sintetico()
    panel = su.build_panel(mart)
    region = panel[panel["series_id"] == RM_SERIES_ID].set_index("t")["y"]
    comunas = panel[panel["nivel"] == su.NIVEL_COMUNA].groupby("t")["y"].sum()
    assert region.equals(comunas.astype(region.dtype))
    assert (panel["semana"] != 53).all()
    ultima = mart[~mart["registro_completo"]].iloc[0]
    assert not ((panel["ano"] == ultima["ano"]) & (panel["semana"] == ultima["semana"])).any()


def test_panel_rechaza_registro_incompleto_en_medio():
    mart = mart_sintetico(incompletas=0)
    mart.loc[(mart["ano"] == 2023) & (mart["semana"] == 10), "registro_completo"] = False
    with pytest.raises(ValueError, match="en medio"):
        su.build_panel(mart)


def test_forma_gamma_distingue_heterogeneidad():
    esperados = np.full(40, 50.0)
    homogeneo = np.random.default_rng(1).poisson(esperados)
    heterogeneo = np.random.default_rng(1).poisson(esperados * np.random.default_rng(2).gamma(4, 1 / 4, 40))
    assert su.forma_gamma(homogeneo, esperados) > 50
    assert su.forma_gamma(heterogeneo, esperados) < 15


def test_cuantiles_conteo_cubren_al_menos_el_nivel():
    mu = np.array([0.2, 1.0, 10.0])
    inf, sup, cob = su.cuantiles_conteo(mu, 1.0, 0.8)
    assert (cob >= 0.8 - 1e-9).all() and (inf >= 0).all()
    _, sup_nb, _ = su.cuantiles_conteo(mu, 2.0, 0.8)
    assert (sup_nb >= sup).all() and sup_nb[-1] > sup[-1]


def test_modelo_coherente_y_cercano_a_la_tasa_real():
    panel = su.build_panel(mart_sintetico(hasta=date(2025, 12, 31), incompletas=0))
    sup = prepare_supervised(panel, (4,), exogenous=())[4]
    origen = int(panel["t"].max()) - 4
    modelo = su.PoissonEstacionalJerarquico(vida_media=52)
    pred = modelo.fit_predict(sup, origen, 4).set_index("series_id")
    assert pred.loc[RM_SERIES_ID, "y_pred"] == pytest.approx(pred.drop(RM_SERIES_ID)["y_pred"].sum())
    semana = int(panel.loc[panel["t"] == origen + 4, "semana"].iloc[0])
    verdad = sum(TASAS.values()) * np.exp(0.2 * np.cos(2 * np.pi * semana / 52))
    assert pred.loc[RM_SERIES_ID, "y_pred"] == pytest.approx(verdad, rel=0.25)
    assert (pred["cobertura_esperada"] >= 0.8).all()
    # Intervalo de enteros: con media 0,06 es [0, 0] (94%), y la media queda sobre el límite.
    assert (pred["y_inferior"] <= pred["y_pred"]).all()
    assert (pred["y_superior"] >= np.floor(pred["y_pred"])).all()
    assert pred.loc["13103", ["y_inferior", "y_superior"]].tolist() == [0.0, 0.0]


def test_exposicion_escala_semanas_cortas():
    panel = su.build_panel(mart_sintetico(hasta=date(2025, 12, 31), incompletas=0))
    sup = prepare_supervised(panel, (1,), exogenous=())[1]
    corta = panel[(panel["ano"] == 2025) & (panel["semana"] == 1)]["t"].iloc[0]  # 4 días
    normal = corta + 1
    modelo = su.PoissonEstacionalJerarquico(vida_media=None)
    a = modelo.fit_predict(sup, int(corta) - 1, 1).set_index("series_id").loc[RM_SERIES_ID, "y_pred"]
    b = modelo.fit_predict(sup, int(normal) - 1, 1).set_index("series_id").loc[RM_SERIES_ID, "y_pred"]
    assert a / b == pytest.approx(4 / 7, rel=0.02)


def test_sin_contraccion_reparte_por_poblacion():
    panel = su.build_panel(mart_sintetico(hasta=date(2025, 12, 31), incompletas=0))
    sup = prepare_supervised(panel, (1,), exogenous=())[1]
    pred = su.PoissonEstacionalJerarquico(contraccion=False).fit_predict(sup, int(panel["t"].max()) - 1, 1)
    pred = pred.set_index("series_id")
    assert pred.loc["13101", "y_pred"] / pred.loc["13103", "y_pred"] == pytest.approx(2.5)


def test_puntaje_intervalo_y_holm():
    s = su.puntaje_intervalo(np.array([5.0, 0.0, 12.0]), np.array([2.0, 1.0, 2.0]), np.array([8.0, 3.0, 10.0]), 0.8)
    assert s.tolist() == pytest.approx([6.0, 2.0 + 10.0, 8.0 + 20.0])
    assert su.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def _tabla(**filas):
    base = {"rmsse_region": 1.0, "rmsse_comuna": 1.0, "calibrado_region": True, "calibrado_comuna": True}
    return pd.DataFrame([{"modelo": k, **base, **v} for k, v in filas.items()]).assign(
        rmsse_promedio=lambda d: (d["rmsse_region"] + d["rmsse_comuna"]) / 2).sort_values("rmsse_promedio")


def test_seleccion_ignora_referencias_y_exige_calibracion():
    tabla = _tabla(**{
        su.REFERENCIA: {},
        su.REFERENCIA_CERO: {"rmsse_region": 0.1, "rmsse_comuna": 0.1},
        "a": {"rmsse_region": 0.7, "rmsse_comuna": 0.5, "calibrado_comuna": False},
        "b": {"rmsse_region": 0.8, "rmsse_comuna": 0.6},
    })
    assert su.seleccionar(tabla)[0] == "b"
    sin_calibrar = tabla.assign(calibrado_comuna=False)
    assert su.seleccionar(sin_calibrar)[0] == "a"
    assert su.seleccionar(_tabla(**{su.REFERENCIA: {}, "c": {"rmsse_region": 1.2}}))[0] == su.REFERENCIA


def test_registro_de_modelos_coincide_con_nombres():
    for nombre in su.available_models():
        assert su.build_model(nombre).name == nombre
    with pytest.raises(KeyError):
        su.build_model("no_existe")


def test_pronostico_coherente_con_fechas_y_dias(monkeypatch):
    mart = mart_sintetico()
    seleccion = {"modelo_recomendado": "poisson_estacional_eb_vm52", "nivel_intervalo": 0.8,
                 "horizontes": list(range(1, 9)), "ano_inicio": 2022}
    pron, panel = su.calcular_pronostico(mart, seleccion)
    assert sorted(pron["horizonte"].unique()) == list(range(1, 9))
    assert pron["series_id"].nunique() == len(TASAS) + 1
    suma = pron[pron["nivel"] == su.NIVEL_COMUNA].groupby("horizonte")["y_pred"].sum()
    region = pron[pron["nivel"] == "region"].set_index("horizonte")["y_pred"]
    assert np.allclose(suma, region)
    fechas = pron[pron["nivel"] == "region"].sort_values("horizonte")["fecha_inicio_semana"]
    assert (fechas.diff().dropna() == pd.Timedelta(days=7)).all()
    # El primer horizonte es la semana con registro incompleto, que no se usó para ajustar.
    incompleta = mart[~mart["registro_completo"]].iloc[0]
    primera = pron[(pron["nivel"] == "region") & (pron["horizonte"] == 1)].iloc[0]
    assert (primera["ano"], primera["semana"]) == (incompleta["ano"], incompleta["semana"])


def test_vigencia_detecta_cambios(tmp_path):
    mart, sel = tmp_path / "mart.parquet", tmp_path / "sel.json"
    mart.write_bytes(b"a")
    sel.write_text(json.dumps({"x": 1}), encoding="utf-8")
    manifiesto = {"entradas": su.huella(mart, sel)}
    assert su.motivo_desactualizacion(manifiesto) is None
    mart.write_bytes(b"b")
    assert "cambió" in su.motivo_desactualizacion(manifiesto)
    assert su.motivo_desactualizacion({"entradas": {}}) is not None


def test_diebold_mariano_detecta_diferencia_de_media_y_no_inventa_una():
    rng = np.random.default_rng(0)
    assert su.diebold_mariano(rng.normal(0, 1, 200), 1) > 0.05
    assert su.diebold_mariano(rng.normal(0.5, 1, 200), 1) < 1e-4
    assert su.diebold_mariano(np.zeros(10), 1) == 1.0


def test_comparacion_pareada_ve_la_media_aunque_la_mediana_favorezca_al_otro():
    # B acierta exactamente en 9 de cada 10 (ambos en cero) pero falla fuerte en el resto.
    filas_a, filas_b = [], []
    for origen in range(0, 120, 4):
        for h in (1, 2):
            for s in range(10):
                real = 3.0 if s == 0 else 0.0
                filas_a.append({"origen": origen, "horizonte": h, "series_id": str(s), "y_real": real, "y_pred": 0.3})
                filas_b.append({"origen": origen, "horizonte": h, "series_id": str(s), "y_real": real, "y_pred": 0.0})
    escala = pd.DataFrame({"escala_rmsse": 1.0}, index=[str(s) for s in range(10)])
    c = su.comparacion_pareada(pd.DataFrame(filas_a), pd.DataFrame(filas_b), escala, [str(s) for s in range(10)])
    assert c["proporcion_b_mejor"] == 0.9 and c["cambio_pct"] > 0 and c["origenes"] == 30
