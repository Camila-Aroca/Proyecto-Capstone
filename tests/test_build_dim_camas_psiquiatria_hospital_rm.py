"""Pruebas dirigidas para la dimensión hospital ↔ camas de psiquiatría (RM)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.build_dim_camas_psiquiatria_hospital_rm import (
    OUTPUT_PATH,
    SCHEMA,
    build_dim_camas_psiquiatria_hospital_rm,
    camas_psiquiatria_por_establecimiento,
    ultimo_ano_camas,
    validate_dim,
)

PSQ_ADULTO = "Área Psiquiatría Adulto Corta Estadía"
PSQ_INFANTO = "Área Psiquiatría infanto-adolescente corta estadía"


def _oferta() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "establecimiento_codigo": [101, 102, 103, 104, 105],
            "establecimiento_nombre": ["Hosp 1", "Hosp 2", "Hosp 3", "Clinica 4", "SAPU 5"],
            "comuna_codigo": ["13101", "13101", "13102", "13102", "13101"],
            "tipo_establecimiento": ["Hospital", "Hospital", "Hospital", "Hospital",
                                     "Servicio de Atención Primaria de Urgencia (SAPU)"],
            "reporto_id36_periodo": [True, True, False, False, True],
        }
    )


def _camas(ano_ultimo: int = 2025) -> pd.DataFrame:
    filas = [
        # (codigo, area_codigo, area, camas_2024, camas_ultimo)
        (101, 100, "Total", 500.0, 500.0),
        (101, 418, PSQ_ADULTO, 270.0, 270.0),
        (101, 421, PSQ_INFANTO, 10.0, 12.0),
        (101, 427, "Área Sociosanitaria Adulto", 30.0, 30.0),  # no es psiquiatría
        (102, 100, "Total", 80.0, 80.0),
        (102, 418, PSQ_ADULTO, np.nan, np.nan),  # área sin cifra declarada
        (103, 100, "Total", 50.0, 50.0),
        (103, 416, "Área Obstetricia", 20.0, 20.0),  # sin psiquiatría
    ]
    frame = pd.DataFrame(
        filas,
        columns=["establecimiento_codigo", "area_funcional_codigo", "area_funcional",
                 "camas_2024", f"camas_{ano_ultimo}"],
    )
    frame["establecimiento_codigo"] = frame["establecimiento_codigo"].astype("int64")
    return frame


def test_ultimo_ano_se_detecta_de_las_columnas():
    assert ultimo_ano_camas(["camas_2023", "camas_2025", "camas_2024", "servicio_salud"]) == 2025
    assert ultimo_ano_camas(["camas_2030", "camas_2029"]) == 2030
    with pytest.raises(ValueError):
        ultimo_ano_camas(["servicio_salud"])


def test_suma_solo_areas_de_psiquiatria_y_excluye_total_y_sociosanitaria():
    agregado = camas_psiquiatria_por_establecimiento(_camas(), 2025).set_index("establecimiento_codigo")
    assert agregado.loc[101, "camas_psiquiatria"] == 282.0
    assert agregado.loc[101, "n_areas_psiquiatria"] == 2
    # Solo un area en blanco: nulo, no cero.
    assert pd.isna(agregado.loc[102, "camas_psiquiatria"])
    assert agregado.loc[102, "n_areas_psiquiatria"] == 0
    assert 103 not in agregado.index


def test_usa_el_ultimo_ano_aunque_no_sea_2025():
    camas = _camas(ano_ultimo=2026)
    dim = build_dim_camas_psiquiatria_hospital_rm(_oferta(), camas)
    assert set(dim["ano_camas"]) == {2026}
    assert dim.set_index("establecimiento_codigo").loc[101, "camas_psiquiatria"] == 282.0


def test_une_por_codigo_y_conserva_todos_los_hospitales_de_la_oferta():
    dim = build_dim_camas_psiquiatria_hospital_rm(_oferta(), _camas()).set_index("establecimiento_codigo")
    assert list(dim.index) == [101, 102, 103, 104]  # el SAPU no es hospital
    assert dim.loc[101, "comuna_codigo"] == "13101"
    assert dim["en_dotacion_snss"].to_dict() == {101: True, 102: True, 103: True, 104: False}
    # En dotacion pero sin psiquiatria, o fuera de la dotacion: nulo, nunca 0.
    assert dim["camas_psiquiatria"].isna().to_dict() == {101: False, 102: True, 103: True, 104: True}
    assert dim["n_areas_psiquiatria"].to_dict() == {101: 2, 102: 0, 103: 0, 104: 0}


def test_un_cero_declarado_se_conserva_como_cero():
    camas = _camas()
    camas.loc[camas["establecimiento_codigo"].eq(102) & camas["area_funcional_codigo"].eq(418),
              "camas_2025"] = 0.0
    dim = build_dim_camas_psiquiatria_hospital_rm(_oferta(), camas).set_index("establecimiento_codigo")
    assert dim.loc[102, "camas_psiquiatria"] == 0.0
    assert dim.loc[102, "n_areas_psiquiatria"] == 1


def test_area_de_psiquiatria_repetida_falla():
    camas = pd.concat([_camas(), _camas().iloc[[1]]], ignore_index=True)
    with pytest.raises(ValueError, match="repite"):
        build_dim_camas_psiquiatria_hospital_rm(_oferta(), camas)


def test_validacion_detecta_camas_fuera_de_dotacion_y_comuna_invalida():
    dim = build_dim_camas_psiquiatria_hospital_rm(_oferta(), _camas())
    malo = dim.copy()
    malo.loc[malo["establecimiento_codigo"].eq(104), ["camas_psiquiatria", "n_areas_psiquiatria"]] = [5.0, 1]
    with pytest.raises(ValueError, match="fuera de la dotación"):
        validate_dim(malo, oferta_hospitales=4)
    malo = dim.copy()
    malo.loc[0, "comuna_codigo"] = "08101"
    with pytest.raises(ValueError, match="13xxx"):
        validate_dim(malo, oferta_hospitales=4)
    with pytest.raises(ValueError, match="conserva"):
        validate_dim(dim, oferta_hospitales=5)


def test_el_esquema_publicado_coincide_con_las_columnas():
    dim = build_dim_camas_psiquiatria_hospital_rm(_oferta(), _camas())
    assert list(dim.columns) == [f.name for f in SCHEMA]


def test_el_stage_esta_registrado_con_sus_dependencias():
    stage = pipeline.STAGES["build_dim_camas_psiquiatria_hospital_rm"]
    assert stage["outputs"] == [OUTPUT_PATH.as_posix()]
    assert stage["depends_on"] == ["clean_dotacion_camas", "build_dim_oferta_urgencia_rm"]
    orden = pipeline.PIPELINE_ORDER
    posicion = orden.index("build_dim_camas_psiquiatria_hospital_rm")
    assert all(orden.index(dep) < posicion for dep in stage["depends_on"])


def test_el_contrato_de_salida_valida_el_parquet_publicado():
    if not OUTPUT_PATH.exists():
        pytest.skip("El output no se ha generado en este entorno.")
    assert pipeline.check_outputs_exist([OUTPUT_PATH.as_posix()])
