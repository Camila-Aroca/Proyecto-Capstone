"""Ingesta segura del snapshot RAW del maestro DEIS de establecimientos."""

from __future__ import annotations

import argparse
import csv
import logging
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Any
import urllib.request

from src.data.raw_provenance import record_raw_snapshot


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEIS_URL = (
    "https://datos.gob.cl/dataset/3bf4cf7c-f638-4735-9a01-f65faae4beca/"
    "resource/2c44d782-3365-44e3-aefb-2c8b8363a1bc/download/establecimientos_20260825.csv"
)
OUTPUT_DIR = Path("data/raw/deis")
OUTPUT_FILE = OUTPUT_DIR / "establecimientos_salud_actualizado.csv"
CACHE_DIR = Path(".cache/downloads/establecimientos")
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")
REQUIRED_COLUMNS = {"EstablecimientoCodigo", "RegionCodigo", "ComunaCodigo", "Latitud", "Longitud"}


def ensure_directory(directory_path: Path) -> None:
    """Garantiza que el directorio especificado exista."""
    directory_path.mkdir(parents=True, exist_ok=True)


def detect_csv_format(file_path: Path) -> tuple[str, str]:
    """Detecta codificación y delimitador de un CSV."""
    sample_bytes = file_path.read_bytes()[:10000]
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "iso-8859-1", "cp1252"):
        try:
            sample_text = sample_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"CSV no decodificable: {file_path.name}")
    try:
        delimiter = csv.Sniffer().sniff(sample_text, delimiters=[",", ";", "\t", "|"]).delimiter
    except csv.Error:
        delimiter = ";" if sample_text.count(";") > sample_text.count(",") else ","
    return encoding, delimiter


def validate_and_preview(file_path: Path, max_rows: int = 5, max_cols: int = 5) -> tuple[list[str], list[list[str]]]:
    """Valida el CSV y devuelve una previsualización sin alterar el candidato."""
    if not file_path.is_file() or file_path.stat().st_size == 0:
        raise ValueError(f"CSV inexistente o vacío: {file_path}")
    encoding, delimiter = detect_csv_format(file_path)
    with file_path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise ValueError(f"CSV sin cabecera: {file_path}") from error
        headers = [header.strip().lstrip("\ufeff") for header in headers]
        if len(headers) < 2 or any(not header for header in headers):
            raise ValueError(f"CSV con cabecera inválida: {file_path}")
        missing = REQUIRED_COLUMNS.difference(headers)
        if missing:
            raise ValueError(f"CSV sin columnas mínimas requeridas: {sorted(missing)}")
        rows: list[list[str]] = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(headers):
                raise ValueError(f"CSV con fila de longitud inválida: {file_path}")
            rows.append(row[:max_cols])
            if len(rows) >= max_rows:
                break
    if not rows:
        raise ValueError(f"CSV sólo contiene encabezados: {file_path}")
    return headers[:max_cols], rows


def _download_to_candidate(url: str, destination: Path) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        status = getattr(response, "status", None) or getattr(response, "getcode", lambda: None)()
        if status is not None and status >= 400:
            raise RuntimeError(f"HTTP {status} al descargar establecimientos")
        shutil.copyfileobj(response, output, length=1024 * 1024)
        content_type = response.headers.get_content_type() if getattr(response, "headers", None) else None
    if destination.stat().st_size == 0:
        raise ValueError("CSV de establecimientos descargado vacío.")
    return {"http_status": status, "content_type": content_type}


def _publish_candidate(candidate: Path, raw_path: Path, *, source_url: str,
                       transport_metadata: dict[str, Any], manifest_path: Path) -> None:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    backup = candidate.parent / f"previous_{raw_path.name}"
    had_previous = raw_path.exists()
    try:
        if had_previous:
            os.replace(raw_path, backup)
        os.replace(candidate, raw_path)
        record_raw_snapshot(
            "deis_establecimientos", source_url, raw_path,
            transport=transport_metadata,
            source_metadata={"dataset": "establecimientos"}, manifest_path=manifest_path,
        )
    except Exception:
        raw_path.unlink(missing_ok=True)
        if had_previous and backup.exists():
            os.replace(backup, raw_path)
        raise
    finally:
        backup.unlink(missing_ok=True)


def ingest_establishments(*, force: bool = False, url: str = DEIS_URL,
                          raw_path: Path = OUTPUT_FILE, cache_dir: Path = CACHE_DIR,
                          manifest_path: Path = MANIFEST_PATH) -> bool:
    """Descarga, valida y publica el CSV; ``--force`` solicita un nuevo snapshot."""
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        validate_and_preview(raw_path)
        logger.info("[SKIP] RAW de establecimientos válido: %s", raw_path.as_posix())
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="establecimientos_", dir=cache_dir) as temporary:
        candidate = Path(temporary) / "establecimientos.csv"
        try:
            transport_metadata = _download_to_candidate(url, candidate)
            validate_and_preview(candidate)
            _publish_candidate(candidate, raw_path, source_url=url,
                               transport_metadata=transport_metadata, manifest_path=manifest_path)
        finally:
            # Temporary CSVs are always cleaned, including validation/download failures.
            candidate.unlink(missing_ok=True)
    logger.info("RAW establecimientos publicado: %s", raw_path.as_posix())
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga segura de establecimientos DEIS.")
    parser.add_argument("--force", action="store_true", help="Solicita explícitamente un snapshot nuevo.")
    args = parser.parse_args()
    ingest_establishments(force=args.force)


if __name__ == "__main__":
    main()
