"""Ejecuta un ciclo de pruebas de SAAD y resume el resultado por entorno (C-06).

Un ciclo corre, en orden, todo lo que hoy se puede verificar de forma reproducible:

1. Tests de Python (`pytest tests/`), con informe JUnit.
2. Verificación del CI en local: síntesis CDK y cfn-lint. Es la contingencia mientras los
   pipelines de CodePipeline estén bloqueados por la conexión con GitHub.
3. Línea base LOCAL con Docker Compose (`scripts/qa_baseline_local.py`).
4. Prueba end-to-end en AWS contrastada con local (`scripts/qa_e2e_local_vs_aws.py`).
5. Contrato API/frontend (`scripts/qa_contrato_api.py`).

Deja en `reports/validation/ciclos_pruebas/ciclo_<NN>_<UTC>/` el resumen (`resumen.md`,
`resumen.json`), el JUnit de pytest y la evidencia de cada paso, y el estado de los 70 casos
del catálogo CP-SAAD-2026. El registro de defectos (`registro_defectos.md`) es un documento
curado: este script no lo modifica, solo informa qué casos fallaron para actualizarlo.

Estados: APROBADO, FALLIDO, BLOCKED (no se puede ejecutar por una dependencia, con su
contingencia) y NO EJECUTADO (fuera del alcance de este ciclo, con motivo).

Uso:
    .venv/bin/python scripts/qa_ciclo_pruebas.py --ciclo 2 [--sin-aws] [--reinicio]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
SALIDA_BASE: Final[Path] = RAIZ / "reports/validation/ciclos_pruebas"
PY: Final[str] = sys.executable
CATALOGO: Final[Path] = RAIZ / "docs/05-entregas/Fase_2_2/Pruebas/SAAD_Casos_de_Prueba_70_Fase_2_2_AWS.docx"
CDK: Final[Path] = RAIZ / "infra/aws/cdk"

APROBADO, FALLIDO, BLOCKED, NO_EJECUTADO = "APROBADO", "FALLIDO", "BLOCKED", "NO EJECUTADO"

# Casos del catálogo que hoy no se pueden ejecutar porque falta un dato o un despliegue.
# El defecto que los bloquea está en registro_defectos.md.
BLOQUEOS: Final[dict[str, str]] = {
    **{c: "DEF-02: sin datos de establecimientos (mart semanal y pronóstico no publicados)"
       for c in ("CP-SAAD-038", "CP-SAAD-039", "CP-SAAD-040", "CP-SAAD-041")},
    **{c: "DEF-01: sin dotación ni ocupación de camas de psiquiatría"
       for c in ("CP-SAAD-042", "CP-SAAD-043", "CP-SAAD-044", "CP-SAAD-045", "CP-SAAD-059")},
    **{c: "DEF-03: sin mart ni pronóstico de suicidios"
       for c in ("CP-SAAD-048", "CP-SAAD-050", "CP-SAAD-052")},
}
# Casos cubiertos indirectamente por otro caso automatizado: caso → (caso fuente, entorno o None = ambos).
DERIVADOS: Final[dict[str, tuple[str, str | None]]] = {
    "CP-SAAD-054": ("CP-SAAD-022", None),   # el orden de los intervalos se verifica dentro de /pronosticos
    "CP-SAAD-006": ("CP-SAAD-020", "AWS"),  # la API en Fargate sirve series con los outputs leídos de S3
}
CICLO_COMPLETO: Final[str] = "CP-SAAD-070"  # lo cubre la E2E completa del ciclo
NO_APLICA: Final[str] = "—"


def correr(args: list[str], log: Path | None = None, entorno: dict[str, str] | None = None,
           timeout: int = 1800) -> tuple[int, str]:
    r = subprocess.run(args, cwd=RAIZ, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(entorno or {})})
    salida = (r.stdout + r.stderr).replace(str(RAIZ), "<repo>").replace(str(Path.home()), "<home>")
    if log:
        log.write_text(salida, encoding="utf-8")
    return r.returncode, salida


def ultimo_resultado(carpeta: Path) -> dict[str, Any] | None:
    archivos = sorted(carpeta.glob("*/resultados.json"))
    return json.loads(archivos[-1].read_text(encoding="utf-8")) if archivos else None


# ------------------------------------------------------------------------------ pasos

def paso_pytest(carpeta: Path) -> dict[str, Any]:
    junit = carpeta / "pytest.xml"
    codigo, salida = correr([PY, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
                             f"--junitxml={junit}"], carpeta / "pytest.log")
    suite = ET.parse(junit).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    total, fallas, errores, omitidos = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    deseleccionados = re.search(r"(\d+) deselected", salida)
    fallidos = [f"{c.get('classname')}::{c.get('name')}" for c in suite.iter("testcase")
                if c.find("failure") is not None or c.find("error") is not None]
    return {"estado": APROBADO if codigo == 0 else FALLIDO, "total": total,
            "aprobados": total - fallas - errores - omitidos, "fallidos": fallas + errores,
            "omitidos": omitidos, "deseleccionados": int(deseleccionados.group(1)) if deseleccionados else 0,
            "tests_fallidos": fallidos}


def estado_conexion_ci() -> str:
    codigo, salida = correr(["aws", "codeconnections", "list-connections", "--region", "us-east-1",
                             "--query", "Connections[?ConnectionName=='saad-github'].ConnectionStatus",
                             "--output", "text"])
    return salida.strip() if codigo == 0 and salida.strip() else "desconocido"


def paso_ci_local(carpeta: Path) -> dict[str, Any]:
    """Lo mismo que hace CodeBuild saad-verificar (sin pytest, que ya corrió): síntesis y cfn-lint."""
    venv = CDK / ".venv/bin"
    if not (venv / "cfn-lint").exists():
        return {"estado": BLOCKED, "detalle": "Falta el venv de CDK con cfn-lint (infra/aws/cdk/.venv)."}
    entorno = {"PATH": f"{venv}:{os.environ['PATH']}", "SAAD_SINTESIS_SIN_CUENTA": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        codigo, salida = _sintetizar(tmp, entorno)
        if codigo != 0:
            (carpeta / "ci_local.log").write_text(salida, encoding="utf-8")
            return {"estado": FALLIDO, "detalle": "La síntesis CDK falló (ver ci_local.log)."}
        plantillas = sorted(Path(tmp).glob("*.template.json"))
        codigo, salida = correr([str(venv / "cfn-lint"), "--non-zero-exit-code", "error", *map(str, plantillas)])
    (carpeta / "ci_local.log").write_text(salida.replace(tmp, "<cdk.out>"), encoding="utf-8")
    advertencias = len(re.findall(r"^W\d{4}", salida, re.M))
    return {"estado": APROBADO if codigo == 0 else FALLIDO,
            "detalle": f"{len(plantillas)} plantillas sintetizadas; cfn-lint sin errores, "
                       f"{advertencias} advertencias de recursos internos de CDK" if codigo == 0
                       else "cfn-lint encontró errores (ver ci_local.log)."}


def _sintetizar(tmp: str, entorno: dict[str, str]) -> tuple[int, str]:
    r = subprocess.run(["npx", "--yes", "aws-cdk@2", "synth", "-q", "-o", tmp, "-c", "api_tag=ci",
                        "-c", "cloudfront_prefix_list=pl-00000000", "-c", "origin_secret=ci"],
                       cwd=CDK, capture_output=True, text=True, timeout=600, env={**os.environ, **entorno})
    return r.returncode, r.stdout + r.stderr


def paso_script(script: str, carpeta: Path, *extra: str) -> dict[str, Any] | None:
    carpeta.mkdir(parents=True, exist_ok=True)
    correr([PY, f"scripts/{script}", "--salida", str(carpeta), *extra], carpeta / "ejecucion.log")
    return ultimo_resultado(carpeta)


def paso_contrato() -> dict[str, Any]:
    codigo, _ = correr([PY, "scripts/qa_contrato_api.py"])
    datos = json.loads((RAIZ / "reports/validation/contrato_api/comparacion_api_frontend.json").read_text())
    return {"estado": APROBADO if codigo == 0 else FALLIDO, **datos["conteo"]}


# -------------------------------------------------------------------------- catálogo

def leer_catalogo() -> dict[str, str]:
    import docx
    documento = docx.Document(str(CATALOGO))
    casos = {}
    for p in documento.paragraphs:
        m = re.match(r"(CP-SAAD-\d{3})\s+·\s+(.+)", p.text.strip())
        if m:
            casos[m.group(1)] = m.group(2).strip()
    return casos


def estados_por_entorno(local: dict | None, aws: dict | None) -> dict[str, dict[str, tuple[str, str]]]:
    """Estado de cada caso automatizado en LOCAL y AWS: id → {entorno: (estado, detalle)}."""
    estados: dict[str, dict[str, list[tuple[str, str]]]] = {}

    def agregar(caso: str, entorno: str, estado: str, detalle: str) -> None:
        estados.setdefault(caso, {}).setdefault(entorno, []).append((estado, detalle))

    for c in (local or {}).get("casos", []):
        agregar(c["id"], "LOCAL", c["estado"], c["detalle"])
    for c in (aws or {}).get("casos", []):
        if c["entorno"] == "LOCAL+AWS":
            falla_aws = c["estado"] == FALLIDO and ("AWS:" in c["detalle"] or "difiere" in c["detalle"])
            agregar(c["id"], "AWS", FALLIDO if falla_aws else APROBADO, c["detalle"])
        elif c["id"] != "—":
            agregar(c["id"], "AWS", c["estado"], c["detalle"])
    resultado = {}
    for caso, por_entorno in estados.items():
        resultado[caso] = {}
        for entorno, lista in por_entorno.items():
            if any(e == FALLIDO for e, _ in lista):
                resultado[caso][entorno] = (FALLIDO, "; ".join(d for e, d in lista if e == FALLIDO))
            elif all(e == APROBADO for e, _ in lista):
                resultado[caso][entorno] = (APROBADO, "")
            else:
                resultado[caso][entorno] = lista[0]
    return resultado


def matriz_catalogo(catalogo: dict[str, str], estados: dict[str, dict[str, tuple[str, str]]],
                    hay_aws: bool, conteo_aws: dict[str, int] | None = None) -> list[dict[str, str]]:
    filas = []
    for caso, nombre in catalogo.items():
        fuente = estados.get(caso, {})
        nota = ""
        if not fuente and caso in DERIVADOS:
            origen, entorno = DERIVADOS[caso]
            fuente = {k: v for k, v in estados.get(origen, {}).items() if entorno in (None, k)}
            nota = f"Cubierto por {origen}."
        if caso == CICLO_COMPLETO and conteo_aws:
            fallos = conteo_aws.get(FALLIDO, 0)
            fuente = {"AWS": (FALLIDO if fallos else APROBADO, "")}
            nota = (f"Ciclo completo ejecutado y comparado con local; {fallos} casos fallan en ambos entornos "
                    "(ver casos fallidos)." if fallos else "Ciclo completo ejecutado; sin fallos.")
        local = fuente.get("LOCAL", ("", ""))[0]
        aws = fuente.get("AWS", ("", ""))[0]
        nota = nota or next((d for _, d in fuente.values() if d), "")
        if not local and not aws:
            if caso in BLOQUEOS:
                local = aws = BLOCKED
                nota = BLOQUEOS[caso]
            else:
                local = aws = NO_EJECUTADO
                nota = "Prueba manual de interfaz o de operación; no automatizada en este ciclo."
        if not hay_aws and aws in ("", APROBADO, FALLIDO):
            aws = BLOCKED
        filas.append({"caso": caso, "nombre": nombre, "local": local or NO_APLICA, "aws": aws or NO_APLICA,
                      "nota": nota})
    return filas


# ---------------------------------------------------------------------------- resumen

def contar(filas: list[dict[str, str]], clave: str) -> dict[str, int]:
    return {e: sum(f[clave] == e for f in filas) for e in (APROBADO, FALLIDO, BLOCKED, NO_EJECUTADO, NO_APLICA)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ciclo de pruebas de SAAD (C-06).")
    parser.add_argument("--ciclo", type=int, required=True, help="Número del ciclo")
    parser.add_argument("--sin-aws", action="store_true", help="No probar AWS (se marca BLOCKED)")
    parser.add_argument("--reinicio", action="store_true", help="Incluir la prueba de reinicio de ECS")
    args = parser.parse_args()

    fecha = datetime.now(timezone.utc)
    carpeta = SALIDA_BASE / f"ciclo_{args.ciclo:02d}_{fecha.strftime('%Y%m%dT%H%M%SZ')}"
    carpeta.mkdir(parents=True, exist_ok=True)
    commit = correr(["git", "rev-parse", "--short", "HEAD"])[1].strip()

    print("→ pytest…", flush=True)
    pytest = paso_pytest(carpeta)
    print("→ Verificación del CI en local (síntesis CDK y cfn-lint)…", flush=True)
    ci = {**paso_ci_local(carpeta), "conexion": estado_conexion_ci()}
    print("→ Línea base local…", flush=True)
    local = paso_script("qa_baseline_local.py", carpeta / "local")
    aws = None
    if not args.sin_aws:
        print("→ E2E en AWS…", flush=True)
        aws = paso_script("qa_e2e_local_vs_aws.py", carpeta / "aws", *(["--reinicio"] if args.reinicio else []))
    print("→ Contrato API/frontend…", flush=True)
    contrato = paso_contrato()

    catalogo = leer_catalogo()
    filas = matriz_catalogo(catalogo, estados_por_entorno(local, aws), aws is not None,
                            aws["conteo"] if aws else None)
    c_local, c_aws = contar(filas, "local"), contar(filas, "aws")
    fallidos = [f for f in filas if FALLIDO in (f["local"], f["aws"])]

    def rel(p: Path) -> str:
        return p.relative_to(carpeta).as_posix()

    ev_local = sorted((carpeta / "local").glob("*/informe.md"))
    ev_aws = sorted((carpeta / "aws").glob("*/informe.md"))
    L = [
        f"# Ciclo {args.ciclo} de pruebas de SAAD (C-06)",
        "",
        f"- **Fecha (UTC):** {fecha.isoformat(timespec='seconds')} · **Commit:** `{commit}`",
        f"- **Ejecutado con:** `scripts/qa_ciclo_pruebas.py --ciclo {args.ciclo}"
        + (" --sin-aws" if args.sin_aws else "") + (" --reinicio" if args.reinicio else "") + "`",
        "- **Registro de defectos:** [`../registro_defectos.md`](../registro_defectos.md)",
        "",
        "## Resultado por entorno",
        "",
        "| Verificación | Entorno | Estado | Detalle | Evidencia |",
        "|---|---|---|---|---|",
        f"| Tests de Python (`pytest`) | Equipo | **{pytest['estado']}** | {pytest['aprobados']} aprobados, "
        f"{pytest['fallidos']} fallidos, {pytest['omitidos']} omitidos, {pytest['deseleccionados']} deseleccionados "
        f"(marcados `data_integration`) | [`pytest.xml`](pytest.xml) · [`pytest.log`](pytest.log) |",
        f"| Verificación del CI: síntesis CDK y cfn-lint | Equipo (contingencia) | **{ci['estado']}** | {ci['detalle']} | [`ci_local.log`](ci_local.log) |",
        f"| CI en CodePipeline (`saad-pr`, `saad-despliegue`) | AWS | **{BLOCKED if ci['conexion'] != 'AVAILABLE' else NO_EJECUTADO}** | "
        f"Conexión con GitHub en estado `{ci['conexion']}`: falta que la dueña del repositorio la apruebe. "
        "Contingencia: la misma verificación se ejecuta en local (fila anterior). | — |",
    ]
    if local:
        r = local["casos"]
        L.append(f"| Línea base (Docker Compose) | LOCAL | **{FALLIDO if any(c['estado'] == FALLIDO for c in r) else APROBADO}** | "
                 f"{sum(c['estado'] == APROBADO for c in r)} de {len(r)} casos aprobados | "
                 + (f"[`{rel(ev_local[-1])}`]({rel(ev_local[-1])})" if ev_local else "—") + " |")
    if aws:
        a = aws["conteo"]
        L.append(f"| E2E CloudFront → ALB → ECS, contrastada con local | AWS | **{FALLIDO if a['FALLIDO'] else APROBADO}** | "
                 f"{a['APROBADO']} aprobados, {a['FALLIDO']} fallidos, {a['NO EJECUTADO']} no ejecutados | "
                 + (f"[`{rel(ev_aws[-1])}`]({rel(ev_aws[-1])})" if ev_aws else "—") + " |")
    else:
        L.append("| E2E en AWS | AWS | **BLOCKED** | Ciclo ejecutado con `--sin-aws`. | — |")
    L.append(f"| Contrato API/frontend | Código | **{contrato['estado']}** | {contrato['ERROR']} errores, "
             f"{contrato['ADVERTENCIA']} advertencias, {contrato['INFO']} observaciones | "
             "[`comparacion_api_frontend.md`](../../contrato_api/comparacion_api_frontend.md) |")
    L += [
        "",
        f"## Catálogo CP-SAAD-2026 ({len(filas)} casos)",
        "",
        "| Entorno | Aprobados | Fallidos | BLOCKED | No ejecutados | No aplica |",
        "|---|---|---|---|---|---|",
        *[f"| {n} | {c[APROBADO]} | {c[FALLIDO]} | {c[BLOCKED]} | {c[NO_EJECUTADO]} | {c[NO_APLICA]} |"
          for n, c in (("LOCAL", c_local), ("AWS", c_aws))],
        "",
        "- **No ejecutado:** prueba manual de interfaz u operación que este ciclo no automatiza, o caso que "
        "no aplica al diseño desplegado (el motivo está en la nota). No cuenta como aprobado.",
        "- **BLOCKED:** no se puede ejecutar por un defecto abierto; la nota indica cuál.",
        f"- **{NO_APLICA}:** el caso no aplica a ese entorno (p. ej. CloudFront o ECS en local).",
        "",
        "| Caso | Prueba | LOCAL | AWS | Nota |",
        "|---|---|---|---|---|",
    ]
    L += [f"| {f['caso']} | {f['nombre']} | {f['local']} | {f['aws']} | {f['nota'][:200].replace('|', '/')} |"
          for f in filas]
    L += ["", "## Casos fallidos (para el registro de defectos)", ""]
    L += [f"- **{f['caso']} · {f['nombre']}** (LOCAL {f['local']}, AWS {f['aws']}): {f['nota'][:220]}"
          for f in fallidos] or ["- Ninguno."]
    if pytest["tests_fallidos"]:
        L += ["", "Tests de Python fallidos:", ""] + [f"- `{t}`" for t in pytest["tests_fallidos"]]
    L.append("")
    (carpeta / "resumen.md").write_text("\n".join(L), encoding="utf-8")
    (carpeta / "resumen.json").write_text(json.dumps({
        "ciclo": args.ciclo, "fecha_utc": fecha.isoformat(timespec="seconds"), "commit": commit,
        "pytest": pytest, "ci": ci, "contrato": contrato, "catalogo": filas,
        "conteo_local": c_local, "conteo_aws": c_aws}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resumen: {carpeta.relative_to(RAIZ)}/resumen.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
