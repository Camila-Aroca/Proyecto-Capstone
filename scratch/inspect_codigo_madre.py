"""Inspecciona establecimiento_codigo_madre y Servicios de Salud en la RM."""

from pathlib import Path
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

df_rm = pd.read_csv("data/processed/establecimientos_rm_clean.csv", dtype=str)

# 1. Servicios de Salud en la RM
print("=== SERVICIOS DE SALUD EN LA RM ===")
ss_counts = df_rm["seremi_salud_glosa_servicio_de_salud_glosa"].value_counts()
print(ss_counts)

# 2. Establecimiento Código Madre en SAPU, SAR y Hospitales
print("\n=== ESTABLECIMIENTO CÓDIGO MADRE EN SAPU / SAR ===")
sapu_sar = df_rm[df_rm["tipo_establecimiento_glosa"].isin([
    "Servicio de Atención Primaria de Urgencia (SAPU)",
    "Servicio de Atención Primaria de Urgencia de Alta Resolutividad (SAR)",
    "Servicio de Urgencia Rural (SUR)"
])]

print(f"Total SAPU / SAR / SUR: {len(sapu_sar)}")
print(f"Con código madre: {sapu_sar['establecimiento_codigo_madre_nuevo'].notna().sum()}")

# Muestra de a qué tipo de centro apunta el código madre
map_estab = df_rm.set_index("establecimiento_codigo")["tipo_establecimiento_glosa"].to_dict()
map_estab_name = df_rm.set_index("establecimiento_codigo")["establecimiento_glosa"].to_dict()

sample_links = []
for idx, r in sapu_sar.head(15).iterrows():
    cod_madre = r["establecimiento_codigo_madre_nuevo"]
    tipo_madre = map_estab.get(cod_madre, "No encontrado en catálogo RM")
    nom_madre = map_estab_name.get(cod_madre, "No encontrado")
    sample_links.append({
        "urgencia_codigo": r["establecimiento_codigo"],
        "urgencia_nombre": r["establecimiento_glosa"],
        "urgencia_tipo": r["tipo_establecimiento_glosa"],
        "madre_codigo": cod_madre,
        "madre_nombre": nom_madre,
        "madre_tipo": tipo_madre
    })

print(pd.DataFrame(sample_links).to_string(index=False))

# 3. ¿Existe relación explícita hacia Hospital de Referencia?
print("\n=== INVESTIGACIÓN DE RELACIÓN HACIA HOSPITAL DE REFERENCIA ===")
hosp_cods = set(df_rm[df_rm["tipo_establecimiento_glosa"] == "Hospital"]["establecimiento_codigo"])
print(f"Total hospitales en RM: {len(hosp_cods)}")
madres_hosp = sapu_sar[sapu_sar["establecimiento_codigo_madre_nuevo"].isin(hosp_cods)]
print(f"SAPU/SAR cuyo código madre apunta a un hospital: {len(madres_hosp)} de {len(sapu_sar)}")

madres_cesfam = sapu_sar[sapu_sar["establecimiento_codigo_madre_nuevo"].isin(
    set(df_rm[df_rm["tipo_establecimiento_glosa"].str.contains("CESFAM|Centro de Salud", na=False)]["establecimiento_codigo"])
)]
print(f"SAPU/SAR cuyo código madre apunta a un CESFAM / Centro de Salud: {len(madres_cesfam)} de {len(sapu_sar)}")

