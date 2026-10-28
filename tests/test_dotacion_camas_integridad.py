"""Verificación de que la limpieza de dotación de camas no perdió datos de dotación.

Compara los dos Parquet de ``data/processed/camas/`` con los libros reales de
``data/raw/camas/``, leyendo estos últimos por una ruta distinta a la del parser
(libro completo, celda por celda por coordenada), de modo que el código no se
verifique con su propia lectura. Requiere los datos locales; se ejecuta con
``pytest -m data_integration``.

1. Hacia adelante: cada fila del libro tiene su fila en el Parquet, con las mismas
   etiquetas y las mismas camas por año; y el Parquet no trae filas de más.
2. Hacia atrás: toda celda con contenido del libro está contabilizada: es una
   etiqueta o un valor de una fila de datos, el total nacional, una nota al pie o
   una marca de nota; nada queda sin explicar.
3. Agregados: conteos, sumas, códigos de establecimiento, totales nacionales y
   procedencia, calculados desde el libro sin pasar por el parser.
"""

import json
from pathlib import Path
from typing import Any

import openpyxl
import pyarrow.parquet as pq
import pytest

import src.data.clean_dotacion_camas as module
import src.data.download_dotacion_camas as download
from src.data.raw_provenance import file_sha256

Grid = dict[tuple[int, int], Any]
HEADER_LAST_ROW = 3


def _norm(value: Any) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _name(value: Any) -> str:
    return _norm(value).rstrip("*").strip()


def _camas(value: Any) -> int | None:
    """Camas de una celda: entero, o None si está en blanco o es una marca de asteriscos."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    assert isinstance(value, str) and set(value.strip()) == {"*"}, f"celda de valor inesperada: {value!r}"
    return None


def _load_grids(path: Path) -> dict[str, Grid]:
    """Cada celda con contenido por (fila, columna), con el libro completo en memoria."""
    workbook = openpyxl.load_workbook(path, read_only=False, data_only=True)
    try:
        return {
            sheet.title: {
                (cell.row, cell.column): cell.value
                for row in sheet.iter_rows() for cell in row
                if cell.value is not None and not (isinstance(cell.value, str) and not cell.value.strip())
            }
            for sheet in workbook.worksheets
        }
    finally:
        workbook.close()


def _hospital_row(cells: Grid, row: int) -> int:
    """Fila del hospital de ``row``: la misma o la anterior con código en la columna B."""
    for candidate in range(row, 0, -1):
        if (candidate, 2) in cells:
            return candidate
    raise AssertionError(f"fila {row} sin hospital previo")


def _classify(cells: Grid, area_column: int) -> tuple[list[int], list[int], list[int]]:
    """(filas de datos, filas de total nacional, filas de nota al pie) de una hoja."""
    rows = sorted({r for (r, _c) in cells if r > HEADER_LAST_ROW})
    data = [r for r in rows if isinstance(cells.get((r, 2)), int)
            or ((r, 2) not in cells and (r, area_column) in cells)]
    last_data = max(data)
    national = [r for r in rows if r not in data and r <= last_data]
    notes = [r for r in rows if r > last_data]
    return data, national, notes


@pytest.fixture(scope="module")
def audit() -> dict[str, Any]:
    raws = {"snss": module.RAW_SNSS_PATH, "no_snss": module.RAW_NO_SNSS_PATH}
    outputs = {"snss": module.OUTPUT_DIR / module.SNSS_FILENAME, "no_snss": module.OUTPUT_DIR / module.NO_SNSS_FILENAME}
    for path in (*raws.values(), *outputs.values()):
        assert path.exists(), f"Falta {path.as_posix()}; ejecutar download_dotacion_camas y clean_dotacion_camas."
    return {
        "raws": raws, "outputs": outputs,
        "grids": {key: _load_grids(path) for key, path in raws.items()},
        "rows": {key: pq.read_table(path).to_pylist() for key, path in outputs.items()},
    }


def _snss_expected(cells: Grid) -> tuple[dict[tuple, dict], dict[int, int | None], list[int]]:
    """Filas esperadas del libro SNSS por llave (servicio, código, área) y su total nacional por año."""
    year_of = {c: int(str(cells[(HEADER_LAST_ROW, c)]).strip().rstrip("*")) for c in range(7, 23)}
    data, national, notes = _classify(cells, area_column=5)
    expected: dict[tuple, dict] = {}
    for row in data:
        hospital = _hospital_row(cells, row)
        key = (_norm(cells[(row, 1)]), cells[(hospital, 2)], cells[(row, 5)])
        assert key not in expected, f"llave repetida en el libro: {key}"
        expected[key] = {
            "tipo": _norm(cells[(hospital, 3)]), "nombre": _name(cells[(hospital, 4)]),
            "area": _norm(cells[(row, 6)]),
            "camas": {year_of[c]: _camas(cells.get((row, c))) for c in range(7, 23)},
        }
    assert len(national) == 1
    national_totals = {year_of[c]: _camas(cells.get((national[0], c))) for c in range(7, 23)}
    return expected, national_totals, notes


@pytest.mark.data_integration
def test_1_forward_snss_every_workbook_row_is_in_the_parquet_with_the_same_values(audit: dict[str, Any]) -> None:
    cells = audit["grids"]["snss"][download.SNSS_SHEET]
    expected, _, _ = _snss_expected(cells)
    rows = audit["rows"]["snss"]
    assert len(rows) == len(expected), "el Parquet no debe tener filas de más ni de menos"
    by_key = {(r["servicio_salud"], r["establecimiento_codigo"], r["area_funcional_codigo"]): r for r in rows}
    assert len(by_key) == len(rows)
    for key, want in expected.items():
        got = by_key[key]
        assert got["tipo_establecimiento"] == want["tipo"], key
        assert got["establecimiento_nombre"] == want["nombre"], key
        assert got["area_funcional"] == want["area"], key
        for year, value in want["camas"].items():
            assert got[f"camas_{year}"] == value, (key, year)


@pytest.mark.data_integration
def test_1_forward_no_snss_every_workbook_row_is_in_the_parquet_with_the_same_values(audit: dict[str, Any]) -> None:
    expected: dict[tuple, dict] = {}
    for sheet, cells in audit["grids"]["no_snss"].items():
        data, national, notes = _classify(cells, area_column=4)
        assert len(national) == 1 and cells[(national[0], 1)] == "TOTAL"
        assert _norm(cells[(HEADER_LAST_ROW, 6)]) == f"Total {sheet}"
        for row in data:
            hospital = _hospital_row(cells, row)
            area = cells.get((row, 4))
            key = (int(sheet), _norm(cells[(hospital, 1)]), cells[(hospital, 2)], area)
            assert key not in expected, f"llave repetida en el libro: {key}"
            expected[key] = {"nombre": _name(cells[(hospital, 3)]),
                             "area": _norm(cells[(row, 5)]) if area is not None else None,
                             "camas": _camas(cells.get((row, 6)))}
    rows = audit["rows"]["no_snss"]
    assert len(rows) == len(expected), "el Parquet no debe tener filas de más ni de menos"
    by_key = {(r["ano"], r["seremi"], r["establecimiento_codigo"], r["area_funcional_codigo"]): r for r in rows}
    assert len(by_key) == len(rows)
    for key, want in expected.items():
        got = by_key[key]
        assert (got["establecimiento_nombre"], got["area_funcional"], got["camas"]) == (
            want["nombre"], want["area"], want["camas"]), key


@pytest.mark.data_integration
def test_2_backward_every_nonempty_workbook_cell_is_accounted_for(audit: dict[str, Any]) -> None:
    unexplained = []
    for key, area_column, value_columns in (("snss", 5, range(7, 23)), ("no_snss", 4, (6,))):
        for sheet, cells in audit["grids"][key].items():
            assert str(cells[(1, 1)]).upper().startswith(("DOTACI", "DATO REFERENCIAL")), sheet
            assert str(cells[(2, 1)]).startswith("Fuente"), sheet
            data, national, notes = _classify(cells, area_column)
            explained_rows = {*data, *national, *notes}
            max_column = 22 if key == "snss" else 6
            for (row, column), value in cells.items():
                if row <= HEADER_LAST_ROW:  # título, fuente y encabezado
                    continue
                if row not in explained_rows:
                    unexplained.append((sheet, row, column, value))
                elif row in notes and column != 1:
                    unexplained.append((sheet, row, column, value))
                elif row in data and column > max_column:
                    # única columna adicional permitida: la anotación de texto "ok" del libro no SNSS
                    if not (key == "no_snss" and isinstance(value, str) and not any(ch.isdigit() for ch in value)):
                        unexplained.append((sheet, row, column, value))
                elif row in data and column in value_columns:
                    _camas(value)  # entero, blanco o marca de asteriscos
    assert unexplained == [], f"Celdas del libro sin explicar: {unexplained[:5]}"


@pytest.mark.data_integration
def test_3_aggregates_match_the_workbooks_without_going_through_the_parser(audit: dict[str, Any]) -> None:
    # --- SNSS
    cells = audit["grids"]["snss"][download.SNSS_SHEET]
    expected, national, _ = _snss_expected(cells)
    rows = audit["rows"]["snss"]
    for year in download.SNSS_YEARS:
        column = [r[f"camas_{year}"] for r in rows]
        raw = [w["camas"][year] for w in expected.values()]
        assert sum(v for v in column if v is not None) == sum(v for v in raw if v is not None), year
        assert sum(v is not None for v in column) == sum(v is not None for v in raw), year
        hospital_totals = sum(r[f"camas_{year}"] or 0 for r in rows if r["area_funcional_codigo"] == 100)
        assert hospital_totals == national[year], f"total nacional SNSS {year}"
    assert {r["establecimiento_codigo"] for r in rows} == {k[1] for k in expected}
    assert sum(r["area_funcional_codigo"] == 100 for r in rows) == sum(k[2] == 100 for k in expected)

    # --- no SNSS
    rows = audit["rows"]["no_snss"]
    raw_values: list[int | None] = []
    for sheet, cells in audit["grids"]["no_snss"].items():
        data, national, _ = _classify(cells, 4)
        raw_values += [_camas(cells.get((r, 6))) for r in data]
        year = int(sheet)
        hospital_total = sum(r["camas"] or 0 for r in rows if r["ano"] == year and r["area_funcional_codigo"] is None)
        assert hospital_total == cells[(national[0], 6)], f"total nacional no SNSS {year}"
        assert sum(r["ano"] == year for r in rows) == len(data), year
    assert sum(v for v in (r["camas"] for r in rows) if v is not None) == sum(v for v in raw_values if v is not None)
    assert sum(r["camas"] is not None for r in rows) == sum(v is not None for v in raw_values)


@pytest.mark.data_integration
def test_3_parquet_files_hold_only_dotacion_and_their_raw_provenance(audit: dict[str, Any]) -> None:
    manifest = json.loads(download.MANIFEST_PATH.read_text(encoding="utf-8"))
    for source in download.CAMAS_SOURCES:
        key = source.key
        current = file_sha256(audit["raws"][key])
        entry = next(item for item in manifest if item["source_id"] == source.source_id)
        assert entry["snapshots"][-1]["raw_sha256"] == current, f"{key}: el RAW cambió desde su descarga"
        metadata = pq.read_schema(audit["outputs"][key]).metadata
        assert set(metadata) - {b"ARROW:schema"} == {b"raw_sha256"}
        assert metadata[b"raw_sha256"].decode() == current, f"{key}: generado desde otro RAW"
        assert not any("*" in str(value) for row in audit["rows"][key] for value in row.values())
