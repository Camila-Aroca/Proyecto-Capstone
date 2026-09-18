"""EDA breve y reproducible del mart contextual por sexo/género."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from src.data.build_contexto_genero_mart import (
    GRAIN_COLUMNS,
    OUTPUT_PATH,
    SOURCE_IDS,
    source_paths,
    validate_output,
)


REPORT_PATH = Path("reports/eda/eda_mart_contexto_genero_indicador_sexo.md")


def build_report() -> str:
    """Construye un reporte QA sin inferencias ni cruces con otros dominios."""
    mart = validate_output(OUTPUT_PATH).to_pandas()
    source_rows = mart["source_id"].value_counts().reindex(SOURCE_IDS)
    source_input_rows = {
        source_id: pq.read_table(path).num_rows
        for source_id, path in source_paths().items()
    }
    reconciles = all(source_rows[source_id] == source_input_rows[source_id] for source_id in SOURCE_IDS)
    years = sorted(int(value) for value in mart["year"].dropna().unique())
    null_year_sources = sorted(mart.loc[mart["year"].isna(), "source_id"].unique())
    text_values = Counter(mart["value_text"].dropna())
    duplicate_count = int(mart.duplicated(list(GRAIN_COLUMNS)).sum())

    rows = [
        "# EDA — `mart_contexto_genero_indicador_sexo`",
        "",
        "**Script reproducible:** `scripts/eda_mart_contexto_genero_indicador_sexo.py`  ",
        "**Archivo analizado:** `data/processed/marts/mart_contexto_genero_indicador_sexo.parquet`",
        "",
        "## 1. Forma y grano",
        "",
        f"- **{len(mart)} filas × {len(mart.columns)} columnas.**",
        "- Grano: una observación publicada de un indicador de contexto de salud mental por sexo, fuente, ámbito geográfico y período.",
        f"- La clave lógica `{', '.join(GRAIN_COLUMNS)}` tiene {duplicate_count} duplicados.",
        "",
        "## 2. Reconciliación contra inputs processed",
        "",
        "| `source_id` | Filas input | Filas mart | ¿Reconcilia? |",
        "|---|---:|---:|---|",
    ]
    for source_id in SOURCE_IDS:
        input_rows = source_input_rows[source_id]
        mart_rows = int(source_rows[source_id])
        rows.append(f"| `{source_id}` | {input_rows} | {mart_rows} | {'Sí' if input_rows == mart_rows else 'No'} |")
    rows.extend([
        "",
        f"- Reconciliación por fuente: **{'exacta' if reconciles else 'fallida'}**.",
        "- Los cuatro `source_id` esperados están presentes; el mart no agrega ni elimina observaciones.",
        "",
        "## 3. Temporalidad, ámbito y valores publicados",
        "",
        f"- Años numéricos observados: {', '.join(map(str, years))}.",
        f"- Fuentes con `year=NULL` preservado: {', '.join(f'`{source_id}`' for source_id in null_year_sources)}.",
        "- `period` se conserva como texto publicado, incluidos `2009-10`, `2016-17` y las rondas PHQ-4; no se reconstruye una periodicidad común.",
        f"- Valores textuales publicados: `{dict(text_values)}`; el símbolo `-` permanece en `value_text`.",
        f"- Ámbitos geográficos observados: {', '.join(sorted(mart['geography_level'].unique()))}; no se fuerza cobertura comunal ni exclusiva RM.",
        "",
        "## 4. Límites de uso",
        "",
        "Este mart es **contexto interpretativo** para serving del MVP. No contiene FK, joins ni enriquecimiento con Urgencias o Egresos; coincidencias de sexo, año, período o territorio no habilitan relaciones automáticas. No se usa automáticamente como feature y no representa personas, pacientes ni episodios individuales.",
        "",
        "## 5. Conclusión QA",
        "",
        "El mart conserva el contrato normalizado de las cuatro fuentes y sus valores publicados, manteniendo sus diferencias semánticas en `source_id`, `period`, `year`, geografía, sexo, indicador y unidad.",
    ])
    return "\n".join(rows) + "\n"


def run_eda() -> Path:
    """Escribe el reporte reproducible en su ubicación canónica."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_report(), encoding="utf-8")
    return REPORT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA breve del mart contextual por sexo/género.")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    print(run_eda().as_posix())


if __name__ == "__main__":
    main()
