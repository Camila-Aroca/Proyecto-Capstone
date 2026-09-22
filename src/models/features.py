"""Construccion del panel y de la matriz supervisada para el modelo de demanda.

Dos transformaciones, deliberadamente separadas:

1. `build_panel`: convierte el mart semanal comunal en un panel largo con un
   indice temporal entero continuo. Incluye el agregado RM como una serie mas,
   de modo que el nivel superior y el inferior de la jerarquia compartan
   exactamente el mismo esquema y el mismo codigo aguas abajo.
2. `build_supervised_frame`: produce la matriz (X, y) para un horizonte dado
   usando **estrategia directa**: para predecir `y[t]` a horizonte `h` solo se
   usan valores observados hasta `t - h`. Esto evita tanto la fuga de
   informacion futura como la acumulacion de error de la estrategia recursiva.

Escalabilidad: ningun anio, comuna ni longitud de serie esta hardcodeado. El
panel se deriva de lo que traiga el mart, de modo que agregar anios o comunas
nuevas no requiere tocar este modulo.

Advertencias de dominio que este modulo respeta:

- Las semanas `semana = 53` del calendario DEIS son fragmentos de pocos dias,
  no semanas completas; se excluyen para obtener una grilla regular.
- El target es un conteo de **atenciones (eventos), no de personas unicas**.
- La poblacion se incorpora como exposicion del territorio, nunca para
  convertir el target en tasa: las tasas se derivan despues del pronostico.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
import unicodedata

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

WEEKLY_MART_PATH: Final[Path] = Path(
    "data/processed/marts/mart_urgencias_comuna_weekly.parquet"
)
ESTABLECIMIENTOS_PATH: Final[Path] = Path(
    "data/processed/establecimientos_rm_clean.parquet"
)

TARGET: Final[str] = "atenciones_id36"
# Identificador reservado para la serie agregada regional dentro del panel.
RM_SERIES_ID: Final[str] = "RM"
# Prefijo de los identificadores de las series agregadas por Servicio de Salud.
SERVICIO_PREFIX: Final[str] = "SS_"
# Solo las glosas con este prefijo son Servicios de Salud. Las demas categorias
# del maestro ("SEREMI de Salud...", "Servicio de Salud No Aplica") no son una
# red asistencial y no definen pertenencia territorial.
SERVICIO_GLOSA_PREFIX: Final[str] = "Servicio de Salud Metropolitano "
# Semanas regulares por anio en el calendario DEIS (la 53 es fragmentaria).
SEASONAL_PERIOD: Final[int] = 52

# Covariables observadas que acompanan al target en el mart y aportan senal
# propia. Entran al modelo unicamente rezagadas, nunca en su valor contemporaneo.
EXOGENOUS_COLUMNS: Final[tuple[str, ...]] = (
    "atenciones_id1",
    "n_establecimientos_reportantes_id36",
)

# Tramo inicial de la serie que el EDA identifico como un regimen de nivel
# distinto, no explicado por la cobertura de reporte (ver seccion 4 de
# `reports/eda/eda_series_demanda_sm.md`). Se marca con una bandera en vez de
# eliminarlo, para que el backtesting decida si conviene excluirlo o no.
INITIAL_REGIME_WEEKS: Final[int] = 13


def load_weekly_mart(path: Path = WEEKLY_MART_PATH) -> pd.DataFrame:
    """Lee del mart semanal solo las columnas que el modelo necesita."""
    columns = [
        "comuna_codigo",
        "comuna_glosa",
        "ano",
        "semana",
        TARGET,
        "poblacion_anual",
        *EXOGENOUS_COLUMNS,
    ]
    return pq.read_table(path, columns=columns).to_pandas()


def _servicio_id(glosa: str) -> str:
    """Deriva un identificador estable desde la glosa del Servicio de Salud.

    Se usa la glosa y no el codigo porque en el maestro DEIS el codigo `13` es
    compartido por dos glosas distintas ("SEREMI de Salud Metropolitana" y
    "Servicio de Salud Metropolitano Sur"): el codigo no es llave unica.
    """
    nombre = glosa.removeprefix(SERVICIO_GLOSA_PREFIX).strip().upper()
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return SERVICIO_PREFIX + "_".join(nombre.split())


def load_servicio_map(path: Path = ESTABLECIMIENTOS_PATH) -> pd.DataFrame:
    """Asigna cada comuna RM al Servicio de Salud Metropolitano que la atiende.

    El maestro de establecimientos no trae la pertenencia administrativa de la
    **comuna** a un Servicio, solo la de cada **establecimiento**. Se aproxima
    con una regla reproducible: la comuna se asigna al Servicio con mas
    establecimientos del maestro ubicados en ella, considerando unicamente las
    glosas que son Servicios de Salud (se excluyen SEREMI y "No Aplica").

    La regla no resuelve empates en silencio: si dos Servicios empatan en una
    comuna, la funcion falla y obliga a documentar la decision. Devuelve ademas
    la participacion del Servicio asignado, para que el informe pueda declarar
    que comunas tienen pertenencia mixta.
    """
    frame = pq.read_table(
        path,
        columns=["comuna_codigo", "seremi_salud_glosa_servicio_de_salud_glosa"],
    ).to_pandas()
    frame = frame.rename(columns={"seremi_salud_glosa_servicio_de_salud_glosa": "glosa"})
    frame = frame[frame["glosa"].fillna("").str.startswith(SERVICIO_GLOSA_PREFIX)]
    frame["comuna_codigo"] = frame["comuna_codigo"].astype(str)

    conteos = (
        frame.groupby(["comuna_codigo", "glosa"]).size().rename("n").reset_index()
    )
    conteos["participacion"] = conteos["n"] / conteos.groupby("comuna_codigo")[
        "n"
    ].transform("sum")

    maximos = conteos.groupby("comuna_codigo")["n"].transform("max")
    ganadores = conteos[conteos["n"] == maximos]
    empates = ganadores[ganadores.duplicated("comuna_codigo", keep=False)]
    if not empates.empty:
        raise ValueError(
            "Empate de Servicio de Salud en comunas "
            f"{sorted(empates['comuna_codigo'].unique())}: la regla de mayoria no "
            "puede asignarlas sin una decision documentada."
        )

    resultado = ganadores.rename(columns={"glosa": "servicio_glosa"})
    resultado["servicio_id"] = resultado["servicio_glosa"].map(_servicio_id)
    resultado["servicios_en_comuna"] = resultado["comuna_codigo"].map(
        conteos.groupby("comuna_codigo").size()
    )
    return resultado[
        [
            "comuna_codigo", "servicio_id", "servicio_glosa",
            "n", "participacion", "servicios_en_comuna",
        ]
    ].sort_values("comuna_codigo").reset_index(drop=True)


def _add_time_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Asigna un indice temporal entero continuo a partir de (ano, semana).

    El indice es la posicion ordinal de cada periodo dentro del calendario
    observado. Se construye sobre la grilla global y no por serie, de modo que
    todas las series queden alineadas en el mismo eje temporal.
    """
    periodos = (
        frame[["ano", "semana"]]
        .drop_duplicates()
        .sort_values(["ano", "semana"])
        .reset_index(drop=True)
    )
    periodos["t"] = np.arange(len(periodos), dtype="int64")
    return frame.merge(periodos, on=["ano", "semana"], how="left", validate="many_to_one")


def build_panel(
    weekly: pd.DataFrame,
    target: str = TARGET,
    include_rm_aggregate: bool = True,
    servicio_map: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convierte el mart semanal en un panel largo `series_id x t`.

    Excluye las semanas fragmentarias (`semana = 53`), agrega la serie RM como
    un `series_id` adicional y valida que la grilla resultante sea regular: cada
    serie debe tener exactamente un registro por periodo observado, sin huecos.

    Si se entrega `servicio_map` (salida de `load_servicio_map`), el panel pasa a
    tener **tres niveles**: RM, un agregado por Servicio de Salud y las comunas.
    Se agrega la columna `servicio_id`, que declara a que Servicio pertenece cada
    comuna, para que la reconciliacion conozca la estructura sin depender de
    convenciones de nombres. Sin mapeo, el panel es identico al de dos niveles.
    """
    regular = weekly[weekly["semana"] != SEASONAL_PERIOD + 1].copy()

    comunas = regular.rename(columns={"comuna_codigo": "series_id"})
    comunas["nivel"] = "comuna"

    if servicio_map is not None:
        mapa = servicio_map.set_index("comuna_codigo")["servicio_id"]
        comunas["servicio_id"] = comunas["series_id"].astype(str).map(mapa)
        sin_servicio = sorted(comunas.loc[comunas["servicio_id"].isna(), "series_id"].unique())
        if sin_servicio:
            raise ValueError(f"Comunas sin Servicio de Salud asignado: {sin_servicio}")

    partes = [comunas]
    if servicio_map is not None:
        # Mismo criterio que el agregado regional: se suman conteos y poblacion,
        # nunca se promedian tasas ya calculadas.
        servicios = (
            comunas.groupby(["servicio_id", "ano", "semana"], as_index=False)[
                [target, "poblacion_anual", *EXOGENOUS_COLUMNS]
            ]
            .sum()
        )
        glosas = servicio_map.drop_duplicates("servicio_id").set_index("servicio_id")[
            "servicio_glosa"
        ]
        servicios["series_id"] = servicios["servicio_id"]
        servicios["comuna_glosa"] = servicios["servicio_id"].map(glosas)
        servicios["nivel"] = "servicio"
        partes.append(servicios)
    if include_rm_aggregate:
        # El agregado regional suma conteos y poblacion; las covariables de
        # conteo tambien se suman. Nunca se promedian tasas ya calculadas.
        agregado = (
            regular.groupby(["ano", "semana"], as_index=False)[
                [target, "poblacion_anual", *EXOGENOUS_COLUMNS]
            ]
            .sum()
        )
        agregado["series_id"] = RM_SERIES_ID
        agregado["comuna_glosa"] = RM_SERIES_ID
        agregado["nivel"] = "region"
        partes.append(agregado)

    panel = pd.concat(partes, ignore_index=True)
    panel = _add_time_index(panel)
    panel = panel.rename(columns={target: "y"}).sort_values(["series_id", "t"])

    duplicados = panel.duplicated(["series_id", "t"]).sum()
    if duplicados:
        raise ValueError(f"Panel con grano duplicado: {duplicados} filas (series_id, t).")

    # Una grilla irregular romperia el significado de los rezagos: se detecta
    # aqui en vez de producir features silenciosamente incorrectas.
    conteos = panel.groupby("series_id")["t"].size().unique()
    if len(conteos) > 1:
        raise ValueError(
            "Las series del panel no comparten la misma longitud: "
            f"se observaron {sorted(conteos)} periodos."
        )

    columnas = [
        "series_id", "nivel", "comuna_glosa", "t", "ano", "semana",
        "y", "poblacion_anual", *EXOGENOUS_COLUMNS,
    ]
    if servicio_map is not None:
        columnas.insert(2, "servicio_id")
    return panel[columnas].reset_index(drop=True)


def add_calendar_features(frame: pd.DataFrame, n_harmonics: int = 2) -> pd.DataFrame:
    """Agrega representacion ciclica de la semana del anio.

    Los terminos de Fourier evitan el salto artificial entre la semana 52 y la
    1 que produciria usar el numero de semana como variable numerica cruda, y
    con pocos armonicos describen la estacionalidad anual sin el costo de
    52 variables indicadoras.
    """
    resultado = frame.copy()
    angulo = 2 * np.pi * resultado["semana"] / SEASONAL_PERIOD
    for k in range(1, n_harmonics + 1):
        resultado[f"sin_{k}"] = np.sin(k * angulo)
        resultado[f"cos_{k}"] = np.cos(k * angulo)
    return resultado


def add_regime_flag(
    frame: pd.DataFrame, initial_weeks: int = INITIAL_REGIME_WEEKS
) -> pd.DataFrame:
    """Marca el tramo inicial de la serie como un regimen potencialmente distinto.

    No elimina observaciones: expone la bandera para que el backtesting compare
    incluirlas, excluirlas o ponderarlas. La causa del cambio de nivel no es
    determinable con los datos disponibles (ver EDA de series).
    """
    resultado = frame.copy()
    resultado["regimen_inicial"] = (resultado["t"] < initial_weeks).astype("int8")
    return resultado


def build_supervised_frame(
    panel: pd.DataFrame,
    horizon: int,
    extra_lags: tuple[int, ...] = (0, 1, 2, 3),
    rolling_windows: tuple[int, ...] = (4, 13),
    seasonal_lag: int = SEASONAL_PERIOD,
    exogenous: tuple[str, ...] = EXOGENOUS_COLUMNS,
) -> pd.DataFrame:
    """Construye la matriz supervisada para un horizonte, sin fuga temporal.

    Estrategia **directa**: la fila que predice `y[t]` solo contiene informacion
    disponible en `t - horizon`. Cada rezago base `l` de `extra_lags` se traduce
    en el rezago efectivo `horizon + l`, de modo que aumentar el horizonte
    desplaza automaticamente toda la ventana de informacion hacia el pasado.

    Las medias moviles se calculan sobre la serie ya desplazada `horizon`
    periodos, por lo que tampoco pueden incorporar observaciones futuras.

    El rezago estacional se incluye solo si es mayor o igual al horizonte; con
    el horizonte maximo del alcance (8) y periodo 52 siempre lo es, pero la
    condicion se verifica en vez de asumirse.
    """
    if horizon < 1:
        raise ValueError("El horizonte debe ser un entero positivo.")

    frame = panel.sort_values(["series_id", "t"]).copy()

    def _shift(columna: str, periodos: int) -> pd.Series:
        """Desplaza una columna dentro de cada serie, sin cruzar entre series."""
        return frame.groupby("series_id", sort=False)[columna].shift(periodos)

    # --- Rezagos del target -------------------------------------------------
    for base in extra_lags:
        rezago = horizon + base
        frame[f"y_lag_{rezago}"] = _shift("y", rezago)

    # --- Rezago estacional --------------------------------------------------
    if seasonal_lag >= horizon:
        frame[f"y_lag_{seasonal_lag}"] = _shift("y", seasonal_lag)
        # Variacion interanual medida en el ultimo punto observable: compara
        # `y[t-h]` con `y[t-h-52]`. Deja ver la tendencia de la serie sin
        # exponer ninguna observacion posterior a `t - h`.
        frame["y_delta_estacional"] = _shift("y", horizon) - _shift(
            "y", horizon + seasonal_lag
        )

    # --- Medias moviles sobre la serie ya desplazada ------------------------
    frame["_y_desplazada"] = _shift("y", horizon)
    for ventana in rolling_windows:
        frame[f"y_media_{ventana}"] = (
            frame.groupby("series_id", sort=False)["_y_desplazada"]
            .transform(lambda s, w=ventana: s.rolling(w, min_periods=w).mean())
        )
        frame[f"y_desv_{ventana}"] = (
            frame.groupby("series_id", sort=False)["_y_desplazada"]
            .transform(lambda s, w=ventana: s.rolling(w, min_periods=w).std())
        )
    frame = frame.drop(columns=["_y_desplazada"])

    # --- Covariables exogenas, siempre rezagadas ----------------------------
    for columna in exogenous:
        frame[f"{columna}_lag_{horizon}"] = _shift(columna, horizon)

    frame = add_calendar_features(frame)
    frame = add_regime_flag(frame)
    frame["horizonte"] = horizon

    # La poblacion es anual y conocida por adelantado (proyeccion INE), por lo
    # que puede usarse en su valor contemporaneo sin fuga: no depende de
    # observaciones futuras del target.
    frame["log_poblacion"] = np.log(frame["poblacion_anual"].clip(lower=1))

    return frame.reset_index(drop=True)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Devuelve las columnas usables como predictores en `frame`.

    Se deriva del contenido real del DataFrame en vez de una lista fija, para
    que agregar un rezago o una covariable no exija actualizar dos lugares.
    """
    excluidas = {
        "series_id", "nivel", "servicio_id", "comuna_glosa", "t", "ano", "semana",
        "y", "poblacion_anual", *EXOGENOUS_COLUMNS,
    }
    return [c for c in frame.columns if c not in excluidas]


def drop_incomplete_rows(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Elimina las filas sin historia suficiente para calcular sus features.

    Son las primeras observaciones de cada serie, donde los rezagos largos no
    existen todavia. No se imputan: un rezago inventado introduciria senal
    falsa en el entrenamiento.
    """
    return frame.dropna(subset=columns).reset_index(drop=True)
