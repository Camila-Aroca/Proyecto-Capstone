"""Script detallado para clasificar y auditar todas las causas de urgencias 2020-2026."""

from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")

PROCESSED_DIR = Path("data/processed/urgencias")

# Cargar todos los datos
dfs = []
for year in range(2020, 2027):
    p = PROCESSED_DIR / f"urgencias_rm_{year}.parquet"
    df = pq.read_table(p, columns=["ano", "id_causa", "glosa_causa", "total"]).to_pandas()
    dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# Resumen por id_causa
grp = df_all.groupby(["id_causa", "glosa_causa"], as_index=False)["total"].sum()

# Agrupar por id_causa combinando posibles glosas distintas entre años
id_summary = df_all.groupby("id_causa").agg(
    glosas=("glosa_causa", lambda x: list(x.unique())),
    total_periodo=("total", "sum")
).reset_index()

print("=== RESUMEN POR ID_CAUSA (1 al 43) ===")
for _, r in id_summary.iterrows():
    print(f"ID {r['id_causa']:2d} | Glosas: {r['glosas']} | Total: {r['total_periodo']:,}")

# Calcular el total de atenciones generales vs salud mental por año
print("\n=== ATENCIONES DE URGENCIA: TOTALES Y SALUD MENTAL POR AÑO ===")
annual_stats = []
for year in range(2020, 2027):
    df_y = df_all[df_all["ano"] == year]
    
    # Total demanda (ID 1 o ID 34)
    tot_s1 = df_y[df_y["id_causa"] == 1]["total"].sum()
    tot_demanda = df_y[df_y["id_causa"] == 34]["total"].sum()
    
    # Salud Mental Total (ID 36)
    tot_sm_36 = df_y[df_y["id_causa"] == 36]["total"].sum()
    
    # Subcausas SM (37, 38, 39, 40, 41)
    tot_37 = df_y[df_y["id_causa"] == 37]["total"].sum()
    tot_38 = df_y[df_y["id_causa"] == 38]["total"].sum()
    tot_39 = df_y[df_y["id_causa"] == 39]["total"].sum()
    tot_40 = df_y[df_y["id_causa"] == 40]["total"].sum()
    tot_41 = df_y[df_y["id_causa"] == 41]["total"].sum()
    
    # Lesiones autoinfligidas (ID 35)
    tot_35 = df_y[df_y["id_causa"] == 35]["total"].sum()
    
    # Hospitalizaciones SM (ID 42)
    tot_42 = df_y[df_y["id_causa"] == 42]["total"].sum()
    
    # Porcentaje SM sobre Total Sección 1 (ID 1)
    pct_sm = (tot_sm_36 / tot_s1 * 100) if tot_s1 > 0 else 0
    
    annual_stats.append({
        "ano": year,
        "total_atenciones_seccion_1": int(tot_s1),
        "total_demanda": int(tot_demanda),
        "total_sm_f00_f99_id36": int(tot_sm_36),
        "pct_sm_sobre_total": round(pct_sm, 2),
        "id37_ideacion_suicida": int(tot_37),
        "id38_sustancias_f10_f19": int(tot_38),
        "id39_afectivos_f30_f39": int(tot_39),
        "id40_estres_ansiedad_f40_f48": int(tot_40),
        "id41_otros_trastornos": int(tot_41),
        "id35_lesiones_autoinfligidas_x60_x84": int(tot_35),
        "id42_hospitalizaciones_sm": int(tot_42),
    })

df_annual_stats = pd.DataFrame(annual_stats)
print(df_annual_stats.to_string(index=False))

# Guardar en json
import json
with open("scratch/causas_annual_stats.json", "w", encoding="utf-8") as out:
    json.dump(annual_stats, out, indent=2, ensure_ascii=False)
