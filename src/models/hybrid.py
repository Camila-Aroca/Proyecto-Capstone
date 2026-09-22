"""Modelo jerarquico hibrido: un modelo por nivel, reconciliados.

**El problema que resuelve.** El benchmark mostro que ningun modelo domina en
todos los niveles de la jerarquia: el GLM de Poisson es mejor en la serie
regional agregada y el boosting es mejor en el detalle comunal. Obligarse a
elegir uno solo significa aceptar el peor desempeno en uno de los niveles,
cuando el producto necesita un indicador regional y un mapa comunal.

El hibrido toma el pronostico regional del modelo que gana en region y el de
todos los niveles subregionales (Servicios de Salud, si existen, y comunas) del
que gana en detalle, y despues los reconcilia.

**Por que top-down por defecto.** `bottom_up` redefine el total regional como
la suma de las comunas, lo que descartaria por completo el pronostico regional
del GLM: exactamente el componente que este diseno quiere conservar. `top_down`
mantiene el total del modelo regional y lo reparte segun las proporciones que el
modelo de detalle asigno a cada territorio.

La composicion es generica: recibe dos modelos que cumplan `DemandModel`, no dos
clases concretas. Cambiar cualquiera de los dos no exige tocar este modulo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.backtesting import DemandModel, PointForecaster
from src.models.features import RM_SERIES_ID
from src.models.hierarchy import RECONCILIACIONES

COLUMNAS_ESTRUCTURA: tuple[str, ...] = ("nivel", "servicio_id")


def select_by_level(
    pred_region: pd.DataFrame, pred_detalle: pd.DataFrame
) -> pd.DataFrame:
    """Toma la fila regional de un modelo y todas las demas del otro.

    Sirve tanto dentro del hibrido como para combinar resultados de backtesting
    ya calculados sin volver a entrenar: dado que ambos modelos son
    deterministas, combinar sus predicciones produce exactamente lo mismo que
    reentrenarlos dentro del hibrido.
    """
    return pd.concat(
        [
            pred_region[pred_region["series_id"] == RM_SERIES_ID],
            pred_detalle[pred_detalle["series_id"] != RM_SERIES_ID],
        ],
        ignore_index=True,
    )


def _estructura(frame: pd.DataFrame) -> pd.DataFrame:
    """Posicion jerarquica de cada serie, tal como viene del panel."""
    columnas = [c for c in COLUMNAS_ESTRUCTURA if c in frame.columns]
    return frame[["series_id", *columnas]].drop_duplicates("series_id")


class HierarchicalHybrid:
    """Combina un modelo para el agregado regional y otro para el detalle."""

    def __init__(
        self,
        region_model: DemandModel,
        comuna_model: DemandModel,
        reconciliacion: str = "top_down",
        name: str | None = None,
    ) -> None:
        if reconciliacion not in RECONCILIACIONES:
            raise ValueError(
                f"Reconciliacion no soportada: {reconciliacion}. "
                f"Opciones: {sorted(RECONCILIACIONES)}"
            )
        self.region_model = region_model
        self.comuna_model = comuna_model
        self.reconciliacion = reconciliacion
        self.name = name or (
            f"hibrido_{region_model.name}_{comuna_model.name}_{reconciliacion}"
        )

    def _reconciliar(
        self, combinado: pd.DataFrame, estructura: pd.DataFrame
    ) -> pd.DataFrame:
        """Adjunta la estructura jerarquica y aplica la reconciliacion elegida."""
        con_estructura = combinado.drop(
            columns=[c for c in COLUMNAS_ESTRUCTURA if c in combinado.columns]
        ).merge(estructura, on="series_id", how="left", validate="many_to_one")
        return RECONCILIACIONES[self.reconciliacion](con_estructura)

    def fit_predict(
        self, supervised: pd.DataFrame, origin: int, horizon: int
    ) -> pd.DataFrame:
        """Ajusta ambos modelos, toma de cada uno su nivel y reconcilia.

        Los dos modelos se entrenan sobre el panel completo --no sobre su nivel
        aislado-- porque ambos son globales y aprenden de todas las series. Lo
        que se selecciona por nivel es el **pronostico**, no el entrenamiento.
        """
        pred_region = self.region_model.fit_predict(supervised, origin, horizon)
        pred_detalle = self.comuna_model.fit_predict(supervised, origin, horizon)
        if pred_region.empty or pred_detalle.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior"])

        combinado = select_by_level(pred_region, pred_detalle)
        # Las funciones de reconciliacion agrupan por (origen, horizonte) porque
        # operan sobre resultados de backtesting completos. Aqui se trabaja sobre
        # un unico pronostico, asi que las claves se agregan temporalmente y se
        # retiran antes de devolver, para no alterar el contrato del protocolo.
        combinado["origen"] = origin
        combinado["horizonte"] = horizon
        reconciliado = self._reconciliar(combinado, _estructura(supervised))
        return reconciliado.drop(columns=["origen", "horizonte"]).reset_index(drop=True)

    def fit_point(
        self, train: pd.DataFrame, target: pd.DataFrame, columns: list[str]
    ) -> np.ndarray:
        """Pronostico puntual reconciliado para filas arbitrarias de `target`.

        `target` puede abarcar varios periodos (la ventana de calibracion de la
        prediccion conforme); la reconciliacion se aplica por separado a cada
        periodo, porque la coherencia es una restriccion dentro de un mismo
        instante, no entre instantes distintos.
        """
        for modelo in (self.region_model, self.comuna_model):
            if not isinstance(modelo, PointForecaster):
                raise TypeError(
                    f"El modelo '{modelo.name}' no implementa `fit_point`; el hibrido "
                    "no puede producir pronosticos puntuales por lotes."
                )

        es_region = (target["series_id"] == RM_SERIES_ID).to_numpy()
        pred = np.zeros(len(target), dtype=float)
        if es_region.any():
            pred[es_region] = self.region_model.fit_point(train, target[es_region], columns)
        if (~es_region).any():
            pred[~es_region] = self.comuna_model.fit_point(train, target[~es_region], columns)

        combinado = target[["series_id", "t"]].copy()
        combinado["y_pred"] = pred
        # El periodo hace de clave del pronostico: cada instante se reconcilia solo.
        combinado["origen"] = combinado["t"]
        combinado["horizonte"] = 0
        reconciliado = self._reconciliar(combinado, _estructura(target))

        alineado = reconciliado.set_index(["series_id", "t"])["y_pred"]
        return alineado.reindex(
            pd.MultiIndex.from_frame(target[["series_id", "t"]])
        ).to_numpy(dtype=float)


def reconcile_combined_backtest(
    pred_region: pd.DataFrame,
    pred_detalle: pd.DataFrame,
    reconciliacion: str,
    nombre: str,
) -> pd.DataFrame:
    """Construye el backtest de un hibrido desde dos backtests ya ejecutados.

    Evita reentrenar: combina por nivel las predicciones existentes y aplica la
    reconciliacion. Requiere que ambos backtests provengan del mismo panel y de
    los mismos origenes y horizontes.
    """
    combinado = select_by_level(pred_region, pred_detalle)
    reconciliado = RECONCILIACIONES[reconciliacion](combinado)
    reconciliado["modelo"] = nombre
    return reconciliado.reset_index(drop=True)


__all__ = ["HierarchicalHybrid", "reconcile_combined_backtest", "select_by_level"]
