from __future__ import annotations

import json

import pandas as pd
import pytest

import scripts.run_pipeline as rp
from scripts import eda_mart_egresos_f00_f99_rm as eda


def _datos():
    anual = pd.DataFrame({
        "series_id": ["13101", "13102", "RM", "13101", "13102", "RM"],
        "nivel": ["comuna", "comuna", "region"] * 2,
        "nombre": ["A", "B", "RM"] * 2,
        "ano": [2020, 2020, 2020, 2021, 2021, 2021],
        "egresos": [3, 7, 10, 4, 6, 10],
        "poblacion": [None, None, None, 1000.0, 2000.0, 3000.0],
        "tasa_por_10000": [None, None, None, 40.0, 30.0, 33.333333],
        "dias_estada_mediana": [5.0] * 6, "dias_estada_p90": [9.0] * 6, "proporcion_snss": [0.5] * 6,
        "proporcion_estadia_mayor_a_un_ano": [0.0] * 6,
    })
    filas = [(s, a, "sexo", c, i, e) for s, a, e in zip(anual.series_id, anual.ano, anual.egresos)
             for i, c in enumerate(["Mujer"])]
    desglose = pd.DataFrame(filas, columns=["series_id", "ano", "dimension", "categoria", "orden", "egresos"])
    contraste = pd.DataFrame({"ano": [2021], "egresos_residentes_rm": [10]})
    residentes = pd.Series([10, 10], index=pd.Index([2020, 2021], name="ano"))
    return anual, desglose, contraste, residentes


def test_analizar_concilia_y_detecta_diferencias() -> None:
    anual, desglose, contraste, residentes = _datos()
    r = eda.analizar(anual, desglose, contraste, residentes)
    assert r["comunas_suman_region"] and r["region_igual_egresos_residentes_rm"]
    assert r["dimension_territorio_ano_distintos_del_total"] == 0
    assert r["nulos_poblacion_por_ano"] == {2020: 3} and r["contraste_egresos_igual_region"]
    desglose.loc[0, "egresos"] = 99
    assert eda.analizar(anual, desglose, contraste, residentes)["dimension_territorio_ano_distintos_del_total"] == 1


def test_validate_outputs_rechaza_resumen_que_no_concilia(tmp_path) -> None:
    informe, resumen = tmp_path / "i.md", tmp_path / "r.json"
    informe.write_text(eda.TITULO + "\n", encoding="utf-8")
    base = {"filas_anual": 1, "filas_desglose": 1, "comunas_suman_region": True, "region_igual_egresos_residentes_rm": True,
            "dimension_territorio_ano_distintos_del_total": 0, "contraste": [], "pk_anual_duplicados": 0}
    resumen.write_text(json.dumps(base), encoding="utf-8")
    eda.validate_outputs(informe, resumen)
    resumen.write_text(json.dumps({**base, "comunas_suman_region": False}), encoding="utf-8")
    with pytest.raises(ValueError):
        eda.validate_outputs(informe, resumen)


def test_etapa_registrada_con_dependencias_y_orden() -> None:
    etapa = rp.STAGES["eda_mart_egresos_f00_f99_rm"]
    assert set(etapa["depends_on"]) == {"build_mart_egresos_f00_f99_rm", "build_contraste_camas_psiquiatria_rm", "build_egresos_f00_f99"}
    for dep in etapa["depends_on"]:
        assert rp.PIPELINE_ORDER.index(dep) < rp.PIPELINE_ORDER.index("eda_mart_egresos_f00_f99_rm")
    assert not rp.es_etapa_evaluacion("eda_mart_egresos_f00_f99_rm")
