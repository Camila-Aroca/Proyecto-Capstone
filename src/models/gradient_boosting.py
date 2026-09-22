"""Modelo global multi-serie con LightGBM sobre el panel jerarquico.

**Por que global y no un modelo por comuna.** El EDA de series mostro que el
baseline ingenuo tiene un MAPE mediano comunal ~3,5 veces peor que el de la
serie RM agregada, y que 4 comunas acumulan menos de 1.000 atenciones en cinco
anios. Ajustar 52 modelos independientes condenaria a las series pequenas a
estimar su estacionalidad con muy pocos eventos. Un unico modelo entrenado
sobre todas las series aprende la forma compartida de la demanda y la adapta a
cada territorio mediante sus propias features (escala, poblacion, rezagos), que
es la manera estandar de prestar fuerza entre series.

**Por que perdida de Poisson.** El target es un conteo no negativo con varianza
creciente en el nivel. La perdida cuadratica asumiria errores homocedasticos y
podria producir pronosticos negativos; el objetivo Poisson respeta el soporte y
la relacion media-varianza del conteo.

Los intervalos de prediccion son empiricos, **relativos** y **calibrados fuera
de muestra**:

- Relativos porque los residuos se expresan como fraccion del nivel ajustado,
  de modo que sean comparables entre series de escalas muy distintas (un error
  de 50 atenciones significa algo muy diferente en Recoleta que en Alhue).
- Calibrados fuera de muestra porque los residuos in-sample de un modelo de
  boosting son sistematicamente optimistas: usarlos producia intervalos
  demasiado estrechos, con cobertura observada muy por debajo del nivel nominal.
  Para evitarlo se reserva el tramo final del entrenamiento como ventana de
  calibracion, se ajusta un modelo sin verla y los cuantiles se estiman sobre
  esos residuos genuinamente fuera de muestra. El pronostico puntual si usa el
  modelo reajustado con toda la ventana de entrenamiento.
"""

from __future__ import annotations

from typing import Any, Final

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.models import RANDOM_SEED
from src.models.backtesting import empirical_interval, split_train_target

# Hiperparametros deliberadamente conservadores: el panel tiene ~10.000 filas
# utiles por horizonte, de modo que un modelo profundo sobreajustaria. No se
# ajustan por busqueda automatica en esta etapa; hacerlo exigiria una particion
# de validacion interna adicional dentro de cada origen del backtesting.
DEFAULT_PARAMS: Final[dict[str, Any]] = {
    "objective": "poisson",
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 40,
    "subsample": 0.9,
    "subsample_freq": 1,
    "colsample_bytree": 0.9,
    "reg_lambda": 1.0,
    "verbose": -1,
}

# Minimo de residuos relativos para estimar cuantiles por serie.
MIN_RESIDUOS_POR_SERIE: Final[int] = 20
# Periodos finales del entrenamiento reservados para calibrar los intervalos.
CALIBRACION_PERIODOS: Final[int] = 26


class LightGBMGlobal:
    """Modelo global de gradient boosting entrenado sobre todas las series."""

    name: str = "lightgbm_global"

    def __init__(
        self,
        nivel: float = 0.80,
        seed: int = RANDOM_SEED,
        params: dict[str, Any] | None = None,
        calibracion_periodos: int = CALIBRACION_PERIODOS,
    ) -> None:
        self.nivel = nivel
        self.seed = seed
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        # Semilla explicita: el submuestreo de filas y columnas es estocastico y
        # sin fijarla el backtesting no seria reproducible entre ejecuciones.
        self.params["random_state"] = seed
        self.calibracion_periodos = calibracion_periodos
        self.ultimo_modelo: LGBMRegressor | None = None
        self.ultimas_features: list[str] = []
        # Queda registrado si los intervalos debieron caer al modo in-sample por
        # falta de historia, para que el informe pueda declararlo.
        self.calibracion_fuera_de_muestra: bool = False

    def _encode_series(self, frame: pd.DataFrame, categorias: pd.Index) -> pd.Series:
        """Codifica `series_id` como categoria con un dominio fijo.

        El dominio se fija desde el entrenamiento para que la fila objetivo use
        exactamente los mismos codigos; sin esto, una serie ausente del objetivo
        desplazaria la codificacion y el modelo leeria la comuna equivocada.
        """
        return pd.Categorical(frame["series_id"], categories=categorias).codes

    def _disenio(
        self, frame: pd.DataFrame, columnas: list[str], categorias: pd.Index
    ) -> pd.DataFrame:
        """Matriz de entrada: features numericas + codigo categorico de la serie."""
        X = frame[columnas].copy()
        X["series_code"] = self._encode_series(frame, categorias)
        return X

    def _ajustar(
        self, train: pd.DataFrame, columnas: list[str]
    ) -> tuple[LGBMRegressor, pd.Index]:
        """Ajusta un booster sobre `train`; devuelve el modelo y su dominio de series."""
        categorias = pd.Index(sorted(train["series_id"].unique()))
        modelo = LGBMRegressor(**self.params)
        modelo.fit(
            self._disenio(train, columnas, categorias),
            train["y"].to_numpy(dtype=float),
            categorical_feature=["series_code"],
        )
        return modelo, categorias

    def fit_point(
        self, train: pd.DataFrame, target: pd.DataFrame, columns: list[str]
    ) -> np.ndarray:
        """Ajusta con `train` y devuelve el pronostico puntual de cada fila de `target`.

        Un conteo no puede ser negativo; el objetivo Poisson ya lo garantiza, pero
        el truncamiento deja la invariante explicita ante cambios de objetivo.
        """
        modelo, categorias = self._ajustar(train, columns)
        return np.clip(modelo.predict(self._disenio(target, columns, categorias)), 0.0, None)

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Entrena con `t <= origin` y pronostica `origin + horizon` para cada serie."""
        train, objetivo, columnas = split_train_target(supervised, origin, horizon)
        if objetivo.empty or train.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior"])

        modelo, categorias = self._ajustar(train, columnas)
        X_train = self._disenio(train, columnas, categorias)
        self.ultimo_modelo = modelo
        self.ultimas_features = list(X_train.columns)
        predicciones = np.clip(
            modelo.predict(self._disenio(objetivo, columnas, categorias)), 0.0, None
        )

        residuos_relativos, serie_train = self._residuos_calibracion(
            train, columnas, modelo, X_train
        )

        registros: list[dict[str, object]] = []
        for serie, prediccion in zip(objetivo["series_id"].to_numpy(), predicciones):
            propios = residuos_relativos[serie_train == serie]
            residuos = (
                propios if len(propios) >= MIN_RESIDUOS_POR_SERIE else residuos_relativos
            )
            inferior, superior = empirical_interval(residuos, self.nivel)
            registros.append(
                {
                    "series_id": serie,
                    "y_pred": float(prediccion),
                    "y_inferior": float(max(0.0, prediccion * (1 + inferior))),
                    "y_superior": float(prediccion * (1 + superior)),
                }
            )
        return pd.DataFrame(registros)

    def _residuos_calibracion(
        self,
        train: pd.DataFrame,
        columnas: list[str],
        modelo_completo: LGBMRegressor,
        X_train: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Estima residuos relativos fuera de muestra para calibrar intervalos.

        Reserva los ultimos `calibracion_periodos` del entrenamiento, ajusta un
        modelo que no los ve y mide su error ahi. Esos residuos si representan el
        desempeno de pronostico; los in-sample de un boosting no, porque el
        modelo ya minimizo el error sobre ellos.

        Si la historia no alcanza para dejar una ventana de calibracion con datos
        suficientes, cae a los residuos in-sample y lo deja registrado en
        `calibracion_fuera_de_muestra` en vez de fingir una calibracion que no se
        hizo.
        """
        corte = int(train["t"].max()) - self.calibracion_periodos
        ajuste_interno = train["t"] <= corte
        ventana = ~ajuste_interno

        if ajuste_interno.sum() < MIN_RESIDUOS_POR_SERIE or ventana.sum() == 0:
            self.calibracion_fuera_de_muestra = False
            y_train = train["y"].to_numpy(dtype=float)
            ajuste = np.clip(modelo_completo.predict(X_train), 1e-6, None)
            return (y_train - ajuste) / ajuste, train["series_id"].to_numpy()

        calibracion = train[ventana]
        ajuste_cal = np.clip(
            self.fit_point(train[ajuste_interno], calibracion, columnas), 1e-6, None
        )
        self.calibracion_fuera_de_muestra = True
        return (
            (calibracion["y"].to_numpy(dtype=float) - ajuste_cal) / ajuste_cal,
            calibracion["series_id"].to_numpy(),
        )

    def feature_importances(self) -> pd.DataFrame:
        """Importancia por ganancia del ultimo ajuste, para lectura del modelo.

        Se expone porque el producto debe poder explicar en que se apoya el
        pronostico; un modelo que no se puede interpretar no es defendible ante
        un usuario de planificacion sanitaria.
        """
        if self.ultimo_modelo is None:
            raise ValueError("El modelo no ha sido ajustado todavia.")
        importancias = self.ultimo_modelo.booster_.feature_importance(importance_type="gain")
        return (
            pd.DataFrame({"feature": self.ultimas_features, "ganancia": importancias})
            .sort_values("ganancia", ascending=False)
            .reset_index(drop=True)
        )
