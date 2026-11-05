"""EDA reproducible de `mart_urgencias_establecimiento_weekly`.

Responde lo que el pronóstico por establecimiento necesita saber antes de
modelar: qué establecimientos tienen una serie semanal continua, con qué
volumen, y qué tan estable es la publicación de ID42 (hospitalizaciones
derivadas desde urgencia por F00-F99). Solo lee el mart; no lo modifica.

Escribe `reports/eda/eda_mart_urgencias_establecimiento_weekly.md` y su tabla
de apoyo `reports/eda/eda_mart_urgencias_establecimiento_weekly_resumen.csv`.
Uso (vía pipeline): `python scripts/run_pipeline.py --stage eda_mart_urgencias_establecimiento_weekly`
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq

from src.data.build_urgencias_establecimiento_weekly_mart import (
    HOSPITALIZACION_COLUMN,
    OUTPUT_PATH as MART_PATH,
)

OUTPUT_REPORT: Final[Path] = Path("reports/eda/eda_mart_urgencias_establecimiento_weekly.md")
OUTPUT_SUMMARY: Final[Path] = Path("reports/eda/eda_mart_urgencias_establecimiento_weekly_resumen.csv")
TITULO: Final[str] = "# EDA: `mart_urgencias_establecimiento_weekly`"
# Semana 53 del calendario DEIS: fragmento de pocos días, fuera de la grilla regular.
SEMANA_FRAGMENTARIA: Final[int] = 53
# Umbrales de volumen semanal medio con que se describe qué series son modelables.
UMBRALES_VOLUMEN: Final[tuple[float, ...]] = (1.0, 5.0, 10.0)


def _fmt(valor: float, decimales: int = 0) -> str:
    """Número con separador de miles chileno."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _tabla_md(frame: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    separador = "|" + "|".join("---" for _ in frame.columns) + "|"
    filas = ["| " + " | ".join(str(v) for v in fila) + " |" for fila in frame.itertuples(index=False)]
    return "\n".join([encabezado, separador, *filas])


def cobertura(regular: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Semanas reportadas por establecimiento sobre la grilla regular del período."""
    total = regular[["ano", "semana"]].drop_duplicates().shape[0]
    por_estab = regular.groupby("establecimiento_codigo").agg(
        tipo=("tipo_establecimiento_urgencia", "first"),
        semanas=("semana", "size"),
        primera=("fecha_inicio_semana", "min"),
        ultima=("fecha_inicio_semana", "max"),
        id36_media=("atenciones_id36", "mean"),
        id42_media=(HOSPITALIZACION_COLUMN, "mean"),
    )
    por_estab["proporcion_semanas"] = por_estab["semanas"] / total
    return por_estab, total


def id42_por_ano(regular: pd.DataFrame) -> pd.DataFrame:
    """Volumen anual de ID42 frente a ID36 y hospitales que lo informan positivo."""
    anual = regular.groupby("ano").agg(
        id36=("atenciones_id36", "sum"), id42=(HOSPITALIZACION_COLUMN, "sum"),
    )
    anual["id42_sobre_id36_pct"] = (anual["id42"] / anual["id36"] * 100).round(2)
    positivos = regular[regular[HOSPITALIZACION_COLUMN] > 0]
    anual["hospitales_con_id42"] = positivos.groupby("ano")["establecimiento_codigo"].nunique()
    return anual.reset_index()


def main() -> None:
    mart = pq.read_table(MART_PATH).to_pandas()
    regular = mart[mart["semana"] != SEMANA_FRAGMENTARIA]
    por_estab, total_semanas = cobertura(regular)
    anual = id42_por_ano(regular)
    ultimo_ano = int(regular["ano"].max())
    reciente = regular[regular["ano"] == ultimo_ano]
    media_reciente = reciente.groupby("establecimiento_codigo")[
        ["atenciones_id36", HOSPITALIZACION_COLUMN]
    ].mean()

    completos = int((por_estab["semanas"] == total_semanas).sum())
    al_95 = int((por_estab["proporcion_semanas"] >= 0.95).sum())
    por_tipo = por_estab.groupby("tipo").agg(
        establecimientos=("semanas", "size"),
        con_todas_las_semanas=("semanas", lambda s: int((s == total_semanas).sum())),
        id36_semanal_medio=("id36_media", "mean"),
    ).reset_index()
    por_tipo["id36_semanal_medio"] = por_tipo["id36_semanal_medio"].map(lambda v: _fmt(v, 1))

    positivos_por_tipo = (
        regular[regular[HOSPITALIZACION_COLUMN] > 0]["tipo_establecimiento_urgencia"]
        .value_counts().to_dict()
    )
    volumen = pd.DataFrame(
        [
            {
                "umbral (promedio semanal)": f">= {_fmt(u)}",
                f"ID36 en {ultimo_ano}": int((media_reciente["atenciones_id36"] >= u).sum()),
                f"ID42 en {ultimo_ano}": int((media_reciente[HOSPITALIZACION_COLUMN] >= u).sum()),
            }
            for u in UMBRALES_VOLUMEN
        ]
    )
    nombres = mart.drop_duplicates("establecimiento_codigo").set_index("establecimiento_codigo")[
        "establecimiento_glosa"
    ]
    top_id42 = (
        media_reciente[HOSPITALIZACION_COLUMN].sort_values(ascending=False).head(10)
        .rename("promedio semanal").to_frame()
        .assign(establecimiento=lambda d: d.index.map(nombres))
        .reset_index()[["establecimiento_codigo", "establecimiento", "promedio semanal"]]
    )
    top_id42["promedio semanal"] = top_id42["promedio semanal"].map(lambda v: _fmt(v, 1))
    incompletos = por_estab[por_estab["semanas"] < total_semanas].sort_values("semanas")
    incompletos_tabla = incompletos.reset_index()[
        ["establecimiento_codigo", "tipo", "semanas", "primera", "ultima"]
    ].assign(establecimiento=lambda d: d["establecimiento_codigo"].map(nombres))
    incompletos_tabla = incompletos_tabla[
        ["establecimiento_codigo", "establecimiento", "tipo", "semanas", "primera", "ultima"]
    ]
    anual_tabla = anual.assign(
        id36=lambda d: d["id36"].map(_fmt), id42=lambda d: d["id42"].map(_fmt),
        id42_sobre_id36_pct=lambda d: d["id42_sobre_id36_pct"].map(lambda v: _fmt(v, 2)),
    ).rename(columns={"id42_sobre_id36_pct": "ID42 / ID36 (%)", "hospitales_con_id42": "hospitales con ID42 > 0"})

    resumen = pd.DataFrame(
        [
            ("filas", len(mart)),
            ("establecimientos", mart["establecimiento_codigo"].nunique()),
            ("semanas_regulares", total_semanas),
            ("establecimientos_con_todas_las_semanas", completos),
            ("establecimientos_con_95pct_o_mas", al_95),
            ("filas_semana_53", int((mart["semana"] == SEMANA_FRAGMENTARIA).sum())),
            ("nulos_en_conteos", int(mart.filter(like="atenciones_id").isna().sum().sum())),
            *[(f"hospitales_con_id42_{int(r.ano)}", int(r.hospitales_con_id42)) for r in anual.itertuples()],
            *[(f"id42_sobre_id36_pct_{int(r.ano)}", float(r.id42_sobre_id36_pct)) for r in anual.itertuples()],
        ],
        columns=["metrica", "valor"],
    )

    lineas = [
        TITULO,
        "",
        "Generado por `scripts/eda_mart_urgencias_establecimiento_weekly.py` (stage "
        "`eda_mart_urgencias_establecimiento_weekly`). No editar a mano. Diccionario: "
        "`reports/dictionary/diccionario_mart_urgencias_establecimiento_weekly.md`.",
        "",
        "## 1. Grano y cobertura",
        "",
        f"- Grano: `establecimiento_codigo` × `ano` × `semana` DEIS. Filas: {_fmt(len(mart))}; "
        f"establecimientos: {mart['establecimiento_codigo'].nunique()}; período "
        f"{int(mart['ano'].min())}-{ultimo_ano}.",
        f"- Grilla regular: {total_semanas} semanas (se excluyen {int((mart['semana'] == SEMANA_FRAGMENTARIA).sum())} "
        "filas de semana 53, fragmentos de pocos días).",
        f"- **{completos} establecimientos reportan todas las semanas** y {al_95} reportan al menos el 95%.",
        f"- Conteos nulos: {int(mart.filter(like='atenciones_id').isna().sum().sum())}. Cuando un "
        "establecimiento reporta una semana publica todas las causas del contrato, con cero si "
        "corresponde; **una semana sin fila es ausencia de reporte y no se imputa**.",
        "",
        _tabla_md(por_tipo.rename(columns={"tipo": "tipo de establecimiento"})),
        "",
        "## 2. Volumen semanal: qué series son modelables",
        "",
        f"Establecimientos según su promedio semanal en {ultimo_ano}. Una serie con menos de una "
        "atención por semana es casi solo ruido; un pronóstico individual sobre ella aporta poco.",
        "",
        _tabla_md(volumen),
        "",
        "## 3. ID42: hospitalizaciones derivadas desde urgencia (F00-F99)",
        "",
        f"- Filas con ID42 positivo por tipo de establecimiento: {positivos_por_tipo}. Los demás "
        "establecimientos publican la fila con cero.",
        "- **Hecho observado:** la proporción ID42 / ID36 sube en los primeros años y se estabiliza "
        "después. **Hipótesis (no verificada):** maduración del registro de la sección 2; con estos "
        "datos no es posible distinguirla de un cambio real en la práctica de hospitalización.",
        "",
        _tabla_md(anual_tabla),
        "",
        f"Hospitales con más ID42 en {ultimo_ano}:",
        "",
        _tabla_md(top_id42),
        "",
        "## 4. Establecimientos con semanas sin reporte",
        "",
        "Ordenados de menor a mayor número de semanas reportadas. La causa de la ausencia "
        "(apertura, cierre o interrupción del reporte) no es determinable con este mart.",
        "",
        _tabla_md(incompletos_tabla) if not incompletos_tabla.empty else "Ninguno.",
        "",
        "## 5. Implicancias para el pronóstico por establecimiento",
        "",
        "- La grilla regular permite reutilizar la construcción del panel del modelo comunal para "
        "los establecimientos con cobertura completa en la ventana de entrenamiento.",
        "- Los establecimientos de bajo volumen no justifican un pronóstico individual; se "
        "evaluará en el benchmark desde qué volumen el modelo supera al baseline.",
        "- ID42 debe modelarse solo sobre hospitales y considerando el cambio de nivel de los "
        "primeros años antes de fijar la ventana de entrenamiento.",
        "",
    ]
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(lineas), encoding="utf-8", newline="\n")
    resumen.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"EDA escrito en {OUTPUT_REPORT.as_posix()}")


if __name__ == "__main__":
    main()
