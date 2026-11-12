"""Pruebas del arranque de la API en ECS: descarga desde S3 simulado antes de uvicorn."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cloud import api_arranque
from src.cloud.api_arranque import preparar_datos
from tests.test_pipeline_task import FakeS3


def _fabrica(s3: FakeS3):
    return lambda servicio: {"s3": s3}[servicio]


def test_baja_data_y_reports_del_bucket(tmp_path: Path) -> None:
    s3 = FakeS3({
        "data/processed/marts/mart.parquet": b"mart",
        "data/raw/poblacion/ine.xlsx": b"ine",
        "reports/modeling/seleccion.json": b"{}",
    })
    bajados = preparar_datos(tmp_path, {"SAAD_S3_BUCKET": "b"}, _fabrica(s3))

    assert bajados == 3
    assert (tmp_path / "data/processed/marts/mart.parquet").read_bytes() == b"mart"
    assert (tmp_path / "data/raw/poblacion/ine.xlsx").read_bytes() == b"ine"
    assert (tmp_path / "reports/modeling/seleccion.json").read_bytes() == b"{}"


def test_respeta_el_prefijo(tmp_path: Path) -> None:
    s3 = FakeS3({"saad/data/processed/a.parquet": b"a", "otro/data/processed/b.parquet": b"b"})
    preparar_datos(tmp_path, {"SAAD_S3_BUCKET": "b", "SAAD_S3_PREFIX": "saad"}, _fabrica(s3))

    assert (tmp_path / "data/processed/a.parquet").exists()
    assert not (tmp_path / "data/processed/b.parquet").exists()


def test_sin_bucket_no_usa_s3(tmp_path: Path) -> None:
    def no_llamar(servicio: str):
        raise AssertionError("no debía crear un cliente de AWS")

    assert preparar_datos(tmp_path, {}, no_llamar) == 0


def test_bucket_vacio_arranca_sin_datos(tmp_path: Path) -> None:
    assert preparar_datos(tmp_path, {"SAAD_S3_BUCKET": "b"}, _fabrica(FakeS3({}))) == 0


def test_falla_de_descarga_detiene_el_arranque(tmp_path: Path) -> None:
    class S3QueFalla(FakeS3):
        def download_file(self, bucket: str, clave: str, destino: str) -> None:
            raise OSError("red caída")

    with pytest.raises(OSError):
        preparar_datos(tmp_path, {"SAAD_S3_BUCKET": "b"}, _fabrica(S3QueFalla({"data/x.parquet": b"x"})))


def test_main_inicia_uvicorn_despues_de_preparar(monkeypatch: pytest.MonkeyPatch) -> None:
    orden: list[str] = []
    monkeypatch.setattr(api_arranque, "preparar_datos", lambda raiz, entorno: orden.append("datos"))
    monkeypatch.setattr(api_arranque.os, "execvp", lambda archivo, args: orden.append(" ".join(args)))
    api_arranque.main()

    assert orden == ["datos", " ".join(api_arranque.UVICORN)]


def test_dockerfile_api_usa_el_arranque() -> None:
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    etapa_api = dockerfile.split("AS api", 1)[1]
    assert 'CMD ["python", "-m", "src.cloud.api_arranque"]' in etapa_api
