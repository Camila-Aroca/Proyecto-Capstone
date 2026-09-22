"""Motor de backtesting con origenes de pronostico deslizantes (rolling origin).

Esquema de validacion acordado para el proyecto: en cada origen `o` el modelo
solo puede usar informacion disponible hasta `o`, y pronostica `t = o + h` para
cada horizonte `h` del alcance (4 a 8 semanas). Desplazando el origen se
obtienen multiples mediciones del error en vez de una sola ventana, que es lo
que exige la evidencia academica del APT.

**Por que no se reconstruyen las features en cada origen.** La matriz
supervisada se calcula una sola vez por horizonte sobre el panel completo. Esto
no introduce fuga temporal porque `build_supervised_frame` usa estrategia
directa: la fila de `t` solo contiene valores observados hasta `t - h`. Por lo
tanto una fila de entrenamiento con `t <= o` jamas mira mas alla de `o`, y la
fila objetivo `t = o + h` solo mira hasta `o`. Precalcular evita repetir el
mismo desplazamiento decenas de veces sin relajar ninguna garantia.

Lo que si depende del origen es el **ajuste**: cada modelo se reentrena con las
filas `t <= o` en cada iteracion.

MASE se escala con el error del baseline estacional calculado solo sobre la
historia previa al primer origen, nunca sobre el tramo evaluado.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from src.models.features import (
    SEASONAL_PERIOD,
    build_supervised_frame,
    drop_incomplete_rows,
    feature_columns,
)
from src.models.metrics import evaluate_predictions, seasonal_naive_scale


@runtime_checkable
class DemandModel(Protocol):
    """Interfaz minima que debe implementar un modelo de demanda.

    Mantenerla pequena permite que el baseline, los modelos estadisticos y los
    de machine learning se evaluen con el mismo motor y las mismas metricas,
    que es la unica forma de que la comparacion sea honesta.
    """

    name: str

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Ajusta con `supervised[t <= origin]` y pronostica `t = origin + horizon`.

        Debe devolver un DataFrame con `series_id`, `y_pred` y, cuando el modelo
        produzca intervalos, `y_inferior` e `y_superior`.
        """
        ...


@runtime_checkable
class PointForecaster(Protocol):
    """Capacidad adicional: ajustar y pronosticar filas arbitrarias, solo puntual.

    `DemandModel.fit_predict` pronostica un unico periodo objetivo. La prediccion
    conforme necesita ademas pronosticar una **ventana de calibracion** completa
    con un solo ajuste, y para eso requiere separar el pronostico puntual de la
    construccion del intervalo. Los modelos que exponen `fit_point` pueden
    envolverse con `ConformalWrapper` sin que este conozca su implementacion.
    """

    name: str

    def fit_point(
        self, train: pd.DataFrame, target: pd.DataFrame, columns: list[str]
    ) -> np.ndarray:
        """Ajusta con `train` y devuelve el pronostico puntual de cada fila de `target`."""
        ...


def prepare_supervised(
    panel: pd.DataFrame, horizons: tuple[int, ...]
) -> dict[int, pd.DataFrame]:
    """Precalcula la matriz supervisada de cada horizonte sobre el panel completo."""
    return {h: build_supervised_frame(panel, horizon=h) for h in horizons}


def split_train_target(
    supervised: pd.DataFrame, origin: int, horizon: int
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Separa entrenamiento y fila objetivo para un origen y horizonte dados.

    Devuelve tambien la lista de predictores, derivada del propio DataFrame para
    que agregar una feature no exija mantener una lista paralela.
    """
    columnas = feature_columns(supervised)
    completo = drop_incomplete_rows(supervised, columnas)
    train = completo[completo["t"] <= origin]
    objetivo = completo[completo["t"] == origin + horizon]
    return train, objetivo, columnas


def build_origins(
    panel: pd.DataFrame,
    horizons: tuple[int, ...],
    n_origins: int,
    step: int = 1,
) -> list[int]:
    """Calcula los origenes validos, del mas reciente hacia atras.

    Un origen es valido si el objetivo mas lejano (`origen + max(horizons)`)
    todavia existe en el panel: de lo contrario no habria valor real contra el
    cual evaluar.
    """
    t_max = int(panel["t"].max())
    ultimo_origen = t_max - max(horizons)
    origenes = [ultimo_origen - i * step for i in range(n_origins)]
    return sorted(o for o in origenes if o >= 0)


def compute_mase_scales(
    panel: pd.DataFrame, hasta_t: int, period: int = SEASONAL_PERIOD
) -> dict[str, float]:
    """Denominadores MASE por serie, usando solo historia previa a la evaluacion."""
    historia = panel[panel["t"] <= hasta_t]
    return {
        serie: seasonal_naive_scale(
            grupo.sort_values("t")["y"].to_numpy(dtype=float), period
        )
        for serie, grupo in historia.groupby("series_id")
    }


def rolling_origin_backtest(
    panel: pd.DataFrame,
    model: DemandModel,
    horizons: tuple[int, ...] = (4, 5, 6, 7, 8),
    n_origins: int = 13,
    step: int = 4,
    supervised: dict[int, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Ejecuta el backtesting: una fila por (origen, horizonte, serie).

    Conserva cada prediccion individual junto a su valor real, de modo que
    cualquier agregacion posterior (por horizonte, por serie, por nivel
    jerarquico) parta exactamente de la misma evidencia.

    `supervised` permite reutilizar matrices ya calculadas cuando se evaluan
    varios modelos sobre el mismo panel, que es el caso del benchmark.
    """
    origenes = build_origins(panel, horizons, n_origins, step)
    if not origenes:
        raise ValueError("No hay origenes validos: el panel es demasiado corto.")

    matrices = supervised if supervised is not None else prepare_supervised(panel, horizons)
    reales = panel.set_index(["series_id", "t"])["y"]
    filas: list[pd.DataFrame] = []

    for origen in origenes:
        for horizonte in horizons:
            prediccion = model.fit_predict(matrices[horizonte], origen, horizonte).copy()
            if prediccion.empty:
                continue
            prediccion["origen"] = origen
            prediccion["t"] = origen + horizonte
            prediccion["horizonte"] = horizonte
            # `reindex` deja NaN si la serie no existe en el periodo objetivo,
            # en vez de descartar la fila en silencio.
            prediccion["y_real"] = reales.reindex(
                pd.MultiIndex.from_arrays([prediccion["series_id"], prediccion["t"]])
            ).to_numpy()
            filas.append(prediccion)

    resultado = pd.concat(filas, ignore_index=True)
    resultado["modelo"] = model.name
    # Cada prediccion lleva su posicion en la jerarquia, tomada del panel. Asi la
    # reconciliacion lee la estructura desde los datos y no desde convenciones
    # de nombres de series.
    estructura = [c for c in ("nivel", "servicio_id") if c in panel.columns]
    resultado = resultado.drop(columns=estructura, errors="ignore").merge(
        panel[["series_id", *estructura]].drop_duplicates("series_id"),
        on="series_id",
        how="left",
        validate="many_to_one",
    )
    return resultado.dropna(subset=["y_real"]).reset_index(drop=True)


def summarize_backtest(
    predicciones: pd.DataFrame,
    panel: pd.DataFrame,
    horizons: tuple[int, ...] = (4, 5, 6, 7, 8),
    n_origins: int = 13,
    step: int = 4,
    nivel_nominal: float = 0.80,
) -> pd.DataFrame:
    """Resume el backtesting en metricas por serie y horizonte."""
    origenes = build_origins(panel, horizons, n_origins, step)
    escalas = compute_mase_scales(panel, hasta_t=min(origenes))
    resumen = evaluate_predictions(predicciones, escalas, nivel_nominal)
    resumen["modelo"] = predicciones["modelo"].iloc[0]
    return resumen


def aggregate_by_level(resumen: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Agrega las metricas por nivel jerarquico (region y comuna).

    Los niveles no se mezclan: la serie RM es una sola y las comunas son muchas,
    de modo que promediarlas juntas ocultaria la diferencia de dificultad que el
    EDA de series documento entre ambos niveles.
    """
    niveles = panel[["series_id", "nivel"]].drop_duplicates()
    unido = resumen.merge(niveles, on="series_id", how="left", validate="many_to_one")
    agregaciones = {
        "series": ("series_id", "nunique"),
        "mae_medio": ("mae", "mean"),
        "rmse_medio": ("rmse", "mean"),
        "mape_mediano_pct": ("mape_pct", "median"),
        "mase_mediano": ("mase", "median"),
    }
    if "cobertura" in unido.columns:
        agregaciones["cobertura_media"] = ("cobertura", "mean")
        agregaciones["amplitud_media"] = ("amplitud_media", "mean")
    return (
        unido.groupby(["modelo", "nivel", "horizonte"], as_index=False)
        .agg(**agregaciones)
        .round(4)
    )


def empirical_interval(residuos: np.ndarray, nivel: float = 0.80) -> tuple[float, float]:
    """Cuantiles empiricos de los residuos para construir un intervalo.

    Se prefiere el intervalo empirico sobre uno gaussiano porque el target es un
    conteo asimetrico: asumir normalidad produciria limites inferiores negativos
    y peor cobertura en las colas.
    """
    if len(residuos) == 0:
        return (float("nan"), float("nan"))
    alfa = (1 - nivel) / 2
    return (float(np.quantile(residuos, alfa)), float(np.quantile(residuos, 1 - alfa)))
