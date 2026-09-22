"""Metricas de evaluacion para el modelo de demanda.

Incluye metricas puntuales y de intervalo. La eleccion responde a dos
propiedades del problema:

- El target es un conteo con rango enorme entre comunas (de ~1,6 a ~357
  atenciones semanales de media). Una metrica absoluta como MAE no es
  comparable entre series, de modo que se acompana siempre de una metrica
  escalada.
- Hay comunas con semanas en cero, donde MAPE es indefinido. Por eso la
  metrica escalada de referencia es **MASE**, que no divide por el valor real
  sino por el error del baseline ingenuo, y se mantiene finita con ceros.

El alcance del proyecto exige intervalos de prediccion, no solo pronostico
puntual: `interval_coverage` y `mean_interval_width` evaluan si el intervalo
declarado cumple su nivel nominal y a que costo de amplitud.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def mae(real: np.ndarray, pred: np.ndarray) -> float:
    """Error absoluto medio, en unidades del target (atenciones)."""
    return float(np.mean(np.abs(real - pred)))


def rmse(real: np.ndarray, pred: np.ndarray) -> float:
    """Raiz del error cuadratico medio; penaliza mas los errores grandes."""
    return float(np.sqrt(np.mean((real - pred) ** 2)))


def mape(real: np.ndarray, pred: np.ndarray) -> float:
    """Error porcentual absoluto medio, excluyendo los reales iguales a cero.

    Los ceros se excluyen en vez de sustituirse por un epsilon arbitrario: un
    epsilon inventado produciria porcentajes enormes sin significado. Si no
    queda ningun punto valido, devuelve NaN.
    """
    positivos = real != 0
    if not positivos.any():
        return float("nan")
    return float(np.mean(np.abs((real[positivos] - pred[positivos]) / real[positivos])) * 100)


def seasonal_naive_scale(historia: np.ndarray, period: int) -> float:
    """Error medio in-sample del baseline estacional, denominador de MASE.

    Es la cantidad que hace a MASE comparable entre series de escalas muy
    distintas: expresa el error del modelo como multiplo del error que cometeria
    repetir el mismo periodo del anio anterior.
    """
    if len(historia) <= period:
        return float("nan")
    diferencias = np.abs(historia[period:] - historia[:-period])
    escala = float(np.mean(diferencias))
    # Una serie constante da escala 0 y MASE indefinido; se declara en vez de
    # devolver un valor enganoso.
    return escala if escala > 0 else float("nan")


def mase(real: np.ndarray, pred: np.ndarray, escala: float) -> float:
    """Error absoluto medio escalado por el error del baseline estacional.

    Interpretacion directa: MASE < 1 significa que el modelo supera al baseline
    ingenuo; MASE > 1 significa que no lo justifica.
    """
    if not np.isfinite(escala) or escala <= 0:
        return float("nan")
    return float(np.mean(np.abs(real - pred)) / escala)


def interval_coverage(
    real: np.ndarray, inferior: np.ndarray, superior: np.ndarray
) -> float:
    """Proporcion de valores reales contenidos en el intervalo de prediccion.

    Se compara contra el nivel nominal declarado: una cobertura muy por debajo
    indica intervalos demasiado estrechos (sobreconfianza) y una muy por encima,
    intervalos inutilmente anchos.
    """
    dentro = (real >= inferior) & (real <= superior)
    return float(np.mean(dentro))


def mean_interval_width(inferior: np.ndarray, superior: np.ndarray) -> float:
    """Amplitud media del intervalo, en unidades del target."""
    return float(np.mean(superior - inferior))


def evaluate_predictions(
    predicciones: pd.DataFrame,
    escalas: dict[str, float] | None = None,
    nivel_nominal: float = 0.80,
) -> pd.DataFrame:
    """Calcula el cuadro completo de metricas sobre un DataFrame de predicciones.

    `predicciones` debe contener `series_id`, `horizonte`, `y_real`, `y_pred` y,
    opcionalmente, `y_inferior`/`y_superior` para las metricas de intervalo.
    `escalas` mapea cada `series_id` a su denominador MASE; si falta, MASE
    queda en NaN para esa serie en vez de calcularse con un denominador erroneo.
    """
    requeridas = {"series_id", "horizonte", "y_real", "y_pred"}
    if faltantes := requeridas - set(predicciones.columns):
        raise ValueError(f"Faltan columnas en las predicciones: {sorted(faltantes)}")

    tiene_intervalo = {"y_inferior", "y_superior"} <= set(predicciones.columns)
    escalas = escalas or {}
    filas: list[dict[str, object]] = []

    for (serie, horizonte), grupo in predicciones.groupby(["series_id", "horizonte"]):
        real = grupo["y_real"].to_numpy(dtype=float)
        pred = grupo["y_pred"].to_numpy(dtype=float)
        registro: dict[str, object] = {
            "series_id": serie,
            "horizonte": int(horizonte),
            "n": len(real),
            "mae": round(mae(real, pred), 3),
            "rmse": round(rmse(real, pred), 3),
            "mape_pct": round(mape(real, pred), 3),
            "mase": round(mase(real, pred, escalas.get(serie, float("nan"))), 4),
        }
        if tiene_intervalo:
            inferior = grupo["y_inferior"].to_numpy(dtype=float)
            superior = grupo["y_superior"].to_numpy(dtype=float)
            registro["cobertura"] = round(interval_coverage(real, inferior, superior), 4)
            registro["cobertura_nominal"] = nivel_nominal
            registro["amplitud_media"] = round(mean_interval_width(inferior, superior), 3)
        filas.append(registro)

    return pd.DataFrame(filas).sort_values(["series_id", "horizonte"]).reset_index(drop=True)


def paired_comparison(
    pred_a: pd.DataFrame,
    pred_b: pd.DataFrame,
    escalas: dict[str, float],
    series: list[str] | None = None,
) -> dict[str, float]:
    """Compara dos modelos sobre exactamente los mismos pronosticos.

    Una diferencia de MASE entre modelos no dice si es real o azar: con 13
    origenes, la serie regional aporta solo 65 evaluaciones y unos pocos errores
    grandes pueden mover el promedio. Esta prueba empareja cada pronostico
    (origen, horizonte, serie) de ambos modelos y aplica Wilcoxon de rangos con
    signo sobre sus errores absolutos escalados por MASE, que no asume
    normalidad de las diferencias.

    Devuelve el error medio de cada modelo, el cambio porcentual de `b` respecto
    de `a`, la proporcion de pronosticos en que `b` es mejor y el p-valor
    bilateral. Si todas las diferencias son nulas, el p-valor es 1.
    """
    clave = ["origen", "horizonte", "series_id"]

    def _errores(pred: pd.DataFrame) -> pd.Series:
        frame = pred[[*clave, "y_real", "y_pred"]].copy()
        if series is not None:
            frame = frame[frame["series_id"].isin(series)]
        escala = frame["series_id"].map(escalas)
        frame["error"] = (frame["y_real"] - frame["y_pred"]).abs() / escala
        return frame.set_index(clave)["error"]

    unido = pd.concat(
        [_errores(pred_a).rename("a"), _errores(pred_b).rename("b")], axis=1, join="inner"
    ).dropna()
    if unido.empty:
        raise ValueError("Los modelos no comparten pronosticos comparables.")

    diferencias = unido["b"] - unido["a"]
    if np.allclose(diferencias, 0.0):
        p_valor = 1.0
    else:
        p_valor = float(stats.wilcoxon(unido["b"], unido["a"]).pvalue)
    media_a, media_b = float(unido["a"].mean()), float(unido["b"].mean())
    return {
        "n": int(len(unido)),
        "error_a": round(media_a, 4),
        "error_b": round(media_b, 4),
        "cambio_pct": round((media_b / media_a - 1) * 100, 2) if media_a else float("nan"),
        "proporcion_b_mejor": round(float((unido["b"] < unido["a"]).mean()), 4),
        "p_valor": round(p_valor, 4),
    }


def coverage_tolerance(n: int, nivel: float) -> float:
    """Desviacion de cobertura compatible con el azar, al 95%.

    Una cobertura observada de 0,78 contra un nominal de 0,80 puede ser pura
    variacion muestral si hay pocas evaluaciones. Con `n` evaluaciones, la
    cobertura observada fluctua alrededor del nominal con desviacion
    `sqrt(nivel * (1 - nivel) / n)`; esta funcion devuelve 1,96 veces ese valor.

    Es una aproximacion: supone evaluaciones independientes, y en el backtesting
    las comunas comparten origenes, de modo que la tolerancia real es algo mayor.
    """
    if n <= 0:
        return float("nan")
    return float(1.96 * np.sqrt(nivel * (1 - nivel) / n))
