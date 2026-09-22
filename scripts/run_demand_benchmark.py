"""Benchmark reproducible de modelos de demanda de urgencia en salud mental.

Ejecuta el backtesting con origenes deslizantes y compara, bajo exactamente el
mismo esquema de validacion:

**Panel de dos niveles (RM -> comunas)**

- `baseline_estacional`: repite el mismo periodo del anio anterior. Referencia
  obligatoria del alcance del proyecto.
- `baseline_estacional_drift`: el anterior corregido por la deriva interanual.
- `poisson_glm_global`: GLM de Poisson sobre las mismas features. Es la
  **ablacion** que obliga a los modelos complejos a justificar su costo.
- `lightgbm_global`: modelo global multi-serie de boosting.
- `lightgbm_global_bottom_up` / `_top_down`: el anterior reconciliado.
- `hibrido_glm_region_lgbm_comuna`: region del GLM, detalle del boosting,
  reconciliados top-down.
- Variantes `*_conformal`: los tres modelos anteriores con intervalos de
  prediccion conforme en lugar de sus intervalos propios.

**Panel de tres niveles (RM -> Servicio de Salud -> comunas)**

- `hibrido_3niveles_*`: el mismo hibrido sobre la jerarquia con Servicios de
  Salud, con reconciliacion top-down, middle-out y WLS estructural.

Publica `reports/modeling/benchmark_demanda_sm.md` y
`reports/modeling/benchmark_demanda_sm_resumen.csv`. Todas las cifras se
calculan en tiempo de ejecucion y la prosa se construye desde esos valores:
las conclusiones son condicionales a los resultados, no afirmaciones fijas.
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

import numpy as np
import pandas as pd

from src.models import RANDOM_SEED
from src.models.backtesting import (
    DemandModel,
    aggregate_by_level,
    build_origins,
    compute_mase_scales,
    prepare_supervised,
    rolling_origin_backtest,
    summarize_backtest,
)
from src.models.features import (
    RM_SERIES_ID,
    build_panel,
    load_servicio_map,
    load_weekly_mart,
)
from src.models.gradient_boosting import LightGBMGlobal
from src.models.hierarchy import (
    reconcile_bottom_up,
    reconcile_top_down,
    reconciliation_report,
)
from src.models.hybrid import reconcile_combined_backtest
from src.models.linear_glm import PoissonGLMGlobal
from src.models.metrics import coverage_tolerance, paired_comparison
from src.models.registry import HIBRIDO, available_models, build_model

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_REPORT: Final[Path] = Path("reports/modeling/benchmark_demanda_sm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/modeling/benchmark_demanda_sm_resumen.csv")
# Seleccion congelada en formato legible por maquina: la evaluacion en holdout
# y la API la leen para instanciar exactamente el modelo elegido aqui.
OUTPUT_SELECTION: Final[Path] = Path("reports/modeling/benchmark_demanda_sm_seleccion.json")

HORIZONS: Final[tuple[int, ...]] = (4, 5, 6, 7, 8)
N_ORIGINS: Final[int] = 13
STEP: Final[int] = 4
NIVEL_INTERVALO: Final[float] = 0.80
# Umbral de significancia para declarar que una diferencia no es azar.
ALFA: Final[float] = 0.05

REFERENCIA: Final[str] = "baseline_estacional"
PARES_CONFORMES: Final[tuple[tuple[str, str], ...]] = (
    ("poisson_glm_global", "poisson_glm_global_conformal"),
    ("lightgbm_global", "lightgbm_global_conformal"),
    (HIBRIDO, f"{HIBRIDO}_conformal"),
)
RECONCILIACIONES_3N: Final[tuple[str, ...]] = ("top_down", "middle_out", "wls_structural")


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
# Ejecucion de los backtests
# --------------------------------------------------------------------------

def _backtest(
    panel: pd.DataFrame, modelo: DemandModel, supervised: dict[int, pd.DataFrame]
) -> pd.DataFrame:
    inicio = time.perf_counter()
    resultado = rolling_origin_backtest(
        panel, modelo, HORIZONS, N_ORIGINS, STEP, supervised=supervised
    )
    print(f"  {modelo.name}: {len(resultado)} predicciones "
          f"en {time.perf_counter() - inicio:.1f}s", flush=True)
    return resultado


def run_backtests_dos_niveles(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Modelos sobre la jerarquia RM -> comunas, instanciados desde el registro.

    El registro incluye las variantes conformes: mismo modelo, intervalos
    conformes. El pronostico puntual no cambia, de modo que cualquier diferencia
    entre un modelo y su version conforme se debe solo a los intervalos.
    """
    supervised = prepare_supervised(panel, HORIZONS)
    modelos = [build_model(nombre, NIVEL_INTERVALO) for nombre in available_models()]
    predicciones = {m.name: _backtest(panel, m, supervised) for m in modelos}

    # Las variantes reconciliadas no reentrenan: transforman predicciones ya
    # obtenidas, de modo que la comparacion aisla el efecto de la reconciliacion.
    base = predicciones["lightgbm_global"]
    for nombre, funcion in (
        ("lightgbm_global_bottom_up", reconcile_bottom_up),
        ("lightgbm_global_top_down", reconcile_top_down),
    ):
        variante = funcion(base)
        variante["modelo"] = nombre
        predicciones[nombre] = variante
    return predicciones


def run_backtests_tres_niveles(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Hibrido sobre la jerarquia RM -> Servicio de Salud -> comunas.

    Se ejecutan una vez el GLM y el boosting sobre el panel de tres niveles y los
    hibridos se construyen combinando esas predicciones: como ambos modelos son
    deterministas, el resultado es identico a reentrenar cada hibrido.
    """
    supervised = prepare_supervised(panel, HORIZONS)
    glm = _backtest(panel, PoissonGLMGlobal(nivel=NIVEL_INTERVALO), supervised)
    lgbm = _backtest(
        panel, LightGBMGlobal(nivel=NIVEL_INTERVALO, seed=RANDOM_SEED), supervised
    )
    return {
        f"hibrido_3niveles_{rec}": reconcile_combined_backtest(
            glm, lgbm, rec, f"hibrido_3niveles_{rec}"
        )
        for rec in RECONCILIACIONES_3N
    }


# --------------------------------------------------------------------------
# Resumenes
# --------------------------------------------------------------------------

def _cobertura_y_amplitud(pred: pd.DataFrame) -> pd.DataFrame:
    """Cobertura, amplitud y numero de evaluaciones por nivel, sobre todas las filas."""
    frame = pred.copy()
    frame["dentro"] = (frame["y_real"] >= frame["y_inferior"]) & (
        frame["y_real"] <= frame["y_superior"]
    )
    frame["amplitud"] = frame["y_superior"] - frame["y_inferior"]
    return frame.groupby("nivel").agg(
        cobertura=("dentro", "mean"), amplitud=("amplitud", "mean"), n=("dentro", "size")
    )


def build_model_table(
    predicciones: dict[str, pd.DataFrame],
    paneles: dict[str, pd.DataFrame],
    por_nivel: pd.DataFrame,
) -> pd.DataFrame:
    """Una fila por modelo, promediando horizontes, con la marca de calibracion.

    Un nivel se considera **calibrado** si su cobertura observada cae dentro de
    la tolerancia muestral alrededor del nominal (`coverage_tolerance`): asi no
    se castiga a un modelo por una desviacion que el azar explica, ni se premia
    a uno que casualmente acierta el nominal con pocas evaluaciones.
    """
    mase = por_nivel.pivot_table(
        index="modelo", columns="nivel", values="mase_mediano", aggfunc="mean"
    )
    filas: list[dict[str, object]] = []
    for nombre, pred in predicciones.items():
        cobertura = _cobertura_y_amplitud(pred)
        fila: dict[str, object] = {
            "modelo": nombre,
            "niveles": 3 if (paneles[nombre]["nivel"] == "servicio").any() else 2,
        }
        for nivel in ("region", "servicio", "comuna"):
            fila[f"mase_{nivel}"] = (
                round(float(mase.loc[nombre, nivel]), 4)
                if nivel in mase.columns and pd.notna(mase.loc[nombre, nivel])
                else np.nan
            )
        for nivel in ("region", "comuna"):
            fila[f"cobertura_{nivel}"] = round(float(cobertura.loc[nivel, "cobertura"]), 4)
            fila[f"amplitud_{nivel}"] = round(float(cobertura.loc[nivel, "amplitud"]), 2)
            tolerancia = coverage_tolerance(int(cobertura.loc[nivel, "n"]), NIVEL_INTERVALO)
            fila[f"calibrado_{nivel}"] = bool(
                abs(cobertura.loc[nivel, "cobertura"] - NIVEL_INTERVALO) <= tolerancia
            )
        fila["mase_promedio"] = round((fila["mase_region"] + fila["mase_comuna"]) / 2, 4)
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("mase_promedio").reset_index(drop=True)


# --------------------------------------------------------------------------
# Lecturas derivadas
# --------------------------------------------------------------------------

def _veredicto_p(p: float) -> str:
    return "significativa" if p < ALFA else "no significativa"


def conformal_effect(
    predicciones: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, str]:
    """Compara cada modelo con su version conforme: mismo punto, otro intervalo."""
    filas: list[dict[str, object]] = []
    for base, conforme in PARES_CONFORMES:
        antes = _cobertura_y_amplitud(predicciones[base])
        despues = _cobertura_y_amplitud(predicciones[conforme])
        clave = ["origen", "horizonte", "series_id"]
        puntos = predicciones[base].set_index(clave)["y_pred"].sub(
            predicciones[conforme].set_index(clave)["y_pred"]
        )
        for nivel in ("region", "comuna"):
            filas.append(
                {
                    "modelo": base,
                    "nivel": nivel,
                    "cobertura_propia": round(float(antes.loc[nivel, "cobertura"]), 4),
                    "cobertura_conforme": round(float(despues.loc[nivel, "cobertura"]), 4),
                    "amplitud_propia": round(float(antes.loc[nivel, "amplitud"]), 2),
                    "amplitud_conforme": round(float(despues.loc[nivel, "amplitud"]), 2),
                    "cambio_amplitud_pct": round(
                        (despues.loc[nivel, "amplitud"] / antes.loc[nivel, "amplitud"] - 1)
                        * 100,
                        1,
                    ),
                    "max_dif_pronostico": round(float(puntos.abs().max()), 6),
                }
            )
    tabla = pd.DataFrame(filas)

    comunas = tabla[tabla["nivel"] == "comuna"]
    error_antes = (comunas["cobertura_propia"] - NIVEL_INTERVALO).abs()
    error_despues = (comunas["cobertura_conforme"] - NIVEL_INTERVALO).abs()
    mejoran = int((error_despues < error_antes).sum())
    mas_angostos = int((comunas["cambio_amplitud_pct"] < 0).sum())
    puntos_identicos = bool((tabla["max_dif_pronostico"] == 0).all())
    lectura = (
        f"**Hecho observado:** a nivel comunal, la prediccion conforme acerca la "
        f"cobertura al nominal en {mejoran} de {len(comunas)} modelos (error medio de "
        f"cobertura {error_antes.mean():.4f} -> {error_despues.mean():.4f}) y produce "
        f"intervalos mas angostos en {mas_angostos} de {len(comunas)}. "
        + (
            "El pronostico puntual es identico al del modelo base en todos los casos "
            "(diferencia maxima 0), de modo que el efecto se debe exclusivamente al "
            "intervalo."
            if puntos_identicos
            else "Hay diferencias en el pronostico puntual respecto del modelo base, "
            "lo que no deberia ocurrir y debe revisarse."
        )
        + "\n\n**Inferencia:** los intervalos propios de cada modelo fallaban por la "
        "forma, no solo por el ancho: repartian mal la amplitud entre comunas de "
        "distinta escala. La normalizacion conforme corrige esa reparticion y por "
        "eso puede mejorar la cobertura sin ensanchar el intervalo."
    )
    return tabla, lectura


def servicio_effect(
    predicciones: dict[str, pd.DataFrame], escalas: dict[str, float]
) -> tuple[pd.DataFrame, str]:
    """Compara cada hibrido de tres niveles con el hibrido de dos niveles.

    La comparacion es pareada sobre los mismos pronosticos de la region y de las
    comunas, que existen identicos en ambos paneles.
    """
    referencia = predicciones[HIBRIDO]
    comunas = sorted(
        referencia.loc[referencia["nivel"] == "comuna", "series_id"].unique()
    )
    filas: list[dict[str, object]] = []
    for rec in RECONCILIACIONES_3N:
        candidato = predicciones[f"hibrido_3niveles_{rec}"]
        for nivel, series in (("region", [RM_SERIES_ID]), ("comuna", comunas)):
            prueba = paired_comparison(referencia, candidato, escalas, series)
            filas.append({"reconciliacion": rec, "nivel": nivel, **prueba})
    tabla = pd.DataFrame(filas)

    significativas = tabla[(tabla["p_valor"] < ALFA) & (tabla["cambio_pct"] < 0)]
    peores = tabla[(tabla["p_valor"] < ALFA) & (tabla["cambio_pct"] > 0)]
    mejor = tabla.loc[tabla["cambio_pct"].idxmin()]
    if significativas.empty:
        conclusion = (
            "**Inferencia:** ninguna reconciliacion de tres niveles mejora de forma "
            f"estadisticamente significativa (p < {ALFA}) al hibrido de dos niveles. "
            f"La mayor reduccion de error promedio es `{mejor['reconciliacion']}` en "
            f"{mejor['nivel']} ({mejor['cambio_pct']:+.2f}%, p = {mejor['p_valor']:.3f}), "
            "compatible con el azar."
        )
    else:
        detalle = "; ".join(
            f"`{f.reconciliacion}` en {f.nivel} ({f.cambio_pct:+.2f}%, "
            f"p = {f.p_valor:.3f}, mejor en {f.proporcion_b_mejor:.1%} de los pronosticos)"
            for f in significativas.itertuples()
        )
        conclusion = (
            f"**Hecho observado:** mejoras significativas (p < {ALFA}): {detalle}. "
            "Todas las demas diferencias son compatibles con el azar."
        )
    if not peores.empty:
        conclusion += " Empeoramientos significativos: " + "; ".join(
            f"`{f.reconciliacion}` en {f.nivel} ({f.cambio_pct:+.2f}%)"
            for f in peores.itertuples()
        ) + "."
    conclusion += (
        "\n\n**Por que la media y la proporcion pueden discrepar:** una reconciliacion "
        "puede bajar el error **promedio** y aun asi ser peor en la mayoria de los "
        "pronosticos, si corrige unos pocos errores grandes. Por eso se reporta la "
        "proporcion de pronosticos en que gana y una prueba sobre rangos, no solo el "
        "promedio."
    )
    return tabla, conclusion


def select_model(
    tabla: pd.DataFrame,
    predicciones: dict[str, pd.DataFrame],
    escalas: dict[str, float],
) -> tuple[str, str]:
    """Regla de seleccion que respeta la incertidumbre de ambos criterios.

    1. Candidatos: modelos que no son baseline y superan su MASE promedio.
    2. Entre ellos, los **calibrados**: cobertura compatible con el nominal en
       region y en comunas, segun la tolerancia muestral.
    3. Se recomienda el calibrado de menor MASE promedio.
    4. Si existe un candidato mas preciso pero no calibrado, se prueba si su
       ventaja de precision es estadisticamente significativa. Solo una ventaja
       significativa justificaria discutir el intercambio.
    """
    referencia = tabla.loc[tabla["modelo"] == REFERENCIA, "mase_promedio"]
    umbral = float(referencia.iloc[0]) if not referencia.empty else float("inf")
    # El orden se fija aqui y no se asume del llamador: la regla depende de el.
    candidatos = tabla[
        (~tabla["modelo"].str.startswith("baseline")) & (tabla["mase_promedio"] < umbral)
    ].sort_values("mase_promedio", kind="stable")
    if candidatos.empty:
        return REFERENCIA, (
            "**Hecho observado:** ningun modelo supera al baseline estacional en MASE "
            "promedio. La referencia sigue siendo la mejor opcion disponible."
        )

    calibrados = candidatos[candidatos["calibrado_region"] & candidatos["calibrado_comuna"]]
    mas_preciso = candidatos.iloc[0]
    if calibrados.empty:
        return str(mas_preciso["modelo"]), (
            f"**Hecho observado:** ninguno de los {len(candidatos)} modelos que superan "
            "al baseline tiene cobertura compatible con el nominal en ambos niveles. "
            f"Se recomienda el mas preciso, `{mas_preciso['modelo']}`, declarando que "
            "sus intervalos no estan calibrados."
        )

    elegido = calibrados.iloc[0]
    texto = (
        f"**Recomendacion:** `{elegido['modelo']}`. De los {len(candidatos)} modelos "
        f"que superan al baseline, {len(calibrados)} tienen cobertura compatible con el "
        f"nominal en ambos niveles, y este es el de menor MASE promedio "
        f"({elegido['mase_promedio']:.4f}; region {elegido['mase_region']:.4f}, "
        f"comunas {elegido['mase_comuna']:.4f}; cobertura region "
        f"{elegido['cobertura_region']:.3f}, comunas {elegido['cobertura_comuna']:.3f})."
    )
    if mas_preciso["modelo"] != elegido["modelo"]:
        comunas = sorted(
            predicciones[elegido["modelo"]]
            .loc[lambda d: d["nivel"] == "comuna", "series_id"]
            .unique()
        )
        pruebas = {
            nivel: paired_comparison(
                predicciones[elegido["modelo"]],
                predicciones[str(mas_preciso["modelo"])],
                escalas,
                series,
            )
            for nivel, series in (("region", [RM_SERIES_ID]), ("comuna", comunas))
        }
        ventaja_real = [
            n for n, p in pruebas.items() if p["p_valor"] < ALFA and p["cambio_pct"] < 0
        ]
        detalle = "; ".join(
            f"{n}: {p['cambio_pct']:+.2f}% de error, p = {p['p_valor']:.3f}"
            for n, p in pruebas.items()
        )
        texto += (
            f"\n\n`{mas_preciso['modelo']}` tiene menor MASE promedio "
            f"({mas_preciso['mase_promedio']:.4f}) pero sus intervalos no estan "
            f"calibrados. Frente al recomendado: {detalle}. "
            + (
                "Su ventaja es significativa en "
                + ", ".join(ventaja_real)
                + ": existe un intercambio real entre precision y calibracion que el "
                "equipo debe resolver."
                if ventaja_real
                else "Su ventaja de precision no es estadisticamente distinguible del "
                "azar en ningun nivel, de modo que no compensa la perdida de "
                "calibracion."
            )
        )
    return str(elegido["modelo"]), texto


# --------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------

def render_report(ctx: dict[str, object]) -> str:
    """Construye el informe Markdown desde valores ya calculados."""
    tabla: pd.DataFrame = ctx["tabla_modelos"]
    columnas_resumen = [
        "modelo", "niveles", "mase_region", "mase_servicio", "mase_comuna",
        "cobertura_region", "cobertura_comuna", "amplitud_comuna",
        "calibrado_region", "calibrado_comuna",
    ]
    return f"""# Benchmark de modelos de demanda de urgencia en salud mental (RM)

Reproducible mediante `python -m scripts.run_demand_benchmark`. Metricas por
serie y horizonte en
[`benchmark_demanda_sm_resumen.csv`](benchmark_demanda_sm_resumen.csv).

Corresponde a las fases de *Modeling* y *Evaluation* (CRISP-DM). El
entendimiento de los datos que lo sustenta esta en
[`../eda/eda_series_demanda_sm.md`](../eda/eda_series_demanda_sm.md).

## 1. Diseno experimental

| Parametro | Valor |
|---|---|
| Panel de dos niveles | {ctx['n_series']} series ({ctx['n_comunas']} comunas + agregado RM) |
| Panel de tres niveles | {ctx['n_series_3n']} series (agrega {ctx['n_servicios']} Servicios de Salud) |
| Periodos | {ctx['n_periodos']} semanas regulares, {ctx['ano_min']}-{ctx['ano_max']} |
| Target | `atenciones_id36` (conteo, ID37 incluido) |
| Horizontes | {', '.join(str(h) for h in HORIZONS)} semanas |
| Origenes de pronostico | {ctx['n_origenes']} (paso {STEP}), de t={ctx['origen_min']} a t={ctx['origen_max']} |
| Evaluaciones por modelo | {ctx['n_eval_region']} en la region, {ctx['n_eval_comuna']:,} en comunas |
| Nivel de los intervalos | {int(NIVEL_INTERVALO * 100)}% |
| Semilla | {RANDOM_SEED} |

**Estrategia directa, sin fuga temporal.** Para pronosticar `y[t]` a horizonte
`h`, la matriz de features solo contiene valores observados hasta `t - h`. El
modelo se reentrena en cada origen usando exclusivamente `t <= origen`.

**MASE** es la metrica principal: escala el error por el del baseline
estacional calculado sobre la historia previa al primer origen. MASE < 1
significa superar a esa referencia. Se prefiere sobre MAPE porque hay comunas
con semanas en cero, donde MAPE es indefinido.

**Calibracion.** Un nivel se marca calibrado si su cobertura observada cae a
menos de {ctx['tol_region']:.4f} del nominal en la region ({ctx['n_eval_region']}
evaluaciones) y a menos de {ctx['tol_comuna']:.4f} en comunas
({ctx['n_eval_comuna']:,}): la distancia que el azar explica al 95%. La tolerancia
supone evaluaciones independientes; como las comunas comparten origenes, la
real es algo mayor y la marca de comunas es por lo tanto exigente.

## 2. Resultados por modelo

Promedio de los {len(HORIZONS)} horizontes. Ordenado por MASE promedio entre
region y comunas.

{_tabla_md(tabla[columnas_resumen])}

## 3. Lectura

{ctx['lectura']}

## 4. Prediccion conforme frente a jerarquia por Servicio de Salud

Las dos propuestas atacan problemas distintos: la prediccion conforme apunta a
la **calibracion de los intervalos**; la jerarquia por Servicio apunta a la
**precision del pronostico puntual** via una reconciliacion con un nivel
intermedio. Se evalua cada una contra su propio objetivo.

### 4.1 Prediccion conforme

Cada modelo contra su version conforme, que conserva el pronostico puntual y
reemplaza el intervalo:

{_tabla_md(ctx['tabla_conforme'])}

{ctx['lectura_conforme']}

### 4.2 Jerarquia por Servicio de Salud

Cada comuna se asigna al Servicio con mas establecimientos del maestro ubicados
en ella (el maestro no trae la pertenencia de la comuna, solo la de cada
establecimiento). Comunas por Servicio:

{_tabla_md(ctx['tabla_servicios'])}

Comunas con establecimientos de mas de un Servicio (se asignan al mayoritario):

{_tabla_md(ctx['tabla_mixtas'])}

Comparacion pareada de cada hibrido de tres niveles contra el hibrido de dos
niveles (`{HIBRIDO}`), sobre los mismos pronosticos. `error_a` es el de dos
niveles, `error_b` el de tres; `proporcion_b_mejor` es la fraccion de
pronosticos en que tres niveles tiene menor error; prueba de Wilcoxon pareada.

{_tabla_md(ctx['tabla_servicio'])}

{ctx['lectura_servicio']}

## 5. Seleccion del modelo

{ctx['seleccion']}

## 6. Coherencia jerarquica

Sin reconciliar, el pronostico regional de `lightgbm_global` y la suma de sus
pronosticos comunales no coinciden:

{_tabla_md(ctx['brecha'])}

Publicar ambos niveles sin reconciliar mostraria cifras que no cuadran entre el
indicador regional y el mapa comunal; por eso todos los hibridos reconcilian.

## 7. Que pesa en el modelo global

Importancia por ganancia del ultimo ajuste de `lightgbm_global`:

{_tabla_md(ctx['importancias'])}

{ctx['lectura_importancias']}

## 8. Limitaciones

- El target son **atenciones (eventos), no personas unicas**.
- Cobertura de {ctx['n_comunas']} de las 52 comunas RM: Vitacura (`13132`) no
  tiene registros en el mart y no se imputa.
- La pertenencia de cada comuna a un Servicio de Salud se **aproxima** por la
  mayoria de sus establecimientos; no es un dato explicito de la fuente.
- La garantia de la prediccion conforme supone intercambiabilidad entre la
  ventana de calibracion y el pronostico; con tendencia se cumple solo
  aproximadamente, por eso la cobertura se mide y no se da por garantizada.
- Los hiperparametros no se optimizaron por busqueda automatica: las cifras son
  un piso del desempeno alcanzable, no un techo.
- {ctx['n_origenes']} origenes dan {ctx['n_eval_region']} evaluaciones de la serie
  regional: suficientes para detectar diferencias grandes, no pequenas.
- No se evalua todavia contra 2026: ese holdout requiere fijar el snapshot
  mutable del anio en curso por SHA256 antes de usarlo.
- No se implementa MinT con covarianza completa: con {ctx['n_origenes']} origenes
  la matriz de covarianza entre {ctx['n_series_3n']} series seria inestable. La
  reconciliacion WLS estructural es la variante que no la requiere.
- La demanda observada refleja utilizacion y oferta instalada, no prevalencia ni
  necesidad sanitaria de la poblacion residente.
"""


def main() -> None:
    """Ejecuta el benchmark completo y publica informe y resumen."""
    print("Cargando paneles...", flush=True)
    weekly = load_weekly_mart()
    servicio_map = load_servicio_map()
    panel = build_panel(weekly)
    panel_3n = build_panel(weekly, servicio_map=servicio_map)
    origenes = build_origins(panel, HORIZONS, N_ORIGINS, STEP)
    escalas = compute_mase_scales(panel, hasta_t=min(origenes))

    print("Backtesting, panel de dos niveles...", flush=True)
    predicciones = run_backtests_dos_niveles(panel)
    print("Backtesting, panel de tres niveles...", flush=True)
    predicciones_3n = run_backtests_tres_niveles(panel_3n)

    paneles = {n: panel for n in predicciones} | {n: panel_3n for n in predicciones_3n}
    predicciones = predicciones | predicciones_3n

    resumenes = []
    for nombre, pred in predicciones.items():
        resumen = summarize_backtest(
            pred, paneles[nombre], HORIZONS, N_ORIGINS, STEP, NIVEL_INTERVALO
        )
        resumen["modelo"] = nombre
        resumenes.append(resumen)
    por_serie = pd.concat(resumenes, ignore_index=True)
    por_nivel = pd.concat(
        [aggregate_by_level(r, paneles[r["modelo"].iloc[0]]) for r in resumenes],
        ignore_index=True,
    )
    tabla = build_model_table(predicciones, paneles, por_nivel)

    # --- Lectura general ---------------------------------------------------
    base = tabla[tabla["modelo"] == REFERENCIA].iloc[0]
    candidatos = tabla[~tabla["modelo"].str.startswith("baseline")]

    def _mejores(columna: str) -> tuple[list[str], float]:
        """Todos los modelos empatados en el minimo, no uno elegido al azar.

        Las variantes conformes y reconciliadas comparten el pronostico de su
        modelo base en algunos niveles, de modo que los empates exactos son
        esperables y elegir uno solo sugeriria una ventaja que no existe.
        """
        minimo = float(candidatos[columna].min())
        empatados = candidatos.loc[np.isclose(candidatos[columna], minimo), "modelo"]
        return sorted(empatados), minimo

    mejores_region, mase_region = _mejores("mase_region")
    mejores_comuna, mase_comuna = _mejores("mase_comuna")
    mejora_region = (1 - mase_region / base["mase_region"]) * 100
    mejora_comuna = (1 - mase_comuna / base["mase_comuna"]) * 100
    por_horizonte = por_nivel[por_nivel["modelo"].isin(mejores_region + mejores_comuna)]
    supera_siempre = bool((por_horizonte["mase_mediano"] < 1).all())

    def _nombres(modelos: list[str]) -> str:
        texto = ", ".join(f"`{m}`" for m in modelos)
        return texto if len(modelos) == 1 else f"{texto} (empatados: mismo pronostico)"

    lectura = (
        f"**Mejor en la region:** {_nombres(mejores_region)}, MASE {mase_region:.4f} "
        f"frente a {base['mase_region']:.4f} del baseline ({mejora_region:.1f}% menos "
        f"error).\n\n"
        f"**Mejor en comunas:** {_nombres(mejores_comuna)}, MASE {mase_comuna:.4f} "
        f"frente a {base['mase_comuna']:.4f} del baseline ({mejora_comuna:.1f}% menos "
        f"error).\n\n"
        + (
            "Todos ellos tienen MASE mediano menor que 1 en todos los horizontes y "
            "niveles evaluados."
            if supera_siempre
            else "Al menos una combinacion de nivel y horizonte de estos modelos queda "
            "con MASE mediano igual o mayor que 1."
        )
        + " Que un modelo gane en un nivel no implica que la diferencia con el "
        "segundo sea significativa: eso se prueba en las secciones 4 y 5."
    )

    tabla_conforme, lectura_conforme = conformal_effect(predicciones)
    tabla_servicio, lectura_servicio = servicio_effect(predicciones, escalas)
    recomendado, seleccion = select_model(tabla, predicciones, escalas)

    comunas_panel = set(panel.loc[panel["nivel"] == "comuna", "series_id"])
    en_panel = servicio_map[servicio_map["comuna_codigo"].isin(comunas_panel)]
    tabla_servicios = (
        en_panel.groupby(["servicio_id", "servicio_glosa"], as_index=False)
        .size()
        .rename(columns={"size": "comunas"})
        .sort_values("comunas", ascending=False)
    )
    tabla_mixtas = en_panel[en_panel["servicios_en_comuna"] > 1][
        ["comuna_codigo", "servicio_id", "participacion", "servicios_en_comuna"]
    ].round({"participacion": 3})

    # --- Diagnosticos del modelo global -------------------------------------
    brecha = reconciliation_report(predicciones["lightgbm_global"])
    modelo_global = LightGBMGlobal(nivel=NIVEL_INTERVALO, seed=RANDOM_SEED)
    supervised = prepare_supervised(panel, (max(HORIZONS),))
    modelo_global.fit_predict(
        supervised[max(HORIZONS)], origin=max(origenes), horizon=max(HORIZONS)
    )
    importancias = modelo_global.feature_importances().head(10)
    importancias["ganancia"] = importancias["ganancia"].round(0)
    principal = str(importancias.iloc[0]["feature"])

    ref = predicciones[REFERENCIA]
    n_eval_region = int((ref["nivel"] == "region").sum())
    n_eval_comuna = int((ref["nivel"] == "comuna").sum())

    ctx: dict[str, object] = {
        "tabla_modelos": tabla,
        "tabla_conforme": tabla_conforme,
        "lectura_conforme": lectura_conforme,
        "tabla_servicio": tabla_servicio,
        "lectura_servicio": lectura_servicio,
        "tabla_servicios": tabla_servicios,
        "tabla_mixtas": tabla_mixtas,
        "seleccion": seleccion,
        "lectura": lectura,
        "brecha": brecha,
        "importancias": importancias,
        "n_series": int(panel["series_id"].nunique()),
        "n_series_3n": int(panel_3n["series_id"].nunique()),
        "n_servicios": int((panel_3n.drop_duplicates("series_id")["nivel"] == "servicio").sum()),
        "n_comunas": len(comunas_panel),
        "n_periodos": int(panel["t"].nunique()),
        "ano_min": int(panel["ano"].min()),
        "ano_max": int(panel["ano"].max()),
        "n_origenes": len(origenes),
        "origen_min": min(origenes),
        "origen_max": max(origenes),
        "n_eval_region": n_eval_region,
        "n_eval_comuna": n_eval_comuna,
        "tol_region": coverage_tolerance(n_eval_region, NIVEL_INTERVALO),
        "tol_comuna": coverage_tolerance(n_eval_comuna, NIVEL_INTERVALO),
        "lectura_importancias": (
            f"**Observacion:** la feature con mas ganancia es `{principal}`. "
            + (
                "El modelo se apoya sobre todo en la identidad y el nivel de cada "
                "territorio, y despues en la inercia reciente de la serie."
                if principal == "series_code"
                else "El orden de importancia debe leerse junto con el EDA de series."
            )
        ),
    }

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    por_serie.to_csv(OUTPUT_SUMMARY, index=False)
    OUTPUT_REPORT.write_text(render_report(ctx), encoding="utf-8")
    fila = tabla.set_index("modelo").loc[recomendado]
    seleccion_json = {
        "modelo_recomendado": recomendado,
        "construible": recomendado in available_models(),
        "criterio": (
            "Menor MASE promedio entre los modelos que superan al baseline y tienen "
            "cobertura compatible con el nominal en region y comunas."
        ),
        "nivel_intervalo": NIVEL_INTERVALO,
        "horizontes": list(HORIZONS),
        "semilla": RANDOM_SEED,
        "periodo_backtest": {
            "ano_min": int(panel["ano"].min()),
            "ano_max": int(panel["ano"].max()),
            "origenes": len(origenes),
            "paso": STEP,
            "t_primer_origen": int(min(origenes)),
            "t_ultimo_origen": int(max(origenes)),
        },
        "metricas_backtest": {
            "mase_region": float(fila["mase_region"]),
            "mase_comuna": float(fila["mase_comuna"]),
            "cobertura_region": float(fila["cobertura_region"]),
            "cobertura_comuna": float(fila["cobertura_comuna"]),
        },
    }
    OUTPUT_SELECTION.write_text(
        json.dumps(seleccion_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print()
    print(tabla.to_string(index=False))
    print(f"\nInforme escrito en {OUTPUT_REPORT.as_posix()}")
    print(f"Resumen escrito en {OUTPUT_SUMMARY.as_posix()}")
    print(f"Seleccion escrita en {OUTPUT_SELECTION.as_posix()}")


if __name__ == "__main__":
    main()
