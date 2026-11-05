"""Benchmark del pronóstico por establecimiento (ID36 e ID42).

Repite, sobre el panel de establecimientos, el mismo diseño del benchmark
comunal (`scripts/run_demand_benchmark.py`): backtesting con origen deslizante,
los modelos del registro único, métricas por nivel y la misma regla de
selección. Lo hace para dos objetivos:

- `atenciones_sm`: atenciones de urgencia en salud mental (ID36).
- `hospitalizaciones_sm`: hospitalizaciones derivadas desde la urgencia (ID42).

**Regla de selección**, idéntica a la comunal: entre los modelos que superan al
baseline estacional en MASE promedio, se elige el de menor MASE entre los que
tienen cobertura compatible con el nominal en el total y en los
establecimientos (tolerancia muestral). Si ninguno está calibrado, se elige el
más preciso y se declara. Las selecciones quedan congeladas en un JSON.

Además responde una pregunta propia de este nivel: **desde qué volumen
semanal el modelo le gana al baseline**, comparando por grupo de volumen.

Uso (vía pipeline): `python scripts/run_pipeline.py --stage benchmark_establecimientos_sm`
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

import numpy as np
import pandas as pd

from src.models import RANDOM_SEED
from src.models.backtesting import (
    aggregate_by_level,
    build_origins,
    compute_mase_scales,
    prepare_supervised,
    rolling_origin_backtest,
    summarize_backtest,
)
from src.models.establecimientos import (
    ANO_INICIO,
    MIN_MEDIA_ANUAL,
    MIN_MEDIA_SEMANAL,
    NIVEL_ESTABLECIMIENTO,
    OBJETIVOS,
    Objetivo,
    build_establishment_panel,
    load_mart,
    select_universe,
)
from src.models.features import RM_SERIES_ID
from src.models.metrics import coverage_tolerance, paired_comparison
from src.models.registry import available_models, build_model

OUTPUT_REPORT: Final[Path] = Path("reports/modeling/benchmark_establecimientos_sm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/modeling/benchmark_establecimientos_sm_resumen.csv")
OUTPUT_UNIVERSE: Final[Path] = Path("reports/modeling/benchmark_establecimientos_sm_universo.csv")
OUTPUT_SELECTION: Final[Path] = Path("reports/modeling/benchmark_establecimientos_sm_seleccion.json")
TITULO: Final[str] = "# Benchmark del pronóstico por establecimiento"

# Mismo diseño de evaluación que el benchmark comunal.
HORIZONS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8)
N_ORIGINS: Final[int] = 13
STEP: Final[int] = 4
NIVEL_INTERVALO: Final[float] = 0.80
ALFA: Final[float] = 0.05
REFERENCIA: Final[str] = "baseline_estacional"
NIVELES: Final[tuple[str, str]] = ("region", NIVEL_ESTABLECIMIENTO)
# Grupos de volumen para la pregunta "desde qué volumen conviene el modelo".
GRUPOS_VOLUMEN: Final[tuple[float, ...]] = (1.0, 5.0, 10.0, 25.0, float("inf"))


def _tabla_md(frame: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |"
        for fila in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([encabezado, separador, *filas])


def model_table(
    predicciones: dict[str, pd.DataFrame], resumenes: dict[str, pd.DataFrame], panel: pd.DataFrame
) -> pd.DataFrame:
    """Una fila por modelo: MASE mediano por nivel (promedio de horizontes) y calibración.

    Mismas definiciones que el benchmark comunal, para que ambas tablas se lean igual.
    """
    filas = []
    for nombre, pred in predicciones.items():
        por_nivel = aggregate_by_level(resumenes[nombre], panel)
        mase = por_nivel.groupby("nivel")["mase_mediano"].mean()
        fila: dict[str, object] = {"modelo": nombre}
        for nivel in NIVELES:
            propias = pred[pred["nivel"] == nivel]
            dentro = (propias["y_real"] >= propias["y_inferior"]) & (
                propias["y_real"] <= propias["y_superior"]
            )
            cobertura = float(dentro.mean())
            fila[f"mase_{nivel}"] = round(float(mase.get(nivel, np.nan)), 4)
            fila[f"cobertura_{nivel}"] = round(cobertura, 4)
            fila[f"calibrado_{nivel}"] = bool(
                abs(cobertura - NIVEL_INTERVALO) <= coverage_tolerance(len(propias), NIVEL_INTERVALO)
            )
        fila["mase_promedio"] = round((fila["mase_region"] + fila[f"mase_{NIVEL_ESTABLECIMIENTO}"]) / 2, 4)
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("mase_promedio").reset_index(drop=True)


def select_model(tabla: pd.DataFrame) -> tuple[str, str]:
    """Regla de selección del benchmark comunal, aplicada a establecimientos."""
    referencia = float(tabla.loc[tabla["modelo"] == REFERENCIA, "mase_promedio"].iloc[0])
    candidatos = tabla[
        ~tabla["modelo"].str.startswith("baseline") & (tabla["mase_promedio"] < referencia)
    ].sort_values("mase_promedio", kind="stable")
    if candidatos.empty:
        return REFERENCIA, "ningún modelo supera al baseline estacional en MASE promedio"
    calibrados = candidatos[
        candidatos["calibrado_region"] & candidatos[f"calibrado_{NIVEL_ESTABLECIMIENTO}"]
    ]
    if calibrados.empty:
        return str(candidatos.iloc[0]["modelo"]), (
            "ninguno de los modelos que superan al baseline tiene cobertura calibrada en ambos "
            "niveles; se elige el más preciso y sus intervalos deben leerse como orientativos"
        )
    return str(calibrados.iloc[0]["modelo"]), (
        "menor MASE promedio entre los modelos que superan al baseline con cobertura "
        "calibrada en el total y en los establecimientos"
    )


def skill_by_volume(
    resumenes: dict[str, pd.DataFrame], elegido: str, universo: pd.DataFrame
) -> pd.DataFrame:
    """MASE del elegido frente al baseline, por grupo de volumen semanal medio."""
    def _por_serie(nombre: str) -> pd.Series:
        r = resumenes[nombre]
        return r[r["series_id"] != RM_SERIES_ID].groupby("series_id")["mase"].mean()

    modelo, base = _por_serie(elegido), _por_serie(REFERENCIA)
    volumen = universo.set_index(universo["establecimiento_codigo"].astype(str))["media_semanal"]
    tabla = pd.DataFrame({"modelo": modelo, "baseline": base}).join(volumen)
    cortes = [MIN_MEDIA_SEMANAL, *GRUPOS_VOLUMEN[1:]]
    etiquetas = [
        f"{cortes[i]:g} a {cortes[i + 1]:g}" if np.isfinite(cortes[i + 1]) else f"{cortes[i]:g} o más"
        for i in range(len(cortes) - 1)
    ]
    tabla["grupo"] = pd.cut(tabla["media_semanal"], cortes, labels=etiquetas, right=False)
    resumen = tabla.groupby("grupo", observed=True).agg(
        establecimientos=("modelo", "size"),
        mase_modelo=("modelo", "median"),
        mase_baseline=("baseline", "median"),
        gana_al_baseline=("modelo", lambda s: float((s < tabla.loc[s.index, "baseline"]).mean())),
    )
    resumen["gana_al_baseline"] = (resumen["gana_al_baseline"] * 100).round(1)
    return resumen.round(4).reset_index()


def run_objetivo(weekly: pd.DataFrame, objetivo: Objetivo) -> dict[str, object]:
    """Backtesting completo de un objetivo y su selección."""
    universo = select_universe(weekly, objetivo)
    panel = build_establishment_panel(weekly, objetivo, universo)
    origenes = build_origins(panel, HORIZONS, N_ORIGINS, STEP)
    escalas = compute_mase_scales(panel, hasta_t=min(origenes))
    supervisada = prepare_supervised(panel, HORIZONS, exogenous=objetivo.exogenas)

    predicciones, resumenes = {}, {}
    for nombre in available_models():
        inicio = time.perf_counter()
        pred = rolling_origin_backtest(
            panel, build_model(nombre, NIVEL_INTERVALO), HORIZONS, N_ORIGINS, STEP,
            supervised=supervisada,
        )
        predicciones[nombre] = pred
        resumen = summarize_backtest(pred, panel, HORIZONS, N_ORIGINS, STEP, NIVEL_INTERVALO)
        resumenes[nombre] = resumen.assign(modelo=nombre)
        print(f"  [{objetivo.nombre}] {nombre}: {time.perf_counter() - inicio:.1f}s", flush=True)

    tabla = model_table(predicciones, resumenes, panel)
    elegido, criterio = select_model(tabla)
    establecimientos = sorted(set(panel["series_id"]) - {RM_SERIES_ID})
    contraste = {
        nivel: paired_comparison(predicciones[REFERENCIA], predicciones[elegido], escalas, series)
        for nivel, series in (("region", [RM_SERIES_ID]), (NIVEL_ESTABLECIMIENTO, establecimientos))
    }
    fila = tabla.set_index("modelo").loc[elegido]
    return {
        "objetivo": objetivo,
        "universo": universo,
        "panel": panel,
        "origenes": origenes,
        "tabla": tabla,
        "elegido": elegido,
        "criterio": criterio,
        "contraste": contraste,
        "volumen": skill_by_volume(resumenes, elegido, universo),
        "resumen": pd.concat(resumenes.values(), ignore_index=True).assign(objetivo=objetivo.nombre),
        "seleccion": {
            "modelo_recomendado": elegido,
            "criterio": criterio,
            "target": objetivo.target,
            "exogenas": list(objetivo.exogenas),
            "nivel_intervalo": NIVEL_INTERVALO,
            "horizontes": list(HORIZONS),
            "semilla": RANDOM_SEED,
            "universo": {
                "ano_inicio": ANO_INICIO,
                "min_media_semanal": MIN_MEDIA_SEMANAL,
                "min_media_anual": MIN_MEDIA_ANUAL,
                "solo_hospitales": objetivo.solo_hospitales,
                "establecimientos": len(establecimientos),
            },
            "periodo_backtest": {
                "origenes": len(origenes), "paso": STEP,
                "t_primer_origen": int(min(origenes)), "t_ultimo_origen": int(max(origenes)),
            },
            "metricas_backtest": {
                "mase_total": float(fila["mase_region"]),
                "mase_establecimiento": float(fila[f"mase_{NIVEL_ESTABLECIMIENTO}"]),
                "cobertura_total": float(fila["cobertura_region"]),
                "cobertura_establecimiento": float(fila[f"cobertura_{NIVEL_ESTABLECIMIENTO}"]),
            },
        },
    }


def render_section(r: dict[str, object], numero: int) -> list[str]:
    objetivo: Objetivo = r["objetivo"]
    universo: pd.DataFrame = r["universo"]
    tabla = r["tabla"].rename(columns={
        "mase_region": "MASE total", f"mase_{NIVEL_ESTABLECIMIENTO}": "MASE establecimientos",
        "cobertura_region": "cobertura total", f"cobertura_{NIVEL_ESTABLECIMIENTO}": "cobertura establecimientos",
        "calibrado_region": "calibrado total", f"calibrado_{NIVEL_ESTABLECIMIENTO}": "calibrado establecimientos",
        "mase_promedio": "MASE promedio",
    })
    exclusiones = universo["motivo_exclusion"].value_counts()
    contraste = pd.DataFrame([
        {"nivel": "total" if n == "region" else "establecimientos", "evaluaciones": c["n"],
         "error baseline": c["error_a"], "error elegido": c["error_b"],
         "cambio (%)": c["cambio_pct"], "pronósticos en que mejora": f"{c['proporcion_b_mejor'] * 100:.1f}%",
         "p-valor": c["p_valor"]}
        for n, c in r["contraste"].items()
    ])
    incluidos = universo[universo["incluido"]]
    return [
        f"## {numero}. {objetivo.descripcion}",
        "",
        f"### {numero}.1 Universo",
        "",
        f"- **{len(incluidos)} establecimientos** entran al panel de un total de {len(universo)}. "
        f"Exclusiones: {', '.join(f'{m} ({n})' for m, n in exclusiones.items()) or 'ninguna'}.",
        f"- Covariables, siempre rezagadas al menos un horizonte: "
        f"{', '.join(f'`{c}`' for c in objetivo.exogenas)}.",
        "- La serie total es la suma de los establecimientos incluidos, no el total regional publicado.",
        "",
        f"### {numero}.2 Comparación de modelos",
        "",
        "MASE mediano por nivel, promedio de los horizontes (menor es mejor; bajo 1 supera al "
        "baseline ingenuo en su propia escala). Calibrado = cobertura dentro de la tolerancia "
        f"muestral alrededor del {int(NIVEL_INTERVALO * 100)}%.",
        "",
        _tabla_md(tabla),
        "",
        f"### {numero}.3 Selección",
        "",
        f"**Elegido: `{r['elegido']}`** — {r['criterio']}.",
        "",
        "Contraste pareado contra el baseline sobre los mismos pronósticos (Wilcoxon):",
        "",
        _tabla_md(contraste),
        "",
        f"### {numero}.4 Desde qué volumen conviene el modelo",
        "",
        "MASE mediano por establecimiento según su volumen semanal medio en la ventana, y "
        "porcentaje de establecimientos donde el elegido tiene menor MASE que el baseline.",
        "",
        _tabla_md(r["volumen"].rename(columns={
            "grupo": "promedio semanal", "mase_modelo": "MASE elegido", "mase_baseline": "MASE baseline",
            "gana_al_baseline": "% que supera al baseline",
        })),
        "",
    ]


def render_report(resultados: list[dict[str, object]]) -> str:
    primero = resultados[0]
    origenes = primero["origenes"]
    lineas = [
        TITULO,
        "",
        "Generado por `scripts/run_benchmark_establecimientos.py` (stage "
        "`benchmark_establecimientos_sm`). No editar a mano. Insumo: "
        "`mart_urgencias_establecimiento_weekly`; su EDA está en "
        "`reports/eda/eda_mart_urgencias_establecimiento_weekly.md`.",
        "",
        "## Diseño",
        "",
        f"- Ventana: semanas regulares desde {ANO_INICIO}. Se excluye 2021 porque el Instituto "
        "Horwitz, el establecimiento de mayor volumen, no reporta sus primeras semanas, y porque "
        "la razón ID42/ID36 cambia de nivel entre 2021 y 2023.",
        f"- Universo: establecimientos con todas las semanas de la ventana reportadas y un promedio "
        f"semanal del objetivo de al menos {MIN_MEDIA_SEMANAL:g}, y de al menos {MIN_MEDIA_ANUAL:g} "
        "en cada año de la ventana (una serie que empieza a registrar a mitad de ventana no tiene "
        "historia comparable y su escala MASE no es interpretable). Una semana sin reporte no se "
        f"imputa; el detalle por establecimiento está en `{OUTPUT_UNIVERSE.as_posix()}`.",
        f"- Backtesting: {len(origenes)} orígenes cada {STEP} semanas (t = {min(origenes)} a "
        f"{max(origenes)}), horizontes {HORIZONS[0]} a {HORIZONS[-1]}. Los modelos son los del "
        "registro único (`src/models/registry.py`), con la misma configuración del modelo comunal.",
        "- Jerarquía: total de los establecimientos → establecimientos. Los modelos híbridos "
        "pronostican el total con el GLM y lo reparten según el boosting (top-down).",
        "",
    ]
    for numero, r in enumerate(resultados, start=1):
        lineas.extend(render_section(r, numero))
    lineas.extend([
        f"## {len(resultados) + 1}. Limitaciones",
        "",
        "- Las cifras son atenciones u hospitalizaciones (eventos), no personas.",
        "- ID42 se registra donde ocurrió la urgencia, no donde quedó hospitalizado el paciente: "
        "no mide la ocupación de camas del establecimiento.",
        "- Con 13 orígenes, la serie total aporta pocas evaluaciones: el contraste detecta "
        "diferencias grandes, no pequeñas.",
        "- El universo exige cobertura completa: un establecimiento nuevo (por ejemplo, un SAR "
        "abierto en la ventana) no se pronostica hasta acumular historia.",
        "- No se evalúa todavía sobre el año en curso; esa evaluación corresponde a una etapa de holdout.",
        "",
    ])
    return "\n".join(lineas)


def main() -> None:
    weekly = load_mart()
    resultados = []
    for objetivo in OBJETIVOS.values():
        print(f"Objetivo {objetivo.nombre}...", flush=True)
        resultados.append(run_objetivo(weekly, objetivo))

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([r["resumen"] for r in resultados], ignore_index=True).to_csv(OUTPUT_SUMMARY, index=False)
    pd.concat(
        [r["universo"].assign(objetivo=r["objetivo"].nombre) for r in resultados], ignore_index=True
    ).to_csv(OUTPUT_UNIVERSE, index=False)
    OUTPUT_SELECTION.write_text(
        json.dumps({r["objetivo"].nombre: r["seleccion"] for r in resultados}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    OUTPUT_REPORT.write_text(render_report(resultados), encoding="utf-8", newline="\n")
    for r in resultados:
        print(r["objetivo"].nombre, "->", r["elegido"])


if __name__ == "__main__":
    main()
