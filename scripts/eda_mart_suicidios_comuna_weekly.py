"""EDA reproducible de `mart_suicidios_comuna_weekly`.

Documenta, con cifras calculadas desde el mart, la fuente y Urgencias, las
decisiones que toman el mart y el modelo: definición del caso, calendario DEIS,
registro incompleto de las semanas finales, cambio de nivel 2020-2021, estacionalidad,
dispersión, ceros y heterogeneidad comunal. Primero los valores observados, después
su lectura.

Uso (vía pipeline): `python scripts/run_pipeline.py --stage eda_mart_suicidios_comuna_weekly`
"""

from __future__ import annotations

from datetime import date
import glob
import json
from pathlib import Path
import sys
from typing import Any, Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats
from statsmodels.genmod import families
from statsmodels.genmod.generalized_linear_model import GLM

from src.data import build_mart_suicidios_comuna_weekly as b
from src.data.raw_provenance import file_sha256

OUTPUT_REPORT: Final[Path] = Path("reports/eda/eda_mart_suicidios_comuna_weekly.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/eda/eda_mart_suicidios_comuna_weekly_resumen.json")
TITULO: Final[str] = "# EDA del mart semanal de suicidios por comuna de residencia (RM)"
URGENCIAS_GLOB: Final[str] = "data/processed/urgencias/urgencias_rm_*.parquet"
ANO_MODELO: Final[int] = 2022


def tabla_md(frame: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |"
             for fila in frame.itertuples(index=False, name=None)]
    return "\n".join([encabezado, separador, *filas])


def verificar_calendario() -> dict[str, int]:
    """Compara `semana_deis` con la codificación publicada en cada fecha de Urgencias."""
    fechas, discrepancias = 0, 0
    for ruta in sorted(glob.glob(URGENCIAS_GLOB)):
        u = pq.read_table(ruta, columns=["ano", "semana", "fecha"]).to_pandas().drop_duplicates()
        dias = pd.to_datetime(u["fecha"], dayfirst=True, format="mixed").dt.date
        codigos = [b.semana_deis(d) for d in dias]
        fechas += len(u)
        discrepancias += int(sum((a, s) != (int(x), int(y)) for (a, s), x, y in zip(codigos, u["ano"], u["semana"])))
    return {"fechas_verificadas": fechas, "discrepancias": discrepancias}


def completitud(mart: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Defunciones diarias (todas las causas) de cada semana frente a la mediana de las 8 previas."""
    semanal = mart[mart["semana"] != b.SEMANA_FRAGMENTO].groupby(["ano", "semana"], as_index=False).agg(
        inicio=("fecha_inicio_semana", "first"), dias=("dias_semana", "first"),
        defunciones=("defunciones_total", "sum"), suicidios=("suicidios", "sum"),
        registro_completo=("registro_completo", "first")).sort_values("inicio").reset_index(drop=True)
    por_dia = semanal["defunciones"] / semanal["dias"]
    semanal["razon_registro"] = (por_dia / por_dia.shift(1).rolling(b.SEMANAS_REFERENCIA).median()).round(3)
    interior = semanal[(semanal["ano"] >= 2021) & semanal["registro_completo"]]
    return semanal, float(interior["razon_registro"].min())


def fourier(semana: pd.Series, k: int) -> pd.DataFrame:
    angulo = 2 * np.pi * semana.to_numpy() / 52
    return pd.DataFrame({f"{f}{i}": fn(i * angulo) for i in range(1, k + 1) for f, fn in (("s", np.sin), ("c", np.cos))})


def estacionalidad(region: pd.DataFrame) -> dict[str, Any]:
    """GLM de Poisson con efecto de año, exposición en días y 0-3 armónicos (2022 al último año cerrado)."""
    y = region["y"].to_numpy(dtype=float)
    offset = np.log(region["dias"].to_numpy() / 7)
    anos = pd.get_dummies(region["ano"], prefix="a").astype(float).reset_index(drop=True)
    ajustes = {}
    for k in range(4):
        X = pd.concat([anos, fourier(region["semana"], k)], axis=1) if k else anos
        ajustes[k] = GLM(y, X, family=families.Poisson(), offset=offset).fit()
    lrt = []
    for k in (1, 2, 3):
        estadistico = 2 * (ajustes[k].llf - ajustes[k - 1].llf)
        lrt.append({"armonicos": f"{k} frente a {k - 1}", "LR": round(estadistico, 2),
                    "gl": 2, "p_valor": float(f"{stats.chi2.sf(estadistico, 2):.3g}")})
    k1 = ajustes[1]
    perfil = np.exp(fourier(pd.Series(np.arange(1, 53)), 1).to_numpy() @ k1.params[["s1", "c1"]].to_numpy())
    residuos = np.asarray(k1.resid_pearson)
    acf = {lag: round(float(np.corrcoef(residuos[:-lag], residuos[lag:])[0, 1]), 3) for lag in (1, 2, 3, 4, 8, 13, 26)}
    return {
        "lrt": lrt,
        "semana_maxima": int(np.argmax(perfil) + 1), "semana_minima": int(np.argmin(perfil) + 1),
        "razon_maximo_minimo": round(float(perfil.max() / perfil.min()), 3),
        "dispersion_pearson_k0": round(float(ajustes[0].pearson_chi2 / ajustes[0].df_resid), 3),
        "dispersion_pearson_k1": round(float(k1.pearson_chi2 / k1.df_resid), 3),
        "acf_residuos": acf, "banda_acf": round(2 / np.sqrt(len(residuos)), 3), "semanas": len(residuos),
    }


def comunas(mart: pd.DataFrame, ano_max: int) -> dict[str, Any]:
    """Escasez, ceros y heterogeneidad de las tasas comunales en la ventana del modelo."""
    v = mart[(mart["ano"] >= ANO_MODELO) & (mart["ano"] <= ano_max) & (mart["semana"] != b.SEMANA_FRAGMENTO)]
    por_comuna = v.groupby(["comuna_codigo", "comuna_glosa"]).agg(
        suicidios=("suicidios", "sum"), semanas=("semana", "size"),
        poblacion=("poblacion_anual", "mean")).reset_index()
    anos = ano_max - ANO_MODELO + 1
    por_comuna["media_semanal"] = por_comuna["suicidios"] / por_comuna["semanas"]
    por_comuna["tasa_100mil_ano"] = por_comuna["suicidios"] / por_comuna["poblacion"] * 1e5 / anos
    esperados = por_comuna["suicidios"].sum() * por_comuna["poblacion"] / por_comuna["poblacion"].sum()
    chi2 = float(((por_comuna["suicidios"] - esperados) ** 2 / esperados).sum())
    gl = len(por_comuna) - 1
    # Ceros esperados si cada comuna-semana fuera Poisson con la media de su comuna.
    medias = v["comuna_codigo"].map(por_comuna.set_index("comuna_codigo")["media_semanal"])
    ceros_obs = float((v["suicidios"] == 0).mean())
    ceros_esp = float(np.exp(-medias).mean())
    varianza = v.groupby("comuna_codigo")["suicidios"].var()
    razon_vm = (varianza / por_comuna.set_index("comuna_codigo")["media_semanal"]).median()
    orden = por_comuna.sort_values("tasa_100mil_ano")
    return {
        "chi2": round(chi2, 1), "gl": gl, "p_valor": float(f"{stats.chi2.sf(chi2, gl):.3g}"),
        "media_semanal": por_comuna["media_semanal"].describe()[["min", "25%", "50%", "75%", "max"]].round(3).to_dict(),
        "tasa_region": round(float(por_comuna["suicidios"].sum() / por_comuna["poblacion"].sum() * 1e5 / anos), 2),
        "tasa_min": round(float(orden["tasa_100mil_ano"].iloc[0]), 2), "tasa_max": round(float(orden["tasa_100mil_ano"].iloc[-1]), 2),
        "ceros_observados": round(ceros_obs, 4), "ceros_esperados_poisson": round(ceros_esp, 4),
        "razon_varianza_media_mediana": round(float(razon_vm), 3),
        "extremos": pd.concat([orden.head(5), orden.tail(5)])[
            ["comuna_glosa", "suicidios", "media_semanal", "tasa_100mil_ano"]].round(3),
    }


def build_report() -> tuple[str, dict[str, Any]]:
    mart = pq.read_table(b.OUTPUT_PATH).to_pandas()
    fuente = b.load_defunciones_rm()
    fuente = fuente[fuente["fecha_defuncion"].notna()]
    publicado = fuente[fuente["fecha_defuncion"] <= max(mart["fecha_fin_semana"])]
    suic = publicado[b.es_suicidio(publicado)]
    categorias = suic["codigo_categoria_diag2"].value_counts()
    ano_max = int(mart.loc[pd.to_datetime(mart["fecha_fin_semana"]).dt.strftime("%m-%d") == "12-31", "ano"].max())

    anual = mart.groupby("ano").agg(suicidios=("suicidios", "sum"), defunciones=("defunciones_total", "sum")).reset_index()
    dias_ano = mart.drop_duplicates(["ano", "semana"]).groupby("ano")["dias_semana"].sum()
    poblacion = mart.drop_duplicates(["comuna_codigo", "ano"]).groupby("ano")["poblacion_anual"].sum()
    anual["dias"] = anual["ano"].map(dias_ano)
    anual["por_dia"] = (anual["suicidios"] / anual["dias"]).round(3)
    anual["tasa_100mil_ano"] = (anual["suicidios"] / anual["ano"].map(poblacion) * 1e5 * 365.25 / anual["dias"]).round(2)
    anual["pct_de_defunciones"] = (anual["suicidios"] / anual["defunciones"] * 100).round(2)

    a = int(anual.loc[anual["ano"] <= 2021, "suicidios"].sum()); da = int(anual.loc[anual["ano"] <= 2021, "dias"].sum())
    ventana = anual[(anual["ano"] >= ANO_MODELO) & (anual["ano"] <= ano_max)]
    bb, db = int(ventana["suicidios"].sum()), int(ventana["dias"].sum())
    prueba = stats.binomtest(a, a + bb, da / (da + db))
    esperado = ventana["suicidios"].sum() * ventana["dias"] / ventana["dias"].sum()
    chi_anos = float(((ventana["suicidios"] - esperado) ** 2 / esperado).sum())

    cal = verificar_calendario()
    semanal, minimo_interior = completitud(mart)
    finales = semanal.tail(8)[["ano", "semana", "inicio", "dias", "defunciones", "suicidios", "razon_registro", "registro_completo"]]
    completas = semanal[semanal["registro_completo"]]
    ultimas6 = completas.tail(6)
    mismo_ano = completas[completas["ano"] == ultimas6["ano"].iloc[-1]]
    ritmo_reciente = float(ultimas6["suicidios"].sum() / ultimas6["dias"].sum() * 7)
    ritmo_ano = float(mismo_ano["suicidios"].sum() / mismo_ano["dias"].sum() * 7)
    raras = mart.drop_duplicates(["ano", "semana"])
    raras = raras[(raras["dias_semana"] != 7)][["ano", "semana", "fecha_inicio_semana", "dias_semana"]]

    region = semanal[(semanal["ano"] >= ANO_MODELO) & (semanal["ano"] <= ano_max)].rename(columns={"suicidios": "y"})
    est = estacionalidad(region.reset_index(drop=True))
    com = comunas(mart, ano_max)

    resumen = {
        "filas": len(mart), "n_comunas": int(mart["comuna_codigo"].nunique()),
        "semanas": int(mart[["ano", "semana"]].drop_duplicates().shape[0]),
        "suicidios": int(mart["suicidios"].sum()), "suicidios_fuente": int(len(suic)),
        "fecha_corte": str(b.fecha_corte()), "ultimo_ano_cerrado": ano_max,
        "calendario": cal, "umbral_registro": b.UMBRAL_REGISTRO, "razon_registro_minima_interior": minimo_interior,
        "semanas_registro_incompleto": [f"{x}-S{y:02d}" for x, y in semanal.loc[~semanal["registro_completo"], ["ano", "semana"]].itertuples(index=False)],
        "cambio_nivel": {"por_dia_2020_2021": round(a / da, 4), "por_dia_ventana": round(bb / db, 4),
                         "razon": round((bb / db) / (a / da), 4), "p_valor": float(f"{prueba.pvalue:.3g}")},
        "homogeneidad_anos_ventana": {"chi2": round(chi_anos, 2), "gl": len(ventana) - 1,
                                      "p_valor": float(f"{stats.chi2.sf(chi_anos, len(ventana) - 1):.3g}")},
        "estacionalidad": {k: v for k, v in est.items() if k != "lrt"} | {"lrt": est["lrt"]},
        "comunas": {k: v for k, v in com.items() if k != "extremos"},
        "mart_sha256": file_sha256(b.OUTPUT_PATH),
    }

    lineas = [
        TITULO, "",
        "Generado por `scripts/eda_mart_suicidios_comuna_weekly.py` (stage `eda_mart_suicidios_comuna_weekly`) "
        f"desde `{b.OUTPUT_PATH.as_posix()}` (SHA256 `{resumen['mart_sha256']}`), "
        f"`{b.DEFUNCIONES_PATH.as_posix()}` y los Parquet anuales de Urgencias. Diccionario: "
        "`reports/dictionary/diccionario_mart_suicidios_comuna_weekly.md`.", "",
        "## 1. Cobertura y conciliación", "",
        f"- {resumen['filas']} filas = {resumen['n_comunas']} comunas x {resumen['semanas']} semanas DEIS "
        f"(incluidos los fragmentos `semana = 53`), desde 2020-01-01 hasta {max(mart['fecha_fin_semana'])}. "
        f"Última fecha de defunción del archivo nacional: {resumen['fecha_corte']}.",
        f"- Suicidios en el mart: {resumen['suicidios']}; defunciones X60-X84 de residentes RM en la fuente para "
        f"el mismo período: {resumen['suicidios_fuente']} (diferencia {resumen['suicidios'] - resumen['suicidios_fuente']}).",
        "- La categoría X60-X84 de `codigo_categoria_diag2` coincide registro a registro con el grupo publicado "
        "`codigo_grupo_diag2 = X60-X84` (la etapa falla si no). Categorías más frecuentes: "
        + ", ".join(f"{c} {n} ({n / len(suic) * 100:.1f}%)" for c, n in categorias.head(4).items()) + ".", "",
        tabla_md(anual[["ano", "dias", "suicidios", "por_dia", "tasa_100mil_ano", "defunciones", "pct_de_defunciones"]]), "",
        f"2026 es parcial ({int(anual['dias'].iloc[-1])} días): sus totales no se comparan con años completos; su "
        "ritmo diario sí.", "",
        "## 2. Calendario DEIS", "",
        f"- `semana_deis` reproduce la codificación (año, semana) publicada por Urgencias en "
        f"{cal['fechas_verificadas']} fechas de 2020 a 2026, con {cal['discrepancias']} discrepancias.",
        "- Semanas con un número de días distinto de 7 (el modelo usa `dias_semana` como exposición):", "",
        tabla_md(raras), "",
        "## 3. Registro de las semanas finales", "",
        f"Razón = defunciones diarias por todas las causas de la semana / mediana de las {b.SEMANAS_REFERENCIA} "
        f"semanas previas. Mínimo en semanas interiores de 2021 en adelante: {minimo_interior:.3f}; umbral de "
        f"registro incompleto: {b.UMBRAL_REGISTRO}.", "",
        tabla_md(finales), "",
        f"- Semanas marcadas con registro incompleto: {', '.join(resumen['semanas_registro_incompleto']) or 'ninguna'}.",
        f"- Suicidios en las últimas 6 semanas completas: {ritmo_reciente:.2f} por semana de 7 días, frente a "
        f"{ritmo_ano:.2f} en el conjunto de semanas completas del mismo año: no se observa un déficit que indique "
        "rezago propio de esta causa en esas semanas.",
        "- **Límite:** con un único snapshot no es posible medir cuántas defunciones recientes se inscribirán o "
        "recodificarán después; la regla solo detecta el rezago visible en el total de defunciones.", "",
        "## 4. Cambio de nivel 2020-2021", "",
        f"- Suicidios por día: {resumen['cambio_nivel']['por_dia_2020_2021']} en 2020-2021 frente a "
        f"{resumen['cambio_nivel']['por_dia_ventana']} en {ANO_MODELO}-{ano_max} (razón "
        f"{resumen['cambio_nivel']['razon']}; prueba binomial exacta condicionada a los días, p = "
        f"{resumen['cambio_nivel']['p_valor']}).",
        f"- Dentro de {ANO_MODELO}-{ano_max} los años tampoco son homogéneos (chi-cuadrado "
        f"{resumen['homogeneidad_anos_ventana']['chi2']}, gl {resumen['homogeneidad_anos_ventana']['gl']}, p = "
        f"{resumen['homogeneidad_anos_ventana']['p_valor']}).",
        "- **Hipótesis, no verificada:** 2020-2021 coinciden con la pandemia; no es posible determinar la causa "
        f"con los datos disponibles. **Decisión:** la ventana del modelo empieza en {ANO_MODELO} y su nivel se "
        "pondera hacia los años recientes.", "",
        f"## 5. Serie regional {ANO_MODELO}-{ano_max}: estacionalidad, dispersión y autocorrelación", "",
        "GLM de Poisson con efecto de año, exposición `log(dias / 7)` y k armónicos anuales:", "",
        tabla_md(pd.DataFrame(est["lrt"])), "",
        f"- Un armónico: máximo en la semana {est['semana_maxima']}, mínimo en la {est['semana_minima']}, razón "
        f"máximo/mínimo {est['razon_maximo_minimo']}.",
        f"- Dispersión de Pearson: {est['dispersion_pearson_k0']} sin estacionalidad y "
        f"{est['dispersion_pearson_k1']} con un armónico (1 = Poisson).",
        f"- Autocorrelación de los residuos de Pearson ({est['semanas']} semanas; banda ±{est['banda_acf']}): "
        + ", ".join(f"rezago {k}: {v}" for k, v in est["acf_residuos"].items()) + ".",
        "- **Lectura:** una vez descontados nivel y estación, la serie se comporta como Poisson y las semanas "
        "recientes no aportan información adicional; esto orienta a un modelo estructural de conteos y no a uno "
        "de rezagos.", "",
        f"## 6. Comunas {ANO_MODELO}-{ano_max}: escasez, ceros y heterogeneidad", "",
        f"- Media semanal por comuna: mínimo {com['media_semanal']['min']}, mediana {com['media_semanal']['50%']}, "
        f"máximo {com['media_semanal']['max']}.",
        f"- Comuna-semanas en cero: {com['ceros_observados'] * 100:.1f}% observado frente a "
        f"{com['ceros_esperados_poisson'] * 100:.1f}% esperado si cada comuna fuera Poisson con su media: no hay "
        f"exceso de ceros que justifique un modelo inflado en cero. Mediana de varianza/media por comuna: "
        f"{com['razon_varianza_media_mediana']}.",
        f"- Tasa anual por 100.000 habitantes: región {com['tasa_region']}, comunas entre {com['tasa_min']} y "
        f"{com['tasa_max']}. Prueba de homogeneidad frente a la población (chi-cuadrado {com['chi2']}, gl "
        f"{com['gl']}, p = {com['p_valor']}): las comunas difieren más de lo que explica el azar.", "",
        "Cinco comunas de menor y cinco de mayor tasa (residencia; pocos casos implican tasas inestables):", "",
        tabla_md(com["extremos"]), "",
        "- **Lectura:** con tan pocos casos, la tasa propia de una comuna es ruidosa pero informativa; por eso el "
        "modelo contrae cada tasa comunal hacia la regional (Bayes empírico) según los casos que aporta.", "",
        "## 7. Advertencias", "",
        "- El territorio es la comuna de residencia, no el lugar del suicidio ni un establecimiento; la relación "
        "con Urgencias es solo ecológica.",
        "- Son defunciones registradas con causa externa X60-X84; los eventos de intención no determinada "
        "(Y10-Y34) no se incluyen.",
    ]
    return "\n".join(lineas) + "\n", resumen


def validate_outputs(report: Path = OUTPUT_REPORT, summary: Path = OUTPUT_SUMMARY) -> None:
    if not report.read_text(encoding="utf-8").startswith(TITULO):
        raise ValueError(f"{report.name}: encabezado inesperado")
    datos = json.loads(summary.read_text(encoding="utf-8"))
    faltantes = {"filas", "suicidios", "suicidios_fuente", "calendario", "cambio_nivel", "estacionalidad", "comunas"} - set(datos)
    if faltantes:
        raise ValueError(f"{summary.name}: faltan claves {sorted(faltantes)}")
    if datos["suicidios"] != datos["suicidios_fuente"] or datos["calendario"]["discrepancias"]:
        raise ValueError(f"{summary.name}: el mart no concilia con la fuente o el calendario no coincide")


def main() -> None:
    texto, resumen = build_report()
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(texto, encoding="utf-8")
    OUTPUT_SUMMARY.write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    validate_outputs()
    print(f"EDA generado: {OUTPUT_REPORT.as_posix()}", flush=True)


if __name__ == "__main__":
    if "--force" in sys.argv:
        sys.argv.remove("--force")
    main()
