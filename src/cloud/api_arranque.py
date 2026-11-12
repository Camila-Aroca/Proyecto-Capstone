"""Punto de entrada del contenedor de la API: baja sus datos desde S3 y luego inicia uvicorn.

En ECS la API no tiene el volumen de Docker Compose. Con `SAAD_S3_BUCKET` definido, antes de
iniciar el servidor descarga `data/` y `reports/` del bucket (lo que publica
`infra/aws/scripts/subir_datos.sh`: outputs procesados, reportes del modelo y el cuadro INE
de población, ~215 MB). La API lee sus datos solo al arrancar, así que publicar datos nuevos
exige reiniciar el servicio, cosa que hace el mismo script.

Sin `SAAD_S3_BUCKET` no descarga nada y se comporta como antes: lee el volumen montado.
Si la descarga falla, el proceso termina con error y ECS no da por sana la tarea, en vez de
servir una API sin datos.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

from src.cloud.pipeline_task import descargar, listar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

UVICORN: Final[list[str]] = ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


def preparar_datos(
    raiz: Path,
    entorno: Mapping[str, str],
    fabrica_cliente: Callable[[str], Any] | None = None,
) -> int:
    """Baja el bucket a `raiz` si hay `SAAD_S3_BUCKET`; devuelve cuántos archivos bajó."""
    bucket = entorno.get("SAAD_S3_BUCKET", "").strip()
    if not bucket:
        logger.info("Sin SAAD_S3_BUCKET: la API usa los datos ya presentes en %s.", raiz)
        return 0
    if fabrica_cliente is None:
        import boto3

        fabrica_cliente = boto3.client
    cliente = fabrica_cliente("s3")
    objetos = listar(cliente, bucket, entorno.get("SAAD_S3_PREFIX", ""), raiz)
    if not objetos:
        logger.warning("El bucket %s no tiene data/ ni reports/: la API arrancará sin datos.", bucket)
        return 0
    bajados = descargar(cliente, bucket, objetos)
    total_mb = sum(tamano for _, _, tamano in objetos) / 2**20
    logger.info("Descargados %s archivos (%.1f MB) desde s3://%s.", bajados, total_mb, bucket)
    return bajados


def main() -> None:
    preparar_datos(Path.cwd(), os.environ)
    # exec reemplaza este proceso: uvicorn queda como proceso principal y recibe las señales de ECS.
    os.execvp(UVICORN[0], UVICORN)


if __name__ == "__main__":
    main()
