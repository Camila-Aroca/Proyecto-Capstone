"""EDA reproducible de las Estadísticas Hospitalarias REM-20 (DEIS).

Perfila los RAW de ``data/raw/estadisticas_hospitalarias/`` y los dos Parquet de
``clean_estadisticas_hospitalarias``: estructura, filas agregadas del origen y su
conciliación con el detalle, definición observada de cada razón publicada,
ocupación sobre la disponibilidad, cobertura del año en curso, coherencia con la
dotación de camas, categorización CUDYR y las áreas de psiquiatría de la Región
Metropolitana. Reporta valores observados antes que su lectura; no corrige nada.

Escribe ``reports/eda/eda_estadisticas_hospitalarias.md`` y su resumen verificable
``reports/eda/eda_estadisticas_hospitalarias_resumen.json``.

Uso (vía pipeline): ``python scripts/run_pipeline.py --stage eda_estadisticas_hospitalarias``
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.data import clean_estadisticas_hospitalarias as clean  # noqa: E402
from src.data import download_estadisticas_hospitalarias as download  # noqa: E402

OUTPUT_REPORT: Final[Path] = Path("reports/eda/eda_estadisticas_hospitalarias.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/eda/eda_estadisticas_hospitalarias_resumen.json")
TITULO: Final[str] = "# EDA: Estadísticas Hospitalarias REM-20 (DEIS)"
DOTACION_PATH: Final[Path] = Path("data/processed/camas/dotacion_camas_snss.parquet")

MESES = list(clean.MESES_COLUMNAS)
LLAVE = ["ano", "servicio_salud_codigo", "establecimiento_codigo", "nivel_cuidado_codigo"]
PSIQUIATRIA = tuple(range(418, 430))  # niveles 418-429 del catálogo; 427 es sociosanitario, no psiquiatría
SOCIOSANITARIO = 427
CRITICOS = ("a1", "a2", "a3", "b1", "b2")
MEDIOS = ("b3", "c1", "c2")
BASICOS = ("c3", "d1", "d2", "d3")
TOLERANCIA_RAZON = 0.0051  # razones publicadas con 2 decimales
TOLERANCIA_AMPLIA = 0.06  # sensibilidad: razones calculadas sobre un promedio de camas ya redondeado
# Campo del diccionario REM-20 (formato largo de datos.gob.cl) -> glosa del libro.
# La correspondencia es por nombre: el diccionario no la declara.
CAMPO_A_INDICADOR = {
    "DIAS_CAMAS_DISPONIBLES": "Dias Cama Disponibles", "DIAS_CAMAS_OCUPADAS": "Dias Cama Ocupados",
    "DIAS_ESTADA": "Dias de Estada", "NUMERO_EGRESOS": "Numero de Egresos",
    "EGRESOS_FALLECIDOS": "Egresos Fallecidos", "TRASLADOS": "Traslados",
    "PROMEDIO_CAMAS_DISPONIBLE": "Promedio Cama Disponibles", "INDICE_OCUPACIONAL": "Indice Ocupacional",
    "PROMEDIO_DIAS_ESTADA": "Promedio Días de Estada", "LETALIDAD": "Letalidad",
    "INDICE_ROTACION": "Indice de Rotación",
}
CITA_CUDYR = (
    "González P, Kappes M, Gallardo-Vargas C. Cuidados según dependencia y riesgo en hospitales de "
    "baja complejidad del Servicio de Salud Reloncaví, Chile. *Ciencia y Enfermería*. 2024;30:31. "
    "doi:[10.29393/CE30-31CSPC30031](https://doi.org/10.29393/CE30-31CSPC30031)"
)


# --------------------------------------------------------------------------- #
# Cálculos
# --------------------------------------------------------------------------- #

def ancho(detalle: pd.DataFrame, columna: str = "acumulado") -> pd.DataFrame:
    """Una fila por área-año y una columna por indicador."""
    return detalle.pivot_table(index=LLAVE, columns="indicador", values=columna, aggfunc="first")


def es_rm(servicios: pd.Series) -> pd.Series:
    """Servicios de Salud de la Región Metropolitana: los ``Metropolitano *`` del origen."""
    return servicios.str.startswith("Metropolitano")


def definicion_razones(w: pd.DataFrame) -> dict[str, dict[int, dict[str, float]]]:
    """Por año, proporción de áreas cuya razón publicada coincide con cada fórmula candidata."""
    egresos = w["Numero de Egresos"]
    con_traslados = egresos + w["Traslados"]
    candidatas = {
        "Indice Ocupacional": {"100 * ocupados / disponibles":
                               100 * w["Dias Cama Ocupados"] / w["Dias Cama Disponibles"]},
        "Promedio Días de Estada": {"estada / (egresos + traslados)": w["Dias de Estada"] / con_traslados,
                                    "estada / egresos": w["Dias de Estada"] / egresos},
        "Letalidad": {"100 * fallecidos / (egresos + traslados)": 100 * w["Egresos Fallecidos"] / con_traslados,
                      "100 * fallecidos / egresos": 100 * w["Egresos Fallecidos"] / egresos},
        "Indice de Rotación": {"(egresos + traslados) / promedio camas": con_traslados / w["Promedio Cama Disponibles"],
                               "egresos / promedio camas": egresos / w["Promedio Cama Disponibles"]},
    }
    salida: dict[str, dict[int, dict[str, float]]] = {}
    for razon, formulas in candidatas.items():
        publicado = w[razon]
        salida[razon] = {}
        for ano in sorted(w.index.get_level_values("ano").unique()):
            fila = publicado.index.get_level_values("ano") == ano
            resultado: dict[str, float] = {}
            for nombre, calculado in formulas.items():
                comparable = fila & publicado.notna().to_numpy() & np.isfinite(calculado.to_numpy())
                n = int(comparable.sum())
                diferencia = (calculado[comparable] - publicado[comparable]).abs()
                resultado[nombre] = round(float((diferencia <= TOLERANCIA_RAZON).mean()), 4) if n else float("nan")
                resultado[f"{nombre} (±{TOLERANCIA_AMPLIA})"] = (
                    round(float((diferencia <= TOLERANCIA_AMPLIA).mean()), 4) if n else float("nan"))
            resultado["areas_comparables"] = int((fila & publicado.notna().to_numpy()).sum())
            salida[razon][int(ano)] = resultado
    return salida


def cambios_de_definicion(definiciones: dict[str, dict[int, dict[str, float]]],
                          umbral: float = 0.99) -> dict[str, list[dict[str, Any]]]:
    """Tramos de años en que una misma fórmula explica al menos ``umbral`` de las áreas (±0,005)."""
    salida: dict[str, list[dict[str, Any]]] = {}
    for razon, por_ano in definiciones.items():
        tramos: list[dict[str, Any]] = []
        for ano, resultado in sorted(por_ano.items()):
            formula = next((f for f, v in resultado.items() if "±" not in f and f != "areas_comparables"
                            and isinstance(v, float) and not np.isnan(v) and v >= umbral), None)
            if tramos and tramos[-1]["formula"] == formula and tramos[-1]["hasta"] == ano - 1:
                tramos[-1]["hasta"] = ano
            else:
                tramos.append({"formula": formula, "desde": ano, "hasta": ano})
        salida[razon] = tramos
    return salida


def sobreocupacion(detalle: pd.DataFrame) -> pd.DataFrame:
    """Área-meses con días cama ocupados por sobre los disponibles (y su índice)."""
    ocupados = detalle[detalle.indicador == "Dias Cama Ocupados"].set_index(LLAVE)[MESES]
    disponibles = detalle[detalle.indicador == "Dias Cama Disponibles"].set_index(LLAVE)[MESES]
    largo = pd.DataFrame({
        "ocupados": ocupados.stack(future_stack=True),
        "disponibles": disponibles.stack(future_stack=True),
    }).dropna()
    largo.index = largo.index.set_names([*LLAVE, "mes"])
    return largo


def coherencia_dotacion(w: pd.DataFrame, dotacion: pd.DataFrame | None) -> dict[str, Any]:
    """Promedio anual de camas disponibles (REM-20) frente a la dotación declarada del mismo año."""
    if dotacion is None:
        return {"disponible": False}
    largo = dotacion.melt(id_vars=["establecimiento_codigo", "area_funcional_codigo"],
                          value_vars=[c for c in dotacion.columns if c.startswith("camas_")],
                          var_name="ano", value_name="camas_dotacion").dropna()
    largo["ano"] = largo["ano"].str.removeprefix("camas_").astype(int)
    largo = largo.groupby(["ano", "establecimiento_codigo", "area_funcional_codigo"]).camas_dotacion.sum()
    rem = w["Promedio Cama Disponibles"].groupby(["ano", "establecimiento_codigo", "nivel_cuidado_codigo"]).sum()
    rem.index = rem.index.set_names(["ano", "establecimiento_codigo", "area_funcional_codigo"])
    unido = pd.concat([rem.rename("promedio_disponibles"), largo], axis=1, join="inner")
    unido = unido[unido.index.get_level_values("ano") <= int(largo.index.get_level_values("ano").max())]
    diferencia = (unido.promedio_disponibles - unido.camas_dotacion).abs()
    psiq = unido.index.get_level_values("area_funcional_codigo").isin(
        [c for c in PSIQUIATRIA if c != SOCIOSANITARIO])
    return {
        "disponible": True,
        "areas_ano_comparadas": int(len(unido)),
        "a_1_cama_o_menos": round(float((diferencia <= 1).mean()), 4),
        "promedio_bajo_dotacion_en_mas_de_10pct": round(
            float((unido.promedio_disponibles < 0.9 * unido.camas_dotacion).mean()), 4),
        "psiquiatria_areas_ano": int(psiq.sum()),
        "psiquiatria_a_1_cama_o_menos": round(float((diferencia[psiq] <= 1).mean()), 4) if psiq.any() else None,
    }


def calcular(indicadores: clean.Indicadores, conciliacion: dict[str, Any], detalle: pd.DataFrame,
             categorizacion: pd.DataFrame, hashes: dict[str, dict[str, str]],
             dotacion: pd.DataFrame | None) -> dict[str, Any]:
    w = ancho(detalle)
    anos = sorted(int(a) for a in detalle.ano.unique())
    meses_por_ano = {str(k): v for k, v in sorted(indicadores.meses_por_ano.items())}
    agregados = pd.DataFrame(indicadores.agregados)

    # Estructura
    estructura = {
        "filas_detalle": int(len(detalle)),
        "filas_agregadas_excluidas": {k: int(v) for k, v in agregados.nivel_agregado.value_counts().items()},
        "establecimientos_por_ano": {str(k): int(v) for k, v in detalle.groupby("ano").establecimiento_codigo.nunique().items()},
        "establecimientos_total": int(detalle.establecimiento_codigo.nunique()),
        "niveles_cuidado": int(detalle.nivel_cuidado_codigo.nunique()),
        "servicios_salud": int(detalle.servicio_salud_codigo.nunique()),
        "establecimientos_en_mas_de_un_servicio": int(
            (detalle.groupby(["ano", "establecimiento_codigo"]).servicio_salud_codigo.nunique() > 1).sum()),
        "glosas_por_nivel_codigo_max": int(detalle.groupby("nivel_cuidado_codigo").nivel_cuidado.nunique().max()),
        "nulos_por_columna": {c: int(detalle[c].isna().sum()) for c in ["acumulado", *MESES]},
        "valores_negativos": int((detalle[["acumulado", *MESES]] < 0).sum().sum()),
    }

    # Conciliación
    promedio = pd.DataFrame(conciliacion["promedio_acumulado_no_aditivo"])
    conciliacion_resumen = {
        "agregados_comparados": conciliacion["agregados_comparados"],
        "discrepancias": len(conciliacion["discrepancias_agregados"]),
        "acumulado_distinto_de_meses": len(conciliacion["acumulado_distinto_de_meses"]),
        "promedio_acumulado_no_aditivo": {k: int(v) for k, v in promedio.nivel_agregado.value_counts().items()}
        if not promedio.empty else {},
    }
    disp = w["Dias Cama Disponibles"]
    prom = w["Promedio Cama Disponibles"]
    dias_ano = pd.Series(w.index.get_level_values("ano"), index=w.index).map(
        lambda y: 366 if calendar.isleap(y) else 365)
    completos = w.index.get_level_values("ano").isin([int(a) for a, m in meses_por_ano.items() if m == 12])
    promedio_definicion = round(float(((disp / dias_ano - prom).abs() <= 0.006)[completos].mean()), 4)

    # Sobreocupación (mes a mes)
    largo = sobreocupacion(detalle)
    sobre = largo[largo.ocupados > largo.disponibles]
    psiq_idx = largo.index.get_level_values("nivel_cuidado_codigo").isin(
        [c for c in PSIQUIATRIA if c != SOCIOSANITARIO])
    sobre_psiq = sobre[sobre.index.get_level_values("nivel_cuidado_codigo").isin(
        [c for c in PSIQUIATRIA if c != SOCIOSANITARIO])]
    sobreocupacion_resumen = {
        "area_meses": int(len(largo)),
        "area_meses_ocupados_mayor_disponibles": int(len(sobre)),
        "area_meses_ocupados_con_disponibles_cero": int(((largo.ocupados > 0) & (largo.disponibles == 0)).sum()),
        "psiquiatria_area_meses": int(psiq_idx.sum()),
        "psiquiatria_ocupados_mayor_disponibles": int(len(sobre_psiq)),
        "indice_mensual_maximo": round(float((sobre.ocupados / sobre.disponibles.replace(0, np.nan)).max() * 100), 2)
        if len(sobre) else None,
    }

    # Psiquiatría RM
    nombres = detalle.drop_duplicates(LLAVE).set_index(LLAVE)[["servicio_salud", "establecimiento_nombre",
                                                              "nivel_cuidado"]]
    w_rm = w.join(nombres)
    rm = w_rm[es_rm(w_rm.servicio_salud)
              & w_rm.index.get_level_values("nivel_cuidado_codigo").isin(
                  [c for c in PSIQUIATRIA if c != SOCIOSANITARIO])]
    por_ano = rm.groupby(level="ano")[["Dias Cama Ocupados", "Dias Cama Disponibles", "Numero de Egresos",
                                         "Traslados", "Dias de Estada"]].sum()
    por_ano["indice_ocupacional"] = 100 * por_ano["Dias Cama Ocupados"] / por_ano["Dias Cama Disponibles"]
    ultimo = max(anos)
    ultimo_completo = max(int(a) for a, m in meses_por_ano.items() if m == 12)
    hospital = rm[rm.index.get_level_values("ano") == ultimo_completo].reset_index()
    hospital = hospital.groupby(["establecimiento_codigo", "establecimiento_nombre"])[
        ["Dias Cama Ocupados", "Dias Cama Disponibles"]].sum()
    hospital["indice_ocupacional"] = 100 * hospital["Dias Cama Ocupados"] / hospital["Dias Cama Disponibles"]
    largo_rm = largo.join(nombres)
    largo_rm = largo_rm[es_rm(largo_rm.servicio_salud) & largo_rm.index.get_level_values(
        "nivel_cuidado_codigo").isin([c for c in PSIQUIATRIA if c != SOCIOSANITARIO])]
    rm_sobre = largo_rm[largo_rm.ocupados > largo_rm.disponibles]
    psiquiatria_rm = {
        "ano_ultimo_completo": ultimo_completo,
        "por_ano": {str(int(a)): {"dias_cama_ocupados": int(r["Dias Cama Ocupados"]),
                                  "dias_cama_disponibles": int(r["Dias Cama Disponibles"]),
                                  "indice_ocupacional": round(float(r["indice_ocupacional"]), 2),
                                  "egresos_mas_traslados": int(r["Numero de Egresos"] + r["Traslados"])}
                    for a, r in por_ano.iterrows()},
        "hospitales_ultimo_completo": [
            {"establecimiento_codigo": int(c), "establecimiento_nombre": n,
             "dias_cama_ocupados": int(r["Dias Cama Ocupados"]), "dias_cama_disponibles": int(r["Dias Cama Disponibles"]),
             "indice_ocupacional": round(float(r["indice_ocupacional"]), 2)}
            for (c, n), r in hospital.sort_values("indice_ocupacional", ascending=False).iterrows()],
        "area_meses": int(len(largo_rm)),
        "area_meses_ocupados_mayor_disponibles": int(len(rm_sobre)),
        "establecimientos_con_ocupados_mayor_disponibles": sorted(
            {str(n) for n in rm_sobre.establecimiento_nombre}),
    }

    # Categorización
    cat = categorizacion.copy()
    cat["criticos"] = cat[list(CRITICOS)].sum(axis=1)
    cat["medios"] = cat[list(MEDIOS)].sum(axis=1)
    cat["basicos"] = cat[list(BASICOS)].sum(axis=1)
    cat["psiquiatria"] = cat.nivel_cuidado_codigo.isin([c for c in PSIQUIATRIA if c != SOCIOSANITARIO])
    cat["rm"] = cat.region == "Metropolitana de Santiago"
    trimestres = cat.groupby(["ano", "trimestre"]).agg(filas=("total", "size"),
                                                       establecimientos=("establecimiento_nombre", "nunique"),
                                                       total=("total", "sum"))
    def distribucion(df: pd.DataFrame) -> dict[str, float]:
        total = df.total.sum()
        return {k: round(float(df[k].sum() / total), 4) if total else None for k in ("criticos", "medios", "basicos")}
    nombres_ind = detalle[["ano", "servicio_salud", "establecimiento_nombre", "establecimiento_codigo"]].drop_duplicates()
    nombres_ind["servicio_salud"] = "SS " + nombres_ind.servicio_salud
    pares = cat[["ano", "servicio_salud", "establecimiento_nombre"]].drop_duplicates()
    cruce = pares.merge(nombres_ind, on=["ano", "servicio_salud", "establecimiento_nombre"], how="left")
    sin_cruce = cruce[cruce.establecimiento_codigo.isna()]
    ambiguo = int(cruce.groupby(["ano", "servicio_salud", "establecimiento_nombre"]).establecimiento_codigo.nunique().gt(1).sum())

    ocupados = detalle[detalle.indicador == "Dias Cama Ocupados"].copy()
    for numero, meses in enumerate((MESES[0:3], MESES[3:6], MESES[6:9], MESES[9:12]), start=1):
        ocupados[f"t{numero}"] = ocupados[meses].sum(axis=1, min_count=len(meses))
    ocup_trim = ocupados.melt(id_vars=["ano", "nivel_cuidado_codigo"], value_vars=["t1", "t2", "t3", "t4"],
                              var_name="t", value_name="ocupados").dropna()
    ocup_trim["trimestre"] = ocup_trim.t.str[1].astype(int)
    ocup_trim = ocup_trim.groupby(["ano", "trimestre", "nivel_cuidado_codigo"]).ocupados.sum()
    cat_trim = cat.groupby(["ano", "trimestre", "nivel_cuidado_codigo"]).total.sum()
    razon = pd.concat([cat_trim, ocup_trim], axis=1, join="inner")
    razon = (razon.total / razon.ocupados).replace([np.inf], np.nan).dropna()
    psiq_niv = razon.index.get_level_values("nivel_cuidado_codigo").isin([c for c in PSIQUIATRIA if c != SOCIOSANITARIO])
    categorizacion_resumen = {
        "trimestres": {f"{a}-T{t}": {k: int(v) for k, v in r.items()} for (a, t), r in trimestres.iterrows()},
        "total_igual_suma_categorias": bool(clean.reconcile_categorizacion(categorizacion.to_dict("records")) == []),
        "distribucion_nacional": distribucion(cat),
        "distribucion_psiquiatria_nacional": distribucion(cat[cat.psiquiatria]),
        "distribucion_psiquiatria_rm": distribucion(cat[cat.psiquiatria & cat.rm]),
        "establecimientos_trimestre": int(len(pares)),
        "establecimientos_sin_codigo_por_nombre": int(len(sin_cruce)),
        "establecimientos_ambiguos_por_nombre": ambiguo,
        "razon_categorizados_sobre_dias_ocupados_mediana": round(float(razon[~psiq_niv].median()), 3),
        "razon_categorizados_sobre_dias_ocupados_mediana_psiquiatria": round(float(razon[psiq_niv].median()), 3)
        if psiq_niv.any() else None,
        "hashes_trimestres_distintos": len(set(hashes["categorizacion"].values())) == len(hashes["categorizacion"]),
    }

    return {
        "raw_sha256": hashes,
        "anos": anos,
        "meses_por_ano": meses_por_ano,
        "estructura": estructura,
        "conciliacion": conciliacion_resumen,
        "promedio_camas_igual_disponibles_sobre_dias_ano": promedio_definicion,
        "definicion_razones": (definiciones := definicion_razones(w)),
        "tramos_definicion_razones": cambios_de_definicion(definiciones),
        "sobreocupacion": sobreocupacion_resumen,
        "coherencia_dotacion": coherencia_dotacion(w, dotacion),
        "psiquiatria_rm": psiquiatria_rm,
        "categorizacion": categorizacion_resumen,
        "ano_en_curso": {"ano": ultimo, "meses_publicados": indicadores.meses_por_ano[ultimo]},
    }


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #

def _n(value: float | int | None, decimales: int = 0) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    texto = f"{value:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _pct(value: float | None) -> str:
    return "—" if value is None or (isinstance(value, float) and np.isnan(value)) else f"{_n(100 * value, 1)} %"


def _seccion_diccionario(r: dict[str, Any]) -> list[str]:
    """Definiciones oficiales del diccionario REM-20 junto a la fórmula observada."""
    d = r.get("diccionario")
    if not d:
        return []
    tramos = r["tramos_definicion_razones"]
    def observada(indicador: str | None) -> str:
        if indicador not in tramos:
            return "—"
        return "; ".join(f"{t['desde']}–{t['hasta']}: `{t['formula']}`" if t["formula"]
                         else f"{t['desde']}–{t['hasta']}: sin fórmula exacta" for t in tramos[indicador])
    filas = [c for c in d["campos"] if c["indicador"]]
    return [
        "### Definiciones del diccionario oficial REM-20", "",
        f"`{d['ruta']}` (SHA256 `{d['sha256'][:12]}`), publicado en datos.gob.cl. Describe el conjunto en formato "
        "largo de ese portal (con `PERIODO` y `MES`), no los libros anchos que usa el pipeline: la correspondencia "
        "de cada campo con la glosa del libro es por nombre (inferencia). No cubre la categorización.", "",
        "| Campo | Glosa del libro | Definición oficial | Fórmula observada |", "|---|---|---|---|",
        *[f"| `{c['campo']}` | {c['indicador']} | {clean._text(c['detalle'])} | {observada(c['indicador'])} |"
          for c in filas],
        "",
        "Lectura: el diccionario define la letalidad sobre el **total de egresos**, lo que coincide con lo publicado "
        "desde que cambia la fórmula, no con los años anteriores, que suman traslados al denominador. Define los "
        "traslados como movimientos a otra área del mismo establecimiento que **no constituyen egreso**. Sobre los "
        "días cama ocupados por sobre los disponibles (sección 5) el diccionario no dice nada.", "",
    ]


def informe(r: dict[str, Any]) -> str:
    e, c, s, p, k = r["estructura"], r["conciliacion"], r["sobreocupacion"], r["psiquiatria_rm"], r["categorizacion"]
    anos = r["anos"]
    curso = r["ano_en_curso"]
    lineas = [
        TITULO, "",
        "Generado por `scripts/eda_estadisticas_hospitalarias.py` (stage `eda_estadisticas_hospitalarias`). "
        "No editar a mano. Diccionario: `reports/dictionary/diccionario_estadisticas_hospitalarias.md`.", "",
        "Fuente: DEIS, repositorio REM-20, «Indicadores Hospitalarios según Servicio de Salud» (SNSS) y "
        "«Categorización de Pacientes Hospitalizados Según Riesgo Dependencia». Son estadísticas mensuales "
        "y trimestrales consolidadas por establecimiento, no gestión de camas en tiempo real.", "",
        "## 1. Archivos y período", "",
        "| RAW | SHA256 (12) |", "|---|---|",
        *[f"| `{ruta}` | `{sha[:12]}` |" for familia in r["raw_sha256"].values() for ruta, sha in familia.items()],
        "",
        f"Indicadores {anos[0]}–{anos[-1]}. Meses publicados por año: "
        + ", ".join(f"{a}: {m}" for a, m in r["meses_por_ano"].items()) + ". "
        f"El año en curso ({curso['ano']}) trae **{curso['meses_publicados']} meses**: los siguientes quedan nulos "
        "en el Parquet, no en cero. La categorización cubre "
        + ", ".join(k["trimestres"]) + " (el trimestre viene del nombre de la publicación; el libro solo declara el año).",
        "",
        "## 2. Estructura y filas agregadas del origen", "",
        "Cada libro de indicadores intercala, en las mismas columnas, filas de **detalle** (un nivel de cuidado "
        "de un establecimiento) y filas **agregadas** que el origen rotula `Datos País`, `Datos Servicio Salud` y "
        "`Datos Establecimiento`. Sumar todas las filas cuenta el mismo dato dos o tres veces. El Parquet "
        "conserva solo el detalle; las agregadas se usan para conciliar (sección 3).", "",
        "| Filas | Cantidad |", "|---|---:|",
        f"| Detalle (Parquet) | {_n(e['filas_detalle'])} |",
        *[f"| Agregadas `{nivel}` (excluidas) | {_n(v)} |" for nivel, v in sorted(e["filas_agregadas_excluidas"].items())],
        "",
        f"- {_n(e['establecimientos_total'])} establecimientos en el período "
        f"({min(e['establecimientos_por_ano'].values())}–{max(e['establecimientos_por_ano'].values())} por año), "
        f"{e['servicios_salud']} Servicios de Salud y {e['niveles_cuidado']} niveles de cuidado.",
        f"- {e['establecimientos_en_mas_de_un_servicio']} combinaciones año-establecimiento figuran bajo más de un "
        "Servicio de Salud; la llave del Parquet incluye el Servicio.",
        f"- Un mismo código de nivel tiene hasta {e['glosas_por_nivel_codigo_max']} glosas distintas entre años "
        "(por ejemplo, en 2014 sin el prefijo `NNN - `): agrupar por `nivel_cuidado_codigo`.",
        f"- Valores nulos en el detalle: acumulado {_n(e['nulos_por_columna']['acumulado'])}; meses del año en curso aún no "
        f"publicados incluidos ({_n(sum(e['nulos_por_columna'][m] for m in MESES))} celdas mensuales nulas en total). "
        f"Valores negativos: {e['valores_negativos']}.",
        "",
        "## 3. Conciliación del detalle con los agregados publicados", "",
        "Se reconstruye cada fila agregada sumando el detalle, para los conteos (días cama disponibles y ocupados, "
        "días de estada, egresos, fallecidos, traslados) y el promedio de camas disponibles, mes a mes y en el "
        "acumulado.", "",
        f"- Agregados comparados: " + ", ".join(f"{k} {_n(v)}" for k, v in sorted(c["agregados_comparados"].items())) + ".",
        f"- **Discrepancias: {c['discrepancias']}.** El detalle reconstruye exactamente todos los agregados en "
        "conteos y en cada mes." if c["discrepancias"] == 0 else
        f"- **Discrepancias: {c['discrepancias']}** (ver el log de `clean_estadisticas_hospitalarias`).",
        f"- Acumulado distinto de la suma de sus meses (conteos): {c['acumulado_distinto_de_meses']}.",
        f"- El **acumulado anual del promedio de camas disponibles no es aditivo entre áreas** "
        f"({sum(c['promedio_acumulado_no_aditivo'].values())} agregados no coinciden con la suma de sus áreas: "
        + ", ".join(f"{k} {v}" for k, v in sorted(c["promedio_acumulado_no_aditivo"].items())) + "). "
        f"En años completos, el {_pct(r['promedio_camas_igual_disponibles_sobre_dias_ano'])} de las áreas cumple "
        "`promedio = días cama disponibles del año / días del año`; en el resto la fuente divide por los días de "
        "los meses en que el área funcionó. Para camas promedio de un período, recalcular desde los días cama "
        "disponibles.",
        "",
        "## 4. Definición observada de las razones publicadas", "",
        "Porcentaje de áreas-año cuya razón publicada coincide (±0,005) con cada fórmula, calculada desde los "
        "conteos de la misma fila:", "",
    ]
    for razon, por_ano in r["definicion_razones"].items():
        formulas = [f for f in next(iter(por_ano.values())) if f != "areas_comparables" and "±" not in f]
        lineas += [f"**{razon}**", "", "| Año | " + " | ".join(f"`{f}`" for f in formulas) + " |",
                   "|---|" + "---:|" * len(formulas)]
        lineas += [f"| {a} | " + " | ".join(_pct(v[f]) for f in formulas) + " |" for a, v in por_ano.items()]
        lineas.append("")
    def _tramos(razon: str) -> str:
        partes = []
        for t in r["tramos_definicion_razones"][razon]:
            anos_t = str(t["desde"]) if t["desde"] == t["hasta"] else f"{t['desde']}–{t['hasta']}"
            partes.append(f"{anos_t}: `{t['formula']}`" if t["formula"] else f"{anos_t}: ninguna fórmula explica ≥99 %")
        return "; ".join(partes)
    rotacion = r["definicion_razones"]["Indice de Rotación"]
    sin_acumulado = [str(a) for a, v in rotacion.items() if v["areas_comparables"] == 0]
    amplia = [v.get(f"(egresos + traslados) / promedio camas (±{TOLERANCIA_AMPLIA})") for v in rotacion.values()
              if v["areas_comparables"]]
    lineas += [
        "Tramos en que una fórmula explica al menos el 99 % de las áreas:", "",
        *[f"- **{razon}**: {_tramos(razon)}." for razon in r["tramos_definicion_razones"]],
        "",
        "Lectura: cuando una razón cambia de fórmula entre tramos, **su serie publicada no es comparable entre "
        "años**; para series largas hay que recalcularla desde los conteos con una definición fija. En el índice de "
        f"rotación ninguna fórmula explica el 99 % con ±0,005; con ±{_n(TOLERANCIA_AMPLIA, 2)}, "
        f"`(egresos + traslados) / promedio camas` explica entre {_pct(min(amplia))} y {_pct(max(amplia))} por año. "
        "Que la diferencia restante se deba al redondeo del promedio de camas es una hipótesis no verificada."
        + (f" El acumulado de esta razón no se publica en {', '.join(sin_acumulado)} (de ahí los nulos del "
           "acumulado en la sección 2)." if sin_acumulado else ""), "",
        *_seccion_diccionario(r),
        "## 5. Días cama ocupados por sobre los disponibles", "",
        f"- Área-meses con ocupados > disponibles: {_n(s['area_meses_ocupados_mayor_disponibles'])} de "
        f"{_n(s['area_meses'])} (índice mensual máximo {_n(s['indice_mensual_maximo'], 2)} %).",
        f"- Área-meses con ocupados > 0 y disponibles = 0: {s['area_meses_ocupados_con_disponibles_cero']}.",
        f"- En psiquiatría (418–429 sin el sociosanitario 427): {_n(s['psiquiatria_ocupados_mayor_disponibles'])} de "
        f"{_n(s['psiquiatria_area_meses'])} área-meses.",
        "",
        "Hecho observado: el REM-20 registra días cama ocupados que superan los disponibles en una fracción "
        "pequeña de área-meses. **No es posible determinar con los datos disponibles** si corresponden a camas "
        "supletorias, a pacientes en camillas o sillas, a traslados internos o a errores de registro: la fuente no "
        "lo desagrega. Tampoco permite saber cuántos pacientes esperan cama en la urgencia (esa espera no es un día "
        "cama ocupado de un área de hospitalización).", "",
        f"## 6. Psiquiatría en la Región Metropolitana", "",
        "Áreas 418–426, 428 y 429 de los Servicios de Salud `Metropolitano *` (se excluye el área sociosanitaria 427). "
        "El índice anual se calcula desde los conteos sumados, no promediando índices.", "",
        "| Año | Días cama ocupados | Días cama disponibles | Índice ocupacional | Egresos + traslados |",
        "|---|---:|---:|---:|---:|",
        *[f"| {a}{' (parcial)' if a == str(curso['ano']) and curso['meses_publicados'] < 12 else ''} | "
          f"{_n(v['dias_cama_ocupados'])} | {_n(v['dias_cama_disponibles'])} | {_n(v['indice_ocupacional'], 1)} % | "
          f"{_n(v['egresos_mas_traslados'])} |" for a, v in p["por_ano"].items()],
        "",
        f"Por establecimiento, {p['ano_ultimo_completo']} (último año completo):", "",
        "| Establecimiento | Código | Índice ocupacional | Días ocupados / disponibles |", "|---|---:|---:|---:|",
        *[f"| {h['establecimiento_nombre']} | {h['establecimiento_codigo']} | {_n(h['indice_ocupacional'], 1)} % | "
          f"{_n(h['dias_cama_ocupados'])} / {_n(h['dias_cama_disponibles'])} |" for h in p["hospitales_ultimo_completo"]],
        "",
        f"Área-meses de psiquiatría RM con ocupados > disponibles: {p['area_meses_ocupados_mayor_disponibles']} de "
        f"{_n(p['area_meses'])}"
        + (f" ({', '.join(p['establecimientos_con_ocupados_mayor_disponibles'])})." if
           p["establecimientos_con_ocupados_mayor_disponibles"] else "."),
        "",
        "## 7. Coherencia con la dotación de camas", "",
    ]
    d = r["coherencia_dotacion"]
    if d["disponible"]:
        lineas += [
            "Mismo `establecimiento_codigo` y mismo código de área funcional que `dotacion_camas_snss` (stage "
            "`clean_dotacion_camas`). Se compara el promedio anual de camas disponibles del REM-20 con la dotación "
            "declarada ese año:", "",
            f"- Áreas-año comparadas: {_n(d['areas_ano_comparadas'])}; a 1 cama o menos: {_pct(d['a_1_cama_o_menos'])}; "
            f"promedio disponible más de 10 % bajo la dotación: {_pct(d['promedio_bajo_dotacion_en_mas_de_10pct'])}.",
            f"- Psiquiatría: {_n(d['psiquiatria_areas_ano'])} áreas-año, a 1 cama o menos: "
            f"{_pct(d['psiquiatria_a_1_cama_o_menos'])}.",
            "",
            "Lectura: la dotación es un stock declarado; las camas disponibles del REM-20 descuentan las que no "
            "estuvieron habilitadas en el período. Son magnitudes distintas aunque cercanas.", "",
        ]
    else:
        lineas += ["`data/processed/camas/dotacion_camas_snss.parquet` no está disponible: sección omitida.", ""]
    lineas += [
        "## 8. Categorización según riesgo-dependencia (CUDYR)", "",
        "El instrumento CUDYR clasifica a cada paciente hospitalizado por **riesgo** (A máximo, B alto, C mediano, "
        "D bajo) y **dependencia** (1 total, 2 parcial, 3 autosuficiencia parcial); se aplica a quienes ocupan una "
        "cama más de 8 horas. Siguiendo la agrupación de González et al. (2024), se lee como pacientes **críticos** "
        "A1, A2, A3, B1 y B2; de **cuidados medios** B3, C1 y C2; y de **cuidados básicos** C3, D1, D2 y D3. Fuente "
        f"de la definición: {CITA_CUDYR}.", "",
        "| Trimestre | Filas | Establecimientos | Categorizaciones |", "|---|---:|---:|---:|",
        *[f"| {t} | {_n(v['filas'])} | {_n(v['establecimientos'])} | {_n(v['total'])} |"
          for t, v in k["trimestres"].items()],
        "",
        f"- Total igual a la suma de las 12 categorías en todas las filas: {'sí' if k['total_igual_suma_categorias'] else 'no'}. "
        f"Libros trimestrales con contenido distinto entre sí (SHA256): {'sí' if k['hashes_trimestres_distintos'] else 'no'}.",
        f"- Distribución nacional: críticos {_pct(k['distribucion_nacional']['criticos'])}, medios "
        f"{_pct(k['distribucion_nacional']['medios'])}, básicos {_pct(k['distribucion_nacional']['basicos'])}. "
        f"Psiquiatría nacional: {_pct(k['distribucion_psiquiatria_nacional']['criticos'])} / "
        f"{_pct(k['distribucion_psiquiatria_nacional']['medios'])} / {_pct(k['distribucion_psiquiatria_nacional']['basicos'])}; "
        f"psiquiatría RM: {_pct(k['distribucion_psiquiatria_rm']['criticos'])} / "
        f"{_pct(k['distribucion_psiquiatria_rm']['medios'])} / {_pct(k['distribucion_psiquiatria_rm']['basicos'])}.",
        f"- El libro **no trae código de establecimiento**, solo nombres. Cruzando por año, Servicio de Salud y nombre "
        f"exacto con los indicadores: {k['establecimientos_sin_codigo_por_nombre']} de {_n(k['establecimientos_trimestre'])} "
        f"pares año-establecimiento sin código y {k['establecimientos_ambiguos_por_nombre']} ambiguos.",
        f"- Categorizaciones del trimestre / días cama ocupados del mismo trimestre y nivel (mediana nacional): "
        f"{_n(k['razon_categorizados_sobre_dias_ocupados_mediana'], 2)} en áreas no psiquiátricas y "
        f"{_n(k['razon_categorizados_sobre_dias_ocupados_mediana_psiquiatria'], 2)} en psiquiatría.",
        "",
        "Inferencia (no declarada por la fuente): la cercanía de esa razón a 1 en las áreas generales es coherente "
        "con que cada categorización corresponda a un paciente-día categorizado, no a un paciente distinto; en "
        "psiquiatría la cobertura es menor. El libro no lo define: no es posible determinarlo con los datos "
        "disponibles.", "",
        "## 9. Advertencias para el cálculo de utilización", "",
        "- Usar solo el detalle (Parquet). Las filas agregadas del origen ya están excluidas.",
        "- Sumar solo conteos. Recalcular índices desde los conteos sumados; no promediar ni sumar razones, ni "
        "usar el acumulado del promedio de camas entre áreas.",
        "- El promedio de estada y la letalidad publicados cambian de definición entre años (sección 4).",
        f"- {curso['ano']} es parcial ({curso['meses_publicados']} meses) y el DEIS reemplaza el corte cada mes.",
        "- Los días cama ocupados miden camas de áreas de hospitalización. No miden pacientes en espera en la "
        "urgencia ni hospitalizaciones en camillas fuera de esas áreas, salvo lo que el registro incluya sin "
        "distinguirlo (sección 5).",
        "- Urgencias y estos indicadores comparten `establecimiento_codigo`, pero el ID42 cuenta indicaciones de "
        "hospitalización en la urgencia de origen, no ingresos al área de ese hospital: la relación es ecológica.",
        "",
    ]
    return "\n".join(lineas)


# --------------------------------------------------------------------------- #
# Publicación
# --------------------------------------------------------------------------- #

def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, prefix=f".{path.name}.",
                                     suffix=".tmp", encoding="utf-8", newline="\n") as temp:
        temp.write(text)
        temporary = Path(temp.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parquet_hashes(path: Path) -> dict[str, str]:
    return json.loads(pq.read_schema(path).metadata[clean.RAW_HASHES_METADATA_KEY])


def run(output_report: Path = OUTPUT_REPORT, output_summary: Path = OUTPUT_SUMMARY,
        processed_dir: Path = clean.OUTPUT_DIR, dotacion_path: Path = DOTACION_PATH) -> dict[str, Any]:
    indicadores, categorizacion, hashes = clean.read_inputs()
    paths = {"indicadores": processed_dir / clean.INDICADORES_FILENAME,
             "categorizacion": processed_dir / clean.CATEGORIZACION_FILENAME}
    for familia, path in paths.items():
        if _parquet_hashes(path) != hashes[familia]:
            raise ValueError(f"{path.as_posix()} no corresponde a los RAW vigentes: ejecute "
                             "`clean_estadisticas_hospitalarias`.")
    detalle = pq.read_table(paths["indicadores"]).to_pandas()
    cat = pq.read_table(paths["categorizacion"]).to_pandas()
    if len(detalle) != len(indicadores.detalle) or len(cat) != len(categorizacion):
        raise ValueError("Los Parquet no tienen las mismas filas que la lectura de los RAW.")
    dotacion = (pq.read_table(dotacion_path, columns=None).to_pandas() if dotacion_path.is_file() else None)
    resultado = calcular(indicadores, clean.reconcile_indicadores(indicadores), detalle, cat, hashes, dotacion)
    config = download.load_config()
    ruta_diccionario = Path(config["raw_dir"]) / config["diccionario"]["archivo"]
    resultado["diccionario"] = {
        "ruta": ruta_diccionario.as_posix(), "sha256": clean.file_sha256(ruta_diccionario),
        "campos": [c | {"indicador": CAMPO_A_INDICADOR.get(c["campo"])}
                   for c in download.read_diccionario(ruta_diccionario)],
    }
    _write_atomic(output_summary, json.dumps(resultado, ensure_ascii=False, indent=2, default=float) + "\n")
    _write_atomic(output_report, informe(resultado))
    return resultado


def validate_outputs(report: Path = OUTPUT_REPORT, summary: Path = OUTPUT_SUMMARY,
                     processed_dir: Path = clean.OUTPUT_DIR) -> None:
    """Contrato de SKIP: título del informe y hashes del resumen iguales a los Parquet vigentes."""
    if not report.read_text(encoding="utf-8").startswith(TITULO):
        raise ValueError(f"{report.name}: título inesperado.")
    resumen = json.loads(summary.read_text(encoding="utf-8"))
    for familia, nombre in (("indicadores", clean.INDICADORES_FILENAME),
                            ("categorizacion", clean.CATEGORIZACION_FILENAME)):
        if resumen.get("raw_sha256", {}).get(familia) != _parquet_hashes(processed_dir / nombre):
            raise ValueError(f"{summary.name}: no corresponde al Parquet vigente {nombre}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args(argv)
    run()
    print(f"Generado: {OUTPUT_REPORT.as_posix()} y {OUTPUT_SUMMARY.as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
