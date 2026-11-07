"""Stage `forecast_suicidios`: genera y persiste el pronóstico semanal de suicidios vigente.

Ajusta la selección congelada del benchmark (`benchmark_suicidios`) con todas las
semanas completas del mart y pronostica los horizontes 1-8 de la región y de cada
comuna de residencia. Persiste el resultado con un manifiesto que registra el
SHA256 del mart y de la selección: si cualquiera cambia, el pronóstico deja de ser
vigente y la API responde 503 en vez de servirlo. Siempre regenera; el orquestador
decide el SKIP.

Uso (vía pipeline): `python scripts/run_pipeline.py --stage forecast_suicidios`
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import suicidios as su  # noqa: E402


def main() -> int:
    seleccion = su.cargar_seleccion()
    mart = su.load_mart()
    pronostico, panel = su.calcular_pronostico(mart, seleccion)
    manifiesto = su.construir_manifiesto(pronostico, panel, mart, seleccion, su.huella())
    su.guardar(pronostico, manifiesto)
    ultima = manifiesto["ultima_semana_observada"]
    region = pronostico[pronostico["nivel"] == "region"]
    print(f"Pronóstico de suicidios persistido: {manifiesto['filas']} filas, {manifiesto['series']['total']} series; "
          f"última semana observada {ultima['ano']}-S{ultima['semana']:02d}; región h1-h8 media "
          f"{region['y_pred'].mean():.2f} por semana.", flush=True)
    return 0


if __name__ == "__main__":
    if "--force" in sys.argv:
        sys.argv.remove("--force")
    raise SystemExit(main())
