"""Persistencia del pronostico de demanda, para no recalcularlo en cada arranque.

El pronostico se obtiene ajustando el modelo seleccionado sobre el panel vigente. Ese
ajuste toma segundos y hasta ahora se repetia cada vez que arrancaba la API. Aqui se
guarda una sola vez junto con la evidencia de lo que lo produjo: cuando se genero, con
que modelo y configuracion, y sobre que snapshot exacto de datos.

**Por que se guarda el pronostico y no un modelo entrenado.** La interfaz de los modelos
es `fit_predict(supervised, origin, horizon)`: ajustar y predecir son un solo paso, y
cada horizonte ajusta su propio modelo. No existe un objeto entrenado con `predict` que
pueda reutilizarse despues, de modo que el artefacto reutilizable es el pronostico junto
con su procedencia. Reutilizarlo exige que las entradas no hayan cambiado.

**Vigencia.** Un pronostico guardado deja de ser valido si cambia el panel observado o la
seleccion congelada del benchmark. `motivo_desactualizacion` lo detecta comparando el
SHA256 de ambas entradas contra el manifiesto, y devuelve el motivo en texto. Quien lo
consume decide: el orquestador regenera el output y la API recalcula en memoria y lo
advierte, en lugar de servir un pronostico vencido en silencio.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.chile_time import run_datetime_chile
from src.data.raw_provenance import file_sha256
from src.models.features import RM_SERIES_ID
from src.models.forecast import (
    HORIZONTES_DEFECTO,
    WEEKLY_MART_PATH,
    DatosActuales,
    append_future_rows,
    forecast_future,
)
from src.models.registry import build_model

DIRECTORIO: Final[Path] = Path("data/processed/modeling")
RUTA_PRONOSTICO: Final[Path] = DIRECTORIO / "pronostico_demanda_sm.parquet"
RUTA_MANIFIESTO: Final[Path] = DIRECTORIO / "pronostico_demanda_sm_manifest.json"
RUTA_SELECCION: Final[Path] = Path("reports/modeling/benchmark_demanda_sm_seleccion.json")

NOMBRE_REGION: Final[str] = "Región Metropolitana"

# Versiones que condicionan el resultado numerico; se registran para poder explicar
# una diferencia entre dos ejecuciones del mismo codigo sobre los mismos datos.
PAQUETES_REGISTRADOS: Final[tuple[str, ...]] = (
    "pandas",
    "numpy",
    "pyarrow",
    "scikit-learn",
    "statsmodels",
    "lightgbm",
)

ESQUEMA: Final[pa.Schema] = pa.schema(
    [
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
        ("poblacion_anual", pa.float64()),
        ("modelo", pa.string()),
    ]
)


CLAVE_MART: Final[str] = "mart_urgencias_comuna_weekly"
CLAVE_SELECCION: Final[str] = "seleccion_benchmark"


@dataclass(frozen=True)
class Entradas:
    """Archivos que determinan el pronostico; su SHA256 define su vigencia."""

    mart_weekly: Path = WEEKLY_MART_PATH
    seleccion: Path = RUTA_SELECCION

    def rutas(self) -> dict[str, Path]:
        return {CLAVE_MART: self.mart_weekly, CLAVE_SELECCION: self.seleccion}

    def huella(self) -> dict[str, dict[str, str]]:
        """SHA256 y ruta de cada entrada, para registrarlos en el manifiesto."""
        return {clave: _huella(ruta) for clave, ruta in self.rutas().items()}

    @classmethod
    def desde_manifiesto(cls, manifiesto: dict[str, Any]) -> "Entradas":
        """Entradas en las rutas que el propio manifiesto registra.

        Comprobar la vigencia contra las rutas declaradas, y no contra las de por
        defecto, mantiene la verificacion valida aunque el pronostico se haya generado
        con otra ubicacion de los insumos.
        """
        registradas = manifiesto.get("entradas") or {}

        def _ruta(clave: str, defecto: Path) -> Path:
            registro = registradas.get(clave) or {}
            return Path(registro.get("ruta") or defecto)

        return cls(
            mart_weekly=_ruta(CLAVE_MART, WEEKLY_MART_PATH),
            seleccion=_ruta(CLAVE_SELECCION, RUTA_SELECCION),
        )


def _huella(ruta: Path) -> dict[str, str]:
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta la entrada del pronostico: {ruta.as_posix()}")
    return {"ruta": ruta.as_posix(), "sha256": file_sha256(ruta)}


def _version(paquete: str) -> str | None:
    try:
        return version(paquete)
    except PackageNotFoundError:
        return None


def nombres_series(panel: pd.DataFrame) -> dict[str, str]:
    """Nombre legible de cada serie; la region se muestra como tal."""
    nombres = panel.drop_duplicates("series_id").set_index("series_id")["comuna_glosa"].to_dict()
    nombres[RM_SERIES_ID] = NOMBRE_REGION
    return nombres


def cargar_seleccion(ruta: Path = RUTA_SELECCION) -> dict[str, Any]:
    """Lee la seleccion congelada del benchmark."""
    if not ruta.is_file():
        raise FileNotFoundError(
            f"Falta {ruta.as_posix()}: ejecute el stage `benchmark_demanda_sm`."
        )
    return json.loads(ruta.read_text(encoding="utf-8"))


def calcular_pronostico(datos: DatosActuales, seleccion: dict[str, Any]) -> pd.DataFrame:
    """Ajusta el modelo seleccionado y pronostica los horizontes congelados.

    Unica implementacion del calculo: la usan tanto el stage que lo persiste como la
    API cuando debe recalcular, de modo que ambos sirven exactamente lo mismo.
    """
    horizontes = tuple(int(h) for h in seleccion.get("horizontes", HORIZONTES_DEFECTO))
    modelo = build_model(seleccion["modelo_recomendado"], float(seleccion["nivel_intervalo"]))
    extendido = append_future_rows(datos.panel, max(horizontes), datos.calendario)
    return forecast_future(extendido, modelo, horizontes)


def _con_identificacion(pronostico: pd.DataFrame, nombres: dict[str, str]) -> pd.DataFrame:
    salida = pronostico.copy()
    salida["nombre"] = salida["series_id"].map(nombres)
    salida["nivel"] = salida["series_id"].map(
        lambda series_id: "region" if series_id == RM_SERIES_ID else "comuna"
    )
    if "fecha_inicio_semana" in salida.columns:
        salida["fecha_inicio_semana"] = pd.to_datetime(
            salida["fecha_inicio_semana"], errors="coerce"
        )
    else:
        salida["fecha_inicio_semana"] = pd.NaT
    return salida[[campo.name for campo in ESQUEMA]]


def construir_manifiesto(
    pronostico: pd.DataFrame,
    datos: DatosActuales,
    seleccion: dict[str, Any],
    entradas: Entradas | None = None,
) -> dict[str, Any]:
    """Describe que se pronostico, cuando y sobre que datos exactos."""
    entradas = entradas or Entradas()
    ahora = datetime.now(timezone.utc)
    observado = datos.panel[datos.panel["y"].notna()]
    ultima = observado.loc[observado["t"] == observado["t"].max()].iloc[0]
    niveles = pronostico["series_id"].map(
        lambda series_id: "region" if series_id == RM_SERIES_ID else "comuna"
    )
    series_por_nivel = (
        pronostico.assign(nivel=niveles).drop_duplicates("series_id")["nivel"].value_counts()
    )

    return {
        "dataset": "pronostico_demanda_sm",
        "generado_en_utc": ahora.isoformat().replace("+00:00", "Z"),
        "generado_en_chile": run_datetime_chile().isoformat(),
        "modelo": seleccion["modelo_recomendado"],
        "nivel_intervalo": float(seleccion["nivel_intervalo"]),
        "horizontes": [int(h) for h in seleccion.get("horizontes", HORIZONTES_DEFECTO)],
        "semilla": seleccion.get("semilla"),
        "ultima_semana_observada": {
            "t": int(ultima["t"]),
            "ano": int(ultima["ano"]),
            "semana": int(ultima["semana"]),
        },
        "series": {
            "total": int(pronostico["series_id"].nunique()),
            "region": int(series_por_nivel.get("region", 0)),
            "comuna": int(series_por_nivel.get("comuna", 0)),
        },
        "filas": int(len(pronostico)),
        "entradas": entradas.huella(),
        "versiones": {
            "python": platform.python_version(),
            **{paquete: _version(paquete) for paquete in PAQUETES_REGISTRADOS},
        },
    }


def guardar(
    pronostico: pd.DataFrame,
    manifiesto: dict[str, Any],
    nombres: dict[str, str],
    ruta_pronostico: Path = RUTA_PRONOSTICO,
    ruta_manifiesto: Path = RUTA_MANIFIESTO,
) -> None:
    """Escribe pronostico y manifiesto con reemplazo atomico.

    El manifiesto se escribe al final: si algo falla antes, no queda un manifiesto
    que describa un pronostico que no existe.
    """
    ruta_pronostico.parent.mkdir(parents=True, exist_ok=True)
    tabla = pa.Table.from_pandas(
        _con_identificacion(pronostico, nombres), schema=ESQUEMA, preserve_index=False
    )

    temporal_parquet = ruta_pronostico.with_suffix(ruta_pronostico.suffix + ".tmp")
    pq.write_table(tabla, temporal_parquet)
    os.replace(temporal_parquet, ruta_pronostico)

    temporal_json = ruta_manifiesto.with_suffix(ruta_manifiesto.suffix + ".tmp")
    temporal_json.write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporal_json, ruta_manifiesto)


def leer_manifiesto(ruta: Path = RUTA_MANIFIESTO) -> dict[str, Any]:
    return json.loads(ruta.read_text(encoding="utf-8"))


def cargar(
    ruta_pronostico: Path = RUTA_PRONOSTICO, ruta_manifiesto: Path = RUTA_MANIFIESTO
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Lee el pronostico persistido y su manifiesto, sin validar vigencia."""
    if not ruta_pronostico.is_file() or not ruta_manifiesto.is_file():
        raise FileNotFoundError(
            f"No hay pronostico persistido en {ruta_pronostico.parent.as_posix()}: "
            "ejecute el stage `forecast_demanda_sm`."
        )
    return pq.read_table(ruta_pronostico).to_pandas(), leer_manifiesto(ruta_manifiesto)


def motivo_desactualizacion(
    manifiesto: dict[str, Any], entradas: Entradas | None = None
) -> str | None:
    """Devuelve por que el pronostico guardado ya no sirve, o None si sigue vigente."""
    entradas = entradas or Entradas.desde_manifiesto(manifiesto)
    registradas = manifiesto.get("entradas") or {}
    try:
        actuales = entradas.huella()
    except FileNotFoundError as error:
        return str(error)

    for clave, actual in actuales.items():
        anterior = registradas.get(clave)
        if anterior is None:
            return f"el manifiesto no registra la entrada '{clave}'"
        if anterior.get("sha256") != actual["sha256"]:
            return f"cambió '{clave}' respecto del snapshot con que se generó"
    return None
