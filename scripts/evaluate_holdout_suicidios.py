"""Evaluación en holdout del pronóstico semanal de suicidios.

El benchmark eligió el modelo con los años cerrados. Aquí se evalúa esa selección
congelada sobre las semanas completas del año en curso, que no vio, con el mismo
diseño que las evaluaciones en holdout del modelo de demanda: un origen por semana,
solo objetivos posteriores al entrenamiento y escalas de la historia previa al
primer origen del benchmark, para que holdout y backtest sean comparables.

Responde: ¿el elegido sigue superando al baseline?, ¿sus intervalos cubren lo que
declaran?, ¿conserva su habilidad?, ¿alguna alternativa es significativamente mejor?

Uso (vía pipeline): `python scripts/run_pipeline.py --stage evaluate_holdout_suicidios`
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from scripts.run_benchmark_suicidios import ALFA, OUTPUT_SUMMARY as BENCHMARK_SUMMARY, contrastes, correr_modelos, tabla_md
from src.data.raw_provenance import file_sha256
from src.models import suicidios as su
from src.models.backtesting import build_origins
from src.models.features import RM_SERIES_ID

OUTPUT_REPORT: Final[Path] = Path("reports/modeling/holdout_suicidios.md")
OUTPUT_SUMMARY: Final[Path] = su.RUTA_HOLDOUT_RESUMEN
TITULO: Final[str] = "# Evaluación en holdout del pronóstico semanal de suicidios (RM)"
PASO: Final[int] = 1
# Los modelos de boosting sin intervalo conforme no se reevalúan: el benchmark ya
# mostró que sus intervalos no están calibrados y su costo es el mayor del registro.
EXCLUIDOS: Final[frozenset[str]] = frozenset({"lightgbm_global", "poisson_glm_global"})


def modelos_a_evaluar(recomendado: str) -> list[str]:
    nombres = [n for n in su.available_models() if n not in EXCLUIDOS]
    if recomendado not in nombres:
        nombres.append(recomendado)
    return nombres


def lectura_rivales(rival: pd.DataFrame, recomendado: str) -> list[str]:
    """Texto sobre las alternativas significativamente mejores en el holdout, calculado desde la tabla."""
    if rival.empty:
        return ["Ninguna alternativa candidata tiene un error medio significativamente menor (Holm, 5%)."]
    detalle = "; ".join(
        f"`{f['alternativa']}` en {'la región' if f['nivel'] == 'region' else 'las comunas'} "
        f"({f['cambio del error frente al elegido (%)']}% de error, p Holm = {f['p_holm']})"
        for f in rival.to_dict("records"))
    return [
        f"**Alternativas con menor error medio significativo en el holdout:** {detalle}.",
        "",
        f"La selección congelada (`{recomendado}`) se mantiene: cambiarla después de ver el holdout usaría el "
        "año en curso para elegir, y este dejaría de ser una evaluación fuera de muestra. Un cambio debe validarse "
        "con semanas posteriores a este snapshot. El tamaño de la diferencia se lee junto a su p: con miles de "
        "pronósticos comunales, diferencias de décimas de punto porcentual resultan significativas sin ser "
        "relevantes.",
    ]


def rmsse_backtest(modelo: str, panel: pd.DataFrame) -> dict[str, float]:
    resumen = pd.read_csv(BENCHMARK_SUMMARY, dtype={"series_id": str})
    resumen = resumen[resumen["modelo"] == modelo].merge(panel[["series_id", "nivel"]].drop_duplicates(), on="series_id")
    por_h = resumen.groupby(["nivel", "horizonte"])["rmsse"].median()
    return {n: float(por_h.loc[n].mean()) for n in su.NIVELES}


def main() -> None:
    seleccion = su.cargar_seleccion()
    recomendado = seleccion["modelo_recomendado"]
    mart = su.load_mart()
    cierre = su.ultimo_ano_cerrado(mart)
    if cierre != int(seleccion["periodo_backtest"]["ano_max"]):
        raise ValueError(f"El último año cerrado ({cierre}) no es el del benchmark: ejecute `benchmark_suicidios`.")
    panel = su.build_panel(mart, int(seleccion["ano_inicio"]))
    t_fin = int(panel.loc[panel["ano"] <= cierre, "t"].max())
    esperado = int(seleccion["periodo_backtest"]["t_ultimo_origen"]) + max(su.HORIZONTES)
    if t_fin != esperado:
        raise ValueError(f"Índice temporal distinto del benchmark: fin t={t_fin}, esperado t={esperado}.")
    n_origenes = int(panel["t"].max()) - max(su.HORIZONTES) - t_fin + 1
    if n_origenes < 1:
        raise ValueError("El holdout es más corto que el horizonte máximo.")
    origenes = build_origins(panel, su.HORIZONTES, n_origenes, PASO)
    escala = su.escalas(panel, int(seleccion["periodo_backtest"]["t_primer_origen"]))
    predicciones, resumenes = correr_modelos(panel, modelos_a_evaluar(recomendado), n_origenes, PASO, escala,
                                             "holdout", desde_t=t_fin)
    tabla = su.tabla_modelos(predicciones, resumenes)
    comunas = sorted(set(panel["series_id"]) - {RM_SERIES_ID})
    series = {"region": [RM_SERIES_ID], su.NIVEL_COMUNA: comunas}
    vs_base = {n: su.comparacion_pareada(predicciones[su.REFERENCIA], predicciones[recomendado], escala, ids)
               for n, ids in series.items()}
    alternativas = contrastes(predicciones, recomendado, escala, series)
    fila, base = tabla.set_index("modelo").loc[recomendado], tabla.set_index("modelo").loc[su.REFERENCIA]
    back_rec, back_ref = rmsse_backtest(recomendado, panel), rmsse_backtest(su.REFERENCIA, panel)
    degradacion = pd.DataFrame([{
        "nivel": nv, "RMSSE backtest": round(back_rec[nv], 4), "RMSSE holdout": float(fila[f"rmsse_{nv}"]),
        "habilidad backtest (%)": round((1 - back_rec[nv] / back_ref[nv]) * 100, 1),
        "habilidad holdout (%)": round((1 - fila[f"rmsse_{nv}"] / base[f"rmsse_{nv}"]) * 100, 1),
    } for nv in su.NIVELES])
    candidatas = alternativas[~alternativas["alternativa"].isin(su.NO_CANDIDATOS)]
    rival = candidatas[(candidatas["p_holm"] < ALFA) & (candidatas["cambio del error frente al elegido (%)"] < 0)]
    criterios = {
        "supera al baseline con diferencia significativa en las comunas":
            vs_base[su.NIVEL_COMUNA]["p_valor"] < ALFA and vs_base[su.NIVEL_COMUNA]["cambio_pct"] < 0,
        "supera al baseline en RMSSE en la región": bool(fila["rmsse_region"] < base["rmsse_region"]),
        "conserva habilidad frente al baseline en ambos niveles": bool((degradacion["habilidad holdout (%)"] > 0).all()),
        "cobertura compatible con la declarada en ambos niveles":
            bool(fila["calibrado_region"] and fila[f"calibrado_{su.NIVEL_COMUNA}"]),
        "ninguna alternativa candidata es significativamente mejor (Holm)": rival.empty,
    }
    semanas = sorted(panel.loc[panel["t"] > t_fin, ["ano", "semana"]].drop_duplicates().itertuples(index=False))
    incompletas = mart.loc[~mart["registro_completo"], ["ano", "semana"]].drop_duplicates()
    columnas = ["modelo", "rmsse_region", "rmsse_comuna", "rmsse_promedio", "mase_region", "mase_comuna",
                "cobertura_region", "cobertura_esperada_region", "calibrado_region", "cobertura_comuna",
                "cobertura_esperada_comuna", "calibrado_comuna", "dispersion_pearson_region",
                "dispersion_pearson_comuna"]
    lineas = [
        TITULO, "",
        "Generado por `scripts/evaluate_holdout_suicidios.py` (stage `evaluate_holdout_suicidios`).", "",
        "## 1. Período y datos", "",
        f"- Modelo evaluado (selección congelada en `{su.RUTA_SELECCION.as_posix()}`): `{recomendado}`.",
        f"- Holdout: {len(semanas)} semanas completas de {cierre + 1} ({semanas[0][0]}-S{semanas[0][1]:02d} a "
        f"{semanas[-1][0]}-S{semanas[-1][1]:02d}); {n_origenes} orígenes semanales, horizontes 1-8, solo "
        "objetivos posteriores al entrenamiento.",
        "- Semanas excluidas por registro incompleto: "
        + (", ".join(f"{a}-S{s:02d}" for a, s in incompletas.itertuples(index=False)) or "ninguna") + ".",
        f"- Mart evaluado: `{su.MART_PATH.as_posix()}`, SHA256 `{file_sha256(su.MART_PATH)}`.", "",
        "## 2. Resultados", "", tabla_md(tabla[columnas]), "",
        "## 3. Criterios", "",
        *[f"- {'Sí' if ok else 'No'}: {texto}." for texto, ok in criterios.items()], "",
        f"Error cuadrático medio del elegido frente al baseline estacional (negativo = el elegido se equivoca "
        f"menos): región {vs_base['region']['cambio_pct']}% (Diebold-Mariano p = {vs_base['region']['p_valor']:.3g}; Wilcoxon p = "
        f"{vs_base['region']['p_wilcoxon']:.3g}), comunas {vs_base[su.NIVEL_COMUNA]['cambio_pct']}% (Diebold-Mariano "
        f"p = {vs_base[su.NIVEL_COMUNA]['p_valor']:.3g}; Wilcoxon p = {vs_base[su.NIVEL_COMUNA]['p_wilcoxon']:.3g}). "
        "Diebold-Mariano compara la pérdida media por origen (la de la regla de selección); Wilcoxon, el pronóstico "
        "típico. Los orígenes semanales comparten semanas objetivo: la varianza usa Newey-West.", "",
        "## 4. Backtest frente a holdout", "",
        "La habilidad se mide contra el baseline del mismo período, para no confundir un año más fácil o más "
        "difícil con un cambio del modelo.", "", tabla_md(degradacion), "",
        "## 5. Alternativas", "",
        "`cambio del error frente al elegido`: error cuadrático medio de la alternativa respecto del elegido "
        "(negativo = la alternativa se equivoca menos). `p_valor`: Diebold-Mariano por origen; `p_holm`: su ajuste "
        "de Holm por nivel; `p_wilcoxon`: pronóstico típico.", "", tabla_md(alternativas), "",
        *lectura_rivales(rival, recomendado), "",
        "## 6. Límites", "",
        "- La serie regional aporta un pronóstico por origen y horizonte; sus pruebas tienen poca potencia y los "
        "orígenes consecutivos comparten semanas objetivo (no son independientes).",
        "- El año en curso es un snapshot: las defunciones recientes pueden recodificarse o inscribirse después "
        "de este corte, y con un único snapshot no es posible medirlo.",
    ]
    OUTPUT_REPORT.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    pd.concat(resumenes.values(), ignore_index=True).to_csv(OUTPUT_SUMMARY, index=False)
    print(json.dumps({k: bool(v) for k, v in criterios.items()}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    if "--force" in sys.argv:
        sys.argv.remove("--force")
    main()
