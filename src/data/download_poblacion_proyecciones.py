"""Ingesta segura de las Estimaciones y Proyecciones de Población INE 2002-2035 (comunal).

Fuente oficial: INE, "Estimaciones y Proyecciones de la Población de Chile a
nivel comunal 2002-2035" (base Censo 2017, documento metodológico de
noviembre 2019). El cuadro publica población residente habitual por sexo,
edad simple y comuna, al 30 de junio de cada año del período 2002-2035. Es un
producto demográfico independiente del Censo: no debe confundirse con la
población efectivamente censada de `download_censo_poblacion`.
"""

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

SOURCE_ID = "ine_proyecciones_poblacion_comunal_2002_2035"
URL_POBLACION_PROYECCIONES = (
    "https://www.ine.gob.cl/docs/default-source/proyecciones-de-poblacion/"
    "cuadros-estadisticos/base-2017/estimaciones-y-proyecciones-2002-2035-comunas.xlsx"
)
FILENAME = "ine_estimaciones_proyecciones_2002_2035_comunas.xlsx"
DEST_DIR = Path("data/raw/poblacion")
FINAL_OUTPUT_PATH = DEST_DIR / FILENAME
CACHE_DIR = Path(".cache/downloads/poblacion_proyecciones")
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")
REQUIRED_SHEET = "Est. y Proy. de Pob. Comunal"
MIN_ROWS = 50_000
MIN_COLS = 40


def validate_poblacion_proyecciones_workbook(path: Path) -> None:
    """Valida legibilidad mínima del XLSX oficial y presencia del cuadro comunal."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("XLSX de estimaciones/proyecciones de población inexistente o vacío.")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if REQUIRED_SHEET not in workbook.sheetnames:
            raise ValueError(f"XLSX sin la hoja requerida: {REQUIRED_SHEET!r}")
        sheet = workbook[REQUIRED_SHEET]
        if sheet.max_row < MIN_ROWS or sheet.max_column < MIN_COLS:
            raise ValueError("Hoja comunal de estimaciones/proyecciones con dimensiones inesperadas.")
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
        raise ValueError("XLSX de estimaciones/proyecciones de población descargado vacío.")
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
                "dataset": "ine_proyecciones_poblacion_comunal",
                "base_censal": 2017,
                "cobertura_anos": "2002-2035",
                "cuadro": "Est. y Proy. de Pob. Comunal (sexo x edad simple x comuna)",
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


def ingest_poblacion_proyecciones(
    *, force: bool = False, url: str = URL_POBLACION_PROYECCIONES,
    raw_path: Path = FINAL_OUTPUT_PATH, cache_dir: Path = CACHE_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> bool:
    """Descarga, valida y publica el cuadro comunal oficial; devuelve si publicó un snapshot."""
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        validate_poblacion_proyecciones_workbook(raw_path)
        logger.info(
            "[SKIP] RAW de estimaciones/proyecciones de población comunal consolidado y válido: %s",
            raw_path.as_posix(),
        )
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=cache_dir, prefix="poblacion_proyecciones_", suffix=".xlsx"
    ) as temp:
        candidate = Path(temp.name)
    try:
        _download_xlsx(url, candidate)
        validate_poblacion_proyecciones_workbook(candidate)
        _publish_candidate(candidate, raw_path, source_url=url, manifest_path=manifest_path)
        logger.info("RAW de estimaciones/proyecciones de población comunal publicado: %s", raw_path.as_posix())
        return True
    finally:
        candidate.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga segura del cuadro comunal INE de estimaciones/proyecciones 2002-2035.",
    )
    parser.add_argument("--force", action="store_true", help="Solicita explícitamente reemplazar el snapshot consolidado.")
    args = parser.parse_args()
    try:
        ingest_poblacion_proyecciones(force=args.force)
    except Exception as error:
        logger.error("Fallo de ingesta de estimaciones/proyecciones de población comunal: %s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
