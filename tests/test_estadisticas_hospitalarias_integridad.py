"""Verificación de que la limpieza del REM-20 no perdió ni duplicó datos.

Compara los Parquet de ``data/processed/estadisticas_hospitalarias/`` con los libros
reales de ``data/raw/estadisticas_hospitalarias/`` leyendo estos últimos con
``pandas.read_excel`` (no con el parser de la etapa), para que el código no se
verifique con su propia lectura. Requiere los datos locales; se ejecuta con
``pytest -m data_integration``.

1. Indicadores: por año e indicador, el número de filas de detalle y la suma de
   cada columna de valor coinciden; las filas agregadas del libro (códigos en 0)
   no están en el Parquet; y el detalle reconstruye los totales país publicados.
2. Categorización: por trimestre, filas de nivel de cuidado y sumas por categoría.
3. Procedencia: el footer registra el SHA256 de cada RAW vigente.
"""

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

import src.data.clean_estadisticas_hospitalarias as module
import src.data.download_estadisticas_hospitalarias as download
from src.data.raw_provenance import file_sha256

pytestmark = pytest.mark.data_integration

MESES = list(module.MESES_COLUMNAS)
VALORES = ["acumulado", *MESES]


def _inputs():
    try:
        return module.raw_inputs()
    except FileNotFoundError as error:
        pytest.skip(f"RAW locales no disponibles: {error}")


@pytest.fixture(scope="module")
def parquet_indicadores() -> pd.DataFrame:
    path = module.OUTPUT_DIR / module.INDICADORES_FILENAME
    if not path.is_file():
        pytest.skip("Parquet de indicadores no generado.")
    return pq.read_table(path).to_pandas()


@pytest.fixture(scope="module")
def raw_indicadores() -> pd.DataFrame:
    hojas = []
    for path, _ in _inputs()["indicadores"]:
        for nombre, hoja in pd.read_excel(path, sheet_name=None, header=None).items():
            ano = int(str(hoja.iloc[1, 0]).strip()[-4:])
            datos = hoja.iloc[3:].dropna(how="all").copy()
            meses = hoja.shape[1] - 8
            datos.columns = ["ss", "ssn", "est", "estn", "niv", "nivn", "glosa", "acumulado", *MESES[:meses]]
            for mes in MESES[meses:]:
                datos[mes] = float("nan")
            datos["ano"] = ano
            datos["glosa"] = datos["glosa"].astype(str).str.strip()
            hojas.append(datos)
    return pd.concat(hojas, ignore_index=True)


def test_detalle_completo_por_ano_e_indicador(parquet_indicadores, raw_indicadores):
    detalle = raw_indicadores[(raw_indicadores.ss > 0) & (raw_indicadores.est > 0) & (raw_indicadores.niv > 0)]
    esperado = detalle.groupby(["ano", "glosa"])[VALORES].agg(["count", "sum"])
    observado = parquet_indicadores.groupby(["ano", "indicador"])[VALORES].agg(["count", "sum"])
    observado.index = pd.MultiIndex.from_tuples(
        [(int(a), g) for a, g in observado.index], names=["ano", "glosa"])
    esperado.index = pd.MultiIndex.from_tuples(
        [(int(a), module._text(g)) for a, g in esperado.index], names=["ano", "glosa"])
    pd.testing.assert_frame_equal(observado.sort_index(), esperado.sort_index(), check_dtype=False, atol=1e-6)
    assert len(parquet_indicadores) == len(detalle)


def test_filas_agregadas_no_estan_en_el_parquet(parquet_indicadores, raw_indicadores):
    agregadas = raw_indicadores[(raw_indicadores.ss == 0) | (raw_indicadores.est == 0) | (raw_indicadores.niv == 0)]
    assert len(agregadas) > 0
    assert (parquet_indicadores.servicio_salud_codigo > 0).all()
    assert (parquet_indicadores.establecimiento_codigo > 0).all()
    assert (parquet_indicadores.nivel_cuidado_codigo > 0).all()
    assert len(parquet_indicadores) + len(agregadas) == len(raw_indicadores)


def test_detalle_reconstruye_el_total_pais_en_conteos(parquet_indicadores, raw_indicadores):
    pais = raw_indicadores[raw_indicadores.ss == 0].assign(glosa=lambda d: d.glosa.map(module._text))
    pais = pais[pais.glosa.isin(module.CONTEOS)].set_index(["ano", "glosa"])[MESES].astype(float)
    suma = parquet_indicadores[parquet_indicadores.indicador.isin(module.CONTEOS)].groupby(
        ["ano", "indicador"])[MESES].sum(min_count=1)
    suma.index = pd.MultiIndex.from_tuples([(int(a), g) for a, g in suma.index], names=["ano", "glosa"])
    pais.index = pd.MultiIndex.from_tuples([(int(a), g) for a, g in pais.index], names=["ano", "glosa"])
    # El libro no publica todos los conteos a nivel país (p. ej., traslados): se comparan los publicados.
    assert len(pais) > 0 and set(pais.index) <= set(suma.index)
    pd.testing.assert_frame_equal(suma.loc[pais.index].sort_index(), pais.sort_index(), check_dtype=False)


def test_categorizacion_completa_por_trimestre():
    path = module.OUTPUT_DIR / module.CATEGORIZACION_FILENAME
    if not path.is_file():
        pytest.skip("Parquet de categorización no generado.")
    parquet = pq.read_table(path).to_pandas()
    columnas = ["total", *[c.lower() for c in download.CATEGORIAS]]
    for raw, info in _inputs()["categorizacion"]:
        hoja = pd.read_excel(raw, header=None).iloc[3:]
        niveles = hoja[hoja[0].astype(str).str.match(r"^\d{3} - ")]
        propio = parquet[(parquet.ano == info["anos"][0]) & (parquet.trimestre == info["trimestre"])]
        assert len(propio) == len(niveles), raw.name
        assert propio[columnas].sum().tolist() == niveles.iloc[:, 1:14].astype(int).sum().tolist(), raw.name


def test_footer_registra_los_raw_vigentes():
    familias = _inputs()
    for nombre, familia in ((module.INDICADORES_FILENAME, "indicadores"),
                            (module.CATEGORIZACION_FILENAME, "categorizacion")):
        path = module.OUTPUT_DIR / nombre
        if not path.is_file():
            pytest.skip(f"{nombre} no generado.")
        guardado = json.loads(pq.read_schema(path).metadata[module.RAW_HASHES_METADATA_KEY])
        assert guardado == {raw.as_posix(): file_sha256(raw) for raw, _ in sorted(familias[familia])}
