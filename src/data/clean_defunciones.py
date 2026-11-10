"""Consolidación de Defunciones registrada en el DAG; conserva el grano publicado."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
import datetime as dt
from functools import lru_cache
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.data.download_defunciones import CSV_COLUMNS
from src.data.raw_provenance import file_sha256


CONFIG_PATH = Path(__file__).with_name("defunciones_config.json")
META_KEY = b"defunciones_consolidacion"
REPORT_TITLE = "# EDA de Defunciones consolidadas"
DICTIONARY_TITLE = "# Diccionario de Defunciones consolidadas"
logger = logging.getLogger(__name__)
COLUMN_MAP = dict(zip(CSV_COLUMNS, [
    "ano_defuncion", "fecha_defuncion", "sexo", "edad_tipo", "edad_cantidad",
    "comuna_codigo_original", "comuna_glosa", "region_glosa",
    *[column.lower() for column in CSV_COLUMNS[8:]],
]))
_TYPES = {"ano_defuncion": pa.int16(), "fecha_defuncion": pa.date32(),
          "edad_tipo": pa.int8(), "edad_cantidad": pa.int32()}
SCHEMA = pa.schema([
    *[(name, _TYPES.get(name, pa.string())) for name in COLUMN_MAP.values()],
    ("comuna_codigo", pa.string()), ("fecha_defuncion_original", pa.string()),
    ("edad_tipo_original", pa.string()), ("edad_cantidad_original", pa.string()),
    ("fuente_id", pa.string()), ("fuente_archivo", pa.string()),
    ("fuente_fila", pa.int64()), ("registro_raw_sha256", pa.string()),
    ("excepciones", pa.list_(pa.string())),
])


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      default=lambda item: item.isoformat()).encode("utf-8")


def _config_hash(settings: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


def _relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
        raise ValueError("La configuración y procedencia deben usar rutas relativas portables.")
    if not path.resolve().is_relative_to(Path.cwd().resolve()):
        raise ValueError("Ruta fuera del proyecto.")
    return path


def load_config(path: Path | None = None) -> dict[str, Any]:
    settings = json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))
    for field in ("raw_root", "provenance_manifest"):
        _relative(settings[field])
    if set(settings["outputs"]) != {"parquet", "summary", "report", "dictionary"}:
        raise ValueError("Configuración sin los cuatro outputs requeridos.")
    for value in settings["outputs"].values():
        _relative(value)
    start = dt.date.fromisoformat(settings["start_date"])
    end = dt.date.fromisoformat(settings["end_date"]) if settings["end_date"] else None
    if end is not None and end < start:
        raise ValueError("Periodo de consolidación invertido.")
    if not 1 <= settings["batch_size"] <= 100000 or not settings["date_formats"]:
        raise ValueError("Tamaño de bloque o formatos de fecha inválidos.")
    if len(set(settings["outputs"].values())) != 4:
        raise ValueError("Outputs duplicados.")
    return settings


def discover_inputs(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Descubre CSV registrados; rechaza omisiones, copias y hashes desalineados."""
    root = _relative(settings["raw_root"])
    manifest = json.loads(_relative(settings["provenance_manifest"]).read_text(encoding="utf-8"))
    from src.data.download_defunciones import active_preliminary_source
    pattern = r"deis_defunciones_\d{4}_\d{4}_\d{8}"
    has_preliminaries = any(re.fullmatch(pattern, entry.get("source_id", "")) for entry in manifest)
    active_id = active_preliminary_source(manifest).source_id if has_preliminaries else None
    sources = []
    for entry in manifest:
        if entry.get("dataset") != "defunciones" or not entry.get("snapshots"):
            continue
        latest = entry["snapshots"][-1]
        path = _relative(latest["raw_path"])
        if path.suffix.lower() != ".csv":
            continue
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("RAW registrado fuera de la carpeta autorizada.")
        if not path.exists() and re.fullmatch(pattern, entry["source_id"]) and entry["source_id"] != active_id:
            continue  # El manifiesto puede conservar historia cuyo RAW no está en un clon nuevo.
        digest = file_sha256(path)
        if digest != latest["raw_sha256"]:
            raise ValueError("RAW modificado sin procedencia vigente.")
        sources.append({"source_id": entry["source_id"], "path": path.as_posix(),
                        "sha256": digest, "size": path.stat().st_size})
    registered = {source["path"] for source in sources}
    found = {p.as_posix() for p in root.rglob("*.csv")}
    if len(sources) < 2 or registered != found or len(registered) != len(sources):
        raise ValueError("CSV faltantes, repetidos o no registrados en procedencia.")
    # Las publicaciones preliminares reemplazan el mismo intervalo: se conserva
    # cada RAW para auditoría, pero solo el snapshot más reciente alimenta el mart.
    preliminaries = [source for source in sources if re.fullmatch(
        pattern, source["source_id"])]
    if preliminaries:
        sources = [source for source in sources
                   if source not in preliminaries or source["source_id"] == active_id]
    if len({s["sha256"] for s in sources}) != len(sources):
        raise ValueError("Fuentes activas con contenido duplicado; posible solapamiento.")
    return sorted(sources, key=lambda source: source["path"])


@lru_cache(maxsize=65536)
def _date(value: str, formats: tuple[str, ...]) -> dt.date | None:
    for fmt in formats:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _integer(value: str, name: str, bits: int, exceptions: list[str]) -> int | None:
    if not value:
        exceptions.append(name + "_ausente")
        return None
    if re.fullmatch(r"-?[0-9]+", value):
        number = int(value)
        if -(2 ** (bits - 1)) <= number < 2 ** (bits - 1):
            return number
    exceptions.append(name + "_invalida")
    return None


def normalize(row: list[str], source: dict[str, Any], number: int,
              settings: dict[str, Any]) -> dict[str, Any]:
    """No infiere sexo, territorio, edad ni glosas desde otros registros."""
    values = [value.strip() for value in row]
    record = {column: value or None for column, value in zip(COLUMN_MAP.values(), values)}
    exceptions: list[str] = []
    year = int(values[0])
    record["ano_defuncion"] = year
    date = _date(values[1], tuple(settings["date_formats"])) if values[1] else None
    record["fecha_defuncion"] = date
    if date is None:
        exceptions.append("fecha_invalida" if values[1] else "fecha_ausente")
    elif date.year != year:
        exceptions.append("fecha_ano_discrepante")
    record["edad_tipo"] = _integer(values[3], "edad_tipo", 8, exceptions)
    record["edad_cantidad"] = _integer(values[4], "edad_cantidad", 32, exceptions)
    if record["edad_tipo"] is not None and record["edad_tipo"] not in range(5):
        exceptions.append("edad_tipo_fuera_diccionario")
    if record["edad_tipo"] == 0:
        exceptions.append("edad_ignorada_segun_unidad")
    if record["edad_cantidad"] is not None and record["edad_cantidad"] < 0:
        exceptions.append("edad_cantidad_negativa")
    code = values[5]
    # Cambio exclusivo de representación: dígitos ASCII, ancho 4/5 y mismo
    # valor entero. No certifica vigencia CUT ni convierte 99999 en ausencia.
    standardized = code.zfill(5) if re.fullmatch(r"[0-9]{4,5}", code) else None
    if standardized is not None and int(standardized) != int(code):
        raise ValueError("Estandarización comunal no reversible.")
    if standardized is None:
        exceptions.append("comuna_formato_no_estandarizable" if code else "comuna_ausente")
    for diagnosis, start in (("diag1", 8), ("diag2", 17)):
        if values[start] and any(not v for v in values[start + 1:start + 9]):
            exceptions.append(diagnosis + "_jerarquia_incompleta")
        elif not values[start] and any(values[start + 1:start + 9]):
            exceptions.append(diagnosis + "_jerarquia_sin_codigo")
    record.update({
        "comuna_codigo_original": row[5], "comuna_codigo": standardized,
        "fecha_defuncion_original": row[1], "edad_tipo_original": row[3],
        "edad_cantidad_original": row[4], "fuente_id": source["source_id"],
        "fuente_archivo": source["path"], "fuente_fila": number,
        "registro_raw_sha256": hashlib.sha256(_json(row)).hexdigest(),
        "excepciones": exceptions,
    })
    return record


class _Stats:
    def __init__(self) -> None:
        self.rows = 0
        self.years: Counter[str] = Counter()
        self.sources: Counter[str] = Counter()
        self.source_years: Counter[str] = Counter()
        self.nulls: Counter[str] = Counter(dict.fromkeys(SCHEMA.names, 0))
        self.exceptions: Counter[str] = Counter()
        self.digest = hashlib.sha256()
        self.minimum: dt.date | None = None
        self.maximum: dt.date | None = None

    def observe(self, record: dict[str, Any]) -> bytes:
        self.rows += 1
        year = str(record["ano_defuncion"])
        self.years[year] += 1
        self.sources[record["fuente_id"]] += 1
        self.source_years[record["fuente_id"] + ":" + year] += 1
        for column in SCHEMA.names:
            self.nulls[column] += int(record[column] is None)
        self.exceptions.update(record["excepciones"])
        encoded = _json([record[column] for column in SCHEMA.names])
        self.digest.update(encoded + b"\n")
        date = record["fecha_defuncion"]
        if date is not None:
            self.minimum = min(self.minimum, date) if self.minimum else date
            self.maximum = max(self.maximum, date) if self.maximum else date
        return hashlib.sha256(_json([record[column] for column in COLUMN_MAP.values()])).digest()

    def payload(self) -> dict[str, Any]:
        return {"rows": self.rows, "counts_by_year": dict(sorted(self.years.items())),
                "counts_by_source": dict(self.sources), "counts_by_source_year": dict(self.source_years),
                "null_counts": dict(self.nulls), "exceptions": dict(self.exceptions),
                "normalized_sequence_sha256": self.digest.hexdigest(),
                "min_date": self.minimum.isoformat() if self.minimum else None,
                "max_date": self.maximum.isoformat() if self.maximum else None}


def _count_hashes(connection: sqlite3.Connection, kind: str, values: list[bytes]) -> None:
    connection.executemany("INSERT INTO duplicates VALUES (?, ?, 1) "
                           "ON CONFLICT(kind,digest) DO UPDATE SET n=n+1",
                           ((kind, digest) for digest in values))


def _duplicates(connection: sqlite3.Connection, kind: str) -> int:
    return connection.execute("SELECT COALESCE(SUM(n-1),0) FROM duplicates WHERE kind=?", (kind,)).fetchone()[0]


def _replace_file(candidate: Path, target: Path) -> None:
    """Temporal junto al destino: hereda ACL pública en Windows."""
    temporary = target.parent / ("." + target.name + ".tmp")
    try:
        shutil.copyfile(candidate, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _publish(staged: dict[str, Path], settings: dict[str, Any], work: Path) -> None:
    published = []
    try:
        for key, candidate in staged.items():
            target = _relative(settings["outputs"][key])
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = work / (key + ".previous")
            if target.exists():
                shutil.copyfile(target, backup)
            else:
                backup = None
            _replace_file(candidate, target)
            published.append((target, backup))
    except Exception:
        for target, backup in reversed(published):
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                _replace_file(backup, target)
        raise


def _reports(audit: dict[str, Any]) -> tuple[str, str]:
    report = [REPORT_TITLE, "", "Una fila por registro publicado. Alcance nacional y todas las causas; "
              "no se deduplica, imputa ni enlaza con otras fuentes. EDA de staging normalizado, no certificación clínica.", "",
              f"Filas: **{audit['rows']}**. Fechas observadas: {audit['min_date']} a {audit['max_date']}. "
              "El último año puede ser parcial; el nombre/fecha del paquete no demuestra consolidación anual.", "",
              "| Año | Filas |", "| --- | ---: |",
              *[f"| {year} | {n} |" for year, n in audit["counts_by_year"].items()], "",
              "| Fuente | Leídas | Incluidas | Excluidas por periodo | SHA256 RAW |", "| --- | ---: | ---: | ---: | --- |"]
    for source in audit["inputs"]:
        report.append(f"| {source['path']} | {source['scanned_rows']} | {source['selected_rows']} | "
                      f"{source['scanned_rows'] - source['selected_rows']} | {source['sha256']} |")
    report += ["", f"Repeticiones adicionales de filas originales completas, por SHA256: **{audit['raw_duplicates']}**. "
               f"Repeticiones de las 27 variables normalizadas: **{audit['normalized_duplicates']}**. "
               "Se conservan todas: ausencia de identificador único de evento/paciente. Los hashes son comprobaciones "
               "criptográficas, no evidencia de identidad personal.", "",
               "| Excepción conservada | Filas |", "| --- | ---: |",
               *[f"| {key} | {n} |" for key, n in sorted(audit["exceptions"].items())], "",
               "| Columna | Nulos |", "| --- | ---: |",
               *[f"| {key} | {n} |" for key, n in audit["null_counts"].items()], "",
               "Validación completa tras escribir: esquema, Zstandard, conteos por fuente/año, nulos, excepciones, "
               "multiplicidad de hashes RAW y normalizados y SHA256 de la secuencia de todas las columnas. "
               "Los SHA256 de los RAW se comprueban antes y después; ninguna fila se pierde por fechas/edades ausentes. "
               "Los tests de integración contrastan además las 27 variables directamente contra los CSV.", "",
               "El resumen JSON asociado incluye configuración efectiva, hashes de código/RAW, conteos por fuente y año "
               "y hashes de los artefactos. No se infieren tasas, causalidad, ausencia clínica por DIAG2 vacío ni validez "
               "territorial por la forma del código. No es posible determinarlo con los datos disponibles.", ""]
    dictionary = [DICTIONARY_TITLE, "", "Grano: una fila por registro publicado, nacional, sin llave natural. "
                  "`fuente_id` + `fuente_fila` identifica una fila dentro del snapshot RAW cuyo hash figura en el footer. "
                  "No es una llave de paciente. Todas las 27 variables se conservan semánticamente.", "",
                  "| Columna RAW | Columna Parquet | Tipo Arrow |", "| --- | --- | --- |",
                  *[f"| {raw} | {name} | {SCHEMA.field(name).type} |" for raw, name in COLUMN_MAP.items()], "",
                  "| Columna adicional | Significado |", "| --- | --- |",
                  "| comuna_codigo | Dígitos ASCII de ancho 4/5 → cinco dígitos con cero inicial; valor entero invariable. "
                  "Otros formatos → nulo con excepción. No certifica pertenencia a un catálogo CUT; 99999 permanece 99999. |",
                  "| fecha_defuncion_original, edad_tipo_original, edad_cantidad_original | Texto publicado intacto para "
                  "auditar conversiones; un valor no interpretable queda nulo solo en su columna tipada. |",
                  "| fuente_id, fuente_archivo, fuente_fila | Identificador de procedencia, ruta relativa y ordinal CSV "
                  "(desde 1, excluye cabecera; no es número de línea física si hay campos multilínea). |",
                  "| registro_raw_sha256 | SHA256 de la lista de las 27 celdas originales serializada JSON UTF-8 compacto. |",
                  "| excepciones | Lista de incidencias conservadas; puede contener más de una por fila. |", "",
                  "Reglas: espacios exteriores retirados en textos analíticos; blanco → nulo excepto columnas originales "
                  "de auditoría (conservan texto exacto). No se interpreta `*`, 0, 99 ni 999 como ausente. Año obligatorio "
                  "entero válido; fecha según formatos configurados, sin inferir día/mes desde el año. Edades enteras "
                  "anulables y unidad separada: 0 ignorado, 1 años, 2 meses, 3 días, 4 horas, según diccionario RAW. "
                  "No se calcula edad equivalente ni se corrigen edades extremas.", "",
                  "DIAG1 conserva causa básica y DIAG2 causa externa; ambos con capítulo, grupo, categoría, "
                  "subcategoría y glosas originales normalizadas solo en espacios. No se completan jerarquías faltantes. "
                  "Territorio representa residencia según diccionario fuente, cuyo título y algunos nombres son anteriores "
                  "al esquema actual; no se interpreta como establecimiento hospitalario.", "",
                  "El periodo, encoding, formatos, tamaño de bloque y rutas están en `src/data/defunciones_config.json`; "
                  "fin nulo toma toda la información disponible desde el inicio configurado. Años de lotes distintos "
                  "no pueden solaparse dentro del periodo: se falla para revisar la fuente, nunca se elige una en silencio. "
                  "Los registros sin fecha se incluyen por el año declarado; discrepancias fecha/año se marcan. "
                  "No se selecciona por región ni diagnóstico.", "",
                  "Ejecución: `python scripts/run_pipeline.py --stage clean_defunciones`. `--force` regenera únicamente "
                  "esta consolidación. Reutilización valida esquema, compresión, conteos del footer, configuración, "
                  "código y hashes de los RAW; sin coincidencia se reconstruye. La publicación de los cuatro outputs "
                  "tiene temporales y rollback conjunto; no se escribe en RAW.", ""]
    return "\n".join(report), "\n".join(dictionary)


def consolidate(settings: dict[str, Any]) -> dict[str, Any]:
    inputs = discover_inputs(settings)
    start = dt.date.fromisoformat(settings["start_date"])
    end = dt.date.fromisoformat(settings["end_date"]) if settings["end_date"] else None
    metadata = {"config": settings, "config_sha256": _config_hash(settings),
                "producer_sha256": file_sha256(Path(__file__)), "inputs": inputs}
    cache = Path(".cache") / "defunciones"
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="consolidacion_", dir=cache) as directory:
        work = Path(directory)
        parquet = work / "candidate.parquet"
        expected = _Stats()
        owners: dict[int, str] = {}
        with closing(sqlite3.connect(work / "audit.sqlite")) as connection:
            connection.execute("CREATE TABLE duplicates(kind TEXT, digest BLOB, n INTEGER, "
                               "PRIMARY KEY(kind,digest)) WITHOUT ROWID")
            buffer: list[dict[str, Any]] = []

            def flush(writer: pq.ParquetWriter) -> None:
                if buffer:
                    writer.write_table(pa.Table.from_pylist(buffer, schema=SCHEMA))
                    _count_hashes(connection, "raw", [bytes.fromhex(r["registro_raw_sha256"]) for r in buffer])
                    _count_hashes(connection, "normalized", [hashlib.sha256(_json(
                        [r[c] for c in COLUMN_MAP.values()])).digest() for r in buffer])
                    connection.commit()
                    buffer.clear()

            with pq.ParquetWriter(parquet, SCHEMA, compression="zstd") as writer:
                for source in inputs:
                    scanned = selected = 0
                    with Path(source["path"]).open(encoding=settings["encoding"], newline="") as handle:
                        reader = csv.reader(handle, delimiter=";", strict=True)
                        if next(reader, None) != CSV_COLUMNS:
                            raise ValueError("Las fuentes no comparten las 27 columnas y orden requeridos.")
                        for scanned, row in enumerate(reader, 1):
                            if len(row) != len(CSV_COLUMNS):
                                raise ValueError("Registro RAW con número de columnas inválido.")
                            if not re.fullmatch(r"[0-9]{1,4}", row[0].strip()) or not 1 <= int(row[0]) <= 9999:
                                raise ValueError("Año RAW no interpretable; no se infiere ni descarta.")
                            year = int(row[0])
                            if year < start.year or (end is not None and year > end.year):
                                continue
                            record = normalize(row, source, scanned, settings)
                            date = record["fecha_defuncion"]
                            if date is not None and (date < start or (end is not None and date > end)):
                                if date.year != year:
                                    raise ValueError("Fecha y año discrepan en el límite del periodo.")
                                continue
                            if year in owners and owners[year] != source["source_id"]:
                                raise ValueError("solapamiento de años entre fuentes: requiere revisión explícita.")
                            owners[year] = source["source_id"]
                            selected += 1
                            expected.observe(record)
                            buffer.append(record)
                            if len(buffer) >= settings["batch_size"]:
                                flush(writer)
                    source.update(scanned_rows=scanned, selected_rows=selected)
                    logger.info("%s: %s filas leídas, %s incluidas", source["path"], scanned, selected)
                flush(writer)
                if not expected.rows:
                    raise ValueError("El periodo configurado no contiene registros.")
                metadata.update(expected.payload())
                metadata["raw_duplicates"] = _duplicates(connection, "raw")
                metadata["normalized_duplicates"] = _duplicates(connection, "normalized")
                writer.add_key_value_metadata({META_KEY.decode(): _json(metadata).decode("utf-8")})
            # Lectura completa del archivo cerrado; verifica serialización y multiplicidad.
            actual = _Stats()
            with pq.ParquetFile(parquet) as reader:
                for batch in reader.iter_batches(batch_size=settings["batch_size"]):
                    records = batch.to_pylist()
                    normalized_hashes = [actual.observe(r) for r in records]
                    _count_hashes(connection, "read_normalized", normalized_hashes)
                    _count_hashes(connection, "read_raw", [bytes.fromhex(r["registro_raw_sha256"]) for r in records])
                    connection.commit()
            if actual.payload() != expected.payload() or any(
                _duplicates(connection, left) != _duplicates(connection, right)
                for left, right in (("raw", "read_raw"), ("normalized", "read_normalized"))
            ):
                raise ValueError("La lectura del Parquet no preservó los registros originales normalizados.")
        current = discover_inputs(settings)
        if [(s["source_id"], s["sha256"]) for s in current] != [(s["source_id"], s["sha256"]) for s in inputs]:
            raise ValueError("RAW cambiaron durante la consolidación.")
        metadata["preservation_verified"] = True
        report, dictionary = _reports(metadata)
        staged = {"parquet": parquet, "report": work / "report.md", "dictionary": work / "dictionary.md"}
        staged["report"].write_text(report, encoding="utf-8")
        staged["dictionary"].write_text(dictionary, encoding="utf-8")
        metadata["artifact_sha256"] = {key: file_sha256(path) for key, path in staged.items()}
        staged["summary"] = work / "summary.json"
        staged["summary"].write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        validate_product(parquet, settings)
        _publish(staged, settings, work)
    logger.info("Consolidación verificada: %s filas, %s", expected.rows, settings["outputs"]["parquet"])
    return metadata


def validate_product(path: Path, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Contrato de SKIP: footer, configuración, código e inputs actuales."""
    settings = settings or load_config()
    with pq.ParquetFile(path) as parquet:
        if not parquet.schema_arrow.equals(SCHEMA, check_metadata=False):
            raise ValueError("Esquema de Defunciones incorrecto.")
        audit = json.loads((parquet.metadata.metadata or {})[META_KEY])
        if audit["config_sha256"] != _config_hash(settings):
            raise ValueError("La configuración cambió; regenerar Defunciones.")
        if audit["producer_sha256"] != file_sha256(Path(__file__)):
            raise ValueError("El código productor cambió; regenerar Defunciones.")
        current = discover_inputs(settings)
        if current != [{key: source[key] for key in ("source_id", "path", "sha256", "size")}
                       for source in audit["inputs"]]:
            raise ValueError("RAW/procedencia cambiaron; regenerar Defunciones.")
        if parquet.metadata.num_rows != audit["rows"] or audit["rows"] <= 0 or any(
            sum(audit[key].values()) != audit["rows"]
            for key in ("counts_by_source", "counts_by_year", "counts_by_source_year")
        ):
            raise ValueError("Conteos de Defunciones no reconcilian.")
        for group in range(parquet.metadata.num_row_groups):
            row_group = parquet.metadata.row_group(group)
            if any(row_group.column(index).compression != "ZSTD" for index in range(row_group.num_columns)):
                raise ValueError("Compresión distinta de Zstandard.")
    return audit


def validate_summary(path: Path, settings: dict[str, Any] | None = None) -> None:
    settings = settings or load_config()
    summary = json.loads(path.read_text(encoding="utf-8"))
    audit = validate_product(Path(settings["outputs"]["parquet"]), settings)
    if not summary.get("preservation_verified") or any(summary.get(key) != value for key, value in audit.items()):
        raise ValueError("Resumen de Defunciones no corresponde al Parquet verificado.")
    for key, digest in summary["artifact_sha256"].items():
        if file_sha256(Path(settings["outputs"][key])) != digest:
            raise ValueError("Artefacto de Defunciones modificado después de validación.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Regenerar por solicitud del orquestador.")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    consolidate(load_config())


if __name__ == "__main__":
    main()
