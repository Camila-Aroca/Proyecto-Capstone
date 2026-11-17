"""Verifica que los outputs del pipeline que lee la API estén completos y sean coherentes (DEF-11).

Lo ejecuta `infra/aws/scripts/subir_datos.sh` antes de publicar en S3. Revisa:
1. Que existan todos los archivos de las rutas que declara la API (`src/api/`).
2. Que cada manifiesto de pronóstico coincida, por SHA-256, con las entradas presentes
   (mart y JSON de selección): si no, la API serviría un pronóstico desactualizado (DEF-04).

Uso:
    .venv/bin/python scripts/verificar_outputs_api.py
Sale con código 1 y la lista de problemas si algo falta o no coincide.
"""

from __future__ import annotations

import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Final

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.api import caracterizacion, hospitalizaciones  # noqa: E402
from src.api.establecimientos import RutasEstablecimientos  # noqa: E402
from src.api.service import Rutas  # noqa: E402
from src.api.suicidios import RutasSuicidios  # noqa: E402
from src.data.raw_provenance import file_sha256, processed_raw_sha256  # noqa: E402
from src.models import persistence, pronostico_establecimientos, suicidios  # noqa: E402

MANIFIESTOS: Final[tuple[Path, ...]] = (
    persistence.RUTA_MANIFIESTO,
    pronostico_establecimientos.RUTA_MANIFIESTO,
    suicidios.RUTA_MANIFIESTO,
)


def requeridos() -> list[Path]:
    rutas = {getattr(r, c.name) for r in (Rutas(), RutasEstablecimientos(), RutasSuicidios()) for c in fields(r)}
    rutas |= {
        suicidios.RUTA_SELECCION,
        hospitalizaciones.CONTRASTE_PATH, hospitalizaciones.ANUAL_PATH, hospitalizaciones.DESGLOSE_PATH,
        caracterizacion.BASE / caracterizacion.DEFUNCIONES, caracterizacion.BASE / caracterizacion.GENERO,
    }
    return sorted(Path(r) for r in rutas)


def problemas(raiz: Path = RAIZ) -> list[str]:
    salida = [f"falta {r.as_posix()}" for r in requeridos() if not (raiz / r).is_file()]
    urgencias = caracterizacion.BASE / caracterizacion.URGENCIAS
    if not any((raiz / urgencias).glob("urgencias_rm_*.parquet")):
        salida.append(f"falta {urgencias.as_posix()}/urgencias_rm_*.parquet")
    for manifiesto in MANIFIESTOS:
        if not (raiz / manifiesto).is_file():
            continue  # ya reportado como faltante
        entradas = json.loads((raiz / manifiesto).read_text(encoding="utf-8"))["entradas"]
        for nombre, entrada in entradas.items():
            ruta = raiz / entrada["ruta"]
            if not ruta.is_file():
                salida.append(f"{manifiesto.name}: falta la entrada {nombre} ({entrada['ruta']})")
            # Para los años en curso el manifiesto guarda la identidad del RAW declarada en el Parquet.
            elif (processed_raw_sha256(ruta) if entrada.get("tipo") == "raw_sha256" else file_sha256(ruta)) != entrada["sha256"]:
                salida.append(f"{manifiesto.name}: {entrada['ruta']} cambió después de generar el pronóstico")
    salida += cortes_desalineados(raiz)
    return salida


def _semana(dato: dict | None) -> tuple[int, int] | None:
    return (int(dato["ano"]), int(dato["semana"])) if dato else None


def cortes_desalineados(raiz: Path = RAIZ) -> list[str]:
    """Demanda comunal y establecimientos salen del mismo RAW de urgencias: deben cerrar en la misma semana.

    Si difieren, un mart quedó sin reconstruir (p. ej. tras una corrida interrumpida) y la API serviría
    un pronóstico que empieza antes de la última semana observada (DEF-16).
    """
    rutas = (raiz / persistence.RUTA_MANIFIESTO, raiz / pronostico_establecimientos.RUTA_MANIFIESTO)
    if not all(r.is_file() for r in rutas):
        return []
    demanda = _semana(json.loads(rutas[0].read_text(encoding="utf-8")).get("ultima_semana_observada"))
    objetivos = json.loads(rutas[1].read_text(encoding="utf-8")).get("objetivos", {})
    establecimientos = _semana((objetivos.get("atenciones_sm") or {}).get("ultima_semana_observada"))
    if demanda and establecimientos and demanda != establecimientos:
        return [f"el pronóstico de demanda cierra en {demanda[0]}-S{demanda[1]} y el de establecimientos en "
                f"{establecimientos[0]}-S{establecimientos[1]}: reconstruya los marts de urgencias y ambos pronósticos"]
    return []


def main() -> int:
    encontrados = problemas()
    if encontrados:
        print("No se publican los datos: los outputs del pipeline están incompletos o desfasados.", file=sys.stderr)
        for p in encontrados:
            print(f"  - {p}", file=sys.stderr)
        print("Ejecuta el pipeline (scripts/run_pipeline.py) y vuelve a intentar.", file=sys.stderr)
        return 1
    print(f"Outputs completos: {len(requeridos())} archivos y {len(MANIFIESTOS)} manifiestos coherentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
