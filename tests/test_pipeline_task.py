"""Pruebas del punto de entrada del pipeline en la nube, con S3 y ECS simulados."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cloud.pipeline_task import MARGEN_DISCO, MODOS, ejecutar, ruta_local

TASK_DEFINITION = Path(__file__).resolve().parents[1] / "infra/aws/pipeline-task-definition.json"


class FakeS3:
    """Bucket en memoria con la parte de la API de boto3 que usa la tarea."""

    def __init__(self, objetos: dict[str, bytes]) -> None:
        self.objetos = dict(objetos)
        self.subidos: list[str] = []

    def get_paginator(self, nombre: str):
        assert nombre == "list_objects_v2"
        objetos = self.objetos

        class Paginador:
            def paginate(self, Bucket: str, Prefix: str):
                yield {"Contents": [{"Key": k, "Size": len(v)} for k, v in sorted(objetos.items())
                                    if k.startswith(Prefix)]}

        return Paginador()

    def download_file(self, bucket: str, clave: str, destino: str) -> None:
        Path(destino).write_bytes(self.objetos[clave])

    def upload_file(self, origen: str, bucket: str, clave: str) -> None:
        self.objetos[clave] = Path(origen).read_bytes()
        self.subidos.append(clave)


class FakeECS:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    def update_service(self, **kwargs) -> None:
        self.llamadas.append(kwargs)


def _fabrica(s3: FakeS3, ecs: FakeECS):
    return lambda servicio: {"s3": s3, "ecs": ecs}[servicio]


def _corredor(raiz: Path, escribir: dict[str, str] | None = None, falla_en: int | None = None):
    """Simula los pasos del pipeline: registra comandos y escribe archivos."""
    llamadas: list[list[str]] = []

    def correr(comando: list[str], cwd: Path):
        llamadas.append(comando)
        if falla_en is not None and len(llamadas) == falla_en:
            return SimpleNamespace(returncode=1)
        for relativa, contenido in (escribir or {}).items():
            destino = raiz / relativa
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido)
            os.utime(destino, ns=(destino.stat().st_atime_ns, destino.stat().st_mtime_ns + 10**9))
        return SimpleNamespace(returncode=0)

    correr.llamadas = llamadas
    return correr


ENTORNO = {"SAAD_S3_BUCKET": "saad-datos", "SAAD_S3_PREFIX": "",
           "SAAD_ECS_CLUSTER": "saad", "SAAD_ECS_SERVICE": "saad-api"}


def test_semanal_baja_ejecuta_sube_solo_cambios_y_redespliega(tmp_path: Path) -> None:
    s3 = FakeS3({"data/raw/a.csv": b"a", "data/processed/p.parquet": b"p", "reports/r.md": b"r"})
    ecs = FakeECS()
    correr = _corredor(tmp_path, escribir={"data/processed/p.parquet": "nuevo", "reports/n.md": "n"})

    assert ejecutar("semanal", tmp_path, ENTORNO, _fabrica(s3, ecs), correr) == 0

    assert (tmp_path / "data/raw/a.csv").read_bytes() == b"a"
    assert correr.llamadas == MODOS["semanal"]
    assert sorted(s3.subidos) == ["data/processed/p.parquet", "reports/n.md"]
    assert ecs.llamadas == [{"cluster": "saad", "service": "saad-api", "forceNewDeployment": True}]


def test_si_un_paso_falla_no_sube_ni_redespliega(tmp_path: Path) -> None:
    s3 = FakeS3({"data/raw/a.csv": b"a"})
    ecs = FakeECS()
    correr = _corredor(tmp_path, escribir={"data/raw/a.csv": "roto"}, falla_en=2)

    assert ejecutar("semanal", tmp_path, ENTORNO, _fabrica(s3, ecs), correr) == 1
    assert s3.subidos == [] and ecs.llamadas == []
    assert s3.objetos["data/raw/a.csv"] == b"a"


def test_sin_cambios_no_sube_ni_redespliega(tmp_path: Path) -> None:
    s3 = FakeS3({"data/raw/a.csv": b"a"})
    ecs = FakeECS()
    assert ejecutar("semanal", tmp_path, ENTORNO, _fabrica(s3, ecs), _corredor(tmp_path)) == 0
    assert s3.subidos == [] and ecs.llamadas == []


def test_sin_servicio_ecs_sube_pero_no_redespliega(tmp_path: Path) -> None:
    s3 = FakeS3({})
    ecs = FakeECS()
    entorno = {"SAAD_S3_BUCKET": "saad-datos"}
    correr = _corredor(tmp_path, escribir={"reports/n.md": "n"})
    assert ejecutar("completo", tmp_path, entorno, _fabrica(s3, ecs), correr) == 0
    assert s3.subidos == ["reports/n.md"] and ecs.llamadas == []


def test_prefijo_se_respeta_al_bajar_y_subir(tmp_path: Path) -> None:
    s3 = FakeS3({"saad/data/raw/a.csv": b"a", "otro/data/raw/x.csv": b"x"})
    correr = _corredor(tmp_path, escribir={"reports/n.md": "n"})
    entorno = {"SAAD_S3_BUCKET": "b", "SAAD_S3_PREFIX": "saad/"}
    assert ejecutar("semanal", tmp_path, entorno, _fabrica(s3, FakeECS()), correr) == 0
    assert (tmp_path / "data/raw/a.csv").exists() and not (tmp_path / "data/raw/x.csv").exists()
    assert s3.subidos == ["saad/reports/n.md"]


def test_modo_local_no_usa_s3(tmp_path: Path) -> None:
    def fabrica(_: str):
        raise AssertionError("no debe crear clientes AWS en modo local")

    correr = _corredor(tmp_path)
    assert ejecutar("completo", tmp_path, {}, fabrica, correr) == 0
    assert correr.llamadas == MODOS["completo"]


@pytest.mark.parametrize("clave", ["data/../etc/passwd", "otra/carpeta/x", "../data/x"])
def test_rechaza_claves_fuera_de_data_y_reports(tmp_path: Path, clave: str) -> None:
    with pytest.raises(ValueError):
        ruta_local(tmp_path, "", clave)


def test_ignora_marcadores_de_carpeta(tmp_path: Path) -> None:
    assert ruta_local(tmp_path, "", "data/raw/") is None


def test_falla_antes_de_descargar_si_no_hay_espacio(tmp_path: Path) -> None:
    s3 = FakeS3({"data/raw/a.csv": b"a" * 100})
    correr = _corredor(tmp_path)
    libre = lambda _: MARGEN_DISCO + 50  # noqa: E731 - no alcanza para 100 bytes más el margen

    assert ejecutar("semanal", tmp_path, ENTORNO, _fabrica(s3, FakeECS()), correr, libre) == 1
    assert correr.llamadas == [] and not (tmp_path / "data").exists()


def test_definicion_de_tarea_da_disco_suficiente() -> None:
    definicion = json.loads(TASK_DEFINITION.read_text(encoding="utf-8"))
    disco_gib = definicion["ephemeralStorage"]["sizeInGiB"]
    datos_gib = 13  # RAW (~12 GB), outputs y reportes de hoy
    assert disco_gib * 2**30 >= datos_gib * 2**30 + MARGEN_DISCO
    assert disco_gib > 20  # sobre el valor por defecto de Fargate
    assert definicion["containerDefinitions"][0]["command"][-2:] == ["--modo", "semanal"]
