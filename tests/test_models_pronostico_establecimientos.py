"""Pruebas del pronóstico persistido por establecimiento y de su vigencia.

Usan archivos sintéticos en `tmp_path`: no dependen de `data/processed/`.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scripts.run_pipeline as pipeline
from src.data.raw_provenance import RAW_SHA256_METADATA_KEY
from src.models.establecimientos import OBJETIVOS, select_universe
from src.models.features import RM_SERIES_ID
from src.models.pronostico_establecimientos import (
    huella_entradas,
    marcar_fuera_de_rango,
    motivo_desactualizacion,
)


def _parquet(ruta, raw_sha: str | None = None, ano: int = 2025) -> None:
    tabla = pa.table({"ano": [ano, ano]})
    if raw_sha:
        tabla = tabla.replace_schema_metadata({RAW_SHA256_METADATA_KEY: raw_sha.encode("ascii")})
    pq.write_table(tabla, ruta)


@pytest.fixture
def entradas(tmp_path):
    """Mart 2022-2025, selección y Parquet del año en curso (2026), sintéticos."""
    mart = tmp_path / "mart.parquet"
    _parquet(mart)
    seleccion = tmp_path / "seleccion.json"
    seleccion.write_text("{}", encoding="utf-8")
    procesados = tmp_path / "urgencias"
    procesados.mkdir()
    _parquet(procesados / "urgencias_rm_2026.parquet", raw_sha="a" * 64, ano=2026)
    manifiesto = {"entradas": huella_entradas(mart, seleccion, procesados, [2026])}
    return manifiesto, mart, seleccion, procesados


class TestVigencia:
    def test_vigente_si_nada_cambio(self, entradas):
        manifiesto, _, _, procesados = entradas
        assert motivo_desactualizacion(manifiesto, procesados) is None

    def test_un_snapshot_nuevo_del_ano_en_curso_lo_invalida(self, entradas):
        manifiesto, _, _, procesados = entradas
        _parquet(procesados / "urgencias_rm_2026.parquet", raw_sha="b" * 64, ano=2026)
        assert "urgencias_2026" in motivo_desactualizacion(manifiesto, procesados)

    def test_un_ano_nuevo_lo_invalida(self, entradas):
        manifiesto, _, _, procesados = entradas
        _parquet(procesados / "urgencias_rm_2027.parquet", raw_sha="c" * 64, ano=2027)
        assert "urgencias_2027" in motivo_desactualizacion(manifiesto, procesados)

    def test_cambiar_la_seleccion_lo_invalida(self, entradas):
        manifiesto, _, seleccion, procesados = entradas
        seleccion.write_text('{"otro": 1}', encoding="utf-8")
        assert "seleccion_benchmark" in motivo_desactualizacion(manifiesto, procesados)

    def test_usa_la_identidad_del_raw_y_no_el_archivo(self, entradas):
        manifiesto, _, _, procesados = entradas
        # Mismo RAW declarado, Parquet reescrito (otro equipo, otros bytes): sigue vigente.
        tabla = pa.table({"ano": [2026, 2026, 2026]}).replace_schema_metadata(
            {RAW_SHA256_METADATA_KEY: ("a" * 64).encode("ascii")}
        )
        pq.write_table(tabla, procesados / "urgencias_rm_2026.parquet")
        assert motivo_desactualizacion(manifiesto, procesados) is None

    def test_manifiesto_sin_entradas_no_es_vigente(self):
        assert motivo_desactualizacion({}) is not None


class TestGuardiaDePlausibilidad:
    def test_marca_lo_que_excede_el_doble_del_maximo_reciente(self):
        panel = pd.DataFrame({"series_id": ["1"] * 60, "t": range(60), "y": [10.0] * 59 + [30.0]})
        pronostico = pd.DataFrame({"series_id": ["1", "1"], "y_pred": [59.0, 61.0]})
        marcado = marcar_fuera_de_rango(pronostico, panel)
        assert marcado["maximo_observado_reciente"].iloc[0] == 30.0
        assert marcado["fuera_de_rango"].tolist() == [False, True]

    def test_solo_mira_las_ultimas_52_semanas(self):
        y = [100.0] + [10.0] * 59  # el pico está fuera de la ventana reciente
        panel = pd.DataFrame({"series_id": ["1"] * 60, "t": range(60), "y": y})
        marcado = marcar_fuera_de_rango(pd.DataFrame({"series_id": ["1"], "y_pred": [25.0]}), panel)
        assert bool(marcado["fuera_de_rango"].iloc[0])


class TestPisoAnual:
    @staticmethod
    def _mart() -> pd.DataFrame:
        filas = []
        for codigo, por_ano in {1: {2022: 8, 2023: 8}, 2: {2022: 0, 2023: 9}}.items():
            for ano, nivel in por_ano.items():
                for semana in range(1, 53):
                    filas.append({
                        "establecimiento_codigo": codigo, "ano": ano, "semana": semana,
                        "establecimiento_glosa": f"E{codigo}", "tipo_establecimiento_urgencia": "SAPU",
                        "comuna_codigo": "13101", "atenciones_id36": nivel,
                    })
        return pd.DataFrame(filas)

    def test_excluye_series_que_empiezan_a_registrar_a_mitad_de_ventana(self):
        universo = select_universe(self._mart(), OBJETIVOS["atenciones_sm"], ano_inicio=2022)
        fila = universo.set_index("establecimiento_codigo")
        # La serie 2 promedia 4,5 en la ventana, pero 2022 está en cero.
        assert fila.loc[1, "incluido"] and not fila.loc[2, "incluido"]
        assert "algún año" in fila.loc[2, "motivo_exclusion"]


def test_stage_registrado_despues_del_benchmark():
    stage = pipeline.STAGES["forecast_establecimientos_sm"]
    assert stage["depends_on"] == ["benchmark_establecimientos_sm", "clean_urgencias"]
    orden = pipeline.PIPELINE_ORDER
    assert orden.index("benchmark_establecimientos_sm") < orden.index("forecast_establecimientos_sm")


def test_el_pronostico_publicado_no_incluye_el_total_y_trae_la_guardia():
    from src.models.establecimientos import build_establishment_panel
    from src.models.pronostico_establecimientos import DatosObjetivo, _calendario, calcular_pronostico
    from tests.test_models_establecimientos import _mart

    mart = _mart(anos=(2022, 2023, 2024))
    mart["fecha_inicio_semana"] = (
        pd.to_datetime(mart["ano"].astype(str) + "-01-01") + pd.to_timedelta((mart["semana"] - 1) * 7, unit="D")
    ).dt.date.astype(str)
    objetivo = OBJETIVOS["atenciones_sm"]
    universo = select_universe(mart, objetivo, ano_inicio=2022)
    datos = DatosObjetivo(
        objetivo, build_establishment_panel(mart, objetivo, universo, 2022), _calendario(mart), universo,
        pd.DataFrame(),
    )
    seleccion = {"modelo_recomendado": "baseline_estacional", "nivel_intervalo": 0.8, "horizontes": [1, 2]}
    pronostico = calcular_pronostico(datos, seleccion)
    assert RM_SERIES_ID not in set(pronostico["series_id"])
    assert set(pronostico["horizonte"]) == {1, 2}
    assert {"fuera_de_rango", "maximo_observado_reciente"} <= set(pronostico.columns)
    assert (pronostico["objetivo"] == "atenciones_sm").all()
    assert not pronostico["fuera_de_rango"].any()
