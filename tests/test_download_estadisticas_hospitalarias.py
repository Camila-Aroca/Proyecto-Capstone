"""Pruebas de ingesta RAW segura de las Estadísticas Hospitalarias REM-20 (DEIS)."""

from datetime import datetime, timezone
import io
import json
from pathlib import Path

import openpyxl
import pytest

import scripts.run_pipeline as pipeline
import src.data.download_estadisticas_hospitalarias as module

ENERO_2026 = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
NOVIEMBRE_2026 = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
FEBRERO_2027 = datetime(2027, 2, 1, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _small_workbooks(monkeypatch) -> None:
    monkeypatch.setattr(module, "INDICADORES_MIN_ROWS", 3)
    monkeypatch.setattr(module, "CATEGORIZACION_MIN_ROWS", 3)


def _config(tmp_path: Path) -> dict:
    config = module.load_config()
    config["raw_dir"] = (tmp_path / "raw").as_posix()
    config["cache_dir"] = (tmp_path / "cache").as_posix()
    return config


def _save(workbook: openpyxl.Workbook) -> bytes:
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def indicadores_bytes(years_months: dict[int, int], *, header=None, rows: int = 4) -> bytes:
    """Libro de indicadores sintético: una hoja por año con ``meses`` columnas de mes."""
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for year, months in years_months.items():
        ws = workbook.create_sheet(f"Año {year}")
        ws.append([None])
        ws.append([f"Indicadores Hospitalarios según Servicio de Salud, SNSS. Período: {year}"])
        ws.append(list(header or (*module.INDICADORES_COLUMNS, *module.MESES_CORTOS[:months])))
        for index in range(rows):
            ws.append([1, "Arica", 101100, "Hospital", 401, "401 - Área", "Dias Cama Ocupados",
                       index * months, *[index] * months])
    return _save(workbook)


def categorizacion_bytes(year: int, *, rows: int = 4, header=None) -> bytes:
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.append([None])
    ws.append([f"Categorización de Pacientes Hospitalizados Según Riesgo Dependencia. Período: {year}"])
    ws.append(list(header or module.CATEGORIZACION_COLUMNS))
    for _ in range(rows):
        ws.append(["401 - Área", 1, *[0] * 11, 1])
    return _save(workbook)


def diccionario_bytes(*, titulo=module.DICCIONARIO_TITULO, campos=module.DICCIONARIO_CAMPOS) -> bytes:
    """Diccionario sintético con el diseño observado: título en B1 y encabezado en la fila 5."""
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws["B1"] = titulo
    for col, valor in enumerate(module.DICCIONARIO_COLUMNS, start=2):
        ws.cell(row=5, column=col, value=f" {valor}" if valor == "Valores" else valor)
    for fila, campo in enumerate(campos, start=6):
        ws.cell(row=fila, column=2, value=campo)
        ws.cell(row=fila, column=6, value=f"Definición de {campo}")
    return _save(workbook)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# --------------------------------------------------------------------------- #
# Validadores
# --------------------------------------------------------------------------- #

def test_indicadores_validos_por_titulo_no_por_nombre_de_hoja(tmp_path):
    path = _write(tmp_path / "x.xlsx", indicadores_bytes({2014: 12, 2015: 12}))
    module.validate_indicadores_workbook(path, (2014, 2015), 12)
    assert module.indicadores_periods(path) == {2014: 12, 2015: 12}


@pytest.mark.parametrize("years, months, error", [
    ((2014,), 12, "años"),
    ((2014, 2015), 9, "meses"),
])
def test_indicadores_rechaza_anos_o_meses_inesperados(tmp_path, years, months, error):
    path = _write(tmp_path / "x.xlsx", indicadores_bytes({2014: 12, 2015: 12}))
    with pytest.raises(ValueError, match=error):
        module.validate_indicadores_workbook(path, years, months)


def test_indicadores_rechaza_encabezado_inesperado(tmp_path):
    header = ("Código", *module.INDICADORES_COLUMNS[1:], *module.MESES_CORTOS)
    path = _write(tmp_path / "x.xlsx", indicadores_bytes({2024: 12}, header=header))
    with pytest.raises(ValueError, match="encabezado"):
        module.validate_indicadores_workbook(path, (2024,), 12)


def test_indicadores_rechaza_meses_desordenados(tmp_path):
    header = (*module.INDICADORES_COLUMNS, "Ene", "Mar")
    path = _write(tmp_path / "x.xlsx", indicadores_bytes({2024: 2}, header=header))
    with pytest.raises(ValueError, match="mes"):
        module.indicadores_periods(path)


def test_categorizacion_exige_ano_del_titulo(tmp_path):
    path = _write(tmp_path / "c.xlsx", categorizacion_bytes(2024))
    module.validate_categorizacion_workbook(path, 2024)
    with pytest.raises(ValueError, match="2025"):
        module.validate_categorizacion_workbook(path, 2025)


def test_categorizacion_rechaza_pocas_filas(tmp_path):
    path = _write(tmp_path / "c.xlsx", categorizacion_bytes(2024, rows=0))
    with pytest.raises(ValueError, match="filas"):
        module.validate_categorizacion_workbook(path, 2024)


def test_validate_raw_file_deduce_contrato_del_nombre(tmp_path):
    config = _config(tmp_path)
    module.validate_raw_file(_write(tmp_path / "indicadores_hospitalarios_2026.xlsx",
                                    indicadores_bytes({2026: 9})), config)
    module.validate_raw_file(_write(tmp_path / "categorizacion_riesgo_dependencia_2026_t1.xlsx",
                                    categorizacion_bytes(2026)), config)
    with pytest.raises(ValueError, match="no reconocido"):
        module.validate_raw_file(_write(tmp_path / "otro.xlsx", categorizacion_bytes(2026)), config)


def test_diccionario_lee_campos_y_definiciones(tmp_path):
    campos = module.read_diccionario(_write(tmp_path / "d.xlsx", diccionario_bytes()))
    assert [c["campo"] for c in campos] == list(module.DICCIONARIO_CAMPOS)
    assert campos[0]["detalle"] == f"Definición de {module.DICCIONARIO_CAMPOS[0]}"


@pytest.mark.parametrize("kwargs, error", [
    ({"titulo": "Otro diccionario"}, "título"),
    ({"campos": module.DICCIONARIO_CAMPOS[:-1]}, "faltan los campos"),
])
def test_diccionario_rechaza_titulo_o_campos_inesperados(tmp_path, kwargs, error):
    with pytest.raises(ValueError, match=error):
        module.read_diccionario(_write(tmp_path / "d.xlsx", diccionario_bytes(**kwargs)))


def test_diccionario_es_una_publicacion_fija_validada_por_nombre(tmp_path):
    config = _config(tmp_path)
    pub = next(p for p in module.closed_publications(config) if p.familia == "diccionario")
    assert pub.archivo == "diccionario_rem20.xlsx" and pub.url.startswith("https://datos.gob.cl/")
    module.validate_raw_file(_write(tmp_path / pub.archivo, diccionario_bytes()), config)
    assert Path(config["raw_dir"]) / pub.archivo in module.required_raw_paths(config, now=NOVIEMBRE_2026)


# --------------------------------------------------------------------------- #
# Descubrimiento del año en curso y RAW requeridos
# --------------------------------------------------------------------------- #

def test_configuracion_cerrada_sin_solapes_de_anos():
    publicaciones = module.closed_publications(module.load_config())
    anos = [ano for pub in publicaciones if pub.familia == "indicadores" for ano in pub.anos]
    assert len(anos) == len(set(anos))
    trimestres = [(pub.anos[0], pub.trimestre) for pub in publicaciones if pub.familia == "categorizacion"]
    assert len(trimestres) == len(set(trimestres))
    assert all(pub.url.startswith("https://repositoriodeis.minsal.cl/") for pub in publicaciones
               if pub.familia != "diccionario")


def test_descubre_el_ultimo_mes_publicado_sin_fijarlo():
    config = module.load_config()
    publicados = {"Agosto", "Septiembre"}
    probe = lambda url: any(f"Hospitalarias%20{mes}%202026" in url for mes in publicados)  # noqa: E731
    encontrados, sin_publicar = module.discover_current(config, now=NOVIEMBRE_2026, probe=probe)
    assert sin_publicar == []
    assert [(p.archivo, p.meses, p.en_curso) for p in encontrados] == [
        ("indicadores_hospitalarios_2026.xlsx", 9, True)]
    assert "Septiembre" in encontrados[0].url


def test_descubre_trimestres_de_categorizacion_publicados():
    config = module.load_config()
    probe = lambda url: "Primer%20Trimestre%202026" in url or "Septiembre%202026" in url  # noqa: E731
    encontrados, _ = module.discover_current(config, now=NOVIEMBRE_2026, probe=probe)
    assert "categorizacion_riesgo_dependencia_2026_t1.xlsx" in [p.archivo for p in encontrados]


def test_ano_sin_ningun_mes_publicado_se_informa():
    encontrados, sin_publicar = module.discover_current(module.load_config(), now=ENERO_2026,
                                                        probe=lambda url: False)
    assert encontrados == [] and sin_publicar == [2026]


def test_required_raw_paths_exige_ano_pasado_y_solo_el_actual_si_existe(tmp_path):
    config = _config(tmp_path)
    raw = Path(config["raw_dir"])
    cerrados = {raw / pub.archivo for pub in module.closed_publications(config)}
    assert set(module.required_raw_paths(config, now=NOVIEMBRE_2026)) == cerrados
    _write(raw / "indicadores_hospitalarios_2026.xlsx", b"x")
    assert raw / "indicadores_hospitalarios_2026.xlsx" in module.required_raw_paths(config, now=NOVIEMBRE_2026)
    # En 2027, 2026 ya es un año pasado no consolidado: se exige; 2027 aún no.
    (raw / "indicadores_hospitalarios_2026.xlsx").unlink()
    requeridos = module.required_raw_paths(config, now=FEBRERO_2027)
    assert raw / "indicadores_hospitalarios_2026.xlsx" in requeridos
    assert raw / "indicadores_hospitalarios_2027.xlsx" not in requeridos


def test_orquestador_registra_las_tres_etapas():
    for stage in ("download_estadisticas_hospitalarias", "clean_estadisticas_hospitalarias",
                  "eda_estadisticas_hospitalarias"):
        assert stage in pipeline.PIPELINE_ORDER and stage in pipeline.STAGES
    order = pipeline.PIPELINE_ORDER
    assert order.index("download_estadisticas_hospitalarias") < order.index("clean_estadisticas_hospitalarias") \
        < order.index("eda_estadisticas_hospitalarias")
    assert order.index("clean_dotacion_camas") < order.index("eda_estadisticas_hospitalarias")
    outputs = pipeline.STAGES["download_estadisticas_hospitalarias"]["outputs"]
    assert "data/raw/estadisticas_hospitalarias/indicadores_hospitalarios_2014_2023.xlsx" in outputs


# --------------------------------------------------------------------------- #
# Ingesta y publicación
# --------------------------------------------------------------------------- #

def _pub(meses: int = 9, ano: int = 2026) -> module.Publicacion:
    return module._indicadores_en_curso(module.load_config(), ano, meses)


def _downloader(content: bytes):
    def download(url: str, target: Path) -> dict[str, str]:
        target.write_bytes(content)
        return {"http_etag": "abc"}
    return download


def _snapshots(manifest: Path, source_id: str) -> list[dict]:
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    return next(e for e in entries if e["source_id"] == source_id)["snapshots"]


def test_publica_registra_procedencia_y_corte(tmp_path):
    manifest = tmp_path / "manifest.json"
    pub = _pub()
    published = module.ingest_publicacion(pub, raw_dir=tmp_path / "raw", cache_dir=tmp_path / "cache",
                                          manifest_path=manifest, force=True,
                                          download=_downloader(indicadores_bytes({2026: 9})))
    assert published
    snapshot = _snapshots(manifest, pub.source_id)[0]
    assert snapshot["transport"]["corte_mes"] == 9 and snapshot["transport"]["http_etag"] == "abc"
    assert not list((tmp_path / "cache").glob("*.xlsx"))  # el candidato temporal no queda en cache


def test_contenido_identico_no_reemplaza_ni_duplica_historial(tmp_path):
    manifest = tmp_path / "manifest.json"
    content = indicadores_bytes({2026: 9})
    kwargs = dict(raw_dir=tmp_path / "raw", cache_dir=tmp_path / "cache", manifest_path=manifest, force=True,
                  download=_downloader(content))
    assert module.ingest_publicacion(_pub(), **kwargs)
    assert not module.ingest_publicacion(_pub(), **kwargs)
    assert len(_snapshots(manifest, _pub().source_id)) == 1


def test_un_corte_anterior_no_reemplaza_al_vigente(tmp_path):
    raw = tmp_path / "raw"
    vigente = _write(raw / "indicadores_hospitalarios_2026.xlsx", indicadores_bytes({2026: 9}))
    before = vigente.read_bytes()
    published = module.ingest_publicacion(_pub(meses=8), raw_dir=raw, cache_dir=tmp_path / "cache",
                                          manifest_path=tmp_path / "m.json", force=True,
                                          download=_downloader(indicadores_bytes({2026: 8})))
    assert not published and vigente.read_bytes() == before


def test_un_corte_nuevo_reemplaza_y_conserva_historial(tmp_path):
    manifest = tmp_path / "m.json"
    kwargs = dict(raw_dir=tmp_path / "raw", cache_dir=tmp_path / "cache", manifest_path=manifest, force=True)
    module.ingest_publicacion(_pub(9), download=_downloader(indicadores_bytes({2026: 9})), **kwargs)
    assert module.ingest_publicacion(_pub(10), download=_downloader(indicadores_bytes({2026: 10})), **kwargs)
    assert [s["transport"]["corte_mes"] for s in _snapshots(manifest, _pub().source_id)] == [9, 10]
    assert module.indicadores_periods(tmp_path / "raw" / "indicadores_hospitalarios_2026.xlsx") == {2026: 10}


def test_candidato_invalido_no_toca_el_raw(tmp_path):
    raw = tmp_path / "raw"
    vigente = _write(raw / "indicadores_hospitalarios_2026.xlsx", indicadores_bytes({2026: 9}))
    before = vigente.read_bytes()
    with pytest.raises(ValueError):
        # El nombre dice septiembre (9 meses) y el libro trae 10: no se publica.
        module.ingest_publicacion(_pub(9), raw_dir=raw, cache_dir=tmp_path / "cache",
                                  manifest_path=tmp_path / "m.json", force=True,
                                  download=_downloader(indicadores_bytes({2026: 10})))
    assert vigente.read_bytes() == before


def test_fallo_de_procedencia_restaura_el_raw(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    vigente = _write(raw / "indicadores_hospitalarios_2026.xlsx", indicadores_bytes({2026: 9}))
    before = vigente.read_bytes()
    monkeypatch.setattr(module, "record_raw_snapshot", lambda *a, **k: (_ for _ in ()).throw(OSError("disco")))
    with pytest.raises(OSError):
        module.ingest_publicacion(_pub(10), raw_dir=raw, cache_dir=tmp_path / "cache",
                                  manifest_path=tmp_path / "m.json", force=True,
                                  download=_downloader(indicadores_bytes({2026: 10})))
    assert vigente.read_bytes() == before


def test_raw_valido_hace_skip_sin_descargar(tmp_path):
    raw = tmp_path / "raw"
    pub = next(p for p in module.closed_publications(module.load_config())
               if p.archivo == "indicadores_hospitalarios_2024.xlsx")
    _write(raw / pub.archivo, indicadores_bytes({2024: 12}))

    def no_download(url, target):
        raise AssertionError("no debía descargar")
    assert not module.ingest_publicacion(pub, raw_dir=raw, cache_dir=tmp_path / "cache",
                                         manifest_path=tmp_path / "m.json", download=no_download)


def test_ingest_all_informa_ano_pasado_sin_publicacion(tmp_path):
    config = _config(tmp_path)
    config["indicadores"]["cerrados"] = config["indicadores"]["cerrados"][1:2]  # solo 2024
    config["categorizacion"]["cerrados"] = []
    config.pop("diccionario")
    raw = Path(config["raw_dir"])
    _write(raw / "indicadores_hospitalarios_2024.xlsx", indicadores_bytes({2024: 12}))
    errores = module.ingest_all(config=config, now=FEBRERO_2027, manifest_path=tmp_path / "m.json",
                                probe=lambda url: False, download=_downloader(b""))
    assert "indicadores_2026" in errores and "indicadores_2027" not in errores


def test_ingest_all_en_enero_sin_meses_no_es_error(tmp_path):
    config = _config(tmp_path)
    config["indicadores"]["cerrados"] = []
    config["categorizacion"]["cerrados"] = []
    config.pop("diccionario")
    assert module.ingest_all(config=config, now=ENERO_2026, manifest_path=tmp_path / "m.json",
                             probe=lambda url: False, download=_downloader(b"")) == {}
