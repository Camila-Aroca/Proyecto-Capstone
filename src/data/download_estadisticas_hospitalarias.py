"""Ingesta segura de las Estadísticas Hospitalarias del REM-20 (DEIS).

Fuente oficial: Departamento de Estadísticas e Información de Salud (DEIS) del
Ministerio de Salud, repositorio ``REM20``. Se publican dos familias de libros XLSX
para los establecimientos del SNSS:

- **Indicadores hospitalarios según Servicio de Salud:** por establecimiento y
  nivel de cuidado (área funcional), una fila por indicador (días cama
  disponibles, días cama ocupados, índice ocupacional, egresos, etc.) con el
  acumulado y una columna por mes. Un libro consolidado 2014-2023 (una hoja por
  año), uno por año cerrado y uno del **año en curso** que el DEIS reemplaza cada
  mes con el último corte publicado.
- **Categorización de pacientes hospitalizados según riesgo-dependencia
  (CUDYR):** un libro por trimestre, jerárquico (región, Servicio de Salud,
  establecimiento y nivel de cuidado) con el total y las 12 categorías A1-D3.

Son estadísticas mensuales o trimestrales consolidadas, no gestión de camas en
tiempo real.

Se conserva además el **diccionario de datos REM-20** que publica datos.gob.cl
(``diccionario_rem20.xlsx``): define los campos de los indicadores (días cama,
egresos, traslados, índices). Describe el conjunto en formato largo de ese
portal, con nombres de campo propios (``DIAS_CAMAS_OCUPADAS``…); su
correspondencia con las glosas de los libros es por nombre, no la declara la
fuente. No cubre la categorización.

**Años cerrados y año en curso.** Los libros de años cerrados se configuran de
forma explícita en ``estadisticas_hospitalarias_config.json``: sus nombres de
archivo no siguen un patrón (``año 2025-_16042026``, ``SegundoTrimestre``), así que
no se adivinan. Para el año en curso (desde ``en_curso.primer_ano`` hasta el año
civil de Chile) no se fija el mes: se consulta la plantilla de URL observada en
la fuente (``{ano}/Estadísticas Hospitalarias {mes} {ano}.xlsx``) de diciembre a
enero y se toma el **último mes publicado**. Que el DEIS mantenga esa plantilla es
una inferencia de las URLs observadas, no una garantía: si no se encuentra ningún
mes la etapa lo informa, y el RAW vigente no se toca. Un corte con menos meses que
el RAW vigente no lo reemplaza (nunca se retrocede). Cuando un año en curso se
cierre y el DEIS publique su libro consolidado, se agrega a ``cerrados`` y se
avanza ``primer_ano``; no se sobrescribe en silencio.

Los trimestres de categorización del año en curso se buscan igual, con la
plantilla ``{ano}/Categorización riesgo dependencia {trimestre} Trimestre {ano}.xlsx``;
un trimestre aún no publicado no es un error.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import shutil
import ssl
import tempfile
from typing import Any, Callable
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from openpyxl import load_workbook

from src.chile_time import current_year_chile
from src.data.raw_provenance import file_sha256, record_raw_snapshot


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).with_name("estadisticas_hospitalarias_config.json")
MANIFEST_PATH = Path("data/raw/provenance_manifest.json")

MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre")
MESES_CORTOS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
TRIMESTRES = ("Primer", "Segundo", "Tercer", "Cuarto")

TITLE_ROW = 2
HEADER_ROW = 3
DICCIONARIO_TITULO = "Diccionario de Datos - Indicadores de Salud REM20"
DICCIONARIO_HEADER_ROW = 5
DICCIONARIO_COLUMNS = ("Nombre del Campo", "Tipo de Dato", "Nro. de caracteres", "Valores", "Detalle")
DICCIONARIO_CAMPOS = (
    "DIAS_CAMAS_OCUPADAS", "DIAS_CAMAS_DISPONIBLES", "DIAS_ESTADA", "NUMERO_EGRESOS", "EGRESOS_FALLECIDOS",
    "TRASLADOS", "INDICE_OCUPACIONAL", "PROMEDIO_CAMAS_DISPONIBLE", "PROMEDIO_DIAS_ESTADA", "LETALIDAD",
    "INDICE_ROTACION",
)
INDICADORES_COLUMNS = (
    "Cód. SS/SEREMI", "Nombre SS/SEREMI", "Cód. Estab.", "Nombre Establecimiento",
    "Cód. Nivel Cuidado", "Nombre Nivel Cuidado", "Glosa", "Acum",
)
CATEGORIAS = ("A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "D3")
CATEGORIZACION_COLUMNS = ("Establecimiento / Nivel de Cuidado", "Total", *CATEGORIAS)
INDICADORES_MIN_ROWS = 5000  # por hoja anual; el snapshot observado tiene unas 14.000
CATEGORIZACION_MIN_ROWS = 500  # el snapshot observado tiene unas 1.340

_PERIODO = re.compile(r"Per[ií]odo:\s*(\d{4})\s*$")


# --------------------------------------------------------------------------- #
# Configuración y publicaciones
# --------------------------------------------------------------------------- #

def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Publicacion:
    """Un libro del REM-20 y lo que se espera de él."""

    familia: str  # "indicadores", "categorizacion" o "diccionario"
    source_id: str
    url: str
    archivo: str
    anos: tuple[int, ...]
    meses: int | None = None  # meses publicados (indicadores); None = no se fija
    trimestre: int | None = None  # solo categorización
    en_curso: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _url(config: dict[str, Any], ruta: str) -> str:
    return config["base_url"] + urllib.parse.quote(ruta)


def _source_id(archivo: str) -> str:
    return "deis_rem20_" + Path(archivo).stem


def closed_publications(config: dict[str, Any]) -> list[Publicacion]:
    """Publicaciones fijas declaradas en la configuración: años cerrados y diccionario."""
    publicaciones = []
    if "diccionario" in config:
        item = config["diccionario"]
        publicaciones.append(Publicacion(
            familia="diccionario", source_id=_source_id(item["archivo"]), url=item["url"],
            archivo=item["archivo"], anos=(),
            metadata={"dataset": "deis_rem20_diccionario",
                      "institucion": "Ministerio de Salud, DEIS (publicado en datos.gob.cl)",
                      "alcance": "Diccionario de campos de los indicadores hospitalarios REM-20"},
        ))
    for item in config["indicadores"]["cerrados"]:
        anos = tuple(int(ano) for ano in item["anos"])
        publicaciones.append(Publicacion(
            familia="indicadores", source_id=_source_id(item["archivo"]), url=_url(config, item["ruta"]),
            archivo=item["archivo"], anos=anos, meses=12,
            metadata={"dataset": "deis_rem20_indicadores_hospitalarios",
                      "institucion": "Ministerio de Salud, DEIS",
                      "alcance": "Establecimientos del SNSS por nivel de cuidado",
                      "periodo": f"{anos[0]}-{anos[-1]}" if len(anos) > 1 else str(anos[0])},
        ))
    for item in config["categorizacion"]["cerrados"]:
        publicaciones.append(Publicacion(
            familia="categorizacion", source_id=_source_id(item["archivo"]), url=_url(config, item["ruta"]),
            archivo=item["archivo"], anos=(int(item["ano"]),), trimestre=int(item["trimestre"]),
            metadata={"dataset": "deis_rem20_categorizacion_riesgo_dependencia",
                      "institucion": "Ministerio de Salud, DEIS",
                      "alcance": "Pacientes hospitalizados del SNSS categorizados con CUDYR",
                      "periodo": f"{item['ano']}-T{item['trimestre']}"},
        ))
    return publicaciones


def _indicadores_en_curso(config: dict[str, Any], ano: int, mes: int) -> Publicacion:
    spec = config["indicadores"]["en_curso"]
    archivo = spec["plantilla_archivo"].format(ano=ano)
    return Publicacion(
        familia="indicadores", source_id=_source_id(archivo),
        url=_url(config, spec["plantilla_ruta"].format(ano=ano, mes=MESES[mes - 1])),
        archivo=archivo, anos=(ano,), meses=mes, en_curso=True,
        metadata={"dataset": "deis_rem20_indicadores_hospitalarios",
                  "institucion": "Ministerio de Salud, DEIS",
                  "alcance": "Establecimientos del SNSS por nivel de cuidado",
                  "periodo": str(ano), "estado": "año en curso: corte mensual reemplazado por la fuente"},
    )


def _categorizacion_en_curso(config: dict[str, Any], ano: int, numero: int) -> Publicacion:
    spec = config["categorizacion"]["en_curso"]
    archivo = spec["plantilla_archivo"].format(ano=ano, numero=numero)
    return Publicacion(
        familia="categorizacion", source_id=_source_id(archivo),
        url=_url(config, spec["plantilla_ruta"].format(ano=ano, trimestre=TRIMESTRES[numero - 1])),
        archivo=archivo, anos=(ano,), trimestre=numero, en_curso=True,
        metadata={"dataset": "deis_rem20_categorizacion_riesgo_dependencia",
                  "institucion": "Ministerio de Salud, DEIS",
                  "alcance": "Pacientes hospitalizados del SNSS categorizados con CUDYR",
                  "periodo": f"{ano}-T{numero}"},
    )


def current_years(config: dict[str, Any], now: datetime | None = None) -> list[int]:
    """Años no consolidados: desde ``en_curso.primer_ano`` hasta el año civil de Chile."""
    return list(range(int(config["indicadores"]["en_curso"]["primer_ano"]), current_year_chile(now) + 1))


def head_exists(url: str) -> bool:
    """True si la URL responde 200; 404 es "no publicado"; otro error se propaga."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=60) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def discover_current(
    config: dict[str, Any], *, now: datetime | None = None, probe: Callable[[str], bool] = head_exists,
) -> tuple[list[Publicacion], list[int]]:
    """Publicaciones vigentes de los años en curso y años sin ningún mes publicado.

    Indicadores: el último mes publicado de cada año (de diciembre a enero).
    Categorización: todos los trimestres publicados.
    """
    publicaciones: list[Publicacion] = []
    sin_publicar: list[int] = []
    for ano in current_years(config, now):
        ultimo = next((pub for mes in range(12, 0, -1)
                       if probe((pub := _indicadores_en_curso(config, ano, mes)).url)), None)
        if ultimo is None:
            sin_publicar.append(ano)
        else:
            publicaciones.append(ultimo)
        publicaciones.extend(pub for numero in range(1, 5)
                             if probe((pub := _categorizacion_en_curso(config, ano, numero)).url))
    return publicaciones, sin_publicar


def required_raw_paths(config: dict[str, Any] | None = None, now: datetime | None = None) -> list[Path]:
    """RAW que deben existir: los cerrados y los de años en curso ya obtenidos o pasados.

    El libro del año civil se exige solo cuando ya existe: en enero el DEIS aún no
    publica ningún mes, y exigirlo haría fallar la etapa sin un error real. Los
    trimestres de categorización del año en curso se exigen si ya se descargaron.
    """
    config = config or load_config()
    raw_dir = Path(config["raw_dir"])
    paths = [raw_dir / pub.archivo for pub in closed_publications(config)]
    this_year = current_year_chile(now)
    for ano in current_years(config, now):
        path = raw_dir / config["indicadores"]["en_curso"]["plantilla_archivo"].format(ano=ano)
        if ano < this_year or path.is_file():
            paths.append(path)
        for numero in range(1, 5):
            trimestre = raw_dir / config["categorizacion"]["en_curso"]["plantilla_archivo"].format(
                ano=ano, numero=numero)
            if trimestre.is_file():
                paths.append(trimestre)
    return paths


# --------------------------------------------------------------------------- #
# Validación estructural
# --------------------------------------------------------------------------- #

def _normalize(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value)).strip() if value is not None else ""


def _title_year(rows: list[tuple[Any, ...]], label: str) -> int:
    title = _normalize(rows[TITLE_ROW - 1][0]) if len(rows) >= TITLE_ROW else ""
    match = _PERIODO.search(title)
    if match is None:
        raise ValueError(f"{label}: título sin 'Período: AAAA' en la fila {TITLE_ROW} ({title!r}).")
    return int(match.group(1))


def _first_rows(sheet: Any, count: int = HEADER_ROW) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in sheet.iter_rows(min_row=1, max_row=count, values_only=True)]


def _count_rows(sheet: Any) -> int:
    return sum(1 for row in sheet.iter_rows(values_only=True) if any(cell is not None for cell in row))


def indicadores_periods(path: Path) -> dict[int, int]:
    """{año del título: meses del encabezado} de cada hoja de un libro de indicadores."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"XLSX de indicadores hospitalarios inexistente o vacío: {path.as_posix()}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        periods: dict[int, int] = {}
        for sheet in workbook.worksheets:
            label = f"{path.name}, hoja {sheet.title!r}"
            rows = _first_rows(sheet)
            year = _title_year(rows, label)
            header = [_normalize(cell) for cell in rows[HEADER_ROW - 1]]
            while header and not header[-1]:
                header.pop()
            fixed = len(INDICADORES_COLUMNS)
            if tuple(header[:fixed]) != INDICADORES_COLUMNS:
                raise ValueError(f"{label}: encabezado inesperado {header[:fixed]}")
            months = header[fixed:]
            if not months or tuple(months) != MESES_CORTOS[:len(months)]:
                raise ValueError(f"{label}: columnas de mes inesperadas {months}")
            if year in periods:
                raise ValueError(f"{label}: el año {year} se repite en otra hoja.")
            if _count_rows(sheet) < INDICADORES_MIN_ROWS:
                raise ValueError(f"{label}: menos filas de las esperadas.")
            periods[year] = len(months)
        return periods
    finally:
        workbook.close()


def validate_indicadores_workbook(path: Path, anos: tuple[int, ...], meses: int | None) -> None:
    """Hojas = años esperados (por el título), encabezado exacto y meses esperados."""
    periods = indicadores_periods(path)
    if sorted(periods) != sorted(anos):
        raise ValueError(f"{path.name}: años {sorted(periods)} distintos de los esperados {sorted(anos)}.")
    if meses is not None:
        wrong = {year: count for year, count in periods.items() if count != meses}
        if wrong:
            raise ValueError(f"{path.name}: se esperaban {meses} meses y el libro trae {wrong}.")


def validate_categorizacion_workbook(path: Path, ano: int) -> None:
    """Una hoja, título con el año esperado, encabezado exacto y mínimo de filas."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"XLSX de categorización inexistente o vacío: {path.as_posix()}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if len(workbook.worksheets) != 1:
            raise ValueError(f"{path.name}: se esperaba una sola hoja, hay {workbook.sheetnames}.")
        sheet = workbook.worksheets[0]
        rows = _first_rows(sheet)
        year = _title_year(rows, path.name)
        if year != ano:
            raise ValueError(f"{path.name}: el título declara {year} y se esperaba {ano}.")
        header = tuple(_normalize(cell) for cell in rows[HEADER_ROW - 1][:len(CATEGORIZACION_COLUMNS)])
        if header != CATEGORIZACION_COLUMNS:
            raise ValueError(f"{path.name}: encabezado inesperado {list(header)}")
        if _count_rows(sheet) < CATEGORIZACION_MIN_ROWS:
            raise ValueError(f"{path.name}: menos filas de las esperadas.")
    finally:
        workbook.close()


def read_diccionario(path: Path) -> list[dict[str, str | None]]:
    """Campos del diccionario REM-20 (una fila por campo), validando título y encabezado."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"XLSX del diccionario REM-20 inexistente o vacío: {path.as_posix()}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if len(workbook.worksheets) != 1:
            raise ValueError(f"{path.name}: se esperaba una sola hoja, hay {workbook.sheetnames}.")
        rows = [tuple(row) for row in workbook.worksheets[0].iter_rows(values_only=True)]
    finally:
        workbook.close()
    titulo = next((_normalize(cell) for cell in (rows[0] if rows else ()) if cell is not None), "")
    if titulo != DICCIONARIO_TITULO:
        raise ValueError(f"{path.name}: título inesperado.")
    header = tuple(_normalize(cell) for cell in rows[DICCIONARIO_HEADER_ROW - 1] if cell is not None)
    if header != DICCIONARIO_COLUMNS:
        raise ValueError(f"{path.name}: encabezado inesperado {list(header)}")
    start = rows[DICCIONARIO_HEADER_ROW - 1].index(next(c for c in rows[DICCIONARIO_HEADER_ROW - 1] if c is not None))
    campos = []
    for row in rows[DICCIONARIO_HEADER_ROW:]:
        celdas = [(_normalize(c) or None) if c is not None else None for c in row[start:start + len(DICCIONARIO_COLUMNS)]]
        if not any(celdas):
            continue
        campos.append(dict(zip(("campo", "tipo", "largo", "valores", "detalle"), celdas)))
    faltantes = sorted(set(DICCIONARIO_CAMPOS) - {c["campo"] for c in campos})
    if faltantes:
        raise ValueError(f"{path.name}: faltan los campos {faltantes}.")
    return campos


def validate_publicacion(pub: Publicacion, path: Path) -> None:
    if pub.familia == "diccionario":
        read_diccionario(path)
    elif pub.familia == "indicadores":
        validate_indicadores_workbook(path, pub.anos, pub.meses)
    else:
        validate_categorizacion_workbook(path, pub.anos[0])


_EN_CURSO_INDICADORES = re.compile(r"^indicadores_hospitalarios_(\d{4})\.xlsx$")
_EN_CURSO_CATEGORIZACION = re.compile(r"^categorizacion_riesgo_dependencia_(\d{4})_t([1-4])\.xlsx$")


def validate_raw_file(path: Path, config: dict[str, Any] | None = None) -> None:
    """Contrato de un RAW publicado, deducido de su nombre (para el orquestador)."""
    config = config or load_config()
    by_name = {pub.archivo: pub for pub in closed_publications(config)}
    if path.name in by_name:
        validate_publicacion(by_name[path.name], path)
    elif match := _EN_CURSO_INDICADORES.match(path.name):
        # El corte del año en curso varía: se exige el año, no un número de meses.
        validate_indicadores_workbook(path, (int(match.group(1)),), None)
    elif match := _EN_CURSO_CATEGORIZACION.match(path.name):
        validate_categorizacion_workbook(path, int(match.group(1)))
    else:
        raise ValueError(f"RAW de estadísticas hospitalarias no reconocido: {path.name}")


# --------------------------------------------------------------------------- #
# Descarga y publicación
# --------------------------------------------------------------------------- #

def _download_xlsx(url: str, target: Path) -> dict[str, str]:
    """Descarga a cache (nunca a ``data/raw``) y devuelve cabeceras HTTP observadas."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(f"{target.suffix}.part")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    observed: dict[str, str] = {}
    try:
        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=300) as response, \
                partial.open("wb") as output:
            for header, key in (("Last-Modified", "http_last_modified"), ("ETag", "http_etag")):
                value = response.headers.get(header)
                if value:
                    observed[key] = value
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if partial.stat().st_size == 0:
            raise ValueError("XLSX del REM-20 descargado vacío.")
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return observed


def _snapshot_registered(source_id: str, sha256: str, manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return any(snapshot.get("raw_sha256") == sha256
               for entry in manifest if entry.get("source_id") == source_id
               for snapshot in entry.get("snapshots", []))


def _record(pub: Publicacion, raw_path: Path, headers: dict[str, str], manifest_path: Path) -> None:
    metadata = dict(pub.metadata)
    snapshot_extra: dict[str, Any] = {"filename": raw_path.name, "size": raw_path.stat().st_size,
                                      "sha256": file_sha256(raw_path), **headers}
    if pub.en_curso and pub.meses is not None:
        snapshot_extra["corte_mes"] = pub.meses
    record_raw_snapshot(pub.source_id, pub.url, raw_path, transport=snapshot_extra,
                        source_metadata=metadata, manifest_path=manifest_path)


def _publish(candidate: Path, raw_path: Path, pub: Publicacion, headers: dict[str, str],
             manifest_path: Path) -> None:
    """Publica el candidato y su procedencia como una unidad, con rollback del RAW previo."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    backup = candidate.parent / f"previous_{raw_path.name}"
    had_previous = raw_path.exists()
    try:
        if had_previous:
            os.replace(raw_path, backup)
        os.replace(candidate, raw_path)
        _record(pub, raw_path, headers, manifest_path)
    except Exception:
        raw_path.unlink(missing_ok=True)
        if had_previous and backup.exists():
            os.replace(backup, raw_path)
        raise
    finally:
        backup.unlink(missing_ok=True)


def ingest_publicacion(
    pub: Publicacion, *, raw_dir: Path, cache_dir: Path, manifest_path: Path = MANIFEST_PATH,
    force: bool = False, download: Callable[[str, Path], dict[str, str]] = _download_xlsx,
) -> bool:
    """Descarga, valida y publica un libro; devuelve si publicó un snapshot nuevo."""
    raw_path = raw_dir / pub.archivo
    if raw_path.is_file() and raw_path.stat().st_size > 0 and not force:
        validate_raw_file(raw_path)
        logger.info("[SKIP] RAW REM-20 válido: %s", raw_path.as_posix())
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=cache_dir, prefix="rem20_", suffix=".xlsx") as temp:
        candidate = Path(temp.name)
    try:
        headers = download(pub.url, candidate)
        validate_publicacion(pub, candidate)
        if pub.en_curso and pub.familia == "indicadores" and raw_path.is_file():
            vigente = max(indicadores_periods(raw_path).values())
            if pub.meses is not None and pub.meses < vigente:
                logger.warning("El corte publicado de %s (%s meses) es anterior al RAW vigente (%s meses): "
                               "no se reemplaza.", pub.archivo, pub.meses, vigente)
                return False
        candidate_hash = file_sha256(candidate)
        if raw_path.is_file() and file_sha256(raw_path) == candidate_hash:
            if not _snapshot_registered(pub.source_id, candidate_hash, manifest_path):
                _record(pub, raw_path, headers, manifest_path)
            logger.info("RAW REM-20 sin cambios respecto de la fuente: %s", raw_path.as_posix())
            return False
        _publish(candidate, raw_path, pub, headers, manifest_path)
        logger.info("RAW REM-20 publicado: %s", raw_path.as_posix())
        return True
    finally:
        candidate.unlink(missing_ok=True)


def ingest_all(
    *, force: bool = False, config: dict[str, Any] | None = None, now: datetime | None = None,
    raw_dir: Path | None = None, cache_dir: Path | None = None, manifest_path: Path = MANIFEST_PATH,
    probe: Callable[[str], bool] = head_exists,
    download: Callable[[str, Path], dict[str, str]] = _download_xlsx,
) -> dict[str, str]:
    """Procesa cada libro de forma independiente; devuelve el error por libro fallido.

    Los años en curso se consultan en la fuente solo si su RAW falta o con ``--force``.
    """
    config = config or load_config()
    raw_dir = raw_dir or Path(config["raw_dir"])
    cache_dir = cache_dir or Path(config["cache_dir"])
    publicaciones = closed_publications(config)
    errors: dict[str, str] = {}

    en_curso_raw = [raw_dir / config["indicadores"]["en_curso"]["plantilla_archivo"].format(ano=ano)
                    for ano in current_years(config, now)]
    if force or not all(path.is_file() for path in en_curso_raw):
        try:
            encontrados, sin_publicar = discover_current(config, now=now, probe=probe)
            publicaciones += encontrados
            for ano in sin_publicar:
                path = raw_dir / config["indicadores"]["en_curso"]["plantilla_archivo"].format(ano=ano)
                if ano < current_year_chile(now) and not path.is_file():
                    errors[f"indicadores_{ano}"] = (f"No se encontró ningún mes publicado de {ano} con la "
                                                    "plantilla de URL configurada.")
                else:
                    logger.warning("El DEIS aún no publica indicadores de %s con la plantilla configurada.", ano)
        except Exception as error:
            logger.error("No se pudo consultar el año en curso del REM-20: %s", error)
            errors["descubrimiento_en_curso"] = str(error)

    for pub in publicaciones:
        try:
            ingest_publicacion(pub, raw_dir=raw_dir, cache_dir=cache_dir, manifest_path=manifest_path,
                               force=force or pub.en_curso, download=download)
        except Exception as error:  # un libro fallido no impide publicar los demás
            logger.error("Fallo de ingesta REM-20 (%s): %s", pub.archivo, error)
            errors[pub.archivo] = str(error)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga segura de las Estadísticas Hospitalarias REM-20 (DEIS).")
    parser.add_argument("--force", action="store_true",
                        help="Vuelve a consultar todas las fuentes, incluido el último corte del año en curso.")
    args = parser.parse_args()
    if ingest_all(force=args.force):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
