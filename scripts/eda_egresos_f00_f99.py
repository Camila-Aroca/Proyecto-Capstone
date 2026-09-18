"""EDA reproducible de `egresos_f00_f99_nacional_2020_2025`.

Script de solo lectura: no modifica el dataset ni genera outputs canónicos
del pipeline. Calcula las cifras citadas en
`reports/hospitalization/eda_egresos_f00_f99.md` y en
`reports/dictionary/diccionario_egresos_f00_f99_nacional.md`, y escribe una
tabla resumen de apoyo en
`reports/hospitalization/eda_egresos_f00_f99_resumen.csv`.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")

DATASET_PATH = Path("data/processed/egresos/egresos_f00_f99_nacional_2020_2025.parquet")
CATALOG_PATH = Path("data/processed/egresos/catalogo_cie10_f00_f99.csv")
OUTPUT_SUMMARY = Path("reports/hospitalization/eda_egresos_f00_f99_resumen.csv")


def main() -> None:
    df = pq.read_table(DATASET_PATH).to_pandas()
    catalog = pd.read_csv(CATALOG_PATH)

    print("=== Forma del dataset ===")
    print(f"{df.shape[0]:,} filas x {df.shape[1]} columnas (nacional, 2020-2025)")

    print("\n=== Registros por año (nacional) ===")
    por_ano = df.groupby("ano_egreso").size()
    print(por_ano)

    print("\n=== Cobertura RM vs nacional (residente_rm) ===")
    print(df["residente_rm"].value_counts(dropna=False))
    rm = df[df["residente_rm"] == True]
    por_ano_rm = rm.groupby("ano_egreso").size()
    print("\nRegistros RM por año:")
    print(por_ano_rm)
    print("\n% RM sobre nacional por año:")
    print((por_ano_rm / por_ano * 100).round(2))

    print("\n=== dias_estada: distribución (nacional) ===")
    print(df["dias_estada"].describe())
    print("dias_estada, distribución RM:")
    print(rm["dias_estada"].describe())
    print("percentil 99 nacional:", df["dias_estada"].quantile(0.99))
    print("filas con dias_estada > 365 (nacional):", int((df["dias_estada"] > 365).sum()))

    print("\n=== sexo (nacional, por año) ===")
    print(pd.crosstab(df["ano_egreso"], df["sexo"]))

    print("\n=== grupo_edad: value_counts (nacional) ===")
    print(df["grupo_edad"].value_counts())
    print(
        "\nAviso: 2021 usa un esquema de grupo_edad distinto (quinquenal/fino) "
        "al resto de los años (decenal); no son directamente comparables."
    )

    print("\n=== previsión (glosa_prevision, nacional) ===")
    print(df["glosa_prevision"].value_counts(dropna=False))

    print("\n=== pertenencia_establecimiento_salud / SNSS (nacional) ===")
    print(df["pertenencia_establecimiento_salud"].value_counts(dropna=False))
    print("\npor año:")
    print(pd.crosstab(df["ano_egreso"], df["pertenencia_establecimiento_salud"]))

    print("\n=== condicion_egreso (nacional) ===")
    print(df["condicion_egreso"].value_counts(dropna=False))

    print("\n=== Diagnósticos principales (diag1), top 15 subcategorías ===")
    diag_counts = df["diag1"].value_counts().head(15)
    diag_glosas = catalog.set_index("CODIGO SUBCATEGORIA")["GLOSA SUBCATEGORIA"]
    for code, count in diag_counts.items():
        print(f"{code} ({diag_glosas.get(code, '¿?')}) : {count:,}")

    print("\n=== Grupos CIE-10 (F00-F09 ... F99), participación ===")
    catalog_map = catalog.set_index("CODIGO SUBCATEGORIA")["CODIGO GRUPO"]
    df["grupo_cie10"] = df["diag1"].map(catalog_map)
    grupo_glosa = catalog.drop_duplicates("CODIGO GRUPO").set_index("CODIGO GRUPO")["GLOSA GRUPO"]
    grupo_counts = df["grupo_cie10"].value_counts()
    for grupo, count in grupo_counts.items():
        print(f"{grupo} ({grupo_glosa.get(grupo, '¿?')}) : {count:,} ({count / len(df) * 100:.2f}%)")

    print("\n=== Nulos por columna ===")
    print(df.isna().sum())

    print("\n=== diag2 (causa externa) ===")
    print("vacío ('') en F00-F99:", (df["diag2"] == "").sum(), "de", len(df))

    print("\n=== Duplicados exactos (todas las columnas salvo residente_rm derivada) ===")
    base_cols = [c for c in df.columns if c != "residente_rm"]
    dup_mask = df.duplicated(subset=base_cols, keep=False)
    print(f"filas que participan en algún duplicado exacto: {dup_mask.sum():,} ({dup_mask.mean() * 100:.2f}%)")
    print(f"grupos de duplicados únicos: {df[dup_mask].drop_duplicates(subset=base_cols).shape[0]:,}")
    print(
        "Nota: no se deduplica (dataset disociado sin identificador de paciente); "
        "coincidencias exactas son esperables en una población grande."
    )

    print("\n=== interv_q / proced / error: disponibilidad por año ===")
    for col in ("interv_q", "proced", "error"):
        disponibles = df.groupby("ano_egreso")[col].apply(lambda s: int(s.notna().sum()))
        print(f"{col}:\n{disponibles}")

    summary = pd.DataFrame(
        {
            "metrica": [
                "filas_totales", "filas_rm", "anos_cubiertos",
                "dias_estada_mediana_nacional", "dias_estada_max_nacional",
                "pct_snss_nacional", "pct_duplicados_exactos",
            ],
            "valor": [
                len(df), int((df["residente_rm"] == True).sum()), df["ano_egreso"].nunique(),
                float(df["dias_estada"].median()), int(df["dias_estada"].max()),
                round(
                    (df["pertenencia_establecimiento_salud"]
                     == "Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS").mean() * 100,
                    2,
                ),
                round(dup_mask.mean() * 100, 2),
            ],
        }
    )
    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\nResumen escrito en {OUTPUT_SUMMARY.as_posix()}")


if __name__ == "__main__":
    main()
