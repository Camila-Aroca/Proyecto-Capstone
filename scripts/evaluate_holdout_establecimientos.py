"""Evaluación en holdout del pronóstico por establecimiento (ID36 e ID42).

El benchmark eligió un modelo por objetivo con 2022-2025. Aquí se evalúa esa
selección congelada en los años posteriores, que no vio: hoy, el año en curso.
Sigue el mismo diseño de la evaluación comunal
(`scripts/evaluate_holdout_demanda_sm.py`):

- Solo semanas completas del año en curso; la última publicada suele venir truncada.
- Universo fijo: los establecimientos del benchmark que reportan todas las
  semanas del holdout. Quien deja de reportar no tiene demanda cero, no tiene
  dato; se excluye y se informa.
- Escalas MASE de la historia previa al primer origen del benchmark, para que el
  holdout y el backtest sean comparables.
- Snapshot del año en curso identificado por SHA256.

Responde tres preguntas por objetivo: ¿el modelo sigue superando al baseline?,
¿sus intervalos cubren lo declarado?, ¿se degradó respecto del backtest?

Uso (vía pipeline): `python scripts/run_pipeline.py --stage evaluate_holdout_establecimientos_sm`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from scripts.run_benchmark_establecimientos import (
    ALFA,
    OUTPUT_SELECTION as SELECTION_PATH,
    OUTPUT_SUMMARY as BENCHMARK_SUMMARY,
    REFERENCIA,
    _tabla_md,
    model_table,
)
from src.models.backtesting import (
    build_origins,
    compute_mase_scales,
    prepare_supervised,
    rolling_origin_backtest,
)
from src.models.establecimientos import (
    NIVEL_ESTABLECIMIENTO,
    OBJETIVOS,
    Objetivo,
    build_establishment_panel,
    fixed_universe,
    load_current_weekly,
    load_mart,
    select_universe,
)
from src.models.features import RM_SERIES_ID
from src.models.holdout import holdout_years, snapshot_info
from src.models.metrics import evaluate_predictions, paired_comparison
from src.models.registry import available_models, build_model

OUTPUT_REPORT: Final[Path] = Path("reports/modeling/holdout_establecimientos_sm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/modeling/holdout_establecimientos_sm_resumen.csv")
TITULO: Final[str] = "# Evaluación en holdout del pronóstico por establecimiento"
# Un origen por semana: el holdout es corto y se aprovecha entero.
STEP: Final[int] = 1
NIVELES: Final[tuple[str, str]] = ("region", NIVEL_ESTABLECIMIENTO)


def models_to_evaluate(recomendado: str) -> list[str]:
    """Baseline, todos los conformes del registro y el recomendado.

    Igual que en la evaluación comunal: la pregunta «¿habría ganado otro?» no
    depende de a quién se invitó.
    """
    nombres = [REFERENCIA] + [n for n in available_models() if n.endswith("_conformal")]
    if recomendado not in nombres:
        nombres.append(recomendado)
    return nombres


def mase_backtest(objetivo: str, modelo: str, panel: pd.DataFrame) -> dict[str, float]:
    """MASE del benchmark para un modelo y objetivo, agregado como en el holdout."""
    resumen = pd.read_csv(BENCHMARK_SUMMARY, dtype={"series_id": str})
    resumen = resumen[(resumen["objetivo"] == objetivo) & (resumen["modelo"] == modelo)]
    niveles = panel[["series_id", "nivel"]].drop_duplicates()
    por_horizonte = resumen.merge(niveles, on="series_id").groupby(["nivel", "horizonte"])["mase"].median()
    return {n: float(por_horizonte.loc[n].mean()) for n in NIVELES}


def degradation(
    objetivo: str, recomendado: str, tabla: pd.DataFrame, panel: pd.DataFrame
) -> pd.DataFrame:
    """MASE en backtest y holdout, y habilidad frente al baseline en cada período.

    La habilidad se mide contra el baseline **del mismo período**: un año más
    fácil o más difícil de pronosticar no se confunde con un cambio del modelo.
    """
    hold = tabla.set_index("modelo")
    back_rec, back_ref = mase_backtest(objetivo, recomendado, panel), mase_backtest(objetivo, REFERENCIA, panel)
    filas = []
    for nivel in NIVELES:
        rec_h, ref_h = float(hold.loc[recomendado, f"mase_{nivel}"]), float(hold.loc[REFERENCIA, f"mase_{nivel}"])
        filas.append({
            "nivel": "total" if nivel == "region" else "establecimientos",
            "MASE backtest": round(back_rec[nivel], 4),
            "MASE holdout": round(rec_h, 4),
            "habilidad backtest (%)": round((1 - back_rec[nivel] / back_ref[nivel]) * 100, 1),
            "habilidad holdout (%)": round((1 - rec_h / ref_h) * 100, 1),
        })
    return pd.DataFrame(filas)


def evaluate_objetivo(
    objetivo: Objetivo, mart: pd.DataFrame, actual: pd.DataFrame, seleccion: dict
) -> dict[str, object]:
    recomendado = seleccion["modelo_recomendado"]
    nivel_intervalo = float(seleccion["nivel_intervalo"])
    horizontes = tuple(int(h) for h in seleccion["horizontes"])
    ano_inicio = int(seleccion["universo"]["ano_inicio"])

    universo, excluidos = fixed_universe(
        select_universe(mart, objetivo, ano_inicio=ano_inicio), actual, objetivo
    )
    panel = build_establishment_panel(
        pd.concat([mart, actual[mart.columns]], ignore_index=True), objetivo, universo, ano_inicio
    )
    t_fin = int(panel.loc[panel["ano"] <= int(mart["ano"].max()), "t"].max())
    esperado = int(seleccion["periodo_backtest"]["t_ultimo_origen"]) + max(horizontes)
    if t_fin != esperado:
        raise ValueError(
            f"El índice temporal no coincide con el benchmark ({objetivo.nombre}): "
            f"fin de entrenamiento t={t_fin}, esperado t={esperado}."
        )
    n_origenes = int(panel["t"].max()) - max(horizontes) - t_fin + 1
    if n_origenes < 1:
        raise ValueError("El holdout es más corto que el horizonte máximo.")
    origenes = build_origins(panel, horizontes, n_origenes, STEP)
    escalas = compute_mase_scales(panel, hasta_t=int(seleccion["periodo_backtest"]["t_primer_origen"]))
    supervisada = prepare_supervised(panel, horizontes, exogenous=objetivo.exogenas)

    predicciones, resumenes = {}, {}
    for nombre in models_to_evaluate(recomendado):
        inicio = time.perf_counter()
        pred = rolling_origin_backtest(
            panel, build_model(nombre, nivel_intervalo), horizontes, n_origenes, STEP, supervised=supervisada,
        )
        # Solo los objetivos del año en curso: los orígenes tempranos alcanzan semanas de entrenamiento.
        pred = pred[pred["t"] > t_fin].reset_index(drop=True)
        predicciones[nombre] = pred
        resumenes[nombre] = evaluate_predictions(pred, escalas, nivel_intervalo).assign(
            modelo=nombre, objetivo=objetivo.nombre
        )
        print(f"  [{objetivo.nombre}] {nombre}: {time.perf_counter() - inicio:.1f}s", flush=True)

    tabla = model_table(predicciones, resumenes, panel)
    establecimientos = sorted(set(panel["series_id"]) - {RM_SERIES_ID})
    series_por_nivel = {"region": [RM_SERIES_ID], NIVEL_ESTABLECIMIENTO: establecimientos}
    contraste = {
        n: paired_comparison(predicciones[REFERENCIA], predicciones[recomendado], escalas, s)
        for n, s in series_por_nivel.items()
    }
    alternativas = []
    for nombre, pred in predicciones.items():
        if nombre in (recomendado, REFERENCIA):
            continue
        for n, s in series_por_nivel.items():
            c = paired_comparison(predicciones[recomendado], pred, escalas, s)
            alternativas.append({
                "alternativa": nombre, "nivel": "total" if n == "region" else "establecimientos",
                "cambio (%)": c["cambio_pct"], "p-valor": c["p_valor"],
            })
    fila = tabla.set_index("modelo").loc[recomendado]
    supera = contraste[NIVEL_ESTABLECIMIENTO]["p_valor"] < ALFA and contraste[NIVEL_ESTABLECIMIENTO]["cambio_pct"] < 0
    calibrado = bool(fila[f"calibrado_{NIVEL_ESTABLECIMIENTO}"])
    tabla_degradacion = degradation(objetivo.nombre, recomendado, tabla, panel)
    conserva = bool(
        tabla_degradacion.loc[tabla_degradacion["nivel"] == "establecimientos", "habilidad holdout (%)"].iloc[0] > 0
    )
    rival = [
        a for a in alternativas
        if a["nivel"] == "establecimientos" and a["p-valor"] < ALFA and a["cambio (%)"] < 0
    ]
    return {
        "objetivo": objetivo, "recomendado": recomendado, "universo": universo, "excluidos": excluidos,
        "origenes": origenes, "t_fin": t_fin, "tabla": tabla, "contraste": contraste,
        "alternativas": pd.DataFrame(alternativas), "degradacion": tabla_degradacion,
        "criterios": {
            "supera al baseline con diferencia significativa en los establecimientos": supera,
            "conserva habilidad frente al baseline en los establecimientos": conserva,
            "cobertura de los establecimientos dentro de la tolerancia": calibrado,
            "ninguna alternativa es significativamente mejor en los establecimientos": not rival,
        },
        "resumen": pd.concat(resumenes.values(), ignore_index=True),
        "semanas": int(panel.loc[panel["t"] > t_fin, "t"].nunique()),
    }


def render_section(r: dict[str, object], numero: int) -> list[str]:
    objetivo: Objetivo = r["objetivo"]
    tabla = r["tabla"].rename(columns={
        "mase_region": "MASE total", f"mase_{NIVEL_ESTABLECIMIENTO}": "MASE establecimientos",
        "cobertura_region": "cobertura total", f"cobertura_{NIVEL_ESTABLECIMIENTO}": "cobertura establecimientos",
        "calibrado_region": "calibrado total", f"calibrado_{NIVEL_ESTABLECIMIENTO}": "calibrado establecimientos",
        "mase_promedio": "MASE promedio",
    })
    contraste = pd.DataFrame([
        {"nivel": "total" if n == "region" else "establecimientos", "evaluaciones": c["n"],
         "cambio (%)": c["cambio_pct"], "pronósticos en que mejora": f"{c['proporcion_b_mejor'] * 100:.1f}%",
         "p-valor": c["p_valor"]}
        for n, c in r["contraste"].items()
    ])
    criterios = pd.DataFrame(
        [{"criterio": k, "se cumple": "sí" if v else "no"} for k, v in r["criterios"].items()]
    )
    excluidos = r["excluidos"]
    return [
        f"## {numero}. {objetivo.descripcion}",
        "",
        f"Modelo congelado: **`{r['recomendado']}`**. {r['semanas']} semanas de holdout evaluadas.",
        "",
        f"### {numero}.1 Universo fijo",
        "",
        f"{int(r['universo']['incluido'].sum())} establecimientos con todas las semanas del holdout. "
        + (
            f"Se excluyen {len(excluidos)} del universo del benchmark por dejar de reportar, "
            f"con {excluidos['share_pct'].sum():.2f}% del volumen del año en curso:"
            if not excluidos.empty else "Ninguno del universo del benchmark se excluye."
        ),
        "",
        *([_tabla_md(excluidos), ""] if not excluidos.empty else []),
        f"### {numero}.2 Modelos en el holdout",
        "",
        _tabla_md(tabla),
        "",
        f"### {numero}.3 Contra el baseline",
        "",
        _tabla_md(contraste),
        "",
        f"### {numero}.4 Degradación respecto del backtest",
        "",
        _tabla_md(r["degradacion"]),
        "",
        f"### {numero}.5 Alternativas frente al elegido",
        "",
        "Cambio del error de cada alternativa respecto del elegido (negativo: la alternativa es mejor).",
        "",
        _tabla_md(r["alternativas"]) if not r["alternativas"].empty else "No hay alternativas.",
        "",
        f"### {numero}.6 Veredicto",
        "",
        _tabla_md(criterios),
        "",
    ]


def render_report(resultados: list[dict[str, object]], snapshot: pd.DataFrame, incompletas: pd.DataFrame) -> str:
    snap = snapshot[["ano", "raw_sha256", "procesado_sha256", "estado_procedencia"]]
    lineas = [
        TITULO,
        "",
        "Generado por `scripts/evaluate_holdout_establecimientos.py` (stage "
        "`evaluate_holdout_establecimientos_sm`). No editar a mano. Evalúa la selección congelada en "
        f"`{SELECTION_PATH.as_posix()}`.",
        "",
        "## Snapshot evaluado",
        "",
        "La fuente del año en curso es mutable: estas cifras valen para este snapshot.",
        "",
        _tabla_md(snap),
        "",
        "Semanas regulares excluidas por estar incompletas: "
        + (", ".join(f"{int(f.ano)}-S{int(f.semana)} ({int(f.dias)} días)" for f in incompletas.itertuples())
           or "ninguna") + ".",
        "",
    ]
    for numero, r in enumerate(resultados, start=1):
        lineas.extend(render_section(r, numero))
    lineas.extend([
        f"## {len(resultados) + 1}. Limitaciones",
        "",
        "- El holdout cubre parte de un solo año: no incluye todas las estaciones.",
        "- Las semanas evaluadas se superponen entre horizontes y orígenes: las evaluaciones no son independientes.",
        "- Usar este holdout para elegir otro modelo lo dejaría de ser una evaluación independiente de ese modelo.",
        "",
    ])
    return "\n".join(lineas)


def main() -> None:
    selecciones = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    mart = load_mart()
    anos = holdout_years(int(mart["ano"].max()))
    if not anos:
        raise ValueError("No hay datos procesados posteriores al período de entrenamiento.")
    actual, incompletas = load_current_weekly(anos)
    resultados = []
    for nombre, objetivo in OBJETIVOS.items():
        print(f"Objetivo {nombre}...", flush=True)
        resultados.append(evaluate_objetivo(objetivo, mart, actual, selecciones[nombre]))
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([r["resumen"] for r in resultados], ignore_index=True).to_csv(OUTPUT_SUMMARY, index=False)
    OUTPUT_REPORT.write_text(
        render_report(resultados, snapshot_info(anos), incompletas), encoding="utf-8", newline="\n"
    )
    for r in resultados:
        print(r["objetivo"].nombre, r["criterios"])


if __name__ == "__main__":
    main()
