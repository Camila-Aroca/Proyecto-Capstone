"""Stage `forecast_demanda_sm`: genera y persiste el pronostico vigente.

Ejecuta una sola vez el ajuste que antes se repetia en cada arranque de la API y deja
el resultado en `data/processed/modeling/`, junto con un manifiesto que registra fecha,
modelo, configuracion y el SHA256 de las entradas con que se genero.

Usa la seleccion congelada del benchmark (`benchmark_demanda_sm`), de modo que se
persiste exactamente la configuracion evaluada. Al invocarlo siempre regenera: es el
orquestador quien decide si corresponde ejecutarlo o hacer SKIP.

Uso, desde la raiz del repositorio:
    python -m scripts.run_forecast_demanda_sm
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.forecast import load_current_panel  # noqa: E402
from src.models.persistence import (  # noqa: E402
    RUTA_MANIFIESTO,
    RUTA_PRONOSTICO,
    calcular_pronostico,
    cargar_seleccion,
    construir_manifiesto,
    guardar,
    nombres_series,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # El orquestador pasa --force a todos los stages; aqui la generacion es
    # incondicional, asi que se acepta y se ignora.
    parser.add_argument("--force", action="store_true", help="Aceptado por compatibilidad.")
    parser.parse_args(argv)

    inicio = time.perf_counter()
    seleccion = cargar_seleccion()
    print(f"Modelo seleccionado (congelado): {seleccion['modelo_recomendado']}", flush=True)

    datos = load_current_panel()
    pronostico = calcular_pronostico(datos, seleccion)
    manifiesto = construir_manifiesto(pronostico, datos, seleccion)
    guardar(pronostico, manifiesto, nombres_series(datos.panel))

    ultima = manifiesto["ultima_semana_observada"]
    print(
        f"Pronostico persistido: {manifiesto['filas']} filas, "
        f"{manifiesto['series']['total']} series "
        f"({manifiesto['series']['region']} region + {manifiesto['series']['comuna']} comunas), "
        f"horizontes {manifiesto['horizontes']}.",
        flush=True,
    )
    print(
        f"Ultima semana observada: {ultima['ano']}-S{ultima['semana']:02d}. "
        f"Generado en {time.perf_counter() - inicio:.1f}s.",
        flush=True,
    )
    print(f"  {RUTA_PRONOSTICO.as_posix()}", flush=True)
    print(f"  {RUTA_MANIFIESTO.as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
