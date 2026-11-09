"""Pruebas del endpoint de hospitalizaciones de residentes (egresos F00-F99)."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.api.hospitalizaciones as hosp
from src.api.main import create_app
from src.api.service import ServicioDemanda


def _anual() -> pd.DataFrame:
    filas = []
    for sid, nivel, nombre in (("RM", "region", "Región Metropolitana"), ("13101", "comuna", "Santiago")):
        for ano, egresos, pob in ((2020, 10, None), (2021, 20, 10_000)):
            filas.append({"series_id": sid, "nivel": nivel, "nombre": nombre, "ano": ano, "egresos": egresos,
                          "poblacion": pob, "tasa_por_10000": None if pob is None else egresos / pob * 10_000,
                          "dias_estada_mediana": 12.0, "dias_estada_p90": 40.0, "proporcion_snss": 0.6,
                          "proporcion_estadia_mayor_a_un_ano": 0.01})
    return pd.DataFrame(filas)


def _desglose() -> pd.DataFrame:
    return pd.DataFrame([
        {"series_id": sid, "ano": 2021, "dimension": "sexo", "categoria": cat, "orden": orden, "egresos": n}
        for sid in ("RM", "13101") for cat, orden, n in (("Mujer", 0, 12), ("Hombre", 1, 8))
    ])


def _contraste() -> pd.DataFrame:
    return pd.DataFrame([{"ano": 2021, "egresos_residentes_rm": 20, "camas_equivalentes_egresos": 6.0,
                          "camas_equivalentes_egresos_snss": 4.0, "camas_ocupadas_rem20": 5.0,
                          "camas_ocupadas_rem20_sin_forense": 4.2, "razon_egresos_snss_rem20_sin_forense": 0.952}])


class TestPerfil:
    def test_region_trae_serie_desglose_y_contraste(self):
        cuerpo = hosp.perfil(_anual(), _desglose(), _contraste(), "RM", None)
        assert cuerpo["ano_desglose"] == 2021 and [p["ano"] for p in cuerpo["anual"]] == [2020, 2021]
        assert cuerpo["anual"][0]["tasa_por_10000"] is None
        assert cuerpo["desglose"]["sexo"][0] == {"categoria": "Mujer", "egresos": 12, "proporcion": 0.6}
        assert cuerpo["contraste_camas"][0]["razon_egresos_snss_rem20_sin_forense"] == 0.952

    def test_comuna_no_trae_el_contraste_regional(self):
        assert hosp.perfil(_anual(), _desglose(), _contraste(), "13101", None)["contraste_camas"] is None

    def test_territorio_inexistente_404_y_ano_invalido_422(self):
        with pytest.raises(HTTPException) as e404:
            hosp.perfil(_anual(), _desglose(), None, "99999", None)
        with pytest.raises(HTTPException) as e422:
            hosp.perfil(_anual(), _desglose(), None, "RM", 1999)
        assert e404.value.status_code == 404 and e422.value.status_code == 422


def test_sin_output_responde_503_con_la_etapa(tmp_path, monkeypatch):
    monkeypatch.setattr(hosp, "ANUAL_PATH", tmp_path / "no_existe.parquet")
    app = create_app(lambda: ServicioDemanda(), iniciar_calculos=False)
    with TestClient(app) as c:
        respuesta = c.get("/api/v1/hospitalizaciones-residentes/RM")
    assert respuesta.status_code == 503 and "build_mart_egresos_f00_f99_rm" in respuesta.json()["detail"]


def test_endpoint_con_outputs_sinteticos(tmp_path, monkeypatch):
    for nombre, frame in (("anual", _anual()), ("desglose", _desglose()), ("contraste", _contraste())):
        frame.to_parquet(tmp_path / f"{nombre}.parquet")
    monkeypatch.setattr(hosp, "ANUAL_PATH", tmp_path / "anual.parquet")
    monkeypatch.setattr(hosp, "DESGLOSE_PATH", tmp_path / "desglose.parquet")
    monkeypatch.setattr(hosp, "CONTRASTE_PATH", tmp_path / "contraste.parquet")
    app = create_app(lambda: ServicioDemanda(), iniciar_calculos=False)
    with TestClient(app) as c:
        cuerpo = c.get("/api/v1/hospitalizaciones-residentes/RM").json()
    assert cuerpo["nombre"] == "Región Metropolitana" and len(cuerpo["contraste_camas"]) == 1
