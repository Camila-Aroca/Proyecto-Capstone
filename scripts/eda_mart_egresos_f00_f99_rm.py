"""EDA reproducible de los marts de egresos de residentes RM y del contraste de camas.

Cubre `mart_egresos_f00_f99_rm_anual`, `mart_egresos_f00_f99_rm_desglose` y
`contraste_camas_psiquiatria_rm`. Calcula, desde los datos, las cifras que citan sus
diccionarios: forma y llaves, conciliación (comunas = región = egresos de residentes RM,
cada dimensión = total), tasas, estadía, volumen por comuna-año y el contraste de camas.
Primero los valores observados, después su lectura.

Uso (vía pipeline): `python scripts/run_pipeline.py --stage eda_mart_egresos_f00_f99_rm`
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq

ANUAL_PATH: Final[Path] = Path("data/processed/marts/mart_egresos_f00_f99_rm_anual.parquet")
DESGLOSE_PATH: Final[Path] = Path("data/processed/marts/mart_egresos_f00_f99_rm_desglose.parquet")
CONTRASTE_PATH: Final[Path] = Path("data/processed/marts/contraste_camas_psiquiatria_rm.parquet")
EGRESOS_PATH: Final[Path] = Path("data/processed/egresos/egresos_f00_f99_nacional_2020_2025.parquet")
OUTPUT_REPORT: Final[Path] = Path("reports/eda/eda_mart_egresos_f00_f99_rm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/eda/eda_mart_egresos_f00_f99_rm_resumen.json")
TITULO: Final[str] = "# EDA de los marts de egresos F00-F99 de residentes RM y del contraste de camas"
REGION_ID: Final[str] = "RM"
UMBRAL_POCOS_EGRESOS: Final[int] = 10


def tabla_md(frame: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |"
             for fila in frame.itertuples(index=False, name=None)]
    return "\n".join([encabezado, separador, *filas])


def analizar(anual: pd.DataFrame, desglose: pd.DataFrame, contraste: pd.DataFrame,
             residentes_por_ano: pd.Series) -> dict[str, Any]:
    """Cifras del EDA calculadas solo desde los datos de entrada."""
    comunas = anual[anual["nivel"] == "comuna"]
    region = anual[anual["nivel"] == "region"].set_index("ano")
    suma_comunas = comunas.groupby("ano")["egresos"].sum()
    por_dimension = desglose.groupby(["series_id", "ano", "dimension"])["egresos"].sum().reset_index()
    por_dimension = por_dimension.merge(anual[["series_id", "ano", "egresos"]], on=["series_id", "ano"], suffixes=("_dim", "_total"))
    con_tasa = comunas.dropna(subset=["poblacion"])
    recalculo = (con_tasa["egresos"] / con_tasa["poblacion"] * 10_000 - con_tasa["tasa_por_10000"]).abs()
    region_ano = region.reset_index()
    return {
        "filas_anual": int(len(anual)),
        "filas_desglose": int(len(desglose)),
        "territorios": int(anual["series_id"].nunique()),
        "comunas": int(comunas["series_id"].nunique()),
        "anos": [int(a) for a in sorted(anual["ano"].unique())],
        "pk_anual_duplicados": int(anual.duplicated(["series_id", "ano"]).sum()),
        "pk_desglose_duplicados": int(desglose.duplicated(["series_id", "ano", "dimension", "categoria"]).sum()),
        "desglose_sin_anual": int(len(set(zip(desglose["series_id"], desglose["ano"])) - set(zip(anual["series_id"], anual["ano"])))),
        "nulos_poblacion_por_ano": {int(a): int(n) for a, n in anual[anual["poblacion"].isna()].groupby("ano").size().items()},
        "poblacion_y_tasa_nulas_a_la_vez": bool((anual["poblacion"].isna() == anual["tasa_por_10000"].isna()).all()),
        "comunas_suman_region": bool(suma_comunas.equals(region["egresos"])),
        "region_igual_egresos_residentes_rm": bool(region["egresos"].astype("int64").equals(residentes_por_ano.astype("int64"))),
        "dimension_territorio_ano_distintos_del_total": int((por_dimension["egresos_dim"] != por_dimension["egresos_total"]).sum()),
        "dimension_territorio_ano_total": int(len(por_dimension)),
        "tasa_recalculo_max_diferencia": float(recalculo.max()) if len(recalculo) else None,
        "p90_menor_que_mediana": int((anual["dias_estada_p90"] < anual["dias_estada_mediana"]).sum()),
        "comunas_ano_sin_egresos": int((comunas["egresos"] == 0).sum()),
        "comunas_ano_con_pocos_egresos": int((comunas["egresos"] < UMBRAL_POCOS_EGRESOS).sum()),
        "umbral_pocos_egresos": UMBRAL_POCOS_EGRESOS,
        "egresos_comuna_ano": {k: float(v) for k, v in comunas["egresos"].describe().items()},
        "categorias_por_dimension": {k: int(v) for k, v in desglose.groupby("dimension")["categoria"].nunique().items()},
        "region_por_ano": region_ano[["ano", "egresos", "poblacion", "tasa_por_10000", "dias_estada_mediana", "dias_estada_p90",
                                      "proporcion_snss"]].to_dict("records"),
        "contraste": contraste.to_dict("records"),
        "contraste_egresos_igual_region": bool(
            contraste.set_index("ano")["egresos_residentes_rm"].astype("int64").equals(region.loc[contraste["ano"], "egresos"].astype("int64"))),
    }


def build_report() -> tuple[str, dict[str, Any]]:
    anual = pq.read_table(ANUAL_PATH).to_pandas()
    desglose = pq.read_table(DESGLOSE_PATH).to_pandas()
    contraste = pq.read_table(CONTRASTE_PATH).to_pandas()
    egresos = pq.read_table(EGRESOS_PATH, columns=["ano_egreso", "residente_rm"]).to_pandas()
    residentes = egresos[egresos["residente_rm"].fillna(False).astype(bool)].groupby("ano_egreso").size().rename_axis("ano")
    r = analizar(anual, desglose, contraste, residentes)
    region = pd.DataFrame(r["region_por_ano"]).round(3)
    cont = contraste.round(3)
    desc = r["egresos_comuna_ano"]
    texto = f"""{TITULO}

Datasets: `{ANUAL_PATH.as_posix()}`, `{DESGLOSE_PATH.as_posix()}` y `{CONTRASTE_PATH.as_posix()}`
(diccionarios en `reports/dictionary/diccionario_mart_egresos_f00_f99_rm.md` y
`reports/dictionary/diccionario_contraste_camas_psiquiatria_rm.md`). Script:
`scripts/eda_mart_egresos_f00_f99_rm.py`. Los egresos son registros publicados, no pacientes únicos, y el
territorio es la comuna de **residencia**: no hay enlace por paciente ni por establecimiento.

## Forma y llaves (observado)

- Anual: {r['filas_anual']} filas = {r['territorios']} territorios ({r['comunas']} comunas y la región `{REGION_ID}`) x {len(r['anos'])} años ({r['anos'][0]}-{r['anos'][-1]}).
- Desglose: {r['filas_desglose']} filas. Categorías por dimensión: {r['categorias_por_dimension']}.
- Duplicados de la llave `series_id, ano`: {r['pk_anual_duplicados']}. Duplicados de `series_id, ano, dimension, categoria`: {r['pk_desglose_duplicados']}.
- `(series_id, ano)` del desglose sin fila en el anual: {r['desglose_sin_anual']}.
- Filas con población nula por año: {r['nulos_poblacion_por_ano']}; población y tasa nulas a la vez en todas las filas: {r['poblacion_y_tasa_nulas_a_la_vez']}.

## Conciliación (observado)

- Las comunas suman la región en todos los años: {r['comunas_suman_region']}.
- La región iguala los egresos de residentes RM del dataset nacional en todos los años: {r['region_igual_egresos_residentes_rm']}.
- Combinaciones territorio-año-dimensión cuya suma difiere del total: {r['dimension_territorio_ano_distintos_del_total']} de {r['dimension_territorio_ano_total']}.
- Máxima diferencia al recalcular `egresos / poblacion x 10.000` en comunas: {r['tasa_recalculo_max_diferencia']}.
- Filas con p90 de estadía menor que la mediana: {r['p90_menor_que_mediana']}.

## Región por año

{tabla_md(region)}

## Volumen por comuna-año (observado)

- Comuna-años sin egresos: {r['comunas_ano_sin_egresos']}. Con menos de {r['umbral_pocos_egresos']} egresos: {r['comunas_ano_con_pocos_egresos']} de {int(desc['count'])}.
- Egresos por comuna-año: mínimo {desc['min']:.0f}, mediana {desc['50%']:.0f}, máximo {desc['max']:.0f}.

## Contraste de camas (observado)

{tabla_md(cont)}

- `egresos_residentes_rm` del contraste iguala los egresos de la región en cada año: {r['contraste_egresos_igual_region']}.

## Lectura (interpretación)

- Con pocos egresos por comuna-año, las tasas comunales son inestables; conviene leerlas junto con el conteo.
- La tasa de 2020 es nula por falta de denominador (la proyección comunal parte en 2021), no cero.
- Las camas equivalentes de Egresos son una cota superior (la estadía se acota al año) y no deben coincidir con REM-20; la razón solo respalda el orden de magnitud. Las causas de la brecha restante no son determinables con estos datos.
"""
    return texto, r


def validate_outputs(report: Path = OUTPUT_REPORT, summary: Path = OUTPUT_SUMMARY) -> None:
    if not report.read_text(encoding="utf-8").startswith(TITULO):
        raise ValueError(f"{report.name}: encabezado inesperado")
    datos = json.loads(summary.read_text(encoding="utf-8"))
    faltantes = {"filas_anual", "filas_desglose", "comunas_suman_region", "region_igual_egresos_residentes_rm",
                 "dimension_territorio_ano_distintos_del_total", "contraste"} - set(datos)
    if faltantes:
        raise ValueError(f"{summary.name}: faltan claves {sorted(faltantes)}")
    if (not datos["comunas_suman_region"] or not datos["region_igual_egresos_residentes_rm"]
            or datos["dimension_territorio_ano_distintos_del_total"] or datos["pk_anual_duplicados"]):
        raise ValueError(f"{summary.name}: los marts no concilian o tienen llaves duplicadas")


def main() -> None:
    texto, resumen = build_report()
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(texto, encoding="utf-8")
    OUTPUT_SUMMARY.write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    validate_outputs()
    print(f"EDA generado: {OUTPUT_REPORT.as_posix()}", flush=True)


if __name__ == "__main__":
    if "--force" in sys.argv:
        sys.argv.remove("--force")
    main()
