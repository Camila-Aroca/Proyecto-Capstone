"""Fixtures sintéticos mínimos: nunca leen ni escriben datasets del proyecto."""

import csv
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import box

from src.data import clean_urgencias
from src.data.clean_censo_comunas import EXPECTED_RM_CUTS


@pytest.fixture
def censo_comunal_raw(tmp_path: Path) -> Path:
    """52 CUT RM oficiales y una comuna externa, con geometrías sintéticas."""
    cuts = [*sorted(EXPECTED_RM_CUTS), 15101]
    table = pa.table({
        "CUT": pa.array(cuts, type=pa.int32()),
        "COMUNA": [f"Comuna sintetica {cut}" for cut in cuts],
        "COD_REGION": pa.array([13] * 52 + [15], type=pa.int32()),
        "SHAPE": [box(i, 0, i + 0.5, 0.5).wkb for i in range(len(cuts))],
    })
    metadata = {b"geo": json.dumps({
        "version": "1.0.0",
        "primary_column": "SHAPE",
        "columns": {"SHAPE": {
            "encoding": "WKB",
            "geometry_types": ["Polygon"],
            "crs": {"name": "SIRGAS 2000", "id": {"authority": "EPSG", "code": 4674}},
        }},
    }).encode("utf-8")}
    raw_path = tmp_path / "censo_comunal_sintetico.parquet"
    pq.write_table(table.replace_schema_metadata(metadata), raw_path)
    return raw_path


@pytest.fixture
def catalogos_urgencias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Catálogo RM (1 fila) y nacional (2), aislados del maestro DEIS vigente."""
    rm_path = tmp_path / "establecimientos_rm.csv"
    nac_path = tmp_path / "establecimientos_nacional.parquet"
    pd.DataFrame([{
        "establecimiento_codigo": 100,
        "establecimiento_codigo_antiguo": "OLD-RM",
        "establecimiento_glosa": "Hospital sintetico RM",
        "comuna_codigo": "13101",
        "comuna_glosa": "Santiago",
        "tipo_establecimiento_glosa": "Hospital",
        "ambito_funcionamiento": "Publico",
        "latitud": -33.4,
        "longitud": -70.6,
    }]).to_csv(rm_path, index=False)
    pd.DataFrame([
        {"establecimiento_codigo": 100, "establecimiento_codigo_antiguo": "OLD-RM",
         "region_codigo": 13, "comuna_codigo": "13101"},
        {"establecimiento_codigo": 200, "establecimiento_codigo_antiguo": "OLD-NON-RM",
         "region_codigo": 15, "comuna_codigo": "15101"},
    ]).to_parquet(nac_path, index=False)
    monkeypatch.setattr(clean_urgencias, "ESTABLECIMIENTOS_RM_PATH", rm_path)
    monkeypatch.setattr(clean_urgencias, "ESTABLECIMIENTOS_NAC_PATH", nac_path)
    return {"rm": rm_path, "nacional": nac_path}


@pytest.fixture(params=[2020, 2022])
def urgencias_legacy_raw(tmp_path: Path, request: pytest.FixtureRequest) -> tuple[int, Path]:
    """CSV antiguo sin región: códigos antiguos/nuevos, externo y desconocido."""
    year = request.param
    raw_dir = tmp_path / "urgencias_sinteticas"
    raw_dir.mkdir()
    fields = [
        "IdEstablecimiento", "NEstablecimiento", "IdCausa", "GlosaCausa", "Total",
        "Menores_1", "De_1_a_4", "De_5_a_14", "De_15_a_64", "De_65_y_mas",
        "fecha", "semana", "GLOSATIPOESTABLECIMIENTO", "GLOSATIPOATENCION",
        "GlosaTipoCampana",
    ]
    with (raw_dir / f"AtencionesUrgencia{year}.csv").open(
        "w", encoding="latin-1", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for code in ["OLD-RM", "100", "OLD-NON-RM", "200", "UNKNOWN", ""]:
            writer.writerow(dict(zip(fields, [
                code, "Establecimiento sintético", 36, "Salud mental", 10,
                1, 2, 3, 3, 1, f"01/01/{year}", 1, "Hospital", "Urgencia", "",
            ])))
    return year, raw_dir
