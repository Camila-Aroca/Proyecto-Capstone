"""Prediccion conforme para intervalos con cobertura verificable.

**El problema que resuelve.** El benchmark midio que los intervalos del modelo
de boosting declaran 80% y cubren bastante menos, y que los del GLM dependen de
un supuesto distribucional (binomial negativa) que puede no cumplirse. Ambos
construyen el intervalo a partir de un modelo del error. La prediccion conforme
no modela el error: lo **mide**. Toma los errores que el modelo cometio sobre
datos que no vio y usa sus cuantiles, con una correccion de muestra finita que
garantiza la cobertura nominal bajo intercambiabilidad.

**Como se aplica aqui (conforme dividida en el tiempo).**

1. Se reserva el tramo final del entrenamiento como ventana de calibracion.
2. El modelo base se ajusta sin esa ventana y pronostica cada fila de ella; la
   diferencia con el valor observado es el residuo de calibracion.
3. El modelo base se reajusta con todo el entrenamiento para el pronostico
   puntual; el intervalo se construye con los cuantiles de los residuos.

Decisiones de diseno, cada una con su motivo:

- **Residuos con signo y dos cuantiles**, no el valor absoluto: el conteo es
  asimetrico y el intervalo no tiene por que ser simetrico alrededor del punto.
- **Normalizacion por `sqrt(y_pred)`**: la dispersion de un conteo crece con su
  nivel. Sin normalizar, las comunas pequenas recibirian intervalos del ancho
  de las grandes. La raiz corresponde a la escala de un proceso de Poisson y no
  depende de los valores observados de calibracion, lo que preserva la validez
  del procedimiento.
- **Conforme por grupos (Mondrian) segun el nivel jerarquico**: el EDA y el GLM
  mostraron que el agregado regional tiene una dispersion relativa un orden de
  magnitud mayor que una comuna. Mezclar sus residuos haria que el cuantil de
  uno contaminara al otro, de modo que cada nivel se calibra con sus propios
  residuos y la garantia de cobertura rige dentro de cada nivel.

**Limites que no se ocultan.**

- La garantia exacta supone intercambiabilidad entre calibracion y pronostico.
  En una serie con tendencia eso se cumple solo aproximadamente; por eso la
  cobertura se sigue **midiendo** en el backtesting en vez de darse por
  garantizada.
- El modelo de calibracion se entrena hasta el inicio de la ventana y no se
  actualiza dentro de ella, de modo que sus errores son algo mayores que los
  del modelo final: los intervalos tienden a ser levemente conservadores.
- Con pocos residuos en un grupo, la correccion de muestra finita puede exigir
  un cuantil fuera del rango observado. En ese caso se usa el extremo
  observado y el grupo queda marcado como `garantia_valida = False`.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from src.models.backtesting import PointForecaster, split_train_target

CALIBRACION_PERIODOS: Final[int] = 26


def conformal_bounds(scores: np.ndarray, nivel: float) -> tuple[float, float, bool]:
    """Cuantiles conformes inferior y superior con correccion de muestra finita.

    Para `n` residuos y nivel `1 - alfa`, el limite inferior es el residuo de
    orden `floor((n + 1) * alfa / 2)` y el superior el de orden
    `ceil((n + 1) * (1 - alfa / 2))`. Esa correccion `n + 1` es la que da la
    garantia de cobertura; un cuantil empirico sin ella queda corto con pocas
    observaciones. Devuelve tambien si la garantia es alcanzable con `n`.
    """
    if len(scores) == 0:
        return float("nan"), float("nan"), False
    ordenados = np.sort(np.asarray(scores, dtype=float))
    n = len(ordenados)
    alfa = 1.0 - nivel
    k_inferior = int(np.floor((n + 1) * alfa / 2))
    k_superior = int(np.ceil((n + 1) * (1 - alfa / 2)))
    valida = k_inferior >= 1 and k_superior <= n
    inferior = ordenados[min(max(k_inferior, 1), n) - 1]
    superior = ordenados[min(k_superior, n) - 1]
    return float(inferior), float(superior), valida


def _escala(prediccion: np.ndarray) -> np.ndarray:
    """Escala de normalizacion de un conteo: raiz de su nivel esperado.

    Se acota en 1 para que una prediccion cercana a cero no produzca escalas
    diminutas y residuos normalizados artificialmente enormes.
    """
    return np.sqrt(np.maximum(prediccion, 1.0))


class ConformalWrapper:
    """Envuelve un modelo con `fit_point` y reemplaza sus intervalos por conformes."""

    def __init__(
        self,
        base: PointForecaster,
        nivel: float = 0.80,
        calibracion_periodos: int = CALIBRACION_PERIODOS,
        name: str | None = None,
    ) -> None:
        if not isinstance(base, PointForecaster):
            raise TypeError(
                f"El modelo '{getattr(base, 'name', base)}' no implementa `fit_point`; "
                "la prediccion conforme necesita pronosticar la ventana de calibracion."
            )
        self.base = base
        self.nivel = nivel
        self.calibracion_periodos = calibracion_periodos
        self.name = name or f"{base.name}_conformal"
        # Cuantiles del ultimo ajuste por grupo, para que el informe pueda
        # declarar con cuantos residuos se calibro cada nivel.
        self.ultima_calibracion: pd.DataFrame | None = None

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Pronostico puntual del modelo base con intervalo conforme por nivel."""
        train, objetivo, columnas = split_train_target(supervised, origin, horizon)
        if train.empty or objetivo.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior"])

        corte = origin - self.calibracion_periodos
        interno = train[train["t"] <= corte]
        ventana = train[train["t"] > corte]
        if interno.empty or ventana.empty:
            raise ValueError(
                f"Historia insuficiente para calibrar en el origen {origin}: se "
                f"necesitan mas de {self.calibracion_periodos} periodos de entrenamiento."
            )

        pred_calibracion = np.clip(self.base.fit_point(interno, ventana, columnas), 0.0, None)
        pred = np.clip(self.base.fit_point(train, objetivo, columnas), 0.0, None)

        residuos = (
            ventana["y"].to_numpy(dtype=float) - pred_calibracion
        ) / _escala(pred_calibracion)
        grupos_calibracion = ventana["nivel"].to_numpy()

        registros: list[dict[str, object]] = []
        cotas: dict[str, tuple[float, float]] = {}
        for grupo in pd.unique(grupos_calibracion):
            propios = residuos[grupos_calibracion == grupo]
            inferior, superior, valida = conformal_bounds(propios, self.nivel)
            cotas[str(grupo)] = (inferior, superior)
            registros.append(
                {
                    "nivel": grupo,
                    "residuos": len(propios),
                    "cuantil_inferior": inferior,
                    "cuantil_superior": superior,
                    "garantia_valida": valida,
                }
            )
        # Un nivel presente en el objetivo pero ausente en la calibracion (no
        # ocurre con paneles regulares) recibe los cuantiles de todos los
        # residuos juntos, en vez de quedar sin intervalo.
        global_inferior, global_superior, _ = conformal_bounds(residuos, self.nivel)
        self.ultima_calibracion = pd.DataFrame(registros)

        escala = _escala(pred)
        niveles = objetivo["nivel"].astype(str).to_numpy()
        inferior = np.array([cotas.get(n, (global_inferior, global_superior))[0] for n in niveles])
        superior = np.array([cotas.get(n, (global_inferior, global_superior))[1] for n in niveles])

        limite_inferior = np.maximum(0.0, pred + inferior * escala)
        # Si el cuantil superior fuera negativo y el inferior se truncara en 0,
        # el intervalo quedaria invertido; se impide explicitamente.
        limite_superior = np.maximum(pred + superior * escala, limite_inferior)
        return pd.DataFrame(
            {
                "series_id": objetivo["series_id"].to_numpy(),
                "y_pred": pred,
                "y_inferior": limite_inferior,
                "y_superior": limite_superior,
            }
        )
