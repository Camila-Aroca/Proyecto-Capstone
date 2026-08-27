import sys
import pyarrow.parquet as pq
import pandas as pd
from pathlib import Path
from shapely import wkb

sys.stdout.reconfigure(encoding="utf-8")

p = Path("data/raw/censo/Cartografia_censo2024_Pais_Comunal.parquet")
t = pq.read_table(p)
df = t.to_pandas()

print(f"Total filas país: {len(df)}")
print(f"Total columnas: {len(df.columns)}")

rm_df = df[df["COD_REGION"] == 13].copy().sort_values("CUT").reset_index(drop=True)
print(f"\nTotal comunas en RM (COD_REGION == 13): {len(rm_df)}")

# Lista oficial de las 52 comunas de la RM (Chile)
OFICIALES_RM = {
    13101: "SANTIAGO",
    13102: "CERRILLOS",
    13103: "CERRO NAVIA",
    13104: "CONCHALÍ",
    13105: "EL BOSQUE",
    13106: "ESTACIÓN CENTRAL",
    13107: "HUECHURABA",
    13108: "INDEPENDENCIA",
    13109: "LA CISTERNA",
    13110: "LA FLORIDA",
    13111: "LA GRANJA",
    13112: "LA PINTANA",
    13113: "LA REINA",
    13114: "LAS CONDES",
    13115: "LO BARNECHEA",
    13116: "LO ESPEJO",
    13117: "LO PRADO",
    13118: "MACUL",
    13119: "MAIPÚ",
    13120: "ÑUÑOA",
    13121: "PEDRO AGUIRRE CERDA",
    13122: "PEÑALOLÉN",
    13123: "PROVIDENCIA",
    13124: "PUDAHUEL",
    13125: "QUILICURA",
    13126: "QUINTA NORMAL",
    13127: "RECOLETA",
    13128: "RENCA",
    13129: "SAN JOAQUÍN",
    13130: "SAN MIGUEL",
    13131: "SAN RAMÓN",
    13132: "VITACURA",
    13201: "PUENTE ALTO",
    13202: "PIRQUE",
    13203: "SAN JOSÉ DE MAIPO",
    13301: "COLINA",
    13302: "LAMPA",
    13303: "TILTIL",
    13401: "SAN BERNARDO",
    13402: "BUIN",
    13403: "CALERA DE TANGO",
    13404: "PAINE",
    13501: "MELIPILLA",
    13502: "ALHUÉ",
    13503: "CURACAVÍ",
    13504: "MARÍA PINTO",
    13505: "SAN PEDRO",
    13601: "TALAGANTE",
    13602: "EL MONTE",
    13603: "ISLA DE MAIPO",
    13604: "PADRE HURTADO",
    13605: "PEÑAFLOR",
}

found_cuts = set(rm_df["CUT"])
expected_cuts = set(OFICIALES_RM.keys())

missing_cuts = expected_cuts - found_cuts
extra_cuts = found_cuts - expected_cuts

print(f"Comunas esperadas: {len(expected_cuts)}")
print(f"Comunas encontradas en RM: {len(found_cuts)}")
print(f"Comunas faltantes: {len(missing_cuts)}")
print(f"Comunas adicionales no esperadas: {len(extra_cuts)}")

# Validar geometrías
invalid_geom_count = 0
null_geom_count = 0
for idx, wkb_bytes in enumerate(df["SHAPE"]):
    if wkb_bytes is None or len(wkb_bytes) == 0:
        null_geom_count += 1
        continue
    try:
        geom = wkb.loads(wkb_bytes)
        if not geom.is_valid:
            invalid_geom_count += 1
    except Exception:
        invalid_geom_count += 1

print(f"\nGeometrías nulas en todo el país: {null_geom_count}")
print(f"Geometrías inválidas en todo el país: {invalid_geom_count}")

# Generar archivo auxiliar reports/eda/comunas_rm_censo2024.csv
eda_dir = Path("reports/eda")
eda_dir.mkdir(parents=True, exist_ok=True)
csv_out = eda_dir / "comunas_rm_censo2024.csv"

records = []
for cut, nom_oficial in sorted(OFICIALES_RM.items()):
    match = rm_df[rm_df["CUT"] == cut]
    presente = len(match) > 0
    nombre_censo = match["COMUNA"].iloc[0] if presente else None
    provincia = match["PROVINCIA"].iloc[0] if presente else None
    area = float(match["SHAPE_Area"].iloc[0]) if presente else None
    length = float(match["SHAPE_Length"].iloc[0]) if presente else None
    n_reg = len(match)
    
    records.append({
        "codigo_comuna_cut": cut,
        "nombre_comuna_oficial": nom_oficial,
        "nombre_comuna_censo": nombre_censo,
        "provincia": provincia,
        "cantidad_registros_geometricos": n_reg,
        "presente_en_dataset": "Sí" if presente else "No",
        "area_grados2": area,
        "perimetro_grados": length
    })

df_out = pd.DataFrame(records)
df_out.to_csv(csv_out, index=False, encoding="utf-8")
print(f"\nArchivo auxiliar guardado: {csv_out.as_posix()} ({len(df_out)} filas)")

print("\nListado completo de las 52 comunas de la RM encontradas:")
for i, r in df_out.iterrows():
    print(f"{i+1:2d}. CUT {r['codigo_comuna_cut']}: {r['nombre_comuna_censo']} ({r['provincia']}) - Registros: {r['cantidad_registros_geometricos']}")
