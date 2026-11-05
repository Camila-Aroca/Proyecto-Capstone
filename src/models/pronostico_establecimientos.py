"""Pronóstico vigente por establecimiento: cálculo, persistencia y vigencia.

Sigue el diseño de `src/models/persistence.py` (se persiste el pronóstico con su
procedencia, no un modelo entrenado), con una diferencia deliberada en la
vigencia: además del mart y de la selección congelada, el manifiesto registra
la identidad del **snapshot del año en curso**. Las semanas recientes entran al
panel desde ese snapshot; si se actualiza, el pronóstico guardado ya no
corresponde a los datos y debe regenerarse. La identidad usa el SHA256 del RAW
que cada Parquet anual declara en su footer, que no depende del equipo que lo
procesó; si el Parquet no lo declara, se usa el SHA256 del propio Parquet.

Un pronóstico por objetivo, ambos en un mismo archivo con la columna `objetivo`.
Solo se publican establecimientos: la serie total del panel no reconcilia con
ellos cuando el modelo elegido no es jerárquico, y la cifra regional ya la
entrega el modelo comunal, que sí reconcilia.

**Guardia de plausibilidad.** Un pronóstico que supera `FACTOR_PLAUSIBLE` veces
el máximo observado por ese establecimiento en las últimas
`SEMANAS_PLAUSIBLES` semanas se marca `fuera_de_rango`. No se recorta ni se
corrige: queda registrado para que quien lo sirva no lo muestre. El boosting
con objetivo de Poisson trabaja en escala logarítmica y puede extrapolar de
forma exponencial ante combinaciones de variables poco vistas.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.chile_time import run_datetime_chile
from src.data.raw_provenance import file_sha256, processed_raw_sha256
from src.models.establecimientos import (
    MART_PATH,
    OBJETIVOS,
    Objetivo,
    build_establishment_panel,
    fixed_universe,
    load_current_weekly,
    load_mart,
    select_universe,
)
from src.models.features import RM_SERIES_ID
from src.models.forecast import append_future_rows, forecast_future
from src.models.holdout import URGENCIAS_PROCESSED_DIR, holdout_years
from src.models.registry import build_model

DIRECTORIO: Final[Path] = Path("data/processed/modeling")
RUTA_PRONOSTICO: Final[Path] = DIRECTORIO / "pronostico_establecimientos_sm.parquet"
RUTA_MANIFIESTO: Final[Path] = DIRECTORIO / "pronostico_establecimientos_sm_manifest.json"
RUTA_SELECCION: Final[Path] = Path("reports/modeling/benchmark_establecimientos_sm_seleccion.json")
FACTOR_PLAUSIBLE: Final[float] = 2.0
SEMANAS_PLAUSIBLES: Final[int] = 52

ESQUEMA: Final[pa.Schema] = pa.schema([
    ("objetivo", pa.string()),
    ("series_id", pa.string()),
    ("nivel", pa.string()),
    ("establecimiento_glosa", pa.string()),
    ("comuna_codigo", pa.string()),
    ("tipo_establecimiento_urgencia", pa.string()),
    ("horizonte", pa.int16()),
    ("origen", pa.int32()),
    ("t", pa.int32()),
    ("ano", pa.int16()),
    ("semana", pa.int16()),
    ("fecha_inicio_semana", pa.date32()),
    ("y_pred", pa.float64()),
    ("y_inferior", pa.float64()),
    ("y_superior", pa.float64()),
    ("modelo", pa.string()),
    ("maximo_observado_reciente", pa.float64()),
    ("fuera_de_rango", pa.bool_()),
])


@dataclass
class DatosObjetivo:
    """Panel observado de un objetivo, su calendario y el universo usado."""

    objetivo: Objetivo
    panel: pd.DataFrame
    calendario: pd.DataFrame
    universo: pd.DataFrame
    excluidos: pd.DataFrame


def cargar_seleccion(ruta: Path = RUTA_SELECCION) -> dict[str, Any]:
    if not ruta.is_file():
        raise FileNotFoundError(
            f"Falta {ruta.as_posix()}: ejecute el stage `benchmark_establecimientos_sm`."
        )
    return json.loads(ruta.read_text(encoding="utf-8"))


def _calendario(semanal: pd.DataFrame) -> pd.DataFrame:
    """Fecha de inicio de cada semana DEIS observada."""
    return (
        semanal.groupby(["ano", "semana"], as_index=False)["fecha_inicio_semana"].min()
        .assign(fecha_inicio_semana=lambda d: pd.to_datetime(d["fecha_inicio_semana"]))
    )


def preparar_datos(
    seleccion: dict[str, Any], mart: pd.DataFrame | None = None, actual: pd.DataFrame | None = None
) -> dict[str, DatosObjetivo]:
    """Panel de cada objetivo: mart más las semanas completas del año en curso.

    El universo es el del benchmark, restringido a quienes reportan todas las
    semanas del año en curso (la misma regla del holdout).
    """
    mart = load_mart() if mart is None else mart
    if actual is None:
        anos = holdout_years(int(mart["ano"].max()))
        actual = load_current_weekly(anos)[0] if anos else mart.iloc[0:0]
    semanal = pd.concat([mart, actual[mart.columns]], ignore_index=True)
    datos = {}
    for nombre, objetivo in OBJETIVOS.items():
        ano_inicio = int(seleccion[nombre]["universo"]["ano_inicio"])
        universo = select_universe(mart, objetivo, ano_inicio=ano_inicio)
        if not actual.empty:
            universo, excluidos = fixed_universe(universo, actual, objetivo)
        else:
            excluidos = pd.DataFrame()
        panel = build_establishment_panel(semanal, objetivo, universo, ano_inicio)
        datos[nombre] = DatosObjetivo(objetivo, panel, _calendario(semanal), universo, excluidos)
    return datos


def calcular_pronostico(datos: DatosObjetivo, seleccion: dict[str, Any]) -> pd.DataFrame:
    """Ajusta el modelo congelado del objetivo y pronostica sus horizontes."""
    horizontes = tuple(int(h) for h in seleccion["horizontes"])
    modelo = build_model(seleccion["modelo_recomendado"], float(seleccion["nivel_intervalo"]))
    exogenas = datos.objetivo.exogenas
    extendido = append_future_rows(datos.panel, max(horizontes), datos.calendario, exogenous=exogenas)
    pronostico = forecast_future(extendido, modelo, horizontes, exogenous=exogenas)
    pronostico = pronostico[pronostico["series_id"] != RM_SERIES_ID]
    atributos = datos.panel.drop_duplicates("series_id")[
        ["series_id", "nivel", "establecimiento_glosa", "comuna_codigo", "tipo_establecimiento_urgencia"]
    ]
    return marcar_fuera_de_rango(
        pronostico.merge(atributos, on="series_id", how="left"), datos.panel
    ).assign(objetivo=datos.objetivo.nombre).reset_index(drop=True)


def marcar_fuera_de_rango(
    pronostico: pd.DataFrame, panel: pd.DataFrame,
    factor: float = FACTOR_PLAUSIBLE, semanas: int = SEMANAS_PLAUSIBLES,
) -> pd.DataFrame:
    """Marca los pronósticos que exceden `factor` veces el máximo reciente de su serie."""
    reciente = panel[panel["t"] > panel["t"].max() - semanas]
    maximo = reciente.groupby("series_id")["y"].max().rename("maximo_observado_reciente")
    salida = pronostico.merge(maximo, on="series_id", how="left")
    salida["fuera_de_rango"] = salida["y_pred"] > factor * salida["maximo_observado_reciente"]
    return salida


def huella_entradas(
    mart_path: Path = MART_PATH,
    seleccion_path: Path = RUTA_SELECCION,
    processed_dir: Path = URGENCIAS_PROCESSED_DIR,
    anos_en_curso: list[int] | None = None,
) -> dict[str, dict[str, str]]:
    """Identidad de cada entrada del pronóstico, para registrar y verificar vigencia."""
    entradas = {
        "mart_urgencias_establecimiento_weekly": {"ruta": mart_path.as_posix(), "sha256": file_sha256(mart_path)},
        "seleccion_benchmark": {"ruta": seleccion_path.as_posix(), "sha256": file_sha256(seleccion_path)},
    }
    for ano in anos_en_curso or []:
        ruta = processed_dir / f"urgencias_rm_{ano}.parquet"
        raw = processed_raw_sha256(ruta)
        entradas[f"urgencias_{ano}"] = {
            "ruta": ruta.as_posix(),
            # Identidad del RAW si el Parquet la declara; si no, la del Parquet.
            "sha256": raw if raw else file_sha256(ruta),
            "tipo": "raw_sha256" if raw else "parquet_sha256",
        }
    return entradas


def construir_manifiesto(
    pronostico: pd.DataFrame, datos: dict[str, DatosObjetivo], seleccion: dict[str, Any],
    entradas: dict[str, dict[str, str]],
) -> dict[str, Any]:
    objetivos = {}
    for nombre, d in datos.items():
        ultima = d.panel.loc[d.panel["t"] == d.panel["t"].max()].iloc[0]
        propio = pronostico[pronostico["objetivo"] == nombre]
        objetivos[nombre] = {
            "modelo": seleccion[nombre]["modelo_recomendado"],
            "horizontes": [int(h) for h in seleccion[nombre]["horizontes"]],
            "nivel_intervalo": float(seleccion[nombre]["nivel_intervalo"]),
            "ultima_semana_observada": {"t": int(ultima["t"]), "ano": int(ultima["ano"]), "semana": int(ultima["semana"])},
            "establecimientos": int(propio["series_id"].nunique()),
            "fuera_de_rango": int(propio["fuera_de_rango"].sum()),
            "excluidos_por_cobertura_en_curso": d.excluidos["establecimiento_codigo"].astype(int).tolist()
            if not d.excluidos.empty else [],
            "filas": int(len(propio)),
        }
    return {
        "dataset": "pronostico_establecimientos_sm",
        "generado_en_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generado_en_chile": run_datetime_chile().isoformat(),
        "objetivos": objetivos,
        "filas": int(len(pronostico)),
        "entradas": entradas,
    }


def guardar(
    pronostico: pd.DataFrame, manifiesto: dict[str, Any],
    ruta_pronostico: Path = RUTA_PRONOSTICO, ruta_manifiesto: Path = RUTA_MANIFIESTO,
) -> None:
    """Escribe pronóstico y manifiesto con reemplazo atómico; el manifiesto al final."""
    ruta_pronostico.parent.mkdir(parents=True, exist_ok=True)
    tabla = pronostico.copy()
    tabla["fecha_inicio_semana"] = pd.to_datetime(tabla["fecha_inicio_semana"], errors="coerce")
    tabla = pa.Table.from_pandas(tabla[[c.name for c in ESQUEMA]], schema=ESQUEMA, preserve_index=False)
    temporal = ruta_pronostico.with_suffix(ruta_pronostico.suffix + ".tmp")
    pq.write_table(tabla, temporal)
    os.replace(temporal, ruta_pronostico)
    temporal_json = ruta_manifiesto.with_suffix(ruta_manifiesto.suffix + ".tmp")
    temporal_json.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal_json, ruta_manifiesto)


def motivo_desactualizacion(
    manifiesto: dict[str, Any], processed_dir: Path = URGENCIAS_PROCESSED_DIR,
) -> str | None:
    """Por qué el pronóstico guardado ya no sirve, o None si sigue vigente.

    Compara cada entrada registrada con su identidad actual, y detecta además
    un año en curso nuevo que el manifiesto no registra (por ejemplo, el primer
    archivo del año siguiente).
    """
    registradas = manifiesto.get("entradas") or {}
    if not registradas:
        return "el manifiesto no registra sus entradas"
    try:
        mart = Path(registradas["mart_urgencias_establecimiento_weekly"]["ruta"])
        anos_actuales = holdout_years(int(pq.read_table(mart, columns=["ano"]).column("ano").to_pandas().max()), processed_dir)
        actuales = huella_entradas(
            mart_path=mart, seleccion_path=Path(registradas["seleccion_benchmark"]["ruta"]),
            processed_dir=processed_dir, anos_en_curso=anos_actuales,
        )
    except (FileNotFoundError, KeyError, OSError) as error:
        return f"no se pudieron verificar las entradas ({error})"
    for clave, actual in actuales.items():
        anterior = registradas.get(clave)
        if anterior is None:
            return f"apareció la entrada '{clave}', que el pronóstico no consideró"
        if anterior.get("sha256") != actual["sha256"]:
            return f"cambió '{clave}' respecto del snapshot con que se generó"
    return None


def cargar(
    ruta_pronostico: Path = RUTA_PRONOSTICO, ruta_manifiesto: Path = RUTA_MANIFIESTO
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Lee el pronóstico persistido y su manifiesto, sin validar vigencia."""
    if not ruta_pronostico.is_file() or not ruta_manifiesto.is_file():
        raise FileNotFoundError(
            "No hay pronóstico por establecimiento persistido: ejecute el stage "
            "`forecast_establecimientos_sm`."
        )
    return pq.read_table(ruta_pronostico).to_pandas(), json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
