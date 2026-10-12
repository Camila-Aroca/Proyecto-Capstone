"""Punto de entrada del contenedor del pipeline: local o como tarea programada en Fargate.

Con `SAAD_S3_BUCKET` definido, la tarea:

1. baja `data/` y `reports/` desde S3 al disco efímero de la tarea;
2. ejecuta el pipeline (`--modo semanal` por defecto);
3. si todo terminó bien, sube solo los archivos nuevos o modificados;
4. si cambió algo y hay `SAAD_ECS_CLUSTER` y `SAAD_ECS_SERVICE`, fuerza un nuevo despliegue
   del servicio de la API, que solo lee sus datos al arrancar.

Si un paso del pipeline falla no se sube nada: S3 conserva el último estado completo y la
próxima ejecución vuelve a intentarlo. Sin `SAAD_S3_BUCKET` trabaja sobre el disco local
(por ejemplo, el volumen de Docker Compose) y omite S3 y ECS.

Modos:
- `semanal`: `--refresh-current-urgencias` y luego el pronóstico con `--force`. El pronóstico
  se fuerza porque usa los datos del año en curso, pero su vigencia solo vigila el mart
  cerrado y la selección del modelo (DT-03 del DAS).
- `completo`: el pipeline completo (`run_pipeline.py` sin argumentos).
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Final

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DIRECTORIOS: Final[tuple[str, ...]] = ("data", "reports")
# Espacio de trabajo sobre lo descargado: el ZIP y el CSV nuevos del año en curso en staging
# (~2 GB hoy) más los Parquet regenerados, con holgura para que crezca el año.
MARGEN_DISCO: Final[int] = 8 * 2**30
PIPELINE: Final[list[str]] = [sys.executable, "scripts/run_pipeline.py"]
MODOS: Final[dict[str, list[list[str]]]] = {
    "semanal": [
        [*PIPELINE, "--refresh-current-urgencias"],
        [*PIPELINE, "--stage", "forecast_demanda_sm", "--force"],
    ],
    "completo": [list(PIPELINE)],
}

Huellas = dict[str, tuple[int, int]]


def clave_s3(prefijo: str, relativa: str) -> str:
    return f"{prefijo.strip('/')}/{relativa}" if prefijo.strip("/") else relativa


def ruta_local(raiz: Path, prefijo: str, clave: str) -> Path | None:
    """Ruta local de una clave S3 bajo `data/` o `reports/`; None si debe ignorarse.

    Rechaza claves que intenten salir de la raíz (`..`, rutas absolutas).
    """
    base = prefijo.strip("/")
    if base:
        if not clave.startswith(base + "/"):
            return None
        relativa = clave[len(base) + 1:]
    else:
        relativa = clave
    if not relativa or relativa.endswith("/"):
        return None
    partes = PurePosixPath(relativa).parts
    if partes[0] not in DIRECTORIOS or ".." in partes:
        raise ValueError(f"Clave S3 fuera de data/ o reports/: {clave}")
    return raiz.joinpath(*partes)


def huellas(raiz: Path) -> Huellas:
    """Tamaño y fecha de modificación de cada archivo bajo `data/` y `reports/`."""
    resultado: Huellas = {}
    for directorio in DIRECTORIOS:
        for archivo in sorted((raiz / directorio).rglob("*")):
            if archivo.is_file():
                estado = archivo.stat()
                resultado[archivo.relative_to(raiz).as_posix()] = (estado.st_size, estado.st_mtime_ns)
    return resultado


def listar(cliente: Any, bucket: str, prefijo: str, raiz: Path) -> list[tuple[str, Path, int]]:
    """Objetos de `data/` y `reports/` del bucket: clave, ruta local y tamaño en bytes."""
    objetos = []
    paginador = cliente.get_paginator("list_objects_v2")
    for directorio in DIRECTORIOS:
        for pagina in paginador.paginate(Bucket=bucket, Prefix=clave_s3(prefijo, directorio + "/")):
            for objeto in pagina.get("Contents", []):
                destino = ruta_local(raiz, prefijo, objeto["Key"])
                if destino is not None:
                    objetos.append((objeto["Key"], destino, int(objeto.get("Size", 0))))
    return objetos


def verificar_espacio(necesario: int, raiz: Path,
                      espacio_libre: Callable[[Path], int] | None = None) -> None:
    """Falla antes de descargar si el disco no alcanza para los datos más el margen de trabajo."""
    requerido = necesario + MARGEN_DISCO
    libre = espacio_libre(raiz) if espacio_libre else shutil.disk_usage(raiz).free
    if libre < requerido:
        raise RuntimeError(
            f"Disco insuficiente: hay {libre / 2**30:.1f} GiB libres y se necesitan "
            f"{requerido / 2**30:.1f} GiB. En Fargate, aumentar ephemeralStorage en la definición "
            "de la tarea (infra/aws/pipeline-task-definition.json)."
        )


def descargar(cliente: Any, bucket: str, objetos: Sequence[tuple[str, Path, int]]) -> int:
    """Baja los objetos listados; devuelve cuántos archivos bajó."""
    for clave, destino, _ in objetos:
        destino.parent.mkdir(parents=True, exist_ok=True)
        cliente.download_file(bucket, clave, str(destino))
    return len(objetos)


def cambios(antes: Huellas, despues: Huellas) -> list[str]:
    """Archivos nuevos o modificados. Lo borrado localmente no se borra en S3."""
    return sorted(ruta for ruta, huella in despues.items() if antes.get(ruta) != huella)


def subir(cliente: Any, bucket: str, prefijo: str, raiz: Path, rutas: Sequence[str]) -> None:
    for relativa in rutas:
        cliente.upload_file(str(raiz / relativa), bucket, clave_s3(prefijo, relativa))


def ejecutar_pasos(pasos: Sequence[Sequence[str]], raiz: Path,
                   correr: Callable[..., Any] = subprocess.run) -> bool:
    for paso in pasos:
        logger.info("Ejecutando: %s", " ".join(paso[1:]))
        if correr(list(paso), cwd=raiz).returncode != 0:
            logger.error("Falló el paso: %s", " ".join(paso[1:]))
            return False
    return True


def ejecutar(
    modo: str,
    raiz: Path,
    entorno: dict[str, str],
    fabrica_cliente: Callable[[str], Any] | None = None,
    correr: Callable[..., Any] = subprocess.run,
    espacio_libre: Callable[[Path], int] | None = None,
) -> int:
    """Orquesta descarga, pipeline, subida y redespliegue. Devuelve el código de salida."""
    bucket = entorno.get("SAAD_S3_BUCKET", "").strip()
    prefijo = entorno.get("SAAD_S3_PREFIX", "")
    if not bucket:
        logger.info("Sin SAAD_S3_BUCKET: modo local sobre %s.", raiz)
        return 0 if ejecutar_pasos(MODOS[modo], raiz, correr) else 1

    if fabrica_cliente is None:
        import boto3

        fabrica_cliente = boto3.client
    s3 = fabrica_cliente("s3")
    objetos = listar(s3, bucket, prefijo, raiz)
    try:
        verificar_espacio(sum(tamano for *_, tamano in objetos), raiz, espacio_libre)
    except RuntimeError as error:
        logger.error("%s", error)
        return 1
    logger.info("Descargados %s archivos desde s3://%s.", descargar(s3, bucket, objetos), bucket)
    antes = huellas(raiz)

    if not ejecutar_pasos(MODOS[modo], raiz, correr):
        logger.error("No se sube nada: S3 conserva el último estado completo.")
        return 1

    modificados = cambios(antes, huellas(raiz))
    subir(s3, bucket, prefijo, raiz, modificados)
    logger.info("Subidos %s archivos nuevos o modificados.", len(modificados))

    cluster, servicio = entorno.get("SAAD_ECS_CLUSTER", ""), entorno.get("SAAD_ECS_SERVICE", "")
    if modificados and cluster and servicio:
        fabrica_cliente("ecs").update_service(cluster=cluster, service=servicio, forceNewDeployment=True)
        logger.info("Nuevo despliegue solicitado para %s/%s.", cluster, servicio)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta el pipeline del SAAD, local o contra S3.")
    parser.add_argument("--modo", choices=sorted(MODOS), default="semanal")
    args = parser.parse_args(argv)
    return ejecutar(args.modo, Path.cwd(), dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
