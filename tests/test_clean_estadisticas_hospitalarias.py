"""Pruebas de la limpieza de las Estadísticas Hospitalarias REM-20 a Parquet."""

import io
import json
from pathlib import Path

import openpyxl
import pyarrow.parquet as pq
import pytest

import src.data.clean_estadisticas_hospitalarias as module
import src.data.download_estadisticas_hospitalarias as download

CONTEO = "Dias Cama Ocupados"
DISPONIBLES = "Dias Cama Disponibles"
PROMEDIO = "Promedio Cama Disponibles"
INDICE = "Indice Ocupacional"


@pytest.fixture(autouse=True)
def _small_workbooks(monkeypatch) -> None:
    monkeypatch.setattr(download, "INDICADORES_MIN_ROWS", 1)
    monkeypatch.setattr(download, "CATEGORIZACION_MIN_ROWS", 1)


def _row(ss, ss_name, est, est_name, niv, niv_name, glosa, months):
    values = list(months)
    return [ss, ss_name, est, est_name, niv, niv_name, glosa, sum(v or 0 for v in values), *values]


def _area_rows(meses: int = 2, *, ocupado_extra: int = 0) -> list[list]:
    """Dos áreas de un hospital y sus tres niveles de agregados, coherentes entre sí."""
    m = lambda *v: list(v)[:meses]  # noqa: E731
    area1, area2 = m(10, 20, 30), m(5, 5, 5)
    ss, est = (1, "Arica"), (101100, "Hospital A")
    detalle = [
        _row(*ss, *est, 401, "401 - Área Médica", CONTEO, area1),
        _row(*ss, *est, 402, "402 - Área Quirúrgica", CONTEO, area2),
        _row(*ss, *est, 401, "401 - Área Médica", DISPONIBLES, m(20, 20, 40)),
        _row(*ss, *est, 402, "402 - Área Quirúrgica", DISPONIBLES, m(10, 10, 10)),
    ]
    total = [a + b for a, b in zip(area1, area2)]
    agregados = [
        _row(0, "Datos País", 0, "Datos País", 0, "Datos País", CONTEO, [t + ocupado_extra for t in total]),
        _row(*ss, 0, "Datos Servicio Salud", 0, "Datos Servicio Salud", CONTEO, total),
        _row(*ss, *est, 0, "Datos Establecimiento", CONTEO, total),
    ]
    return agregados + detalle


def indicadores_bytes(rows_by_year: dict[int, list[list]], meses: int = 2) -> bytes:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for year, rows in rows_by_year.items():
        ws = workbook.create_sheet(str(year))
        ws.append([None])
        ws.append([f"Indicadores Hospitalarios según Servicio de Salud, SNSS. Período: {year}"])
        ws.append([*download.INDICADORES_COLUMNS, *download.MESES_CORTOS[:meses]])
        for row in rows:
            ws.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def categorizacion_bytes(year: int, rows: list[list]) -> bytes:
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.append([None])
    ws.append([f"Categorización de Pacientes Hospitalizados Según Riesgo Dependencia. Período: {year}"])
    ws.append(list(download.CATEGORIZACION_COLUMNS))
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _categorias(total: int) -> list[int]:
    return [total, *[0] * 11]


CATEGORIZACION_OK = [
    ["de Arica y Parinacota", *[None] * 13],
    ["SS Arica y Parinacota", *[None] * 13],
    ["Hospital A", *[None] * 13],
    ["401 - Área Médica", 3, *_categorias(3)],
    ["418 - Área Psiquiatría Adulto Corta estadía", 2, 1, 0, 0, 0, 1, *[0] * 7],
    ["Metropolitana de Santiago", *[None] * 13],
    ["SS Metropolitano Norte", *[None] * 13],
    ["Hospital B", *[None] * 13],
    ["401 - Área Médica", 1, *_categorias(1)],
]


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# --------------------------------------------------------------------------- #
# Indicadores
# --------------------------------------------------------------------------- #

def test_parquet_solo_lleva_detalle_y_agregados_quedan_para_validar(tmp_path):
    path = _write(tmp_path / "i.xlsx", indicadores_bytes({2024: _area_rows()}))
    datos = module.parse_indicadores(path)
    assert len(datos.detalle) == 4
    assert sorted(r["nivel_agregado"] for r in datos.agregados) == ["establecimiento", "pais", "servicio"]
    assert all(r["nivel_cuidado_codigo"] > 0 for r in datos.detalle)


def test_conciliacion_exacta_sin_discrepancias(tmp_path):
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2024: _area_rows()})))
    resultado = module.reconcile_indicadores(datos)
    assert resultado["discrepancias_agregados"] == []
    assert resultado["agregados_comparados"] == {"pais": 1, "servicio": 1, "establecimiento": 1}


def test_conciliacion_informa_agregado_que_no_cuadra(tmp_path):
    rows = _area_rows(ocupado_extra=1)
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2024: rows})))
    discrepancias = module.reconcile_indicadores(datos)["discrepancias_agregados"]
    assert {(d["nivel_agregado"], d["columna"]) for d in discrepancias} == {
        ("pais", "acumulado"), ("pais", "ene"), ("pais", "feb")}


def test_promedio_acumulado_no_aditivo_se_separa_de_las_discrepancias(tmp_path):
    ss, est = (1, "Arica"), (101100, "Hospital A")
    rows = [
        [*ss, *est, 0, "Datos Establecimiento", PROMEDIO, 10.0, 10.0, 10.0],
        [*ss, *est, 401, "401 - Área", PROMEDIO, 6.0, 5.0, 5.0],  # acumulado no es la suma del año
        [*ss, *est, 402, "402 - Área", PROMEDIO, 5.0, 5.0, 5.0],
    ]
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2024: rows})))
    resultado = module.reconcile_indicadores(datos)
    assert resultado["discrepancias_agregados"] == []
    assert [d["columna"] for d in resultado["promedio_acumulado_no_aditivo"]] == ["acumulado"]


def test_razones_no_se_concilian_como_sumas(tmp_path):
    ss, est = (1, "Arica"), (101100, "Hospital A")
    rows = [[*ss, *est, 0, "Datos Establecimiento", INDICE, 80.0, 80.0, 80.0],
            [*ss, *est, 401, "401 - Área", INDICE, 80.0, 80.0, 80.0],
            [*ss, *est, 402, "402 - Área", INDICE, 80.0, 80.0, 80.0]]
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2024: rows})))
    assert module.reconcile_indicadores(datos)["discrepancias_agregados"] == []


def test_meses_no_publicados_quedan_nulos_no_en_cero(tmp_path):
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2026: _area_rows()}, meses=2)))
    fila = datos.detalle[0]
    assert fila["ene"] == 10 and fila["feb"] == 20 and fila["mar"] is None and fila["dic"] is None
    assert datos.meses_por_ano == {2026: 2}


def test_acumulado_distinto_de_meses_se_informa(tmp_path):
    rows = _area_rows()
    rows[3][7] = 999  # acumulado del área 401
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2024: rows})))
    assert len(module.reconcile_indicadores(datos)["acumulado_distinto_de_meses"]) == 1


@pytest.mark.parametrize("cambio, error", [
    (lambda r: r.__setitem__(6, "Camas Fantasma"), "indicador no reconocido"),
    (lambda r: r.__setitem__(8, "n/d"), "no numérico"),
    (lambda r: r.__setitem__(5, "Otra etiqueta") or r.__setitem__(4, 0), "estructura no reconocida"),
    (lambda r: r.extend([None, None, 7]), "fuera de las columnas"),
])
def test_filas_desconocidas_detienen_la_etapa(tmp_path, cambio, error):
    rows = _area_rows()
    cambio(rows[3])
    path = _write(tmp_path / "i.xlsx", indicadores_bytes({2024: rows}))
    with pytest.raises(ValueError, match=error):
        module.parse_indicadores(path)


def test_llave_duplicada_falla(tmp_path):
    rows = _area_rows()
    rows.append(list(rows[3]))
    datos = module.parse_indicadores(_write(tmp_path / "i.xlsx", indicadores_bytes({2024: rows})))
    with pytest.raises(ValueError, match="duplicada"):
        module._assert_unique(datos.detalle, module.INDICADORES_KEY, "Indicadores")


# --------------------------------------------------------------------------- #
# Categorización
# --------------------------------------------------------------------------- #

def test_categorizacion_aplana_la_jerarquia(tmp_path):
    rows = module.parse_categorizacion(_write(tmp_path / "c.xlsx", categorizacion_bytes(2024, CATEGORIZACION_OK)),
                                       2024, 3)
    assert [(r["region"], r["servicio_salud"], r["establecimiento_nombre"], r["nivel_cuidado_codigo"], r["total"])
            for r in rows] == [
        ("de Arica y Parinacota", "SS Arica y Parinacota", "Hospital A", 401, 3),
        ("de Arica y Parinacota", "SS Arica y Parinacota", "Hospital A", 418, 2),
        ("Metropolitana de Santiago", "SS Metropolitano Norte", "Hospital B", 401, 1),
    ]
    assert all(r["ano"] == 2024 and r["trimestre"] == 3 for r in rows)
    assert module.reconcile_categorizacion(rows) == []


def test_categorizacion_total_distinto_de_categorias_se_informa(tmp_path):
    filas = [list(r) for r in CATEGORIZACION_OK]
    filas[3][1] = 4
    rows = module.parse_categorizacion(_write(tmp_path / "c.xlsx", categorizacion_bytes(2024, filas)), 2024, 1)
    assert [r["total"] for r in module.reconcile_categorizacion(rows)] == [4]


@pytest.mark.parametrize("filas, error", [
    ([["Hospital A", *[None] * 13], ["401 - Área", 1, *_categorias(1)]], "sin Servicio de Salud"),
    ([["de Arica", *[None] * 13], ["SS Arica", *[None] * 13], ["401 - Área", 1, *_categorias(1)]],
     "sin establecimiento"),
    ([["de Arica", *[None] * 13], ["SS Arica", *[None] * 13], ["Hospital A", 1, *_categorias(1)]],
     "no es un nivel de cuidado"),
    ([["de Arica", *[None] * 13], ["SS Arica", *[None] * 13], ["Hospital A", *[None] * 13],
      ["401 - Área", -1, *_categorias(1)]], "conteo entero"),
])
def test_categorizacion_filas_desconocidas_fallan(tmp_path, filas, error):
    path = _write(tmp_path / "c.xlsx", categorizacion_bytes(2024, filas))
    with pytest.raises(ValueError, match=error):
        module.parse_categorizacion(path, 2024, 1)


# --------------------------------------------------------------------------- #
# Construcción, footer y contrato de SKIP
# --------------------------------------------------------------------------- #

@pytest.fixture
def entorno(tmp_path, monkeypatch):
    config = download.load_config()
    raw = tmp_path / "raw"
    config["raw_dir"] = raw.as_posix()
    config["indicadores"]["cerrados"] = [{"ruta": "x.xlsx", "archivo": "indicadores_hospitalarios_2024.xlsx",
                                          "anos": [2024]}]
    config["categorizacion"]["cerrados"] = [{"ruta": "y.xlsx", "archivo": "categorizacion_riesgo_dependencia_2024_t1.xlsx",
                                             "ano": 2024, "trimestre": 1}]
    config["indicadores"]["en_curso"]["primer_ano"] = 2100  # sin años en curso en la prueba
    config["categorizacion"]["en_curso"]["primer_ano"] = 2100
    _write(raw / "indicadores_hospitalarios_2024.xlsx", indicadores_bytes({2024: _area_rows()}))
    _write(raw / "categorizacion_riesgo_dependencia_2024_t1.xlsx", categorizacion_bytes(2024, CATEGORIZACION_OK))
    _write(raw / config["diccionario"]["archivo"], b"documentacion")  # requerido, pero no se procesa
    monkeypatch.setattr(download, "load_config", lambda path=None: config)
    return config, raw, tmp_path / "out"


def test_build_escribe_los_dos_parquet_con_hashes_de_sus_raw(entorno):
    config, raw, out = entorno
    resumen = module.build_estadisticas_hospitalarias(output_dir=out, config=config)
    assert resumen["filas_indicadores"] == 4 and resumen["filas_agregadas_excluidas"] == 3
    assert resumen["discrepancias_agregados"] == 0 and resumen["filas_categorizacion"] == 3
    indicadores = pq.read_table(out / module.INDICADORES_FILENAME)
    assert indicadores.schema.remove_metadata() == module.INDICADORES_SCHEMA
    hashes = json.loads(indicadores.schema.metadata[module.RAW_HASHES_METADATA_KEY])
    assert list(hashes) == [(raw / "indicadores_hospitalarios_2024.xlsx").as_posix()]
    categorizacion = pq.read_schema(out / module.CATEGORIZACION_FILENAME).metadata[module.RAW_HASHES_METADATA_KEY]
    assert "diccionario" not in categorizacion.decode()
    for name in (module.INDICADORES_FILENAME, module.CATEGORIZACION_FILENAME):
        module.validate_output(out / name)


def test_contrato_detecta_raw_cambiado(entorno):
    config, raw, out = entorno
    module.build_estadisticas_hospitalarias(output_dir=out, config=config)
    rows = _area_rows()
    rows[3][8] = 11
    rows[3][7] = 31
    _write(raw / "indicadores_hospitalarios_2024.xlsx", indicadores_bytes({2024: rows}))
    with pytest.raises(ValueError, match="RAW distintos"):
        module.validate_output(out / module.INDICADORES_FILENAME)


def test_falta_un_raw_requerido(entorno):
    config, raw, out = entorno
    (raw / "categorizacion_riesgo_dependencia_2024_t1.xlsx").unlink()
    with pytest.raises(FileNotFoundError, match="Faltan RAW"):
        module.build_estadisticas_hospitalarias(output_dir=out, config=config)


def test_dos_libros_con_el_mismo_ano_fallan(entorno):
    config, raw, out = entorno
    config["indicadores"]["cerrados"].append({"ruta": "z.xlsx", "archivo": "indicadores_hospitalarios_2024b.xlsx",
                                              "anos": [2024]})
    _write(raw / "indicadores_hospitalarios_2024b.xlsx", indicadores_bytes({2024: _area_rows()}))
    with pytest.raises(ValueError, match="ya leídos"):
        module.build_estadisticas_hospitalarias(output_dir=out, config=config)
