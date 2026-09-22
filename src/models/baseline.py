"""Baseline estacional ingenuo: la referencia obligatoria del alcance del proyecto.

Predice `y[t] = y[t - 52]`, es decir, repite la misma semana del anio anterior.
Sirve como piso de comparacion: un modelo mas complejo solo se justifica si lo
supera en el mismo backtesting, y MASE expresa exactamente esa comparacion.

El intervalo de prediccion es **empirico**: se construye con los cuantiles de
los residuos que el propio baseline produce dentro del tramo de entrenamiento,
por serie. No se asume normalidad, porque el target es un conteo asimetrico y
una banda gaussiana produciria limites inferiores negativos.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from src.models.backtesting import empirical_interval, split_train_target
from src.models.features import SEASONAL_PERIOD

# Minimo de residuos por serie para que sus cuantiles empiricos sean utilizables.
# Por debajo de este umbral se recurre a los residuos agrupados de todas las
# series, en vez de publicar un intervalo calculado con un punado de puntos.
MIN_RESIDUOS_POR_SERIE: Final[int] = 20


class SeasonalNaive:
    """Baseline estacional ingenuo con intervalo de prediccion empirico."""

    name: str = "baseline_estacional"

    def __init__(self, period: int = SEASONAL_PERIOD, nivel: float = 0.80) -> None:
        self.period = period
        self.nivel = nivel
        # La columna de rezago estacional ya viene calculada en la matriz
        # supervisada: el pronostico del baseline es literalmente esa columna.
        self.columna_rezago = f"y_lag_{period}"

    def fit_point(
        self, train: pd.DataFrame, target: pd.DataFrame, columns: list[str]
    ) -> np.ndarray:
        """Pronostico puntual de cada fila de `target`: su rezago estacional.

        No necesita ajuste; `train` se recibe solo para cumplir el protocolo.
        """
        return target[self.columna_rezago].to_numpy(dtype=float)

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Pronostica `origin + horizon` repitiendo el mismo periodo del anio previo."""
        train, objetivo, _ = split_train_target(supervised, origin, horizon)
        if objetivo.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior"])
        if self.columna_rezago not in supervised.columns:
            raise ValueError(
                f"La matriz supervisada no contiene '{self.columna_rezago}'; "
                "el baseline requiere que el rezago estacional este disponible."
            )

        # Residuos in-sample del baseline, calculados solo sobre entrenamiento.
        residuos_train = train["y"] - train[self.columna_rezago]
        residuos_globales = residuos_train.to_numpy(dtype=float)

        registros: list[dict[str, object]] = []
        for _, fila in objetivo.iterrows():
            serie = fila["series_id"]
            prediccion = float(fila[self.columna_rezago])
            propios = residuos_train[train["series_id"] == serie].to_numpy(dtype=float)
            residuos = propios if len(propios) >= MIN_RESIDUOS_POR_SERIE else residuos_globales
            inferior, superior = empirical_interval(residuos, self.nivel)
            registros.append(
                {
                    "series_id": serie,
                    "y_pred": prediccion,
                    # El target es un conteo: el limite inferior se trunca en 0
                    # porque una demanda negativa no es interpretable.
                    "y_inferior": max(0.0, prediccion + inferior),
                    "y_superior": prediccion + superior,
                }
            )
        return pd.DataFrame(registros)


class SeasonalNaiveDrift:
    """Variante del baseline que corrige el nivel con la deriva interanual reciente.

    Ajusta el pronostico estacional por el cambio medio observado entre el ultimo
    tramo disponible y el mismo tramo del anio anterior. Es deliberadamente
    simple: sirve para distinguir cuanta de la mejora de un modelo complejo viene
    de capturar la tendencia y cuanta de estructura genuinamente nueva.
    """

    name: str = "baseline_estacional_drift"

    def __init__(
        self, period: int = SEASONAL_PERIOD, nivel: float = 0.80, ventana: int = 13
    ) -> None:
        self.period = period
        self.nivel = nivel
        self.ventana = ventana
        self.columna_rezago = f"y_lag_{period}"

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Pronostica el rezago estacional mas la deriva interanual de cada serie."""
        train, objetivo, _ = split_train_target(supervised, origin, horizon)
        if objetivo.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior"])

        # Deriva por serie: diferencia media reciente entre el valor observado y
        # su referencia estacional, medida solo dentro del entrenamiento.
        recientes = train[train["t"] > origin - self.ventana]
        deriva = (
            (recientes["y"] - recientes[self.columna_rezago])
            .groupby(recientes["series_id"])
            .mean()
        )
        residuos_train = train["y"] - train[self.columna_rezago]
        residuos_globales = residuos_train.to_numpy(dtype=float)

        registros: list[dict[str, object]] = []
        for _, fila in objetivo.iterrows():
            serie = fila["series_id"]
            ajuste = float(deriva.get(serie, 0.0))
            prediccion = max(0.0, float(fila[self.columna_rezago]) + ajuste)
            propios = residuos_train[train["series_id"] == serie].to_numpy(dtype=float)
            residuos = propios if len(propios) >= MIN_RESIDUOS_POR_SERIE else residuos_globales
            # Los residuos se centran por la deriva ya aplicada, para que el
            # intervalo no herede el sesgo que la correccion acaba de remover.
            inferior, superior = empirical_interval(
                np.asarray(residuos, dtype=float) - ajuste, self.nivel
            )
            registros.append(
                {
                    "series_id": serie,
                    "y_pred": prediccion,
                    "y_inferior": max(0.0, prediccion + inferior),
                    "y_superior": prediccion + superior,
                }
            )
        return pd.DataFrame(registros)
