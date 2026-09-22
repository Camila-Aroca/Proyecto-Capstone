"""Evaluacion del modelo seleccionado en el periodo posterior al entrenamiento (holdout).

**Que responde.** El benchmark eligio un modelo con el backtesting 2021-2025.
Esta etapa lo evalua en los anios que esa seleccion nunca vio y responde cuatro
preguntas, cada una con su evidencia:

1. Supera al baseline estacional fuera de muestra, y la diferencia es real?
2. Sus intervalos siguen calibrados?
3. Se degrado su desempeno respecto del backtesting?
4. Algun otro candidato lo habria hecho significativamente mejor?

**Seleccion congelada.** El modelo evaluado se lee de
`reports/modeling/benchmark_demanda_sm_seleccion.json` y se instancia desde el
registro unico (`src.models.registry`), de modo que se evalua exactamente la
configuracion elegida. Los resultados de esta etapa **no** vuelven a la
seleccion: si lo hicieran, el holdout dejaria de ser un holdout.

**Protocolo.** Origenes deslizantes con paso 1 desde el ultimo periodo de
entrenamiento hasta el ultimo que deja el horizonte maximo dentro de los datos.
En cada origen el modelo se reentrena con todo lo observado hasta ese momento,
incluido el propio holdout ya transcurrido, que es exactamente como operaria en
produccion. MASE usa la misma escala que el benchmark para que las cifras de
ambos periodos sean comparables.

Publica `reports/modeling/holdout_demanda_sm.md` y
`reports/modeling/holdout_demanda_sm_resumen.csv`. Toda cifra se calcula en
tiempo de ejecucion y las conclusiones se derivan de ellas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
import json
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.models.backtesting import (
    aggregate_by_level,
    build_origins,
    compute_mase_scales,
    prepare_supervised,
    rolling_origin_backtest,
)
from src.models.features import RM_SERIES_ID, TARGET, build_panel, load_weekly_mart
from src.models.holdout import holdout_years, load_holdout_weekly, snapshot_info
from src.models.metrics import coverage_tolerance, evaluate_predictions, paired_comparison
from src.models.registry import available_models, build_model

sys.stdout.reconfigure(encoding="utf-8")

SELECTION_PATH: Final[Path] = Path("reports/modeling/benchmark_demanda_sm_seleccion.json")
BENCHMARK_SUMMARY: Final[Path] = Path("reports/modeling/benchmark_demanda_sm_resumen.csv")
OUTPUT_REPORT: Final[Path] = Path("reports/modeling/holdout_demanda_sm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/modeling/holdout_demanda_sm_resumen.csv")

REFERENCIA: Final[str] = "baseline_estacional"
ALFA: Final[float] = 0.05
STEP: Final[int] = 1


def _tabla_md(frame: pd.DataFrame) -> str:
    """Convierte un DataFrame a tabla Markdown sin dependencias externas."""
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |"
        for fila in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([encabezado, separador, *filas])


# --------------------------------------------------------------------------
# Preparacion
# --------------------------------------------------------------------------

def load_selection(path: Path = SELECTION_PATH) -> dict:
    """Lee la seleccion congelada del benchmark y verifica que sea evaluable."""
    seleccion = json.loads(path.read_text(encoding="utf-8"))
    recomendado = seleccion["modelo_recomendado"]
    if recomendado not in available_models():
        raise ValueError(
            f"El modelo seleccionado '{recomendado}' no es construible desde el "
            "registro; no puede evaluarse en holdout tal como fue elegido."
        )
    return seleccion


def models_to_evaluate(recomendado: str) -> list[str]:
    """Baseline de referencia, todos los modelos conformes y el recomendado.

    Se evaluan todos los conformes del registro, no una seleccion a mano, para
    que la pregunta "habria ganado otro?" no dependa de a quien se invito. Los
    modelos no conformes comparten el pronostico puntual con su version conforme
    y ya fueron descartados por calibracion en el benchmark.
    """
    nombres = [REFERENCIA] + [n for n in available_models() if n.endswith("_conformal")]
    if recomendado not in nombres:
        nombres.append(recomendado)
    return nombres


def build_extended_panel(
    mart: pd.DataFrame, holdout: pd.DataFrame, seleccion: dict, horizontes: tuple[int, ...]
) -> tuple[pd.DataFrame, int]:
    """Panel de entrenamiento + holdout, con verificacion de alineacion temporal.

    El indice `t` del periodo de entrenamiento debe coincidir con el del
    benchmark: si no, las escalas MASE y los origenes no serian comparables. Se
    verifica contra los metadatos de la seleccion en vez de asumirlo.
    """
    panel = build_panel(pd.concat([mart, holdout[mart.columns]], ignore_index=True))
    ultimo_ano = seleccion["periodo_backtest"]["ano_max"]
    t_fin = int(panel.loc[panel["ano"] <= ultimo_ano, "t"].max())
    esperado = seleccion["periodo_backtest"]["t_ultimo_origen"] + max(horizontes)
    if t_fin != esperado:
        raise ValueError(
            f"El indice temporal no coincide con el benchmark: fin de entrenamiento "
            f"t={t_fin}, esperado t={esperado}."
        )
    return panel, t_fin


# --------------------------------------------------------------------------
# Metricas
# --------------------------------------------------------------------------

def _resumen_modelo(
    pred: pd.DataFrame, panel: pd.DataFrame, escalas: dict[str, float], nivel: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Metricas por serie y horizonte, y su agregacion por nivel."""
    por_serie = evaluate_predictions(pred, escalas, nivel)
    por_serie["modelo"] = pred["modelo"].iloc[0]
    return por_serie, aggregate_by_level(por_serie, panel)


def _por_nivel(pred: pd.DataFrame, agregado: pd.DataFrame, nivel_intervalo: float) -> dict:
    """Una fila de resultados: MASE promedio de horizontes y cobertura agrupada."""
    fila: dict[str, object] = {"modelo": pred["modelo"].iloc[0]}
    for nivel in ("region", "comuna"):
        sub = pred[pred["nivel"] == nivel]
        dentro = (sub["y_real"] >= sub["y_inferior"]) & (sub["y_real"] <= sub["y_superior"])
        cobertura = float(dentro.mean())
        tolerancia = coverage_tolerance(len(sub), nivel_intervalo)
        fila[f"mase_{nivel}"] = round(
            float(agregado.loc[agregado["nivel"] == nivel, "mase_mediano"].mean()), 4
        )
        fila[f"cobertura_{nivel}"] = round(cobertura, 4)
        fila[f"amplitud_{nivel}"] = round(float((sub["y_superior"] - sub["y_inferior"]).mean()), 2)
        fila[f"calibrado_{nivel}"] = bool(abs(cobertura - nivel_intervalo) <= tolerancia)
    fila["mase_promedio"] = round((fila["mase_region"] + fila["mase_comuna"]) / 2, 4)
    return fila


def _mase_backtest(modelo: str, panel: pd.DataFrame) -> dict[str, float]:
    """MASE del benchmark para un modelo, agregado igual que en el holdout."""
    resumen = pd.read_csv(BENCHMARK_SUMMARY, dtype={"series_id": str})
    resumen = resumen[resumen["modelo"] == modelo]
    niveles = panel[["series_id", "nivel"]].drop_duplicates()
    unido = resumen.merge(niveles, on="series_id", how="inner")
    por_horizonte = unido.groupby(["nivel", "horizonte"])["mase"].median()
    return {n: float(por_horizonte.loc[n].mean()) for n in ("region", "comuna")}


def _comunas(pred: pd.DataFrame) -> list[str]:
    return sorted(pred.loc[pred["nivel"] == "comuna", "series_id"].unique())


def compare(
    pred_a: pd.DataFrame, pred_b: pd.DataFrame, escalas: dict[str, float]
) -> dict[str, dict[str, float]]:
    """Prueba pareada por nivel: error de `b` relativo a `a`."""
    return {
        "region": paired_comparison(pred_a, pred_b, escalas, [RM_SERIES_ID]),
        "comuna": paired_comparison(pred_a, pred_b, escalas, _comunas(pred_a)),
    }


# --------------------------------------------------------------------------
# Lecturas derivadas
# --------------------------------------------------------------------------

def _lectura_vs_baseline(recomendado: str, pruebas: dict[str, dict[str, float]]) -> tuple[str, bool]:
    partes = []
    ganadas = 0
    for nivel, p in pruebas.items():
        significativa = p["p_valor"] < ALFA
        mejor = p["cambio_pct"] < 0
        ganadas += int(significativa and mejor)
        partes.append(
            f"- **{nivel}**: {p['cambio_pct']:+.2f}% de error frente al baseline "
            f"(mejor en {p['proporcion_b_mejor']:.1%} de {p['n']:,} pronosticos, "
            f"Wilcoxon p = {p['p_valor']:.4f}) -> "
            + (
                "mejora significativa."
                if significativa and mejor
                else "empeoramiento significativo."
                if significativa
                else "diferencia no significativa."
            )
        )
    supera = ganadas == len(pruebas)
    cierre = (
        f"**Inferencia:** `{recomendado}` supera al baseline estacional fuera de muestra "
        "en ambos niveles, con diferencias que no son atribuibles al azar."
        if supera
        else f"**Inferencia:** `{recomendado}` no supera al baseline de forma "
        "significativa en todos los niveles fuera de muestra; ver el detalle."
    )
    return "\n".join(partes) + "\n\n" + cierre, supera


def _lectura_calibracion(fila: dict, n_region: int, n_comuna: int, nivel: float) -> tuple[str, bool]:
    calibrado = fila["calibrado_region"] and fila["calibrado_comuna"]
    texto = (
        f"Cobertura observada: region {fila['cobertura_region']:.3f} "
        f"({n_region} evaluaciones, tolerancia +/-{coverage_tolerance(n_region, nivel):.3f}); "
        f"comunas {fila['cobertura_comuna']:.3f} ({n_comuna:,} evaluaciones, "
        f"tolerancia +/-{coverage_tolerance(n_comuna, nivel):.3f}). Nominal {nivel:.2f}.\n\n"
    )
    if calibrado:
        texto += (
            "**Hecho observado:** la cobertura es compatible con el nominal en ambos "
            "niveles fuera de muestra: la calibracion conforme se sostiene en datos que "
            "no participaron ni de la seleccion ni de la calibracion."
        )
    else:
        fallidos = [
            n for n in ("region", "comuna") if not fila[f"calibrado_{n}"]
        ]
        direccion = {
            n: ("sobrecubre (intervalos mas anchos de lo necesario)"
                if fila[f"cobertura_{n}"] > nivel
                else "subcubre (intervalos demasiado estrechos)")
            for n in fallidos
        }
        texto += "**Hecho observado:** la cobertura se aleja del nominal mas de lo que el azar explica en: " + "; ".join(
            f"{n}, que {d}" for n, d in direccion.items()
        ) + "."
    return texto, calibrado


def _lectura_degradacion(
    recomendado: str,
    mase_holdout: dict[str, float],
    mase_back: dict[str, float],
    ref_holdout: dict[str, float],
    ref_back: dict[str, float],
) -> tuple[pd.DataFrame, str]:
    """Compara backtest y holdout, en MASE y en habilidad sobre el baseline.

    El MASE crudo puede cambiar solo porque el periodo es mas facil o mas dificil
    de pronosticar. La habilidad (`1 - MASE_modelo / MASE_baseline` dentro del
    mismo periodo) controla por eso, y es la comparacion que importa.
    """
    filas = []
    for nivel in ("region", "comuna"):
        hab_back = 1 - mase_back[nivel] / ref_back[nivel]
        hab_hold = 1 - mase_holdout[nivel] / ref_holdout[nivel]
        filas.append(
            {
                "nivel": nivel,
                "mase_backtest": round(mase_back[nivel], 4),
                "mase_holdout": round(mase_holdout[nivel], 4),
                "mase_baseline_backtest": round(ref_back[nivel], 4),
                "mase_baseline_holdout": round(ref_holdout[nivel], 4),
                "habilidad_backtest_pct": round(hab_back * 100, 1),
                "habilidad_holdout_pct": round(hab_hold * 100, 1),
            }
        )
    tabla = pd.DataFrame(filas)
    cambios = (tabla["habilidad_holdout_pct"] - tabla["habilidad_backtest_pct"]).round(1)
    detalle = "; ".join(
        f"{n}: {c:+.1f} puntos" for n, c in zip(tabla["nivel"], cambios)
    )
    if (tabla["habilidad_holdout_pct"] > 0).all():
        juicio = (
            f"`{recomendado}` conserva ventaja sobre el baseline en ambos niveles fuera "
            f"de muestra. Cambio de habilidad respecto del backtest: {detalle}."
        )
    else:
        juicio = (
            f"`{recomendado}` pierde su ventaja sobre el baseline en al menos un nivel "
            f"fuera de muestra. Cambio de habilidad respecto del backtest: {detalle}."
        )
    texto = (
        "**Hecho observado:** " + juicio + "\n\n"
        "La habilidad se mide contra el baseline **dentro del mismo periodo**, de modo "
        "que un anio mas facil o mas dificil de pronosticar no se confunde con una "
        "mejora o un deterioro del modelo."
    )
    return tabla, texto


def _lectura_alternativas(
    recomendado: str, pruebas: dict[str, dict[str, dict[str, float]]]
) -> tuple[pd.DataFrame, str]:
    filas = []
    for alternativa, por_nivel in pruebas.items():
        for nivel, p in por_nivel.items():
            filas.append({"alternativa": alternativa, "nivel": nivel, **p})
    tabla = pd.DataFrame(filas)
    if tabla.empty:
        return tabla, "No hay otros candidatos para comparar."
    mejores = tabla[(tabla["p_valor"] < ALFA) & (tabla["cambio_pct"] < 0)]
    if mejores.empty:
        texto = (
            f"**Hecho observado:** ninguna alternativa supera a `{recomendado}` de forma "
            f"significativa (p < {ALFA}) en ningun nivel fuera de muestra. La seleccion "
            "hecha con el backtesting se sostiene."
        )
    else:
        texto = (
            "**Hecho observado:** alternativas significativamente mejores fuera de "
            "muestra: "
            + "; ".join(
                f"`{f.alternativa}` en {f.nivel} ({f.cambio_pct:+.2f}%, p = {f.p_valor:.4f})"
                for f in mejores.itertuples()
            )
            + ". La seleccion no se revisa aqui --el holdout no alimenta la seleccion--, "
            "pero el resultado debe considerarse en la proxima iteracion del benchmark."
        )
    return tabla, texto


def _lectura_universo(
    n_evaluables: int, n_benchmark: int, cobertura_incompleta: pd.DataFrame
) -> str:
    """Declara el universo de comunas y su efecto sobre la comparabilidad."""
    texto = (
        f"**Universo evaluado:** {n_evaluables} comunas con historia y cobertura "
        "completa. El total regional se define como la suma de ese mismo universo en "
        "todo el periodo, entrenamiento incluido, para que el target no cambie de "
        "definicion a mitad de la serie."
    )
    if n_evaluables != n_benchmark:
        excluido = float(cobertura_incompleta["share_referencia_pct"].sum())
        texto += (
            f" El benchmark usaba {n_benchmark} comunas; las excluidas aqui representaban "
            f"{excluido:.2f}% del volumen del ultimo anio de entrenamiento. Las cifras "
            "regionales de ambos informes son comparables con esa salvedad; las "
            "comunales se comparan sobre las mismas comunas."
        )
    return texto


# --------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------

def render_report(ctx: dict[str, object]) -> str:
    snap: pd.DataFrame = ctx["snapshot"]
    return f"""# Evaluacion en holdout del modelo de demanda de urgencia en salud mental

Reproducible mediante `python -m scripts.evaluate_holdout_demanda_sm`. Metricas
por serie y horizonte en
[`holdout_demanda_sm_resumen.csv`](holdout_demanda_sm_resumen.csv).

Corresponde a la fase de *Evaluation* (CRISP-DM). Evalua el modelo que eligio
[`benchmark_demanda_sm.md`](benchmark_demanda_sm.md) en un periodo que esa
seleccion nunca vio.

## 1. Veredicto

{ctx['veredicto']}

## 2. Protocolo

| Parametro | Valor |
|---|---|
| Modelo evaluado (seleccion congelada) | `{ctx['recomendado']}` |
| Periodo de seleccion (backtest) | {ctx['ano_min']}-{ctx['ano_max_train']} |
| Periodo holdout | {ctx['anos_holdout']} |
| Origenes | {ctx['n_origenes']} (paso {STEP}), t={ctx['origen_min']} a t={ctx['origen_max']} |
| Horizontes | {ctx['horizontes']} semanas |
| Evaluaciones por modelo | {ctx['n_region']} en la region, {ctx['n_comuna']:,} en comunas |
| Semanas holdout evaluadas | {ctx['semanas_objetivo']} |
| Modelos comparados | {ctx['modelos']} |

En cada origen el modelo se reentrena con todo lo observado hasta ese momento,
como operaria en produccion. Ninguna cifra de esta evaluacion se uso para elegir
el modelo. MASE usa la misma escala que el benchmark (historia previa a su primer
origen), de modo que ambos informes son comparables.

## 3. Snapshot evaluado

La fuente del anio en curso es mutable: DEIS la sobrescribe sin versionarla. Este
resultado corresponde exactamente a los archivos siguientes.

{_tabla_md(snap)}

Fecha maxima observada en la fuente: **{ctx['fecha_corte']}**.

{ctx['lectura_procedencia']}

## 4. Preparacion de los datos del holdout

El semanal comunal del holdout se construye con la misma carga y agregacion que
el mart de entrenamiento, y la poblacion con el mismo cuadro oficial INE.

**Semanas truncadas excluidas** (menos de 7 dias; tratadas como completas
parecerian una caida de demanda):

{_tabla_md(ctx['semanas_incompletas'])}

**Comunas sin historia de entrenamiento excluidas** (no son pronosticables: no
tienen rezagos ni identidad aprendida):

{_tabla_md(ctx['comunas_sin_historia'])}

**Comunas con historia pero cobertura incompleta en el holdout** (dejan de
tener filas para todas las causas: es ausencia de dato, no demanda cero, y no se
rellena):

{_tabla_md(ctx['comunas_cobertura_incompleta'])}

{ctx['lectura_universo']}

## 5. Resultados

{_tabla_md(ctx['tabla'])}

## 6. Supera al baseline fuera de muestra?

{ctx['lectura_baseline']}

## 7. Se sostiene la calibracion?

{ctx['lectura_calibracion']}

## 8. Se degrado respecto del backtest?

{_tabla_md(ctx['tabla_degradacion'])}

{ctx['lectura_degradacion']}

## 9. Habria ganado otro candidato?

Comparacion pareada de cada alternativa contra `{ctx['recomendado']}`
(`error_a` es el del recomendado, `error_b` el de la alternativa):

{_tabla_md(ctx['tabla_alternativas'])}

{ctx['lectura_alternativas']}

## 10. Detalle por horizonte del modelo evaluado

{_tabla_md(ctx['por_horizonte'])}

## 11. Limitaciones

- El holdout cubre {ctx['semanas_objetivo']} semanas de un solo anio: evidencia
  valida pero acotada, y sin un ciclo estacional completo.
- El snapshot del anio en curso puede cambiar retroactivamente; el resultado vale
  para los hashes de la seccion 3 y debe regenerarse si cambian.
- La comuna excluida por falta de historia no recibe pronostico: el producto debe
  mostrarla como "sin pronostico", nunca con cero.
- El target son **atenciones (eventos), no personas unicas**, y la demanda
  observada refleja utilizacion y oferta, no prevalencia.
"""


def main() -> None:
    inicio = time.perf_counter()
    seleccion = load_selection()
    recomendado = seleccion["modelo_recomendado"]
    nivel = float(seleccion["nivel_intervalo"])
    horizontes = tuple(int(h) for h in seleccion["horizontes"])

    print(f"Modelo seleccionado (congelado): {recomendado}", flush=True)
    mart = load_weekly_mart()
    ultimo_ano = int(seleccion["periodo_backtest"]["ano_max"])
    anos = holdout_years(ultimo_ano)
    if not anos:
        raise ValueError("No hay datos procesados posteriores al periodo de entrenamiento.")
    print(f"Anios de holdout: {anos}", flush=True)

    # Universo fijo: solo comunas con historia y cobertura completa en el holdout.
    # El total regional se define sobre ese universo tambien en el entrenamiento,
    # para que el target no cambie de definicion a mitad de la serie.
    referencia = (
        mart[mart["ano"] == ultimo_ano].groupby("comuna_codigo")[TARGET].sum()
    )
    holdout, diagnostico = load_holdout_weekly(anos, referencia)
    evaluables = set(holdout["comuna_codigo"])
    n_comunas_benchmark = int(mart["comuna_codigo"].nunique())
    mart = mart[mart["comuna_codigo"].isin(evaluables)]
    panel, t_fin = build_extended_panel(mart, holdout, seleccion, horizontes)
    snapshot = snapshot_info(anos)

    t_max = int(panel["t"].max())
    n_origenes = t_max - max(horizontes) - t_fin + 1
    if n_origenes < 1:
        raise ValueError("El holdout es mas corto que el horizonte maximo.")
    origenes = build_origins(panel, horizontes, n_origenes, STEP)
    escalas = compute_mase_scales(
        panel, hasta_t=int(seleccion["periodo_backtest"]["t_primer_origen"])
    )

    supervised = prepare_supervised(panel, horizontes)
    predicciones: dict[str, pd.DataFrame] = {}
    for nombre in models_to_evaluate(recomendado):
        t0 = time.perf_counter()
        predicciones[nombre] = rolling_origin_backtest(
            panel, build_model(nombre, nivel), horizontes, n_origenes, STEP,
            supervised=supervised,
        )
        print(f"  {nombre}: {len(predicciones[nombre])} predicciones "
              f"en {time.perf_counter() - t0:.1f}s", flush=True)

    # --- Metricas -----------------------------------------------------------
    por_serie, filas, agregados = [], [], {}
    for nombre, pred in predicciones.items():
        serie, agregado = _resumen_modelo(pred, panel, escalas, nivel)
        por_serie.append(serie)
        agregados[nombre] = agregado
        filas.append(_por_nivel(pred, agregado, nivel))
    tabla = pd.DataFrame(filas).sort_values("mase_promedio").reset_index(drop=True)
    fila_rec = tabla.set_index("modelo").loc[recomendado].to_dict()
    fila_rec["modelo"] = recomendado

    rec = predicciones[recomendado]
    n_region = int((rec["nivel"] == "region").sum())
    n_comuna = int((rec["nivel"] == "comuna").sum())

    lectura_baseline, supera = _lectura_vs_baseline(
        recomendado, compare(predicciones[REFERENCIA], rec, escalas)
    )
    lectura_calibracion, calibrado = _lectura_calibracion(fila_rec, n_region, n_comuna, nivel)

    mase_hold = {n: float(fila_rec[f"mase_{n}"]) for n in ("region", "comuna")}
    fila_ref = tabla.set_index("modelo").loc[REFERENCIA]
    ref_hold = {n: float(fila_ref[f"mase_{n}"]) for n in ("region", "comuna")}
    tabla_degradacion, lectura_degradacion = _lectura_degradacion(
        recomendado,
        mase_hold,
        _mase_backtest(recomendado, panel),
        ref_hold,
        _mase_backtest(REFERENCIA, panel),
    )
    conserva = bool((tabla_degradacion["habilidad_holdout_pct"] > 0).all())

    alternativas = {
        n: compare(rec, p, escalas)
        for n, p in predicciones.items()
        if n not in (recomendado, REFERENCIA)
    }
    tabla_alternativas, lectura_alternativas = _lectura_alternativas(recomendado, alternativas)
    sin_rival = tabla_alternativas.empty or tabla_alternativas[
        (tabla_alternativas["p_valor"] < ALFA) & (tabla_alternativas["cambio_pct"] < 0)
    ].empty

    criterios = {
        "supera al baseline con diferencia significativa en ambos niveles": supera,
        "intervalos calibrados en ambos niveles": calibrado,
        "conserva ventaja sobre el baseline respecto del backtest": conserva,
        "ninguna alternativa es significativamente mejor": sin_rival,
    }
    cumplidos = [c for c, ok in criterios.items() if ok]
    fallidos = [c for c, ok in criterios.items() if not ok]
    veredicto = (
        f"**La seleccion se sostiene fuera de muestra.** `{recomendado}` cumple los "
        f"{len(criterios)} criterios: " + "; ".join(cumplidos) + "."
        if not fallidos
        else f"**La seleccion se sostiene solo parcialmente.** `{recomendado}` cumple: "
        + ("; ".join(cumplidos) or "ninguno")
        + ". No cumple: " + "; ".join(fallidos) + ". Ver secciones 6 a 9."
    )

    lectura_procedencia = "\n".join(
        (
            f"- **{f.ano}**: el RAW coincide con el ultimo snapshot registrado en el "
            f"manifiesto de procedencia ({f.procedencia_registrada_en})."
            if f.estado_procedencia == "registrado"
            else f"- **{f.ano}**: el RAW **no tiene registro** en "
            "`data/raw/provenance_manifest.json`. Los hashes de esta tabla son la unica "
            "identificacion del snapshot evaluado. Registrar la procedencia corresponde a "
            "la etapa de ingesta, no a esta evaluacion."
            if f.estado_procedencia == "sin_registro"
            else f"- **{f.ano}**: estado de procedencia `{f.estado_procedencia}`; el RAW "
            "en disco no coincide con el ultimo snapshot registrado."
        )
        for f in snapshot.itertuples()
    )

    objetivos = rec[["t"]].drop_duplicates().merge(
        panel[["t", "ano", "semana"]].drop_duplicates(), on="t"
    )
    por_horizonte = agregados[recomendado][
        ["nivel", "horizonte", "mae_medio", "mase_mediano", "cobertura_media", "amplitud_media"]
    ]

    ctx = {
        "veredicto": veredicto,
        "recomendado": recomendado,
        "ano_min": int(mart["ano"].min()),
        "ano_max_train": ultimo_ano,
        "anos_holdout": ", ".join(str(a) for a in anos),
        "n_origenes": len(origenes),
        "origen_min": min(origenes),
        "origen_max": max(origenes),
        "horizontes": ", ".join(str(h) for h in horizontes),
        "n_region": n_region,
        "n_comuna": n_comuna,
        "semanas_objetivo": (
            f"{len(objetivos)} (semanas {objetivos['semana'].min()} a "
            f"{objetivos['semana'].max()} de {', '.join(str(a) for a in anos)})"
        ),
        "modelos": ", ".join(f"`{n}`" for n in predicciones),
        "snapshot": snapshot[
            ["ano", "raw_path", "raw_bytes", "raw_sha256", "procesado_sha256", "estado_procedencia"]
        ],
        "fecha_corte": diagnostico["fecha_corte"]["fecha_maxima"].iloc[0].date().isoformat(),
        "lectura_procedencia": lectura_procedencia,
        "semanas_incompletas": diagnostico["semanas_incompletas"],
        "comunas_sin_historia": diagnostico["comunas_sin_historia"],
        "comunas_cobertura_incompleta": diagnostico["comunas_cobertura_incompleta"],
        "lectura_universo": _lectura_universo(
            len(evaluables), n_comunas_benchmark, diagnostico["comunas_cobertura_incompleta"]
        ),
        "tabla": tabla[
            [
                "modelo", "mase_region", "mase_comuna", "cobertura_region",
                "cobertura_comuna", "amplitud_comuna", "calibrado_region", "calibrado_comuna",
            ]
        ],
        "lectura_baseline": lectura_baseline,
        "lectura_calibracion": lectura_calibracion,
        "tabla_degradacion": tabla_degradacion,
        "lectura_degradacion": lectura_degradacion,
        "tabla_alternativas": tabla_alternativas,
        "lectura_alternativas": lectura_alternativas,
        "por_horizonte": por_horizonte,
    }

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(por_serie, ignore_index=True).to_csv(OUTPUT_SUMMARY, index=False)
    OUTPUT_REPORT.write_text(render_report(ctx), encoding="utf-8")

    print()
    print(tabla.to_string(index=False))
    print(f"\n{veredicto}")
    print(f"\nInforme escrito en {OUTPUT_REPORT.as_posix()} "
          f"({time.perf_counter() - inicio:.0f}s)")


if __name__ == "__main__":
    main()
