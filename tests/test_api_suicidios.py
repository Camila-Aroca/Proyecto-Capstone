"""Pruebas del endpoint de suicidios con un pronóstico persistido sintético (no lee data/processed)."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.service import ServicioDemanda
from src.api.suicidios import RutasSuicidios, ServicioSuicidios, cobertura_por_nivel, tasa_reciente
from src.data.build_mart_suicidios_comuna_weekly import SCHEMA
from src.models import suicidios as su
from tests.test_models_suicidios import mart_sintetico

SELECCION = {"modelo_recomendado": "poisson_estacional_eb_vm52", "nivel_intervalo": 0.8,
             "horizontes": list(range(1, 9)), "ano_inicio": 2022}


@pytest.fixture(scope="module")
def rutas(tmp_path_factory) -> RutasSuicidios:
    base = tmp_path_factory.mktemp("suicidios")
    mart = mart_sintetico()
    ruta_mart, ruta_sel = base / "mart.parquet", base / "seleccion.json"
    pq.write_table(pa.Table.from_pandas(mart, schema=SCHEMA, preserve_index=False), ruta_mart)
    ruta_sel.write_text(json.dumps(SELECCION), encoding="utf-8")
    pronostico, panel = su.calcular_pronostico(mart, SELECCION)
    manifiesto = su.construir_manifiesto(pronostico, panel, mart, SELECCION, su.huella(ruta_mart, ruta_sel))
    rutas = RutasSuicidios(mart=ruta_mart, pronostico=base / "p.parquet", manifiesto=base / "m.json",
                           holdout_resumen=base / "holdout.csv")
    su.guardar(pronostico, manifiesto, rutas.pronostico, rutas.manifiesto)
    pd.DataFrame([
        {"series_id": "RM", "modelo": SELECCION["modelo_recomendado"], "n": 10, "cobertura": 0.8, "cobertura_esperada": 0.85},
        {"series_id": "13101", "modelo": SELECCION["modelo_recomendado"], "n": 10, "cobertura": 1.0, "cobertura_esperada": 0.95},
        {"series_id": "13102", "modelo": SELECCION["modelo_recomendado"], "n": 30, "cobertura": 0.9, "cobertura_esperada": 0.97},
    ]).to_csv(rutas.holdout_resumen, index=False)
    return rutas


def _cliente(servicio: ServicioSuicidios) -> TestClient:
    return TestClient(create_app(lambda: ServicioDemanda(), iniciar_calculos=False, fabrica_suicidios=lambda: servicio))


def test_serie_regional_y_comunal(rutas):
    servicio = ServicioSuicidios(rutas=rutas)
    servicio.cargar()
    assert servicio.estado.estado == "listo", servicio.estado.detalle
    with _cliente(servicio) as c:
        region = c.get("/api/v1/suicidios/RM?semanas=26").json()
        comuna = c.get("/api/v1/suicidios/13102").json()
    assert len(region["historico"]) == 26 and len(region["pronostico"]) == 8
    assert region["nivel"] == "region" and comuna["nivel"] == "comuna"
    assert region["semanas_registro_incompleto"] and region["modelo"] == SELECCION["modelo_recomendado"]
    # Las comunas suman la región en cada horizonte.
    total = sum(c_["pronostico"] for s in ("13101", "13102", "13103")
                for c_ in servicio.serie(s, 4)["pronostico"] if c_["horizonte"] == 1)
    assert total == pytest.approx(region["pronostico"][0]["pronostico"], abs=0.02)
    assert comuna["cobertura_holdout"] == {"observada": 0.925, "esperada": 0.965, "evaluaciones": 40}
    ultima = region["historico"][-1]
    assert (ultima["ano"], ultima["semana"]) == (region["ultima_semana_observada"]["ano"],
                                                  region["ultima_semana_observada"]["semana"])


def test_territorio_inexistente_da_404(rutas):
    servicio = ServicioSuicidios(rutas=rutas)
    servicio.cargar()
    with _cliente(servicio) as c:
        assert c.get("/api/v1/suicidios/99999").status_code == 404


def test_pronostico_vencido_responde_503_con_el_stage(rutas, tmp_path):
    copia = tmp_path / "mart.parquet"
    copia.write_bytes(rutas.mart.read_bytes())
    manifiesto = json.loads(rutas.manifiesto.read_text(encoding="utf-8"))
    manifiesto["entradas"][su.CLAVE_MART]["sha256"] = "otro"
    vencido = tmp_path / "m.json"
    vencido.write_text(json.dumps(manifiesto), encoding="utf-8")
    servicio = ServicioSuicidios(rutas=RutasSuicidios(mart=copia, pronostico=rutas.pronostico, manifiesto=vencido))
    servicio.cargar()
    with _cliente(servicio) as c:
        r = c.get("/api/v1/suicidios/RM")
    assert r.status_code == 503 and "forecast_suicidios" in r.json()["detail"]
    assert "Retry-After" not in r.headers


def test_mientras_carga_pide_reintentar():
    with _cliente(ServicioSuicidios()) as c:
        r = c.get("/api/v1/suicidios/RM")
    assert r.status_code == 503 and r.headers["Retry-After"] == "5"


def test_tasa_reciente_incluye_fragmentos_de_borde_de_ano():
    # Ventana de 364 días que cruza el año: la semana 53 (fragmento) se cuenta.
    mart = mart_sintetico(hasta=date(2026, 3, 28), incompletas=0)
    fin = date(2026, 3, 28)
    total, tasa = tasa_reciente(mart, "13101", fin)
    inicio = date(2025, 3, 30)
    esperado = mart[(mart["comuna_codigo"] == "13101") & (mart["fecha_inicio_semana"] >= inicio)
                    & (mart["fecha_fin_semana"] <= fin)]
    assert ((esperado["ano"] == 2025) & (esperado["semana"] == 53)).any()
    assert total == int(esperado["suicidios"].sum())
    assert tasa == pytest.approx(total / 500_000 * 1e5 * 365.25 / 364, abs=0.01)
    region, _ = tasa_reciente(mart, "RM", fin)
    assert region == int(mart[(mart["fecha_inicio_semana"] >= inicio) & (mart["fecha_fin_semana"] <= fin)]["suicidios"].sum())
    assert cobertura_por_nivel(None, "m", "region") is None


def test_calendario_eventos_endpoint():
    with _cliente(ServicioSuicidios()) as c:
        r = c.get("/api/v1/calendario-eventos?desde=2025-12-01&hasta=2026-01-15")
        assert r.status_code == 200
        nombres = {e["nombre"] for e in r.json()}
        assert {"Navidad", "Año Nuevo", "Primavera", "Verano"} <= nombres
        assert c.get("/api/v1/calendario-eventos?desde=2026-02-01&hasta=2026-01-01").status_code == 422
        assert c.get("/api/v1/calendario-eventos?desde=2000-01-01&hasta=2026-01-01").status_code == 422
