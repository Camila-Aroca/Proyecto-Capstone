"""Línea base local de SAAD con Docker Compose (C-07): evidencia SOLO del entorno local.

Registra un recorrido repetible de la plataforma levantada con `docker compose up` y lo deja
en `reports/validation/baseline_local/<UTC>/`:

- `informe.md`: entorno (commit, máquina, versiones), contenedores, recorrido de la API,
  limitaciones y capturas.
- `resultados.json`: respuestas resumidas por caso.
- `dataset.csv`: inventario de los archivos que lee la API (ruta, bytes, SHA-256).
- `logs/`: logs recientes de los contenedores `api` y `web`.
- `capturas/`: inicio, tablero y establecimientos.

Sirve como control para contrastar el despliegue en AWS (`scripts/qa_e2e_local_vs_aws.py`),
pero no lo prueba: aquí no se consulta AWS. No se registran el nombre de la máquina ni rutas
del equipo, porque la evidencia se versiona en un repositorio público.

Uso (con `docker compose up -d` y la API lista):
    .venv/bin/python scripts/qa_baseline_local.py [--local URL] [--sin-capturas]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.qa_e2e_local_vs_aws import (  # noqa: E402 - reutiliza casos y utilidades de la E2E
    APROBADO,
    ENDPOINTS,
    FALLIDO,
    Caso,
    capturar,
    intervalos_ordenados,
    pedir,
    resumen_api,
)

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
SALIDA_BASE: Final[Path] = RAIZ / "reports/validation/baseline_local"
# Lo que lee la API al arrancar (igual a lo que publica infra/aws/scripts/subir_datos.sh).
DATASET: Final[tuple[str, ...]] = ("data/processed", "reports", "data/raw/poblacion")
EXCLUIR_DATASET: Final[tuple[str, ...]] = ("reports/validation/",)
LINEAS_LOG: Final[int] = 400


def comando(*args: str, cwd: Path = RAIZ) -> str:
    """Salida de un comando, o el error como texto: un dato faltante no detiene la línea base."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=120)
        return (r.stdout or r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as error:
        return f"no disponible ({type(error).__name__})"


def sin_rutas_locales(texto: str) -> str:
    """Quita la ruta del repositorio y el home del equipo de cualquier texto."""
    for ruta, marcador in ((str(RAIZ), "<repo>"), (str(Path.home()), "<home>")):
        texto = texto.replace(ruta, marcador)
    return texto


def entorno() -> dict[str, Any]:
    """Commit, máquina (sin nombre de host) y versiones de las herramientas."""
    memoria = next((l for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal")), "")
    cpu = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                if l.startswith("model name")), platform.processor())
    so = next((l.split("=", 1)[1].strip('"') for l in Path("/etc/os-release").read_text().splitlines()
               if l.startswith("PRETTY_NAME=")), platform.system())
    return {
        "commit": comando("git", "rev-parse", "--short", "HEAD"),
        "rama": comando("git", "rev-parse", "--abbrev-ref", "HEAD"),
        "cambios_sin_commit_en_codigo": bool(comando("git", "status", "--porcelain", "--", "src", "frontend/src",
                                                     "Dockerfile", "docker-compose.yml", "requirements.txt")),
        "sistema_operativo": so,
        "kernel": platform.release(),
        "cpu": cpu,
        "nucleos": os.cpu_count(),
        "memoria_gib": round(int(re.sub(r"\D", "", memoria) or 0) / 2**20, 1),
        "docker": comando("docker", "version", "--format", "{{.Server.Version}}"),
        "docker_compose": comando("docker", "compose", "version", "--short"),
        "python_equipo": platform.python_version(),
        "node_equipo": comando("node", "--version"),
    }


def contenedores() -> list[dict[str, Any]]:
    """Estado, imagen y versiones de librerías de cada servicio de Docker Compose."""
    servicios = []
    for linea in comando("docker", "compose", "ps", "--format", "json").splitlines():
        try:
            s = json.loads(linea)
        except ValueError:
            continue
        imagen = comando("docker", "image", "inspect", s["Image"], "--format", "{{.Id}} {{.Created}}").split()
        servicios.append({"servicio": s["Service"], "estado": s["State"], "detalle": s["Status"],
                          "imagen": s["Image"], "id_imagen": imagen[0][:19] if imagen else None,
                          "imagen_creada": imagen[1] if len(imagen) > 1 else None})
    versiones = comando("docker", "compose", "exec", "-T", "api", "python", "-c",
                        "import sys, fastapi, pandas, pyarrow, lightgbm; "
                        "print(sys.version.split()[0], fastapi.__version__, pandas.__version__, "
                        "pyarrow.__version__, lightgbm.__version__)").split()
    variable = comando("docker", "compose", "exec", "-T", "api", "printenv", "SAAD_USAR_PRONOSTICO_DESACTUALIZADO")
    for s in servicios:
        if s["servicio"] == "api" and len(versiones) == 5:
            s["versiones"] = dict(zip(("python", "fastapi", "pandas", "pyarrow", "lightgbm"), versiones))
            s["SAAD_USAR_PRONOSTICO_DESACTUALIZADO"] = variable or "0"
    return servicios


def inventario_dataset(destino: Path) -> dict[str, Any]:
    """Escribe dataset.csv con ruta, bytes y SHA-256 de cada archivo que lee la API."""
    filas = []
    for base in DATASET:
        for archivo in sorted((RAIZ / base).rglob("*")):
            relativa = archivo.relative_to(RAIZ).as_posix()
            if archivo.is_file() and not relativa.startswith(EXCLUIR_DATASET):
                sha = hashlib.sha256()
                with archivo.open("rb") as f:
                    for bloque in iter(lambda: f.read(1 << 20), b""):
                        sha.update(bloque)
                filas.append({"ruta": relativa, "bytes": archivo.stat().st_size, "sha256": sha.hexdigest()})
    with destino.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["ruta", "bytes", "sha256"])
        escritor.writeheader()
        escritor.writerows(filas)
    huella = hashlib.sha256("".join(f"{x['ruta']}{x['sha256']}" for x in filas).encode()).hexdigest()
    manifiestos = {}
    for m in sorted((RAIZ / "data/processed/modeling").glob("*manifest.json")):
        datos = json.loads(m.read_text(encoding="utf-8"))
        manifiestos[m.name] = {"generado_en_utc": datos.get("generado_en_utc"), "modelo": datos.get("modelo")}
    return {"archivos": len(filas), "megabytes": round(sum(x["bytes"] for x in filas) / 2**20, 1),
            "huella_sha256": huella, "manifiestos_pronostico": manifiestos}


def recorrido(local: str) -> tuple[list[Caso], list[str]]:
    """Los mismos endpoints de la E2E, solo contra el entorno local."""
    casos = []
    with httpx.Client(follow_redirects=False) as cliente:
        r = pedir(cliente, local + "/")
        casos.append(Caso("CP-SAAD-028", "Portal local (nginx)", "LOCAL",
                          APROBADO if r.estado == 200 and "<div id=\"root\"" in str(r.cuerpo) else FALLIDO,
                          f"HTTP {r.estado}", {"http": r.estado, "ms": r.ms}))
        for caso, nombre, ruta, esperado in ENDPOINTS:
            r = pedir(cliente, local + ruta)
            resumen = resumen_api(nombre, r)
            fallas = [] if r.estado == esperado else [f"HTTP {r.estado or r.error} (se esperaba {esperado})"]
            if nombre == "pronosticos" and r.estado == 200:
                fallas += [f"intervalo desordenado {m}" for m in intervalos_ordenados(r.cuerpo)]
            if fallas and isinstance(r.cuerpo, dict) and "detail" in r.cuerpo:
                fallas.append(f"detalle de la API: {str(r.cuerpo['detail'])[:220]}")
            casos.append(Caso(caso, f"GET {ruta}", "LOCAL", FALLIDO if fallas else APROBADO,
                              "; ".join(fallas) or f"HTTP {r.estado} en {r.ms} ms",
                              {"http": r.estado, "ms": r.ms, **resumen}))
        meta = pedir(cliente, local + "/api/v1/meta")
    advertencias = meta.cuerpo.get("advertencias", []) if meta.estado == 200 else []
    return casos, advertencias


def guardar_logs(carpeta: Path) -> list[str]:
    carpeta.mkdir(parents=True, exist_ok=True)
    guardados = []
    for servicio in ("api", "web"):
        texto = comando("docker", "compose", "logs", "--no-color", "--timestamps", "--tail", str(LINEAS_LOG), servicio)
        (carpeta / f"{servicio}.log").write_text(sin_rutas_locales(texto) + "\n", encoding="utf-8")
        guardados.append(f"{servicio}.log")
    return guardados


def escribir_informe(carpeta: Path, datos: dict[str, Any], casos: list[Caso], capturas: list[str]) -> None:
    e, d = datos["entorno"], datos["dataset"]
    aprobados = sum(c.estado == APROBADO for c in casos)
    fallidos = [c for c in casos if c.estado == FALLIDO]
    lineas = [
        "# Línea base local de SAAD con Docker Compose (C-07)",
        "",
        "> Evidencia **solo del entorno local**. Sirve como control para contrastar el despliegue en AWS; "
        "no prueba AWS.",
        "",
        "## Entorno",
        "",
        "| Dato | Valor |", "|---|---|",
        f"| Fecha (UTC) | {datos['fecha_utc']} |",
        f"| Commit | `{e['commit']}` (rama `{e['rama']}`) |",
        f"| Cambios sin commit en el código | {'sí' if e['cambios_sin_commit_en_codigo'] else 'no'} |",
        f"| Máquina | {e['cpu']}, {e['nucleos']} núcleos, {e['memoria_gib']} GiB de RAM |",
        f"| Sistema operativo | {e['sistema_operativo']} (kernel {e['kernel']}) |",
        f"| Docker / Compose | {e['docker']} / {e['docker_compose']} |",
        f"| Python / Node del equipo | {e['python_equipo']} / {e['node_equipo']} |",
        f"| URL local | {datos['local']} |",
        f"| Comando | `{datos['comando']}` |",
        "",
        "## Contenedores",
        "",
        "| Servicio | Estado | Imagen | Id | Creada |", "|---|---|---|---|---|",
    ]
    for s in datos["contenedores"]:
        lineas.append(f"| {s['servicio']} | {s['detalle']} | `{s['imagen']}` | `{s['id_imagen']}` | {s['imagen_creada']} |")
    api = next((s for s in datos["contenedores"] if s["servicio"] == "api"), {})
    if api.get("versiones"):
        v = api["versiones"]
        lineas += ["", f"Versiones en el contenedor `api`: Python {v['python']}, FastAPI {v['fastapi']}, "
                       f"pandas {v['pandas']}, PyArrow {v['pyarrow']}, LightGBM {v['lightgbm']}. "
                       f"`SAAD_USAR_PRONOSTICO_DESACTUALIZADO={api.get('SAAD_USAR_PRONOSTICO_DESACTUALIZADO')}`."]
    lineas += [
        "", "## Dataset",
        "",
        f"La API lee {d['archivos']} archivos ({d['megabytes']} MB) de `data/processed/`, `reports/` y "
        f"`data/raw/poblacion/`. Inventario con SHA-256 en [`dataset.csv`](dataset.csv); huella del conjunto: "
        f"`{d['huella_sha256'][:16]}…`. Si la huella coincide, otro equipo está usando exactamente los mismos datos.",
        "",
        "| Pronóstico persistido | Generado (UTC) | Modelo |", "|---|---|---|",
    ]
    lineas += [f"| `{n}` | {m['generado_en_utc']} | {m['modelo']} |" for n, m in d["manifiestos_pronostico"].items()]
    lineas += ["", "## Recorrido", "",
               f"**Resultado:** {aprobados} aprobados · {len(fallidos)} fallidos de {len(casos)} casos.", "",
               "| Caso | Prueba | Estado | Detalle |", "|---|---|---|---|"]
    lineas += [f"| {c.id} | {c.nombre} | **{c.estado}** | {c.detalle.replace('|', '/')} |" for c in casos]
    lineas += ["", "## Limitaciones explícitas", ""]
    lineas += [f"- **{c.nombre}:** {c.detalle}" for c in fallidos]
    lineas += [f"- **Advertencia de la API:** {a}" for a in datos["advertencias"]]
    if capturas:
        lineas += ["", "## Capturas", ""] + [f"![{n}](capturas/{n})" for n in capturas]
    lineas += ["", "## Logs", "", "Últimas líneas de cada contenedor: "
               + ", ".join(f"[`logs/{n}`](logs/{n})" for n in datos["logs"]) + ".", ""]
    (carpeta / "informe.md").write_text(sin_rutas_locales("\n".join(lineas)), encoding="utf-8")
    (carpeta / "resultados.json").write_text(
        sin_rutas_locales(json.dumps({**datos, "casos": [asdict(c) for c in casos]},
                                     ensure_ascii=False, indent=2, default=str)), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Línea base local de SAAD con Docker Compose (C-07).")
    parser.add_argument("--local", default="http://localhost:8080", help="URL del frontend local")
    parser.add_argument("--sin-capturas", action="store_true", help="No sacar capturas con Chrome")
    parser.add_argument("--salida", type=Path, default=SALIDA_BASE, help="Carpeta base de la evidencia")
    args = parser.parse_args()

    fecha = datetime.now(timezone.utc)
    carpeta = args.salida / fecha.strftime("%Y%m%dT%H%M%SZ")
    (carpeta / "capturas").mkdir(parents=True, exist_ok=True)

    print("→ Entorno y contenedores…", flush=True)
    datos: dict[str, Any] = {"fecha_utc": fecha.isoformat(timespec="seconds"), "local": args.local,
                             "comando": "scripts/qa_baseline_local.py", "entorno": entorno(),
                             "contenedores": contenedores()}
    print("→ Inventario del dataset…", flush=True)
    datos["dataset"] = inventario_dataset(carpeta / "dataset.csv")
    print("→ Recorrido de la API…", flush=True)
    casos, datos["advertencias"] = recorrido(args.local)
    capturas: list[str] = []
    if not args.sin_capturas:
        print("→ Capturas…", flush=True)
        for vista, ruta in (("inicio", "/"), ("tablero", "/#/tablero"), ("establecimientos", "/#/establecimientos")):
            archivo = f"local_{vista}.png"
            if capturar(args.local + ruta, carpeta / "capturas" / archivo) is None:
                capturas.append(archivo)
    print("→ Logs…", flush=True)
    datos["logs"] = guardar_logs(carpeta / "logs")
    escribir_informe(carpeta, datos, casos, capturas)
    print(f"Informe: {carpeta / 'informe.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
