"""GLM de Poisson global sobre el panel jerarquico.

**Por que este modelo merece estar en el benchmark.** Una ablacion sobre las
mismas features mostro que la mayor parte de la mejora frente al baseline
proviene de la ingenieria de features y no del algoritmo: un GLM lineal captura
casi toda esa ganancia a nivel comunal y **supera** al modelo de boosting en la
serie regional agregada, que es la cifra titular del producto. Un modelo que
iguala o mejora el desempeno con una fraccion de la complejidad es la opcion
por defecto correcta; el modelo complejo debe justificar su costo, no al reves.

Ventajas concretas en este proyecto:

- **Intervalos derivados del proceso de error**, no parcheados con cuantiles
  empiricos. El GLM modela la media condicional de un conteo y su dispersion se
  estima explicitamente, de modo que el intervalo tiene una interpretacion
  distribucional.
- **Interpretabilidad**: los coeficientes son legibles por un equipo de
  planificacion sanitaria, que es el usuario del producto.
- **Costo**: se ajusta en una fraccion del tiempo del boosting y no tiene
  hiperparametros que justificar ante una comision academica.

**Sobredispersion, estimada por serie.** Un Poisson puro asume varianza igual a
la media, supuesto que rara vez se cumple en demanda de urgencias. Se estima el
parametro de dispersion de Pearson sobre una ventana de calibracion fuera de
muestra y, si hay sobredispersion, los intervalos se construyen con una binomial
negativa de media `mu` y varianza `phi * mu`.

La dispersion se estima **por serie**, no agrupada. Una unica dispersion comun
fallaba precisamente donde mas importa: el agregado regional es la suma de 51
series y su varianza relativa a la media no tiene por que parecerse a la de una
comuna individual, de modo que un `phi` promediado producia intervalos
regionales demasiado estrechos. Las series sin suficientes puntos de
calibracion caen al valor agrupado en vez de estimar con un punado de datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler

from src.models.backtesting import split_train_target

# Regularizacion debil: hay ~10.000 filas y ~70 columnas tras el one-hot, de
# modo que el problema no es de alta dimension, pero un ridge minimo estabiliza
# la estimacion cuando dos rezagos consecutivos son casi colineales.
DEFAULT_ALPHA: Final[float] = 1e-4
DEFAULT_MAX_ITER: Final[int] = 20_000
# Periodos finales del entrenamiento reservados para estimar la dispersion.
CALIBRACION_PERIODOS: Final[int] = 26
# Minimo de puntos de calibracion para estimar la dispersion de una serie.
MIN_PUNTOS_DISPERSION: Final[int] = 10


@dataclass(frozen=True)
class _GLMAjustado:
    """Todo lo necesario para predecir con un GLM ya ajustado."""

    dominio: pd.Index
    escalador: StandardScaler
    modelo: PoissonRegressor


class PoissonGLMGlobal:
    """GLM de Poisson global con intervalos ajustados por sobredispersion."""

    name: str = "poisson_glm_global"

    def __init__(
        self,
        nivel: float = 0.80,
        alpha: float = DEFAULT_ALPHA,
        max_iter: int = DEFAULT_MAX_ITER,
        calibracion_periodos: int = CALIBRACION_PERIODOS,
        min_puntos_dispersion: int = MIN_PUNTOS_DISPERSION,
    ) -> None:
        self.nivel = nivel
        self.alpha = alpha
        self.max_iter = max_iter
        self.calibracion_periodos = calibracion_periodos
        self.min_puntos_dispersion = min_puntos_dispersion
        # Dispersion del ultimo ajuste; 1.0 significa Poisson puro.
        self.dispersion_por_serie: dict[str, float] = {}
        self.dispersion_agrupada: float = 1.0
        self.coeficientes: pd.DataFrame | None = None

    def _matriz(
        self, frame: pd.DataFrame, columnas: list[str], dominio: pd.Index
    ) -> np.ndarray:
        """Arma la matriz de diseno: features numericas + one-hot de la serie.

        El dominio de series se fija desde el entrenamiento y se reindexa en el
        objetivo, para que una serie ausente no desplace las columnas y el
        modelo termine leyendo el territorio equivocado.
        """
        dummies = (
            pd.get_dummies(frame["series_id"], prefix="s")
            .reindex(columns=dominio, fill_value=0)
            .to_numpy(dtype=float)
        )
        return np.hstack([frame[columnas].to_numpy(dtype=float), dummies])

    def _ajustar(self, train: pd.DataFrame, columnas: list[str]) -> _GLMAjustado:
        """Ajusta el GLM sobre `train` con escalado y one-hot de la serie.

        El dominio de series sale del propio entrenamiento: las filas a predecir
        se reindexan contra el, nunca al reves.
        """
        dominio = pd.Index(sorted(f"s_{s}" for s in train["series_id"].unique()))
        X = self._matriz(train, columnas, dominio)
        escalador = StandardScaler().fit(X)
        modelo = PoissonRegressor(alpha=self.alpha, max_iter=self.max_iter)
        modelo.fit(escalador.transform(X), train["y"].to_numpy(dtype=float))
        return _GLMAjustado(dominio=dominio, escalador=escalador, modelo=modelo)

    def _predecir(
        self, ajustado: _GLMAjustado, frame: pd.DataFrame, columnas: list[str]
    ) -> np.ndarray:
        """Media condicional predicha, truncada en 0 porque es un conteo."""
        X = ajustado.escalador.transform(self._matriz(frame, columnas, ajustado.dominio))
        return np.clip(ajustado.modelo.predict(X), 0.0, None)

    def fit_point(
        self, train: pd.DataFrame, target: pd.DataFrame, columns: list[str]
    ) -> np.ndarray:
        """Ajusta con `train` y devuelve la media predicha para cada fila de `target`."""
        return self._predecir(self._ajustar(train, columns), target, columns)

    def _estimar_dispersion(
        self,
        train: pd.DataFrame,
        columnas: list[str],
    ) -> tuple[dict[str, float], float]:
        """Estima la dispersion de Pearson por serie, fuera de muestra.

        Ajusta un modelo sin ver la ventana final del entrenamiento y mide ahi
        `mean((y - mu)^2 / mu)` para cada serie. Estimarla in-sample la
        subestimaria, porque el modelo ya minimizo su desviacion sobre esos
        mismos puntos.

        Devuelve el mapa por serie y el valor agrupado, que sirve de respaldo
        para las series con pocos puntos de calibracion.
        """
        corte = int(train["t"].max()) - self.calibracion_periodos
        interno = train[train["t"] <= corte]
        ventana = train[train["t"] > corte]
        if len(interno) < len(columnas) + 1 or ventana.empty:
            return {}, 1.0

        mu = np.clip(self.fit_point(interno, ventana, columnas), 1e-6, None)
        residuo_pearson = (ventana["y"].to_numpy(dtype=float) - mu) ** 2 / mu
        # Una dispersion menor que 1 (subdispersion) no se corrige: se deja en
        # Poisson puro en vez de estrechar artificialmente los intervalos.
        agrupada = max(1.0, float(np.mean(residuo_pearson)))

        por_serie = (
            pd.DataFrame(
                {"series_id": ventana["series_id"].to_numpy(), "pearson": residuo_pearson}
            )
            .groupby("series_id")["pearson"]
            .agg(["mean", "size"])
        )
        suficientes = por_serie[por_serie["size"] >= self.min_puntos_dispersion]
        return (
            {serie: max(1.0, float(v)) for serie, v in suficientes["mean"].items()},
            agrupada,
        )

    def _intervalo(
        self, mu: np.ndarray, dispersiones: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Cuantiles predictivos para conteos, con dispersion propia de cada serie."""
        alfa = (1 - self.nivel) / 2
        inferior = np.empty_like(mu, dtype=float)
        superior = np.empty_like(mu, dtype=float)

        # Sin sobredispersion la binomial negativa degenera; se usa Poisson.
        poisson_puro = dispersiones <= 1.0
        if poisson_puro.any():
            inferior[poisson_puro] = stats.poisson.ppf(alfa, mu[poisson_puro])
            superior[poisson_puro] = stats.poisson.ppf(1 - alfa, mu[poisson_puro])

        negbin = ~poisson_puro
        if negbin.any():
            # Binomial negativa con media `mu` y varianza `phi * mu`.
            phi = dispersiones[negbin]
            p = 1.0 / phi
            n = mu[negbin] / (phi - 1.0)
            inferior[negbin] = stats.nbinom.ppf(alfa, n, p)
            superior[negbin] = stats.nbinom.ppf(1 - alfa, n, p)
        return inferior, superior

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Entrena con `t <= origin` y pronostica `origin + horizon`."""
        train, objetivo, columnas = split_train_target(supervised, origin, horizon)
        if train.empty or objetivo.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior"])

        ajustado = self._ajustar(train, columnas)
        self.dispersion_por_serie, self.dispersion_agrupada = self._estimar_dispersion(
            train, columnas
        )
        self.coeficientes = pd.DataFrame(
            {
                "termino": columnas + list(ajustado.dominio),
                "coeficiente": np.round(ajustado.modelo.coef_, 5),
            }
        )

        mu = self._predecir(ajustado, objetivo, columnas)
        series = objetivo["series_id"].to_numpy()
        dispersiones = np.array(
            [
                self.dispersion_por_serie.get(s, self.dispersion_agrupada)
                for s in series
            ]
        )
        inferior, superior = self._intervalo(np.clip(mu, 1e-6, None), dispersiones)
        return pd.DataFrame(
            {
                "series_id": series,
                "y_pred": mu,
                "y_inferior": np.maximum(0.0, inferior),
                "y_superior": superior,
            }
        )
