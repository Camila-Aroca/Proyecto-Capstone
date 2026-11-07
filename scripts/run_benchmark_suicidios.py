"""Benchmark del pronóstico semanal de suicidios (región y comunas de residencia, RM).

Mismo diseño de evaluación que el modelo de demanda: backtesting con origen
deslizante (13 orígenes cada 4 semanas, horizontes 1-8, solo años cerrados), el
baseline estacional como referencia obligatoria, los modelos globales del registro
y los modelos propios de este objetivo (`src/models/suicidios.py`).

**Regla de selección, fijada antes de evaluar:** entre los modelos que superan al
baseline estacional en RMSSE en la región y en las comunas, el de menor RMSSE
promedio cuya cobertura sea compatible con la que declara (tolerancia muestral) en
ambos niveles. Por qué RMSSE y no MASE, y por qué la cobertura se compara con la
declarada y no con 80%: ver el módulo del modelo y el informe.

Uso (vía pipeline): `python scripts/run_pipeline.py --stage benchmark_suicidios`
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.models import RANDOM_SEED
from src.models import suicidios as su
from src.models.backtesting import build_origins, prepare_supervised, rolling_origin_backtest
from src.models.features import RM_SERIES_ID

OUTPUT_REPORT: Final[Path] = Path("reports/modeling/benchmark_suicidios.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/modeling/benchmark_suicidios_resumen.csv")
OUTPUT_SELECTION: Final[Path] = su.RUTA_SELECCION
TITULO: Final[str] = "# Benchmark del pronóstico semanal de suicidios (RM)"
ALFA: Final[float] = 0.05


def tabla_md(frame: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |"
             for fila in frame.itertuples(index=False, name=None)]
    return "\n".join([encabezado, separador, *filas])


def correr_modelos(panel: pd.DataFrame, nombres: list[str], n_origenes: int, paso: int,
                   escala: pd.DataFrame, etiqueta: str, desde_t: int | None = None
                   ) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Backtesting de cada modelo sobre el mismo panel y las mismas matrices."""
    supervisada = prepare_supervised(panel, su.HORIZONTES, exogenous=())
    predicciones, resumenes = {}, {}
    for nombre in nombres:
        inicio = time.perf_counter()
        pred = rolling_origin_backtest(panel, su.build_model(nombre), su.HORIZONTES, n_origenes, paso,
                                       supervised=supervisada)
        if desde_t is not None:
            pred = pred[pred["t"] > desde_t].reset_index(drop=True)
        predicciones[nombre] = pred
        resumenes[nombre] = su.evaluar(pred, escala).assign(modelo=nombre)
        print(f"  [{etiqueta}] {nombre}: {time.perf_counter() - inicio:.1f}s", flush=True)
    return predicciones, resumenes


def contrastes(predicciones: dict[str, pd.DataFrame], elegido: str, escala: pd.DataFrame,
               series: dict[str, list[str]]) -> pd.DataFrame:
    """Elegido frente a cada alternativa (error cuadrático escalado), con Holm por nivel."""
    filas = []
    for nombre, pred in predicciones.items():
        if nombre == elegido:
            continue
        for nivel, ids in series.items():
            c = su.comparacion_pareada(predicciones[elegido], pred, escala, ids)
            filas.append({"alternativa": nombre, "nivel": nivel, "n": c["n"],
                          "cambio del error frente al elegido (%)": c["cambio_pct"],
                          "proporción en que la alternativa es mejor": c["proporcion_b_mejor"],
                          "p_valor": c["p_valor"], "p_wilcoxon": c["p_wilcoxon"]})
    tabla = pd.DataFrame(filas)
    tabla["p_holm"] = np.nan
    for nivel in series:
        mascara = tabla["nivel"] == nivel
        tabla.loc[mascara, "p_holm"] = su.holm(tabla.loc[mascara, "p_valor"].tolist())
    tabla["p_valor"] = tabla["p_valor"].map(lambda p: float(f"{p:.3g}"))
    tabla["p_holm"] = tabla["p_holm"].map(lambda p: float(f"{p:.3g}"))
    tabla["p_wilcoxon"] = tabla["p_wilcoxon"].map(lambda p: float(f"{p:.3g}"))
    return tabla


def por_horizonte(resumenes: dict[str, pd.DataFrame], panel: pd.DataFrame, modelos: list[str]) -> pd.DataFrame:
    niveles = panel[["series_id", "nivel"]].drop_duplicates()
    partes = []
    for nombre in modelos:
        r = resumenes[nombre].merge(niveles, on="series_id")
        partes.append(r.groupby(["nivel", "horizonte"])["rmsse"].median().rename(nombre))
    return pd.concat(partes, axis=1).round(4).reset_index()


def parametros_finales(panel: pd.DataFrame, modelo: str, origen: int) -> dict[str, float]:
    """Parámetros del modelo elegido ajustado en el último origen (lectura, no selección)."""
    instancia = su.build_model(modelo)
    if not isinstance(instancia, su.PoissonEstacionalJerarquico):
        return {}
    supervisada = prepare_supervised(panel, (1,), exogenous=())[1]
    instancia.fit_predict(supervisada, origen, 1)
    region = supervisada[(supervisada["nivel"] == "region") & (supervisada["t"] <= origen)]
    regresor, _ = instancia._ajustar_region(region, origen)
    semanas = np.arange(1, 53)
    perfil = np.exp(su._fourier(semanas, instancia.armonicos) @ regresor.coef_)
    return {
        "nivel_semanal_7_dias": round(float(np.exp(regresor.intercept_)), 3),
        "semana_maxima": int(semanas[np.argmax(perfil)]), "semana_minima": int(semanas[np.argmin(perfil)]),
        "razon_maximo_minimo": round(float(perfil.max() / perfil.min()), 3),
        **{k: round(v, 3) for k, v in instancia.diagnostico.items()},
    }


def render(contexto: dict[str, object]) -> str:
    tabla: pd.DataFrame = contexto["tabla"]
    elegido, criterio = contexto["elegido"], contexto["criterio"]
    fila = tabla.set_index("modelo").loc[elegido]
    base = tabla.set_index("modelo").loc[su.REFERENCIA]
    cero = tabla.set_index("modelo").loc[su.REFERENCIA_CERO]
    columnas = ["modelo", "rmsse_region", "rmsse_comuna", "rmsse_promedio", "mase_region", "mase_comuna",
                "cobertura_region", "cobertura_esperada_region", "calibrado_region", "cobertura_comuna",
                "cobertura_esperada_comuna", "calibrado_comuna", "puntaje_intervalo_region",
                "puntaje_intervalo_comuna", "dispersion_pearson_region", "dispersion_pearson_comuna"]
    vs_base = contexto["vs_base"]
    habilidad_r = (1 - fila["rmsse_region"] / base["rmsse_region"]) * 100
    habilidad_c = (1 - fila["rmsse_comuna"] / base["rmsse_comuna"]) * 100
    params = contexto["parametros"]
    lineas = [
        TITULO, "",
        "Generado por `scripts/run_benchmark_suicidios.py` (stage `benchmark_suicidios`). Cifras calculadas "
        "desde `data/processed/marts/mart_suicidios_comuna_weekly.parquet`; ver el EDA del mart en "
        "`reports/eda/eda_mart_suicidios_comuna_weekly.md`.", "",
        "## 1. Qué se pronostica y cómo se evalúa", "",
        "- **Objetivo:** defunciones por lesiones autoinfligidas intencionalmente (CIE-10 X60-X84 en la causa "
        "externa) por semana DEIS, de residentes de la RM (región) y de cada una de sus 52 comunas de residencia.",
        f"- **Ventana:** semanas regulares desde {su.ANO_INICIO} hasta {contexto['ano_max']} (años cerrados); "
        "2026 queda para el holdout. La semana 53 (fragmento de calendario) no entra.",
        f"- **Backtesting:** {su.N_ORIGENES} orígenes cada {su.PASO} semanas (t = {contexto['origenes'][0]} a "
        f"{contexto['origenes'][-1]}), horizontes 1-8; cada modelo se reajusta en cada origen solo con lo "
        "observado hasta él.",
        f"- **Escala:** {contexto['n_region']} pronósticos regionales y {contexto['n_comuna']} comunales por modelo.", "",
        "**Métrica de selección: RMSSE.** Cuatro de cada cinco comuna-semanas son cero. El error absoluto lo "
        "minimiza la mediana, que en una comuna es 0: la referencia que pronostica siempre cero obtiene el menor "
        f"MASE comunal de la tabla ({cero['mase_comuna']}) y el menor error absoluto ({cero['mae_comuna']} frente "
        f"a {fila['mae_comuna']} del elegido), aunque no anticipa nada. El error cuadrático lo minimiza la "
        "media, que es lo que se quiere estimar; RMSSE lo escala por el error cuadrático del baseline estacional "
        "en la historia previa al primer origen (como MASE). RMSSE < 1 significa superar al baseline. MASE se "
        "informa solo para leer la tabla igual que la del modelo de demanda.", "",
        "**Calibración de intervalos de conteos.** Un intervalo de enteros no cubre exactamente 80%: con una "
        "media de 0,2 semanal, el intervalo [0, 1] ya cubre ~98%. Se compara la cobertura observada con la que "
        "el propio modelo declara para cada intervalo (`cobertura_esperada`); los modelos sin distribución "
        "declarada se comparan con el 80% nominal. Tolerancia: 1,96 errores estándar binomiales.", "",
        "## 2. Resultados", "", tabla_md(tabla[columnas]), "",
        f"`referencia_cero` y `baseline_estacional_drift` son referencias, no candidatos. El puntaje de intervalo "
        "(Gneiting y Raftery, 2007) suma el ancho y una penalización de 2/0,2 por cada unidad fuera; menor es "
        "mejor. La dispersión de Pearson es el error cuadrático dividido por la media pronosticada: ~1 indica que "
        "el error que queda es el azar propio de un conteo de Poisson.", "",
        "## 3. Selección", "",
        f"- **Modelo elegido:** `{elegido}`.",
        f"- **Criterio:** {criterio}.",
        f"- **Habilidad frente al baseline estacional (RMSSE):** {habilidad_r:.1f}% en la región y "
        f"{habilidad_c:.1f}% en las comunas.",
        f"- **Error cuadrático medio del elegido frente al baseline** (negativo = el elegido se equivoca menos; "
        f"Diebold-Mariano por origen con Newey-West y corrección HLN): región {vs_base['region']['cambio_pct']}%, "
        f"p = {vs_base['region']['p_valor']:.3g}; comunas {vs_base['comuna']['cambio_pct']}%, "
        f"p = {vs_base['comuna']['p_valor']:.3g} ({vs_base['comuna']['origenes']} orígenes).",
        f"- **Pronóstico típico (Wilcoxon):** región p = {vs_base['region']['p_wilcoxon']:.3g}; comunas p = "
        f"{vs_base['comuna']['p_wilcoxon']:.3g}. En las comunas el baseline acierta exactamente más semanas "
        f"(el elegido tiene menor error solo en una proporción {vs_base['comuna']['proporcion_b_mejor']} de los "
        "pronósticos: en las semanas en cero el baseline acierta exactamente) y "
        "falla fuerte en las demás; por eso la prueba de la mediana no refleja la diferencia de la media, que es "
        "lo que mide la regla de selección.",
        f"- **Cobertura:** región {fila['cobertura_region']} (declarada {fila['cobertura_esperada_region']}), "
        f"comunas {fila['cobertura_comuna']} (declarada {fila['cobertura_esperada_comuna']}).",
        f"- **Error restante:** dispersión de Pearson fuera de muestra {fila['dispersion_pearson_region']} en la "
        f"región y {fila['dispersion_pearson_comuna']} en las comunas.", "",
    ]
    if params:
        lineas += [
            "Parámetros del modelo elegido ajustado en el último origen (lectura descriptiva):", "",
            f"- Nivel regional de una semana de 7 días en la media estacional: {params['nivel_semanal_7_dias']}.",
            f"- Estacionalidad: máximo en la semana {params['semana_maxima']}, mínimo en la "
            f"{params['semana_minima']}, razón máximo/mínimo {params['razon_maximo_minimo']}.",
            f"- Forma de la distribución Gamma de las tasas relativas comunales: a = "
            f"{params.get('forma_gamma', float('nan'))} (casos efectivos que equivalen a la tasa regional; "
            "una comuna con E casos esperados conserva E/(E+a) de su desviación propia).",
            f"- Dispersión estimada en el entrenamiento: región {params['dispersion_region']}, comunas "
            f"{params['dispersion_comuna']} (1 = Poisson).", "",
        ]
    lineas += [
        "## 4. Contraste del elegido frente a cada alternativa", "",
        "Cambio porcentual del error cuadrático escalado medio de la alternativa respecto del elegido (positivo = "
        "la alternativa es peor). `p_valor`: Diebold-Mariano sobre la pérdida media por origen; `p_holm`: su "
        "ajuste de Holm dentro de cada nivel; `p_wilcoxon`: prueba de rangos sobre cada pronóstico (pronóstico "
        "típico, informativa). Con 13 orígenes la potencia es baja: un p alto no prueba equivalencia.", "",
        tabla_md(contexto["contrastes"]), "",
        "## 5. RMSSE por horizonte (mediana entre series)", "",
        tabla_md(contexto["horizontes"]), "",
        "## 6. Lectura y límites", "",
        "- **Hecho observado:** el modelo elegido tiene menor RMSSE que el baseline estacional en ambos niveles, "
        "sus intervalos cubren lo que declaran y su error restante es del orden de la varianza de Poisson de su "
        "propio pronóstico (dispersión de Pearson cercana a 1). La significancia de cada diferencia está en la "
        "sección 4.",
        "- Los RMSSE por horizonte se calculan con 13 pronósticos cada uno: su variación entre horizontes es "
        "ruido muestral y no se interpreta horizonte a horizonte.",
        "- **Inferencia:** a escala comunal y semanal, la mayor parte de la variación es azar de conteos "
        "pequeños; ningún modelo de esta tabla la reduce de forma significativa. El pronóstico comunal es la "
        "**tasa esperada** de la semana, no una predicción de casos individuales.",
        "- El territorio es la comuna de **residencia** del fallecido: no es el lugar del suicidio ni un "
        "establecimiento, y no se cruza con Urgencias por persona.",
        "- Los conteos son defunciones registradas; las semanas finales con inscripción incompleta se excluyen "
        "(regla y evidencia en el EDA del mart). Con un único snapshot no es posible medir revisiones posteriores "
        "de la causa de muerte.",
    ]
    return "\n".join(lineas) + "\n"


def main() -> None:
    mart = su.load_mart()
    ano_max = su.ultimo_ano_cerrado(mart)
    panel = su.build_panel(mart, hasta_ano=ano_max)
    origenes = build_origins(panel, su.HORIZONTES, su.N_ORIGENES, su.PASO)
    escala = su.escalas(panel, min(origenes))
    predicciones, resumenes = correr_modelos(panel, su.available_models(), su.N_ORIGENES, su.PASO, escala,
                                             "benchmark")
    tabla = su.tabla_modelos(predicciones, resumenes)
    elegido, criterio = su.seleccionar(tabla)
    comunas = sorted(set(panel["series_id"]) - {RM_SERIES_ID})
    series = {"region": [RM_SERIES_ID], su.NIVEL_COMUNA: comunas}
    vs_base = {n: su.comparacion_pareada(predicciones[su.REFERENCIA], predicciones[elegido], escala, ids)
               for n, ids in series.items()}
    pred = predicciones[elegido]
    contexto = {
        "tabla": tabla, "elegido": elegido, "criterio": criterio, "origenes": origenes, "ano_max": ano_max,
        "vs_base": vs_base, "contrastes": contrastes(predicciones, elegido, escala, series),
        "horizontes": por_horizonte(resumenes, panel, [elegido, su.REFERENCIA]),
        "parametros": parametros_finales(panel, elegido, max(origenes)),
        "n_region": int((pred["nivel"] == "region").sum()), "n_comuna": int((pred["nivel"] == su.NIVEL_COMUNA).sum()),
    }
    fila = tabla.set_index("modelo").loc[elegido]
    seleccion = {
        "modelo_recomendado": elegido,
        "construible": True,
        "criterio": criterio,
        "nivel_intervalo": su.NIVEL_INTERVALO,
        "horizontes": list(su.HORIZONTES),
        "semilla": RANDOM_SEED,
        "ano_inicio": su.ANO_INICIO,
        "periodo_backtest": {"ano_min": su.ANO_INICIO, "ano_max": ano_max, "origenes": len(origenes),
                             "paso": su.PASO, "t_primer_origen": int(min(origenes)),
                             "t_ultimo_origen": int(max(origenes))},
        "metricas_backtest": {
            "rmsse_region": float(fila["rmsse_region"]), "rmsse_comuna": float(fila["rmsse_comuna"]),
            "mase_region": float(fila["mase_region"]), "mase_comuna": float(fila["mase_comuna"]),
            "cobertura_region": float(fila["cobertura_region"]), "cobertura_comuna": float(fila["cobertura_comuna"]),
            "cobertura_esperada_region": float(fila["cobertura_esperada_region"]),
            "cobertura_esperada_comuna": float(fila["cobertura_esperada_comuna"]),
        },
    }
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(render(contexto), encoding="utf-8")
    pd.concat(resumenes.values(), ignore_index=True).to_csv(OUTPUT_SUMMARY, index=False)
    OUTPUT_SELECTION.write_text(json.dumps(seleccion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Modelo elegido: {elegido} ({criterio}).", flush=True)


if __name__ == "__main__":
    if "--force" in sys.argv:
        sys.argv.remove("--force")
    main()
