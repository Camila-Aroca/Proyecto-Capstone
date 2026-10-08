"""Pruebas de la persistencia del pronostico (`src/models/persistence.py`).

Usan un panel sintetico y archivos temporales: no dependen de `data/processed/`ni de
los reports del pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.api.service as service_mod
import src.models.forecast as forecast_mod
from src.api.main import create_app
from src.api.service import Rutas, ServicioDemanda
from src.data.output_contracts import validate_expected_schema
from src.models.baseline import SeasonalNaive
from src.models.features import RM_SERIES_ID, SEASONAL_PERIOD, build_panel
from src.models.forecast import DatosActuales, append_future_rows, forecast_future
from src.models.persistence import (
    CLAVE_MART,
    CLAVE_SELECCION,
    ESQUEMA,
    Entradas,
    cargar,
    construir_manifiesto,
    guardar,
    motivo_desactualizacion,
    nombres_series,
)

COMUNAS = ("13101", "13102")
HORIZONTES = (4, 5)
SELECCION = {
    "modelo_recomendado": "baseline_estacional",
    "nivel_intervalo": 0.8,
    "horizontes": list(HORIZONTES),
    "semilla": 42,
}


@pytest.fixture(autouse=True)
def poblacion_falsa(monkeypatch):
    """Evita leer el cuadro INE real cuando el horizonte cruza a un anio nuevo."""
    monkeypatch.setattr(
        forecast_mod,
        "load_rm_population",
        lambda years: pd.DataFrame(
            [
                {"comuna_codigo": c, "ano": a, "poblacion": 50_000 * (i + 1)}
                for a in years
                for i, c in enumerate(COMUNAS)
            ]
        ),
    )


def _weekly(anos: int = 2) -> pd.DataFrame:
    rng = np.random.RandomState(0)
    filas = []
    for indice, comuna in enumerate(COMUNAS):
        for ano in range(2024, 2024 + anos):
            for semana in range(1, SEASONAL_PERIOD + 1):
                nivel = 10 * (indice + 1) + 3 * np.sin(2 * np.pi * semana / SEASONAL_PERIOD)
                filas.append(
                    {
                        "comuna_codigo": comuna,
                        "comuna_glosa": f"Comuna {comuna}",
                        "ano": ano,
                        "semana": semana,
                        "atenciones_id36": max(0, int(nivel + rng.normal(0, 1))),
                        "poblacion_anual": 50_000 * (indice + 1),
                        "atenciones_id1": int(nivel * 10),
                        "n_establecimientos_reportantes_id36": 2,
                    }
                )
    return pd.DataFrame(filas)


def _calendario(panel: pd.DataFrame) -> pd.DataFrame:
    periodos = panel[["t", "ano", "semana"]].drop_duplicates().sort_values("t")
    periodos["fecha_inicio_semana"] = pd.Timestamp("2024-01-01") + pd.to_timedelta(
        periodos["t"] * 7, unit="D"
    )
    return periodos[["ano", "semana", "fecha_inicio_semana"]]


@pytest.fixture
def datos() -> DatosActuales:
    panel = build_panel(_weekly())
    return DatosActuales(panel, _calendario(panel), [2025], {})


@pytest.fixture
def pronostico(datos: DatosActuales) -> pd.DataFrame:
    extendido = append_future_rows(datos.panel, max(HORIZONTES), datos.calendario)
    return forecast_future(extendido, SeasonalNaive(), horizontes=HORIZONTES)


@pytest.fixture
def entradas(tmp_path: Path) -> Entradas:
    """Dos archivos reales cuyo SHA256 define la vigencia del pronostico."""
    mart = tmp_path / "mart_urgencias_comuna_weekly.parquet"
    mart.write_bytes(b"panel-version-1")
    seleccion = tmp_path / "benchmark_demanda_sm_seleccion.json"
    seleccion.write_text(json.dumps(SELECCION), encoding="utf-8")
    return Entradas(mart_weekly=mart, seleccion=seleccion)


@pytest.fixture
def rutas(tmp_path: Path) -> tuple[Path, Path]:
    destino = tmp_path / "modeling"
    destino.mkdir()
    return (
        destino / "pronostico_demanda_sm.parquet",
        destino / "pronostico_demanda_sm_manifest.json",
    )


def _guardar(pronostico, datos, entradas, rutas) -> dict:
    manifiesto = construir_manifiesto(pronostico, datos, SELECCION, entradas)
    guardar(pronostico, manifiesto, nombres_series(datos.panel), *rutas)
    return manifiesto


# --------------------------------------------------------------------------------------
# Guardado y lectura
# --------------------------------------------------------------------------------------
def test_guardar_y_cargar_conserva_esquema_y_valores(pronostico, datos, entradas, rutas):
    _guardar(pronostico, datos, entradas, rutas)
    leido, manifiesto = cargar(*rutas)

    assert list(leido.columns) == [campo.name for campo in ESQUEMA]
    assert len(leido) == len(pronostico) == manifiesto["filas"]
    assert sorted(leido["horizonte"].unique()) == list(HORIZONTES)
    esperado = pronostico.sort_values(["series_id", "horizonte"])["y_pred"].to_numpy()
    obtenido = leido.sort_values(["series_id", "horizonte"])["y_pred"].to_numpy()
    assert np.allclose(obtenido, esperado)


def test_identifica_region_y_comunas_con_nombre_legible(pronostico, datos, entradas, rutas):
    _guardar(pronostico, datos, entradas, rutas)
    leido, _ = cargar(*rutas)

    region = leido[leido["series_id"] == RM_SERIES_ID]
    assert set(region["nivel"]) == {"region"}
    assert set(region["nombre"]) == {"Región Metropolitana"}
    assert set(leido.loc[leido["series_id"] != RM_SERIES_ID, "nivel"]) == {"comuna"}


def test_guardar_no_deja_archivos_temporales(pronostico, datos, entradas, rutas):
    _guardar(pronostico, datos, entradas, rutas)
    assert not list(rutas[0].parent.glob("*.tmp"))


def test_cargar_sin_pronostico_persistido_falla_con_el_stage(rutas):
    with pytest.raises(FileNotFoundError, match="forecast_demanda_sm"):
        cargar(*rutas)


# --------------------------------------------------------------------------------------
# Manifiesto
# --------------------------------------------------------------------------------------
def test_manifiesto_registra_modelo_datos_y_procedencia(pronostico, datos, entradas, rutas):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)

    assert manifiesto["modelo"] == SELECCION["modelo_recomendado"]
    assert manifiesto["horizontes"] == list(HORIZONTES)
    assert manifiesto["nivel_intervalo"] == SELECCION["nivel_intervalo"]
    assert manifiesto["semilla"] == SELECCION["semilla"]
    assert manifiesto["generado_en_utc"].endswith("Z")
    assert manifiesto["series"] == {"total": 3, "region": 1, "comuna": 2}
    assert manifiesto["versiones"]["pandas"] == pd.__version__
    assert set(manifiesto["entradas"]) == {CLAVE_MART, CLAVE_SELECCION}
    assert len(manifiesto["entradas"][CLAVE_MART]["sha256"]) == 64


def test_manifiesto_registra_la_ultima_semana_observada(pronostico, datos, entradas, rutas):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)
    observado = datos.panel[datos.panel["y"].notna()]
    ultima = observado.loc[observado["t"] == observado["t"].max()].iloc[0]

    assert manifiesto["ultima_semana_observada"]["t"] == int(ultima["t"])
    assert manifiesto["ultima_semana_observada"]["ano"] == int(ultima["ano"])
    assert manifiesto["ultima_semana_observada"]["semana"] == int(ultima["semana"])


# --------------------------------------------------------------------------------------
# Vigencia
# --------------------------------------------------------------------------------------
def test_pronostico_recien_generado_esta_vigente(pronostico, datos, entradas, rutas):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)
    assert motivo_desactualizacion(manifiesto) is None


@pytest.mark.parametrize("entrada", [CLAVE_MART, CLAVE_SELECCION])
def test_detecta_entrada_modificada(pronostico, datos, entradas, rutas, entrada):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)
    ruta = entradas.rutas()[entrada]
    ruta.write_bytes(ruta.read_bytes() + b"-modificado")

    motivo = motivo_desactualizacion(manifiesto)
    assert motivo is not None and entrada in motivo


def test_detecta_entrada_faltante(pronostico, datos, entradas, rutas):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)
    entradas.mart_weekly.unlink()

    assert "Falta la entrada" in (motivo_desactualizacion(manifiesto) or "")


def test_manifiesto_sin_entradas_no_se_considera_vigente(pronostico, datos, entradas, rutas):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)
    del manifiesto["entradas"][CLAVE_SELECCION]

    assert "no registra la entrada" in (motivo_desactualizacion(manifiesto) or "")


# --------------------------------------------------------------------------------------
# Contrato de outputs del orquestador
# --------------------------------------------------------------------------------------
def test_contrato_acepta_los_outputs_recien_generados(pronostico, datos, entradas, rutas):
    _guardar(pronostico, datos, entradas, rutas)

    assert validate_expected_schema(rutas[0]) is True
    assert validate_expected_schema(rutas[1]) is True


def test_contrato_rechaza_un_pronostico_desactualizado(pronostico, datos, entradas, rutas):
    _guardar(pronostico, datos, entradas, rutas)
    entradas.mart_weekly.write_bytes(b"panel-version-2")

    with pytest.raises(ValueError, match="desactualizado"):
        validate_expected_schema(rutas[1])


def test_contrato_rechaza_un_manifiesto_incompleto(pronostico, datos, entradas, rutas):
    manifiesto = _guardar(pronostico, datos, entradas, rutas)
    del manifiesto["modelo"]
    rutas[1].write_text(json.dumps(manifiesto), encoding="utf-8")

    with pytest.raises(ValueError, match="faltan claves"):
        validate_expected_schema(rutas[1])


# --------------------------------------------------------------------------------------
# Reutilizacion desde la API
# --------------------------------------------------------------------------------------
def _servicio(datos: DatosActuales, rutas: tuple[Path, Path]) -> ServicioDemanda:
    servicio = ServicioDemanda(
        rutas=Rutas(pronostico=rutas[0], manifiesto_pronostico=rutas[1]),
        datos=datos,
        seleccion=SELECCION,
    )
    servicio.nombres = nombres_series(datos.panel)
    servicio.estado_datos.marcar("listo")
    return servicio


def test_la_api_reutiliza_el_pronostico_persistido_sin_reajustar(
    pronostico, datos, entradas, rutas, monkeypatch
):
    _guardar(pronostico, datos, entradas, rutas)
    monkeypatch.setattr(
        service_mod,
        "ajustar_pronostico",
        lambda *_: pytest.fail("No debe reajustar: el pronóstico persistido está vigente."),
    )
    servicio = _servicio(datos, rutas)

    servicio.calcular_pronostico()

    assert servicio.origen_pronostico == "persistido"
    assert servicio.aviso_pronostico is None
    assert len(servicio.pronostico) == len(pronostico)
    assert servicio.estado_pronostico.estado == "listo"


def test_la_api_recalcula_y_advierte_si_no_hay_pronostico_persistido(
    pronostico, datos, rutas, monkeypatch
):
    monkeypatch.setattr(service_mod, "ajustar_pronostico", lambda *_: pronostico)
    servicio = _servicio(datos, rutas)

    servicio.calcular_pronostico()

    assert servicio.origen_pronostico == "en_memoria"
    assert "forecast_demanda_sm" in servicio.aviso_pronostico
    assert servicio.estado_pronostico.estado == "listo"


def test_la_api_recalcula_si_el_pronostico_persistido_quedo_desactualizado(
    pronostico, datos, entradas, rutas, monkeypatch
):
    _guardar(pronostico, datos, entradas, rutas)
    entradas.mart_weekly.write_bytes(b"panel-version-2")
    monkeypatch.setattr(service_mod, "ajustar_pronostico", lambda *_: pronostico)
    servicio = _servicio(datos, rutas)

    servicio.calcular_pronostico()

    assert servicio.origen_pronostico == "en_memoria"
    assert "cambió" in servicio.aviso_pronostico


def test_meta_informa_el_origen_del_pronostico(pronostico, datos, entradas, rutas):
    _guardar(pronostico, datos, entradas, rutas)
    servicio = _servicio(datos, rutas)
    servicio.calcular_pronostico()

    with TestClient(create_app(lambda: servicio, iniciar_calculos=False)) as cliente:
        cuerpo = cliente.get("/api/v1/meta").json()

    assert cuerpo["origen_pronostico"] == "persistido"
    assert cuerpo["pronostico_calculado_en"] is not None
