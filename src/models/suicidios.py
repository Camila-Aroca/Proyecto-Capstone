"""Pronóstico semanal de suicidios de residentes RM (región y comunas).

Reutiliza el motor del modelo de demanda (matriz supervisada directa, backtesting con
origen deslizante, modelos del registro, pronóstico con filas marcadoras) sobre el
panel de `mart_suicidios_comuna_weekly`. Lo propio de este objetivo es **el tipo de
serie**: conteos escasos. La RM registra del orden de 10 suicidios por semana y una
comuna, en mediana, 0,2; cuatro de cada cinco comuna-semanas son cero (EDA del mart).

Eso cambia dos cosas, ambas con evidencia en `reports/eda/eda_mart_suicidios_comuna_weekly.md`:

1. **El modelo.** En 2022-2025, con nivel anual y un armónico estacional, la serie
   regional tiene dispersión de Pearson ~1 y residuos sin autocorrelación: lo
   predecible es el nivel y la estación, no las semanas recientes. Las comunas
   difieren en su tasa más de lo que explica el azar, pero con tan pocos casos su
   tasa propia es ruidosa. `PoissonEstacionalJerarquico` modela exactamente eso:
   un GLM de Poisson regional con estacionalidad anual y nivel ponderado en el
   tiempo (vida media), y un reparto top-down a comunas con tasas de Bayes empírico
   (Gamma-Poisson) contraídas hacia la tasa regional por habitante. La suma de las
   comunas es la región: el pronóstico es coherente por construcción.
2. **La métrica de selección.** Con series casi siempre en cero, el error absoluto
   (MAE, MASE) premia pronosticar cero: la mediana de cada comuna-semana es 0. El
   error cuadrático lo minimiza la media, que es lo que se quiere estimar; por eso
   la regla elige por **RMSSE** (error cuadrático escalado por el del baseline
   estacional, la métrica de la competencia M5 para series intermitentes). MASE se
   informa para que las tablas se lean igual que las del modelo de demanda.

**Intervalos de conteos.** Un intervalo de enteros no puede cubrir exactamente 80%:
con media 0,2, [0, 1] cubre ~98%. La calibración se juzga contra la cobertura que el
propio modelo declara para cada intervalo (`cobertura_esperada`), y contra el 80%
nominal en los modelos que no declaran una distribución.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import optimize, special, stats
from sklearn.linear_model import PoissonRegressor

from src.chile_time import run_datetime_chile
from src.data.build_mart_suicidios_comuna_weekly import OUTPUT_PATH as MART_PATH
from src.data.build_mart_suicidios_comuna_weekly import SEMANA_FRAGMENTO, calendario_deis
from src.data.raw_provenance import file_sha256
from src.models import RANDOM_SEED
from src.models.backtesting import DemandModel
from src.models.features import RM_SERIES_ID, SEASONAL_PERIOD, _add_time_index, build_supervised_frame
from src.models.forecast import append_future_rows
from src.models.metrics import coverage_tolerance, seasonal_naive_scale
from src.models.persistence import PAQUETES_REGISTRADOS, _version
from src.models.registry import build_model as build_registry_model

NOMBRE_REGION: Final[str] = "Región Metropolitana"
NIVEL_COMUNA: Final[str] = "comuna"
# 2020-2021 tienen un nivel 25% menor que 2022-2025 (prueba binomial exacta en el
# EDA); la causa no es determinable con estos datos. Como en el modelo por
# establecimiento, la ventana empieza en 2022.
ANO_INICIO: Final[int] = 2022
HORIZONTES: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8)
NIVEL_INTERVALO: Final[float] = 0.80
N_ORIGENES: Final[int] = 13
PASO: Final[int] = 4
REFERENCIA: Final[str] = "baseline_estacional"
REFERENCIA_CERO: Final[str] = "referencia_cero"
# Un armónico: el segundo y el tercero no mejoran la verosimilitud en 2022-2025 (EDA).
ARMONICOS: Final[int] = 1
VIDAS_MEDIAS: Final[tuple[int, ...]] = (26, 52, 104)
NIVELES: Final[tuple[str, str]] = ("region", NIVEL_COMUNA)

DIRECTORIO: Final[Path] = Path("data/processed/modeling")
RUTA_PRONOSTICO: Final[Path] = DIRECTORIO / "pronostico_suicidios.parquet"
RUTA_MANIFIESTO: Final[Path] = DIRECTORIO / "pronostico_suicidios_manifest.json"
RUTA_SELECCION: Final[Path] = Path("reports/modeling/benchmark_suicidios_seleccion.json")
RUTA_HOLDOUT_RESUMEN: Final[Path] = Path("reports/modeling/holdout_suicidios_resumen.csv")
CLAVE_MART: Final[str] = "mart_suicidios_comuna_weekly"
CLAVE_SELECCION: Final[str] = "seleccion_benchmark"

ESQUEMA: Final[pa.Schema] = pa.schema([
    ("series_id", pa.string()),
    ("nombre", pa.string()),
    ("nivel", pa.string()),
    ("horizonte", pa.int16()),
    ("origen", pa.int32()),
    ("t", pa.int32()),
    ("ano", pa.int16()),
    ("semana", pa.int16()),
    ("fecha_inicio_semana", pa.date32()),
    ("y_pred", pa.float64()),
    ("y_inferior", pa.float64()),
    ("y_superior", pa.float64()),
    ("cobertura_esperada", pa.float64()),
    ("poblacion_anual", pa.float64()),
    ("modelo", pa.string()),
])


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

def load_mart(path: Path = MART_PATH) -> pd.DataFrame:
    return pq.read_table(path).to_pandas()


def ultimo_ano_cerrado(mart: pd.DataFrame) -> int:
    """Último año con todos sus días publicados: el que tiene una semana terminada el 31-12."""
    fines = pd.to_datetime(mart["fecha_fin_semana"])
    cerrados = mart.loc[(fines.dt.month == 12) & (fines.dt.day == 31), "ano"]
    if cerrados.empty:
        raise ValueError("El mart no tiene ningún año completo.")
    return int(cerrados.max())


def build_panel(mart: pd.DataFrame, ano_inicio: int = ANO_INICIO, hasta_ano: int | None = None) -> pd.DataFrame:
    """Panel `series_id x t`: la región (suma de las 52 comunas) y cada comuna.

    Solo semanas regulares (la 53 es un fragmento, como en el modelo de demanda) con
    registro completo. Una semana con registro incompleto solo puede estar al final:
    en medio de la serie rompería la grilla de rezagos y no se imputa.
    """
    regular = mart[(mart["ano"] >= ano_inicio) & (mart["semana"] != SEMANA_FRAGMENTO)]
    if hasta_ano is not None:
        regular = regular[regular["ano"] <= hasta_ano]
    semanas = regular[["ano", "semana", "fecha_inicio_semana", "registro_completo"]].drop_duplicates(
        ["ano", "semana"]).sort_values("fecha_inicio_semana").reset_index(drop=True)
    incompletas = np.flatnonzero(~semanas["registro_completo"].to_numpy())
    if len(incompletas) and incompletas.min() != len(semanas) - len(incompletas):
        raise ValueError("Hay semanas con registro incompleto en medio de la serie, no solo al final.")
    regular = regular[regular["registro_completo"]]

    comunas = regular.rename(columns={"comuna_codigo": "series_id", "suicidios": "y"}).assign(nivel=NIVEL_COMUNA)
    region = regular.groupby(["ano", "semana"], as_index=False).agg(
        y=("suicidios", "sum"), dias_semana=("dias_semana", "first"), poblacion_anual=("poblacion_anual", "sum"))
    region = region.assign(series_id=RM_SERIES_ID, comuna_glosa=NOMBRE_REGION, nivel="region")
    panel = _add_time_index(pd.concat([comunas, region], ignore_index=True)).sort_values(["series_id", "t"])
    if panel.duplicated(["series_id", "t"]).any() or panel.groupby("series_id")["t"].size().nunique() != 1:
        raise ValueError("Panel de suicidios con grano duplicado o series de distinta longitud.")
    columnas = ["series_id", "nivel", "comuna_glosa", "t", "ano", "semana", "y", "dias_semana", "poblacion_anual"]
    panel = panel[columnas].reset_index(drop=True)
    panel["dias_semana"] = panel["dias_semana"].astype(float)
    panel["poblacion_anual"] = panel["poblacion_anual"].astype(float)
    return panel


def calendario(mart: pd.DataFrame, semanas_extra: int = 0) -> pd.DataFrame:
    """Fecha de inicio y días de cada semana DEIS observada y de las `semanas_extra` siguientes."""
    observado = mart[["ano", "semana", "fecha_inicio_semana", "dias_semana"]].drop_duplicates(["ano", "semana"])
    if semanas_extra:
        ultimo = max(mart["fecha_fin_semana"])
        futuro = calendario_deis(ultimo + pd.Timedelta(days=1).to_pytimedelta(),
                                 ultimo + pd.Timedelta(days=7 * semanas_extra + 14).to_pytimedelta())
        observado = pd.concat([observado, futuro[observado.columns]], ignore_index=True)
    return observado.drop_duplicates(["ano", "semana"]).assign(
        fecha_inicio_semana=lambda d: pd.to_datetime(d["fecha_inicio_semana"]))


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

def _fourier(semana: np.ndarray, armonicos: int) -> np.ndarray:
    angulo = 2 * np.pi * np.asarray(semana, dtype=float) / SEASONAL_PERIOD
    columnas = [f(k * angulo) for k in range(1, armonicos + 1) for f in (np.sin, np.cos)]
    return np.column_stack(columnas) if columnas else np.zeros((len(angulo), 0))


def forma_gamma(conteos: np.ndarray, esperados: np.ndarray) -> float:
    """Forma `a` de las tasas relativas comunales RR ~ Gamma(a, a), por máxima verosimilitud marginal.

    Con `n_c ~ Poisson(E_c RR_c)`, la marginal es binomial negativa. Una `a` grande
    significa que las comunas no difieren más que por azar (contracción total a la
    tasa regional); chica, que sus tasas propias son informativas. Acepta conteos
    ponderados (no enteros): la ponderación temporal da recuentos efectivos.
    """
    n, e = np.asarray(conteos, dtype=float), np.clip(np.asarray(esperados, dtype=float), 1e-9, None)

    def negativa(log_a: float) -> float:
        a = np.exp(log_a)
        return -float(np.sum(special.gammaln(n + a) - special.gammaln(a) + a * np.log(a / (a + e))
                             + n * np.log(e / (a + e))))

    return float(np.exp(optimize.minimize_scalar(negativa, bounds=(-3.0, 12.0), method="bounded").x))


def cuantiles_conteo(mu: np.ndarray, dispersion: float, nivel: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Intervalo central de un conteo (Poisson, o binomial negativa si hay sobredispersión).

    Devuelve los límites y la probabilidad que el modelo asigna al intervalo cerrado
    [inferior, superior], que en un conteo es mayor o igual al nivel nominal.
    """
    mu = np.clip(np.asarray(mu, dtype=float), 1e-9, None)
    alfa = (1 - nivel) / 2
    if dispersion <= 1.0:
        dist = stats.poisson(mu)
    else:
        dist = stats.nbinom(mu / (dispersion - 1.0), 1.0 / dispersion)
    inferior, superior = dist.ppf(alfa), dist.ppf(1 - alfa)
    cobertura = dist.cdf(superior) - dist.cdf(inferior - 1)
    return inferior, superior, cobertura


class PoissonEstacionalJerarquico:
    """GLM de Poisson regional estacional + reparto comunal de Bayes empírico.

    - Región: `log E[y_t] = log(dias_t / 7) + b0 + sum_k (a_k sin + c_k cos)(2 pi k semana / 52)`,
      ajustado con pesos `0,5 ** ((origen - t) / vida_media)`: el nivel sigue los años
      recientes (2022-2025 no son homogéneos) sin perder la forma estacional.
    - Comunas: `E[y_ct] = E[y_t] * p_c`, con `p_c` proporcional a
      `poblacion_c * (n_c + a) / (E_c + a)`: la tasa relativa de la comuna contraída
      hacia 1 según cuántos casos aporta (`n_c` y `E_c` ponderados igual que la región).
      Con `contraccion=False`, `p_c` es la participación en la población (ablación).
    - Intervalo: Poisson, o binomial negativa con la dispersión de Pearson de cada
      nivel dentro del entrenamiento si es mayor que 1.
    """

    def __init__(self, nivel: float = NIVEL_INTERVALO, vida_media: float | None = 52,
                 armonicos: int = ARMONICOS, contraccion: bool = True, name: str | None = None) -> None:
        self.nivel = nivel
        self.vida_media = vida_media
        self.armonicos = armonicos
        self.contraccion = contraccion
        sufijo = "eb" if contraccion else "poblacion"
        self.name = name or f"poisson_estacional_{sufijo}_vm{vida_media or 'inf'}"
        self.diagnostico: dict[str, float] = {}

    def _pesos(self, t: np.ndarray, origen: int) -> np.ndarray:
        if self.vida_media is None:
            return np.ones(len(t))
        return 0.5 ** ((origen - np.asarray(t, dtype=float)) / self.vida_media)

    def _ajustar_region(self, region: pd.DataFrame, origen: int) -> tuple[PoissonRegressor, float]:
        exposicion = region["dias_semana"].to_numpy(dtype=float) / 7.0
        pesos = self._pesos(region["t"].to_numpy(), origen)
        X = _fourier(region["semana"].to_numpy(), self.armonicos)
        if X.shape[1] == 0:
            X = np.zeros((len(region), 1))
        y = region["y"].to_numpy(dtype=float)
        # Poisson con exposición: ajustar la tasa y / e con peso w * e es exactamente la
        # verosimilitud de y ~ Poisson(e * tasa) (scikit-learn no tiene offset).
        modelo = PoissonRegressor(alpha=0.0, max_iter=5000).fit(X, y / exposicion, sample_weight=pesos * exposicion)
        mu = modelo.predict(X) * exposicion
        parametros = X.shape[1] + 1
        dispersion = float(np.sum(pesos * (y - mu) ** 2 / mu) / max(np.sum(pesos) - parametros, 1.0))
        return modelo, max(1.0, dispersion)

    def _participaciones(self, comunas: pd.DataFrame, origen: int) -> pd.Series:
        pesos = self._pesos(comunas["t"].to_numpy(), origen)
        conteos = (comunas["y"] * pesos).groupby(comunas["series_id"]).sum()
        poblacion = comunas[comunas["t"] == origen].set_index("series_id")["poblacion_anual"].reindex(conteos.index)
        pi = poblacion / poblacion.sum()
        if not self.contraccion:
            return pi
        esperados = conteos.sum() * pi
        a = forma_gamma(conteos.to_numpy(), esperados.to_numpy())
        self.diagnostico["forma_gamma"] = a
        relativo = (conteos + a) / (esperados + a)
        p = pi * relativo
        return p / p.sum()

    def fit_predict(self, supervised: pd.DataFrame, origin: int, horizon: int) -> pd.DataFrame:
        """Ajusta con `t <= origin` (historia cruda del panel) y pronostica `origin + horizon`."""
        pasado = supervised[supervised["t"] <= origin]
        objetivo = supervised[supervised["t"] == origin + horizon]
        if pasado.empty or objetivo.empty:
            return pd.DataFrame(columns=["series_id", "y_pred", "y_inferior", "y_superior", "cobertura_esperada"])
        region = pasado[pasado["nivel"] == "region"]
        comunas = pasado[pasado["nivel"] == NIVEL_COMUNA]
        modelo, dispersion_region = self._ajustar_region(region, origin)
        participacion = self._participaciones(comunas, origin)

        # Dispersión comunal dentro del entrenamiento, con el mismo reparto.
        X_pasado = _fourier(comunas["semana"].to_numpy(), self.armonicos) if self.armonicos else np.zeros((len(comunas), 1))
        mu_c = modelo.predict(X_pasado) * comunas["dias_semana"].to_numpy() / 7.0 * comunas["series_id"].map(participacion).to_numpy()
        pesos = self._pesos(comunas["t"].to_numpy(), origin)
        r2 = (comunas["y"].to_numpy() - mu_c) ** 2 / np.clip(mu_c, 1e-9, None)
        dispersion_comuna = max(1.0, float(np.sum(pesos * r2) / max(np.sum(pesos) - participacion.size, 1.0)))
        self.diagnostico.update(dispersion_region=dispersion_region, dispersion_comuna=dispersion_comuna)

        fila_region = objetivo[objetivo["nivel"] == "region"].iloc[0]
        X_obj = _fourier(np.array([fila_region["semana"]]), self.armonicos) if self.armonicos else np.zeros((1, 1))
        mu_region = float(modelo.predict(X_obj)[0] * float(fila_region["dias_semana"]) / 7.0)

        series = objetivo["series_id"].to_numpy()
        es_region = objetivo["nivel"].to_numpy() == "region"
        mu = np.where(es_region, mu_region, mu_region * pd.Series(series).map(participacion).to_numpy(dtype=float))
        if np.isnan(mu).any():
            raise ValueError("Hay comunas a pronosticar sin historia en el entrenamiento.")
        salida = pd.DataFrame({"series_id": series, "y_pred": mu})
        for mascara, dispersion in ((es_region, dispersion_region), (~es_region, dispersion_comuna)):
            if mascara.any():
                inf, sup, cob = cuantiles_conteo(mu[mascara], dispersion, self.nivel)
                salida.loc[mascara, "y_inferior"] = inf
                salida.loc[mascara, "y_superior"] = sup
                salida.loc[mascara, "cobertura_esperada"] = cob
        return salida


class ReferenciaCero:
    """Pronostica cero siempre. No es candidato: muestra por qué MAE no sirve para elegir."""

    name: str = REFERENCIA_CERO

    def fit_predict(self, supervised: pd.DataFrame, origin: int, horizon: int) -> pd.DataFrame:
        objetivo = supervised[supervised["t"] == origin + horizon]
        cero = np.zeros(len(objetivo))
        return pd.DataFrame({"series_id": objetivo["series_id"].to_numpy(), "y_pred": cero,
                             "y_inferior": cero, "y_superior": cero})


def _jerarquico(vida_media: float | None, contraccion: bool = True) -> Callable[[float], DemandModel]:
    return lambda n: PoissonEstacionalJerarquico(nivel=n, vida_media=vida_media, contraccion=contraccion)


# Única fuente de verdad de los modelos de este objetivo: el benchmark, el holdout y
# el pronóstico instancian por nombre. Los del registro se reutilizan tal cual.
_FABRICAS: Final[dict[str, Callable[[float], DemandModel]]] = {
    REFERENCIA: lambda n: build_registry_model(REFERENCIA, n),
    "baseline_estacional_drift": lambda n: build_registry_model("baseline_estacional_drift", n),
    "poisson_glm_global": lambda n: build_registry_model("poisson_glm_global", n),
    "lightgbm_global": lambda n: build_registry_model("lightgbm_global", n),
    "poisson_glm_global_conformal": lambda n: build_registry_model("poisson_glm_global_conformal", n),
    "lightgbm_global_conformal": lambda n: build_registry_model("lightgbm_global_conformal", n),
    **{f"poisson_estacional_eb_vm{v}": _jerarquico(v) for v in VIDAS_MEDIAS},
    "poisson_estacional_poblacion_vm52": _jerarquico(52, contraccion=False),
    REFERENCIA_CERO: lambda n: ReferenciaCero(),
}
NO_CANDIDATOS: Final[frozenset[str]] = frozenset({REFERENCIA, "baseline_estacional_drift", REFERENCIA_CERO})


def available_models() -> list[str]:
    return list(_FABRICAS)


def build_model(nombre: str, nivel: float = NIVEL_INTERVALO) -> DemandModel:
    if nombre not in _FABRICAS:
        raise KeyError(f"Modelo no registrado para suicidios: '{nombre}'. Registrados: {available_models()}.")
    modelo = _FABRICAS[nombre](nivel)
    if modelo.name != nombre:
        raise RuntimeError(f"Incoherencia del registro: '{nombre}' produjo '{modelo.name}'.")
    return modelo


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------

def escalas(panel: pd.DataFrame, hasta_t: int) -> pd.DataFrame:
    """Escalas del baseline estacional por serie (MASE: absoluta; RMSSE: cuadrática), sin el tramo evaluado."""
    filas = []
    for serie, grupo in panel[panel["t"] <= hasta_t].groupby("series_id"):
        y = grupo.sort_values("t")["y"].to_numpy(dtype=float)
        dif = y[SEASONAL_PERIOD:] - y[:-SEASONAL_PERIOD]
        cuadratica = float(np.mean(dif ** 2)) if len(dif) else float("nan")
        filas.append({"series_id": serie, "escala_mase": seasonal_naive_scale(y, SEASONAL_PERIOD),
                      "escala_rmsse": cuadratica if cuadratica > 0 else float("nan")})
    return pd.DataFrame(filas).set_index("series_id")


def puntaje_intervalo(real: np.ndarray, inferior: np.ndarray, superior: np.ndarray, nivel: float) -> np.ndarray:
    """Puntaje de intervalo de Gneiting y Raftery (2007): ancho + penalización por cada fallo. Menor es mejor."""
    alfa = 1 - nivel
    return (superior - inferior) + (2 / alfa) * np.clip(inferior - real, 0, None) + (2 / alfa) * np.clip(real - superior, 0, None)


def evaluar(predicciones: pd.DataFrame, escala: pd.DataFrame, nivel: float = NIVEL_INTERVALO) -> pd.DataFrame:
    """Métricas por serie y horizonte (una fila por par), con las mismas columnas en todos los modelos."""
    p = predicciones.copy()
    if "cobertura_esperada" not in p.columns:
        p["cobertura_esperada"] = np.nan
    p["error"] = p["y_real"] - p["y_pred"]
    p["dentro"] = (p["y_real"] >= p["y_inferior"]) & (p["y_real"] <= p["y_superior"])
    p["puntaje"] = puntaje_intervalo(p["y_real"].to_numpy(), p["y_inferior"].to_numpy(),
                                     p["y_superior"].to_numpy(), nivel)
    filas = []
    for (serie, horizonte), g in p.groupby(["series_id", "horizonte"]):
        e = g["error"].to_numpy(dtype=float)
        esc = escala.loc[serie] if serie in escala.index else pd.Series({"escala_mase": np.nan, "escala_rmsse": np.nan})
        filas.append({
            "series_id": serie, "horizonte": int(horizonte), "n": len(g),
            "mae": round(float(np.mean(np.abs(e))), 4), "rmse": round(float(np.sqrt(np.mean(e ** 2))), 4),
            "mase": round(float(np.mean(np.abs(e)) / esc["escala_mase"]), 4),
            "rmsse": round(float(np.sqrt(np.mean(e ** 2) / esc["escala_rmsse"])), 4),
            "cobertura": round(float(g["dentro"].mean()), 4),
            "cobertura_esperada": round(float(g["cobertura_esperada"].mean()), 4)
            if g["cobertura_esperada"].notna().all() else np.nan,
            "cobertura_nominal": nivel,
            "amplitud_media": round(float((g["y_superior"] - g["y_inferior"]).mean()), 4),
            "puntaje_intervalo": round(float(g["puntaje"].mean()), 4),
        })
    return pd.DataFrame(filas)


def tabla_modelos(predicciones: dict[str, pd.DataFrame], resumenes: dict[str, pd.DataFrame],
                  nivel: float = NIVEL_INTERVALO) -> pd.DataFrame:
    """Una fila por modelo: RMSSE y MASE por nivel (mediana entre series, promedio de horizontes) y calibración."""
    filas = []
    for nombre, pred in predicciones.items():
        resumen = resumenes[nombre].merge(pred[["series_id", "nivel"]].drop_duplicates(), on="series_id")
        fila: dict[str, object] = {"modelo": nombre}
        for nv in NIVELES:
            propio = resumen[resumen["nivel"] == nv]
            por_h = propio.groupby("horizonte")[["rmsse", "mase"]].median()
            obs = pred[pred["nivel"] == nv]
            dentro = (obs["y_real"] >= obs["y_inferior"]) & (obs["y_real"] <= obs["y_superior"])
            cobertura = float(dentro.mean())
            esperada = float(obs["cobertura_esperada"].mean()) if "cobertura_esperada" in obs and obs[
                "cobertura_esperada"].notna().all() else nivel
            mu = obs["y_pred"].clip(lower=1e-9)
            fila.update({
                f"rmsse_{nv}": round(float(por_h["rmsse"].mean()), 4),
                f"mase_{nv}": round(float(por_h["mase"].mean()), 4),
                f"mae_{nv}": round(float((obs["y_real"] - obs["y_pred"]).abs().mean()), 4),
                f"mse_{nv}": round(float(((obs["y_real"] - obs["y_pred"]) ** 2).mean()), 4),
                f"cobertura_{nv}": round(cobertura, 4),
                f"cobertura_esperada_{nv}": round(esperada, 4),
                f"calibrado_{nv}": bool(abs(cobertura - esperada) <= coverage_tolerance(len(obs), nivel)),
                f"puntaje_intervalo_{nv}": round(float(puntaje_intervalo(
                    obs["y_real"].to_numpy(), obs["y_inferior"].to_numpy(), obs["y_superior"].to_numpy(), nivel
                ).mean()), 4),
                # Error cuadrático sobre la varianza Poisson del propio pronóstico: ~1 si
                # el error restante es el azar del conteo.
                f"dispersion_pearson_{nv}": round(float((((obs["y_real"] - obs["y_pred"]) ** 2) / mu).mean()), 4)
                if (obs["y_pred"] > 0).all() else np.nan,
            })
        fila["rmsse_promedio"] = round((fila["rmsse_region"] + fila[f"rmsse_{NIVEL_COMUNA}"]) / 2, 4)
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("rmsse_promedio").reset_index(drop=True)


def seleccionar(tabla: pd.DataFrame) -> tuple[str, str]:
    """Regla fijada antes de evaluar: menor RMSSE promedio entre los que superan al baseline y están calibrados."""
    base = tabla.set_index("modelo").loc[REFERENCIA]
    candidatos = tabla[~tabla["modelo"].isin(NO_CANDIDATOS)
                       & (tabla["rmsse_region"] < base["rmsse_region"])
                       & (tabla[f"rmsse_{NIVEL_COMUNA}"] < base[f"rmsse_{NIVEL_COMUNA}"])]
    if candidatos.empty:
        return REFERENCIA, "ningún modelo supera al baseline estacional en RMSSE en ambos niveles"
    calibrados = candidatos[candidatos["calibrado_region"] & candidatos[f"calibrado_{NIVEL_COMUNA}"]]
    if calibrados.empty:
        return str(candidatos.iloc[0]["modelo"]), (
            "ninguno de los que superan al baseline está calibrado en ambos niveles; se elige el más "
            "preciso y sus intervalos deben leerse como orientativos")
    return str(calibrados.iloc[0]["modelo"]), (
        "menor RMSSE promedio entre los modelos que superan al baseline estacional en ambos niveles "
        "con cobertura compatible con la declarada en la región y en las comunas")


def diebold_mariano(diferencias: np.ndarray, rezagos: int) -> float:
    """p-valor bilateral de Diebold-Mariano (1995) con la corrección de Harvey, Leybourne y Newbold (1997).

    `diferencias` es la serie temporal de diferencias de pérdida; la varianza de su
    media usa Newey-West con `rezagos` autocovarianzas, porque los pronósticos de
    orígenes vecinos comparten semanas objetivo.
    """
    d = np.asarray(diferencias, dtype=float)
    n = len(d)
    if n < 3 or np.allclose(d, 0.0):
        return 1.0
    rezagos = max(0, min(rezagos, n - 2))
    centrada = d - d.mean()
    varianza = float(centrada @ centrada) / n
    for k in range(1, rezagos + 1):
        varianza += 2 * (1 - k / (rezagos + 1)) * float(centrada[k:] @ centrada[:-k]) / n
    if varianza <= 0:
        return 1.0
    h = rezagos + 1
    correccion = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    estadistico = d.mean() / np.sqrt(varianza / n) * correccion
    return float(2 * stats.t.sf(abs(estadistico), df=n - 1))


def comparacion_pareada(pred_a: pd.DataFrame, pred_b: pd.DataFrame, escala: pd.DataFrame,
                        series: list[str]) -> dict[str, float]:
    """Compara dos modelos sobre los mismos pronósticos por su error cuadrático escalado.

    - **Diebold-Mariano** (`p_valor`): ¿difiere la pérdida **media**? Es la pregunta de
      la regla de selección. Las diferencias se promedian por origen (todas las series
      y horizontes de un origen comparten información) y la serie de orígenes se trata
      con Newey-West, con tantos rezagos como orígenes vecinos comparten semanas objetivo.
    - **Wilcoxon** (`p_wilcoxon`): ¿cambia el pronóstico **típico**? Con conteos casi
      siempre en cero, quien pronostica cero acierta la mayoría de las semanas y falla
      fuerte en las demás: Wilcoxon puede no ver una diferencia grande en la media.
    """
    clave = ["origen", "horizonte", "series_id"]

    def _err(pred: pd.DataFrame) -> pd.Series:
        f = pred[pred["series_id"].isin(series)][[*clave, "y_real", "y_pred"]].copy()
        f["e"] = (f["y_real"] - f["y_pred"]) ** 2 / f["series_id"].map(escala["escala_rmsse"])
        return f.set_index(clave)["e"]

    unido = pd.concat([_err(pred_a).rename("a"), _err(pred_b).rename("b")], axis=1, join="inner").dropna()
    dif = unido["b"] - unido["a"]
    p_wilcoxon = 1.0 if np.allclose(dif, 0.0) else float(stats.wilcoxon(unido["b"], unido["a"]).pvalue)
    por_origen = dif.groupby(level="origen").mean().sort_index()
    origenes = por_origen.index.to_numpy()
    paso = int(np.min(np.diff(origenes))) if len(origenes) > 1 else 1
    horizonte = int(unido.index.get_level_values("horizonte").max())
    rezagos = int(np.ceil(horizonte / paso)) - 1
    media_a, media_b = float(unido["a"].mean()), float(unido["b"].mean())
    return {"n": int(len(unido)), "origenes": int(len(por_origen)), "error_a": round(media_a, 5),
            "error_b": round(media_b, 5),
            "cambio_pct": round((media_b / media_a - 1) * 100, 2) if media_a else float("nan"),
            "proporcion_b_mejor": round(float((unido["b"] < unido["a"]).mean()), 4),
            "p_valor": diebold_mariano(por_origen.to_numpy(), rezagos), "p_wilcoxon": p_wilcoxon}


def holm(p_valores: list[float]) -> list[float]:
    """Ajuste de Holm-Bonferroni para una familia de pruebas."""
    orden = np.argsort(p_valores)
    m = len(p_valores)
    ajustados = np.empty(m)
    acumulado = 0.0
    for rango, i in enumerate(orden):
        acumulado = max(acumulado, min(1.0, (m - rango) * p_valores[i]))
        ajustados[i] = acumulado
    return ajustados.tolist()


# --------------------------------------------------------------------------
# Pronóstico vigente
# --------------------------------------------------------------------------

def cargar_seleccion(ruta: Path = RUTA_SELECCION) -> dict[str, Any]:
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta {ruta.as_posix()}: ejecute el stage `benchmark_suicidios`.")
    return json.loads(ruta.read_text(encoding="utf-8"))


def calcular_pronostico(mart: pd.DataFrame, seleccion: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajusta el modelo congelado con todas las semanas completas y pronostica los horizontes."""
    horizontes = tuple(int(h) for h in seleccion["horizontes"])
    panel = build_panel(mart, int(seleccion["ano_inicio"]))
    cal = calendario(mart, semanas_extra=max(horizontes))
    extendido = append_future_rows(panel.drop(columns=["dias_semana"]), max(horizontes), exogenous=())
    extendido = extendido.merge(cal[["ano", "semana", "dias_semana"]], on=["ano", "semana"], how="left",
                                validate="many_to_one")
    extendido["dias_semana"] = extendido["dias_semana"].astype(float)
    if extendido["dias_semana"].isna().any():
        raise ValueError("Falta el número de días de alguna semana futura.")
    modelo = build_model(seleccion["modelo_recomendado"], float(seleccion["nivel_intervalo"]))
    pronostico = _pronosticar(extendido, modelo, horizontes)
    pronostico = pronostico.drop(columns=["fecha_inicio_semana"], errors="ignore").merge(
        cal[["ano", "semana", "fecha_inicio_semana"]], on=["ano", "semana"], how="left")
    nombres = panel.drop_duplicates("series_id").set_index("series_id")["comuna_glosa"]
    niveles = panel.drop_duplicates("series_id").set_index("series_id")["nivel"]
    pronostico["nombre"] = pronostico["series_id"].map(nombres)
    pronostico["nivel"] = pronostico["series_id"].map(niveles)
    return pronostico.sort_values(["series_id", "horizonte"]).reset_index(drop=True), panel


def _pronosticar(extendido: pd.DataFrame, modelo: DemandModel, horizontes: tuple[int, ...]) -> pd.DataFrame:
    """Mismo procedimiento que `forecast_future`, conservando la cobertura que declara el modelo.

    `forecast_future` solo devuelve el punto y el intervalo; aquí se necesita además
    `cobertura_esperada`. Las garantías son las mismas: filas marcadoras con `y`
    desconocido y matriz directa por horizonte.
    """
    observados = extendido[~extendido["es_futuro"]]
    if observados["y"].isna().any():
        raise ValueError("Hay semanas observadas sin valor: el panel no es regular.")
    origen = int(observados["t"].max())
    base = extendido.drop(columns=["es_futuro"])
    periodos = base[["t", "ano", "semana"]].drop_duplicates("t")
    salidas = []
    for horizonte in horizontes:
        supervisada = build_supervised_frame(base, horizon=horizonte, exogenous=())
        prediccion = modelo.fit_predict(supervisada, origen, horizonte).copy()
        if "cobertura_esperada" not in prediccion.columns:
            prediccion["cobertura_esperada"] = np.nan
        prediccion = prediccion[["series_id", "y_pred", "y_inferior", "y_superior", "cobertura_esperada"]]
        prediccion["horizonte"], prediccion["t"] = horizonte, origen + horizonte
        salidas.append(prediccion)
    resultado = pd.concat(salidas, ignore_index=True).merge(periodos, on="t", how="left")
    resultado = resultado.merge(base[["series_id", "t", "poblacion_anual"]], on=["series_id", "t"], how="left")
    resultado["origen"], resultado["modelo"] = origen, modelo.name
    return resultado


def huella(mart_path: Path = MART_PATH, seleccion_path: Path = RUTA_SELECCION) -> dict[str, dict[str, str]]:
    return {CLAVE_MART: {"ruta": mart_path.as_posix(), "sha256": file_sha256(mart_path)},
            CLAVE_SELECCION: {"ruta": seleccion_path.as_posix(), "sha256": file_sha256(seleccion_path)}}


def construir_manifiesto(pronostico: pd.DataFrame, panel: pd.DataFrame, mart: pd.DataFrame,
                         seleccion: dict[str, Any], entradas: dict[str, dict[str, str]]) -> dict[str, Any]:
    ultima = panel.loc[panel["t"] == panel["t"].max()].iloc[0]
    incompletas = mart.loc[~mart["registro_completo"], ["ano", "semana"]].drop_duplicates()
    return {
        "dataset": "pronostico_suicidios",
        "generado_en_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generado_en_chile": run_datetime_chile().isoformat(),
        "modelo": seleccion["modelo_recomendado"],
        "nivel_intervalo": float(seleccion["nivel_intervalo"]),
        "horizontes": [int(h) for h in seleccion["horizontes"]],
        "semilla": RANDOM_SEED,
        "ultima_semana_observada": {"t": int(ultima["t"]), "ano": int(ultima["ano"]), "semana": int(ultima["semana"])},
        "fecha_corte_datos": str(max(mart["fecha_fin_semana"])),
        "semanas_registro_incompleto": [f"{a}-S{s:02d}" for a, s in incompletas.itertuples(index=False)],
        "series": {"total": int(pronostico["series_id"].nunique()),
                   "region": int((pronostico.drop_duplicates("series_id")["nivel"] == "region").sum()),
                   "comuna": int((pronostico.drop_duplicates("series_id")["nivel"] == NIVEL_COMUNA).sum())},
        "filas": int(len(pronostico)),
        "entradas": entradas,
        "versiones": {"python": ".".join(map(str, __import__("sys").version_info[:3])),
                      **{p: _version(p) for p in PAQUETES_REGISTRADOS}},
    }


def guardar(pronostico: pd.DataFrame, manifiesto: dict[str, Any],
            ruta_pronostico: Path = RUTA_PRONOSTICO, ruta_manifiesto: Path = RUTA_MANIFIESTO) -> None:
    """Pronóstico y manifiesto con reemplazo atómico; el manifiesto al final."""
    ruta_pronostico.parent.mkdir(parents=True, exist_ok=True)
    tabla = pronostico.copy()
    tabla["fecha_inicio_semana"] = pd.to_datetime(tabla["fecha_inicio_semana"]).dt.date
    tabla = pa.Table.from_pandas(tabla[[c.name for c in ESQUEMA]], schema=ESQUEMA, preserve_index=False)
    temporal = ruta_pronostico.with_suffix(ruta_pronostico.suffix + ".tmp")
    pq.write_table(tabla, temporal)
    os.replace(temporal, ruta_pronostico)
    temporal_json = ruta_manifiesto.with_suffix(ruta_manifiesto.suffix + ".tmp")
    temporal_json.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal_json, ruta_manifiesto)


def motivo_desactualizacion(manifiesto: dict[str, Any]) -> str | None:
    """Por qué el pronóstico guardado ya no corresponde a sus entradas, o None si sigue vigente."""
    registradas = manifiesto.get("entradas") or {}
    if set(registradas) != {CLAVE_MART, CLAVE_SELECCION}:
        return "el manifiesto no registra sus entradas"
    for clave, registro in registradas.items():
        ruta = Path(registro["ruta"])
        if not ruta.is_file():
            return f"falta la entrada '{clave}' ({ruta.as_posix()})"
        if file_sha256(ruta) != registro.get("sha256"):
            return f"cambió '{clave}' respecto de la versión con que se generó"
    return None


def cargar(ruta_pronostico: Path = RUTA_PRONOSTICO, ruta_manifiesto: Path = RUTA_MANIFIESTO
           ) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not ruta_pronostico.is_file() or not ruta_manifiesto.is_file():
        raise FileNotFoundError("No hay pronóstico de suicidios persistido: ejecute el stage `forecast_suicidios`.")
    return pq.read_table(ruta_pronostico).to_pandas(), json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
