"""
Orquestador Principal del Pipeline - Proyecto Capstone

Permite la ejecución parcial o total del pipeline de procesamiento de datos,
asegurando la idempotencia (salto de etapas ya procesadas).
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Definición de las etapas del pipeline y sus outputs esperados para idempotencia
STAGES = {
    "download_censo": {
        "module": "src.data.download_censo",
        "outputs": ["data/raw/censo/Cartografia_censo2024_Pais_Comunal.parquet"],
        "depends_on": []
    },
    "download_deis": {
        "module": "src.data.download_deis_sources",
        "outputs": [
            "data/raw/urgencias/AtencionesUrgencia2020.csv",
            "data/raw/urgencias/AtencionesUrgencia2021.csv",
            "data/raw/urgencias/AtencionesUrgencia2022.csv",
            "data/raw/urgencias/AtencionesUrgencia2023.csv",
            "data/raw/urgencias/AtencionesUrgencia2024.csv",
            "data/raw/urgencias/AtencionesUrgencia2025.csv",
            "data/raw/urgencias/AtencionesUrgencia2026.csv",
            "data/raw/egresos/EGRESOS_2020.csv",
            "data/raw/egresos/EGRESOS_2021.csv",
            "data/raw/egresos/EGRESOS_2022.csv",
            "data/raw/egresos/EGRESOS_2023.csv",
            "data/raw/egresos/EGRESOS_2024.csv",
            "data/raw/egresos/EGRESOS_2025.csv"
        ],
        "depends_on": []
    },
    "download_establishments": {
        "module": "src.data.download_establishments",
        "outputs": ["data/raw/deis/establecimientos_salud_actualizado.csv"],
        "depends_on": []
    },
    "clean_establishments": {
        "module": "src.data.clean_establishments",
        "outputs": [
            "data/processed/establecimientos_rm_clean.csv",
            "data/processed/establecimientos_rm_clean.parquet",
            "data/processed/establecimientos_salud_clean.parquet"
        ],
        "depends_on": ["download_establishments"]
    },
    "clean_censo": {
        "module": "src.data.clean_censo_comunas",
        "outputs": ["data/processed/censo/Cartografia_censo2024_RM_Comunal.parquet"],
        "depends_on": ["download_censo"]
    },
    "build_catalogs": {
        "module": "src.data.build_catalogs",
        "outputs": ["data/processed/urgencias/catalogo_f00_f99.csv"],
        "depends_on": []
    },
    "clean_urgencias": {
        "module": "src.data.clean_urgencias",
        "outputs": [
            "data/processed/urgencias/urgencias_rm_2020.parquet",
            "data/processed/urgencias/urgencias_rm_2021.parquet",
            "data/processed/urgencias/urgencias_rm_2022.parquet",
            "data/processed/urgencias/urgencias_rm_2023.parquet",
            "data/processed/urgencias/urgencias_rm_2024.parquet",
            "data/processed/urgencias/urgencias_rm_2025.parquet",
            "data/processed/urgencias/urgencias_rm_2026.parquet"
        ],
        "depends_on": ["download_deis", "clean_establishments", "clean_censo", "build_catalogs"]
    },
    "clean_egresos": {
        "module": "src.data.clean_egresos",
        "outputs": [
            "data/processed/egresos/egresos_2020.parquet",
            "data/processed/egresos/egresos_2021.parquet",
            "data/processed/egresos/egresos_2022.parquet",
            "data/processed/egresos/egresos_2023.parquet",
            "data/processed/egresos/egresos_2024.parquet",
            "data/processed/egresos/egresos_2025.parquet"
        ],
        "depends_on": ["download_deis"]
    },
    "eda_establishments": {
        "module": "scripts.eda_establecimientos_rm",
        "outputs": ["reports/eda/registros_sin_coordenadas.csv"],
        "depends_on": ["clean_establishments"]
    },
    "eda_urgencias": {
        "module": "scripts.eda_demanda_urgencias_rm",
        "outputs": ["data/processed/urgencias/tabla1_demanda_anual_rm.csv"],
        "depends_on": ["clean_urgencias"]
    }
}

# Orden estricto de ejecución
PIPELINE_ORDER = [
    "download_censo",
    "download_deis",
    "download_establishments",
    "clean_establishments",
    "clean_censo",
    "build_catalogs",
    "clean_urgencias",
    "clean_egresos",
    "eda_establishments",
    "eda_urgencias"
]


def check_outputs_exist(outputs: list[str]) -> bool:
    """Verifica que todos los archivos de salida existan, tengan tamaño > 0 y sean legibles."""
    if not outputs:
        return False
    
    for out in outputs:
        p = Path(out)
        if not p.exists() or p.stat().st_size == 0:
            return False
            
        # Validación mínima según tipo
        try:
            ext = p.suffix.lower()
            if ext == '.csv':
                import pandas as pd
                df = pd.read_csv(p, nrows=0, encoding="latin-1")
                if len(df.columns) == 0:
                    return False
            elif ext == '.parquet':
                import pyarrow.parquet as pq
                schema = pq.read_schema(p)
                if len(schema.names) == 0:
                    return False
        except Exception as e:
            logger.warning(f"Archivo corrupto o ilegible {p}: {e}")
            return False

    return True


def run_stage(stage_name: str, force: bool = False, upstream_changed: bool = False) -> bool:
    """Ejecuta una etapa específica. Devuelve True si se ejecutó, False si hizo SKIP."""
    if stage_name not in STAGES:
        logger.error(f"Stage desconocido: {stage_name}")
        sys.exit(1)
        
    config = STAGES[stage_name]
    module = config["module"]
    outputs = config["outputs"]
    
    logger.info(f"--- Evaluando etapa: {stage_name} ---")
    
    if upstream_changed:
        logger.info(f"[FORZADO] Dependencias upstream fueron modificadas. Se ejecutará '{stage_name}'.")
    
    if not force and not upstream_changed and check_outputs_exist(outputs):
        logger.info(f"[SKIP] Etapa '{stage_name}' omitida. Los outputs ya existen y son válidos.")
        return False
        
    logger.info(f"[EJECUTANDO] Etapa '{stage_name}' -> Módulo: {module}")
    try:
        cmd = [sys.executable, "-m", module]
        if force:
            cmd.append("--force")
        subprocess.run(cmd, check=True)
        logger.info(f"[EXITO] Etapa '{stage_name}' finalizada correctamente.\n")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[ERROR] La etapa '{stage_name}' falló con código {e.returncode}.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Orquestador del Pipeline de Datos")
    parser.add_argument(
        "--stage", 
        type=str, 
        choices=PIPELINE_ORDER + ["all"],
        default="all",
        help="Especifica la etapa a ejecutar (o 'all' para todo el pipeline)."
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Fuerza la ejecución ignorando si los archivos de salida ya existen."
    )
    args = parser.parse_args()

    logger.info("Iniciando ejecución del pipeline...")
    
    # Determinar qué etapas evaluar según el --stage indicado
    target_stages = set(PIPELINE_ORDER) if args.stage == "all" else {args.stage}
    if args.stage != "all":
        # Propagar recursivamente dependencias downstream (transitive closure)
        added = True
        while added:
            added = False
            for stage in PIPELINE_ORDER:
                if stage not in target_stages:
                    deps = STAGES[stage].get("depends_on", [])
                    if any(d in target_stages for d in deps):
                        target_stages.add(stage)
                        added = True
                        
    executed_stages = set()
    for stage in PIPELINE_ORDER:
        if stage in target_stages:
            deps = STAGES[stage].get("depends_on", [])
            upstream_changed = any(d in executed_stages for d in deps)
            
            # Solo aplicar args.force a la etapa explícitamente solicitada o a todas si es "all"
            is_explicit_target = (args.stage == "all" or stage == args.stage)
            stage_force = args.force if is_explicit_target else False
            
            executed = run_stage(stage, force=stage_force, upstream_changed=upstream_changed)
            if executed:
                executed_stages.add(stage)
                
    logger.info("Pipeline completado satisfactoriamente.")


if __name__ == "__main__":
    main()
