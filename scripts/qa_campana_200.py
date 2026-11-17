"""Ejecuta casos automatizables del catálogo SAAD-CP v2.1 (200 casos) y registra la evidencia.

Para cada caso pedido lee del catálogo (`docs/05-entregas/Fase_2_3/Pruebas/`) su selector de
pytest, lo ejecuta con un JUnit propio y deja el resultado con el formato del plan de pruebas:
ID, run_id, fecha y hora, ejecutor real, entorno, SHA, snapshot, resultado real, estado,
evidencia, defecto y observaciones.

La evidencia va en `reports/validation/ciclos_pruebas/ciclo_<NN>_<UTC>/catalogo_200/`. Si el
ciclo ya existe se reutiliza su carpeta y solo se agrega `catalogo_200/`: el resumen del ciclo
(`resumen.md`, `resumen.json`) lo consolida quien coordina el ciclo, no este script. Una
carpeta `catalogo_200/` existente nunca se sobrescribe: repetir exige otro ciclo.

Los casos sin selector de pytest (interfaz, API con datos reales o AWS) se registran como
NO EJECUTADO con su motivo. Este script no modifica el catálogo ni el registro de defectos.

Uso:
    python scripts/qa_campana_200.py --ciclo 5 --ejecutor "Nombre Apellido" --casos 081-096,108-110
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse
from importlib import metadata
from pathlib import Path
from typing import Any, Final

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
SALIDA_BASE: Final[Path] = RAIZ / "reports/validation/ciclos_pruebas"
CATALOGO: Final[Path] = RAIZ / "docs/05-entregas/Fase_2_3/Pruebas/SAAD_Casos_de_Prueba_200_AWS_2026.docx"
SUBCARPETA: Final[str] = "catalogo_200"
ENTORNO_FIXTURE: Final[str] = "FIXTURE (pytest con tmp_path/monkeypatch, aislado de RAW y AWS)"
SNAPSHOT_FIXTURE: Final[str] = "No aplica: datos sintéticos de fixtures del repositorio"
LIBRERIAS: Final[tuple[str, ...]] = (
    "pytest", "pandas", "numpy", "pyarrow", "scikit-learn", "statsmodels", "lightgbm", "fastapi",
)
APROBADO, FALLIDO, NO_EJECUTADO = "APROBADO", "FALLIDO", "NO EJECUTADO"

_ENCABEZADO = re.compile(r"^SAAD-CP-(\d{3})\s{2}(.+)$")
_SELECTOR = re.compile(r"python -m pytest (.+?) -q --junitxml=EVIDENCIA/")
_GET = re.compile(r"^2\.\s+GET\s+(\S+)")
_HTTP = re.compile(r"HTTP\s+(\d{3})")
_Y_LUEGO = re.compile(r"^2\.\s+GET\s+(\S+?=)(\d+) y luego \w+=(\d+)")
_RANGO = re.compile(r"desde=(\d{4}-\d{2}-\d{2}) con hasta=desde\+(\d+) d[ií]as y luego \+(\d+)")
ENTORNO_LOCAL: Final[str] = "LOCAL (API local con Uvicorn en 127.0.0.1)"
ENTORNO_AWS: Final[str] = "AWS (URL desplegada; host redactado)"
SNAPSHOT_HTTP_NO_DISPONIBLE: Final[str] = "No disponible: /meta no respondió"


def parsear_casos(texto: str) -> list[str]:
    """Convierte '081-083,090' en ['081', '082', '083', '090'] (orden de aparición, sin repetir)."""
    ids: list[str] = []
    for parte in (p.strip() for p in texto.split(",") if p.strip()):
        if "-" in parte:
            ini, fin = (int(x) for x in parte.split("-", 1))
            if ini > fin:
                raise ValueError(f"Rango invertido: {parte}")
            tramo = range(ini, fin + 1)
        else:
            tramo = range(int(parte), int(parte) + 1)
        for n in tramo:
            if not 1 <= n <= 200:
                raise ValueError(f"Caso fuera del catálogo (1-200): {n}")
            if f"{n:03d}" not in ids:
                ids.append(f"{n:03d}")
    return ids


def leer_catalogo(ruta: Path) -> dict[str, dict[str, str | None]]:
    """Lee id → título, módulo, entorno y selector de pytest de cada caso del catálogo."""
    import docx

    casos: dict[str, dict[str, str | None]] = {}
    actual: dict[str, str | None] | None = None
    for parrafo in docx.Document(str(ruta)).paragraphs:
        texto = parrafo.text.strip()
        m = _ENCABEZADO.match(texto)
        if m:
            actual = {"titulo": m.group(2), "modulo": "", "entorno": "", "selector": None,
                      "paso2": None, "esperado": ""}
            casos[m.group(1)] = actual
            continue
        if actual is None:
            continue
        if texto.startswith("Módulo  "):
            actual["modulo"] = texto.removeprefix("Módulo  ").split("·")[0].strip()
        elif texto.startswith("Entorno  "):
            actual["entorno"] = texto.removeprefix("Entorno  ").strip()
        elif texto.startswith("Resultado esperado  "):
            actual["esperado"] = texto.removeprefix("Resultado esperado  ").strip()
        elif texto.startswith("2. ") and actual["paso2"] is None:
            actual["paso2"] = texto
            s = _SELECTOR.search(texto)
            actual["selector"] = s.group(1) if s else None
    return casos


def carpeta_ciclo(base: Path, ciclo: int, ahora: datetime) -> Path:
    """Reutiliza la carpeta del ciclo si existe; si no, la nombra ciclo_<NN>_<UTC>."""
    existentes = sorted(base.glob(f"ciclo_{ciclo:02d}_*")) if base.exists() else []
    if existentes:
        return existentes[0]
    return base / f"ciclo_{ciclo:02d}_{ahora.strftime('%Y%m%dT%H%M%SZ')}"


_TEXTO: Final[tuple[str, ...]] = (".json", ".md", ".xml", ".log")


def normalizar_lf(ruta: Path) -> None:
    """Deja en LF los saltos de línea de un archivo de texto de evidencia (los binarios no se tocan).

    En Windows, pytest y Python escriben CRLF; git los guarda como LF y otros sistemas los leen así.
    Con LF en todas partes el SHA256 registrado coincide en cualquier clon.
    """
    if ruta.suffix.lower() in _TEXTO:
        datos = ruta.read_bytes()
        if b"\r\n" in datos:
            ruta.write_bytes(datos.replace(b"\r\n", b"\n"))


def ocultar_rutas_locales(ruta: Path) -> None:
    """Quita de un archivo de texto de evidencia las rutas absolutas del equipo y el usuario del sistema.

    pytest copia al JUnit lo que los tests imprimen (p. ej. rutas temporales con el nombre de usuario);
    los informes del repositorio solo pueden llevar rutas relativas al proyecto.
    """
    if ruta.suffix.lower() not in _TEXTO:
        return
    original = ruta.read_text(encoding="utf-8", errors="surrogateescape")
    texto = original
    for base, marca in ((RAIZ, "<repo>"), (Path.home(), "<home>")):
        for variante in {str(base), base.as_posix()}:
            texto = texto.replace(variante, marca)
    # El directorio temporal de pytest lleva el nombre del usuario (que puede tener espacios).
    texto = re.sub(r"pytest-of-[^/\\]+", "pytest-of-<usuario>", texto)
    texto = re.sub(r"<home>[/\\]AppData[/\\]Local[/\\]Temp", "<tmp>", texto)
    if texto != original:
        ruta.write_text(texto, encoding="utf-8", errors="surrogateescape", newline="\n")


def preparar_evidencia(ruta: Path) -> None:
    """Deja un archivo de evidencia listo para hashearse y versionarse: LF y sin rutas locales."""
    normalizar_lf(ruta)
    ocultar_rutas_locales(ruta)


def sha256(ruta: Path) -> str:
    """SHA256 del archivo, tras prepararlo (LF y sin rutas locales) para que no dependa del equipo."""
    preparar_evidencia(ruta)
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def correr_pytest(selector: str, xml: Path) -> tuple[int, str]:
    """Ejecuta el selector del caso y deja su JUnit (con la salida estándar dentro)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *selector.split(), "-q", "-p", "no:cacheprovider",
         "-o", "junit_logging=system-out", f"--junitxml={xml}"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode, (r.stdout + r.stderr).replace(str(RAIZ), "<repo>").replace(str(Path.home()), "<home>")


def leer_junit(xml: Path) -> tuple[int, int, int, list[str]]:
    """Instancias, fallidas (fallos y errores), omitidas y nodeids de un JUnit."""
    raiz = ET.parse(xml).getroot()
    suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
    if suite is None:
        raise ValueError(f"JUnit sin testsuite: {xml.name}")
    nodeids = sorted({f"{t.get('classname')}::{t.get('name')}" for t in raiz.iter("testcase")})
    return (int(suite.get("tests", 0)), int(suite.get("failures", 0)) + int(suite.get("errors", 0)),
            int(suite.get("skipped", 0)), nodeids)


def _relativo(ruta: Path) -> str:
    """Ruta relativa al repositorio (o tal cual si queda fuera, p. ej. en pruebas)."""
    try:
        return ruta.relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.as_posix()


def iso(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


def ejecutar_caso(cid: str, info: dict[str, str | None], contexto: dict[str, Any], evidencia: Path,
                  fecha: str) -> dict[str, Any]:
    """Ejecuta un caso y devuelve su registro con los campos exigidos por el plan."""
    registro: dict[str, Any] = {
        "id": f"SAAD-CP-{cid}", "run_id": contexto["run_id"], "titulo": info["titulo"],
        "modulo": info["modulo"], "ejecutor_real": contexto["ejecutor"], "entorno": ENTORNO_FIXTURE,
        "sha": contexto["sha"], "snapshot": SNAPSHOT_FIXTURE, "defecto": "Sin defecto registrado",
    }
    selector = info["selector"]
    if not selector:
        registro.update(
            estado=NO_EJECUTADO, fecha_hora_utc=None, resultado_real="No ejecutado", evidencia=None,
            evidencia_sha256=None, hash_input=None,
            observaciones="Sin selector de pytest en el catálogo: requiere interfaz, API con datos reales o AWS.",
        )
        return registro
    nombre = f"{registro['id']}_{fecha}_fixture.xml"
    xml = evidencia / nombre
    inicio = datetime.now(timezone.utc)
    codigo, salida = correr_pytest(selector, xml)
    fin = datetime.now(timezone.utc)
    instancias, fallidas, omitidas, nodeids = leer_junit(xml)
    aprobado = codigo == 0 and instancias >= 1 and fallidas == 0 and omitidas == 0
    archivo = selector.split("::")[0]
    observaciones = "—"
    if "StarletteDeprecationWarning" in salida:
        observaciones = ("pytest informa una advertencia de deprecación de Starlette/httpx (TestClient); "
                         "no afecta el resultado.")
    registro.update(
        estado=APROBADO if aprobado else FALLIDO,
        fecha_hora_utc={"inicio": iso(inicio), "fin": iso(fin)},
        resultado_real=f"{instancias} instancias, {fallidas} fallidas, {omitidas} omitidas; exit code {codigo}",
        comando=f"python -m pytest {selector} -q --junitxml=EVIDENCIA/{nombre}",
        nodeids=nodeids, evidencia=f"EVIDENCIA/{nombre}", evidencia_sha256=sha256(xml),
        hash_input={"archivo": archivo, "git_blob": git("rev-parse", f"HEAD:{archivo}") or None},
        observaciones=observaciones,
    )
    if not aprobado:
        registro["salida_cola"] = salida[-1500:]
    return registro


def peticiones_http(paso2: str | None, esperado: str) -> list[dict[str, Any]]:
    """Peticiones del caso: ruta (sin /api/v1) y código HTTP esperado; vacío si el caso no es HTTP simple."""
    if not paso2:
        return []
    rango = _RANGO.search(paso2)
    if rango:
        inicio = date.fromisoformat(rango.group(1))
        dentro, fuera = int(rango.group(2)), int(rango.group(3))
        return [
            {"ruta": f"/calendario-eventos?desde={inicio}&hasta={inicio + timedelta(days=dentro)}", "esperado": 200},
            {"ruta": f"/calendario-eventos?desde={inicio}&hasta={inicio + timedelta(days=fuera)}", "esperado": 422},
        ]
    get, codigo = _GET.search(paso2), _HTTP.search(esperado)
    par = _Y_LUEGO.search(paso2)
    if par and codigo:
        # «GET /x?p=A y luego p=B»: A es el valor válido (200) y B el que el contrato rechaza.
        base = par.group(1)
        return [{"ruta": f"{base}{par.group(2)}", "esperado": 200},
                {"ruta": f"{base}{par.group(3)}", "esperado": int(codigo.group(1))}]
    if get and codigo:
        # El catálogo cierra cada paso con un punto de oración; no forma parte de la URL.
        return [{"ruta": get.group(1).rstrip("."), "esperado": int(codigo.group(1))}]
    return []


def consultar(url_base: str, ruta: str, timeout: int = 60) -> dict[str, Any]:
    """GET de solo lectura; devuelve código, cabeceras relevantes, cuerpo acotado y duración."""
    destino = url_base.rstrip("/") + (ruta if ruta.startswith("/api/") else "/api/v1" + ruta)
    inicio = datetime.now(timezone.utc)
    pedido = urllib.request.Request(destino, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:  # noqa: S310 - GET a la URL indicada
            codigo, cabeceras, cuerpo = r.status, r.headers, r.read()
    except urllib.error.HTTPError as error:
        codigo, cabeceras, cuerpo = error.code, error.headers, error.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"url": destino, "codigo": None, "error": str(error), "cuerpo": "", "cabeceras": {},
                "inicio": iso(inicio), "fin": iso(datetime.now(timezone.utc))}
    texto = cuerpo.decode("utf-8", errors="replace")
    return {
        "url": destino, "codigo": codigo,
        "cabeceras": {k: v for k, v in cabeceras.items() if k.lower() in ("content-type", "retry-after")},
        "cuerpo": texto[:1500], "cuerpo_truncado": len(texto) > 1500,
        "inicio": iso(inicio), "fin": iso(datetime.now(timezone.utc)),
    }


def entorno_http(url_base: str) -> tuple[str, str]:
    """(descripción del entorno, sufijo del nombre de evidencia) según el host."""
    host = urlparse(url_base).hostname or ""
    return (ENTORNO_LOCAL, "local") if host in ("127.0.0.1", "localhost", "::1") else (ENTORNO_AWS, "aws")


def snapshot_http(url_base: str) -> tuple[str, dict[str, Any]]:
    """Versión/snapshot observados en /meta (paso 1 del procedimiento) y la respuesta usada."""
    r = consultar(url_base, "/meta")
    if r["codigo"] != 200:
        return SNAPSHOT_HTTP_NO_DISPONIBLE, r
    try:
        meta = json.loads(r["cuerpo"] if not r.get("cuerpo_truncado") else "{}")
    except ValueError:
        return SNAPSHOT_HTTP_NO_DISPONIBLE, r
    semana = meta.get("ultima_semana_observada") or {}
    return (f"/meta: última semana observada {semana.get('fecha_inicio', '?')}; pronóstico calculado "
            f"{meta.get('pronostico_calculado_en', '?')} ({meta.get('origen_pronostico', '?')})"), r


def ejecutar_caso_http(cid: str, info: dict[str, str | None], contexto: dict[str, Any], evidencia: Path,
                       fecha: str) -> dict[str, Any]:
    """Ejecuta las peticiones del caso contra la API y compara cada código con el esperado."""
    registro: dict[str, Any] = {
        "id": f"SAAD-CP-{cid}", "run_id": contexto["run_id"], "titulo": info["titulo"],
        "modulo": info["modulo"], "ejecutor_real": contexto["ejecutor"], "entorno": contexto["entorno"],
        "sha": contexto["sha"], "snapshot": contexto["snapshot"], "defecto": "Sin defecto registrado",
    }
    peticiones = peticiones_http(info.get("paso2"), info.get("esperado") or "")
    if not peticiones:
        registro.update(
            estado=NO_EJECUTADO, fecha_hora_utc=None, resultado_real="No ejecutado", evidencia=None,
            evidencia_sha256=None, hash_input=None,
            observaciones="El procedimiento no es una consulta HTTP automatizable en este modo.",
        )
        return registro
    inicio = datetime.now(timezone.utc)
    respuestas = [consultar(contexto["url_base"], p["ruta"]) for p in peticiones]
    fin = datetime.now(timezone.utc)
    resultados = [r["codigo"] == p["esperado"] for p, r in zip(peticiones, respuestas)]
    nombre = f"{registro['id']}_{fecha}_{contexto['sufijo']}.json"
    cuerpo_evidencia = json.dumps(
        {"caso": registro["id"], "entorno": contexto["entorno"], "snapshot": contexto["snapshot"],
         "estado_inicial": contexto["estado_inicial"], "esperado": info.get("esperado"),
         "peticiones": [{**p, "respuesta": r} for p, r in zip(peticiones, respuestas)]},
        ensure_ascii=False, indent=1)
    if contexto["sufijo"] == "aws":   # el plan pide consultas AWS redactadas
        cuerpo_evidencia = cuerpo_evidencia.replace(contexto["url_base"].rstrip("/"), "<url-base>")
    ruta = evidencia / nombre
    ruta.write_text(cuerpo_evidencia + "\n", encoding="utf-8", newline="\n")
    resumen = "; ".join(
        f"GET {p['ruta']} → HTTP {r['codigo'] if r['codigo'] is not None else 'sin respuesta'} "
        f"(esperado {p['esperado']})" for p, r in zip(peticiones, respuestas))
    registro.update(
        estado=APROBADO if all(resultados) else FALLIDO,
        fecha_hora_utc={"inicio": iso(inicio), "fin": iso(fin)},
        resultado_real=resumen,
        peticiones=[{"ruta": p["ruta"], "esperado": p["esperado"], "obtenido": r["codigo"]}
                    for p, r in zip(peticiones, respuestas)],
        evidencia=f"EVIDENCIA/{nombre}", evidencia_sha256=sha256(ruta),
        hash_input={"peticiones_sha256": hashlib.sha256(
            json.dumps([p["ruta"] for p in peticiones]).encode("utf-8")).hexdigest()},
        observaciones=contexto["nota"] or "—",
    )
    return registro


VERSION_AWS_NO_CONFIRMADA: Final[str] = (
    "No confirmada: /meta no expone el SHA ni el digest de la imagen desplegada "
    "(la última corrida AWS registrada en el ciclo 4 usó la imagen 95d00f8)."
)
ESTADOS_VALIDOS: Final[tuple[str, ...]] = (APROBADO, FALLIDO, NO_EJECUTADO)


def registrar_manual(cid: str, info: dict[str, str | None], entrada: dict[str, Any], contexto: dict[str, Any],
                     evidencia: Path, anexos_dir: Path) -> dict[str, Any]:
    """Registra un caso manual asistido: toma el veredicto y los anexos ya producidos y los copia con sus hashes."""
    if entrada.get("estado") not in ESTADOS_VALIDOS:
        raise ValueError(f"SAAD-CP-{cid}: estado inválido {entrada.get('estado')!r}")
    registro: dict[str, Any] = {
        "id": f"SAAD-CP-{cid}", "run_id": contexto["run_id"], "titulo": info["titulo"],
        "modulo": info["modulo"], "ejecutor_real": contexto["ejecutor"], "entorno": contexto["entorno"],
        "sha": contexto["sha"], "snapshot": entrada.get("snapshot") or "No registrado",
        "defecto": entrada.get("defecto") or "Sin defecto registrado", "estado": entrada["estado"],
        "resultado_real": entrada.get("resultado_real") or "No ejecutado",
        "observaciones": entrada.get("observaciones") or "—",
    }
    if isinstance(registro["snapshot"], dict):
        registro["snapshot"] = json.dumps(registro["snapshot"], ensure_ascii=False, separators=(",", ":"))
    if contexto.get("version_desplegada"):
        registro["version_desplegada"] = contexto["version_desplegada"]
    nombres = list(entrada.get("anexos") or [])
    if not nombres:
        registro.update(fecha_hora_utc=None, evidencia=None, evidencia_sha256=None, hash_input=None, anexos=[])
        return registro
    copiados = []
    for nombre in nombres:
        origen = anexos_dir / nombre
        if not origen.is_file():
            raise FileNotFoundError(f"Falta el anexo {nombre} de SAAD-CP-{cid}")
        shutil.copy2(origen, evidencia / origen.name)
        copiados.append({"archivo": f"EVIDENCIA/{origen.name}", "sha256": sha256(evidencia / origen.name)})
    registro.update(
        fecha_hora_utc={"inicio": entrada.get("inicio"), "fin": entrada.get("fin")},
        evidencia=copiados[0]["archivo"], evidencia_sha256=copiados[0]["sha256"], anexos=copiados,
        hash_input=entrada.get("hash_input"),
    )
    return registro


def resumir(casos: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "aprobados": sum(c["estado"] == APROBADO for c in casos),
        "fallidos": sum(c["estado"] == FALLIDO for c in casos),
        "no_ejecutados": sum(c["estado"] == NO_EJECUTADO for c in casos),
    }


def escribir_resultados(destino: Path, meta: dict[str, Any]) -> None:
    (destino / "resultados.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    r = meta["resumen"]
    limpio = "sí" if meta["arbol_versionado_limpio"] else "no"
    sin_rastrear = ", ".join(f"`{x}`" for x in meta["archivos_sin_rastrear"]) or "ninguno"
    lineas = [
        f"# Ciclo {meta['ciclo']} · Catálogo SAAD-CP v2.1 (200 casos): {meta['ejecutor_real']}", "",
        f"- **Ejecutor real:** {meta['ejecutor_real']} · **Alcance:** {meta['alcance']} · **Estado:** FORMAL",
        f"- **Commit:** `{meta['commit']}` · árbol versionado limpio: {limpio}",
        f"- **Archivos sin rastrear al ejecutar:** {sin_rastrear}",
        *([f"- **Versión desplegada:** {meta['version_desplegada']}"] if meta.get("version_desplegada") else []),
        *([f"- **Nota:** {meta['nota']}"] if meta.get("nota") else []),
        f"- **Entorno:** {meta['entorno']} · Python {meta['python']} · pytest {meta['librerias']['pytest']}",
        f"- **Inicio / fin (UTC):** {meta['inicio_utc']} / {meta['fin_utc']}",
        f"- **Resultado:** {r['aprobados']} aprobados · {r['fallidos']} fallidos · {r['no_ejecutados']} no ejecutados",
        "",
        "Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), "
        "con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en "
        "`../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.", "",
        "| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in meta["casos"]:
        fecha = c["fecha_hora_utc"]["inicio"] if c["fecha_hora_utc"] else "—"
        evidencia = f"[`{c['evidencia']}`]({c['evidencia']})" if c["evidencia"] else "—"
        if len(c.get("anexos") or []) > 1:
            evidencia += f" (+{len(c['anexos']) - 1} anexos en `EVIDENCIA/`)"
        lineas.append(f"| {c['id']} | {c['titulo']} | {fecha} | {c['estado']} | {c['resultado_real']} | "
                      f"{evidencia} | {c['defecto']} | {c['observaciones']} |")
    lineas += ["", "## Límites", ""] + [f"- {a}" for a in meta["advertencias"]]
    (destino / "resultados.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta casos del catálogo SAAD-CP v2.1 con evidencia.")
    parser.add_argument("--ciclo", type=int, required=True, help="Número del ciclo (se reutiliza si existe)")
    parser.add_argument("--ejecutor", required=True, help="Nombre de quien ejecuta, tal como figurará")
    parser.add_argument("--casos", required=True, help="Casos a ejecutar, p. ej. 081-096,108-110,135")
    parser.add_argument("--catalogo", type=Path, default=CATALOGO, help="Catálogo .docx")
    parser.add_argument("--salida", type=Path, default=SALIDA_BASE, help="Carpeta base de los ciclos")
    parser.add_argument("--modo", choices=("pytest", "http", "manual"), default="pytest",
                        help="pytest: casos con selector; http: consultas GET contra una API; "
                             "manual: registra veredictos y anexos de casos hechos con navegador u otra persona")
    parser.add_argument("--url-base", help="Base de la API en modo http, p. ej. http://127.0.0.1:8000")
    parser.add_argument("--nota", default="", help="Condición del entorno que debe quedar registrada")
    parser.add_argument("--entradas", type=Path, help="JSON con los veredictos de los casos (modo manual)")
    parser.add_argument("--entorno", choices=("local", "aws"), help="Entorno donde se ejecutó (modo manual)")
    parser.add_argument("--subcarpeta", default=SUBCARPETA,
                        help="Carpeta de la corrida dentro del ciclo; permite varias corridas (p. ej. catalogo_200_aws)")
    args = parser.parse_args(argv)
    if not args.subcarpeta.startswith(SUBCARPETA) or "/" in args.subcarpeta or "\\" in args.subcarpeta:
        parser.error(f"--subcarpeta debe empezar con {SUBCARPETA} y no llevar separadores")
    if args.modo == "http" and not args.url_base:
        parser.error("--modo http requiere --url-base")
    if args.modo == "manual" and not (args.entradas and args.entorno):
        parser.error("--modo manual requiere --entradas y --entorno")

    ids = parsear_casos(args.casos)
    catalogo = leer_catalogo(args.catalogo)
    faltan = [i for i in ids if i not in catalogo]
    if faltan:
        parser.error(f"Casos que no están en el catálogo: {', '.join(faltan)}")

    ahora = datetime.now(timezone.utc)
    ciclo = carpeta_ciclo(args.salida, args.ciclo, ahora)
    destino = ciclo / args.subcarpeta
    if destino.exists():
        parser.error(f"Ya existe {destino.name} en {ciclo.name}: repetir exige otro ciclo; no se sobrescribe.")
    evidencia = destino / "EVIDENCIA"
    ciclo_existia = ciclo.exists()
    evidencia.mkdir(parents=True)
    try:

        sha = git("rev-parse", "HEAD")
        modificados = [x for x in git("status", "--short", "--untracked-files=no").split("\n") if x]
        sin_rastrear = [x[3:] for x in git("status", "--short").split("\n") if x.startswith("??")]
        propio = _relativo(ciclo)
        sin_rastrear = [x for x in sin_rastrear if not x.startswith(propio)]
        contexto: dict[str, Any] = {"run_id": f"{ciclo.name}/{args.subcarpeta}", "ejecutor": args.ejecutor, "sha": sha}
        fecha = ahora.strftime("%Y%m%d")
        entorno = ENTORNO_FIXTURE
        if args.modo == "http":
            entorno, sufijo = entorno_http(args.url_base)
            snapshot, meta_api = snapshot_http(args.url_base)
            contexto.update(url_base=args.url_base, sufijo=sufijo, entorno=entorno, snapshot=snapshot,
                            version_desplegada=VERSION_AWS_NO_CONFIRMADA if sufijo == "aws" else None,
                            nota=args.nota, estado_inicial={"hora_utc": iso(datetime.now(timezone.utc)),
                                                            "meta": {k: v for k, v in meta_api.items() if k != "url"}})
            casos = [ejecutar_caso_http(i, catalogo[i], contexto, evidencia, fecha) for i in ids]
        elif args.modo == "manual":
            entradas = {e["id"].removeprefix("SAAD-CP-"): e for e in json.loads(args.entradas.read_text(encoding="utf-8"))}
            faltan_entradas = [i for i in ids if i not in entradas]
            if faltan_entradas:
                parser.error(f"Sin veredicto en --entradas para: {', '.join(faltan_entradas)}")
            entorno = ENTORNO_AWS if args.entorno == "aws" else ENTORNO_LOCAL
            contexto.update(entorno=entorno, nota=args.nota,
                            version_desplegada=VERSION_AWS_NO_CONFIRMADA if args.entorno == "aws" else None)
            casos = [registrar_manual(i, catalogo[i], entradas[i], contexto, evidencia, args.entradas.parent) for i in ids]
        else:
            casos = [ejecutar_caso(i, catalogo[i], contexto, evidencia, fecha) for i in ids]
        inicio_corrida, fin_corrida = iso(ahora), iso(datetime.now(timezone.utc))
        if args.modo == "manual":
            # Casos hechos antes de registrarlos: el periodo es el de sus propias ejecuciones, no el del registro.
            tiempos = [t for c in casos for t in (c.get("fecha_hora_utc") or {}).values() if t]
            if tiempos:
                inicio_corrida, fin_corrida = min(tiempos), max(tiempos)
        librerias = {}
        for paquete in LIBRERIAS:
            try:
                librerias[paquete] = metadata.version(paquete)
            except metadata.PackageNotFoundError:
                librerias[paquete] = "no instalado"
        meta = {
            "run_id": contexto["run_id"], "ciclo": args.ciclo,
            "catalogo": f"{args.catalogo.name} (v2.1)", "ejecutor_real": args.ejecutor,
            "alcance": f"{len(ids)} casos", "estado_corrida": "FORMAL",
            "inicio_utc": inicio_corrida, "fin_utc": fin_corrida, "commit": sha,
            "arbol_versionado_limpio": not modificados, "archivos_versionados_modificados": len(modificados),
            "archivos_sin_rastrear": sin_rastrear, "entorno": entorno, "modo": args.modo, "nota": args.nota,
            "version_desplegada": contexto.get("version_desplegada"),
            "python": platform.python_version(), "so": f"{platform.system()} {platform.release()}",
            "librerias": librerias, "resumen": resumir(casos),
            "advertencias": [
                ("Los tests unitarios verifican el código con fixtures; no acreditan los datos reales del snapshot vigente."
                 if args.modo == "pytest" else
                 "Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan "
                 "otros entornos ni otros datos."),
                "Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.",
                "Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.",
            ],
            "casos": casos,
        }
        escribir_resultados(destino, meta)
    except BaseException:
        # Un fallo no deja una carpeta a medias que bloquee el reintento.
        shutil.rmtree(destino, ignore_errors=True)
        if not ciclo_existia:
            try:
                ciclo.rmdir()
            except OSError:
                pass
        raise
    r = meta["resumen"]
    print(f"{ciclo.name}/{args.subcarpeta}: {r['aprobados']} aprobados, {r['fallidos']} fallidos, "
          f"{r['no_ejecutados']} no ejecutados")
    return 1 if r["fallidos"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
