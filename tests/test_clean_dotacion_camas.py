"""Pruebas de la limpieza de dotación de camas hospitalarias (DEIS): RAW XLSX -> 2 Parquet.

Cada libro de ``data/raw/camas/`` produce su propio Parquet canónico, con las
mismas columnas que el libro. Lo que no es dato (notas al pie, totales nacionales
publicados, marcas de celda) va en el footer del Parquet.

Los libros sintéticos reproducen las rarezas observadas en los libros reales:
espacios duros y asteriscos en los nombres, marcas de nota dentro de celdas de
valor, marcas ``ok``, celdas en blanco frente a ceros explícitos, filas de área
con otro nombre que su fila de total y un establecimiento repetido en una hoja.
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import openpyxl
import pyarrow.parquet as pq
import pytest

import scripts.run_pipeline as pipeline
import src.data.clean_dotacion_camas as module
import src.data.download_dotacion_camas as download
from src.data.clean_dotacion_camas import build_dotacion_camas
from src.data.raw_provenance import file_sha256

YEARS = download.SNSS_YEARS  # 2010..2025
NO_SNSS_YEARS = download.NO_SNSS_YEARS  # 2019..2025
CAMAS_COLUMNS = [f"camas_{year}" for year in YEARS]


@pytest.fixture(autouse=True)
def _small_workbooks(monkeypatch) -> None:
    monkeypatch.setattr(download, "SNSS_MIN_ROWS", 3)
    monkeypatch.setattr(download, "NO_SNSS_MIN_ROWS", 3)


# --------------------------------------------------------------------------- #
# Constructores de libros sintéticos
# --------------------------------------------------------------------------- #

def _snss_block(servicio: str, codigo: int, nombre: str, total: list, areas: list,
                tipo: str = "Alta complejidad") -> dict[str, Any]:
    return {"servicio": servicio, "codigo": codigo, "nombre": nombre, "total": total,
            "areas": areas, "tipo": tipo}


def _vals(default: int | None, **overrides: Any) -> list:
    """16 valores 2010..2025; ``overrides`` con claves ``y2014=...``."""
    values: list = [default] * len(YEARS)
    for key, value in overrides.items():
        values[YEARS.index(int(key[1:]))] = value
    return values


def _write_snss(path: Path, blocks: list[dict], *, national: list | None = None,
                notes: tuple[str, ...] = (), extra_rows: tuple[tuple, ...] = ()) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = download.SNSS_SHEET
    sheet.append(["DOTACIÓN DE CAMAS HOSPITALARIAS (título)"])
    sheet.append(["Fuente: DEIS, DIGERA"])
    sheet.append([*download.SNSS_COLUMNS, *[f"{y}*" if y == 2014 else y for y in YEARS]])
    if national is None:
        national = [sum(b["total"][i] for b in blocks if isinstance(b["total"][i], int))
                    for i in range(len(YEARS))]
    sheet.append([None] * 5 + ["Total País", *national])
    for block in blocks:
        sheet.append([block["servicio"], block["codigo"], block["tipo"], block["nombre"],
                      100, "Total", *block["total"]])
        for area in block["areas"]:
            code, glosa, values = area[:3]
            row_name = area[3] if len(area) > 3 else block["nombre"]
            sheet.append([block["servicio"], None, None, row_name, code, glosa, *values])
    sheet.append([None] * 6)
    for note in notes:
        sheet.append([note])
    for row in extra_rows:
        sheet.append(list(row))
    workbook.save(path)
    return path


def _write_no_snss(path: Path, sheets: dict[int, list[dict]], *,
                   notes: dict[int, tuple[str, ...]] | None = None,
                   national: dict[int, int] | None = None,
                   extra_rows: dict[int, tuple[tuple, ...]] | None = None) -> Path:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for year in NO_SNSS_YEARS:
        blocks = sheets.get(year, [])
        sheet = workbook.create_sheet(str(year))
        wide = year >= 2024
        sheet.append(["DATO REFERENCIAL DE DOTACIÓN (título)"])
        sheet.append(["Fuente: DEIS, DIGERA y Super Intendencia de Salud"])
        header = [*download.NO_SNSS_COLUMNS, f"Total {year}"]
        sheet.append(header + ([None] * 6 if wide else []))
        total = (national or {}).get(year)
        if total is None:
            total = sum(b["total"] for b in blocks if isinstance(b.get("total"), int))
        sheet.append(["TOTAL", None, None, None, None, total] + ([None] * 6 if wide else []))
        for block in blocks:
            row = [block["seremi"], block["codigo"], block["nombre"], None, None, block["total"]]
            if wide:
                row += [None] * 5 + [block.get("marca")]
            sheet.append(row)
            for area in block["areas"]:
                code, glosa, value = area[:3]
                row = [None, None, None, code, glosa, value]
                if wide:
                    row += [None] * 5 + [area[3] if len(area) > 3 else None]
                sheet.append(row)
        for note in (notes or {}).get(year, ()):
            sheet.append([note])
        for extra in (extra_rows or {}).get(year, ()):
            sheet.append(list(extra))
    workbook.save(path)
    return path


def _minimal_no_snss(path: Path, sheets: dict[int, list[dict]] | None = None, **kwargs) -> Path:
    base = {2019: [{"seremi": " Arica y Parinacota", "codigo": 101203, "nombre": "Clínica Uno ",
                    "total": 3, "areas": [(404, "Área Médico-Quirúrgico Cuidados Medios", 3)]}]}
    return _write_no_snss(path, sheets if sheets is not None else base, **kwargs)


def _standard_snss(path: Path) -> Path:
    blocks = [
        _snss_block("Arica   ", 101100, "Hospital Uno\xa0\xa0", _vals(10, y2012=None),
                    [(401, "Área Médica  Adulto Cuidados Básicos", _vals(6, y2012=None)),
                     (402, "Área Médica Adulto Cuidados Medios", _vals(4, y2012=None, y2010=0))]),
        _snss_block("Tarapaca", 102100, "Hospital Dos", _vals(5),
                    [(403, "Área Quirúrgico", _vals(5), "Hospital Dos Viejo")]),
        _snss_block("Atacama", 103100, "Hospital Tres**",
                    _vals(7, y2023="*******", y2024="*******", y2025="*******"),
                    [(401, "Área Médica", _vals(7, y2023=None, y2024=None, y2025=None))],
                    tipo="Mediana complejidad"),
        _snss_block("Metropolitano Occidente", 114104, "Hospital Metropolitano (Ex Militar)**",
                    _vals(None, **{f"y{y}": 9 for y in range(2014, 2022)}), []),
        _snss_block("Metropolitano Oriente", 114104, "Hospital Metropolitano (Ex Militar)",
                    _vals(8, **{f"y{y}": None for y in range(2014, 2022)}), []),
    ]
    notes = ("* A partir del año 2014, la agrupación de camas es por áreas funcionales.",
             "** Hospital Tres, nota con referencia en el nombre.",
             "*** Nota sin referencia en la grilla.")
    return _write_snss(path, blocks, notes=notes)


def _build(tmp_path: Path, snss: Path | None = None, no_snss: Path | None = None) -> dict[str, Any]:
    snss = snss or _standard_snss(tmp_path / "snss.xlsx")
    no_snss = no_snss or _minimal_no_snss(tmp_path / "no_snss.xlsx")
    return build_dotacion_camas(snss, no_snss, tmp_path / "processed")


def _snss_rows(tmp_path: Path) -> list[dict]:
    return pq.read_table(tmp_path / "processed" / module.SNSS_FILENAME).to_pylist()


def _no_snss_rows(tmp_path: Path) -> list[dict]:
    return pq.read_table(tmp_path / "processed" / module.NO_SNSS_FILENAME).to_pylist()


def _snss_row(rows: list[dict], codigo: int, area: int, servicio: str | None = None) -> dict:
    matches = [r for r in rows if r["establecimiento_codigo"] == codigo and r["area_funcional_codigo"] == area
               and (servicio is None or r["servicio_salud"] == servicio)]
    assert len(matches) == 1, (codigo, area, servicio, len(matches))
    return matches[0]


# --------------------------------------------------------------------------- #
# Estructura: un Parquet por libro, con las columnas del libro
# --------------------------------------------------------------------------- #

def test_exactly_two_parquet_files_one_per_workbook(tmp_path: Path) -> None:
    result = _build(tmp_path)
    assert sorted(p.name for p in (tmp_path / "processed").iterdir()) == sorted(
        [module.SNSS_FILENAME, module.NO_SNSS_FILENAME])
    assert len(result["archivos_generados"]) == 2


def test_outputs_match_declared_schemas(tmp_path: Path) -> None:
    _build(tmp_path)
    for filename, schema in ((module.SNSS_FILENAME, module.SNSS_SCHEMA),
                             (module.NO_SNSS_FILENAME, module.NO_SNSS_SCHEMA)):
        written = pq.read_schema(tmp_path / "processed" / filename)
        assert [(f.name, f.type) for f in written] == [(f.name, f.type) for f in schema]


def test_snss_parquet_has_the_columns_of_its_workbook() -> None:
    """Nombre Servicio de Salud, Código, Tipo, Nombre, Cod. Área, Área y un año por columna."""
    assert module.SNSS_SCHEMA.names == [
        "servicio_salud", "establecimiento_codigo", "tipo_establecimiento", "establecimiento_nombre",
        "area_funcional_codigo", "area_funcional", *CAMAS_COLUMNS]


def test_no_snss_parquet_has_the_columns_of_its_workbook() -> None:
    """Nombre SEREMI, Código, Nombre, Código área, Area y el total del año (hoja)."""
    assert module.NO_SNSS_SCHEMA.names == [
        "ano", "seremi", "establecimiento_codigo", "establecimiento_nombre",
        "area_funcional_codigo", "area_funcional", "camas"]


def test_one_row_per_source_row(tmp_path: Path) -> None:
    result = _build(tmp_path)
    # 5 filas de total + 4 de área
    assert len(_snss_rows(tmp_path)) == 9 == result["filas_snss"]
    assert len(_no_snss_rows(tmp_path)) == 2 == result["filas_no_snss"]


def test_numeric_values_are_preserved_exactly(tmp_path: Path) -> None:
    _build(tmp_path)
    expected = 0
    for block in (_vals(10, y2012=None), _vals(6, y2012=None), _vals(4, y2012=None, y2010=0),
                  _vals(5), _vals(5), _vals(7, y2023=None, y2024=None, y2025=None),
                  _vals(7, y2023=None, y2024=None, y2025=None),
                  _vals(None, **{f"y{y}": 9 for y in range(2014, 2022)}),
                  _vals(8, **{f"y{y}": None for y in range(2014, 2022)})):
        expected += sum(v for v in block if isinstance(v, int))
    total = sum(r[c] for r in _snss_rows(tmp_path) for c in CAMAS_COLUMNS if r[c] is not None)
    assert total == expected


def test_blank_stays_null_and_explicit_zero_stays_zero(tmp_path: Path) -> None:
    _build(tmp_path)
    area_402 = _snss_row(_snss_rows(tmp_path), 101100, 402)
    assert area_402["camas_2010"] == 0
    assert area_402["camas_2012"] is None
    assert area_402["camas_2011"] == 4


# --------------------------------------------------------------------------- #
# Libro SNSS
# --------------------------------------------------------------------------- #

def test_snss_hospital_total_is_the_total_row_and_areas_follow_with_their_code(tmp_path: Path) -> None:
    _build(tmp_path)
    rows = _snss_rows(tmp_path)
    total = _snss_row(rows, 101100, 100)
    assert total["area_funcional"] == "Total" and total["camas_2010"] == 10
    area_401 = _snss_row(rows, 101100, 401)
    assert area_401["area_funcional"] == "Área Médica Adulto Cuidados Básicos"
    assert area_401["camas_2011"] == 6


def test_snss_fills_down_establishment_data_and_normalizes_names(tmp_path: Path) -> None:
    _build(tmp_path)
    rows = _snss_rows(tmp_path)
    for area in (100, 401, 402):
        row = _snss_row(rows, 101100, area)
        assert (row["servicio_salud"], row["tipo_establecimiento"], row["establecimiento_nombre"]) == (
            "Arica", "Alta complejidad", "Hospital Uno")
    assert _snss_row(rows, 103100, 100)["establecimiento_nombre"] == "Hospital Tres"
    assert _snss_row(rows, 103100, 100)["tipo_establecimiento"] == "Mediana complejidad"


def test_snss_area_rows_attach_to_their_hospital_even_if_the_row_name_differs(tmp_path: Path) -> None:
    _build(tmp_path)
    row = _snss_row(_snss_rows(tmp_path), 102100, 403)
    assert row["establecimiento_nombre"] == "Hospital Dos"


def test_same_code_under_two_services_is_kept_as_two_rows(tmp_path: Path) -> None:
    _build(tmp_path)
    rows = [r for r in _snss_rows(tmp_path) if r["establecimiento_codigo"] == 114104]
    assert sorted(r["servicio_salud"] for r in rows) == ["Metropolitano Occidente", "Metropolitano Oriente"]




# --------------------------------------------------------------------------- #
# Libro no SNSS
# --------------------------------------------------------------------------- #

def test_no_snss_rows_are_the_sheets_stacked_with_year_from_the_sheet(tmp_path: Path) -> None:
    _build(tmp_path)
    rows = _no_snss_rows(tmp_path)
    assert {r["ano"] for r in rows} == {2019}
    assert {r["seremi"] for r in rows} == {"Arica y Parinacota"}
    assert {r["establecimiento_nombre"] for r in rows} == {"Clínica Uno"}
    total = next(r for r in rows if r["area_funcional_codigo"] is None)
    assert total["camas"] == 3 and total["area_funcional"] is None
    area = next(r for r in rows if r["area_funcional_codigo"] == 404)
    assert area["camas"] == 3 and area["area_funcional"] == "Área Médico-Quirúrgico Cuidados Medios"




def test_no_snss_blank_values_are_kept_as_rows_with_null(tmp_path: Path) -> None:
    sheets = {2025: [
        {"seremi": "Tarapacá", "codigo": 102200, "nombre": "Clínica Iquique ", "total": 40,
         "areas": [(403, "Área Médico-Quirúrgico", None), (405, "Área Cuidados Intensivos", None)]},
        {"seremi": "Tarapacá", "codigo": 102201, "nombre": "Clínica Cerrada", "total": None, "areas": []},
    ]}
    _build(tmp_path, no_snss=_minimal_no_snss(tmp_path / "ns.xlsx", sheets))
    rows = [r for r in _no_snss_rows(tmp_path) if r["ano"] == 2025]
    iquique = [r for r in rows if r["establecimiento_codigo"] == 102200]
    assert len(iquique) == 3
    assert [r["camas"] for r in iquique if r["area_funcional_codigo"] is not None] == [None, None]
    assert next(r for r in iquique if r["area_funcional_codigo"] is None)["camas"] == 40
    cerrada = [r for r in rows if r["establecimiento_codigo"] == 102201]
    assert len(cerrada) == 1 and cerrada[0]["camas"] is None




# --------------------------------------------------------------------------- #
# Totales publicados y notas: metadatos de la fuente en el footer
# --------------------------------------------------------------------------- #









def test_text_only_row_between_data_rows_is_not_taken_for_a_note(tmp_path: Path) -> None:
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10), [(401, "Área", _vals(10))]),
              _snss_block("Atacama", 103100, "Hospital Tres", _vals(7), [(401, "Área", _vals(7))])]
    snss = _write_snss(tmp_path / "snss.xlsx", blocks)
    workbook = openpyxl.load_workbook(snss)
    workbook.active.insert_rows(7)  # entre el primer establecimiento y el segundo
    workbook.active.cell(row=7, column=1).value = "Texto suelto entre datos"
    workbook.save(snss)
    with pytest.raises(ValueError, match="no reconocida"):
        _build(tmp_path, snss=snss)






# --------------------------------------------------------------------------- #
# Fallos explícitos: nada se descarta en silencio
# --------------------------------------------------------------------------- #

def test_a_value_cell_with_a_note_marker_becomes_null(tmp_path: Path) -> None:
    """`*******` ocupa el lugar de una cifra: el dato es 'no declara', es decir, nulo."""
    _build(tmp_path)
    row = _snss_row(_snss_rows(tmp_path), 103100, 100)
    assert [row[f"camas_{y}"] for y in (2022, 2023, 2024, 2025)] == [7, None, None, None]


def test_no_snss_ok_marks_are_ignored_and_the_values_are_kept(tmp_path: Path) -> None:
    sheets = {2024: [{"seremi": "Metropolitana", "codigo": 112246, "nombre": "Clínica Dos", "total": 361,
                      "marca": "ok", "areas": [(406, "Área Cuidados", 166, "ok"), (416, "Área Obstetricia", 195)]}]}
    _build(tmp_path, no_snss=_minimal_no_snss(tmp_path / "ns.xlsx", sheets))
    rows = [r for r in _no_snss_rows(tmp_path) if r["ano"] == 2024]
    assert sorted(r["camas"] for r in rows) == [166, 195, 361]
    assert set(rows[0]) == set(module.NO_SNSS_SCHEMA.names)


def test_no_snss_repeated_establishment_is_kept_and_counted(tmp_path: Path) -> None:
    sheets = {2025: [
        {"seremi": "Metropolitana", "codigo": 200063, "nombre": "Clínica Alemana", "total": 12,
         "areas": [(403, "Área Médico-Quirúrgico", 12)]},
        {"seremi": "Metropolitana", "codigo": 111276, "nombre": "Clínica UC", "total": 94,
         "areas": [(403, "Área Médico-Quirúrgico", 94)]},
        {"seremi": "Metropolitano", "codigo": 200063, "nombre": "Clínica Alemana", "total": 12,
         "areas": [(403, "Área Médico-Quirúrgico", 12)]},
    ]}
    result = _build(tmp_path, no_snss=_minimal_no_snss(tmp_path / "ns.xlsx", sheets))
    rows = [r for r in _no_snss_rows(tmp_path) if r["ano"] == 2025 and r["establecimiento_codigo"] == 200063]
    assert len(rows) == 4, "ninguna copia se elimina"
    assert {r["seremi"] for r in rows} == {"Metropolitana", "Metropolitano"}
    assert result["establecimientos_repetidos"] == 1


def test_published_national_totals_are_used_to_validate_not_stored(tmp_path: Path) -> None:
    assert _build(tmp_path)["totales_que_no_coinciden"] == 0


def test_a_published_total_that_does_not_match_is_reported_not_corrected(tmp_path: Path) -> None:
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10), [(401, "Área", _vals(10))])]
    snss = _write_snss(tmp_path / "snss.xlsx", blocks, national=_vals(10, y2020=999))
    result = _build(tmp_path, snss=snss)
    assert result["totales_que_no_coinciden"] == 1
    assert _snss_row(_snss_rows(tmp_path), 101100, 100)["camas_2020"] == 10


def test_parquet_files_contain_neither_footnotes_nor_marks_nor_national_totals(tmp_path: Path) -> None:
    """Notas al pie, marcas y totales nacionales no son datos de dotación: siguen solo en el RAW."""
    _build(tmp_path)
    for filename in (module.SNSS_FILENAME, module.NO_SNSS_FILENAME):
        path = tmp_path / "processed" / filename
        user_metadata = set(pq.read_schema(path).metadata or {}) - {b"ARROW:schema"}
        assert user_metadata == {b"raw_sha256"}
        content = path.read_bytes()
        for fragment in (b"Nota sin referencia", b"agrupaci", b"*******", b"Total Pa", b"2014*"):
            assert fragment not in content, fragment
    assert not any("*" in str(value) for r in _snss_rows(tmp_path) for value in r.values())
    assert "camas_2014" in module.SNSS_SCHEMA.names and "camas_2014*" not in module.SNSS_SCHEMA.names


def test_duplicated_area_row_for_the_same_hospital_raises(tmp_path: Path) -> None:
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10), [(401, "Área", _vals(5)), (401, "Área", _vals(5))])]
    with pytest.raises(ValueError, match="(?i)duplicad"):
        _build(tmp_path, snss=_write_snss(tmp_path / "snss.xlsx", blocks))


def test_no_snss_duplicated_row_in_a_sheet_raises(tmp_path: Path) -> None:
    sheets = {2025: [{"seremi": "Metropolitana", "codigo": 1, "nombre": "Clínica", "total": 4,
                      "areas": [(403, "Área", 2), (403, "Área", 2)]}]}
    with pytest.raises(ValueError, match="(?i)duplicad"):
        _build(tmp_path, no_snss=_minimal_no_snss(tmp_path / "ns.xlsx", sheets))


def test_snss_workbook_without_the_national_total_row_raises(tmp_path: Path) -> None:
    """Cada año de dotación debe tener su total publicado."""
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10), [(401, "Área", _vals(10))])]
    snss = _write_snss(tmp_path / "snss.xlsx", blocks)
    workbook = openpyxl.load_workbook(snss)
    workbook.active.delete_rows(4)  # fila "Total País"
    workbook.save(snss)
    with pytest.raises(ValueError, match="(?i)total nacional publicado"):
        _build(tmp_path, snss=snss)


def test_no_snss_sheet_without_the_total_row_raises(tmp_path: Path) -> None:
    sheets = {2019: [{"seremi": "Metropolitana", "codigo": 1, "nombre": "Clínica", "total": 1,
                      "areas": [(403, "Área", 1)]}]}
    no_snss = _minimal_no_snss(tmp_path / "ns.xlsx", sheets)
    workbook = openpyxl.load_workbook(no_snss)
    workbook["2019"].delete_rows(4)  # fila "TOTAL"
    workbook.save(no_snss)
    with pytest.raises(ValueError, match="(?i)total nacional publicado"):
        _build(tmp_path, no_snss=no_snss)


def test_unrecognized_row_pattern_raises(tmp_path: Path) -> None:
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10), [(401, "Área", _vals(10))])]
    snss = _write_snss(tmp_path / "snss.xlsx", blocks, extra_rows=((None, None, "texto suelto", None, None, None),))
    with pytest.raises(ValueError, match="no reconocida"):
        _build(tmp_path, snss=snss)


def test_area_row_before_any_establishment_raises(tmp_path: Path) -> None:
    snss = _write_snss(tmp_path / "snss.xlsx", [], extra_rows=(("Arica", None, None, "Hospital", 401, "Área", *_vals(1)),))
    with pytest.raises(ValueError, match="sin establecimiento"):
        _build(tmp_path, snss=snss)


def test_data_beyond_the_known_columns_raises(tmp_path: Path) -> None:
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10), [(401, "Área", _vals(10))])]
    snss = _write_snss(tmp_path / "snss.xlsx", blocks)
    workbook = openpyxl.load_workbook(snss)
    workbook.active.cell(row=6, column=len(download.SNSS_COLUMNS) + len(YEARS) + 2).value = 7
    workbook.save(snss)
    with pytest.raises(ValueError, match="fuera de las columnas"):
        _build(tmp_path, snss=snss)


@pytest.mark.parametrize("bad", [-1, 2.5, "12"])
def test_invalid_bed_count_raises(tmp_path: Path, bad) -> None:
    blocks = [_snss_block("Arica", 101100, "Hospital Uno", _vals(10, y2015=bad), [(401, "Área", _vals(10))])]
    with pytest.raises(ValueError, match="valor"):
        _build(tmp_path, snss=_write_snss(tmp_path / "snss.xlsx", blocks))


def test_missing_raw_raises_and_creates_nothing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_dotacion_camas(tmp_path / "no_existe.xlsx", tmp_path / "tampoco.xlsx", tmp_path / "processed")
    assert not (tmp_path / "processed").exists()


# --------------------------------------------------------------------------- #
# Reproducibilidad, procedencia y escritura atómica
# --------------------------------------------------------------------------- #

def test_each_parquet_records_the_sha256_of_its_own_raw_workbook(tmp_path: Path) -> None:
    snss, no_snss = _standard_snss(tmp_path / "snss.xlsx"), _minimal_no_snss(tmp_path / "no_snss.xlsx")
    _build(tmp_path, snss=snss, no_snss=no_snss)
    for filename, raw in ((module.SNSS_FILENAME, snss), (module.NO_SNSS_FILENAME, no_snss)):
        metadata = pq.read_schema(tmp_path / "processed" / filename).metadata
        assert metadata[b"raw_sha256"].decode() == file_sha256(raw)


def test_parquet_files_use_zstd_compression(tmp_path: Path) -> None:
    _build(tmp_path)
    for filename in (module.SNSS_FILENAME, module.NO_SNSS_FILENAME):
        metadata = pq.ParquetFile(tmp_path / "processed" / filename).metadata
        compressions = {metadata.row_group(0).column(i).compression for i in range(metadata.num_columns)}
        assert compressions == {"ZSTD"}


def test_build_is_deterministic(tmp_path: Path) -> None:
    snss, no_snss = _standard_snss(tmp_path / "snss.xlsx"), _minimal_no_snss(tmp_path / "no_snss.xlsx")
    build_dotacion_camas(snss, no_snss, tmp_path / "a")
    build_dotacion_camas(snss, no_snss, tmp_path / "b")
    for filename in (module.SNSS_FILENAME, module.NO_SNSS_FILENAME):
        assert pq.read_table(tmp_path / "a" / filename).equals(pq.read_table(tmp_path / "b" / filename))
        assert pq.read_schema(tmp_path / "a" / filename).metadata == pq.read_schema(tmp_path / "b" / filename).metadata


def test_failed_write_keeps_previous_outputs_and_leaves_no_temp_files(tmp_path: Path) -> None:
    snss, no_snss = _standard_snss(tmp_path / "snss.xlsx"), _minimal_no_snss(tmp_path / "no_snss.xlsx")
    _build(tmp_path, snss=snss, no_snss=no_snss)
    out = tmp_path / "processed"
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    real_write = pq.write_table
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disco lleno")
        return real_write(*args, **kwargs)

    with patch("src.data.clean_dotacion_camas.pq.write_table", side_effect=flaky):
        with pytest.raises(OSError):
            build_dotacion_camas(snss, no_snss, out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


# --------------------------------------------------------------------------- #
# Registro en el pipeline y contrato de outputs
# --------------------------------------------------------------------------- #

def test_clean_stage_is_registered_after_its_download() -> None:
    stage = pipeline.STAGES["clean_dotacion_camas"]
    assert stage["module"] == "src.data.clean_dotacion_camas"
    assert stage["depends_on"] == ["download_dotacion_camas"]
    assert stage["outputs"] == [f"data/processed/camas/{module.SNSS_FILENAME}",
                                f"data/processed/camas/{module.NO_SNSS_FILENAME}"]
    order = pipeline.PIPELINE_ORDER
    assert order.index("download_dotacion_camas") < order.index("clean_dotacion_camas")


def test_output_contract_accepts_valid_outputs_and_rejects_a_foreign_schema(tmp_path: Path) -> None:
    _build(tmp_path)
    out = tmp_path / "processed"
    paths = [(out / module.SNSS_FILENAME).as_posix(), (out / module.NO_SNSS_FILENAME).as_posix()]
    assert pipeline.check_outputs_exist(paths)
    # Un Parquet con el nombre correcto pero el esquema del otro libro no debe aceptarse.
    pq.write_table(pq.read_table(out / module.NO_SNSS_FILENAME), out / module.SNSS_FILENAME)
    assert not pipeline.check_outputs_exist(paths)
