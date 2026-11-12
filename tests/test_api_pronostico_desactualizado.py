"""Interruptor temporal para servir el pronóstico persistido aunque no esté vigente."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.api import service
from src.api.service import VARIABLE_PRONOSTICO_DESACTUALIZADO, Rutas, ServicioDemanda

MOTIVO = "cambió 'seleccion_benchmark' respecto del snapshot con que se generó"


@pytest.fixture
def servicio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ServicioDemanda:
    pronostico = tmp_path / "pronostico.parquet"
    manifiesto = tmp_path / "manifiesto.json"
    pd.DataFrame({"series_id": ["RM"], "y_pred": [10.0]}).to_parquet(pronostico)
    manifiesto.write_text(json.dumps({"generado_en_utc": "2026-11-10T23:00:32Z"}), encoding="utf-8")
    monkeypatch.setattr(service, "motivo_desactualizacion", lambda manifiesto: MOTIVO)
    monkeypatch.setattr(service, "ajustar_pronostico", lambda datos, seleccion: pd.DataFrame({"recalculado": [1]}))
    return ServicioDemanda(rutas=Rutas(pronostico=pronostico, manifiesto_pronostico=manifiesto))


def test_sin_interruptor_recalcula(servicio: ServicioDemanda, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE_PRONOSTICO_DESACTUALIZADO, raising=False)
    pronostico, origen, _, aviso = servicio._obtener_pronostico()

    assert origen == "en_memoria"
    assert "recalculado" in pronostico.columns
    assert MOTIVO in aviso


def test_con_interruptor_sirve_el_persistido_y_lo_advierte(
    servicio: ServicioDemanda, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(VARIABLE_PRONOSTICO_DESACTUALIZADO, "1")
    pronostico, origen, generado, aviso = servicio._obtener_pronostico()

    assert origen == "persistido"
    assert pronostico["y_pred"].tolist() == [10.0]
    assert generado.isoformat().startswith("2026-11-10T23:00:32")
    assert aviso.startswith("Vista temporal") and MOTIVO in aviso


def test_con_interruptor_y_sin_persistido_recalcula(
    servicio: ServicioDemanda, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(VARIABLE_PRONOSTICO_DESACTUALIZADO, "1")
    servicio.rutas.pronostico.unlink()
    _, origen, _, _ = servicio._obtener_pronostico()

    assert origen == "en_memoria"
