"""Inspecciona tablas para extraer cifras exactas del reporte EDA."""

import pandas as pd

t3 = pd.read_csv("data/processed/urgencias/tabla3_demanda_por_comuna.csv")
print("=== TOP 10 COMUNAS DEMANDA GENERAL ===")
print(t3.head(10)[["ranking", "comuna_codigo", "comuna_glosa", "total_2021_2026", "pct_participacion_rm", "establecimientos_reportantes"]].to_string(index=False))

t4 = pd.read_csv("data/processed/urgencias/tabla4_demanda_por_establecimiento.csv")
print("\n=== TOP 10 ESTABLECIMIENTOS DEMANDA GENERAL ===")
print(t4.head(10)[["ranking", "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_maestro", "comuna_glosa", "total_2021_2026", "pct_participacion_rm"]].to_string(index=False))

t5 = pd.read_csv("data/processed/urgencias/tabla5_demanda_por_tipo_establecimiento.csv")
print("\n=== DEMANDA POR TIPO ESTABLECIMIENTO ===")
print(t5.to_string(index=False))

t8 = pd.read_csv("data/processed/urgencias/tabla8_f00_f99_por_comuna.csv")
print("\n=== TOP 10 COMUNAS SALUD MENTAL F00-F99 ===")
print(t8.head(10)[["ranking_volumen_sm", "comuna_codigo", "comuna_glosa", "total_sm_2021_2026", "pct_de_salud_mental_rm", "prop_sm_en_comuna_pct"]].to_string(index=False))

t9 = pd.read_csv("data/processed/urgencias/tabla9_f00_f99_por_establecimiento.csv")
print("\n=== TOP 10 ESTABLECIMIENTOS SALUD MENTAL F00-F99 (VOLUMEN) ===")
print(t9.head(10)[["ranking_volumen_sm", "establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_maestro", "comuna_glosa", "total_sm_2021_2026", "prop_sm_en_estab_pct"]].to_string(index=False))

print("\n=== TOP 10 ESTABLECIMIENTOS SALUD MENTAL F00-F99 (PROPORCIÓN RELATIVA, min 500 atenciones) ===")
print(t9[t9["atenciones_totales_estab"] > 5000].sort_values(by="prop_sm_en_estab_pct", ascending=False).head(10)[["establecimiento_codigo", "establecimiento_glosa", "tipo_establecimiento_maestro", "comuna_glosa", "total_sm_2021_2026", "atenciones_totales_estab", "prop_sm_en_estab_pct"]].to_string(index=False))
