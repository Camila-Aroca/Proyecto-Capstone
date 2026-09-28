"""Pruebas del pronostico futuro (`src/models/forecast.py`) y de la API (`src/api`).

Usan un panel sintetico y un servicio poblado en memoria: no dependen de
`data/processed/` ni de los reports del pipeline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.models.forecast as forecast_mod
from src.api.main import create_app
from src.api.service import (
    Estado,
    ServicioDemanda,
    cobertura_holdout,
    exclusiones,
    nombres_series,
    resumen_comunal,
)
from src.models.baseline import SeasonalNaive
from src.models.features import RM_SERIES_ID, SEASONAL_PERIOD, build_panel
from src.models.forecast import DatosActuales, append_future_rows, forecast_future

COMUNAS = ("13101", "13102")


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


def _weekly(anos: int = 3) -> pd.DataFrame:
    rng = np.random.RandomState(0)
    filas = []
    for indice, comuna in enumerate(COMUNAS):
        for ano in range(2023, 2023 + anos):
            for semana in range(1, SEASONAL_PERIOD + 1):
                nivel = 10 * (indice + 1) + 3 * np.sin(2 * np.pi * semana / SEASONAL_PERIOD)
                filas.append(
                    {
                        "comuna_codigo": comuna, "comuna_glosa": f"Comuna {comuna}",
                        "ano": ano, "semana": semana,
                        "atenciones_id36": max(0, int(nivel + rng.normal(0, 1))),
                        "poblacion_anual": 50_000 * (indice + 1),
                        "atenciones_id1": int(nivel * 10),
                        "n_establecimientos_reportantes_id36": 2,
                    }
                )
    return pd.DataFrame(filas)


def _calendario(panel: pd.DataFrame) -> pd.DataFrame:
    periodos = panel[["t", "ano", "semana"]].drop_duplicates().sort_values("t")
    periodos["fecha_inicio_semana"] = pd.Timestamp("2023-01-01") + pd.to_timedelta(
        periodos["t"] * 7, unit="D"
    )
    return periodos[["ano", "semana", "fecha_inicio_semana"]]


class TestFilasFuturas:
    def test_agrega_periodos_con_y_desconocido(self):
        panel = build_panel(_weekly())
        extendido = append_future_rows(panel, 3)
        futuros = extendido[extendido["es_futuro"]]
        assert futuros["y"].isna().all()
        assert sorted(futuros["t"].unique()) == [156, 157, 158]
        # Todas las series, region incluida, reciben las mismas filas futuras.
        assert futuros.groupby("series_id").size().nunique() == 1
        assert RM_SERIES_ID in set(futuros["series_id"])

    def test_el_calendario_salta_la_semana_53(self, monkeypatch):
        panel = build_panel(_weekly())
        monkeypatch.setattr(
            forecast_mod,
            "load_rm_population",
            lambda years: pd.DataFrame(
                {"comuna_codigo": list(COMUNAS), "ano": [years[0]] * 2, "poblacion": [1, 2]}
            ),
        )
        futuros = append_future_rows(panel, 2).query("es_futuro")
        semanas = futuros.drop_duplicates("t")[["ano", "semana"]].values.tolist()
        assert semanas == [[2026, 1], [2026, 2]]

    def test_anio_nuevo_usa_la_poblacion_proyectada(self, monkeypatch):
        panel = build_panel(_weekly())
        monkeypatch.setattr(
            forecast_mod,
            "load_rm_population",
            lambda years: pd.DataFrame(
                {"comuna_codigo": list(COMUNAS), "ano": [years[0]] * 2, "poblacion": [70, 30]}
            ),
        )
        futuros = append_future_rows(panel, 1).query("es_futuro").set_index("series_id")
        assert futuros.loc["13101", "poblacion_anual"] == 70
        assert futuros.loc[RM_SERIES_ID, "poblacion_anual"] == 100

    def test_fechas_futuras_avanzan_de_a_siete_dias(self):
        panel = build_panel(_weekly(2))
        extendido = append_future_rows(panel, 2, _calendario(panel))
        serie = extendido[extendido["series_id"] == "13101"].sort_values("t")
        ultimas = serie["fecha_inicio_semana"].tail(3).diff().dropna()
        assert (ultimas == pd.Timedelta(days=7)).all()

    def test_rechaza_cero_pasos(self):
        with pytest.raises(ValueError, match="al menos un periodo"):
            append_future_rows(build_panel(_weekly()), 0)


class TestPronosticoFuturo:
    def test_baseline_pronostica_el_mismo_periodo_del_anio_anterior(self):
        panel = build_panel(_weekly(2))
        extendido = append_future_rows(panel, 8)
        pronostico = forecast_future(extendido, SeasonalNaive(), horizontes=(4, 8))
        observado = panel.set_index(["series_id", "t"])["y"]
        for fila in pronostico.itertuples():
            assert fila.y_pred == observado[(fila.series_id, fila.t - SEASONAL_PERIOD)]
        assert set(pronostico["horizonte"]) == {4, 8}
        assert (pronostico["origen"] == int(panel["t"].max())).all()

    def test_exige_filas_futuras_suficientes(self):
        panel = build_panel(_weekly(2))
        with pytest.raises(ValueError, match="filas futuras suficientes"):
            forecast_future(append_future_rows(panel, 3), SeasonalNaive(), horizontes=(4,))


def _servicio_listo() -> ServicioDemanda:
    panel = build_panel(_weekly(2))
    calendario = _calendario(panel)
    pronostico = forecast_future(
        append_future_rows(panel, 8, calendario), SeasonalNaive(), horizontes=(4, 5)
    )
    territorial = pd.DataFrame(
        {
            "comuna_codigo": ["13101", "13102", "13132"],
            "comuna_glosa": ["Comuna 13101", "Comuna 13102", "Vitacura"],
            "indicador_vulnerabilidad": [0.1, 0.2, 0.05],
            "n_oferta_urgencia_actual": [3, 1, 1],
        }
    )
    diagnostico = {
        "comunas_sin_historia": pd.DataFrame({"comuna_codigo": ["13132"]}),
        "comunas_cobertura_incompleta": pd.DataFrame(
            {"comuna_codigo": [], "ultima_semana_con_datos": []}
        ),
    }
    servicio = ServicioDemanda(
        datos=DatosActuales(panel, calendario, [2024], diagnostico),
        territorial=territorial,
        geojson={"type": "FeatureCollection", "features": []},
        seleccion={
            "modelo_recomendado": "baseline_estacional",
            "nivel_intervalo": 0.8,
            "horizontes": [4, 5],
            "metricas_backtest": {"mase_region": 0.9},
        },
        pronostico=pronostico,
    )
    servicio.nombres = nombres_series(panel)
    servicio.motivos = exclusiones(diagnostico)
    servicio.estado_datos.marcar("listo")
    servicio.estado_pronostico.marcar("listo")
    return servicio


@pytest.fixture
def cliente():
    servicio = _servicio_listo()
    with TestClient(create_app(lambda: servicio, iniciar_calculos=False)) as c:
        yield c


class TestApi:
    def test_salud(self, cliente):
        assert cliente.get("/api/v1/salud").json()["estado_pronostico"] == "listo"

    def test_meta_informa_modelo_y_ultima_semana(self, cliente):
        meta = cliente.get("/api/v1/meta").json()
        assert meta["modelo"] == "baseline_estacional"
        assert meta["ultima_semana_observada"]["semana"] == SEASONAL_PERIOD
        assert meta["comunas_con_pronostico"] == 2
        assert any("sin pronóstico" in a for a in meta["advertencias"])

    def test_territorios_marcan_comunas_sin_pronostico(self, cliente):
        territorios = {t["series_id"]: t for t in cliente.get("/api/v1/territorios").json()}
        assert territorios[RM_SERIES_ID]["nivel"] == "region"
        assert not territorios["13132"]["tiene_pronostico"]
        assert "historia" in territorios["13132"]["motivo_sin_pronostico"]

    def test_serie_devuelve_historia_y_pronostico(self, cliente):
        serie = cliente.get("/api/v1/series/13101?semanas=10").json()
        assert len(serie["historico"]) == 10
        assert [p["horizonte"] for p in serie["pronostico"]] == [4, 5]
        punto = serie["pronostico"][0]
        assert punto["limite_inferior"] <= punto["pronostico"] <= punto["limite_superior"]

    def test_serie_sin_modelo_da_404_con_motivo(self, cliente):
        respuesta = cliente.get("/api/v1/series/13132")
        assert respuesta.status_code == 404
        assert "historia" in respuesta.json()["detail"]

    def test_pronosticos_filtra_por_nivel_y_horizonte(self, cliente):
        filas = cliente.get("/api/v1/pronosticos?nivel=comuna&horizonte=4").json()
        assert {f["series_id"] for f in filas} == set(COMUNAS)
        assert {f["horizonte"] for f in filas} == {4}
        assert cliente.get("/api/v1/pronosticos?nivel=otro").status_code == 422

    def test_resumen_incluye_comunas_sin_pronostico_en_null(self, cliente):
        filas = {f["series_id"]: f for f in cliente.get("/api/v1/resumen-comunal").json()}
        assert filas["13132"]["pronostico_promedio"] is None
        assert not filas["13132"]["tiene_pronostico"]
        assert filas["13101"]["tasa_pronostico_por_10000"] > 0

    def test_geojson(self, cliente):
        respuesta = cliente.get("/api/v1/geo/comunas")
        assert respuesta.headers["content-type"].startswith("application/geo+json")
        assert respuesta.json()["type"] == "FeatureCollection"


class TestEstadosIntermedios:
    def test_pronostico_en_calculo_da_503_con_reintento(self):
        servicio = _servicio_listo()
        servicio.estado_pronostico = Estado()
        servicio.estado_pronostico.marcar("calculando")
        with TestClient(create_app(lambda: servicio, iniciar_calculos=False)) as c:
            respuesta = c.get("/api/v1/pronosticos")
            assert respuesta.status_code == 503
            assert respuesta.headers["retry-after"] == "5"
            # La historia sigue disponible mientras tanto.
            serie = c.get("/api/v1/series/13101").json()
            assert serie["pronostico"] is None
            assert serie["estado_pronostico"] == "calculando"

    def test_error_de_datos_se_informa(self):
        servicio = ServicioDemanda()
        servicio.estado_datos.marcar("error", "Falta el mart: ejecute el pipeline.")
        with TestClient(create_app(lambda: servicio, iniciar_calculos=False)) as c:
            respuesta = c.get("/api/v1/meta")
            assert respuesta.status_code == 503
            assert "pipeline" in respuesta.json()["detail"]


class TestClasificacionDelCambio:
    def _resumen(self, reciente, inferior, superior, tiene=True):
        return pd.DataFrame(
            {
                "promedio_ultimas_semanas": [reciente],
                "limite_inferior_promedio": [inferior],
                "limite_superior_promedio": [superior],
                "tiene_pronostico": [tiene],
            }
        )

    @pytest.mark.parametrize(
        ("reciente", "esperado"),
        [(5.0, "alza"), (15.0, "estable"), (25.0, "baja")],
    )
    def test_solo_declara_cambio_fuera_del_intervalo(self, reciente, esperado):
        from src.api.service import clasificar_cambio

        assert clasificar_cambio(self._resumen(reciente, 10.0, 20.0)).iloc[0] == esperado

    def test_sin_pronostico_nunca_es_estable(self):
        from src.api.service import clasificar_cambio

        fila = self._resumen(15.0, None, None, tiene=False)
        assert clasificar_cambio(fila).iloc[0] == "sin_pronostico"

    def test_el_resumen_expone_la_clasificacion(self, cliente):
        filas = {f["series_id"]: f for f in cliente.get("/api/v1/resumen-comunal").json()}
        assert filas["13132"]["cambio_esperado"] == "sin_pronostico"
        assert filas["13101"]["cambio_esperado"] in {"alza", "baja", "estable"}
        assert filas["13101"]["limite_inferior_promedio"] <= filas["13101"]["limite_superior_promedio"]


class TestFuncionesPuras:
    def test_resumen_calcula_variacion_contra_ultimas_semanas(self):
        servicio = _servicio_listo()
        tabla = resumen_comunal(
            servicio.datos.panel, servicio.pronostico, servicio.territorial, servicio.motivos
        ).set_index("series_id")
        fila = tabla.loc["13101"]
        # Los insumos vienen redondeados a 0,1 y con series pequenas eso mueve la
        # variacion recalculada en algunas decimas; la tolerancia lo refleja.
        esperado = (fila["pronostico_promedio"] / fila["promedio_ultimas_semanas"] - 1) * 100
        assert fila["variacion_pct"] == pytest.approx(esperado, abs=1.0)

    def test_cobertura_holdout_sin_informe_es_none(self, tmp_path):
        assert cobertura_holdout(tmp_path / "no_existe.csv", "m", 0.8) is None

    def test_cobertura_holdout_pondera_por_evaluaciones(self, tmp_path):
        ruta = tmp_path / "holdout.csv"
        pd.DataFrame(
            {
                "modelo": ["m"] * 3,
                "series_id": [RM_SERIES_ID, "13101", "13102"],
                "n": [100, 100, 300],
                "cobertura": [0.8, 1.0, 0.6],
            }
        ).to_csv(ruta, index=False)
        cobertura = {c["nivel"]: c for c in cobertura_holdout(ruta, "m", 0.8)}
        assert cobertura["comuna"]["cobertura_observada"] == pytest.approx(0.7)
        assert cobertura["comuna"]["evaluaciones"] == 400
        assert cobertura["region"]["dentro_de_tolerancia"]
