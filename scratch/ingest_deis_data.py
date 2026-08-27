"""Script de descarga, extracción e inspección de datos RAW DEIS-MINSAL (Urgencias 2020-2026 y Egresos 2020-2025)."""

import json
from pathlib import Path
import ssl
import sys
import urllib.request
import zipfile

# Configurar salida en UTF-8
sys.stdout.reconfigure(encoding="utf-8")

URGENCIAS_CONFIG = [
    {"year": 2020, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2020.zip"},
    {"year": 2021, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2021.zip"},
    {"year": 2022, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2022.zip"},
    {"year": 2023, "url": "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2023.zip"},
    {"year": 2024, "url": "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2024.zip"},
    {"year": 2025, "url": "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2025.zip"},
    {"year": 2026, "url": "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2026.zip"},
]

EGRESOS_CONFIG = [
    {"year": 2020, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_2020.zip"},
    {"year": 2021, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_2021.zip"},
    {"year": 2022, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_2022.zip"},
    {"year": 2023, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_2023.zip"},
    {"year": 2024, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_2024.zip"},
    {"year": 2025, "url": "https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_2025.zip"},
]

DEST_URGENCIAS = Path("data/raw/urgencias")
DEST_EGRESOS = Path("data/raw/egresos")

# Contexto SSL seguro pero resiliente
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def download_and_extract_source(source_name: str, config_list: list, dest_dir: Path):
    dest_dir.mkdir(parents=True, exist_ok=True)
    results = []

    print(f"\n{'='*70}\nPROCESANDO FUENTE: {source_name.upper()} -> {dest_dir.as_posix()}\n{'='*70}")

    for item in config_list:
        year = item["year"]
        url = item["url"]
        zip_filename = url.split("/")[-1]
        zip_path = dest_dir / zip_filename

        print(f"\n--- [{year}] {zip_filename} ---")
        print(f"URL: {url}")

        # 1. Descarga si no existe
        if not zip_path.exists() or zip_path.stat().st_size == 0:
            print(f"Descargando {zip_filename}...")
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, context=ssl_context) as resp, open(zip_path, "wb") as out_file:
                    total_bytes = int(resp.headers.get("content-length", 0))
                    downloaded = 0
                    chunk_size = 1024 * 1024 * 5
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes > 0:
                            print(f"  Progreso: {downloaded:,} / {total_bytes:,} bytes ({downloaded/total_bytes*100:.1f}%)")
                print(f"Descarga completada: {zip_path.as_posix()} ({zip_path.stat().st_size:,} bytes)")
            except Exception as e:
                print(f"ERROR al descargar {url}: {e}")
                results.append({
                    "year": year,
                    "zip": zip_filename,
                    "zip_valido": False,
                    "error": str(e),
                    "url": url,
                    "archivos_extraidos": [],
                    "datos": [],
                    "diccionarios": [],
                    "tiene_diccionario": "No",
                    "nombre_diccionario": "Error en descarga"
                })
                continue
        else:
            print(f"Archivo ZIP ya existe en destino: {zip_path.as_posix()} ({zip_path.stat().st_size:,} bytes)")

        # 2. Validar ZIP e inspeccionar contenido
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                # Comprobar integridad del zip
                bad_file = z.testzip()
                if bad_file:
                    raise zipfile.BadZipFile(f"Archivo corrupto en zip: {bad_file}")

                infolist = z.infolist()
                extracted_files = []
                data_files = []
                dict_files = []

                print(f"Extrayendo {len(infolist)} archivo(s)...")
                for member in infolist:
                    z.extract(member, dest_dir)
                    extracted_path = dest_dir / member.filename
                    extracted_files.append({
                        "nombre": member.filename,
                        "tamano_bytes": member.file_size,
                        "extension": Path(member.filename).suffix.lower()
                    })

                    # Clasificar datos vs diccionario
                    filename_upper = member.filename.upper()
                    if "DICCIONARIO" in filename_upper or "METADATA" in filename_upper or member.filename.lower().endswith(".xlsx"):
                        dict_files.append(member.filename)
                    else:
                        data_files.append(member.filename)

                has_dict = len(dict_files) > 0
                dict_name = ", ".join(dict_files) if has_dict else "No contiene diccionario dentro del ZIP."

                results.append({
                    "year": year,
                    "zip": zip_filename,
                    "zip_valido": True,
                    "tamano_zip": zip_path.stat().st_size,
                    "archivos_extraidos": extracted_files,
                    "datos": data_files,
                    "diccionarios": dict_files,
                    "tiene_diccionario": "Sí" if has_dict else "No",
                    "nombre_diccionario": dict_name
                })
                print(f"  Datos extraídos: {data_files}")
                print(f"  Diccionario: {dict_name}")

        except Exception as e:
            print(f"ERROR al validar/extraer ZIP {zip_path}: {e}")
            results.append({
                "year": year,
                "zip": zip_filename,
                "zip_valido": False,
                "error": str(e),
                "url": url,
                "archivos_extraidos": [],
                "datos": [],
                "diccionarios": [],
                "tiene_diccionario": "No",
                "nombre_diccionario": f"Error: {e}"
            })

    return results


def main():
    urgencias_res = download_and_extract_source("Atenciones de Urgencia", URGENCIAS_CONFIG, DEST_URGENCIAS)
    egresos_res = download_and_extract_source("Egresos Hospitalarios", EGRESOS_CONFIG, DEST_EGRESOS)

    summary = {
        "urgencias": urgencias_res,
        "egresos": egresos_res
    }

    with open("scratch/deis_ingest_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n\nProceso de descarga y extracción finalizado. Resumen guardado en scratch/deis_ingest_summary.json")


if __name__ == "__main__":
    main()
