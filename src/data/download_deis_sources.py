"""Script de descarga, extracción e inspección de datos RAW DEIS-MINSAL (Urgencias 2020-2026 y Egresos 2020-2025)."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import ssl
import sys
from typing import Any
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


def canonical_egresos_raw_path(year: int) -> Path:
    """Return the stable RAW path consumed by the Egresos normalizer."""
    return DEST_EGRESOS / f"egresos_{year}.csv"

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def file_sha256(file_path: Path) -> str:
    """Calculate the SHA256 digest of a file without loading it into memory."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        for byte_block in iter(lambda: file_handle.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def update_manifest(
    source_url: str,
    zip_path: Path,
    year: int,
    raw_path: Path | None = None,
    archive_member: str | None = None,
) -> None:
    manifest_path = Path("data/raw/provenance_manifest.json")
    manifest = []
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
    entry = {
        "source_id": f"deis_{year}_{zip_path.stem.lower()}",
        "source_url": source_url,
        "filename": zip_path.name,
        "year": year,
        "downloaded_at": datetime.datetime.now().isoformat(),
        "file_size": zip_path.stat().st_size,
        "sha256": file_sha256(zip_path),
    }

    if raw_path is not None:
        entry.update(
            {
                "raw_path": raw_path.as_posix(),
                "raw_filename": raw_path.name,
                "raw_sha256": file_sha256(raw_path),
                "archive_member": archive_member,
            }
        )
    
    # Update the snapshot for this source, retaining the published archive and
    # member names alongside the deterministic internal RAW path.
    for i, e in enumerate(manifest):
        if e.get("source_id") == entry["source_id"]:
            manifest[i] = entry
            break
    else:
        manifest.append(entry)
        
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def find_single_csv_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    """Return the unique CSV member in a DEIS archive.

    DEIS has changed the published Egresos CSV filename between years. The
    archive contract is therefore structural (one tabular CSV), not lexical.
    """
    csv_members = [
        member
        for member in archive.infolist()
        if not member.is_dir() and Path(member.filename).suffix.lower() == ".csv"
    ]
    if len(csv_members) != 1:
        names = ", ".join(member.filename for member in csv_members) or "none"
        raise ValueError(
            "Expected exactly one DEIS CSV data member; found: " f"{names}."
        )
    return csv_members[0]


def extract_canonical_egresos_csv(
    archive_path: Path,
    year: int,
    destination_dir: Path = DEST_EGRESOS,
    force: bool = False,
) -> dict[str, Any]:
    """Publish a DEIS Egresos CSV under the stable per-year RAW contract."""
    canonical_path = destination_dir / canonical_egresos_raw_path(year).name
    if canonical_path.exists() and canonical_path.stat().st_size > 0 and not force:
        with zipfile.ZipFile(archive_path, "r") as archive:
            member = find_single_csv_member(archive)
        return {
            "raw_path": canonical_path,
            "archive_member": member.filename,
            "published": False,
        }

    destination_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = canonical_path.with_suffix(".csv.tmp")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise zipfile.BadZipFile(f"Archivo corrupto en zip: {bad_file}")
            member = find_single_csv_member(archive)
            with archive.open(member) as source, open(temporary_path, "wb") as target:
                shutil.copyfileobj(source, target)
        if temporary_path.stat().st_size == 0:
            raise ValueError(f"CSV extracted empty: {member.filename}")
        temporary_path.replace(canonical_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "raw_path": canonical_path,
        "archive_member": member.filename,
        "published": True,
    }


def download_and_extract_source(
    source_name: str,
    config_list: list[dict[str, Any]],
    dest_dir: Path,
    force: bool = False,
) -> list[dict[str, Any]]:
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

                if source_name == "Egresos Hospitalarios":
                    extracted = extract_canonical_egresos_csv(
                        zip_path, year, destination_dir=dest_dir, force=force
                    )
                    update_manifest(
                        url,
                        zip_path,
                        year,
                        raw_path=extracted["raw_path"],
                        archive_member=extracted["archive_member"],
                    )
                    results.append(
                        {
                            "year": year,
                            "zip_valido": True,
                            "raw_path": extracted["raw_path"].as_posix(),
                            "archive_member": extracted["archive_member"],
                        }
                    )
                else:
                    infolist = z.infolist()
                    for member in infolist:
                        extracted_path = dest_dir / member.filename
                        if force or not extracted_path.exists() or extracted_path.stat().st_size == 0:
                            z.extract(member, dest_dir)
                    update_manifest(url, zip_path, year)
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
