"""Ingesta de los dos paquetes DEIS de Defunciones, sin modificar sus miembros."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import datetime as dt
import json
import logging
import os
from pathlib import Path
import shutil
import ssl
import stat
from tempfile import TemporaryDirectory
from typing import Any
import urllib.request
import zipfile

from openpyxl import load_workbook

from src.data.raw_provenance import MANIFEST_PATH, file_sha256, record_raw_snapshot


logger = logging.getLogger(__name__)
DEST_DIR = Path("data/raw/defunciones")
CACHE_DIR = Path(".cache/downloads/defunciones")
DICTIONARY_FILENAME = "Diccionario de Datos y Manual de Uso BBDD-COVID19 liberada.xlsx"
CSV_COLUMNS = (
    "AÑO;FECHA_DEF;SEXO_NOMBRE;EDAD_TIPO;EDAD_CANT;COD_COMUNA;COMUNA;"
    "NOMBRE_REGION;DIAG1;CAPITULO_DIAG1;GLOSA_CAPITULO_DIAG1;"
    "CODIGO_GRUPO_DIAG1;GLOSA_GRUPO_DIAG1;CODIGO_CATEGORIA_DIAG1;"
    "GLOSA_CATEGORIA_DIAG1;CODIGO_SUBCATEGORIA_DIAG1;GLOSA_SUBCATEGORIA_DIAG1;"
    "DIAG2;CAPITULO_DIAG2;GLOSA_CAPITULO_DIAG2;CODIGO_GRUPO_DIAG2;"
    "GLOSA_GRUPO_DIAG2;CODIGO_CATEGORIA_DIAG2;GLOSA_CATEGORIA_DIAG2;"
    "CODIGO_SUBCATEGORIA_DIAG2;GLOSA_SUBCATEGORIA_DIAG2;LUGAR_DEFUNCION"
).split(";")
MAX_RAW_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class DefuncionesSource:
    key: str
    basename: str
    first_year: int
    last_year: int
    status: str

    @property
    def csv_filename(self) -> str:
        return self.basename + ".csv"

    @property
    def url(self) -> str:
        return "https://repositoriodeis.minsal.cl/DatosAbiertos/VITALES/" + self.basename + ".zip"

    @property
    def source_id(self) -> str:
        return "deis_defunciones_" + self.key


DEFUNCIONES_SOURCES = (
    DefuncionesSource("1990_2023", "DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES",
                      1990, 2023, "cifras_oficiales_segun_nombre_fuente"),
    DefuncionesSource("2024_2026_27102026", "DEFUNCIONES_FUENTE_DEIS_2024_2026_27102026",
                      2024, 2026, "snapshot_fechado_27102026_sin_afirmar_cierre_anual"),
)


def source_for_csv(path: Path) -> DefuncionesSource:
    for source in DEFUNCIONES_SOURCES:
        if path.name == source.csv_filename:
            return source
    raise ValueError("CSV de Defunciones no configurado.")


def validate_csv(path: Path, source: DefuncionesSource, *, full_scan: bool = False) -> int:
    """Cabecera exacta y filas rectangulares; ingesta completa, SKIP hasta 100 filas.

    La lectura latin-1 reproduce los bytes de la cabecera publicada (AÑO). No
    reemplaza caracteres, transforma valores ni valida equivalencia clínica.
    """
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_RAW_BYTES:
        raise ValueError(f"CSV vacío, ausente o fuera de límite: {path.name}")
    count = 0
    with path.open(encoding="latin-1", newline="") as handle:
        reader = csv.reader(handle, delimiter=";", strict=True)
        if next(reader, None) != CSV_COLUMNS:
            raise ValueError(f"Cabecera de Defunciones inesperada: {path.name}")
        for row in reader:
            if len(row) != len(CSV_COLUMNS):
                raise ValueError(f"Número de columnas inválido en registro {count + 1}: {path.name}")
            if not row[0].isdigit() or not source.first_year <= int(row[0]) <= source.last_year:
                raise ValueError(f"Año fuera del periodo configurado en registro {count + 1}: {path.name}")
            count += 1
            if not full_scan and count >= 100:
                break
    if not count:
        raise ValueError(f"CSV sin registros: {path.name}")
    return count


def validate_dictionary(path: Path) -> None:
    """Legibilidad XLSX y hojas observadas; solo lectura, sin guardar el libro."""
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        if not {"Diccionario Dato Abierto", "Manual de Uso"}.issubset(
            {name.strip() for name in workbook.sheetnames}
        ):
            raise ValueError("Diccionario de Defunciones sin hojas requeridas.")
    finally:
        workbook.close()


def _download(url: str, path: Path) -> dict[str, Any]:
    partial = path.with_suffix(".zip.part")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    metadata: dict[str, Any] = {}
    try:
        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=120) as response, \
                partial.open("wb") as output:
            headers = getattr(response, "headers", {})
            for field in ("Last-Modified", "ETag"):
                if headers.get(field):
                    metadata[field] = headers[field]
            expected_size = headers.get("Content-Length")
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 512 * 1024**2:
                    raise ValueError("Descarga ZIP supera el límite de 512 MiB.")
                output.write(chunk)
        if not size or (expected_size is not None and size != int(expected_size)):
            raise ValueError("Descarga ZIP vacía o incompleta.")
        metadata["downloaded_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return metadata


def _extract(archive_path: Path, staging: Path, source: DefuncionesSource) -> list[Path]:
    expected = {source.csv_filename, DICTIONARY_FILENAME}
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        # Solo los dos nombres exactos: rechaza traversal, rutas Windows,
        # duplicados, enlaces simbólicos y miembros no contemplados.
        if len(names) != 2 or set(names) != expected:
            raise ValueError("Miembros ZIP inesperados o inseguros en Defunciones.")
        if sum(member.file_size for member in members) > MAX_RAW_BYTES:
            raise ValueError("Expansión ZIP supera el límite de 2 GiB.")
        for member in members:
            if member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Miembro ZIP cifrado o enlace simbólico.")
            if not member.file_size:
                raise ValueError("Miembro ZIP vacío.")
            target = staging / member.filename
            # Leer cada miembro hasta EOF comprueba CRC; no se extrae dos veces.
            with archive.open(member) as incoming, target.open("wb") as output:
                shutil.copyfileobj(incoming, output, length=1024 * 1024)
            if target.stat().st_size != member.file_size:
                raise ValueError("Miembro ZIP incompleto.")
    count = validate_csv(staging / source.csv_filename, source, full_scan=True)
    validate_dictionary(staging / DICTIONARY_FILENAME)
    logger.info("%s: %s registros validados; CRC y diccionario legible", source.key, count)
    return [staging / source.csv_filename, staging / DICTIONARY_FILENAME]


def _registered(source_id: str, digest: str, manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("El manifiesto debe ser una lista.")
    return any(snapshot.get("raw_sha256") == digest
               for entry in entries if entry.get("source_id") == source_id
               for snapshot in entry.get("snapshots", []))


def _replace_public(candidate: Path, target: Path) -> None:
    """Publica desde el directorio destino para heredar sus permisos normales.

    En Windows, mover directamente desde TemporaryDirectory conserva su ACL
    privada e impide que otros procesos locales lean el RAW/manifiesto.
    """
    temporary = target.parent / f".{target.name}.tmp"
    try:
        shutil.copyfile(candidate, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def ingest_source(
    source: DefuncionesSource, *, force: bool = False, dest_dir: Path = DEST_DIR,
    cache_dir: Path = CACHE_DIR, manifest_path: Path = MANIFEST_PATH,
) -> bool:
    """Publica CSV + diccionario + provenance con rollback ante cualquier fallo.

    ZIP retenido en cache si falla la validación/publicación; eliminado solo
    después del éxito. Un --force idéntico no duplica el historial ni toca RAW.
    """
    target_dir = dest_dir / source.key
    targets = [target_dir / source.csv_filename, target_dir / DICTIONARY_FILENAME]
    if not force and all(path.is_file() for path in targets):
        try:
            validate_csv(targets[0], source)
            validate_dictionary(targets[1])
            registered = all(_registered(source.source_id + suffix, file_sha256(path), manifest_path)
                             for path, suffix in zip(targets, ("", "_dictionary")))
            if registered:
                logger.info("[SKIP] %s: RAW válidos y registrados", source.key)
                return False
        except (ValueError, OSError, zipfile.BadZipFile):
            logger.warning("%s: RAW inválido; se intentará recuperar desde fuente", source.key)
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cache_dir / (source.basename + ".zip")
    logger.info("Descargando %s", source.url)
    metadata = _download(source.url, archive_path)
    transport = {"filename": archive_path.name, "size": archive_path.stat().st_size,
                 "sha256": file_sha256(archive_path), **metadata}
    with TemporaryDirectory(prefix="staging_", dir=cache_dir) as directory:
        staging = Path(directory)
        candidates = _extract(archive_path, staging, source)
        changes = [not target.exists() or file_sha256(candidate) != file_sha256(target)
                   for candidate, target in zip(candidates, targets)]
        needs_registration = [not _registered(source.source_id + suffix, file_sha256(candidate), manifest_path)
                              for candidate, suffix in zip(candidates, ("", "_dictionary"))]
        if any(changes) or any(needs_registration):
            target_dir.mkdir(parents=True, exist_ok=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            pending_manifest = staging / "manifest.json"
            if manifest_path.exists():
                shutil.copyfile(manifest_path, pending_manifest)
            published: list[tuple[Path, Path | None]] = []
            try:
                for index, (candidate, target, changed) in enumerate(zip(candidates, targets, changes)):
                    if not changed:
                        continue
                    backup = staging / f"previous_{index}"
                    if target.exists():
                        shutil.copyfile(target, backup)
                    else:
                        backup = None
                    _replace_public(candidate, target)
                    published.append((target, backup))
                for target, suffix, changed, missing in zip(targets, ("", "_dictionary"), changes, needs_registration):
                    if changed or missing:
                        record_raw_snapshot(
                            source.source_id + suffix, source.url, target,
                            manifest_path=pending_manifest,
                            downloaded_at=metadata["downloaded_at"],
                            transport={**transport, "archive_member": target.name},
                            source_metadata={"dataset": "defunciones", "periodo": f"{source.first_year}-{source.last_year}",
                                             "estado_fuente": source.status},
                        )
                _replace_public(pending_manifest, manifest_path)
            except Exception:
                for target, backup in reversed(published):
                    if backup is None:
                        target.unlink(missing_ok=True)
                    else:
                        _replace_public(backup, target)
                raise
    archive_path.unlink()
    logger.info("%s: RAW y procedencia verificados; ZIP eliminado", source.key)
    return any(changes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Solicitar nuevamente ambos paquetes oficiales.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    failures = []
    for source in DEFUNCIONES_SOURCES:
        try:
            ingest_source(source, force=args.force)
        except Exception as error:
            logger.error("%s: %s: %s", source.key, type(error).__name__, error)
            failures.append(source.key)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
