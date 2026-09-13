"""Pruebas del perfil comunal-semanal de cobertura ID 36."""

from __future__ import annotations

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
from src.data.profile_urgencias_sm_coverage import build_profile


def test_build_profile_separates_observed_zero_from_missing_week() -> None:
    calendar = pd.DataFrame(
        [
            (2021, 1, "03/01/2021", "13101", "Santiago"),
            (2021, 2, "10/01/2021", "13101", "Santiago"),
            (2021, 3, "17/01/2021", "13101", "Santiago"),
            (2021, 1, "03/01/2021", "13102", "Cerrillos"),
            (2021, 2, "10/01/2021", "13102", "Cerrillos"),
            (2021, 3, "17/01/2021", "13102", "Cerrillos"),
        ],
        columns=["ano", "semana", "fecha", "comuna_codigo", "comuna_glosa"],
    )
    sm = pd.DataFrame(
        [
            (2021, 1, "03/01/2021", "13101", "Santiago", 10, 0),
            (2021, 3, "17/01/2021", "13101", "Santiago", 10, 4),
            (2021, 1, "03/01/2021", "13102", "Cerrillos", 20, 2),
            (2021, 2, "10/01/2021", "13102", "Cerrillos", 21, 3),
            (2021, 3, "17/01/2021", "13102", "Cerrillos", 21, 0),
        ],
        columns=[
            "ano", "semana", "fecha", "comuna_codigo", "comuna_glosa",
            "establecimiento_codigo", "total",
        ],
    )

    profile = build_profile(calendar, sm).set_index("comuna_codigo")
    santiago = profile.loc["13101"]
    cerrillos = profile.loc["13102"]

    assert santiago["semanas_calendario_esperadas"] == 3
    assert santiago["semanas_con_reporte"] == 2
    assert santiago["semanas_sin_reporte"] == 1
    assert santiago["semanas_id36_cero"] == 1
    assert santiago["proporcion_cobertura"] == pytest.approx(2 / 3)
    assert santiago["proporcion_ceros"] == pytest.approx(1 / 2)
    assert santiago["atenciones_sm_total"] == 4
    assert santiago["maximo_semanas_consecutivas_sin_reporte"] == 1
    assert santiago["numero_gaps_sin_reporte"] == 1
    assert santiago["cambios_en_establecimientos"] == 0

    assert cerrillos["semanas_sin_reporte"] == 0
    assert cerrillos["establecimientos_reportantes"] == 2
    assert cerrillos["cambios_en_establecimientos"] == 1
    assert cerrillos["inicio_observado"] == "2021-01-03"
    assert cerrillos["fin_observado"] == "2021-01-17"


def test_build_profile_rejects_incomplete_input_schema() -> None:
    with pytest.raises(ValueError, match="Columnas faltantes"):
        build_profile(pd.DataFrame(), pd.DataFrame())


def test_profile_stage_is_registered_after_clean_urgencias() -> None:
    assert pipeline.STAGES["profile_urgencias_sm_coverage"]["depends_on"] == [
        "clean_urgencias"
    ]
    assert "profile_urgencias_sm_coverage" in pipeline.PIPELINE_ORDER
