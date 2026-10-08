"""Pronostico de semanas futuras con el modelo seleccionado.

El resto del paquete evalua el pasado: `rolling_origin_backtest` siempre tiene
el valor real del periodo objetivo. Este modulo produce el pronostico que el
producto necesita, el de semanas que **todavia no ocurren**.

**Como se hace sin romper las garantias del paquete.** La matriz supervisada
usa estrategia directa: la fila del periodo `t` a horizonte `h` solo contiene
valores observados hasta `t - h`. Por eso basta con agregar al panel filas
*marcadoras* para los periodos futuros (con `y` desconocido) y construir las
features como siempre: los rezagos de esas filas apuntan exclusivamente a
semanas ya observadas. El modelo se ajusta con `t <= ultimo observado` y
pronostica las filas marcadoras. Ningun valor futuro se inventa: `y` queda en
NaN y nunca entra al entrenamiento.

**Datos usados.** El entrenamiento cerrado (mart 2021-2025) mas las semanas
completas del anio en curso, con el mismo universo fijo de comunas que la
evaluacion en holdout (`src.models.holdout`): solo comunas con historia y
cobertura completa, y el total regional definido sobre ese universo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.data.clean_poblacion_proyecciones import load_rm_population
from src.models.backtesting import DemandModel
from src.models.features import (
    EXOGENOUS_COLUMNS,
    RM_SERIES_ID,
    SEASONAL_PERIOD,
    TARGET,
    WEEKLY_MART_PATH,
    build_panel,
    build_supervised_frame,
    load_weekly_mart,
)
from src.models.holdout import holdout_years, load_holdout_weekly

# 1-3 cubren el tramo entre la ultima semana completa publicada y el primer horizonte
# comprometido del objetivo APT (4-8), que de otro modo queda sin dato ni pronostico.
HORIZONTES_DEFECTO: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8)


@dataclass
class DatosActuales:
    """Panel observado hasta la ultima semana completa y su contexto."""

    panel: pd.DataFrame
    calendario: pd.DataFrame
    anos_en_curso: list[int]
    diagnostico: dict[str, pd.DataFrame] = field(default_factory=dict)


def _calendario(weekly: pd.DataFrame) -> pd.DataFrame:
    """Fecha de inicio observada de cada semana DEIS regular."""
    regular = weekly[weekly["semana"] != SEASONAL_PERIOD + 1]
    return (
        regular.groupby(["ano", "semana"], as_index=False)["fecha_inicio_semana"]
        .min()
        .assign(fecha_inicio_semana=lambda d: pd.to_datetime(d["fecha_inicio_semana"]))
    )


def load_current_panel(mart_path: Path = WEEKLY_MART_PATH) -> DatosActuales:
    """Panel de entrenamiento extendido con las semanas completas del anio en curso.

    Si no hay datos posteriores al mart, el panel es el del mart. Si los hay,
    aplica las mismas exclusiones documentadas que la evaluacion en holdout.
    """
    mart = load_weekly_mart(mart_path)
    fechas_mart = pq.read_table(
        mart_path, columns=["ano", "semana", "fecha_inicio_semana"]
    ).to_pandas()
    ultimo_ano = int(mart["ano"].max())
    anos = holdout_years(ultimo_ano)
    if not anos:
        return DatosActuales(
            panel=build_panel(mart), calendario=_calendario(fechas_mart), anos_en_curso=[]
        )

    referencia = mart[mart["ano"] == ultimo_ano].groupby("comuna_codigo")[TARGET].sum()
    reciente, diagnostico = load_holdout_weekly(anos, referencia)
    universo = set(reciente["comuna_codigo"])
    mart = mart[mart["comuna_codigo"].isin(universo)]
    panel = build_panel(pd.concat([mart, reciente[mart.columns]], ignore_index=True))
    calendario = _calendario(
        pd.concat(
            [fechas_mart, reciente[["ano", "semana", "fecha_inicio_semana"]]],
            ignore_index=True,
        )
    )
    return DatosActuales(
        panel=panel, calendario=calendario, anos_en_curso=anos, diagnostico=diagnostico
    )


def _siguiente_semana(ano: int, semana: int) -> tuple[int, int]:
    """Siguiente semana regular del calendario DEIS (la 53 es un fragmento)."""
    return (ano + 1, 1) if semana >= SEASONAL_PERIOD else (ano, semana + 1)


def append_future_rows(
    panel: pd.DataFrame, pasos: int, calendario: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Agrega `pasos` periodos futuros por serie, con `y` desconocido.

    La poblacion de un anio futuro sale de la proyeccion INE: es conocida de
    antemano y no depende de observaciones futuras. Las covariables exogenas
    quedan en NaN; el modelo solo las usa rezagadas al menos un horizonte, es
    decir, en semanas ya observadas.
    """
    if pasos < 1:
        raise ValueError("Se necesita al menos un periodo futuro.")
    t_max = int(panel["t"].max())
    ultimo = panel[panel["t"] == t_max].iloc[0]
    periodos, ano, semana = [], int(ultimo["ano"]), int(ultimo["semana"])
    for paso in range(1, pasos + 1):
        ano, semana = _siguiente_semana(ano, semana)
        periodos.append({"t": t_max + paso, "ano": ano, "semana": semana})
    futuros = pd.DataFrame(periodos)

    poblacion = panel.groupby(["series_id", "ano"])["poblacion_anual"].first()
    anos_faltantes = sorted(set(futuros["ano"]) - set(panel["ano"]))
    if anos_faltantes:
        poblacion = pd.concat([poblacion, _poblacion_proyectada(panel, anos_faltantes)])

    series = panel.drop_duplicates("series_id")[
        [c for c in ("series_id", "nivel", "servicio_id", "comuna_glosa") if c in panel.columns]
    ]
    filas = series.merge(futuros, how="cross")
    filas["y"] = np.nan
    for columna in EXOGENOUS_COLUMNS:
        filas[columna] = np.nan
    filas["poblacion_anual"] = [
        poblacion.get((s, a), np.nan) for s, a in zip(filas["series_id"], filas["ano"])
    ]
    if filas["poblacion_anual"].isna().any():
        raise ValueError("Falta la poblacion proyectada de algun periodo futuro.")

    extendido = pd.concat([panel, filas[panel.columns]], ignore_index=True)
    extendido["es_futuro"] = extendido["t"] > t_max
    if calendario is not None:
        extendido = _con_fechas(extendido, calendario, t_max)
    return extendido.sort_values(["series_id", "t"]).reset_index(drop=True)


def _poblacion_proyectada(panel: pd.DataFrame, anos: list[int]) -> pd.Series:
    """Poblacion INE de anios sin datos, agregada con la misma jerarquia del panel."""
    comunas = panel.loc[panel["nivel"] == "comuna"].drop_duplicates("series_id")
    proyeccion = load_rm_population(years=tuple(anos)).rename(
        columns={"comuna_codigo": "series_id"}
    )
    proyeccion = proyeccion[proyeccion["series_id"].isin(set(comunas["series_id"]))]
    partes = [
        proyeccion,
        proyeccion.groupby("ano", as_index=False)["poblacion"].sum().assign(
            series_id=RM_SERIES_ID
        ),
    ]
    if "servicio_id" in panel.columns:
        mapa = comunas.set_index("series_id")["servicio_id"]
        partes.append(
            proyeccion.assign(series_id=proyeccion["series_id"].map(mapa))
            .groupby(["series_id", "ano"], as_index=False)["poblacion"]
            .sum()
        )
    return pd.concat(partes, ignore_index=True).set_index(["series_id", "ano"])["poblacion"]


def _con_fechas(frame: pd.DataFrame, calendario: pd.DataFrame, t_max: int) -> pd.DataFrame:
    """Fecha de inicio de cada semana: observada, o proyectada de 7 en 7 dias."""
    unido = frame.merge(calendario, on=["ano", "semana"], how="left")
    ultima = unido.loc[unido["t"] == t_max, "fecha_inicio_semana"].dropna()
    if not ultima.empty:
        base = ultima.iloc[0]
        futuros = unido["t"] > t_max
        unido.loc[futuros, "fecha_inicio_semana"] = base + pd.to_timedelta(
            (unido.loc[futuros, "t"] - t_max) * 7, unit="D"
        )
    return unido


def forecast_future(
    panel_extendido: pd.DataFrame,
    modelo: DemandModel,
    horizontes: tuple[int, ...] = HORIZONTES_DEFECTO,
) -> pd.DataFrame:
    """Pronostica cada horizonte desde la ultima semana observada.

    Devuelve una fila por serie y horizonte con el pronostico puntual y el
    intervalo del modelo, y la poblacion proyectada del periodo objetivo.
    """
    observados = panel_extendido[~panel_extendido["es_futuro"]]
    if observados["y"].isna().any():
        raise ValueError("Hay periodos observados sin valor: el panel no es regular.")
    origen = int(observados["t"].max())
    if int(panel_extendido["t"].max()) < origen + max(horizontes):
        raise ValueError("El panel no tiene filas futuras suficientes para los horizontes.")

    base = panel_extendido.drop(columns=["es_futuro", "fecha_inicio_semana"], errors="ignore")
    periodos = panel_extendido[["t", "ano", "semana"]].drop_duplicates()
    if "fecha_inicio_semana" in panel_extendido.columns:
        periodos = panel_extendido[["t", "ano", "semana", "fecha_inicio_semana"]].drop_duplicates("t")

    salidas = []
    for horizonte in horizontes:
        supervisada = build_supervised_frame(base, horizon=horizonte)
        prediccion = modelo.fit_predict(supervisada, origen, horizonte)
        prediccion = prediccion[["series_id", "y_pred", "y_inferior", "y_superior"]].copy()
        prediccion["horizonte"] = horizonte
        prediccion["t"] = origen + horizonte
        salidas.append(prediccion)

    resultado = pd.concat(salidas, ignore_index=True).merge(periodos, on="t", how="left")
    # La poblacion del periodo pronosticado (proyeccion INE, conocida de antemano)
    # permite derivar tasas sin depender de que ese anio ya tenga observaciones.
    resultado = resultado.merge(
        panel_extendido[["series_id", "t", "poblacion_anual"]], on=["series_id", "t"], how="left"
    )
    resultado["origen"] = origen
    resultado["modelo"] = modelo.name
    return resultado.sort_values(["series_id", "horizonte"]).reset_index(drop=True)
