"""Script de descarga, extracción e inspección de datos RAW DEIS-MINSAL (Urgencias 2020-2026 y Egresos 2020-2025)."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import ssl
import sys
import urllib.request
import zipfile

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

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def update_manifest(source_url, zip_path, year):
    manifest_path = Path("data/raw/provenance_manifest.json")
    manifest = []
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
    # Calculate SHA256
    sha256_hash = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    entry = {
        "source_url": source_url,
        "filename": zip_path.name,
        "year": year,
        "downloaded_at": datetime.datetime.now().isoformat(),
        "file_size": zip_path.stat().st_size,
        "sha256": sha256_hash.hexdigest()
    }
    
    # Update if exists, else append
    for i, e in enumerate(manifest):
        if e["filename"] == entry["filename"]:
            manifest[i] = entry
            break
    else:
        manifest.append(entry)
        
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def download_and_extract_source(source_name: str, config_list: list, dest_dir: Path, force: bool = False):
    dest_dir.mkdir(parents=True, exist_ok=True)
    results = []

    print(f"\n{'='*70}\nPROCESANDO FUENTE: {source_name.upper()} -> {dest_dir.as_posix()}\n{'='*70}")

    for item in config_list:
        year = item["year"]
        url = item["url"]
        zip_filename = url.split("/")[-1]
        zip_path = dest_dir / zip_filename

        print(f"\n--- [{year}] {zip_filename} ---")
        
        if force or not zip_path.exists() or zip_path.stat().st_size == 0:
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
                print(f"Descarga completada: {zip_path.as_posix()} ({zip_path.stat().st_size:,} bytes)")
                update_manifest(url, zip_path, year)
            except Exception as e:
                print(f"ERROR al descargar {url}: {e}")
                results.append({"year": year, "zip_valido": False, "error": str(e)})
                continue
        else:
            print(f"Archivo ZIP ya existe en destino: {zip_path.as_posix()} ({zip_path.stat().st_size:,} bytes)")

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                bad_file = z.testzip()
                if bad_file:
                    raise zipfile.BadZipFile(f"Archivo corrupto en zip: {bad_file}")

                infolist = z.infolist()
                for member in infolist:
                    # Skip extraction if the file already exists and has size > 0
                    extracted_path = dest_dir / member.filename
                    if force or not extracted_path.exists() or extracted_path.stat().st_size == 0:
                        z.extract(member, dest_dir)
                
                results.append({"year": year, "zip_valido": True})
        except Exception as e:
            print(f"ERROR al validar/extraer ZIP {zip_path}: {e}")
            results.append({"year": year, "zip_valido": False, "error": str(e)})

    return results


def main():
    parser = argparse.ArgumentParser(description="Descarga de fuentes DEIS.")
    parser.add_argument("--force", action="store_true", help="Fuerza la redescarga y extracción.")
    args = parser.parse_args()

    urgencias_res = download_and_extract_source("Atenciones de Urgencia", URGENCIAS_CONFIG, DEST_URGENCIAS, force=args.force)
    egresos_res = download_and_extract_source("Egresos Hospitalarios", EGRESOS_CONFIG, DEST_EGRESOS, force=args.force)

    summary = {
        "urgencias": urgencias_res,
        "egresos": egresos_res
    }

    # Use data/processed for summary since scratch might not be the official place
    summary_path = Path("data/processed/deis_ingest_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nProceso finalizado. Resumen en {summary_path}")


if __name__ == "__main__":
    main()
