"""Preparacion de datos para evaluar el modelo en el periodo posterior al entrenamiento.

El benchmark selecciona el modelo con 2021-2025. El **holdout** son los anios
posteriores, que la seleccion nunca vio: hoy, el anio en curso. Evaluar ahi
responde si la seleccion generaliza o si solo se ajusto al periodo en que se
eligio.

El anio en curso trae cuatro problemas que este modulo resuelve de forma
explicita y auditable, sin corregir ni imputar datos:

1. **Es una fuente mutable.** DEIS sobrescribe el archivo del anio en curso sin
   versionarlo. `snapshot_info` calcula el SHA256 del RAW y del Parquet
   procesado que efectivamente se evaluan y contrasta el RAW con el manifiesto
   de procedencia, para que cada resultado quede atado a un snapshot
   identificable.
2. **Termina en una semana truncada.** La ultima semana publicada suele tener
   menos de 7 dias; tratada como semana completa pareceria una caida de
   demanda. Se excluyen las semanas con menos dias que los de una semana
   regular, y se informa cuales.
3. **Puede traer territorios sin historia.** Una comuna que reporta por primera
   vez no tiene rezagos ni identidad aprendida y no es pronosticable. Se
   excluye y se cuantifica su volumen.
4. **Puede perder territorios a mitad de anio.** Un establecimiento que deja de
   reportar deja a su comuna sin filas: eso no es demanda cero, es ausencia de
   dato, y rellenarla con ceros seria inventar. La comuna se excluye y se
   informa desde que semana falta.

Con 3 y 4, la evaluacion usa un **universo fijo** de comunas con cobertura
completa en todo el periodo, y el total regional se define sobre ese mismo
universo antes y durante el holdout: un total que sumara distintas comunas en
distintas semanas cambiaria la definicion del target a mitad de la serie. Si lo
excluido supera `MAX_SHARE_EXCLUIDA_PCT` del volumen, la evaluacion falla,
porque ya no representaria a la region.

Ningun anio esta fijado en el codigo: el holdout son los anios con datos
procesados posteriores al ultimo anio del mart de entrenamiento.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pandas as pd

from src.data.build_urgencias_comuna_marts import build_weekly_mart, load_urgencias_source
from src.data.clean_poblacion_proyecciones import load_rm_population
from src.data.download_deis_sources import canonical_urgencias_raw_path, file_sha256
from src.models.features import SEASONAL_PERIOD, TARGET

URGENCIAS_PROCESSED_DIR: Final[Path] = Path("data/processed/urgencias")
URGENCIAS_RAW_DIR: Final[Path] = Path("data/raw/urgencias")
MANIFEST_PATH: Final[Path] = Path("data/raw/provenance_manifest.json")
# Dias de una semana regular del calendario DEIS.
DIAS_SEMANA_COMPLETA: Final[int] = 7
# Volumen maximo excluido por cobertura antes de declarar la evaluacion no
# representativa de la region (porcentaje del volumen del ultimo anio de
# entrenamiento).
MAX_SHARE_EXCLUIDA_PCT: Final[float] = 5.0
_PATRON_ANUAL: Final[re.Pattern[str]] = re.compile(r"urgencias_rm_(\d{4})\.parquet$")


def holdout_years(
    ultimo_ano_entrenamiento: int, processed_dir: Path = URGENCIAS_PROCESSED_DIR
) -> list[int]:
    """Anios con Urgencias procesadas posteriores al periodo de entrenamiento."""
    anos = []
    for ruta in processed_dir.glob("urgencias_rm_*.parquet"):
        coincidencia = _PATRON_ANUAL.search(ruta.name)
        if coincidencia and int(coincidencia.group(1)) > ultimo_ano_entrenamiento:
            anos.append(int(coincidencia.group(1)))
    return sorted(anos)


def _registro_en_manifiesto(
    ano: int, raw_sha256: str, manifest_path: Path
) -> tuple[str, str | None]:
    """Estado del RAW frente al manifiesto: registrado, distinto o sin registro."""
    if not manifest_path.exists():
        return "sin_manifiesto", None
    manifiesto = json.loads(manifest_path.read_text(encoding="utf-8"))
    entrada = next(
        (e for e in manifiesto if e.get("source_id") == f"deis_urgencias_{ano}"), None
    )
    if entrada is None or not entrada.get("snapshots"):
        return "sin_registro", None
    ultimo = entrada["snapshots"][-1]
    if ultimo.get("raw_sha256") == raw_sha256:
        return "registrado", ultimo.get("downloaded_at")
    return "difiere_del_registrado", ultimo.get("downloaded_at")


def snapshot_info(
    anos: list[int],
    raw_dir: Path = URGENCIAS_RAW_DIR,
    processed_dir: Path = URGENCIAS_PROCESSED_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> pd.DataFrame:
    """Identifica con SHA256 el snapshot exacto que se evalua, por anio.

    Registra el hash del RAW (la fuente) y del Parquet procesado (lo que el
    modelo lee realmente). No modifica el manifiesto: registrar procedencia es
    responsabilidad de la etapa de ingesta, no de una evaluacion.
    """
    filas = []
    for ano in anos:
        raw = raw_dir / canonical_urgencias_raw_path(ano).name
        procesado = processed_dir / f"urgencias_rm_{ano}.parquet"
        raw_sha = file_sha256(raw) if raw.is_file() else None
        estado, registrado_en = (
            _registro_en_manifiesto(ano, raw_sha, manifest_path)
            if raw_sha
            else ("raw_ausente", None)
        )
        filas.append(
            {
                "ano": ano,
                "raw_path": raw.as_posix(),
                "raw_bytes": raw.stat().st_size if raw.is_file() else None,
                "raw_sha256": raw_sha,
                "procesado_path": procesado.as_posix(),
                "procesado_sha256": file_sha256(procesado),
                "estado_procedencia": estado,
                "procedencia_registrada_en": registrado_en,
            }
        )
    return pd.DataFrame(filas)


def load_holdout_weekly(
    anos: list[int],
    volumen_referencia: pd.Series,
    processed_dir: Path = URGENCIAS_PROCESSED_DIR,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Construye el semanal comunal del holdout con la misma logica que el mart.

    Reutiliza la carga y la agregacion de `build_urgencias_comuna_marts`, de modo
    que las definiciones de atenciones, causas y reportantes son identicas a las
    del entrenamiento. La poblacion sale del mismo cuadro INE que la dimension
    canonica, para los anios del holdout.

    `volumen_referencia` es el volumen del target por comuna en el ultimo anio de
    entrenamiento: define el universo de comunas con historia y sirve para
    medir cuanto pesa lo que se excluye.

    Devuelve el semanal del universo evaluable y un diccionario con lo excluido
    y por que: `semanas_incompletas`, `comunas_sin_historia`,
    `comunas_cobertura_incompleta` y `fecha_corte`.
    """
    comunas_entrenamiento = set(volumen_referencia.index.astype(str))
    fuente = load_urgencias_source(input_dir=processed_dir, years=tuple(anos))
    poblacion = load_rm_population(years=tuple(anos)).rename(
        columns={"poblacion": "poblacion_anual"}
    )
    semanal = build_weekly_mart(fuente, poblacion)

    # --- Semanas truncadas --------------------------------------------------
    # La semana 53 se descarta aguas abajo en `build_panel` por ser un fragmento
    # de calendario; aqui se tratan las semanas regulares que quedaron cortas.
    dias = (
        fuente.groupby(["ano", "semana"])["fecha"].nunique().rename("dias").reset_index()
    )
    volumen = (
        fuente[fuente["id_causa"] == 36]
        .groupby(["ano", "semana"])["total"]
        .sum()
        .rename(TARGET)
        .reset_index()
    )
    calendario = dias.merge(volumen, on=["ano", "semana"], how="left")
    regulares = calendario["semana"] != SEASONAL_PERIOD + 1
    incompletas = calendario[regulares & (calendario["dias"] < DIAS_SEMANA_COMPLETA)]
    completas = calendario[regulares & (calendario["dias"] >= DIAS_SEMANA_COMPLETA)]
    claves_incompletas = set(zip(incompletas["ano"], incompletas["semana"]))
    semanal = semanal[
        ~semanal[["ano", "semana"]].apply(tuple, axis=1).isin(claves_incompletas)
    ]

    # --- Comunas sin historia -----------------------------------------------
    nuevas = semanal[~semanal["comuna_codigo"].isin(comunas_entrenamiento)]
    sin_historia = nuevas.groupby(["comuna_codigo", "comuna_glosa"], as_index=False).agg(
        semanas=("semana", "nunique"), atenciones_id36=(TARGET, "sum")
    )
    total_holdout = float(semanal[TARGET].sum())
    participacion = (
        sin_historia["atenciones_id36"] / total_holdout * 100
        if total_holdout
        else pd.Series(0.0, index=sin_historia.index)
    )
    sin_historia["share_holdout_pct"] = participacion.round(3)
    semanal = semanal[semanal["comuna_codigo"].isin(comunas_entrenamiento)]

    # --- Comunas con historia pero cobertura incompleta ----------------------
    # Se comparan las semanas regulares completas del holdout contra las que
    # cada comuna efectivamente reporta. Una comuna ausente por completo del
    # holdout tambien cae aqui, con cero semanas.
    esperadas = len(completas)
    regulares_semanal = semanal[semanal["semana"] != SEASONAL_PERIOD + 1]
    presentes = regulares_semanal.groupby("comuna_codigo")["semana"].agg(
        ["nunique", "max"]
    )
    presentes = presentes.reindex(sorted(comunas_entrenamiento)).fillna(0)
    cortas = presentes[presentes["nunique"] < esperadas]
    total_referencia = float(volumen_referencia.sum())
    cobertura_incompleta = pd.DataFrame(
        {
            "comuna_codigo": cortas.index,
            "semanas_con_datos": cortas["nunique"].astype(int).to_numpy(),
            "semanas_esperadas": esperadas,
            "ultima_semana_con_datos": cortas["max"].astype(int).to_numpy(),
            "share_referencia_pct": [
                round(float(volumen_referencia.get(c, 0.0)) / total_referencia * 100, 3)
                if total_referencia
                else 0.0
                for c in cortas.index
            ],
        }
    )
    semanal = semanal[~semanal["comuna_codigo"].isin(set(cortas.index))]

    excluido = float(cobertura_incompleta["share_referencia_pct"].sum())
    if excluido > MAX_SHARE_EXCLUIDA_PCT:
        raise ValueError(
            f"Las comunas con cobertura incompleta suman {excluido:.2f}% del volumen de "
            f"referencia (limite {MAX_SHARE_EXCLUIDA_PCT}%): la evaluacion ya no "
            f"representaria a la region. Comunas: {list(cortas.index)}."
        )

    diagnostico = {
        "semanas_incompletas": incompletas.reset_index(drop=True),
        "comunas_sin_historia": sin_historia.reset_index(drop=True),
        "comunas_cobertura_incompleta": cobertura_incompleta.reset_index(drop=True),
        "fecha_corte": pd.DataFrame(
            {"fecha_maxima": [fuente["fecha"].max()], "fecha_minima": [fuente["fecha"].min()]}
        ),
    }
    return semanal.reset_index(drop=True), diagnostico
