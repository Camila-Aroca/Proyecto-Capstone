"""Reconciliacion jerarquica entre el agregado RM, los Servicios de Salud y las comunas.

El problema que resuelve: si cada nivel se pronostica por separado, los
resultados no son **coherentes** --la suma de las comunas no da el total del
Servicio ni el regional--. Para un producto de planificacion eso es
inaceptable: el mapa comunal y los indicadores agregados mostrarian cifras que
no cuadran.

La jerarquia admite dos formas, y cada funcion las maneja sin cambiar de firma:

- **Dos niveles**: RM -> comunas.
- **Tres niveles**: RM -> Servicio de Salud -> comunas.

La estructura se lee de las columnas `nivel` y `servicio_id` que el motor de
backtesting adjunta desde el panel. Si faltan (predicciones construidas a mano),
se infiere la forma de dos niveles: la serie `RM` es la region y el resto son
comunas.

Reconciliaciones implementadas, todas auditables y sin estimar covarianzas:

- `reconcile_bottom_up`: los agregados pasan a ser la suma de las comunas.
- `reconcile_top_down`: se conserva el total regional y se reparte entre las
  comunas segun la participacion que el propio modelo les asigno.
- `reconcile_middle_out`: se conserva el pronostico de cada Servicio, se reparte
  entre sus comunas y el total regional pasa a ser la suma de los Servicios.
  Requiere el nivel Servicio.
- `reconcile_wls_structural`: proyeccion de minimos cuadrados ponderados que usa
  la informacion de **todos** los niveles a la vez, con pesos estructurales
  (cada nodo pondera segun cuantas comunas agrega). Es la variante de MinT que
  no requiere estimar la matriz de covarianza de los errores.

MinT con covarianza completa sigue sin implementarse: con 13 origenes de
evaluacion la covarianza entre decenas de series seria inestable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.features import RM_SERIES_ID

# Clave que identifica un pronostico individual dentro del backtesting.
CLAVE_PRONOSTICO: tuple[str, ...] = ("origen", "horizonte")
COLUMNAS_VALOR: tuple[str, ...] = ("y_pred", "y_inferior", "y_superior")


def _con_estructura(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Garantiza la columna `nivel`, infiriendo dos niveles si no viene dada."""
    resultado = predicciones.copy()
    if "nivel" not in resultado.columns:
        resultado["nivel"] = np.where(
            resultado["series_id"] == RM_SERIES_ID, "region", "comuna"
        )
    return resultado


def _columnas_valor(frame: pd.DataFrame) -> list[str]:
    """Columnas numericas presentes que la reconciliacion debe transformar."""
    return [c for c in COLUMNAS_VALOR if c in frame.columns]


def _tiene_servicios(frame: pd.DataFrame) -> bool:
    return bool((frame["nivel"] == "servicio").any())


def _reagregar(
    comunas: pd.DataFrame, destino: pd.DataFrame, por: list[str]
) -> pd.DataFrame:
    """Reemplaza los valores de `destino` por la suma de `comunas` segun `por`.

    Los intervalos agregados se obtienen sumando los limites comunales, una cota
    **conservadora**: asume dependencia perfecta entre comunas y produce un
    intervalo mas ancho que el real si los errores son parcialmente
    independientes. Se prefiere errar por exceso de amplitud antes que declarar
    una precision que no se tiene.
    """
    columnas = _columnas_valor(comunas)
    suma = comunas.groupby(por, as_index=False)[columnas].sum()
    return destino.drop(columns=columnas).merge(suma, on=por, how="left")


def coherence_gap(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Mide la incoherencia entre el total regional y la suma de las comunas.

    Devuelve, por cada pronostico, el total regional predicho, la suma de las
    comunas y su diferencia absoluta y relativa. Es el diagnostico que justifica
    (o descarta) la necesidad de reconciliar.
    """
    frame = _con_estructura(predicciones)
    region = frame[frame["nivel"] == "region"]
    comunas = frame[frame["nivel"] == "comuna"]

    suma = (
        comunas.groupby(list(CLAVE_PRONOSTICO), as_index=False)["y_pred"]
        .sum()
        .rename(columns={"y_pred": "suma_comunas"})
    )
    total = region[[*CLAVE_PRONOSTICO, "y_pred"]].rename(columns={"y_pred": "total_region"})
    unido = total.merge(suma, on=list(CLAVE_PRONOSTICO), how="inner")
    unido["brecha_absoluta"] = (unido["total_region"] - unido["suma_comunas"]).abs()
    unido["brecha_relativa_pct"] = (
        unido["brecha_absoluta"] / unido["total_region"].replace(0, np.nan) * 100
    )
    return unido.round(4)


def reconcile_bottom_up(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Redefine cada agregado como la suma de las comunas que contiene.

    Las comunas quedan intactas. Con tres niveles, cada Servicio pasa a ser la
    suma de sus comunas y el total regional la suma de todas.
    """
    frame = _con_estructura(predicciones)
    clave = list(CLAVE_PRONOSTICO)
    comunas = frame[frame["nivel"] == "comuna"]
    partes = [comunas]
    if _tiene_servicios(frame):
        partes.append(
            _reagregar(comunas, frame[frame["nivel"] == "servicio"], [*clave, "servicio_id"])
        )
    partes.append(_reagregar(comunas, frame[frame["nivel"] == "region"], clave))
    return pd.concat(partes, ignore_index=True)


def _escalar_comunas(
    comunas: pd.DataFrame, totales: pd.DataFrame, por: list[str]
) -> pd.DataFrame:
    """Escala las comunas para que sumen el total de su grupo.

    `totales` trae la columna `total_objetivo` por grupo. Las proporciones las
    determinan los propios pronosticos comunales, de modo que la estructura
    territorial la sigue definiendo el modelo y no un supuesto externo. Si la
    suma comunal de un grupo es 0 el factor es indefinido y se deja en 1, para
    no inventar una redistribucion sobre un total vacio. Los intervalos se
    reescalan por el mismo factor, preservando su amplitud relativa.
    """
    suma = (
        comunas.groupby(por, as_index=False)["y_pred"]
        .sum()
        .rename(columns={"y_pred": "suma_comunas"})
    )
    factores = totales.merge(suma, on=por, how="inner")
    factores["factor"] = np.where(
        factores["suma_comunas"] > 0,
        factores["total_objetivo"] / factores["suma_comunas"],
        1.0,
    )
    escaladas = comunas.merge(factores[[*por, "factor"]], on=por, how="left")
    escaladas["factor"] = escaladas["factor"].fillna(1.0)
    for columna in _columnas_valor(escaladas):
        escaladas[columna] = escaladas[columna] * escaladas["factor"]
    return escaladas.drop(columns=["factor"])


def reconcile_top_down(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Conserva el total regional y lo reparte entre comunas segun su proporcion.

    Con tres niveles, los Servicios se recalculan como la suma de sus comunas ya
    reescaladas, de modo que los tres niveles quedan coherentes.
    """
    frame = _con_estructura(predicciones)
    clave = list(CLAVE_PRONOSTICO)
    region = frame[frame["nivel"] == "region"]
    totales = region[[*clave, "y_pred"]].rename(columns={"y_pred": "total_objetivo"})
    comunas = _escalar_comunas(frame[frame["nivel"] == "comuna"], totales, clave)

    partes = [region, comunas]
    if _tiene_servicios(frame):
        partes.append(
            _reagregar(comunas, frame[frame["nivel"] == "servicio"], [*clave, "servicio_id"])
        )
    return pd.concat(partes, ignore_index=True)


def reconcile_middle_out(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Conserva cada Servicio, lo reparte entre sus comunas y suma hacia la region.

    La hipotesis que evalua: el nivel intermedio es mas predecible que cada
    comuna (agrega ruido idiosincratico) pero conserva mas detalle territorial
    que el total regional, de modo que anclar ahi la reconciliacion podria
    mejorar ambos extremos.
    """
    frame = _con_estructura(predicciones)
    if not _tiene_servicios(frame):
        raise ValueError(
            "La reconciliacion middle-out requiere el nivel Servicio de Salud en "
            "las predicciones (panel construido con `servicio_map`)."
        )
    clave = list(CLAVE_PRONOSTICO)
    por_servicio = [*clave, "servicio_id"]
    servicios = frame[frame["nivel"] == "servicio"]
    totales = servicios[[*por_servicio, "y_pred"]].rename(
        columns={"y_pred": "total_objetivo"}
    )
    comunas = _escalar_comunas(frame[frame["nivel"] == "comuna"], totales, por_servicio)
    region = _reagregar(servicios, frame[frame["nivel"] == "region"], clave)
    return pd.concat([region, servicios, comunas], ignore_index=True)


def _matriz_estructural(
    comunas: list[str], servicio_de: dict[str, str], servicios: list[str]
) -> tuple[list[str], np.ndarray]:
    """Construye la matriz de sumas `S` (nodos x comunas) y el orden de los nodos.

    Filas: primero la region, luego los Servicios (si existen), luego cada comuna.
    Cada fila indica que comunas suman ese nodo.
    """
    m = len(comunas)
    filas = [np.ones(m)]
    nodos = [RM_SERIES_ID]
    for servicio in servicios:
        filas.append(np.array([1.0 if servicio_de[c] == servicio else 0.0 for c in comunas]))
        nodos.append(servicio)
    filas.extend(np.eye(m))
    nodos.extend(comunas)
    return nodos, np.vstack(filas)


def reconcile_wls_structural(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Reconciliacion por minimos cuadrados ponderados con pesos estructurales.

    Calcula `y_rec = S (S' L^-1 S)^-1 S' L^-1 y_base`, con `L` diagonal igual al
    numero de comunas que agrega cada nodo. Usa los pronosticos de todos los
    niveles a la vez en lugar de descartar alguno, que es la diferencia de fondo
    con bottom-up, top-down y middle-out.

    Los intervalos se desplazan en la misma magnitud que el pronostico puntual
    de su nodo; es una aproximacion que conserva la amplitud del modelo base.
    Si la proyeccion produce alguna comuna negativa, se trunca en 0 y los
    agregados se recalculan desde las comunas truncadas, de modo que la
    coherencia se mantiene exacta y ningun conteo queda negativo.
    """
    frame = _con_estructura(predicciones)
    clave = list(CLAVE_PRONOSTICO)
    comunas_df = frame[frame["nivel"] == "comuna"]
    comunas = sorted(comunas_df["series_id"].unique())
    tiene_servicios = _tiene_servicios(frame)
    if tiene_servicios:
        servicio_de = (
            comunas_df.drop_duplicates("series_id").set_index("series_id")["servicio_id"].to_dict()
        )
        servicios = sorted(frame.loc[frame["nivel"] == "servicio", "series_id"].unique())
    else:
        servicio_de, servicios = {}, []

    nodos, S = _matriz_estructural(comunas, servicio_de, servicios)
    # Un agregado sin comunas (p. ej. un Servicio cuyas comunas faltan en las
    # predicciones) deja una fila nula en `S`: su peso seria infinito y la
    # proyeccion devolveria NaN en silencio. Se rechaza de forma explicita.
    miembros = S.sum(axis=1)
    vacios = [nodo for nodo, n in zip(nodos, miembros) if n == 0]
    if vacios:
        raise ValueError(
            f"Agregados sin comunas en las predicciones: {vacios}. La jerarquia "
            "observada esta incompleta y no puede reconciliarse."
        )
    lambda_inv = np.diag(1.0 / miembros)
    proyeccion = np.linalg.solve(S.T @ lambda_inv @ S, S.T @ lambda_inv)

    grupos: list[pd.DataFrame] = []
    for _, grupo in frame.groupby(clave, sort=False):
        indexado = grupo.set_index("series_id")
        faltantes = set(nodos) - set(indexado.index)
        if faltantes:
            raise ValueError(
                "La reconciliacion WLS requiere todos los nodos de la jerarquia en "
                f"cada pronostico; faltan {sorted(faltantes)[:5]}."
            )
        base = indexado.loc[nodos, "y_pred"].to_numpy(dtype=float)
        comunas_rec = np.clip(proyeccion @ base, 0.0, None)
        reconciliado = S @ comunas_rec
        ajuste = reconciliado - base

        salida = indexado.loc[nodos].copy()
        salida["y_pred"] = reconciliado
        if "y_inferior" in salida.columns:
            salida["y_inferior"] = np.maximum(0.0, salida["y_inferior"].to_numpy() + ajuste)
        if "y_superior" in salida.columns:
            salida["y_superior"] = salida["y_superior"].to_numpy() + ajuste
        grupos.append(salida.reset_index())

    return pd.concat(grupos, ignore_index=True)


RECONCILIACIONES = {
    "bottom_up": reconcile_bottom_up,
    "top_down": reconcile_top_down,
    "middle_out": reconcile_middle_out,
    "wls_structural": reconcile_wls_structural,
}


def reconciliation_report(predicciones: pd.DataFrame) -> pd.DataFrame:
    """Resume la incoherencia por horizonte, antes de reconciliar."""
    brecha = coherence_gap(predicciones)
    return (
        brecha.groupby("horizonte", as_index=False)
        .agg(
            pronosticos=("brecha_absoluta", "size"),
            brecha_absoluta_media=("brecha_absoluta", "mean"),
            brecha_relativa_media_pct=("brecha_relativa_pct", "mean"),
            brecha_relativa_max_pct=("brecha_relativa_pct", "max"),
        )
        .round(4)
    )
