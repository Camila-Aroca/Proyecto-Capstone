"""Script optimizado y reproducible para el perfilado descriptivo de la demanda de urgencias en la RM (2020-2026)."""

import json
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import pyarrow.dataset as ds

sys.stdout.reconfigure(encoding="utf-8")

PROCESSED_DIR = Path("data/processed/urgencias")
ESTAB_PATH = Path("data/processed/establecimientos_rm_clean.parquet")
OUTPUT_TABLES_DIR = Path("data/processed/urgencias")

# 1. Cargar maestro de establecimientos RM enriquecido
df_estab_rm = pd.read_parquet(ESTAB_PATH)
df_estab_rm["establecimiento_codigo"] = df_estab_rm["establecimiento_codigo"].astype(str).str.strip()

estab_meta = df_estab_rm.set_index("establecimiento_codigo")[
    ["establecimiento_glosa", "comuna_codigo", "comuna_glosa", 
     "seremi_salud_glosa_servicio_de_salud_glosa", "tipo_establecimiento_glosa",
     "latitud", "longitud"]
].to_dict("index")

print(f"Maestro de establecimientos RM cargado: {len(df_estab_rm)} centros.")

# 2. Cargar dataset PyArrow completo
files = [PROCESSED_DIR / f"urgencias_rm_{y}.parquet" for y in range(2020, 2027)]
dataset = ds.dataset(files, format="parquet")

cols = ["ano", "fecha", "semana", "comuna_codigo", "comuna_glosa", 
        "establecimiento_codigo", "establecimiento_glosa", "id_causa", "glosa_causa", "total"]

df = dataset.to_table(columns=cols).to_pandas()
df["establecimiento_codigo"] = df["establecimiento_codigo"].astype(str).str.strip()
print(f"Total registros cargados RM: {len(df):,}")

# FASE 0: Resumen estructural por año
print("\n=== FASE 0: INVENTARIO Y ESTRUCTURA POR AÑO ===")
fase0_summary = []
for y in range(2020, 2027):
    df_y = df[df["ano"] == y]
    fase0_summary.append({
        "ano": y,
        "filas": len(df_y),
        "estabs_unicos": df_y["establecimiento_codigo"].nunique(),
        "comunas_unicas": df_y["comuna_codigo"].nunique(),
        "causas_unicas": df_y["id_causa"].nunique(),
        "fecha_min": df_y["fecha"].min(),
        "fecha_max": df_y["fecha"].max(),
        "semanas_min": df_y["semana"].min(),
        "semanas_max": df_y["semana"].max(),
        "total_atenciones_sum_todas_filas": int(df_y["total"].sum())
    })
print(pd.DataFrame(fase0_summary).to_string(index=False))

# FASE 1: Validación del Método de Conteo (ID 1 vs ID 34 vs ID 36)
print("\n=== FASE 1: VALIDACIÓN DEL MÉTODO DE CONTEO ===")
fase1_check = []
for y in range(2020, 2027):
    df_y = df[df["ano"] == y]
    tot_id1 = int(df_y[df_y["id_causa"] == 1]["total"].sum())
    tot_id34 = int(df_y[df_y["id_causa"] == 34]["total"].sum())
    tot_id36 = int(df_y[df_y["id_causa"] == 36]["total"].sum())
    comp_sm = int(df_y[df_y["id_causa"].isin([37, 38, 39, 40, 41])]["total"].sum())
    
    fase1_check.append({
        "ano": y,
        "id1_seccion1_total": tot_id1,
        "id34_total_demanda": tot_id34,
        "id36_total_salud_mental": tot_id36,
        "suma_comp_sm_37_a_41": comp_sm,
        "diff_sm": tot_id36 - comp_sm
    })
print(pd.DataFrame(fase1_check).to_string(index=False))

# FASE 2, 3 & 4: TABLA 1 (Demanda Anual General ID 1) y TABLA 2 (Demanda Semanal)
print("\n=== TABLA 1: DEMANDA ANUAL GENERAL RM (ID 1) ===")
df_id1 = df[df["id_causa"] == 1].copy()
df_id1["fecha_dt"] = pd.to_datetime(df_id1["fecha"], format="%d/%m/%Y")

tabla1 = []
for y in range(2020, 2027):
    df_y = df_id1[df_id1["ano"] == y]
    w_sum = df_y.groupby("semana")["total"].sum()
    d_sum = df_y.groupby("fecha_dt")["total"].sum()
    
    tabla1.append({
        "ano": y,
        "atenciones_totales": int(df_y["total"].sum()),
        "establecimientos_unicos": df_y["establecimiento_codigo"].nunique(),
        "comunas_unicas": df_y["comuna_codigo"].nunique(),
        "semanas_observadas": len(w_sum),
        "dias_observados": len(d_sum),
        "fecha_inicio": df_y["fecha_dt"].min().strftime("%d/%m/%Y"),
        "fecha_termino": df_y["fecha_dt"].max().strftime("%d/%m/%Y"),
        "promedio_semanal": round(float(w_sum.mean()), 1),
        "mediana_semanal": round(float(w_sum.median()), 1),
        "minimo_semanal": int(w_sum.min()),
        "maximo_semanal": int(w_sum.max()),
        "promedio_diario": round(float(d_sum.mean()), 1)
    })
df_t1 = pd.DataFrame(tabla1)
print(df_t1.to_string(index=False))
df_t1.to_csv(OUTPUT_TABLES_DIR / "tabla1_demanda_anual_rm.csv", index=False, encoding="utf-8")

# TABLA 2: Demanda Semanal por Año
weekly_pivot = df_id1.pivot_table(
    index="semana",
    columns="ano",
    values="total",
    aggfunc="sum",
    fill_value=0
)
weekly_pivot.to_csv(OUTPUT_TABLES_DIR / "tabla2_demanda_semanal_rm.csv", encoding="utf-8")

# FASE 5: TABLA 3 - Demanda por Comuna (2021-2026)
print("\n=== TABLA 3: DEMANDA GENERAL POR COMUNA (2021-2026) ===")
df_id1_p = df_id1[df_id1["ano"].between(2021, 2026)]

comuna_piv = df_id1_p.pivot_table(
    index=["comuna_codigo", "comuna_glosa"],
    columns="ano",
    values="total",
    aggfunc="sum",
    fill_value=0
).reset_index()

comuna_piv["total_2021_2026"] = comuna_piv[[2021, 2022, 2023, 2024, 2025, 2026]].sum(axis=1)
comuna_piv["total_2021_2025_completo"] = comuna_piv[[2021, 2022, 2023, 2024, 2025]].sum(axis=1)

estab_counts = df_id1_p.groupby("comuna_codigo")["establecimiento_codigo"].nunique().to_dict()
comuna_piv["establecimientos_reportantes"] = comuna_piv["comuna_codigo"].map(estab_counts)

tot_gen_period = comuna_piv["total_2021_2026"].sum()
comuna_piv["pct_participacion_rm"] = round(comuna_piv["total_2021_2026"] / tot_gen_period * 100, 2)
comuna_piv = comuna_piv.sort_values(by="total_2021_2026", ascending=False).reset_index(drop=True)
comuna_piv["ranking"] = comuna_piv.index + 1

print(comuna_piv[["ranking", "comuna_codigo", "comuna_glosa", "total_2021_2026", "pct_participacion_rm", "establecimientos_reportantes"]].head(10))
comuna_piv.to_csv(OUTPUT_TABLES_DIR / "tabla3_demanda_por_comuna.csv", index=False, encoding="utf-8")

# FASE 6 & 7: TABLA 4 (Establecimientos) y TABLA 5 (Tipos)
print("\n=== TABLA 4 & 5: ESTABLECIMIENTOS Y TIPOLOGÍA ===")
estab_piv = df_id1_p.pivot_table(
    index=["establecimiento_codigo", "establecimiento_glosa", "comuna_codigo", "comuna_glosa"],
    columns="ano",
    values="total",
    aggfunc="sum",
    fill_value=0
).reset_index()

estab_piv["total_2021_2026"] = estab_piv[[2021, 2022, 2023, 2024, 2025, 2026]].sum(axis=1)
estab_piv["tipo_establecimiento_maestro"] = estab_piv["establecimiento_codigo"].apply(
    lambda c: estab_meta.get(str(c).strip(), {}).get("tipo_establecimiento_glosa", "No encontrado")
)
estab_piv["servicio_salud"] = estab_piv["establecimiento_codigo"].apply(
    lambda c: estab_meta.get(str(c).strip(), {}).get("seremi_salud_glosa_servicio_de_salud_glosa", "No encontrado")
)
estab_piv["latitud"] = estab_piv["establecimiento_codigo"].apply(
    lambda c: estab_meta.get(str(c).strip(), {}).get("latitud", None)
)
estab_piv["longitud"] = estab_piv["establecimiento_codigo"].apply(
    lambda c: estab_meta.get(str(c).strip(), {}).get("longitud", None)
)
estab_piv["pct_participacion_rm"] = round(estab_piv["total_2021_2026"] / tot_gen_period * 100, 2)
estab_piv = estab_piv.sort_values(by="total_2021_2026", ascending=False).reset_index(drop=True)
estab_piv["ranking"] = estab_piv.index + 1

print("Top 10 Establecimientos por Demanda:")
print(estab_piv[["ranking", "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_maestro", "comuna_glosa", "total_2021_2026", "pct_participacion_rm"]].head(10))
estab_piv.to_csv(OUTPUT_TABLES_DIR / "tabla4_demanda_por_establecimiento.csv", index=False, encoding="utf-8")

# TABLA 5: Tipos de Establecimiento
tipo_piv = estab_piv.groupby("tipo_establecimiento_maestro").agg(
    establecimientos=("establecimiento_codigo", "count"),
    atenciones_total=("total_2021_2026", "sum")
).reset_index()
tipo_piv["pct_demanda_rm"] = round(tipo_piv["atenciones_total"] / tot_gen_period * 100, 2)
tipo_piv["promedio_por_establecimiento"] = round(tipo_piv["atenciones_total"] / tipo_piv["establecimientos"], 1)
tipo_piv = tipo_piv.sort_values(by="atenciones_total", ascending=False).reset_index(drop=True)
print("\nDemanda por Tipo de Establecimiento:")
print(tipo_piv)
tipo_piv.to_csv(OUTPUT_TABLES_DIR / "tabla5_demanda_por_tipo_establecimiento.csv", index=False, encoding="utf-8")

# FASE 8, 9 & 10: SALUD MENTAL F00-F99 (ID 36)
print("\n=== TABLA 6 & 7: DEMANDA SALUD MENTAL F00-F99 ANUAL Y PARTICIPACIÓN ===")
df_sm36 = df[df["id_causa"] == 36].copy()
df_sm36["fecha_dt"] = pd.to_datetime(df_sm36["fecha"], format="%d/%m/%Y")

tabla6 = []
for y in range(2020, 2027):
    df_y_sm = df_sm36[df_sm36["ano"] == y]
    df_y_tot = df_id1[df_id1["ano"] == y]
    
    tot_sm = int(df_y_sm["total"].sum())
    tot_gen = int(df_y_tot["total"].sum())
    pct_sm = round(tot_sm / tot_gen * 100, 2) if tot_gen > 0 else 0
    w_sum = df_y_sm.groupby("semana")["total"].sum()
    
    tabla6.append({
        "ano": y,
        "atenciones_totales_urgencia": tot_gen,
        "atenciones_f00_f99": tot_sm,
        "pct_f00_f99_sobre_total": pct_sm,
        "promedio_semanal_sm": round(float(w_sum.mean()), 1),
        "mediana_semanal_sm": round(float(w_sum.median()), 1),
        "minimo_semanal_sm": int(w_sum.min()),
        "maximo_semanal_sm": int(w_sum.max()),
        "establecimientos_con_sm": df_y_sm[df_y_sm["total"] > 0]["establecimiento_codigo"].nunique(),
        "comunas_con_sm": df_y_sm[df_y_sm["total"] > 0]["comuna_codigo"].nunique()
    })
df_t6 = pd.DataFrame(tabla6)
print(df_t6.to_string(index=False))
df_t6.to_csv(OUTPUT_TABLES_DIR / "tabla6_demanda_f00_f99_anual.csv", index=False, encoding="utf-8")

# TABLA 8: F00-F99 por Comuna
print("\n=== TABLA 8: F00-F99 POR COMUNA (2021-2026) ===")
df_sm36_p = df_sm36[df_sm36["ano"].between(2021, 2026)]

comuna_sm_piv = df_sm36_p.pivot_table(
    index=["comuna_codigo", "comuna_glosa"],
    columns="ano",
    values="total",
    aggfunc="sum",
    fill_value=0
).reset_index()

comuna_sm_piv["total_sm_2021_2026"] = comuna_sm_piv[[2021, 2022, 2023, 2024, 2025, 2026]].sum(axis=1)

comuna_sm_piv = comuna_sm_piv.merge(
    comuna_piv[["comuna_codigo", "total_2021_2026", "establecimientos_reportantes"]],
    on="comuna_codigo",
    how="left"
).rename(columns={"total_2021_2026": "atenciones_totales_comuna"})

tot_sm_period = comuna_sm_piv["total_sm_2021_2026"].sum()
comuna_sm_piv["pct_de_salud_mental_rm"] = round(comuna_sm_piv["total_sm_2021_2026"] / tot_sm_period * 100, 2)
comuna_sm_piv["prop_sm_en_comuna_pct"] = round(comuna_sm_piv["total_sm_2021_2026"] / comuna_sm_piv["atenciones_totales_comuna"] * 100, 2)
comuna_sm_piv = comuna_sm_piv.sort_values(by="total_sm_2021_2026", ascending=False).reset_index(drop=True)
comuna_sm_piv["ranking_volumen_sm"] = comuna_sm_piv.index + 1

print(comuna_sm_piv[["ranking_volumen_sm", "comuna_codigo", "comuna_glosa", "total_sm_2021_2026", "pct_de_salud_mental_rm", "prop_sm_en_comuna_pct"]].head(10))
comuna_sm_piv.to_csv(OUTPUT_TABLES_DIR / "tabla8_f00_f99_por_comuna.csv", index=False, encoding="utf-8")

# TABLA 9: F00-F99 por Establecimiento
print("\n=== TABLA 9: F00-F99 POR ESTABLECIMIENTO ===")
estab_sm_piv = df_sm36_p.pivot_table(
    index=["establecimiento_codigo", "establecimiento_glosa", "comuna_codigo", "comuna_glosa"],
    columns="ano",
    values="total",
    aggfunc="sum",
    fill_value=0
).reset_index()

estab_sm_piv["total_sm_2021_2026"] = estab_sm_piv[[2021, 2022, 2023, 2024, 2025, 2026]].sum(axis=1)
estab_sm_piv = estab_sm_piv.merge(
    estab_piv[["establecimiento_codigo", "total_2021_2026", "tipo_establecimiento_maestro", "servicio_salud", "latitud", "longitud"]],
    on="establecimiento_codigo",
    how="left"
).rename(columns={"total_2021_2026": "atenciones_totales_estab"})

estab_sm_piv["pct_de_salud_mental_rm"] = round(estab_sm_piv["total_sm_2021_2026"] / tot_sm_period * 100, 2)
estab_sm_piv["prop_sm_en_estab_pct"] = round(estab_sm_piv["total_sm_2021_2026"] / estab_sm_piv["atenciones_totales_estab"] * 100, 2)
estab_sm_piv = estab_sm_piv.sort_values(by="total_sm_2021_2026", ascending=False).reset_index(drop=True)
estab_sm_piv["ranking_volumen_sm"] = estab_sm_piv.index + 1

print("Top 10 Establecimientos por Volumen de Salud Mental:")
print(estab_sm_piv[["ranking_volumen_sm", "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_maestro", "comuna_glosa", "total_sm_2021_2026", "prop_sm_en_estab_pct"]].head(10))
estab_sm_piv.to_csv(OUTPUT_TABLES_DIR / "tabla9_f00_f99_por_establecimiento.csv", index=False, encoding="utf-8")

# FASE 11: TABLA 10 - Desagregación de Causas de Salud Mental
print("\n=== TABLA 10: DESAGREGACIÓN DE CAUSAS DE SALUD MENTAL ===")
sm_ids = [36, 38, 39, 40, 41, 37, 35, 42]
df_sm_all = df[df["id_causa"].isin(sm_ids) & df["ano"].between(2021, 2026)]

t10 = df_sm_all.pivot_table(
    index="id_causa",
    columns="ano",
    values="total",
    aggfunc="sum",
    fill_value=0
).reset_index()

map_glosa_std = {
    36: "TOTAL CAUSAS DE TRASTORNOS MENTALES (F00-F99) [Macro-agregador]",
    38: "Trastornos debidos al uso de sustancias psicoactivas (F10-F19)",
    39: "Trastornos del Humor (Afectivos) (F30-F39)",
    40: "Trastornos neuróticos, estrés y somatomorfos (F40-F48)",
    41: "Otros trastornos mentales no contenidos en categorías anteriores",
    37: "Ideación Suicida (R45.8) [Síntoma / Signo]",
    35: "Lesiones autoinfligidas intencionalmente (X60-X84) [Causa Externa]",
    42: "Hospitalizaciones derivadas por trastornos mentales (F00-F99) [Sección 2]"
}

t10["glosa_estandar"] = t10["id_causa"].map(map_glosa_std)
t10["total_2021_2026"] = t10[[2021, 2022, 2023, 2024, 2025, 2026]].sum(axis=1)
t10["pct_sobre_id36"] = round(t10["total_2021_2026"] / tot_sm_period * 100, 2)
print(t10[["id_causa", "glosa_estandar", "total_2021_2026", "pct_sobre_id36"]].to_string(index=False))
t10.to_csv(OUTPUT_TABLES_DIR / "tabla10_desagregacion_salud_mental.csv", index=False, encoding="utf-8")

# FASE 12: TABLA 12 - Controles de Consistencia y Doble Conteo
print("\n=== TABLA 12: CONTROLES DE CONSISTENCIA Y DOBLE CONTEO ===")
check_results = []
for y in range(2021, 2027):
    df_y = df[df["ano"] == y]
    
    t_id1 = df_y[df_y["id_causa"] == 1]["total"].sum()
    s_weeks = df_y[df_y["id_causa"] == 1].groupby("semana")["total"].sum().sum()
    s_comunas = df_y[df_y["id_causa"] == 1].groupby("comuna_codigo")["total"].sum().sum()
    s_estabs = df_y[df_y["id_causa"] == 1].groupby("establecimiento_codigo")["total"].sum().sum()
    t_id36 = df_y[df_y["id_causa"] == 36]["total"].sum()
    s_comp_sm = df_y[df_y["id_causa"].isin([37, 38, 39, 40, 41])]["total"].sum()
    
    check_results.append({
        "ano": y,
        "total_id1": int(t_id1),
        "suma_semanas_id1": int(s_weeks),
        "diff_semanas": int(t_id1 - s_weeks),
        "suma_comunas_id1": int(s_comunas),
        "diff_comunas": int(t_id1 - s_comunas),
        "suma_estabs_id1": int(s_estabs),
        "diff_estabs": int(t_id1 - s_estabs),
        "total_sm_id36": int(t_id36),
        "suma_comp_sm": int(s_comp_sm),
        "diff_sm": int(t_id36 - s_comp_sm)
    })
df_t12 = pd.DataFrame(check_results)
print(df_t12.to_string(index=False))
df_t12.to_csv(OUTPUT_TABLES_DIR / "tabla12_controles_consistencia.csv", index=False, encoding="utf-8")

# FASE 13: TABLA 11 - Cobertura de Establecimientos contra Maestro
print("\n=== TABLA 11: COBERTURA DE ESTABLECIMIENTOS CONTRA MAESTRO ===")
estab_cods_maestro = set(df_estab_rm["establecimiento_codigo"].astype(str).str.strip())

t11_rows = []
for y in range(2020, 2027):
    df_y = df[df["ano"] == y]
    unique_estabs = df_y["establecimiento_codigo"].astype(str).unique()
    found = [c for c in unique_estabs if c in estab_cods_maestro]
    not_found = [c for c in unique_estabs if c not in estab_cods_maestro]
    
    coords_valid = [c for c in found if pd.notna(estab_meta.get(c, {}).get("latitud"))]
    no_coords = [c for c in found if pd.isna(estab_meta.get(c, {}).get("latitud"))]
    
    t11_rows.append({
        "ano": y,
        "estabs_reportantes": len(unique_estabs),
        "encontrados_maestro": len(found),
        "no_encontrados": len(not_found),
        "pct_cobertura": round(len(found) / len(unique_estabs) * 100, 2),
        "con_coordenadas": len(coords_valid),
        "sin_coordenadas": len(no_coords)
    })
df_t11 = pd.DataFrame(t11_rows)
print(df_t11.to_string(index=False))
df_t11.to_csv(OUTPUT_TABLES_DIR / "tabla11_cobertura_maestro.csv", index=False, encoding="utf-8")

print("\n¡Ejecución completada con éxito!")
