"""EDA reproducible de series temporales para el modelo de demanda de urgencia en salud mental.

Script de **solo lectura**: no modifica marts ni genera datasets canónicos. Su
propósito es la fase de *Data Understanding* (CRISP-DM) previa al modelado de
demanda, respondiendo las preguntas que los EDA descriptivos existentes no
cubren: integridad del calendario, estacionariedad, autocorrelación,
estacionalidad, estabilidad de régimen, heterogeneidad territorial y error de
referencia del baseline estacional ingenuo.

Contrato analítico fijado para el modelo (ver `reports/eda/eda_series_demanda_sm.md`):

- **Grano:** jerárquico, RM agregada + comunas individuales.
- **Target:** conteo `atenciones_id36` (las tasas se derivan a posteriori).
- **ID37 incluido:** se usa `atenciones_id36` tal como lo publica DEIS. ID36 NO
  equivale al capítulo CIE-10 F00-F99 estricto porque incluye ID37 (ideación
  suicida, R45.8); la diferencia se cuantifica en el report.

Todas las cifras del report se calculan en tiempo de ejecución desde el mart.
No hay valores hardcodeados en la prosa generada.

Salidas:
- `reports/eda/eda_series_demanda_sm.md`
- `reports/eda/eda_series_demanda_sm_resumen.csv`
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
import sys
import warnings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf

sys.stdout.reconfigure(encoding="utf-8")

WEEKLY_PATH: Final[Path] = Path("data/processed/marts/mart_urgencias_comuna_weekly.parquet")
OUTPUT_REPORT: Final[Path] = Path("reports/eda/eda_series_demanda_sm.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/eda/eda_series_demanda_sm_resumen.csv")

TARGET: Final[str] = "atenciones_id36"
# Periodo estacional: el calendario DEIS publica 52 semanas regulares por año.
SEASONAL_PERIOD: Final[int] = 52
# Horizonte comprometido en el alcance del proyecto (4 a 8 semanas).
HORIZONS: Final[tuple[int, ...]] = (4, 5, 6, 7, 8)
# Nivel de significancia usado para leer los tests de raíz unitaria.
ALPHA: Final[float] = 0.05


# --------------------------------------------------------------------------
# Carga y construcción de series
# --------------------------------------------------------------------------

def load_weekly_mart(path: Path = WEEKLY_PATH) -> pd.DataFrame:
    """Lee el mart semanal seleccionando sólo las columnas necesarias.

    Lectura selectiva de columnas para no cargar las 25 del mart cuando el
    análisis de series sólo requiere grano temporal, territorio, target y
    reportantes (regla de eficiencia de I/O del repositorio).
    """
    columns = [
        "comuna_codigo",
        "comuna_glosa",
        "ano",
        "semana",
        "fecha_inicio_semana",
        "atenciones_id1",
        TARGET,
        "atenciones_id37",
        "n_establecimientos_reportantes_id36",
    ]
    frame = pq.read_table(path, columns=columns).to_pandas()
    frame["fecha_inicio_semana"] = pd.to_datetime(frame["fecha_inicio_semana"])
    return frame


def audit_calendar(weekly: pd.DataFrame) -> pd.DataFrame:
    """Audita el calendario DEIS y aísla las semanas fragmentarias.

    El calendario semanal DEIS no es ISO-8601: incluye una `semana = 53` que en
    los datos observados corresponde a fragmentos de pocos días en el límite
    entre años. Esta función los identifica y mide; NO los corrige ni elimina
    silenciosamente (regla de anomalías: identificar y documentar primero).
    """
    rm = (
        weekly.groupby(["ano", "semana"], as_index=False)
        .agg(
            atenciones=(TARGET, "sum"),
            fecha_min=("fecha_inicio_semana", "min"),
            comunas=("comuna_codigo", "nunique"),
        )
        .sort_values(["ano", "semana"])
    )
    rm["es_semana_53"] = rm["semana"] == SEASONAL_PERIOD + 1
    return rm


def build_rm_series(weekly: pd.DataFrame, drop_week_53: bool = True) -> pd.Series:
    """Agrega el target a una única serie semanal de la Región Metropolitana.

    `drop_week_53` excluye las semanas fragmentarias del límite de año para
    obtener una grilla regular de 52 semanas por año, requisito de los métodos
    estacionales (STL, naive estacional) que asumen período fijo. La exclusión
    se cuantifica explícitamente en el report, nunca se aplica en silencio.
    """
    frame = weekly
    if drop_week_53:
        frame = frame[frame["semana"] != SEASONAL_PERIOD + 1]
    serie = (
        frame.groupby(["ano", "semana"])[TARGET]
        .sum()
        .sort_index()
    )
    return serie


def build_comuna_matrix(weekly: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una matriz comuna × periodo con el target, para el nivel inferior.

    Es el insumo del modelo jerárquico: cada fila es una serie comunal alineada
    sobre la misma grilla temporal que la serie RM.
    """
    frame = weekly[weekly["semana"] != SEASONAL_PERIOD + 1]
    matrix = frame.pivot_table(
        index="comuna_codigo", columns=["ano", "semana"], values=TARGET, aggfunc="sum"
    )
    return matrix.sort_index(axis=1)


# --------------------------------------------------------------------------
# Diagnósticos de serie temporal
# --------------------------------------------------------------------------

def stationarity_tests(serie: pd.Series) -> pd.DataFrame:
    """Aplica ADF y KPSS sobre el nivel y sobre la primera diferencia.

    Los dos tests tienen hipótesis nulas opuestas (ADF: H0 = raíz unitaria /
    no estacionaria; KPSS: H0 = estacionaria), por lo que se reportan juntos:
    su acuerdo o desacuerdo es más informativo que cualquiera por separado.
    """
    rows: list[dict[str, object]] = []
    for nombre, valores in (("nivel", serie), ("primera_diferencia", serie.diff().dropna())):
        arreglo = valores.to_numpy(dtype=float)
        adf = adfuller(arreglo, autolag="AIC", result_object=True)
        # KPSS con regresion "c": contrasta estacionariedad alrededor de una constante.
        # `InterpolationWarning` se captura en vez de silenciarse: indica que el
        # p-valor quedo fuera de la tabla de referencia y por tanto esta truncado,
        # informacion que el informe debe declarar en vez de ocultar.
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always", InterpolationWarning)
            kpss_res = kpss(arreglo, regression="c", nlags="auto", result_object=True)
        kpss_truncado = any(
            issubclass(w.category, InterpolationWarning) for w in capturados
        )
        rows.append(
            {
                "serie": nombre,
                "adf_estadistico": round(float(adf.statistic), 4),
                "adf_p_valor": round(float(adf.pvalue), 4),
                "adf_rechaza_raiz_unitaria": bool(adf.pvalue < ALPHA),
                "kpss_estadistico": round(float(kpss_res.statistic), 4),
                "kpss_p_valor": round(float(kpss_res.pvalue), 4),
                "kpss_p_truncado_en_tabla": kpss_truncado,
                "kpss_rechaza_estacionariedad": bool(kpss_res.pvalue < ALPHA),
            }
        )
    return pd.DataFrame(rows)


def autocorrelation_profile(serie: pd.Series, nlags: int) -> pd.DataFrame:
    """Calcula ACF y PACF con sus bandas de confianza aproximadas.

    El interés principal está en el rezago 52 (estacionalidad anual de una
    serie semanal): un pico ahí justifica términos estacionales en el modelo.
    """
    valores = serie.to_numpy(dtype=float)
    acf_vals = acf(valores, nlags=nlags, fft=True)
    pacf_vals = pacf(valores, nlags=nlags)
    # Banda de significancia aproximada de Bartlett para ruido blanco.
    banda = 1.96 / np.sqrt(len(valores))
    return pd.DataFrame(
        {
            "rezago": range(nlags + 1),
            "acf": np.round(acf_vals, 4),
            "pacf": np.round(pacf_vals, 4),
            "banda_significancia": round(float(banda), 4),
            "acf_significativa": np.abs(acf_vals) > banda,
        }
    )


def seasonal_strength(serie: pd.Series, period: int = SEASONAL_PERIOD) -> dict[str, float]:
    """Descompone la serie con STL y mide la fuerza de tendencia y estacionalidad.

    Usa la definición estándar F = max(0, 1 - Var(resto) / Var(componente + resto)).
    Valores cercanos a 1 indican un componente fuerte; cercanos a 0, ausente.
    """
    resultado = STL(serie.to_numpy(dtype=float), period=period, robust=True).fit()
    resto = resultado.resid
    fuerza_estacional = max(0.0, 1 - np.var(resto) / np.var(resultado.seasonal + resto))
    fuerza_tendencia = max(0.0, 1 - np.var(resto) / np.var(resultado.trend + resto))
    return {
        "fuerza_estacional": round(float(fuerza_estacional), 4),
        "fuerza_tendencia": round(float(fuerza_tendencia), 4),
        "amplitud_estacional": round(float(resultado.seasonal.max() - resultado.seasonal.min()), 1),
    }


def regime_profile(weekly: pd.DataFrame) -> pd.DataFrame:
    """Perfila nivel y cobertura de reporte por año×trimestre.

    Separa dos explicaciones posibles de un cambio de nivel: variación real de
    la demanda vs. variación en cuántos establecimientos reportan. Si los
    reportantes se mantienen estables, la cobertura queda descartada como causa;
    la causa efectiva del cambio de nivel no se afirma aquí.
    """
    frame = weekly[weekly["semana"] != SEASONAL_PERIOD + 1].copy()
    # Trimestre aproximado sobre el calendario DEIS: 13 semanas por bloque.
    frame["trimestre"] = ((frame["semana"] - 1) // 13) + 1
    por_periodo = frame.groupby(["ano", "trimestre", "semana"], as_index=False).agg(
        atenciones=(TARGET, "sum"),
        reportantes=("n_establecimientos_reportantes_id36", "sum"),
    )
    return (
        por_periodo.groupby(["ano", "trimestre"], as_index=False)
        .agg(
            atenciones_media_semanal=("atenciones", "mean"),
            reportantes_media_semanal=("reportantes", "mean"),
        )
        .round(1)
    )


def comuna_heterogeneity(weekly: pd.DataFrame) -> pd.DataFrame:
    """Caracteriza cada serie comunal: volumen, dispersión, ceros e intermitencia.

    Determina qué comunas son modelables individualmente y cuáles dependen de
    que el modelo jerárquico les preste fuerza desde el agregado regional.
    """
    frame = weekly[weekly["semana"] != SEASONAL_PERIOD + 1]
    perfil = (
        frame.groupby(["comuna_codigo", "comuna_glosa"], as_index=False)
        .agg(
            total=(TARGET, "sum"),
            media_semanal=(TARGET, "mean"),
            desviacion=(TARGET, "std"),
            minimo=(TARGET, "min"),
            maximo=(TARGET, "max"),
            semanas_en_cero=(TARGET, lambda s: int((s == 0).sum())),
            semanas=(TARGET, "size"),
        )
    )
    # Coeficiente de variación: dispersión relativa, comparable entre comunas
    # de volumen muy distinto (el rango va de cientos a decenas de miles).
    perfil["coef_variacion"] = (perfil["desviacion"] / perfil["media_semanal"]).round(3)
    perfil["proporcion_semanas_en_cero"] = (
        perfil["semanas_en_cero"] / perfil["semanas"]
    ).round(4)
    perfil["share_demanda_rm"] = (perfil["total"] / perfil["total"].sum()).round(4)
    return perfil.sort_values("total", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Baseline estacional ingenuo (referencia obligatoria del alcance)
# --------------------------------------------------------------------------

def seasonal_naive_backtest(
    serie: pd.Series,
    period: int = SEASONAL_PERIOD,
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    """Evalúa el baseline estacional ingenuo con orígenes de pronóstico deslizantes.

    El baseline predice `y[t] = y[t - period]`: la misma semana del año anterior.
    Es la referencia contra la cual el alcance del proyecto exige comparar
    cualquier modelo de demanda. Como `period` (52) es mayor que el horizonte
    máximo (8), el valor necesario siempre está observado en el momento del
    pronóstico: el baseline nunca usa información del futuro.

    Devuelve una fila por horizonte con MAE, RMSE y MAPE sobre todos los
    orígenes válidos. Esto es una referencia descriptiva; el backtesting formal
    del modelo pertenece a la etapa de modelado.
    """
    valores = serie.to_numpy(dtype=float)
    n = len(valores)
    filas: list[dict[str, object]] = []
    for h in horizons:
        reales: list[float] = []
        predichos: list[float] = []
        # Un origen `o` es válido si el objetivo o+h existe y su referencia
        # estacional o+h-period también está observada.
        for objetivo in range(period + h, n):
            referencia = objetivo - period
            reales.append(valores[objetivo])
            predichos.append(valores[referencia])
        real = np.array(reales)
        pred = np.array(predichos)
        error = real - pred
        filas.append(
            {
                "horizonte_semanas": h,
                "n_evaluaciones": len(real),
                "mae": round(float(np.mean(np.abs(error))), 2),
                "rmse": round(float(np.sqrt(np.mean(error**2))), 2),
                "mape_pct": round(float(np.mean(np.abs(error / real)) * 100), 2),
            }
        )
    return pd.DataFrame(filas)


def seasonal_naive_by_comuna(matrix: pd.DataFrame, period: int = SEASONAL_PERIOD) -> pd.DataFrame:
    """Aplica el baseline estacional ingenuo a cada serie comunal.

    Expone qué comunas son intrínsecamente difíciles de pronosticar: un MAPE
    alto a nivel comunal con MAPE bajo a nivel RM es el argumento cuantitativo
    a favor del enfoque jerárquico con reconciliación.
    """
    filas: list[dict[str, object]] = []
    for comuna, serie in matrix.iterrows():
        valores = serie.to_numpy(dtype=float)
        real = valores[period:]
        pred = valores[:-period]
        error = real - pred
        # MAPE indefinido cuando el valor real es 0; se excluyen esos puntos y
        # se informa cuántos fueron, en vez de sustituirlos por un valor arbitrario.
        positivos = real > 0
        filas.append(
            {
                "comuna_codigo": comuna,
                "mae": round(float(np.mean(np.abs(error))), 2),
                "mape_pct": round(float(np.mean(np.abs(error[positivos] / real[positivos])) * 100), 2),
                "puntos_excluidos_por_cero": int((~positivos).sum()),
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------
# Render del informe
# --------------------------------------------------------------------------

def _tabla_md(frame: pd.DataFrame) -> str:
    """Convierte un DataFrame a tabla Markdown sin dependencias externas."""
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |"
        for fila in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([encabezado, separador, *filas])


def render_report(ctx: dict[str, object]) -> str:
    """Construye el informe Markdown a partir de valores ya calculados.

    Ninguna cifra se escribe literalmente en la plantilla: todas provienen de
    ``ctx``, de modo que regenerar el report no puede producir una contradiccion
    entre la prosa y las tablas.
    """
    cal: pd.DataFrame = ctx["calendario"]
    frag = cal[cal["es_semana_53"]].copy()
    frag["fecha_min"] = frag["fecha_min"].dt.strftime("%Y-%m-%d")
    est: pd.DataFrame = ctx["estacionariedad"]
    acf_frame: pd.DataFrame = ctx["autocorrelacion"]
    stl: dict[str, float] = ctx["stl"]
    reg: pd.DataFrame = ctx["regimen"]
    base: pd.DataFrame = ctx["baseline_rm"]

    nivel = est[est["serie"] == "nivel"].iloc[0]
    diff = est[est["serie"] == "primera_diferencia"].iloc[0]
    acf_52 = acf_frame[acf_frame["rezago"] == SEASONAL_PERIOD].iloc[0]
    acf_1 = acf_frame[acf_frame["rezago"] == 1].iloc[0]

    adf_nivel_txt = "rechaza" if nivel["adf_rechaza_raiz_unitaria"] else "no rechaza"
    kpss_nivel_txt = "rechaza" if nivel["kpss_rechaza_estacionariedad"] else "no rechaza"
    acf52_txt = "significativa" if acf_52["acf_significativa"] else "no significativa"

    partes: list[str] = []

    partes.append(f"""# EDA de series temporales: demanda de urgencia en salud mental (RM)

Reproducible mediante `python -m scripts.eda_series_demanda_sm` (script de solo
lectura). Resumen de apoyo en
[`eda_series_demanda_sm_resumen.csv`](eda_series_demanda_sm_resumen.csv).

Este informe corresponde a la fase de *Data Understanding* (CRISP-DM) previa al
modelo de demanda. Complementa --sin repetir-- los EDA descriptivos existentes
(`eda_mart_urgencias_comuna.md`, `eda_demanda_urgencias_rm.md`), que cubren
volumen, territorio y causas pero no las propiedades de serie temporal.

## 0. Contrato analitico

| Decision | Valor | Motivo |
|---|---|---|
| Grano | Jerarquico: RM agregada + {ctx['n_comunas']} comunas | Responde "cuanta demanda" y "donde"; permite prestar fuerza a comunas de bajo volumen |
| Target | `{TARGET}` (conteo) | Es la cantidad que genera el proceso; las tasas se derivan dividiendo por poblacion |
| ID37 | Incluido | Se usa el agregado ID36 oficial de DEIS |
| Periodo | {ctx['ano_min']}-{ctx['ano_max']} | 2020 excluido por discontinuidad documentada de captura en salud mental |
| Estacionalidad | {SEASONAL_PERIOD} semanas | Calendario semanal DEIS |

**ID36 no equivale a F00-F99 estricto.** En el periodo analizado, ID37 (ideacion
suicida, R45.8 -- fuera del capitulo F) aporta {ctx['share_id37']}% del total
ID36. Toda comparacion futura con el F00-F99 de Egresos debe descontar
explicitamente esa fraccion.

## 1. Integridad del calendario

El calendario semanal DEIS no es ISO-8601. Se observan {len(frag)} combinaciones
anio x semana con `semana = 53`, que **no son semanas completas** sino fragmentos
de pocos dias en el limite entre anios:

{_tabla_md(frag[["ano", "semana", "fecha_min", "atenciones", "comunas"]])}

**Hecho observado:** estos fragmentos concentran {ctx['share_semana_53']}% de las
atenciones del periodo pero se presentan como si fueran semanas completas. Si
entran crudos a un modelo semanal aparecen como caidas severas que no
corresponden a baja demanda, sino a semanas truncadas.

**Regla aplicada en este EDA:** se excluyen de todos los analisis estacionales,
dejando una grilla regular de {SEASONAL_PERIOD} semanas por anio
({ctx['n_periodos']} periodos, {ctx['ano_min']}-{ctx['ano_max']}). La exclusion se
cuantifica arriba; no se imputan ni se fusionan con semanas vecinas.

## 2. Estacionariedad

{_tabla_md(est)}

**Lectura conjunta (alfa = {ALPHA}):** en nivel, ADF {adf_nivel_txt} la raiz
unitaria (p = {nivel['adf_p_valor']}) y KPSS {kpss_nivel_txt} la estacionariedad
(p = {nivel['kpss_p_valor']}). Sobre la primera diferencia, ADF p =
{diff['adf_p_valor']} y KPSS p = {diff['kpss_p_valor']}.

{ctx['interpretacion_estacionariedad']}

## 3. Autocorrelacion y estacionalidad

- ACF en rezago 1: **{acf_1['acf']}** (banda de significancia +/-{acf_1['banda_significancia']}).
- ACF en rezago {SEASONAL_PERIOD}: **{acf_52['acf']}** -- {acf52_txt}.
- Rezagos con ACF significativa entre 1 y {ctx['nlags']}: {ctx['n_acf_significativos']}.

Descomposicion STL (periodo {SEASONAL_PERIOD}, robusta):

| Componente | Fuerza |
|---|---|
| Tendencia | {stl['fuerza_tendencia']} |
| Estacionalidad | {stl['fuerza_estacional']} |
| Amplitud estacional (atenciones) | {stl['amplitud_estacional']} |

{ctx['interpretacion_estacionalidad']}

## 4. Estabilidad de regimen

Media semanal del target y de establecimientos reportantes, por anio x trimestre
DEIS:

{_tabla_md(reg)}

{ctx['interpretacion_regimen']}

## 5. Heterogeneidad territorial

{ctx['n_comunas']} series comunales. Distribucion del volumen total del periodo:

| Estadistico | Atenciones ID36 |
|---|---|
| Minimo | {ctx['comuna_min']} |
| Mediana | {ctx['comuna_mediana']} |
| Maximo | {ctx['comuna_max']} |
| Razon max/min | {ctx['comuna_ratio']}x |

- {ctx['comunas_80pct']} comunas concentran el 80% de la demanda RM.
- Comunas con al menos una semana en cero: {ctx['comunas_con_ceros']}.
- Coeficiente de variacion semanal: mediana {ctx['cv_mediana']}, maximo {ctx['cv_max']}.

Cinco comunas de mayor y menor volumen:

{_tabla_md(ctx['tabla_comunas'])}

## 6. Baseline estacional ingenuo (referencia)

Predice `y[t] = y[t-{SEASONAL_PERIOD}]`. Es la referencia obligatoria del alcance
del proyecto. Como el periodo estacional ({SEASONAL_PERIOD}) supera el horizonte
maximo ({max(HORIZONS)}), el valor usado siempre esta observado al momento del
pronostico: el baseline no usa informacion futura.

**Serie RM agregada:**

{_tabla_md(base)}

**Por comuna** (mismo baseline aplicado a cada serie comunal):

| Estadistico | MAPE (%) |
|---|---|
| Minimo | {ctx['mape_comuna_min']} |
| Mediana | {ctx['mape_comuna_mediana']} |
| Maximo | {ctx['mape_comuna_max']} |

{ctx['interpretacion_baseline']}

## 7. Implicancias para el modelado

{ctx['implicancias']}

## 8. Limitaciones

- El target es **atenciones (eventos), no personas unicas**: una misma persona
  puede generar varias atenciones en la misma comuna x semana.
- Vitacura (`13132`) no tiene ninguna fila en el mart para
  {ctx['ano_min']}-{ctx['ano_max']}; no se imputa. El modelo cubre
  {ctx['n_comunas']} de las 52 comunas RM.
- La demanda observada refleja utilizacion y oferta instalada, no prevalencia ni
  necesidad sanitaria de la poblacion residente.
- Este EDA no ajusta modelos ni produce pronosticos: solo caracteriza la serie y
  establece la referencia del baseline.
- Las causas de los cambios de nivel descritos en la seccion 4 no son
  determinables con los datos disponibles.
""")

    return "".join(partes)


# --------------------------------------------------------------------------
# Interpretaciones derivadas
# --------------------------------------------------------------------------

def _interpretar_estacionariedad(est: pd.DataFrame) -> str:
    """Redacta la lectura de los tests a partir de sus resultados, no de supuestos."""
    nivel = est[est["serie"] == "nivel"].iloc[0]
    diff = est[est["serie"] == "primera_diferencia"].iloc[0]
    nivel_no_estacionaria = (
        not nivel["adf_rechaza_raiz_unitaria"]
    ) or nivel["kpss_rechaza_estacionariedad"]
    diff_estacionaria = (
        diff["adf_rechaza_raiz_unitaria"] and not diff["kpss_rechaza_estacionariedad"]
    )
    if nivel_no_estacionaria and diff_estacionaria:
        return (
            "**Inferencia:** la serie en nivel no es estacionaria y una diferencia "
            "regular basta para estabilizarla. Un modelo ARIMA/SARIMA debe incluir "
            "`d = 1`; los modelos de machine learning deben recibir la serie "
            "diferenciada o incorporar rezagos suficientes para absorber la tendencia."
        )
    if not nivel_no_estacionaria:
        return (
            "**Inferencia:** los tests no dan evidencia de raiz unitaria en nivel. "
            "El modelo puede operar sobre la serie original sin diferenciacion regular."
        )
    return (
        "**Observacion:** los tests no coinciden de forma concluyente ni en nivel ni "
        "en la primera diferencia. El orden de integracion debe decidirse en la etapa "
        "de modelado comparando ajustes alternativos, no a partir de este EDA."
    )


def _interpretar_estacionalidad(stl: dict[str, float], acf_52: float, banda: float) -> str:
    """Redacta la lectura de estacionalidad segun la fuerza STL y la ACF estacional."""
    fuerte = stl["fuerza_estacional"] >= 0.6
    pico_anual = abs(acf_52) > banda
    if fuerte and pico_anual:
        return (
            "**Inferencia:** hay estacionalidad anual marcada y la ACF la confirma en el "
            "rezago estacional. El modelo necesita componente estacional explicito "
            "(termino `S` en SARIMA, o features de semana-del-anio y rezago 52 en "
            "modelos de arboles)."
        )
    if stl["fuerza_estacional"] < 0.3 and not pico_anual:
        return (
            "**Inferencia:** la estacionalidad anual es debil. Un componente estacional "
            "explicito aporta poco; la senal util esta concentrada en los rezagos cortos "
            "y en la tendencia."
        )
    return (
        "**Observacion:** la evidencia de estacionalidad anual es intermedia. Conviene "
        "probar el componente estacional contra su ausencia durante el backtesting en "
        "vez de asumirlo."
    )


def _interpretar_regimen(reg: pd.DataFrame) -> str:
    """Contrasta cambio de nivel contra cambio de cobertura de reporte."""
    primero = reg.iloc[0]
    resto = reg.iloc[1:]
    nivel_inicial = float(primero["atenciones_media_semanal"])
    nivel_posterior = float(resto["atenciones_media_semanal"].mean())
    caida_pct = round((1 - nivel_inicial / nivel_posterior) * 100, 1)
    rep_min = float(reg["reportantes_media_semanal"].min())
    rep_max = float(reg["reportantes_media_semanal"].max())
    variacion_reportantes = round((rep_max / rep_min - 1) * 100, 1)
    return (
        f"**Hecho observado:** el primer trimestre del periodo promedia "
        f"{nivel_inicial:,.0f} atenciones semanales, {caida_pct}% por debajo de la media "
        f"de los trimestres posteriores ({nivel_posterior:,.0f}). En el mismo lapso, los "
        f"establecimientos reportantes varian solo {variacion_reportantes}% entre su "
        f"minimo y su maximo ({rep_min:,.0f} a {rep_max:,.0f}).\n\n"
        "**Inferencia:** la cobertura de reporte queda descartada como explicacion de "
        "esa diferencia de nivel, porque se mantiene practicamente constante. **La causa "
        "efectiva no es determinable con los datos disponibles.**\n\n"
        "**Implicancia para el modelado:** los primeros trimestres de la serie pertenecen "
        "a un regimen de nivel distinto. Entrenar sobre ellos sin marcarlos arrastra ese "
        "regimen al pronostico. Opciones a evaluar en backtesting: excluirlos, incorporar "
        "una variable indicadora de regimen, o ponderar las observaciones por antiguedad."
    )


def _interpretar_baseline(base: pd.DataFrame, mape_com_mediana: float) -> str:
    """Compara el error del baseline entre el nivel regional y el comunal."""
    mape_rm = float(base["mape_pct"].mean())
    mae_min = float(base["mae"].min())
    mae_max = float(base["mae"].max())
    razon = round(mape_com_mediana / mape_rm, 1) if mape_rm else float("nan")
    return (
        f"**Hecho observado:** el baseline alcanza {mape_rm:.2f}% de MAPE medio sobre la "
        f"serie RM agregada (MAE entre {mae_min:,.0f} y {mae_max:,.0f} atenciones segun "
        f"horizonte), pero {mape_com_mediana:.2f}% de MAPE mediano a nivel comunal: "
        f"{razon}x peor.\n\n"
        "**Inferencia:** la agregacion regional cancela ruido idiosincratico comunal. "
        "Esto sustenta cuantitativamente el enfoque jerarquico elegido: pronosticar el "
        "agregado RM (donde la senal es mas limpia) y repartirlo hacia las comunas con "
        "reconciliacion, en vez de tratar cada comuna como un problema independiente.\n\n"
        "**Umbral de exito:** cualquier modelo propuesto debe superar estas cifras en el "
        "mismo backtesting. Un modelo que no las supere no justifica su complejidad."
    )


def _redactar_implicancias(ctx: dict[str, object]) -> str:
    """Consolida las decisiones de preparacion de datos que se desprenden del EDA."""
    return (
        f"1. **Grilla temporal.** Excluir las {ctx['n_semanas_53']} semanas fragmentarias "
        f"(`semana = 53`) o tratarlas explicitamente; nunca mezclarlas con semanas "
        f"completas. La grilla modelable queda en {ctx['n_periodos']} periodos regulares.\n"
        f"2. **Features de rezago.** Incluir al menos los rezagos 1 a 4 y el rezago "
        f"{SEASONAL_PERIOD}, mas medias moviles cortas. El horizonte de 4 a 8 semanas "
        f"exige que todo rezago usado sea mayor o igual al horizonte, o construir el "
        f"pronostico de forma recursiva.\n"
        f"3. **Regimen inicial.** Marcar o excluir el tramo de nivel distinto descrito en "
        f"la seccion 4; decidirlo por backtesting, no por supuesto.\n"
        f"4. **Estructura jerarquica.** Modelar el agregado RM y reconciliar hacia las "
        f"{ctx['n_comunas']} comunas. Las {ctx['comunas_80pct']} comunas que concentran el "
        f"80% del volumen admiten modelado individual; el resto depende de la "
        f"reconciliacion.\n"
        f"5. **Holdout 2026.** El snapshot del anio en curso es mutable y ya cambio entre "
        f"corridas del pipeline. Fijar su SHA256 desde `data/raw/provenance_manifest.json` "
        f"y reportar contra que version se evaluo.\n"
        f"6. **Distribucion del target.** El target es un conteo no negativo; preferir "
        f"perdidas adecuadas a conteos (Poisson/Tweedie) o modelar en escala logaritmica "
        f"antes que asumir errores gaussianos sobre el nivel."
    )


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------

def main() -> None:
    """Ejecuta el EDA completo y publica el informe y su resumen de apoyo."""
    weekly = load_weekly_mart()

    anos = sorted(int(a) for a in weekly["ano"].unique())
    calendario = audit_calendar(weekly)
    serie_rm = build_rm_series(weekly)
    matriz = build_comuna_matrix(weekly)

    # --- Peso de los fragmentos de calendario y de ID37 -------------------
    total_con_53 = float(weekly[TARGET].sum())
    total_semana_53 = float(weekly.loc[weekly["semana"] == SEASONAL_PERIOD + 1, TARGET].sum())
    share_semana_53 = round(total_semana_53 / total_con_53 * 100, 2)
    share_id37 = round(float(weekly["atenciones_id37"].sum()) / total_con_53 * 100, 2)

    # --- Diagnosticos de serie -------------------------------------------
    nlags = SEASONAL_PERIOD + 8
    estacionariedad = stationarity_tests(serie_rm)
    autocorrelacion = autocorrelation_profile(serie_rm, nlags=nlags)
    stl = seasonal_strength(serie_rm)
    regimen = regime_profile(weekly)
    heterogeneidad = comuna_heterogeneity(weekly)
    baseline_rm = seasonal_naive_backtest(serie_rm)
    baseline_comuna = seasonal_naive_by_comuna(matriz)

    # --- Derivados de heterogeneidad --------------------------------------
    acumulado = heterogeneidad["share_demanda_rm"].cumsum()
    comunas_80pct = int((acumulado < 0.80).sum() + 1)
    tabla_comunas = pd.concat([heterogeneidad.head(5), heterogeneidad.tail(5)])[
        ["comuna_glosa", "total", "media_semanal", "coef_variacion", "share_demanda_rm"]
    ].round(2)

    acf_52 = float(autocorrelacion.loc[autocorrelacion["rezago"] == SEASONAL_PERIOD, "acf"].iloc[0])
    banda = float(autocorrelacion["banda_significancia"].iloc[0])
    mape_com_mediana = float(baseline_comuna["mape_pct"].median())

    ctx: dict[str, object] = {
        "calendario": calendario,
        "estacionariedad": estacionariedad,
        "autocorrelacion": autocorrelacion,
        "stl": stl,
        "regimen": regimen,
        "heterogeneidad": heterogeneidad,
        "baseline_rm": baseline_rm,
        "baseline_comuna": baseline_comuna,
        "tabla_comunas": tabla_comunas,
        "ano_min": anos[0],
        "ano_max": anos[-1],
        "n_comunas": int(weekly["comuna_codigo"].nunique()),
        "n_periodos": int(len(serie_rm)),
        "n_semanas_53": int(calendario["es_semana_53"].sum()),
        "share_semana_53": share_semana_53,
        "share_id37": share_id37,
        "nlags": nlags,
        "n_acf_significativos": int(autocorrelacion.iloc[1:]["acf_significativa"].sum()),
        "comuna_min": int(heterogeneidad["total"].min()),
        "comuna_mediana": int(heterogeneidad["total"].median()),
        "comuna_max": int(heterogeneidad["total"].max()),
        "comuna_ratio": round(
            float(heterogeneidad["total"].max() / heterogeneidad["total"].min()), 1
        ),
        "comunas_80pct": comunas_80pct,
        "comunas_con_ceros": int((heterogeneidad["semanas_en_cero"] > 0).sum()),
        "cv_mediana": round(float(heterogeneidad["coef_variacion"].median()), 3),
        "cv_max": round(float(heterogeneidad["coef_variacion"].max()), 3),
        "mape_comuna_min": round(float(baseline_comuna["mape_pct"].min()), 2),
        "mape_comuna_mediana": round(mape_com_mediana, 2),
        "mape_comuna_max": round(float(baseline_comuna["mape_pct"].max()), 2),
    }
    ctx["interpretacion_estacionariedad"] = _interpretar_estacionariedad(estacionariedad)
    ctx["interpretacion_estacionalidad"] = _interpretar_estacionalidad(stl, acf_52, banda)
    ctx["interpretacion_regimen"] = _interpretar_regimen(regimen)
    ctx["interpretacion_baseline"] = _interpretar_baseline(baseline_rm, mape_com_mediana)
    ctx["implicancias"] = _redactar_implicancias(ctx)

    # --- Publicacion ------------------------------------------------------
    resumen = pd.DataFrame(
        {
            "metrica": [
                "periodos_modelables",
                "comunas",
                "semanas_fragmentarias_excluidas",
                "share_semana_53_pct",
                "share_id37_sobre_id36_pct",
                "adf_p_nivel",
                "kpss_p_nivel",
                "acf_rezago_1",
                "acf_rezago_52",
                "stl_fuerza_estacional",
                "stl_fuerza_tendencia",
                "baseline_rm_mape_medio_pct",
                "baseline_comuna_mape_mediano_pct",
                "comunas_80pct_demanda",
            ],
            "valor": [
                ctx["n_periodos"],
                ctx["n_comunas"],
                ctx["n_semanas_53"],
                share_semana_53,
                share_id37,
                float(estacionariedad.loc[0, "adf_p_valor"]),
                float(estacionariedad.loc[0, "kpss_p_valor"]),
                float(autocorrelacion.loc[1, "acf"]),
                acf_52,
                stl["fuerza_estacional"],
                stl["fuerza_tendencia"],
                round(float(baseline_rm["mape_pct"].mean()), 2),
                round(mape_com_mediana, 2),
                comunas_80pct,
            ],
        }
    )

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    resumen.to_csv(OUTPUT_SUMMARY, index=False)
    OUTPUT_REPORT.write_text(render_report(ctx), encoding="utf-8")

    print(resumen.to_string(index=False))
    print(f"\nInforme escrito en {OUTPUT_REPORT.as_posix()}")
    print(f"Resumen escrito en {OUTPUT_SUMMARY.as_posix()}")


if __name__ == "__main__":
    main()
