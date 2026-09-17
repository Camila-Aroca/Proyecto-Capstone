"""Renderiza los diagramas UML de `docs/07-diagramas/` a PNG y SVG.

Convierte cada archivo `.puml` del directorio de diagramas usando PlantUML, de modo
que las imagenes versionadas sean reproducibles desde el fuente de texto.

Requisitos:
  - Java 8 o superior en el PATH.
  - `plantuml.jar`, localizado mediante la variable de entorno `PLANTUML_JAR`
    o en `tools/plantuml.jar` dentro del repositorio.
    Descarga: https://plantuml.com/download

Opcional pero recomendado:
  - Graphviz (`dot`). Mejora notablemente el layout de los diagramas de casos de uso
    y de componentes. Se localiza mediante `GRAPHVIZ_DOT` o en el PATH.
    Si no esta disponible se usa el motor interno Smetana, cuyo resultado es
    correcto pero de menor calidad de diagramacion.

Ejecucion:
    python scripts/render_diagrams.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

DIAGRAMS_DIR = Path("docs/07-diagramas")
FORMATS = ("png", "svg")


def find_plantuml_jar() -> Path:
    """Localiza plantuml.jar mediante variable de entorno o ruta convencional."""
    env_jar = os.environ.get("PLANTUML_JAR")
    candidates = [Path(env_jar)] if env_jar else []
    candidates.append(Path("tools/plantuml.jar"))

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "No se encontro plantuml.jar. Definir la variable de entorno PLANTUML_JAR "
        "o colocar el archivo en tools/plantuml.jar (descarga: https://plantuml.com/download)."
    )


def find_graphviz_dot() -> Optional[str]:
    """Localiza el ejecutable `dot` de Graphviz, si esta disponible."""
    env_dot = os.environ.get("GRAPHVIZ_DOT")
    if env_dot and Path(env_dot).is_file():
        return env_dot
    return shutil.which("dot")


def build_command(jar: Path, dot: Optional[str], fmt: str, sources: List[Path]) -> List[str]:
    """Arma la invocacion de PlantUML para un formato de salida."""
    command = ["java", "-jar", str(jar), "-charset", "UTF-8"]
    if dot:
        command += ["-graphvizdot", dot]
    else:
        command += ["-Playout=smetana"]
    command += [f"-t{fmt}"]
    command += [str(source) for source in sources]
    return command


def main() -> int:
    sources = sorted(DIAGRAMS_DIR.glob("*.puml"))
    if not sources:
        print(f"No hay archivos .puml en {DIAGRAMS_DIR.as_posix()}", file=sys.stderr)
        return 1

    jar = find_plantuml_jar()
    dot = find_graphviz_dot()

    engine = f"Graphviz ({dot})" if dot else "Smetana (motor interno, sin Graphviz)"
    print(f"PlantUML: {jar.as_posix()}")
    print(f"Layout:   {engine}")

    for fmt in FORMATS:
        result = subprocess.run(build_command(jar, dot, fmt, sources), capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return result.returncode
        for source in sources:
            print(f"  generado: {source.with_suffix('.' + fmt).as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
