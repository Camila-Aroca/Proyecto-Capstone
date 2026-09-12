"""Ingesta segura de la cartografía comunal RAW del Censo 2024."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import ssl
from tempfile import TemporaryDirectory
import urllib.request
import zipfile

import pyarrow.parquet as pq
from shapely import wkb

from src.data.raw_provenance import file_sha256, record_raw_snapshot


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

URL_CENSO = "https://storage.googleapis.com/bktdescargascenso2024/Cartografia/GEOPARQUET/Cartografia_censo2024_Pais.zip"
DEST_DIR = Path("data/raw/censo")
CACHE_DIR = Path(".cache/downloads/censo")
TARGET_FILE_NAME = "Cartografia_censo2024_Pais_Comunal.parquet"
FINAL_OUTPUT_PATH = DEST_DIR / TARGET_FILE_NAME
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")
REQUIRED_COLUMNS = {"CUT", "COMUNA", "COD_REGION", "SHAPE"}


def _download_zip(url: str, cache_path: Path) -> None:
    """Descarga el transporte a cache; nunca a ``data/raw``."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = cache_path.with_suffix(f"{cache_path.suffix}.part")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(request, context=context) as response, partial_path.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if partial_path.stat().st_size == 0:
        raise ValueError("ZIP del Censo descargado vacío.")
    os.replace(partial_path, cache_path)


def _find_target_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    matches = [member for member in archive.infolist()
               if not member.is_dir() and Path(member.filename).name == TARGET_FILE_NAME]
    if len(matches) != 1:
        raise ValueError(f"Se esperaba exactamente una capa {TARGET_FILE_NAME} en el ZIP.")
    return matches[0]


def _validate_transport(zip_path: Path) -> zipfile.ZipInfo:
    if not zip_path.is_file() or zip_path.stat().st_size == 0 or not zipfile.is_zipfile(zip_path):
        raise ValueError("Transporte ZIP del Censo inexistente, vacío o inválido.")
    with zipfile.ZipFile(zip_path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member:
            raise zipfile.BadZipFile(f"Miembro corrupto en ZIP Censo: {corrupt_member}")
        return _find_target_member(archive)


def validate_censo_geoparquet(path: Path) -> None:
    """Valida legibilidad, esquema y una geometría mínima de la capa comunal."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("GeoParquet Censo inexistente o vacío.")
    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    missing = REQUIRED_COLUMNS.difference(schema.names)
    if missing:
        raise ValueError(f"GeoParquet Censo sin columnas requeridas: {sorted(missing)}")
    if parquet.metadata is None or parquet.metadata.num_rows <= 0:
        raise ValueError("GeoParquet Censo sin filas.")
    geo_metadata = (schema.metadata or {}).get(b"geo")
    if not geo_metadata:
        raise ValueError("GeoParquet Censo sin metadata geoespacial.")
    try:
        geo_columns = json.loads(geo_metadata.decode("utf-8")).get("columns", {})
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Metadata geoespacial inválida en GeoParquet Censo.") from error
    if "SHAPE" not in geo_columns:
        raise ValueError("Metadata geoespacial sin columna SHAPE.")
    geometry_batch = next(parquet.iter_batches(batch_size=1, columns=["SHAPE"]), None)
    if geometry_batch is None or geometry_batch.num_rows != 1:
        raise ValueError("GeoParquet Censo sin geometría legible.")
    geometry = geometry_batch.column(0)[0].as_py()
    if not geometry:
        raise ValueError("GeoParquet Censo con geometría vacía.")
    try:
        wkb.loads(geometry)
    except Exception as error:
        raise ValueError("GeoParquet Censo con geometría WKB inválida.") from error


def _extract_candidate(zip_path: Path, staging_dir: Path) -> tuple[Path, str]:
    member = _validate_transport(zip_path)
    candidate = staging_dir / TARGET_FILE_NAME
    with zipfile.ZipFile(zip_path) as archive, archive.open(member) as source, candidate.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)
    validate_censo_geoparquet(candidate)
    return candidate, member.filename


def _publish_candidate(candidate: Path, raw_path: Path, *, source_url: str, zip_path: Path,
                       archive_member: str, manifest_path: Path) -> None:
    """Publica candidato y provenance como una unidad con rollback del RAW previo."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    backup = candidate.parent / f"previous_{raw_path.name}"
    had_previous = raw_path.exists()
    try:
        if had_previous:
            os.replace(raw_path, backup)
        os.replace(candidate, raw_path)
        record_raw_snapshot(
            "censo_2024_cartografia_comunal", source_url, raw_path,
            transport={"filename": zip_path.name, "size": zip_path.stat().st_size,
                       "sha256": file_sha256(zip_path), "archive_member": archive_member},
            source_metadata={"dataset": "censo", "year": 2024}, manifest_path=manifest_path,
        )
    except Exception:
        raw_path.unlink(missing_ok=True)
        if had_previous and backup.exists():
            os.replace(backup, raw_path)
        raise
    finally:
        backup.unlink(missing_ok=True)


def ingest_censo(*, force: bool = False, url: str = URL_CENSO,
                 raw_path: Path = FINAL_OUTPUT_PATH, cache_dir: Path = CACHE_DIR,
                 manifest_path: Path = MANIFEST_PATH) -> bool:
    """Descarga, valida y publica Censo 2024; devuelve si publicó un snapshot."""
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        validate_censo_geoparquet(raw_path)
        logger.info("[SKIP] RAW Censo 2024 consolidado y válido: %s", raw_path.as_posix())
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "Cartografia_censo2024_Pais.zip"
    succeeded = False
    try:
        _download_zip(url, zip_path)
        with TemporaryDirectory(prefix="censo_2024_", dir=cache_dir) as temporary:
            candidate, archive_member = _extract_candidate(zip_path, Path(temporary))
            _publish_candidate(candidate, raw_path, source_url=url, zip_path=zip_path,
                               archive_member=archive_member, manifest_path=manifest_path)
        succeeded = True
        logger.info("RAW Censo publicado: %s", raw_path.as_posix())
        return True
    finally:
        # Un transporte fallido se conserva fuera de RAW para diagnóstico.
        if succeeded:
            zip_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga segura de Censo 2024.")
    parser.add_argument("--force", action="store_true", help="Solicita explícitamente reemplazar el snapshot consolidado.")
    args = parser.parse_args()
    try:
        ingest_censo(force=args.force)
    except Exception as error:
        logger.error("Fallo de ingesta Censo: %s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
