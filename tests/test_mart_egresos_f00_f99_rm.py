"""Pruebas del perfil de egresos F00-F99 de residentes RM y del contraste de camas."""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_contraste_camas_psiquiatria_rm import build_contraste
from src.data.build_mart_egresos_f00_f99_rm import (
    REGION_ID,
    SNSS,
    build_anual,
    build_desglose,
    grupo_diagnostico,
    validar,
)

COMUNAS = [str(13101 + i) for i in range(52)]


def _poblacion(anos=(2021, 2022)) -> pd.DataFrame:
    return pd.DataFrame([
        {"comuna_codigo": c, "comuna_glosa": f"C{c}", "ano": a, "poblacion": 10_000}
        for c in COMUNAS for a in anos
    ])


def _residentes() -> pd.DataFrame:
    filas = [
        # 13101: dos egresos en 2021 (uno SNSS) y uno en 2022; 13102: uno en 2021.
        ("13101", 2021, "F329", 10, True, "Mujer", "20 a 29", "FONASA"),
        ("13101", 2021, "F200", 30, False, "Hombre", "30 a 39", "ISAPRE"),
        ("13101", 2022, "F100", 400, True, "Hombre", "40 a 49", "FONASA"),
        ("13102", 2021, "F411", 5, True, "Mujer", "10 a 19", "Sin dato"),
    ]
    rm = pd.DataFrame(filas, columns=["comuna_codigo", "ano", "diag1", "dias_estada", "es_snss",
                                      "sexo_armonizado", "grupo_edad_armonizado", "prevision"])
    rm["pertenencia_establecimiento_salud"] = rm.pop("es_snss").map({True: SNSS, False: "No SNSS"})
    rm["estadia_mayor_a_un_ano"] = rm["dias_estada"] > 365
    rm["grupo_diagnostico"] = grupo_diagnostico(rm["diag1"])
    return rm


class TestPerfilAnual:
    def test_comunas_suman_la_region_y_ceros_explicitos(self):
        anual = build_anual(_residentes(), _poblacion())
        region = anual[anual["series_id"] == REGION_ID].set_index("ano")
        assert region.loc[2021, "egresos"] == 3 and region.loc[2022, "egresos"] == 1
        # Una comuna sin egresos tiene 0, no falta la fila; su estadía queda nula.
        sin = anual[(anual["series_id"] == "13150") & (anual["ano"] == 2021)].iloc[0]
        assert sin["egresos"] == 0 and pd.isna(sin["dias_estada_mediana"])
        assert len(anual) == 2 * (52 + 1)

    def test_tasa_estadia_y_snss(self):
        anual = build_anual(_residentes(), _poblacion()).set_index(["series_id", "ano"])
        fila = anual.loc[("13101", 2021)]
        assert fila["tasa_por_10000"] == pytest.approx(2.0)
        assert fila["dias_estada_mediana"] == pytest.approx(20.0)
        assert fila["proporcion_snss"] == pytest.approx(0.5)
        assert anual.loc[("13101", 2022), "proporcion_estadia_mayor_a_un_ano"] == 1.0

    def test_sin_poblacion_la_tasa_es_nula_no_cero(self):
        rm = _residentes().assign(ano=2020)
        anual = build_anual(rm, _poblacion())
        assert anual["tasa_por_10000"].isna().all() and (anual.loc[anual["series_id"] == REGION_ID, "egresos"] > 0).all()

    def test_comuna_fuera_de_la_rm_falla(self):
        rm = _residentes()
        rm.loc[0, "comuna_codigo"] = "05101"
        with pytest.raises(ValueError, match="fuera de las 52"):
            build_anual(rm, _poblacion())


class TestDesglose:
    def test_cada_dimension_suma_los_egresos(self):
        rm = _residentes()
        anual, desglose = build_anual(rm, _poblacion()), build_desglose(rm)
        validar(anual, desglose, rm)
        diag = desglose[(desglose["series_id"] == REGION_ID) & (desglose["ano"] == 2021)
                        & (desglose["dimension"] == "grupo_diagnostico")]
        assert diag["egresos"].sum() == 3 and diag["categoria"].str.contains("ánimo").any()

    def test_bloques_cie10(self):
        grupos = grupo_diagnostico(pd.Series(["F059", "F102", "F209", "F329", "F99X"]))
        assert grupos.str.extract(r"\((F\d\d)")[0].tolist() == ["F00", "F10", "F20", "F30", "F99"]


class TestContrasteCamas:
    def test_compara_ambas_fuentes_solo_en_anos_completos(self):
        egresos = pd.DataFrame({
            "ano_egreso": [2023, 2023, 2023],
            "residente_rm": [True, True, False],
            "pertenencia_establecimiento_salud": [SNSS, "No SNSS", SNSS],
            "dias_estada_acotado_anual": [365, 365, 365],
        })
        # REM-20: 12 meses de 2023 con 31 días cama ocupados al mes en un área no forense
        # y otros tantos en una forense; 2024 incompleto.
        filas = [(2023, m, area, 31.0) for m in range(1, 13) for area in (418, 424)] + [(2024, 1, 418, 31.0)]
        ocupacion = pd.DataFrame(filas, columns=["ano", "mes", "nivel_cuidado_codigo", "dias_cama_ocupados"])
        contraste = build_contraste(egresos, ocupacion).set_index("ano")
        assert list(contraste.index) == [2023]
        fila = contraste.loc[2023]
        assert fila["egresos_residentes_rm"] == 2
        assert fila["camas_equivalentes_egresos"] == pytest.approx(2.0)
        assert fila["camas_equivalentes_egresos_snss"] == pytest.approx(1.0)
        assert fila["camas_ocupadas_rem20_sin_forense"] == pytest.approx(372 / 365, abs=0.05)


def test_etapas_registradas_con_sus_dependencias():
    perfil = pipeline.STAGES["build_mart_egresos_f00_f99_rm"]
    contraste = pipeline.STAGES["build_contraste_camas_psiquiatria_rm"]
    assert "build_egresos_f00_f99" in perfil["depends_on"]
    assert "build_mart_ocupacion_psiquiatria_hospital_rm" in contraste["depends_on"]
    orden = pipeline.PIPELINE_ORDER
    assert orden.index("build_egresos_f00_f99") < orden.index("build_mart_egresos_f00_f99_rm")
    assert orden.index("build_mart_ocupacion_psiquiatria_hospital_rm") < orden.index("build_contraste_camas_psiquiatria_rm")
