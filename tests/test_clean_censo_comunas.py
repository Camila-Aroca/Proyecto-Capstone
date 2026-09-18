"""Pruebas unitarias para el procesamiento de cartografía Censo 2024 (comunal y subcomunal) RM."""

from pathlib import Path
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import Point

from src.data.clean_censo_comunas import (
    RAW_CENSO_COMUNAL,
    RAW_CENSO_DISTRITAL,
    RAW_CENSO_ZONAL,
    RAW_CENSO_ENTIDADES,
    RAW_CENSO_MANZANAS,
    PROCESSED_CENSO_RM_COMUNAL,
    EXPECTED_RM_CUTS,
    process_censo_comunal_rm,
    process_censo_distrital_rm,
    process_censo_zonal_rm,
    process_censo_entidades_rm,
    process_censo_manzanas_rm,
    process_censo_subcomunal_rm,
)


def test_raw_censo_comunal_exists():
    """Verifica que el archivo raw exista."""
    assert RAW_CENSO_COMUNAL.exists(), f"Falta archivo raw: {RAW_CENSO_COMUNAL}"


def test_process_censo_comunal_rm(tmp_path: Path):
    """Prueba la función de procesamiento y validación en un directorio temporal."""
    output_tmp = tmp_path / "Cartografia_censo2024_RM_Comunal.parquet"
    res = process_censo_comunal_rm(raw_path=RAW_CENSO_COMUNAL, output_path=output_tmp)

    assert res["filas"] == 52
    assert res["comunas_unicas"] == 52
    assert res["estan_52_comunas"] is True
    assert res["cod_region_unico"] is True
    assert res["geometrias_nulas"] == 0
    assert res["geometrias_invalidas"] == 0
    assert res["duplicados_cut"] == 0
    assert res["validacion_exitosa"] is True

    # Verificar que el GeoParquet guardado se abre y tiene las 52 filas
    t = pq.read_table(output_tmp)
    assert t.num_rows == 52
    assert set(t["CUT"].to_pylist()) == EXPECTED_RM_CUTS


def _write_geoparquet(path: Path, rows: list[dict], *, demografia: bool = False,
                       distrito: bool = False, key_column: str = "ID_ZONA") -> None:
    """Crea un GeoParquet sintético mínimo con el esquema real observado en la fuente."""
    fields = [("CUT", pa.int32()), ("COD_REGION", pa.int32()), (key_column, pa.float64()), ("SHAPE", pa.binary())]
    if distrito:
        fields.insert(-1, ("ID_DISTRITO", pa.float64()))
    if demografia:
        fields[-1:-1] = [("n_per", pa.float64()), ("n_hombres", pa.float64()), ("n_mujeres", pa.float64())]
    schema = pa.schema(fields, metadata={b"geo": json.dumps({
        "columns": {"SHAPE": {"encoding": "WKB", "crs": {"id": {"authority": "EPSG", "code": 4674}, "name": "SIRGAS 2000"}}}
    }).encode()})
    columns = []
    for name, _ in fields:
        if name == "SHAPE":
            columns.append(pa.array([Point(0, 0).wkb for _ in rows]))
        else:
            columns.append(pa.array([row[name] for row in rows]))
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_arrays(columns, schema=schema), path)


def test_process_censo_subcomunal_rm_rejects_duplicate_key(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [
        {"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0},
        {"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0},
    ])
    with pytest.raises(ValueError, match="duplicado"):
        process_censo_subcomunal_rm("Zonal", raw_path, tmp_path / "out.parquet",
                                     key_column="ID_ZONA", expect_full_52=False)


def test_process_censo_subcomunal_rm_rejects_cut_outside_rm(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [
        {"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0},
        {"CUT": 99999, "COD_REGION": 13, "ID_ZONA": 2.0},
    ])
    with pytest.raises(ValueError, match="fuera del dominio"):
        process_censo_subcomunal_rm("Zonal", raw_path, tmp_path / "out.parquet",
                                     key_column="ID_ZONA", expect_full_52=False)


def test_process_censo_subcomunal_rm_accepts_partial_coverage_when_not_required(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [{"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0}])
    result = process_censo_subcomunal_rm("Zonal", raw_path, tmp_path / "out.parquet",
                                          key_column="ID_ZONA", expect_full_52=False)
    assert result["todas_las_52_comunas"] is False
    assert result["validacion_exitosa"] is True


def test_process_censo_subcomunal_rm_requires_full_coverage_when_flagged(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [{"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0}])
    with pytest.raises(ValueError, match="faltan comunas"):
        process_censo_subcomunal_rm("Distrital", raw_path, tmp_path / "out.parquet",
                                     key_column="ID_ZONA", expect_full_52=True)


def test_process_censo_subcomunal_rm_rejects_negative_demografia(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [
        {"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0, "n_per": -5.0, "n_hombres": 0.0, "n_mujeres": 0.0},
    ], demografia=True)
    with pytest.raises(ValueError, match="negativas"):
        process_censo_subcomunal_rm("Zonal", raw_path, tmp_path / "out.parquet",
                                     key_column="ID_ZONA", expect_full_52=False)


def test_process_censo_subcomunal_rm_rejects_orphan_distrito(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [
        {"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0, "ID_DISTRITO": 999.0},
    ], distrito=True)
    with pytest.raises(ValueError, match="ID_DISTRITO sin distrito"):
        process_censo_subcomunal_rm("Zonal", raw_path, tmp_path / "out.parquet",
                                     key_column="ID_ZONA", expect_full_52=False,
                                     distrito_ids_rm={1310101.0})


def test_process_censo_subcomunal_rm_reports_sex_mismatch_without_failing(tmp_path: Path):
    raw_path = tmp_path / "raw.parquet"
    _write_geoparquet(raw_path, [
        {"CUT": 13101, "COD_REGION": 13, "ID_ZONA": 1.0, "n_per": 10.0, "n_hombres": None, "n_mujeres": None},
    ], demografia=True)
    result = process_censo_subcomunal_rm("Zonal", raw_path, tmp_path / "out.parquet",
                                          key_column="ID_ZONA", expect_full_52=False)
    assert result["demografia"]["equidad_sexo_inconsistente"] == 1
    assert result["validacion_exitosa"] is True


@pytest.mark.parametrize("raw_path,func", [
    (RAW_CENSO_DISTRITAL, process_censo_distrital_rm),
    (RAW_CENSO_ZONAL, process_censo_zonal_rm),
    (RAW_CENSO_ENTIDADES, process_censo_entidades_rm),
    (RAW_CENSO_MANZANAS, process_censo_manzanas_rm),
])
def test_process_censo_subcomunal_layers_against_real_raw(tmp_path: Path, raw_path: Path, func):
    """Si el RAW oficial ya fue descargado, procesa la capa completa y valida el dominio RM."""
    if not raw_path.exists():
        pytest.skip(f"RAW no disponible localmente: {raw_path.as_posix()}")
    output_tmp = tmp_path / raw_path.name
    result = func(raw_path=raw_path, output_path=output_tmp)
    assert result["filas"] > 0
    assert result["comunas_representadas"] <= 52
    assert set(pq.read_table(output_tmp, columns=["CUT"])["CUT"].to_pylist()) <= EXPECTED_RM_CUTS
    assert result["crs"].startswith("SIRGAS 2000")
