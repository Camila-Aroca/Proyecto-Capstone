"""Ingesta segura de la estimación comunal de pobreza por ingresos (MDS, Casen).

Fuente oficial: Ministerio de Desarrollo Social y Familia (MDS), Observatorio
Social, "Estimaciones de Tasa de Pobreza por Ingresos por Comuna. Aplicación
de Metodología de Estimación para Áreas Pequeñas (SAE)", Encuesta Casen 2022.
El cuadro publica, para cada una de las 346 comunas del país, el porcentaje de
personas en situación de pobreza por ingresos 2022 con su intervalo de
confianza, la presencia de la comuna en la muestra Casen y el tipo de
estimación SAE (directa+sintética Fay-Herriot cuando la comuna cumple los
criterios de inclusión muestral, o sintética pura en caso contrario, incluso
con presencia en Casen).

Es un indicador/proxy oficial de vulnerabilidad socioeconómica comunal (tasa
de pobreza por ingresos), no un índice general ni compuesto de vulnerabilidad;
tiene cobertura verificada de las 52 comunas RM.
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

SOURCE_ID = "mds_casen_pobreza_comunal_2022"
URL_POBREZA_COMUNAL = (
    "https://observatorio.ministeriodesarrollosocial.gob.cl/storage/docs/"
    "pobreza-comunal/2022/Estimaciones_Tasa_Pobreza_Ingresos_Comunas_2022.xlsx"
)
FILENAME = "mds_casen_2022_tasa_pobreza_ingresos_comunal.xlsx"
DEST_DIR = Path("data/raw/pobreza")
FINAL_OUTPUT_PATH = DEST_DIR / FILENAME
CACHE_DIR = Path(".cache/downloads/pobreza_comunal")
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")
REQUIRED_SHEET = "Estimaciones"
MIN_ROWS = 340
MIN_COLS = 9


def validate_pobreza_comunal_workbook(path: Path) -> None:
    """Valida legibilidad mínima del XLSX oficial y presencia del cuadro comunal."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("XLSX de pobreza comunal inexistente o vacío.")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if REQUIRED_SHEET not in workbook.sheetnames:
            raise ValueError(f"XLSX sin la hoja requerida: {REQUIRED_SHEET!r}")
        sheet = workbook[REQUIRED_SHEET]
        if sheet.max_row < MIN_ROWS or sheet.max_column < MIN_COLS:
            raise ValueError("Hoja comunal de pobreza con dimensiones inesperadas.")
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
        raise ValueError("XLSX de pobreza comunal descargado vacío.")
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
                "dataset": "mds_casen_pobreza_comunal_ingresos",
                "institucion": "Ministerio de Desarrollo Social y Familia (MDS), Observatorio Social",
                "encuesta": "Casen 2022",
                "metodologia": "Estimación para Áreas Pequeñas (SAE, Fay-Herriot)",
                "cuadro": "Estimaciones de Tasa de Pobreza por Ingresos por Comuna 2022",
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


def ingest_pobreza_comunal(
    *, force: bool = False, url: str = URL_POBREZA_COMUNAL,
    raw_path: Path = FINAL_OUTPUT_PATH, cache_dir: Path = CACHE_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> bool:
    """Descarga, valida y publica el cuadro comunal oficial; devuelve si publicó un snapshot."""
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        validate_pobreza_comunal_workbook(raw_path)
        logger.info(
            "[SKIP] RAW de pobreza comunal consolidado y válido: %s",
            raw_path.as_posix(),
        )
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=cache_dir, prefix="pobreza_comunal_", suffix=".xlsx"
    ) as temp:
        candidate = Path(temp.name)
    try:
        _download_xlsx(url, candidate)
        validate_pobreza_comunal_workbook(candidate)
        _publish_candidate(candidate, raw_path, source_url=url, manifest_path=manifest_path)
        logger.info("RAW de pobreza comunal publicado: %s", raw_path.as_posix())
        return True
    finally:
        candidate.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga segura del cuadro comunal MDS/Casen de tasa de pobreza por ingresos 2022.",
    )
    parser.add_argument("--force", action="store_true", help="Solicita explícitamente reemplazar el snapshot consolidado.")
    args = parser.parse_args()
    try:
        ingest_pobreza_comunal(force=args.force)
    except Exception as error:
        logger.error("Fallo de ingesta de pobreza comunal: %s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
