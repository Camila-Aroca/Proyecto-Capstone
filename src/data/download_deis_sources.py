"""Ingesta segura de snapshots RAW DEIS de Urgencias y Egresos."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import sys
from tempfile import TemporaryDirectory
from typing import Any
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

URGENCIAS_CONFIG = [
    {"year": year, "url": url}
    for year, url in (
        (2020, "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2020.zip"),
        (2021, "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2021.zip"),
        (2022, "https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia2022.zip"),
        (2023, "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2023.zip"),
        (2024, "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2024.zip"),
        (2025, "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2025.zip"),
        (2026, "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2026.zip"),
    )
]
EGRESOS_CONFIG = [
    {"year": year, "url": f"https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_{year}.zip"}
    for year in range(2020, 2026)
]

DEST_URGENCIAS = Path("data/raw/urgencias")
DEST_EGRESOS = Path("data/raw/egresos")
CACHE_DOWNLOADS = Path(".cache/downloads")
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def canonical_urgencias_raw_path(year: int) -> Path:
    return DEST_URGENCIAS / f"AtencionesUrgencia{year}.csv"


def canonical_egresos_raw_path(year: int) -> Path:
    return DEST_EGRESOS / f"egresos_{year}.csv"


def file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp"
    try:
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def record_deis_snapshot(
    dataset: str, year: int, source_url: str, zip_path: Path, raw_path: Path,
    archive_member: str, manifest_path: Path = MANIFEST_PATH,
    downloaded_at: str | None = None,
) -> None:
    """Append, never replace, a future DEIS snapshot."""
    manifest: list[dict[str, Any]] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, list):
            raise ValueError("El manifiesto de provenance debe ser una lista JSON.")
    source_id = f"deis_{dataset}_{year}"
    entry = next((item for item in manifest if item.get("source_id") == source_id), None)
    if entry is None:
        entry = {"source_id": source_id, "dataset": dataset, "year": year, "snapshots": []}
        manifest.append(entry)
    entry.setdefault("dataset", dataset)
    entry.setdefault("year", year)
    entry.setdefault("snapshots", []).append({
        "source_url": source_url,
        "downloaded_at": downloaded_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "zip_filename": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": file_sha256(zip_path),
        "archive_member": archive_member,
        "raw_path": raw_path.as_posix(),
        "raw_filename": raw_path.name,
        "raw_size": raw_path.stat().st_size,
        "raw_sha256": file_sha256(raw_path),
    })
    _atomic_json_write(manifest_path, manifest)


def find_single_csv_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    members = [member for member in archive.infolist()
               if not member.is_dir() and Path(member.filename).suffix.lower() == ".csv"]
    if len(members) != 1:
        names = ", ".join(member.filename for member in members) or "none"
        raise ValueError(f"Expected exactly one DEIS CSV data member; found: {names}.")
    return members[0]


def _safe_member_name(name: str) -> Path:
    member = Path(name)
    if member.is_absolute() or ".." in member.parts:
        raise ValueError(f"Miembro ZIP inseguro: {name}")
    return member


def _validate_csv(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"CSV extraído vacío o inexistente: {path.name}")
    with path.open("rb") as handle:
        header = handle.readline()
    if not header.strip() or b";" not in header:
        raise ValueError(f"CSV DEIS inválido (sin cabecera delimitada): {path.name}")


def _validate_supporting_file(path: Path) -> None:
    """Perform a format-level check for source dictionaries when supplied."""
    if path.suffix.lower() == ".xlsx" and not zipfile.is_zipfile(path):
        raise ValueError(f"Diccionario XLSX inválido: {path.name}")


def _extract_to_staging(archive_path: Path, staging_dir: Path) -> tuple[Path, list[Path], str]:
    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise zipfile.BadZipFile(f"Archivo corrupto en ZIP: {bad_member}")
        csv_member = find_single_csv_member(archive)
        extracted: list[Path] = []
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = staging_dir / _safe_member_name(member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            if target.stat().st_size == 0:
                raise ValueError(f"Miembro ZIP vacío: {member.filename}")
            if target.suffix.lower() != ".csv":
                _validate_supporting_file(target)
            extracted.append(target)
    csv_path = staging_dir / _safe_member_name(csv_member.filename)
    _validate_csv(csv_path)
    return csv_path, extracted, csv_member.filename


def _download_zip(url: str, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    partial = cache_path.with_suffix(f"{cache_path.suffix}.part")
    partial.unlink(missing_ok=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, context=ssl_context) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        if partial.stat().st_size == 0:
            raise ValueError("ZIP descargado vacío.")
        os.replace(partial, cache_path)
    except Exception:
        partial.unlink(missing_ok=True)
        cache_path.unlink(missing_ok=True)
        raise


def extract_canonical_egresos_csv(
    archive_path: Path, year: int, destination_dir: Path = DEST_EGRESOS,
    force: bool = False,
) -> dict[str, Any]:
    """Compatibility helper: validate then publish an Egresos ZIP canonically."""
    raw_path = destination_dir / canonical_egresos_raw_path(year).name
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        with zipfile.ZipFile(archive_path) as archive:
            member = find_single_csv_member(archive)
        return {"raw_path": raw_path, "archive_member": member.filename, "published": False}
    destination_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f"deis_egresos_{year}_", dir=archive_path.parent) as temporary:
        csv_path, _, member = _extract_to_staging(archive_path, Path(temporary))
        os.replace(csv_path, raw_path)
    return {"raw_path": raw_path, "archive_member": member, "published": True}


def ingest_deis_source(
    dataset: str, year: int, url: str, destination_dir: Path, force: bool = False,
    cache_dir: Path = CACHE_DOWNLOADS, manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    """Download, validate, publish and record one DEIS snapshot safely."""
    raw_name = (canonical_urgencias_raw_path(year).name if dataset == "urgencias"
                else canonical_egresos_raw_path(year).name)
    raw_path = destination_dir / raw_name
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        return {"year": year, "raw_path": raw_path.as_posix(), "published": False, "skipped": True}
    zip_path = cache_dir / f"deis_{dataset}_{year}_{Path(url).name}"
    succeeded = False
    try:
        _download_zip(url, zip_path)
        with TemporaryDirectory(prefix=f"deis_{dataset}_{year}_", dir=cache_dir) as temporary:
            staging = Path(temporary)
            csv_path, files, archive_member = _extract_to_staging(zip_path, staging)
            destination_dir.mkdir(parents=True, exist_ok=True)
            publications = [(csv_path, raw_path)] + [
                (path, destination_dir / path.name) for path in files if path != csv_path
            ]
            backups: list[tuple[Path, Path]] = []
            published: list[Path] = []
            try:
                for index, (_, destination) in enumerate(publications):
                    if destination.exists():
                        backup = staging / f"previous_{index}"
                        os.replace(destination, backup)
                        backups.append((backup, destination))
                for staged_file, destination in publications:
                    os.replace(staged_file, destination)
                    published.append(destination)
                record_deis_snapshot(dataset, year, url, zip_path, raw_path,
                                     archive_member, manifest_path)
            except Exception:
                for destination in published:
                    destination.unlink(missing_ok=True)
                for backup, destination in backups:
                    if backup.exists():
                        os.replace(backup, destination)
                raise
        succeeded = True
        return {"year": year, "raw_path": raw_path.as_posix(), "archive_member": archive_member, "published": True}
    finally:
        # Retain failed transport artifacts for diagnosis outside RAW; remove
        # them only after all validation, publication and provenance succeed.
        if succeeded:
            zip_path.unlink(missing_ok=True)


def migrate_legacy_egresos_raw(destination_dir: Path = DEST_EGRESOS) -> list[dict[str, Any]]:
    """Create canonical Egresos aliases from a sole legacy CSV byte-for-byte."""
    results: list[dict[str, Any]] = []
    for year in range(2020, 2026):
        canonical = destination_dir / canonical_egresos_raw_path(year).name
        csv_files = list(destination_dir.glob("*.csv"))
        case_only = [path for path in csv_files if path.name.casefold() == canonical.name.casefold()]
        exact = next((path for path in case_only if path.name == canonical.name), None)
        if exact is None and len(case_only) == 1:
            # Windows treats EGRESOS_2023.csv and egresos_2023.csv as one
            # pathname. Rename through a temporary name to reconcile casing
            # without changing the file bytes.
            legacy = case_only[0]
            legacy_hash = file_sha256(legacy)
            staged = destination_dir / f".{canonical.name}.case-migration.tmp"
            staged.unlink(missing_ok=True)
            try:
                os.replace(legacy, staged)
                os.replace(staged, canonical)
            finally:
                staged.unlink(missing_ok=True)
            results.append({"year": year, "legacy_path": legacy.as_posix(),
                            "canonical_path": canonical.as_posix(),
                            "legacy_sha256": legacy_hash,
                            "canonical_sha256": file_sha256(canonical),
                            "identical": True, "migrated": True})
            continue
        variants = [path for path in destination_dir.glob("*.csv")
                    if path.name != canonical.name and str(year) in path.stem]
        if exact is not None:
            for variant in variants:
                results.append({"year": year, "legacy_path": variant.as_posix(),
                                "canonical_path": canonical.as_posix(),
                                "identical": file_sha256(variant) == file_sha256(canonical),
                                "migrated": False})
            continue
        if not variants:
            continue
        if len(variants) != 1:
            raise ValueError(f"Egresos {year}: variantes históricas ambiguas.")
        legacy = variants[0]
        staged = destination_dir / f".{canonical.name}.migration.tmp"
        staged.unlink(missing_ok=True)
        try:
            os.link(legacy, staged)
            os.replace(staged, canonical)
        finally:
            staged.unlink(missing_ok=True)
        results.append({"year": year, "legacy_path": legacy.as_posix(),
                        "canonical_path": canonical.as_posix(),
                        "legacy_sha256": file_sha256(legacy),
                        "canonical_sha256": file_sha256(canonical),
                        "identical": True, "migrated": True})
    return results


def download_and_extract_source(source_name: str, config_list: list[dict[str, Any]], dest_dir: Path, force: bool = False) -> list[dict[str, Any]]:
    dataset = "urgencias" if source_name == "Atenciones de Urgencia" else "egresos"
    results = []
    for item in config_list:
        try:
            results.append(ingest_deis_source(dataset, item["year"], item["url"], dest_dir, force))
        except Exception as error:
            results.append({"year": item["year"], "zip_valido": False, "error": str(error)})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga segura de fuentes DEIS.")
    parser.add_argument("--force", action="store_true", help="Solicita explícitamente un snapshot nuevo.")
    args = parser.parse_args()
    summary = {
        "egresos_migration": migrate_legacy_egresos_raw(),
        "urgencias": download_and_extract_source("Atenciones de Urgencia", URGENCIAS_CONFIG, DEST_URGENCIAS, args.force),
        "egresos": download_and_extract_source("Egresos Hospitalarios", EGRESOS_CONFIG, DEST_EGRESOS, args.force),
    }
    _atomic_json_write(Path("data/processed/deis_ingest_summary.json"), summary)


if __name__ == "__main__":
    main()
