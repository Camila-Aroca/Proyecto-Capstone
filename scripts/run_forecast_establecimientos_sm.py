"""Stage `forecast_establecimientos_sm`: genera y persiste el pronóstico por establecimiento.

Ajusta, para cada objetivo (ID36 e ID42), el modelo congelado en
`reports/modeling/benchmark_establecimientos_sm_seleccion.json` sobre el panel
vigente (mart más semanas completas del año en curso) y deja el resultado en
`data/processed/modeling/` con un manifiesto de procedencia. Siempre regenera:
es el orquestador quien decide si corresponde ejecutarlo o hacer SKIP.

Uso (vía pipeline): `python scripts/run_pipeline.py --stage forecast_establecimientos_sm`
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from src.models.establecimientos import load_mart  # noqa: E402
from src.models.holdout import holdout_years  # noqa: E402
from src.models.pronostico_establecimientos import (  # noqa: E402
    RUTA_MANIFIESTO,
    RUTA_PRONOSTICO,
    calcular_pronostico,
    cargar_seleccion,
    construir_manifiesto,
    guardar,
    huella_entradas,
    preparar_datos,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # El orquestador pasa --force; aquí la generación es incondicional.
    parser.add_argument("--force", action="store_true", help="Aceptado por compatibilidad.")
    parser.parse_args(argv)

    inicio = time.perf_counter()
    seleccion = cargar_seleccion()
    mart = load_mart()
    anos = holdout_years(int(mart["ano"].max()))
    datos = preparar_datos(seleccion, mart)
    pronostico = pd.concat(
        [calcular_pronostico(d, seleccion[nombre]) for nombre, d in datos.items()], ignore_index=True
    )
    manifiesto = construir_manifiesto(pronostico, datos, seleccion, huella_entradas(anos_en_curso=anos))
    guardar(pronostico, manifiesto)

    for nombre, info in manifiesto["objetivos"].items():
        ultima = info["ultima_semana_observada"]
        print(
            f"{nombre}: {info['modelo']}, {info['establecimientos']} establecimientos, "
            f"horizontes {info['horizontes'][0]}-{info['horizontes'][-1]}, "
            f"última semana observada {ultima['ano']}-S{ultima['semana']:02d}.",
            flush=True,
        )
    print(f"Generado en {time.perf_counter() - inicio:.1f}s:", flush=True)
    print(f"  {RUTA_PRONOSTICO.as_posix()}\n  {RUTA_MANIFIESTO.as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
