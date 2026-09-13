"""Ingesta segura del tabulado oficial INE de población censada por comuna (Censo 2024)."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import shutil
import ssl
import tempfile
import urllib.request

from openpyxl import load_workbook

from src.data.raw_provenance import file_sha256, record_raw_snapshot


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SOURCE_ID = "censo_2024_poblacion_comunal"
URL_CENSO_POBLACION = (
    "https://censo2024.ine.gob.cl/wp-content/uploads/2025/03/"
    "D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx"
)
FILENAME = "D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx"
DEST_DIR = Path("data/raw/censo")
FINAL_OUTPUT_PATH = DEST_DIR / FILENAME
CACHE_DIR = Path(".cache/downloads/censo_poblacion")
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")
REQUIRED_SHEETS = ("1", "2")


def validate_censo_poblacion_workbook(path: Path) -> None:
    """Valida legibilidad mínima del XLSX oficial y presencia de los cuadros 1 y 2."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("XLSX de población censada del Censo inexistente o vacío.")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        missing = [name for name in REQUIRED_SHEETS if name not in workbook.sheetnames]
        if missing:
            raise ValueError(f"XLSX de población censada sin hojas requeridas: {missing}")
        sheet = workbook["2"]
        if sheet.max_row < 350 or sheet.max_column < 7:
            raise ValueError("Cuadro comunal de población censada con dimensiones inesperadas.")
    finally:
        workbook.close()


def _download_xlsx(url: str, cache_path: Path) -> None:
    """Descarga el XLSX oficial a cache; nunca directamente a ``data/raw``."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = cache_path.with_suffix(f"{cache_path.suffix}.part")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(request, context=context) as response, partial_path.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if partial_path.stat().st_size == 0:
        raise ValueError("XLSX de población censada descargado vacío.")
    os.replace(partial_path, cache_path)


def _publish_candidate(candidate: Path, raw_path: Path, *, source_url: str, manifest_path: Path) -> None:
    """Publica el candidato validado y su provenance como una unidad, con rollback del RAW previo."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    backup = candidate.parent / f"previous_{raw_path.name}"
    had_previous = raw_path.exists()
    try:
        if had_previous:
            os.replace(raw_path, backup)
        os.replace(candidate, raw_path)
        record_raw_snapshot(
            SOURCE_ID, source_url, raw_path,
            transport={"filename": raw_path.name, "size": raw_path.stat().st_size,
                       "sha256": file_sha256(raw_path)},
            source_metadata={
                "dataset": "censo",
                "year": 2024,
                "cuadro": "2. Población censada por sexo y razón hombre-mujer, según comuna.",
            },
            manifest_path=manifest_path,
        )
    except Exception:
        raw_path.unlink(missing_ok=True)
        if had_previous and backup.exists():
            os.replace(backup, raw_path)
        raise
    finally:
        backup.unlink(missing_ok=True)


def ingest_censo_poblacion(*, force: bool = False, url: str = URL_CENSO_POBLACION,
                           raw_path: Path = FINAL_OUTPUT_PATH, cache_dir: Path = CACHE_DIR,
                           manifest_path: Path = MANIFEST_PATH) -> bool:
    """Descarga, valida y publica el tabulado comunal oficial; devuelve si publicó un snapshot."""
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        validate_censo_poblacion_workbook(raw_path)
        logger.info("[SKIP] RAW población comunal Censo 2024 consolidado y válido: %s", raw_path.as_posix())
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=cache_dir, prefix="censo_poblacion_", suffix=".xlsx") as temp:
        candidate = Path(temp.name)
    try:
        _download_xlsx(url, candidate)
        validate_censo_poblacion_workbook(candidate)
        _publish_candidate(candidate, raw_path, source_url=url, manifest_path=manifest_path)
        logger.info("RAW población comunal Censo publicado: %s", raw_path.as_posix())
        return True
    finally:
        candidate.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga segura del tabulado comunal de población Censo 2024.")
    parser.add_argument("--force", action="store_true", help="Solicita explícitamente reemplazar el snapshot consolidado.")
    args = parser.parse_args()
    try:
        ingest_censo_poblacion(force=args.force)
    except Exception as error:
        logger.error("Fallo de ingesta población comunal Censo: %s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
