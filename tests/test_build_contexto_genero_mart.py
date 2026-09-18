"""Pruebas del mart canónico de contexto interpretativo por sexo/género."""

from pathlib import Path

import pyarrow.parquet as pq

import scripts.run_pipeline as pipeline
from src.data import build_contexto_genero_mart as mart


def test_build_mart_reconciles_all_processed_sources_and_preserves_contract():
    """El mart concatena exactamente los inputs, sin alterar su contrato."""
    built = mart.build_mart()
    input_rows = {
        source_id: pq.read_table(path).num_rows
        for source_id, path in mart.source_paths().items()
    }
    frame = built.to_pandas()

    assert built.schema == mart.SCHEMA
    assert built.num_rows == sum(input_rows.values())
    assert set(frame["source_id"]) == set(mart.SOURCE_IDS)
    assert frame.groupby("source_id").size().to_dict() == input_rows
    assert not frame.duplicated(list(mart.GRAIN_COLUMNS)).any()
    assert frame.loc[
        frame["source_id"].eq("ansiedad_depresion_sintomas_18_mas_sexo"), "year"
    ].isna().all()
    assert set(
        frame.loc[
            frame["source_id"].eq("prevalencia_sintomas_depresivos_sexo"), "period"
        ]
    ) == {"2003", "2009-10", "2016-17"}
    assert "-" in set(frame["value_text"].dropna())


def test_publish_is_atomic_valid_and_idempotent(tmp_path: Path):
    """La publicación valida el output y luego realiza SKIP sin --force."""
    output_path = tmp_path / "mart_contexto_genero_indicador_sexo.parquet"
    table = mart.build_mart()
    mart.atomic_write(table, output_path)

    published = mart.validate_output(output_path)
    assert published.equals(table)
    assert mart.build_and_publish(force=False, output_path=output_path) is False


def test_contexto_genero_mart_stages_are_registered_in_dag():
    """El output canónico y su EDA reproducible quedan en el DAG oficial."""
    assert pipeline.STAGES["build_mart_contexto_genero_indicador_sexo"]["depends_on"] == [
        "normalize_contexto_genero"
    ]
    assert pipeline.STAGES["eda_mart_contexto_genero_indicador_sexo"]["depends_on"] == [
        "build_mart_contexto_genero_indicador_sexo"
    ]
    assert pipeline.PIPELINE_ORDER.index("normalize_contexto_genero") < pipeline.PIPELINE_ORDER.index(
        "build_mart_contexto_genero_indicador_sexo"
    )
