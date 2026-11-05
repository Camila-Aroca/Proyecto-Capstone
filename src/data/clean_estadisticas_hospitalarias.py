"""Limpieza de las Estadísticas Hospitalarias del REM-20 (DEIS): RAW XLSX -> Parquet.

Salidas en ``data/processed/estadisticas_hospitalarias/``, una por familia de libros
(los libros de una familia comparten columnas; se apilan con el año y, en la
categorización, el trimestre):

- ``indicadores_hospitalarios_snss.parquet``: las columnas del libro de
  indicadores (Servicio de Salud, establecimiento, nivel de cuidado, indicador,
  acumulado y un mes por columna) con **solo las filas de detalle**: un nivel de
  cuidado (área funcional) de un establecimiento. Las filas agregadas que el libro
  intercala con el detalle (``Datos País``, ``Datos Servicio Salud`` y ``Datos
  Establecimiento``) **no entran al Parquet**: sumarlas junto al detalle contaría
  dos o tres veces lo mismo. Se usan para validar que el detalle reconstruye cada
  agregado publicado; una discrepancia se informa, nunca se corrige.
- ``categorizacion_riesgo_dependencia.parquet``: el libro trimestral de
  categorización CUDYR, que es jerárquico (región, Servicio de Salud,
  establecimiento y nivel de cuidado en una sola columna), aplanado a una fila por
  nivel de cuidado de un establecimiento, con el total y las 12 categorías A1-D3.
  El libro no trae filas de totales agregados; ``total`` es el de la fila, y se
  valida que sea la suma de las 12 categorías.

Advertencias que deben acompañar cualquier uso (ver el diccionario):

- En el Parquet de indicadores conviven **conteos** (días cama disponibles y
  ocupados, días de estada, egresos, fallecidos, traslados), un **promedio**
  (camas disponibles) y **razones** (índice ocupacional, promedio de días de
  estada, índice de rotación, letalidad). Solo los conteos se suman entre áreas o
  meses; ``acumulado`` de una razón es la razón del año, no una suma.
- El año en curso trae solo los meses ya publicados: los siguientes quedan nulos,
  no en cero.

Principios (``.agents/rules.md``): no se imputa ni se corrige nada. Un blanco queda
nulo. Toda fila del origen debe responder a un patrón conocido; si no, si un valor
no es numérico, si un indicador no es uno de los conocidos o si una fila repite la
llave lógica de otra, la etapa falla en vez de descartar o elegir en silencio.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import unicodedata

from openpyxl import load_workbook
import pyarrow as pa
import pyarrow.parquet as pq

from src.data import download_estadisticas_hospitalarias as download
from src.data.raw_provenance import file_sha256


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/processed/estadisticas_hospitalarias")
INDICADORES_FILENAME = "indicadores_hospitalarios_snss.parquet"
CATEGORIZACION_FILENAME = "categorizacion_riesgo_dependencia.parquet"
RAW_HASHES_METADATA_KEY = b"raw_sha256_por_archivo"
ZSTD_LEVEL = 19

MESES_COLUMNAS = tuple(mes.lower() for mes in download.MESES_CORTOS)

# Indicadores publicados, con su naturaleza. Solo los conteos son aditivos.
CONTEOS = ("Dias Cama Disponibles", "Dias Cama Ocupados", "Dias de Estada",
           "Numero de Egresos", "Egresos Fallecidos", "Traslados")
PROMEDIOS = ("Promedio Cama Disponibles",)
RAZONES = ("Indice Ocupacional", "Promedio Días de Estada", "Indice de Rotación", "Letalidad")
INDICADORES = (*CONTEOS, *PROMEDIOS, *RAZONES)

# Etiquetas con que el libro marca sus filas agregadas.
ETIQUETA_PAIS = "Datos País"
ETIQUETA_SERVICIO = "Datos Servicio Salud"
ETIQUETA_ESTABLECIMIENTO = "Datos Establecimiento"

# El promedio de camas se publica con 2 decimales en cada fila: la suma de las áreas
# puede diferir del total publicado solo por redondeo, hasta 0,005 por área sumada.
TOLERANCIA_REDONDEO_POR_FILA = 0.005

INDICADORES_SCHEMA = pa.schema([
    ("ano", pa.int32()),
    ("servicio_salud_codigo", pa.int32()),
    ("servicio_salud", pa.string()),
    ("establecimiento_codigo", pa.int64()),
    ("establecimiento_nombre", pa.string()),
    ("nivel_cuidado_codigo", pa.int32()),
    ("nivel_cuidado", pa.string()),
    ("indicador", pa.string()),
    ("acumulado", pa.float64()),
    *[(mes, pa.float64()) for mes in MESES_COLUMNAS],
])
INDICADORES_KEY = ("ano", "servicio_salud_codigo", "establecimiento_codigo", "nivel_cuidado_codigo", "indicador")

CATEGORIZACION_SCHEMA = pa.schema([
    ("ano", pa.int32()),
    ("trimestre", pa.int32()),
    ("region", pa.string()),
    ("servicio_salud", pa.string()),
    ("establecimiento_nombre", pa.string()),
    ("nivel_cuidado_codigo", pa.int32()),
    ("nivel_cuidado", pa.string()),
    ("total", pa.int64()),
    *[(categoria.lower(), pa.int64()) for categoria in download.CATEGORIAS],
])
CATEGORIZACION_KEY = ("ano", "trimestre", "servicio_salud", "establecimiento_nombre", "nivel_cuidado_codigo")

_NIVEL = re.compile(r"^(\d{3}) - (.+)$")


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

def _text(value: Any) -> str | None:
    """NFC, espacios colapsados (incluido el duro) y recortados; vacío -> None."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value)).replace("\xa0", " ")).strip()
    return text or None


def _number(value: Any, where: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: valor no numérico {value!r}.")
    return float(value)


def _code(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) != int(value):
        raise ValueError(f"{where}: código entero esperado, se encontró {value!r}.")
    return int(value)


def _count(value: Any, where: str) -> int:
    number = _number(value, where)
    if number is None or number < 0 or number != int(number):
        raise ValueError(f"{where}: se esperaba un conteo entero no negativo, se encontró {value!r}.")
    return int(number)


def _assert_unique(rows: list[dict[str, Any]], key: tuple[str, ...], label: str) -> None:
    if not rows:
        raise ValueError(f"{label}: no produjo ninguna fila.")
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        identity = tuple(row[column] for column in key)
        if identity in seen:
            raise ValueError(f"{label}: fila duplicada para {dict(zip(key, identity))}.")
        seen.add(identity)


# --------------------------------------------------------------------------- #
# Indicadores hospitalarios
# --------------------------------------------------------------------------- #

@dataclass
class Indicadores:
    """Lo leído de los libros de indicadores: detalle (Parquet) y agregados (validación)."""

    detalle: list[dict[str, Any]] = field(default_factory=list)
    agregados: list[dict[str, Any]] = field(default_factory=list)  # con la clave "nivel_agregado"
    meses_por_ano: dict[int, int] = field(default_factory=dict)


def parse_indicadores(path: Path) -> Indicadores:
    """Clasifica cada fila de cada hoja por sus códigos y etiquetas; falla ante lo desconocido."""
    periods = download.indicadores_periods(path)
    resultado = Indicadores(meses_por_ano=dict(periods))
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(min_row=1, values_only=True)
            first = [tuple(next(rows, ())) for _ in range(download.HEADER_ROW)]
            ano = download._title_year(first, f"{path.name}, hoja {sheet.title!r}")
            meses = periods[ano]
            width = len(download.INDICADORES_COLUMNS) + meses
            for number, row in enumerate(rows, start=download.HEADER_ROW + 1):
                row = tuple(row)
                where = f"{path.name}, hoja {sheet.title!r}, fila {number}"
                if not any(cell is not None for cell in row):
                    continue
                if any(cell is not None for cell in row[width:]):
                    raise ValueError(f"{where}: datos fuera de las columnas contempladas.")
                ss_cod, ss, est_cod, est, niv_cod, niv, glosa, acum = row[:8]
                ss_cod = _code(ss_cod, where)
                est_cod = _code(est_cod, where)
                niv_cod = _code(niv_cod, where)
                indicador = _text(glosa)
                if indicador not in INDICADORES:
                    raise ValueError(f"{where}: indicador no reconocido {glosa!r}.")
                valores = {"acumulado": _number(acum, where)}
                for index, mes in enumerate(MESES_COLUMNAS):
                    valores[mes] = _number(row[8 + index], where) if index < meses else None
                base = {"ano": ano, "servicio_salud_codigo": ss_cod, "servicio_salud": _text(ss),
                        "establecimiento_codigo": est_cod, "establecimiento_nombre": _text(est),
                        "nivel_cuidado_codigo": niv_cod, "nivel_cuidado": _text(niv),
                        "indicador": indicador, **valores}
                if ss_cod == 0 and est_cod == 0 and niv_cod == 0 and _text(ss) == ETIQUETA_PAIS:
                    resultado.agregados.append({**base, "nivel_agregado": "pais"})
                elif ss_cod > 0 and est_cod == 0 and niv_cod == 0 and _text(est) == ETIQUETA_SERVICIO:
                    resultado.agregados.append({**base, "nivel_agregado": "servicio"})
                elif ss_cod > 0 and est_cod > 0 and niv_cod == 0 and _text(niv) == ETIQUETA_ESTABLECIMIENTO:
                    resultado.agregados.append({**base, "nivel_agregado": "establecimiento"})
                elif ss_cod > 0 and est_cod > 0 and niv_cod > 0 and _text(niv) and _text(est):
                    resultado.detalle.append(base)
                else:
                    raise ValueError(f"{where}: estructura no reconocida {list(row[:7])!r}.")
    finally:
        workbook.close()
    return resultado


def _sumar(rows: list[dict[str, Any]], columnas: tuple[str, ...]) -> dict[str, float | None]:
    salida: dict[str, float | None] = {}
    for columna in columnas:
        valores = [row[columna] for row in rows if row[columna] is not None]
        salida[columna] = sum(valores) if valores else None
    return salida


def reconcile_indicadores(datos: Indicadores) -> dict[str, Any]:
    """Contrasta el detalle con cada agregado publicado y el acumulado con sus meses.

    Solo para conteos y el promedio de camas (aditivo entre áreas mes a mes). Devuelve
    las discrepancias con los valores publicado y reconstruido; no corrige nada. El
    acumulado anual del promedio se informa aparte: no es aditivo entre áreas.
    """
    columnas = ("acumulado", *MESES_COLUMNAS)
    aditivos = (*CONTEOS, *PROMEDIOS)
    detalle = [row for row in datos.detalle if row["indicador"] in aditivos]
    agregados = [row for row in datos.agregados if row["indicador"] in aditivos]

    por_establecimiento: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in detalle:
        por_establecimiento[(row["ano"], row["servicio_salud_codigo"], row["establecimiento_codigo"],
                             row["indicador"])].append(row)
    reconstruido: dict[str, dict[tuple[Any, ...], tuple[dict[str, float | None], int]]] = {
        "establecimiento": {key: (_sumar(rows, columnas), len(rows)) for key, rows in por_establecimiento.items()},
    }
    por_servicio: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for (ano, ss, _est, indicador), rows in por_establecimiento.items():
        por_servicio[(ano, ss, 0, indicador)].extend(rows)
    reconstruido["servicio"] = {key: (_sumar(rows, columnas), len(rows)) for key, rows in por_servicio.items()}
    por_pais: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for (ano, _ss, _est, indicador), rows in por_establecimiento.items():
        por_pais[(ano, 0, 0, indicador)].extend(rows)
    reconstruido["pais"] = {key: (_sumar(rows, columnas), len(rows)) for key, rows in por_pais.items()}

    discrepancias: list[dict[str, Any]] = []
    promedio_acumulado: list[dict[str, Any]] = []
    comparados: dict[str, int] = defaultdict(int)
    for row in agregados:
        nivel = row["nivel_agregado"]
        key = (row["ano"], row["servicio_salud_codigo"], row["establecimiento_codigo"], row["indicador"])
        suma, n_filas = reconstruido[nivel].get(key, ({c: None for c in columnas}, 0))
        tolerancia = TOLERANCIA_REDONDEO_POR_FILA * n_filas if row["indicador"] in PROMEDIOS else 0.0
        comparados[nivel] += 1
        for columna in columnas:
            publicado, calculado = row[columna], suma[columna]
            if publicado is None and calculado is None:
                continue
            if publicado is None or calculado is None or abs(publicado - calculado) > tolerancia + 1e-9:
                item = {"nivel_agregado": nivel, "ano": row["ano"],
                        "servicio_salud_codigo": row["servicio_salud_codigo"],
                        "establecimiento_codigo": row["establecimiento_codigo"],
                        "indicador": row["indicador"], "columna": columna,
                        "publicado": publicado, "suma_detalle": calculado}
                # El promedio anual no es aditivo entre áreas: según el área, la fuente
                # divide los días cama disponibles del año por los días del año o por los
                # días de los meses en que el área funcionó. Es definición, no error.
                es_definicion = row["indicador"] in PROMEDIOS and columna == "acumulado"
                (promedio_acumulado if es_definicion else discrepancias).append(item)

    acumulado_vs_meses = []
    for row in [*datos.detalle, *datos.agregados]:
        if row["indicador"] not in CONTEOS:
            continue
        meses = [row[mes] for mes in MESES_COLUMNAS if row[mes] is not None]
        suma = sum(meses) if meses else None
        if row["acumulado"] != suma:
            acumulado_vs_meses.append({key: row[key] for key in
                                       ("ano", "establecimiento_codigo", "nivel_cuidado_codigo", "indicador",
                                        "acumulado")} | {"suma_meses": suma})
    return {"agregados_comparados": dict(comparados), "discrepancias_agregados": discrepancias,
            "promedio_acumulado_no_aditivo": promedio_acumulado,
            "acumulado_distinto_de_meses": acumulado_vs_meses}


# --------------------------------------------------------------------------- #
# Categorización según riesgo-dependencia
# --------------------------------------------------------------------------- #

def parse_categorizacion(path: Path, ano: int, trimestre: int) -> list[dict[str, Any]]:
    """Aplana la jerarquía región > Servicio de Salud > establecimiento > nivel de cuidado.

    Una fila con valores debe ser un nivel de cuidado (``NNN - nombre``). Una fila
    sin valores es: un Servicio de Salud si empieza con ``SS ``; una región si la
    siguiente fila con texto es un Servicio de Salud; si no, un establecimiento.
    """
    download.validate_categorizacion_workbook(path, ano)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = [tuple(row) for row in workbook.worksheets[0].iter_rows(
            min_row=download.HEADER_ROW + 1, values_only=True)]
    finally:
        workbook.close()
    width = len(download.CATEGORIZACION_COLUMNS)
    labelled = [(number, row) for number, row in enumerate(rows, start=download.HEADER_ROW + 1)
                if any(cell is not None for cell in row)]
    salida: list[dict[str, Any]] = []
    region = servicio = establecimiento = None
    for position, (number, row) in enumerate(labelled):
        where = f"{path.name}, fila {number}"
        if any(cell is not None for cell in row[width:]):
            raise ValueError(f"{where}: datos fuera de las columnas contempladas.")
        etiqueta = _text(row[0])
        if etiqueta is None:
            raise ValueError(f"{where}: valores sin etiqueta de establecimiento o nivel.")
        tiene_valores = any(cell is not None for cell in row[1:width])
        nivel = _NIVEL.match(etiqueta)
        if tiene_valores:
            if nivel is None:
                raise ValueError(f"{where}: fila con valores que no es un nivel de cuidado ({etiqueta!r}).")
            if establecimiento is None or servicio is None:
                raise ValueError(f"{where}: nivel de cuidado sin establecimiento previo.")
            total = _count(row[1], where)
            categorias = {c.lower(): _count(row[2 + i], where) for i, c in enumerate(download.CATEGORIAS)}
            salida.append({"ano": ano, "trimestre": trimestre, "region": region, "servicio_salud": servicio,
                           "establecimiento_nombre": establecimiento, "nivel_cuidado_codigo": int(nivel.group(1)),
                           "nivel_cuidado": etiqueta, "total": total, **categorias})
            continue
        if nivel is not None:
            raise ValueError(f"{where}: nivel de cuidado sin valores ({etiqueta!r}).")
        siguiente = next((_text(r[0]) for _, r in labelled[position + 1:position + 2]), None)
        if etiqueta.startswith("SS "):
            if region is None:
                raise ValueError(f"{where}: Servicio de Salud sin región previa.")
            servicio, establecimiento = etiqueta, None
        elif siguiente is not None and siguiente.startswith("SS "):
            region, servicio, establecimiento = etiqueta, None, None
        else:
            if servicio is None:
                raise ValueError(f"{where}: establecimiento sin Servicio de Salud previo.")
            establecimiento = etiqueta
    return salida


def reconcile_categorizacion(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filas cuyo total publicado no es la suma de sus 12 categorías."""
    return [{key: row[key] for key in CATEGORIZACION_KEY} | {"total": row["total"],
             "suma_categorias": sum(row[c.lower()] for c in download.CATEGORIAS)}
            for row in rows if row["total"] != sum(row[c.lower()] for c in download.CATEGORIAS)]


# --------------------------------------------------------------------------- #
# Publicaciones vigentes y escritura
# --------------------------------------------------------------------------- #

def raw_inputs(config: dict[str, Any] | None = None) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    """RAW a procesar por familia, con año/trimestre; exige los requeridos por la descarga."""
    config = config or download.load_config()
    raw_dir = Path(config["raw_dir"])
    required = download.required_raw_paths(config)
    missing = [path.as_posix() for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Faltan RAW de estadísticas hospitalarias: {missing}")
    cerrados = {pub.archivo: pub for pub in download.closed_publications(config)}
    familias: dict[str, list[tuple[Path, dict[str, Any]]]] = {"indicadores": [], "categorizacion": []}
    for path in required:
        if path.name in cerrados:
            pub = cerrados[path.name]
            if pub.familia == "diccionario":
                continue  # documentación de campos: no es un libro de datos
            info = {"anos": pub.anos, "trimestre": pub.trimestre}
            familia = pub.familia
        elif match := download._EN_CURSO_INDICADORES.match(path.name):
            info, familia = {"anos": (int(match.group(1)),), "trimestre": None}, "indicadores"
        elif match := download._EN_CURSO_CATEGORIZACION.match(path.name):
            info = {"anos": (int(match.group(1)),), "trimestre": int(match.group(2))}
            familia = "categorizacion"
        else:
            raise ValueError(f"RAW no reconocido: {path.name}")
        familias[familia].append((raw_dir / path.name, info))
    return familias


def raw_hashes(paths: list[Path]) -> dict[str, str]:
    return {path.as_posix(): file_sha256(path) for path in sorted(paths)}


def _table(rows: list[dict[str, Any]], schema: pa.Schema, hashes: dict[str, str]) -> pa.Table:
    table = pa.Table.from_pylist(rows, schema=schema)
    return table.replace_schema_metadata({RAW_HASHES_METADATA_KEY: json.dumps(hashes, sort_keys=True).encode()})


def _write_all(tables: dict[Path, pa.Table]) -> None:
    """Escribe todas las salidas en temporales y las publica juntas, con rollback."""
    directory = next(iter(tables)).parent
    directory.mkdir(parents=True, exist_ok=True)
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for target, table in tables.items():
            with tempfile.NamedTemporaryFile(delete=False, dir=directory, prefix=f".{target.name}.",
                                             suffix=".tmp") as temp:
                temporary = Path(temp.name)
            staged[target] = temporary
            pq.write_table(table, temporary, compression="zstd", compression_level=ZSTD_LEVEL)
            if pq.read_metadata(temporary).num_rows != table.num_rows:
                raise ValueError(f"{target.name}: la relectura no coincide en filas.")
        for target, temporary in staged.items():
            if target.exists():
                backup = directory / f".{target.name}.previous"
                os.replace(target, backup)
                backups[target] = backup
            os.replace(temporary, target)
            published.append(target)
    except Exception:
        for target in published:
            target.unlink(missing_ok=True)
        for target, backup in backups.items():
            if backup.exists():
                os.replace(backup, target)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)


def read_inputs(config: dict[str, Any] | None = None) -> tuple[Indicadores, list[dict[str, Any]], dict[str, Any]]:
    """Lee y valida todos los RAW vigentes: indicadores, categorización y sus hashes."""
    familias = raw_inputs(config)
    indicadores = Indicadores()
    for path, info in familias["indicadores"]:
        datos = parse_indicadores(path)
        if sorted(datos.meses_por_ano) != sorted(info["anos"]):
            raise ValueError(f"{path.name}: años {sorted(datos.meses_por_ano)} distintos de {list(info['anos'])}.")
        repetidos = set(datos.meses_por_ano) & set(indicadores.meses_por_ano)
        if repetidos:
            raise ValueError(f"{path.name}: años {sorted(repetidos)} ya leídos de otro libro.")
        indicadores.detalle += datos.detalle
        indicadores.agregados += datos.agregados
        indicadores.meses_por_ano.update(datos.meses_por_ano)
    categorizacion: list[dict[str, Any]] = []
    for path, info in familias["categorizacion"]:
        categorizacion += parse_categorizacion(path, info["anos"][0], info["trimestre"])
    hashes = {
        "indicadores": raw_hashes([path for path, _ in familias["indicadores"]]),
        "categorizacion": raw_hashes([path for path, _ in familias["categorizacion"]]),
    }
    return indicadores, categorizacion, hashes


def build_estadisticas_hospitalarias(output_dir: Path = OUTPUT_DIR,
                                     config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Genera los dos Parquet de forma validada y atómica; informa las discrepancias."""
    indicadores, categorizacion, hashes = read_inputs(config)
    _assert_unique(indicadores.detalle, INDICADORES_KEY, "Indicadores hospitalarios")
    _assert_unique(categorizacion, CATEGORIZACION_KEY, "Categorización riesgo-dependencia")

    conciliacion = reconcile_indicadores(indicadores)
    for item in conciliacion["discrepancias_agregados"][:20]:
        logger.warning("Agregado %(nivel_agregado)s %(ano)s, SS %(servicio_salud_codigo)s, establecimiento "
                       "%(establecimiento_codigo)s, %(indicador)s, %(columna)s: publicado %(publicado)s, "
                       "suma del detalle %(suma_detalle)s.", item)
    totales = reconcile_categorizacion(categorizacion)
    for item in totales[:20]:
        logger.warning("Categorización: total distinto de la suma de categorías: %s", item)

    tables = {
        output_dir / INDICADORES_FILENAME: _table(indicadores.detalle, INDICADORES_SCHEMA, hashes["indicadores"]),
        output_dir / CATEGORIZACION_FILENAME: _table(categorizacion, CATEGORIZACION_SCHEMA,
                                                     hashes["categorizacion"]),
    }
    _write_all(tables)
    return {
        "archivos_generados": [path.as_posix() for path in tables],
        "filas_indicadores": len(indicadores.detalle),
        "filas_agregadas_excluidas": len(indicadores.agregados),
        "filas_categorizacion": len(categorizacion),
        "meses_por_ano": dict(sorted(indicadores.meses_por_ano.items())),
        "agregados_comparados": conciliacion["agregados_comparados"],
        "discrepancias_agregados": len(conciliacion["discrepancias_agregados"]),
        "promedio_acumulado_no_aditivo": len(conciliacion["promedio_acumulado_no_aditivo"]),
        "acumulado_distinto_de_meses": len(conciliacion["acumulado_distinto_de_meses"]),
        "categorizacion_total_distinto": len(totales),
    }


def validate_output(path: Path) -> None:
    """Contrato de SKIP: esquema exacto y footer alineado con los RAW vigentes."""
    schema = {INDICADORES_FILENAME: INDICADORES_SCHEMA, CATEGORIZACION_FILENAME: CATEGORIZACION_SCHEMA}[path.name]
    observed = pq.read_schema(path)
    if observed.remove_metadata() != schema:
        raise ValueError(f"{path.name}: esquema distinto del esperado.")
    stored = (observed.metadata or {}).get(RAW_HASHES_METADATA_KEY)
    if stored is None:
        raise ValueError(f"{path.name}: sin hashes de sus RAW en el footer.")
    familia = "indicadores" if path.name == INDICADORES_FILENAME else "categorizacion"
    actuales = raw_hashes([raw for raw, _ in raw_inputs()[familia]])
    if json.loads(stored) != actuales:
        raise ValueError(f"{path.name}: generado desde RAW distintos de los vigentes.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Limpia las Estadísticas Hospitalarias REM-20 (DEIS) a Parquet.")
    parser.add_argument("--force", action="store_true", help="Aceptado para interoperar con el orquestador.")
    parser.parse_args()
    logger.info("Estadísticas hospitalarias generadas: %s", build_estadisticas_hospitalarias())


if __name__ == "__main__":
    main()
