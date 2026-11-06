"""Pruebas de la API del pronóstico por establecimiento.

Usan un servicio poblado en memoria con datos sintéticos: no leen
`data/processed/` ni los reports.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.establecimientos import (
    MOTIVO_FUERA_DE_RANGO,
    ServicioEstablecimientos,
    cobertura_objetivo,
    motivos_sin_pronostico,
    areas_en_ventana,
    colapso_por_establecimiento,
    dotacion_por_area,
    motivo_sin_dotacion,
    ocupacion_en_ventana,
    resumen_establecimientos,
)
from src.api.main import create_app
from src.data import build_mart_ocupacion_psiquiatria_hospital_rm as mart_ocupacion
from src.data.build_mart_ocupacion_psiquiatria_hospital_rm import nivel_colapso
from src.api.service import ServicioDemanda


def _semanal() -> pd.DataFrame:
    filas = []
    for codigo, (nombre, tipo, id36, id42) in {
        10: ("Hospital A", "Hospital", 40, 8),
        11: ("SAPU B", "SAPU", 6, 0),
        12: ("SAR C", "SAR", 0, 0),
    }.items():
        for semana in range(1, 11):
            filas.append({
                "establecimiento_codigo": codigo, "ano": 2026, "semana": semana,
                "fecha_inicio_semana": f"2026-01-{semana:02d}", "establecimiento_glosa": nombre,
                "tipo_establecimiento_urgencia": tipo, "comuna_codigo": "13101", "comuna_glosa": "Santiago",
                "atenciones_id36": id36, "atenciones_id42": id42, "atenciones_id1": id36 * 10,
            })
    return pd.DataFrame(filas)


def _pronostico() -> pd.DataFrame:
    filas = []
    for objetivo, series in {"atenciones_sm": {"10": 44.0, "11": 6.6}, "hospitalizaciones_sm": {"10": 9.0}}.items():
        for series_id, valor in series.items():
            for horizonte in (1, 2):
                filas.append({
                    "objetivo": objetivo, "series_id": series_id, "horizonte": horizonte,
                    "ano": 2026, "semana": 10 + horizonte, "fecha_inicio_semana": date(2026, 3, horizonte),
                    "y_pred": valor, "y_inferior": valor * 0.8, "y_superior": valor * 1.2,
                    # El SAPU B tiene un horizonte retenido por la guardia de plausibilidad.
                    "fuera_de_rango": series_id == "11" and horizonte == 2,
                })
    return pd.DataFrame(filas)


def _universo() -> pd.DataFrame:
    return pd.DataFrame({
        "objetivo": ["atenciones_sm"] * 3 + ["hospitalizaciones_sm"] * 3,
        "establecimiento_codigo": [10, 11, 12] * 2,
        "incluido": [True, True, False, True, False, False],
        "motivo_exclusion": [None, None, "volumen medio menor a 1 por semana", None, "no es hospital", "no es hospital"],
    })


def _atributos() -> pd.DataFrame:
    return pd.DataFrame({
        "establecimiento_codigo": [10, 11, 12], "nombre": ["Hospital A", "SAPU B", "SAR C"],
        "tipo": ["Hospital", "SAPU", "SAR"], "comuna_codigo": ["13101"] * 3, "comuna": ["Santiago"] * 3,
        "latitud": [-33.4, -33.5, None], "longitud": [-70.6, -70.7, None],
        "camas_psiquiatria": [20.0, None, None],
    })


def _manifiesto() -> dict:
    return {
        "generado_en_utc": "2026-11-01T00:00:00Z",
        "objetivos": {
            "atenciones_sm": {"modelo": "m1", "horizontes": [1, 2], "nivel_intervalo": 0.8, "establecimientos": 2,
                              "fuera_de_rango": 1, "ultima_semana_observada": {"t": 9, "ano": 2026, "semana": 10},
                              "excluidos_por_cobertura_en_curso": []},
            "hospitalizaciones_sm": {"modelo": "m2", "horizontes": [1, 2], "nivel_intervalo": 0.8, "establecimientos": 1,
                                     "fuera_de_rango": 0, "ultima_semana_observada": {"t": 9, "ano": 2026, "semana": 10},
                                     "excluidos_por_cobertura_en_curso": []},
        },
    }


def _ocupacion() -> pd.DataFrame:
    """Hospital A, dos áreas: diciembre (fuera de la ventana de la historia) y dos meses dentro.

    Área 418: 20 camas, llena en febrero (sin holgura); área 421: 10 camas con holgura.
    """
    filas = []
    for ano, mes, ocup_418, ocup_421 in ((2025, 12, 558.0, 248.0), (2026, 1, 589.0, 248.0), (2026, 2, 560.0, 196.0)):
        dias = {12: 31, 1: 31, 2: 28}[mes]
        filas.append({"establecimiento_codigo": 10, "nivel_cuidado_codigo": 418, "nivel_cuidado": "418 - Psiq. adulto",
                      "ano": ano, "mes": mes, "dias_cama_ocupados": ocup_418, "dias_cama_disponibles": 20.0 * dias})
        filas.append({"establecimiento_codigo": 10, "nivel_cuidado_codigo": 421, "nivel_cuidado": "421 - Psiq. infanto",
                      "ano": ano, "mes": mes, "dias_cama_ocupados": ocup_421, "dias_cama_disponibles": 10.0 * dias})
    return mart_ocupacion._derivar(pd.DataFrame(filas))


def _servicio() -> ServicioEstablecimientos:
    semanal, pronostico, manifiesto = _semanal(), _pronostico(), _manifiesto()
    servicio = ServicioEstablecimientos(
        semanal=semanal, pronostico=pronostico, manifiesto=manifiesto, atributos=_atributos(),
        calendario=semanal.groupby(["ano", "semana"], as_index=False)["fecha_inicio_semana"].min(),
        motivos=motivos_sin_pronostico(_universo(), pronostico, manifiesto),
        holdout=pd.DataFrame({
            "objetivo": ["atenciones_sm"] * 2, "modelo": ["m1"] * 2, "series_id": ["10", "11"],
            "n": [30, 10], "cobertura": [0.8, 0.6],
        }),
        ocupacion=_ocupacion(),
        colapso=nivel_colapso(_ocupacion()),
    )
    servicio.estado.marcar("listo")
    return servicio


@pytest.fixture
def cliente():
    servicio = _servicio()
    app = create_app(lambda: ServicioDemanda(), iniciar_calculos=False, fabrica_establecimientos=lambda: servicio)
    with TestClient(app) as c:
        yield c


class TestFuncionesPuras:
    def test_resumen_informa_reciente_y_pronostico(self):
        servicio = _servicio()
        filas = {f["establecimiento_codigo"]: f for f in resumen_establecimientos(
            servicio.semanal, servicio.pronostico, servicio.atributos, servicio.motivos)}
        hospital = filas[10]["objetivos"]["atenciones_sm"]
        assert hospital["incluido"] and hospital["promedio_ultimas_semanas"] == 40.0
        assert hospital["pronostico_promedio"] == 44.0 and hospital["variacion_pct"] == 10.0

    def test_un_horizonte_retenido_no_entra_al_promedio(self):
        servicio = _servicio()
        filas = {f["establecimiento_codigo"]: f for f in resumen_establecimientos(
            servicio.semanal, servicio.pronostico, servicio.atributos, servicio.motivos)}
        # El SAPU B conserva su horizonte 1; el 2 quedó fuera de rango.
        assert filas[11]["objetivos"]["atenciones_sm"]["pronostico_promedio"] == 6.6

    def test_sin_pronostico_se_explica_y_no_es_cero(self):
        servicio = _servicio()
        filas = {f["establecimiento_codigo"]: f for f in resumen_establecimientos(
            servicio.semanal, servicio.pronostico, servicio.atributos, servicio.motivos)}
        sar = filas[12]["objetivos"]["atenciones_sm"]
        assert not sar["incluido"] and sar["pronostico_promedio"] is None
        assert "volumen medio" in sar["motivo_sin_pronostico"]

    def test_motivo_de_la_guardia_de_plausibilidad(self):
        motivos = motivos_sin_pronostico(_universo(), _pronostico(), _manifiesto())
        assert motivos[("atenciones_sm", 11)] == MOTIVO_FUERA_DE_RANGO

    def test_cobertura_ponderada_por_evaluaciones(self):
        assert cobertura_objetivo(_servicio().holdout, "atenciones_sm", "m1") == pytest.approx(0.75)
        assert cobertura_objetivo(None, "atenciones_sm", "m1") is None


    def test_ocupacion_recortada_a_la_ventana_y_sumada_por_hospital(self):
        meses = ocupacion_en_ventana(_ocupacion(), 10, "2026-01-05")
        assert [(m["ano"], m["mes"]) for m in meses] == [(2026, 1), (2026, 2)]
        enero = meses[0]
        assert enero["camas_ocupadas_promedio"] == round((589 + 248) / 31, 1)
        assert enero["camas_disponibles_promedio"] == 30.0
        assert enero["indice_ocupacional"] == round(100 * (589 + 248) / 930, 1)  # razón de sumas
        assert enero["camas_libres_promedio"] == round((930 - 837) / 31, 1)

    def test_saturacion_por_area_en_la_ventana(self):
        areas = {a["nivel_cuidado_codigo"]: a for a in areas_en_ventana(_ocupacion(), 10, "2026-01-05")}
        # 418: enero 589/620 (1 cama libre por día) y febrero 560/560 (0): solo febrero sin holgura.
        assert areas[418]["meses"] == 2 and areas[418]["meses_sin_holgura"] == 1
        assert areas[418]["meses_sobre_capacidad"] == 0 and areas[418]["ultimo_camas_libres_promedio"] == 0.0
        assert areas[421]["meses_sin_holgura"] == 0
        assert areas[418]["dotacion_declarada"] is None  # sin libro de dotación: null, no cero
        # Cada área trae su serie mensual en la ventana, para dinamizar el gráfico.
        assert [m["mes"] for m in areas[418]["serie"]] == [1, 2]
        assert areas[418]["serie"][1]["camas_libres_promedio"] == 0.0

    def test_dotacion_declarada_por_area_del_ultimo_ano(self):
        dotacion = pd.DataFrame({
            "establecimiento_codigo": [10, 10, 10, 10],
            "area_funcional_codigo": [100, 418, 421, 427],
            "area_funcional": ["Total", "Área Psiquiatría Adulto", "Área Psiquiatría Infanto", "Área Sociosanitaria"],
            "camas_2024": [90, 18, 9, 30], "camas_2025": [95, 22, None, 30],
        })
        por_area = dotacion_por_area(dotacion)
        assert set(por_area["area_funcional_codigo"]) == {418, 421}  # sin Total ni sociosanitaria
        areas = {a["nivel_cuidado_codigo"]: a for a in areas_en_ventana(_ocupacion(), 10, "2026-01-05", por_area)}
        assert areas[418]["dotacion_declarada"] == 22.0 and areas[418]["ano_dotacion"] == 2025
        assert areas[421]["dotacion_declarada"] is None  # el libro no declara cifra: null, no cero

    def test_motivo_sin_dotacion_distingue_causas(self):
        assert motivo_sin_dotacion(pd.Series({"camas": 20.0}), 2025, 2014) is None
        assert "sin cifra" in motivo_sin_dotacion(pd.Series({"camas": float("nan")}), 2025, 2014)
        assert "habilitó en 2026" in motivo_sin_dotacion(None, 2025, 2026)
        assert "no es determinable" in motivo_sin_dotacion(None, 2025, 2019)
        assert motivo_sin_dotacion(None, None, 2026) is None  # sin libro de dotación no se afirma nada

    def test_colapso_por_hospital_desde_el_mart(self):
        colapso = colapso_por_establecimiento(nivel_colapso(_ocupacion()))
        # (1707 + 692) / (1800 + 900) = 88,85 %: entre 85 y 90 = presión.
        assert colapso[10]["nivel"] == "presion" and colapso[10]["indice_ocupacional"] == 88.9
        assert colapso_por_establecimiento(None) == {}

    def test_sin_ocupacion_es_null_no_cero(self):
        assert ocupacion_en_ventana(_ocupacion(), 11, "2026-01-05") is None
        assert ocupacion_en_ventana(None, 10, "2026-01-05") is None
        assert areas_en_ventana(_ocupacion(), 11, "2026-01-05") is None


class TestEndpoints:
    def test_lista(self, cliente):
        filas = cliente.get("/api/v1/establecimientos").json()
        assert len(filas) == 3
        hospital = next(f for f in filas if f["establecimiento_codigo"] == 10)
        assert hospital["camas_psiquiatria"] == 20.0
        assert hospital["colapso_psiquiatria"]["nivel"] == "presion"
        assert next(f for f in filas if f["establecimiento_codigo"] == 11)["colapso_psiquiatria"] is None
        assert hospital["objetivos"]["hospitalizaciones_sm"]["incluido"]

    def test_detalle_con_historia_y_pronostico(self, cliente):
        cuerpo = cliente.get("/api/v1/establecimientos/10?semanas=4").json()
        atenciones = next(s for s in cuerpo["series"] if s["objetivo"] == "atenciones_sm")
        assert len(atenciones["historico"]) == 4 and atenciones["historico"][-1]["valor"] == 40
        assert [p["horizonte"] for p in atenciones["pronostico"]] == [1, 2]

    def test_detalle_sin_pronostico_trae_el_motivo(self, cliente):
        cuerpo = cliente.get("/api/v1/establecimientos/11").json()
        hosp = next(s for s in cuerpo["series"] if s["objetivo"] == "hospitalizaciones_sm")
        assert hosp["pronostico"] is None and hosp["motivo_sin_pronostico"] == "Fuera del universo del modelo: no es hospital."

    def test_detalle_trae_la_ocupacion_de_psiquiatria(self, cliente):
        hospital = cliente.get("/api/v1/establecimientos/10").json()
        assert [m["mes"] for m in hospital["ocupacion_psiquiatria"]] == [1, 2]
        assert hospital["ocupacion_psiquiatria"][1]["indice_ocupacional"] == round(100 * 756 / 840, 1)
        assert [a["nivel_cuidado_codigo"] for a in hospital["areas_psiquiatria"]] == [418, 421]
        sapu = cliente.get("/api/v1/establecimientos/11").json()
        assert sapu["ocupacion_psiquiatria"] is None and sapu["areas_psiquiatria"] is None

    def test_establecimiento_inexistente_da_404(self, cliente):
        assert cliente.get("/api/v1/establecimientos/999").status_code == 404

    def test_meta(self, cliente):
        cuerpo = cliente.get("/api/v1/establecimientos-meta").json()
        assert cuerpo["ultima_semana_observada"] == {"ano": 2026, "semana": 10}
        assert cuerpo["ultima_semana_fecha_inicio"] == "2026-01-10"
        assert cuerpo["umbral_cambio_pct"] == 7.0
        atenciones = next(o for o in cuerpo["objetivos"] if o["objetivo"] == "atenciones_sm")
        assert atenciones["cobertura_holdout"] == pytest.approx(0.75)
        assert atenciones["pronosticos_fuera_de_rango"] == 1
        assert any("no donde quedó hospitalizado" in a for a in cuerpo["advertencias"])
        assert any("no ocupación en tiempo real" in a for a in cuerpo["advertencias"])


class TestEstados:
    def test_pronostico_vencido_da_503_con_la_etapa_a_ejecutar(self):
        servicio = ServicioEstablecimientos()
        servicio.estado.marcar("error", "desactualizado: ejecute el stage `forecast_establecimientos_sm`")
        app = create_app(lambda: ServicioDemanda(), iniciar_calculos=False, fabrica_establecimientos=lambda: servicio)
        with TestClient(app) as c:
            respuesta = c.get("/api/v1/establecimientos")
        assert respuesta.status_code == 503 and "forecast_establecimientos_sm" in respuesta.json()["detail"]
        assert "Retry-After" not in respuesta.headers

    def test_mientras_carga_pide_reintentar(self):
        app = create_app(
            lambda: ServicioDemanda(), iniciar_calculos=False, fabrica_establecimientos=ServicioEstablecimientos
        )
        with TestClient(app) as c:
            respuesta = c.get("/api/v1/establecimientos-meta")
        assert respuesta.status_code == 503 and respuesta.headers["Retry-After"] == "5"
