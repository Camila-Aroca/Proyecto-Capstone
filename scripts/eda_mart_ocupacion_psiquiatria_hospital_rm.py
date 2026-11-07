"""EDA reproducible de `mart_ocupacion_psiquiatria_hospital_rm`.

Cobertura por área y hospital, verificación de la identidad que sustenta el
cálculo (promedio publicado de camas disponibles = días disponibles / días del mes,
área por área), saturación por área en los últimos 12 meses publicados (meses sin
holgura y sobre la capacidad), ocupación del último mes por hospital, coherencia con
la dotación declarada (`dim_camas_psiquiatria_hospital_rm`) y con los hospitales del
pronóstico de hospitalizaciones. Reporta valores observados antes que su lectura.

Escribe `reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm.md` y su resumen
`reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm_resumen.json`.
Uso (vía pipeline): `python scripts/run_pipeline.py --stage eda_mart_ocupacion_psiquiatria_hospital_rm`
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import re
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.data import build_mart_ocupacion_psiquiatria_hospital_rm as mart_mod  # noqa: E402
from src.data.raw_provenance import file_sha256  # noqa: E402

OUTPUT_REPORT: Final[Path] = Path("reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm_resumen.json")
TITULO: Final[str] = "# EDA: `mart_ocupacion_psiquiatria_hospital_rm`"
CAMAS_PATH: Final[Path] = Path("data/processed/camas/dim_camas_psiquiatria_hospital_rm.parquet")
DOTACION_PATH: Final[Path] = Path("data/processed/camas/dotacion_camas_snss.parquet")
NIVELES_TEXTO: Final[dict[str, str]] = {
    "holgura": "Holgura", "presion": "Presión", "saturacion": "Saturación", "sobre_capacidad": "Sobre la capacidad",
}
PRONOSTICO_PATH: Final[Path] = Path("data/processed/modeling/pronostico_establecimientos_sm.parquet")


def _n(value: float | None, decimales: int = 0) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def huecos(meses: pd.DataFrame) -> int:
    """Meses sin fila entre el primero y el último de un hospital."""
    indice = meses["ano"] * 12 + meses["mes"]
    return int(indice.max() - indice.min() + 1 - indice.nunique())


VENTANA_MESES: Final[int] = 12


def saturacion_por_area(mart: pd.DataFrame, meses: int = VENTANA_MESES) -> pd.DataFrame:
    """Por área, en los últimos `meses` publicados: meses sin holgura y sobre la capacidad."""
    indice = mart["ano"] * 12 + mart["mes"]
    return mart_mod.resumen_areas(mart[indice > indice.max() - meses])


def backtest_dotacion(indicadores: pd.DataFrame, dotacion: pd.DataFrame) -> dict[str, Any]:
    """¿Las camas disponibles del REM-20 reproducen la dotación declarada del mismo año?

    Para cada área-año con ambas cifras (dotación > 0) se estima la dotación con el
    promedio mensual de camas disponibles (días disponibles / días del mes), resumido
    por la mediana o el máximo del año y redondeado a entero. Se informa la tasa de
    acierto exacto, a ±1 cama y el error absoluto medio, en todas las áreas y en las de
    psiquiatría. Sustenta si una dotación faltante puede estimarse con este dato.
    """
    import calendar
    import numpy as np
    meses = list(mart_mod.rem20.MESES_COLUMNAS)
    disponibles = indicadores[indicadores.indicador == mart_mod.DISPONIBLES]
    disponibles = disponibles.assign(**{m: pd.to_numeric(disponibles[m]) for m in meses})
    disp = disponibles.groupby(["ano", "establecimiento_codigo", "nivel_cuidado_codigo"])[meses].sum(min_count=1)
    dias = np.array([[calendar.monthrange(int(a), i + 1)[1] for i in range(12)]
                     for a in disp.index.get_level_values("ano")])
    promedio = pd.DataFrame(disp.to_numpy(dtype=float, na_value=np.nan) / dias, index=disp.index, columns=meses)
    anos = [c for c in dotacion.columns if c.startswith("camas_")]
    largo = dotacion[dotacion.area_funcional_codigo != 100].melt(
        id_vars=["establecimiento_codigo", "area_funcional_codigo", "area_funcional"], value_vars=anos,
        var_name="ano", value_name="dotacion").dropna()
    largo["ano"] = largo["ano"].str.removeprefix("camas_").astype(int)
    psiq = set(largo.loc[largo.area_funcional.str.contains(mart_mod.AREA_PSIQUIATRIA, case=False), "area_funcional_codigo"])
    real = largo.groupby(["ano", "establecimiento_codigo", "area_funcional_codigo"])["dotacion"].sum()
    real.index = real.index.set_names(["ano", "establecimiento_codigo", "nivel_cuidado_codigo"])
    salida: dict[str, Any] = {}
    for nombre, estimado in (("mediana", promedio.median(axis=1)), ("maximo", promedio.max(axis=1))):
        unido = pd.concat([estimado.rename("estimado"), real], axis=1, join="inner").dropna()
        unido = unido[unido["dotacion"] > 0]
        error = unido["estimado"].round() - unido["dotacion"]
        es_psiq = unido.index.get_level_values("nivel_cuidado_codigo").isin(psiq)
        salida[nombre] = {
            alcance: {"areas_ano": int(mask.sum()), "exacto": round(float((error[mask] == 0).mean()), 3),
                      "a_1_cama": round(float((error[mask].abs() <= 1).mean()), 3),
                      "error_absoluto_medio": round(float(error[mask].abs().mean()), 2)}
            for alcance, mask in (("todas", pd.Series(True, index=unido.index)), ("psiquiatría", pd.Series(es_psiq, index=unido.index)))
        }
    return salida


def sin_dotacion(mart: pd.DataFrame, dotacion: pd.DataFrame) -> list[dict[str, Any]]:
    """Áreas del mart sin dotación declarada en el último año del libro, con su causa observada."""
    from src.data.build_dim_camas_psiquiatria_hospital_rm import camas_psiquiatria_por_area, ultimo_ano_camas
    ano = ultimo_ano_camas(list(dotacion.columns))
    por_area = camas_psiquiatria_por_area(dotacion, ano).set_index(["establecimiento_codigo", "area_funcional_codigo"])
    primeras = mart.groupby(["establecimiento_codigo", "nivel_cuidado_codigo"]).agg(
        primer_ano=("ano", "min"), nivel_cuidado=("nivel_cuidado", "last"))
    salida = []
    for (codigo, area), fila in primeras.iterrows():
        declarada = por_area.loc[(codigo, area)] if (codigo, area) in por_area.index else None
        motivo = mart_mod.motivo_sin_dotacion(declarada, ano, int(fila.primer_ano))
        if motivo:
            salida.append({"establecimiento_codigo": int(codigo), "nivel_cuidado_codigo": int(area),
                           "nivel_cuidado": fila.nivel_cuidado, "primer_ano": int(fila.primer_ano), "motivo": motivo})
    return salida


def calcular(mart: pd.DataFrame, indicadores: pd.DataFrame, oferta: pd.DataFrame,
             camas: pd.DataFrame | None, hospitalizaciones: set[int] | None,
             dotacion: pd.DataFrame | None = None) -> dict[str, Any]:
    nombres = oferta.set_index("establecimiento_codigo")["establecimiento_nombre"]
    # Identidad: se recalcula desde el insumo, área por área, sin pasar por el mart.
    areas = mart_mod.areas_psiquiatria_mensual(indicadores)
    areas = areas[areas.establecimiento_codigo.isin(set(mart.establecimiento_codigo))]
    llave = ["establecimiento_codigo", "nivel_cuidado_codigo", "ano", "mes"]
    por = areas.groupby(llave).agg(publicado=(mart_mod.PROMEDIO_DISPONIBLES, "sum"),
                                   n=(mart_mod.OCUPADOS, "size"))
    unido = mart.set_index(llave).join(por)
    diferencia = (unido.camas_disponibles_promedio - unido.publicado).abs()
    ultimo_periodo = mart[["ano", "mes"]].drop_duplicates().sort_values(["ano", "mes"]).iloc[-1]
    total = mart_mod.por_hospital(mart)
    saturacion = saturacion_por_area(mart)
    hospitales = []
    for codigo, propio in total.groupby("establecimiento_codigo"):
        propio = propio.sort_values(["ano", "mes"])
        fin = propio.iloc[-1]
        dotacion_hospital = None
        if camas is not None and codigo in set(camas.establecimiento_codigo):
            valor = camas.set_index("establecimiento_codigo").loc[codigo, "camas_psiquiatria"]
            dotacion_hospital = None if pd.isna(valor) else float(valor)
        hospitales.append({
            "establecimiento_codigo": int(codigo), "establecimiento_nombre": str(nombres.get(codigo, "")),
            "desde": f"{int(propio.iloc[0].ano)}-{int(propio.iloc[0].mes):02d}",
            "hasta": f"{int(fin.ano)}-{int(fin.mes):02d}", "meses": int(len(propio)), "huecos": huecos(propio),
            "ultimo_camas_ocupadas_promedio": round(float(fin.camas_ocupadas_promedio), 1),
            "ultimo_camas_disponibles_promedio": round(float(fin.camas_disponibles_promedio), 1),
            "ultimo_indice_ocupacional": None if pd.isna(fin.indice_ocupacional)
            else round(float(fin.indice_ocupacional), 1),
            "dotacion_psiquiatria": dotacion_hospital,
            "en_pronostico_hospitalizaciones": None if hospitalizaciones is None else int(codigo) in hospitalizaciones,
        })
    rm = total.groupby("ano")[["dias_cama_ocupados", "dias_cama_disponibles"]].sum()
    rm["indice_ocupacional"] = 100 * rm.dias_cama_ocupados / rm.dias_cama_disponibles
    sobre = mart[mart.camas_libres_promedio < 0]
    con_mart = set(mart.establecimiento_codigo)
    return {
        "mart_sha256": None,
        "filas": int(len(mart)), "hospitales": int(mart.establecimiento_codigo.nunique()),
        "areas": int(mart[["establecimiento_codigo", "nivel_cuidado_codigo"]].drop_duplicates().shape[0]),
        "periodo": {"desde": f"{int(mart.ano.min())}-{int(mart.loc[mart.ano == mart.ano.min(), 'mes'].min()):02d}",
                    "hasta": f"{int(ultimo_periodo.ano)}-{int(ultimo_periodo.mes):02d}"},
        "identidad": {"area_mes": int(len(unido)), "max_diferencia": round(float(diferencia.max()), 6),
                      "max_tolerancia": round(float((mart_mod.REDONDEO_POR_AREA * unido.n).max()), 6),
                      "fuera_de_tolerancia": int((diferencia > mart_mod.REDONDEO_POR_AREA * unido.n + 1e-9).sum())},
        "indice_rm_por_ano": {str(int(a)): round(float(v), 2) for a, v in rm.indice_ocupacional.items()},
        "area_mes_sobre_capacidad": [
            {"establecimiento_codigo": int(r.establecimiento_codigo), "nivel_cuidado_codigo": int(r.nivel_cuidado_codigo),
             "periodo": f"{int(r.ano)}-{int(r.mes):02d}", "indice_ocupacional": round(float(r.indice_ocupacional), 2)}
            for r in sobre.itertuples()],
        "hospital_mes_sobre_capacidad": int((total.camas_libres_promedio < 0).sum()),
        "colapso": {
            "umbrales_pct": {"presion": mart_mod.UMBRAL_PRESION_PCT, "saturacion": mart_mod.UMBRAL_SATURACION_PCT},
            "hospitales": [
                {"establecimiento_codigo": int(f.establecimiento_codigo),
                 "establecimiento_nombre": str(nombres.get(f.establecimiento_codigo, "")),
                 "nivel": f.nivel, "indice_ocupacional": round(float(f.indice_ocupacional), 1), "meses": int(f.meses),
                 "area_mes_sobre_capacidad": int(f.area_mes_sobre_capacidad), "desde": str(f.desde), "hasta": str(f.hasta)}
                for f in mart_mod.nivel_colapso(mart).sort_values("indice_ocupacional", ascending=False).itertuples()],
        },
        "sin_dotacion": sin_dotacion(mart, dotacion) if dotacion is not None else None,
        "backtest_dotacion": backtest_dotacion(indicadores, dotacion) if dotacion is not None else None,
        "area_mes_sin_camas": int((mart.dias_cama_disponibles == 0).sum()),
        "umbral_holgura_camas": mart_mod.UMBRAL_HOLGURA_CAMAS,
        "saturacion_ultimos_meses": {
            "meses": VENTANA_MESES,
            "areas": [{"establecimiento_codigo": int(r.establecimiento_codigo),
                       "establecimiento_nombre": str(nombres.get(r.establecimiento_codigo, "")),
                       "nivel_cuidado": r.nivel_cuidado, "meses": int(r.meses),
                       "meses_sin_holgura": int(r.meses_sin_holgura),
                       "meses_sobre_capacidad": int(r.meses_sobre_capacidad),
                       "camas_disponibles_promedio": round(float(r.camas_disponibles_promedio), 1),
                       "camas_libres_promedio": round(float(r.camas_libres_promedio), 2),
                       "indice_ocupacional": round(float(r.indice_ocupacional), 1)}
                      for r in saturacion.sort_values(["meses_sin_holgura", "indice_ocupacional"],
                                                       ascending=False).itertuples()],
        },
        "hospitales_detalle": hospitales,
        "hospitales_oferta_sin_psiquiatria_rem20": int(
            (oferta.tipo_establecimiento == mart_mod.TIPO_HOSPITAL).sum() - len(con_mart)),
        "con_ocupacion_sin_dotacion": sorted(h["establecimiento_codigo"] for h in hospitales
                                             if camas is not None and h["dotacion_psiquiatria"] is None),
        "pronostico_hospitalizaciones": None if hospitalizaciones is None else {
            "hospitales": len(hospitalizaciones), "con_ocupacion": len(hospitalizaciones & con_mart),
            "sin_ocupacion": sorted(hospitalizaciones - con_mart)},
    }


def _tabla_sobre(sobre: list[dict[str, Any]], hospitales: list[dict[str, Any]]) -> list[str]:
    """Área-mes sobre la capacidad resumidos por área (cantidad, primer y último mes, máximo)."""
    if not sobre:
        return []
    nombres = {h["establecimiento_codigo"]: h["establecimiento_nombre"] for h in hospitales}
    tabla = pd.DataFrame(sobre).groupby(["establecimiento_codigo", "nivel_cuidado_codigo"]).agg(
        meses=("periodo", "size"), primero=("periodo", "min"), ultimo=("periodo", "max"),
        maximo=("indice_ocupacional", "max")).reset_index().sort_values("meses", ascending=False)
    return [f"| {nombres.get(f.establecimiento_codigo, f.establecimiento_codigo)} | {f.nivel_cuidado_codigo} | "
            f"{f.meses} | {f.primero} | {f.ultimo} | {_n(f.maximo, 1)} % |" for f in tabla.itertuples()]


def _area_sin_prefijo(glosa: str) -> str:
    """Glosa del área sin el prefijo `NNN - ` (que el origen omite en algunos años)."""
    return re.sub(r"^\d{3}\s*-\s*", "", glosa)


def _secciones_colapso_y_dotacion(r: dict[str, Any]) -> list[str]:
    nombres = {h["establecimiento_codigo"]: h["establecimiento_nombre"] for h in r["hospitales_detalle"]}
    c = r["colapso"]
    h = c["hospitales"]
    lineas = [
        "## 6. Nivel de colapso por hospital", "",
        f"Ocupación de las camas de psiquiatría de cada hospital en la ventana común {h[0]['desde'][:7]} a "
        f"{h[0]['hasta'][:7]} (últimos 12 meses publicados), como razón de sumas sobre los área-mes con camas "
        f"habilitadas. **Holgura** < {_n(c['umbrales_pct']['presion'])} %; **presión** de "
        f"{_n(c['umbrales_pct']['presion'])} a {_n(c['umbrales_pct']['saturacion'])} %; **saturación** ≥ "
        f"{_n(c['umbrales_pct']['saturacion'])} %; **sobre la capacidad** si algún área registró más días cama ocupados "
        "que disponibles en la ventana. Umbrales de la literatura, no ajustados a estos datos: 85 % es la ocupación "
        "máxima recomendada para salas de psiquiatría (Royal College of Psychiatrists) y desde la que Bagust, Place y "
        "Posnett (BMJ 1999;319:155-8) observan riesgos discernibles; con 90 % o más de ocupación media ese estudio "
        "espera escasez regular de camas y crisis periódicas. Ese estudio simula un hospital de agudos sin pacientes "
        "psiquiátricos: es una referencia, no una calibración local.", "",
        "| Hospital | Nivel | Ocupación | Meses | Área-mes sobre la capacidad |", "|---|---|---:|---:|---:|",
        *[f"| {x['establecimiento_nombre']} | {NIVELES_TEXTO[x['nivel']]} | {_n(x['indice_ocupacional'], 1)} % | "
          f"{x['meses']} | {x['area_mes_sobre_capacidad']} |" for x in h],
        "",
        "Lectura: el nivel resume al hospital; un área puede estar saturada aunque el hospital no (sección 3).", "",
    ]
    if r.get("sin_dotacion") is not None:
        b = r["backtest_dotacion"]
        lineas += [
            "## 7. Áreas sin dotación declarada", "",
            "| Hospital | Área | En el REM-20 desde | Causa observada |", "|---|---|---:|---|",
            *[f"| {nombres.get(x['establecimiento_codigo'], x['establecimiento_codigo'])} | {x['nivel_cuidado_codigo']} · "
              f"{_area_sin_prefijo(x['nivel_cuidado'])} | {x['primer_ano']} | {x['motivo']} |" for x in r["sin_dotacion"]],
            "",
            "¿Se puede estimar la dotación faltante con las camas disponibles del REM-20? Se prueba en todas las "
            "áreas-año que tienen ambas cifras, estimando la dotación con la mediana o el máximo del promedio mensual de "
            "camas disponibles del año:", "",
            "| Estimador | Alcance | Áreas-año | Acierto exacto | A ±1 cama | Error absoluto medio |",
            "|---|---|---:|---:|---:|---:|",
            *[f"| {nombre} | {alcance} | {_n(v['areas_ano'])} | {_n(100 * v['exacto'], 1)} % | {_n(100 * v['a_1_cama'], 1)} % | "
              f"{_n(v['error_absoluto_medio'], 2)} camas |" for nombre, porr in b.items() for alcance, v in porr.items()],
            "",
            "Lectura: las camas disponibles no reproducen la dotación declarada con la precisión necesaria para "
            "publicarla como dato (en psiquiatría, una de cada tres áreas-año difiere en más de una cama). Por eso no "
            "se imputa la dotación faltante: el tablero muestra las camas disponibles del REM-20 como capacidad "
            "observada y explica la causa de la ausencia.", "",
        ]
    return lineas


def informe(r: dict[str, Any]) -> str:
    i = r["identidad"]
    p = r["pronostico_hospitalizaciones"]
    sat = r["saturacion_ultimos_meses"]
    umbral = _n(r["umbral_holgura_camas"])
    sobre = r["area_mes_sobre_capacidad"]
    lineas = [
        TITULO, "",
        "Generado por `scripts/eda_mart_ocupacion_psiquiatria_hospital_rm.py` (stage "
        "`eda_mart_ocupacion_psiquiatria_hospital_rm`). No editar a mano. Diccionario: "
        "`reports/dictionary/diccionario_mart_ocupacion_psiquiatria_hospital_rm.md`.", "",
        "## 1. Cobertura", "",
        f"{_n(r['filas'])} filas área-mes: {r['areas']} áreas de psiquiatría de {r['hospitales']} hospitales de la oferta "
        f"de urgencia RM, de {r['periodo']['desde']} a {r['periodo']['hasta']} (último mes publicado por el DEIS). "
        f"{r['hospitales_oferta_sin_psiquiatria_rem20']} hospitales de la oferta no tienen áreas de psiquiatría en el "
        "REM-20 (o no son del SNSS) y no aparecen.", "",
        "## 2. Verificación del cálculo", "",
        "`camas_ocupadas_promedio = días cama ocupados / días del mes` es exacto: los días cama del mes son la suma "
        "diaria de camas (diccionario REM-20). Como prueba de que la fuente usa esa misma definición, se recalcula "
        "`días cama disponibles / días del mes` en cada área y mes, y se compara con el «Promedio Cama Disponibles» que "
        "el DEIS publica para esa área (2 decimales):", "",
        f"- Área-mes comparados: {_n(i['area_mes'])}; diferencia máxima {_n(i['max_diferencia'], 4)} camas "
        f"(tolerancia de redondeo {_n(i['max_tolerancia'], 3)}); fuera de tolerancia: **{i['fuera_de_tolerancia']}**.",
        "- `camas_libres_promedio = (días disponibles − días ocupados) / días del mes`: misma identidad. Negativa = "
        "más días cama ocupados que disponibles registrados en el mes.",
        "", "## 3. Saturación por área", "",
        f"Últimos {sat['meses']} meses publicados. **Sin holgura**: menos de {umbral} cama libre por día en promedio del "
        "mes (umbral en camas, comparable entre áreas chicas y grandes). **Sobre la capacidad**: más días cama "
        "ocupados que disponibles. Ambos se cuentan solo en los meses **con camas disponibles**: un área con 0 días "
        "cama disponibles no estuvo habilitada, no saturada. Índice del período como razón de sumas.", "",
        "| Hospital | Área | Camas disponibles (prom.) | Camas libres (prom. diario) | Índice | Meses sin holgura | Meses sobre la capacidad |",
        "|---|---|---:|---:|---:|---:|---:|",
        *[f"| {a['establecimiento_nombre']} | {a['nivel_cuidado']} | {_n(a['camas_disponibles_promedio'], 1)} | "
          f"{_n(a['camas_libres_promedio'], 2)} | {_n(a['indice_ocupacional'], 1)} % | "
          f"{a['meses_sin_holgura']} de {a['meses']} | {a['meses_sobre_capacidad']} |" for a in sat["areas"]],
        "",
        f"Área-mes sin camas disponibles en todo el período (excluidos de la saturación): {r['area_mes_sin_camas']}.",
        "",
        "Lectura: el total de un hospital puede ocultar áreas saturadas (las camas libres de un área no sirven a "
        "pacientes de otra, por ejemplo entre forense y corta estadía). Los días cama ocupados cuentan pacientes en "
        "camas de áreas de hospitalización: quien espera en la urgencia en camilla, silla o sillón no ocupa una de "
        "esas camas y no queda registrado. Por definición del indicador, la ocupación observada es entonces un piso "
        "de la demanda de camas; la fuente no cuantifica esa espera, así que su magnitud no es determinable con "
        "estos datos.", "",
        f"En todo el período hay **{len(sobre)} área-mes sobre la capacidad**, pero solo "
        f"{r['hospital_mes_sobre_capacidad']} hospital-mes al sumar las áreas: el agregado compensa un área "
        "desbordada con camas libres de otra. Por área:", "",
        "| Hospital | Área | Meses sobre la capacidad | Primero | Último | Índice máximo |", "|---|---:|---:|---|---|---:|",
        *_tabla_sobre(sobre, r["hospitales_detalle"]),
        "", "## 4. Ocupación agregada de los hospitales del mart", "",
        "Razón de sumas (`100 · Σ ocupados / Σ disponibles`), no promedio de índices:", "",
        "| Año | Índice ocupacional |", "|---|---:|",
        *[f"| {a} | {_n(v, 1)} % |" for a, v in r["indice_rm_por_ano"].items()],
        "", "## 5. Último mes por hospital", "",
        "| Hospital | Código | Hasta | Meses (huecos) | Ocupadas / disponibles (prom. diario) | Índice | Dotación declarada | En pronóstico de hospitalizaciones |",
        "|---|---:|---|---:|---:|---:|---:|---|",
        *[f"| {h['establecimiento_nombre']} | {h['establecimiento_codigo']} | {h['hasta']} | {h['meses']} ({h['huecos']}) | "
          f"{_n(h['ultimo_camas_ocupadas_promedio'], 1)} / {_n(h['ultimo_camas_disponibles_promedio'], 1)} | "
          f"{_n(h['ultimo_indice_ocupacional'], 1)} % | {_n(h['dotacion_psiquiatria'])} | "
          f"{'—' if h['en_pronostico_hospitalizaciones'] is None else ('sí' if h['en_pronostico_hospitalizaciones'] else 'no')} |"
          for h in r["hospitales_detalle"]],
        "",
        f"- Hospitales con ocupación en el REM-20 pero **sin cifra de dotación** de psiquiatría: "
        f"{', '.join(map(str, r['con_ocupacion_sin_dotacion'])) or 'ninguno'}. Hecho observado; la causa (área "
        "habilitada después del libro de dotación, diferencia de registro u otra) no es determinable con estos datos.",
        "",
    ]
    lineas += _secciones_colapso_y_dotacion(r)
    if p:
        lineas += [
            "## 8. Relación con el pronóstico de hospitalizaciones", "",
            f"De los {p['hospitales']} hospitales con pronóstico de hospitalizaciones (ID42), {p['con_ocupacion']} tienen "
            f"ocupación de psiquiatría en este mart; sin ella: {', '.join(map(str, p['sin_ocupacion'])) or 'ninguno'} "
            "(sin áreas de psiquiatría en el REM-20).", "",
            "Lectura: son magnitudes distintas. El ID42 cuenta, por semana, hospitalizaciones indicadas en la urgencia "
            "(un flujo, registrado donde ocurrió la urgencia). Este mart cuenta, por mes, pacientes en cama de "
            "psiquiatría en promedio por día (un stock, de cualquier origen). Por eso el tablero los muestra en "
            "gráficos separados y no en un mismo eje.", "",
        ]
    lineas += [
        "## Advertencias", "",
        "- No es ocupación en tiempo real: es el último mes publicado por el DEIS.",
        "- Es un promedio mensual: un mes sin holgura puede incluir días con camas libres y días sobre la capacidad.",
        "- Disponibles (REM-20) no es dotación (libro de camas): la primera descuenta las camas no habilitadas.",
        "",
    ]
    return "\n".join(lineas)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                     encoding="utf-8", newline="\n") as temp:
        temp.write(text)
        temporary = Path(temp.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run(mart_path: Path = mart_mod.OUTPUT_PATH, report: Path = OUTPUT_REPORT,
        summary: Path = OUTPUT_SUMMARY) -> dict[str, Any]:
    mart = pq.read_table(mart_path).to_pandas()
    indicadores = pq.read_table(mart_mod.INDICADORES_PATH).to_pandas()
    oferta = pq.read_table(mart_mod.DIM_OFERTA_PATH, columns=[
        "establecimiento_codigo", "establecimiento_nombre", "tipo_establecimiento"]).to_pandas()
    camas = pq.read_table(CAMAS_PATH).to_pandas() if CAMAS_PATH.is_file() else None
    hospitalizaciones = None
    if PRONOSTICO_PATH.is_file():
        pron = pq.read_table(PRONOSTICO_PATH, columns=["objetivo", "series_id"]).to_pandas()
        hospitalizaciones = {int(s) for s in pron.loc[pron.objetivo == "hospitalizaciones_sm", "series_id"].unique()}
    dotacion = pq.read_table(DOTACION_PATH).to_pandas() if DOTACION_PATH.is_file() else None
    resultado = calcular(mart, indicadores, oferta, camas, hospitalizaciones, dotacion)
    resultado['propuestas_camas'] = auditar_propuestas(mart, dotacion)
    resultado["mart_sha256"] = file_sha256(mart_path)
    resultado['dotacion_sha256'] = file_sha256(DOTACION_PATH) if DOTACION_PATH.is_file() else None
    _write_atomic(summary, json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
    _write_atomic(report, informe(resultado) + informe_propuestas(resultado['propuestas_camas']))
    return resultado


def auditar_propuestas(mart: pd.DataFrame, dotacion: pd.DataFrame | None,
                      fecha_corte: date | None = None) -> dict[str, Any]:
    """QA del mismo cálculo servido y prueba retrospectiva anual sin ajuste al futuro.

    Cortes anuales no solapados, antes de cada enero; mide meses cuyo promedio
    no supera 85% del objetivo, no probabilidad de encontrar cama un día dado.
    """
    from src.data.build_dim_camas_psiquiatria_hospital_rm import camas_psiquiatria_por_area, ultimo_ano_camas
    corte = fecha_corte or date.today()
    declaradas = None if dotacion is None else camas_psiquiatria_por_area(
        dotacion, ultimo_ano_camas(list(dotacion.columns)))
    mapa = {} if declaradas is None else declaradas.set_index(
        ['establecimiento_codigo', 'area_funcional_codigo']).camas.to_dict()
    propuestas = []
    meses_evaluados = meses_cubiertos = cortes = 0
    for (hospital, area), serie in mart.groupby(['establecimiento_codigo', 'nivel_cuidado_codigo']):
        p = mart_mod.propuesta_camas(serie, mapa.get((hospital, area)), int(area), corte)
        p.update(establecimiento_codigo=int(hospital), nivel_cuidado_codigo=int(area))
        if p['camas_objetivo'] is not None:
            objetivo = p['camas_objetivo']
            pico = p['pico_camas_ocupadas']
            if objetivo * .85 + 1e-9 < pico or (objetivo > 0 and (objetivo - 1) * .85 >= pico):
                raise ValueError('El objetivo no es el entero mínimo que cumple 85%.')
            if p['aumento_dotacion'] is not None and p['aumento_dotacion'] > 0:
                if p['base_capacidad'] + p['aumento_dotacion'] < objetivo:
                    raise ValueError('La dotación propuesta no cubre el objetivo.')
        propuestas.append(p)
        for ano in sorted(serie.ano.unique()):
            historia = serie[serie.ano < ano]
            futuro = serie[serie.ano == ano]
            if len(futuro) != 12 or futuro.mes.nunique() != 12:
                continue
            pasado = mart_mod.propuesta_camas(historia, None, int(area), date(int(ano), 1, 1))
            if pasado['camas_objetivo'] is None or (futuro.dias_cama_disponibles <= 0).any():
                continue
            capacidad = pasado['camas_objetivo']
            cargas = futuro.dias_cama_ocupados / futuro.dias_mes
            meses_evaluados += len(futuro)
            meses_cubiertos += int((cargas <= capacidad * .85 + 1e-9).sum())
            cortes += 1
    return dict(fecha_corte=corte.isoformat(), propuestas=propuestas, cortes_retrospectivos=cortes,
                meses_evaluados=meses_evaluados, meses_bajo_objetivo=meses_cubiertos,
                proporcion_meses_bajo_objetivo=meses_cubiertos / meses_evaluados if meses_evaluados else None)


def informe_propuestas(qa: dict[str, Any]) -> str:
    lineas = ['', '## Propuesta anual de camas: escenario de continuidad', '',
              f"Corte reproducible: {qa['fecha_corte']}. Método `continuidad_pico_12m_v1`.", '',
              'Objetivo = techo(max(días cama ocupados / días del mes) / 0,85), últimos 12 meses consecutivos. '
              'Sensibilidad a 90%. Cada área de psiquiatría se calcula por separado. Fuera de corta estadía 418/421, '
              'el 85% es un supuesto explícito del escenario, no un estándar clínico específico validado. '
              'Primero evaluar habilitación de dotación existente; ampliar solo la brecha positiva respecto de la declarada. '
              'Sin cifra declarada, la base es la disponibilidad diaria calculada del último REM-20: '
              'el aumento es capacidad adicional estimada y no distingue camas nuevas de rehabilitación. '
              'Las disponibles son promedios: la habilitación calculada puede ser fraccionaria; las camas nuevas son enteras.', '',
              '| Hospital | Área | Hasta | Objetivo 85% | Objetivo 90% | Aumento capacidad | Base | Habilitar existentes (prom.) | Motivo de abstención |',
              '|---:|---:|---|---:|---:|---:|---|---:|---|']
    for p in qa['propuestas']:
        lineas.append(f"| {p['establecimiento_codigo']} | {p['nivel_cuidado_codigo']} | {p['hasta'] or '—'} | "
                      f"{_n(p['camas_objetivo'])} | {_n(p['camas_objetivo_90'])} | {_n(p['aumento_dotacion'])} | {p['fuente_base'] or '—'} | "
                      f"{_n(p['habilitar_existentes'], 2)} | {p['motivo'] or '—'} |")
    lineas += ['', f"QA: {qa['cortes_retrospectivos']} cortes anuales retrospectivos no solapados; "
               f"{qa['meses_bajo_objetivo']} de {qa['meses_evaluados']} meses siguientes con promedio ≤85% del objetivo. "
               'Diagnóstico histórico agregado, no cobertura probabilística ni validación de un pronóstico anual.', '',
               'No presupone crecimiento ni mide demanda insatisfecha o máximos diarios. No garantiza dar abasto. '
               'Presupuesto, personal, espacio y plazos no están disponibles: la factibilidad requiere validación local. '
               'No mezcla ID42 ni Egresos con la ocupación por hospital. No se compensan áreas entre sí.', '',
               'Referencia: [Royal College of Psychiatrists](https://mentalhealthwatch.rcpsych.ac.uk/indicators/bed-occupancy-across-mental-health-trust). '
               'La sensibilidad al tamaño y especialidad está documentada en '
               '[Pratt y Wood, 2021](https://pubmed.ncbi.nlm.nih.gov/34219171/).', '']
    return '\n'.join(lineas)


def validate_outputs(report: Path = OUTPUT_REPORT, summary: Path = OUTPUT_SUMMARY,
                     mart_path: Path = mart_mod.OUTPUT_PATH) -> None:
    """Contrato de SKIP: título y resumen generado desde el mart vigente."""
    if not report.read_text(encoding="utf-8").startswith(TITULO):
        raise ValueError(f"{report.name}: título inesperado.")
    if json.loads(summary.read_text(encoding="utf-8")).get("mart_sha256") != file_sha256(mart_path):
        raise ValueError(f"{summary.name}: no corresponde al mart vigente.")
    contenido = json.loads(summary.read_text(encoding='utf-8'))
    if contenido.get('propuestas_camas', {}).get('fecha_corte') != date.today().isoformat():
        raise ValueError('QA de propuestas requiere actualizar fecha de corte.')
    if DOTACION_PATH.is_file() and contenido.get('dotacion_sha256') != file_sha256(DOTACION_PATH):
        raise ValueError('QA de propuestas no corresponde a la dotación vigente.')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args(argv)
    run()
    print(f"Generado: {OUTPUT_REPORT.as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
