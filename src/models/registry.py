"""Registro unico de las configuraciones de modelo evaluadas.

**Por que existe.** El benchmark elige un modelo por nombre y la evaluacion en
holdout (y a futuro la API) tiene que instanciar **exactamente** esa misma
configuracion. Si cada consumidor construyera sus modelos por su cuenta,
bastaria un hiperparametro distinto en uno de ellos para evaluar algo diferente
de lo que se selecciono, sin que nada lo delatara. Este modulo es la unica
fuente de verdad: un nombre -> una configuracion.

Solo registra modelos **construibles**, es decir, que se ajustan y pronostican
por si mismos sobre el panel de dos niveles. Las variantes que son
post-procesamiento de otro backtest (reconciliaciones aplicadas a posteriori,
hibridos de tres niveles armados desde dos backtests) no son un modelo que se
pueda desplegar tal cual y por eso no estan aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from src.models import RANDOM_SEED
from src.models.backtesting import DemandModel
from src.models.baseline import SeasonalNaive, SeasonalNaiveDrift
from src.models.conformal import ConformalWrapper
from src.models.gradient_boosting import LightGBMGlobal
from src.models.hybrid import HierarchicalHybrid
from src.models.linear_glm import PoissonGLMGlobal

HIBRIDO: Final[str] = "hibrido_glm_region_lgbm_comuna"


def _hibrido(nivel: float) -> HierarchicalHybrid:
    return HierarchicalHybrid(
        region_model=PoissonGLMGlobal(nivel=nivel),
        comuna_model=LightGBMGlobal(nivel=nivel, seed=RANDOM_SEED),
        reconciliacion="top_down",
        name=HIBRIDO,
    )


_FABRICAS: Final[dict[str, Callable[[float], DemandModel]]] = {
    "baseline_estacional": lambda n: SeasonalNaive(nivel=n),
    "baseline_estacional_drift": lambda n: SeasonalNaiveDrift(nivel=n),
    "poisson_glm_global": lambda n: PoissonGLMGlobal(nivel=n),
    "lightgbm_global": lambda n: LightGBMGlobal(nivel=n, seed=RANDOM_SEED),
    HIBRIDO: _hibrido,
    "poisson_glm_global_conformal": lambda n: ConformalWrapper(
        PoissonGLMGlobal(nivel=n), nivel=n
    ),
    "lightgbm_global_conformal": lambda n: ConformalWrapper(
        LightGBMGlobal(nivel=n, seed=RANDOM_SEED), nivel=n
    ),
    f"{HIBRIDO}_conformal": lambda n: ConformalWrapper(_hibrido(n), nivel=n),
}


def available_models() -> list[str]:
    """Nombres de los modelos construibles, en orden de registro."""
    return list(_FABRICAS)


def build_model(nombre: str, nivel: float = 0.80) -> DemandModel:
    """Instancia una configuracion registrada.

    Falla con un mensaje explicito si el nombre no es construible, en vez de
    devolver un modelo parecido: evaluar algo distinto de lo seleccionado es el
    error que este registro existe para impedir.
    """
    if nombre not in _FABRICAS:
        raise KeyError(
            f"Modelo no construible: '{nombre}'. Registrados: {available_models()}. "
            "Las variantes de post-procesamiento no se pueden instanciar por si solas."
        )
    modelo = _FABRICAS[nombre](nivel)
    if modelo.name != nombre:
        raise RuntimeError(
            f"Incoherencia del registro: '{nombre}' produjo un modelo llamado '{modelo.name}'."
        )
    return modelo
