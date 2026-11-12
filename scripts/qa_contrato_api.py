"""Contrato de datos API/frontend (#61): exporta el OpenAPI y lo compara con los tipos del frontend.

1. Exporta el OpenAPI que genera FastAPI desde los esquemas Pydantic a
   `docs/06-requisitos/contrato_api/openapi.json` (contrato versionado de la API).
2. Lee las interfaces de `frontend/src/api.ts` y el objeto `api`, que asocia cada ruta con el
   tipo que el frontend espera.
3. Compara cada respuesta campo por campo: campos que el frontend espera y la API no envía,
   campos nulos que el frontend trata como no nulos, tipos y valores de enumeraciones distintos.
4. Inventaría los errores que lanza cada ruta, leyendo el código de `src/api/` (el OpenAPI solo
   declara 200 y 422), y cómo los maneja el cliente del frontend.

Deja el informe en `reports/validation/contrato_api/comparacion_api_frontend.md` y el detalle
en `comparacion_api_frontend.json`. No modifica la API ni el frontend.

Uso:
    .venv/bin/python scripts/qa_contrato_api.py
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

API_TS: Final[Path] = RAIZ / "frontend/src/api.ts"
API_PY: Final[Path] = RAIZ / "src/api"
SALIDA_CONTRATO: Final[Path] = RAIZ / "docs/06-requisitos/contrato_api/openapi.json"
SALIDA_INFORME: Final[Path] = RAIZ / "reports/validation/contrato_api"
PREFIJO: Final[str] = "/api/v1"

ERROR, ADVERTENCIA, INFO = "ERROR", "ADVERTENCIA", "INFO"


@dataclass
class Hallazgo:
    severidad: str
    ruta: str
    campo: str
    detalle: str


# --------------------------------------------------------------------- tipos TypeScript

def _dividir_nivel_superior(texto: str, separadores: str) -> list[str]:
    """Divide por separadores que no estén dentro de {}, <>, () o []."""
    partes, actual, nivel = [], [], 0
    for c in texto:
        if c in "{<([":
            nivel += 1
        elif c in "}>)]":
            nivel -= 1
        if c in separadores and nivel == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(c)
    partes.append("".join(actual))
    return [p.strip() for p in partes if p.strip()]


def _cuerpo_entre_llaves(texto: str, inicio: int) -> tuple[str, int]:
    """Contenido de la llave que abre en `inicio` y posición siguiente a su cierre."""
    nivel = 0
    for i in range(inicio, len(texto)):
        if texto[i] == "{":
            nivel += 1
        elif texto[i] == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio + 1:i], i + 1
    raise ValueError("Llaves sin cerrar en api.ts")


def _campos(cuerpo: str) -> dict[str, tuple[str, bool]]:
    """Campos de un objeto TS: nombre → (expresión de tipo, opcional)."""
    sin_comentarios = re.sub(r"//[^\n]*", "", cuerpo)
    campos = {}
    for declaracion in _dividir_nivel_superior(sin_comentarios, ";\n"):
        m = re.match(r"(\w+)(\?)?\s*:\s*(.+)$", declaracion, re.S)
        if m:
            campos[m.group(1)] = (" ".join(m.group(3).split()), bool(m.group(2)))
    return campos


def leer_tipos_ts(texto: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Interfaces (con sus campos, incluida la herencia) y alias de tipos exportados."""
    interfaces: dict[str, Any] = {}
    for m in re.finditer(r"export interface (\w+)(?:\s+extends\s+(\w+))?\s*\{", texto):
        cuerpo, _ = _cuerpo_entre_llaves(texto, m.end() - 1)
        interfaces[m.group(1)] = {"base": m.group(2), "campos": _campos(cuerpo)}
    for nombre, interfaz in interfaces.items():
        base = interfaz["base"]
        if base and base in interfaces:
            interfaz["campos"] = {**interfaces[base]["campos"], **interfaz["campos"]}
    alias = {m.group(1): " ".join(m.group(2).split())
             for m in re.finditer(r"export type (\w+)\s*=\s*([^;]+);", texto)}
    return interfaces, alias


def leer_rutas_ts(texto: str) -> list[dict[str, Any]]:
    """Llamadas del objeto `api`: método, ruta normalizada, tipo esperado y parámetros de consulta."""
    rutas = []
    for m in re.finditer(r"(\w+):\s*\([^)]*\)\s*=>\s*obtener<([^>]+(?:<[^>]*>)?[^>]*)>\(\s*[`\"]([^`\"]+)[`\"]", texto):
        metodo, tipo, plantilla = m.group(1), m.group(2).strip(), m.group(3)
        ruta, _, consulta = plantilla.partition("?")
        ruta = re.sub(r"\$\{[^}]+\}", "{}", ruta)
        parametros = sorted(re.findall(r"(\w+)=", consulta))
        rutas.append({"metodo": metodo, "ruta": PREFIJO + ruta, "tipo": tipo, "consulta": parametros})
    return rutas


def normalizar_ts(expresion: str, interfaces: dict[str, Any], alias: dict[str, str]) -> dict[str, Any]:
    """Estructura comparable de una expresión de tipo TS."""
    expresion = expresion.strip()
    variantes = _dividir_nivel_superior(expresion, "|")
    nulo = "null" in variantes
    variantes = [v for v in variantes if v != "null"]
    if len(variantes) > 1 or (variantes and variantes[0].startswith('"')):
        if all(v.startswith('"') for v in variantes):
            return {"tipo": "string", "enum": sorted(v.strip('"') for v in variantes), "nulo": nulo}
        return {"tipo": "union", "nulo": nulo, "texto": expresion}
    v = variantes[0]
    if v.startswith("(") and v.endswith(")"):
        return {**normalizar_ts(v[1:-1], interfaces, alias), **({"nulo": True} if nulo else {})}
    if v.endswith("[]"):
        return {"tipo": "array", "items": normalizar_ts(v[:-2], interfaces, alias), "nulo": nulo}
    if v.startswith("{"):
        cuerpo, _ = _cuerpo_entre_llaves(v, 0)
        return {"tipo": "object", "campos": {k: (normalizar_ts(t, interfaces, alias), o)
                                             for k, (t, o) in _campos(cuerpo).items()}, "nulo": nulo}
    if v in ("number", "string", "boolean"):
        return {"tipo": v, "nulo": nulo}
    if v in alias:
        return {**normalizar_ts(alias[v], interfaces, alias), **({"nulo": True} if nulo else {})}
    if v in interfaces:
        return {"tipo": "object", "nombre": v, "nulo": nulo,
                "campos": {k: (normalizar_ts(t, interfaces, alias), o)
                           for k, (t, o) in interfaces[v]["campos"].items()}}
    if v.startswith(("Partial<Record", "Record<")):
        return {"tipo": "map", "nulo": nulo}
    return {"tipo": "externo", "texto": v, "nulo": nulo}


# ------------------------------------------------------------------------- OpenAPI

def generar_openapi() -> dict[str, Any]:
    from src.api.main import create_app
    return create_app(iniciar_calculos=False).openapi()


def normalizar_openapi(esquema: dict[str, Any], componentes: dict[str, Any]) -> dict[str, Any]:
    """Estructura comparable de un esquema OpenAPI (resuelve $ref, anyOf con null y enums)."""
    if "$ref" in esquema:
        nombre = esquema["$ref"].rsplit("/", 1)[-1]
        return {**normalizar_openapi(componentes[nombre], componentes), "nombre": nombre.removesuffix("-Output")}
    variantes = esquema.get("anyOf") or esquema.get("oneOf")
    if variantes:
        nulo = any(x.get("type") == "null" for x in variantes)
        resto = [x for x in variantes if x.get("type") != "null"]
        if len(resto) == 1:
            return {**normalizar_openapi(resto[0], componentes), "nulo": nulo}
        return {"tipo": "union", "nulo": nulo}
    tipo = esquema.get("type")
    if "enum" in esquema or "const" in esquema:
        valores = esquema.get("enum", [esquema.get("const")])
        return {"tipo": "string" if all(isinstance(x, str) for x in valores) else tipo,
                "enum": sorted(map(str, valores)), "nulo": False}
    if tipo in ("integer", "number"):
        return {"tipo": "number", "nulo": False}
    if tipo == "array":
        return {"tipo": "array", "items": normalizar_openapi(esquema.get("items", {}), componentes), "nulo": False}
    if tipo == "object" or "properties" in esquema:
        if "properties" not in esquema:
            return {"tipo": "map", "nulo": False}
        requeridos = set(esquema.get("required", []))
        return {"tipo": "object", "nulo": False, "campos": {
            k: (normalizar_openapi(v, componentes), k not in requeridos) for k, v in esquema["properties"].items()}}
    if tipo in ("string", "boolean"):
        return {"tipo": tipo, "nulo": False}
    return {"tipo": "cualquiera", "nulo": False}


# ----------------------------------------------------------------------- comparación

def comparar(api: dict[str, Any], ts: dict[str, Any], ruta: str, campo: str = "") -> list[Hallazgo]:
    """Hallazgos de comparar lo que envía la API (`api`) con lo que espera el frontend (`ts`)."""
    h: list[Hallazgo] = []
    nombre = campo or "(respuesta)"
    if ts["tipo"] == "externo" or api["tipo"] in ("cualquiera", "union") or ts["tipo"] == "union":
        return h
    if api.get("nulo") and not ts.get("nulo"):
        h.append(Hallazgo(ERROR, ruta, nombre, "La API puede enviar null y el frontend no lo admite."))
    elif ts.get("nulo") and not api.get("nulo"):
        h.append(Hallazgo(INFO, ruta, nombre, "El frontend admite null aunque la API nunca lo envía (defensivo)."))
    if api["tipo"] != ts["tipo"]:
        if not (api["tipo"] == "map" and ts["tipo"] == "object"):
            h.append(Hallazgo(ERROR, ruta, nombre, f"Tipo distinto: API {api['tipo']}, frontend {ts['tipo']}."))
        return h
    if "enum" in api and "enum" in ts and api["enum"] != ts["enum"]:
        solo_api = sorted(set(api["enum"]) - set(ts["enum"]))
        solo_ts = sorted(set(ts["enum"]) - set(api["enum"]))
        h.append(Hallazgo(ERROR if solo_api else INFO, ruta, nombre,
                          f"Valores distintos: solo en API {solo_api or '—'}, solo en frontend {solo_ts or '—'}."))
    if api["tipo"] == "array":
        h += comparar(api["items"], ts["items"], ruta, f"{campo}[]")
    if api["tipo"] == "object":
        campos_api, campos_ts = api["campos"], ts["campos"]
        for k in sorted(set(campos_ts) - set(campos_api)):
            h.append(Hallazgo(ERROR, ruta, f"{campo}.{k}".lstrip("."), "El frontend espera el campo y la API no lo envía."))
        for k in sorted(set(campos_api) - set(campos_ts)):
            h.append(Hallazgo(INFO, ruta, f"{campo}.{k}".lstrip("."), "La API lo envía y el frontend no lo tipa (lo ignora)."))
        # La API serializa todos los campos del modelo, también los que tienen valor por defecto
        # (no usa exclude_none/exclude_unset), así que "opcional" en el esquema no significa ausente.
        for k in sorted(set(campos_api) & set(campos_ts)):
            h += comparar(campos_api[k][0], campos_ts[k][0], ruta, f"{campo}.{k}".lstrip("."))
    return h


def patron_ruta(ruta: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", ruta)


# ------------------------------------------------------------------ errores por ruta

def _codigos(nodo: ast.AST) -> set[int]:
    """Códigos de HTTPException(...) dentro de un nodo."""
    codigos = set()
    for llamada in ast.walk(nodo):
        if isinstance(llamada, ast.Call) and getattr(llamada.func, "id", getattr(llamada.func, "attr", "")) == "HTTPException":
            argumentos = list(llamada.args) + [k.value for k in llamada.keywords if k.arg == "status_code"]
            codigos |= {a.value for a in argumentos if isinstance(a, ast.Constant) and isinstance(a.value, int)}
    return codigos


def _reintenta(nodo: ast.AST) -> bool:
    return any(isinstance(c, ast.Constant) and c.value == "Retry-After" for c in ast.walk(nodo))


def errores_por_ruta() -> dict[str, dict[str, Any]]:
    """Para cada GET: códigos de error que puede lanzar (incluye funciones auxiliares del módulo)."""
    resultado = {}
    for archivo in sorted(API_PY.glob("*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        prefijo = next((k.value.value for n in ast.walk(arbol) if isinstance(n, ast.Call)
                        and getattr(n.func, "id", "") == "APIRouter"
                        for k in n.keywords if k.arg == "prefix"), "")
        funciones = {f.name: f for f in arbol.body if isinstance(f, ast.FunctionDef)}

        def alcanzables(f: ast.FunctionDef, vistas: set[str]) -> list[ast.FunctionDef]:
            res = [f]
            for llamada in ast.walk(f):
                nombre = getattr(getattr(llamada, "func", None), "id", None)
                if isinstance(llamada, ast.Call) and nombre in funciones and nombre not in vistas:
                    vistas.add(nombre)
                    res += alcanzables(funciones[nombre], vistas)
            return res

        for f in funciones.values():
            for d in f.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "get" and d.args:
                    cuerpo = alcanzables(f, {f.name})
                    resultado[patron_ruta(prefijo + d.args[0].value)] = {
                        "codigos": sorted(set().union(*(_codigos(x) for x in cuerpo))),
                        "retry_after": any(_reintenta(x) for x in cuerpo),
                        "modulo": archivo.name,
                    }
    return resultado


def manejo_en_frontend() -> dict[str, str]:
    """Cómo trata cada componente los errores de cada llamada de `api`."""
    usos: dict[str, list[str]] = {}
    for archivo in sorted((RAIZ / "frontend/src").rglob("*.tsx")):
        texto = archivo.read_text(encoding="utf-8")
        for m in re.finditer(r"api\.(\w+)\([^;]*?\.catch\(([^;]*)", texto, re.S):
            silencioso = "undefined" in m.group(2)[:40]
            usos.setdefault(m.group(1), []).append(
                f"{archivo.name}: {'se ignora (la vista sigue sin ese dato)' if silencioso else 'muestra el mensaje de error'}")
    return {k: "; ".join(sorted(set(v))) for k, v in usos.items()}


# ---------------------------------------------------------------------------- informe

def main() -> int:
    fecha = datetime.now(timezone.utc)
    spec = generar_openapi()
    SALIDA_CONTRATO.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_CONTRATO.write_text(json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    texto_ts = API_TS.read_text(encoding="utf-8")
    interfaces, alias = leer_tipos_ts(texto_ts)
    rutas_ts = leer_rutas_ts(texto_ts)
    componentes = spec.get("components", {}).get("schemas", {})
    rutas_api = {patron_ruta(r): (r, op["get"]) for r, op in spec["paths"].items() if "get" in op}
    errores = errores_por_ruta()
    manejo = manejo_en_frontend()

    hallazgos: list[Hallazgo] = []
    filas = []
    usadas = set()
    for llamada in rutas_ts:
        clave = patron_ruta(llamada["ruta"])
        if clave not in rutas_api:
            hallazgos.append(Hallazgo(ERROR, llamada["ruta"], "(ruta)", "El frontend llama una ruta que la API no expone."))
            continue
        usadas.add(clave)
        ruta, op = rutas_api[clave]
        esquema = op["responses"]["200"]["content"].get("application/json", {}).get("schema", {})
        api_norm = normalizar_openapi(esquema, componentes)
        ts_norm = normalizar_ts(llamada["tipo"], interfaces, alias)
        hallazgos += comparar(api_norm, ts_norm, ruta)
        parametros = {p["name"]: p.get("required", False) for p in op.get("parameters", []) if p["in"] == "query"}
        for p in sorted(set(llamada["consulta"]) - set(parametros)):
            hallazgos.append(Hallazgo(ERROR, ruta, f"?{p}", "El frontend envía un parámetro que la API no declara."))
        for p in sorted(k for k, req in parametros.items() if req and k not in llamada["consulta"]):
            hallazgos.append(Hallazgo(ERROR, ruta, f"?{p}", "Parámetro obligatorio que el frontend no envía."))
        err = errores.get(clave, {"codigos": [], "retry_after": False})
        if api_norm["tipo"] == "array":
            esquema_api = f"{api_norm['items'].get('nombre', api_norm['items']['tipo'])}[]"
        elif api_norm["tipo"] == "cualquiera":
            esquema_api = "GeoJSON (sin esquema)"
        else:
            esquema_api = api_norm.get("nombre", api_norm["tipo"])
        filas.append({"metodo": llamada["metodo"], "ruta": ruta, "tipo_frontend": llamada["tipo"],
                      "esquema_api": esquema_api, "parametros": parametros,
                      "errores": sorted(set(err["codigos"]) | ({422} if parametros or "{" in ruta else set())),
                      "retry_after": err["retry_after"], "manejo": manejo.get(llamada["metodo"], "—")})
    for clave, (ruta, _) in sorted(rutas_api.items()):
        if clave not in usadas:
            hallazgos.append(Hallazgo(INFO, ruta, "(ruta)", "La API expone la ruta y el frontend no la usa."))
    declarados = {r: sorted(op["get"]["responses"]) for r, op in spec["paths"].items() if "get" in op}
    no_declarados = {f["ruta"]: sorted(set(map(str, f["errores"])) - set(declarados.get(f["ruta"], [])))
                     for f in filas}
    for ruta, codigos in no_declarados.items():
        if codigos:
            hallazgos.append(Hallazgo(ADVERTENCIA, ruta, "(errores)",
                                      f"Lanza {', '.join(codigos)} y el OpenAPI no lo declara (solo {', '.join(declarados[ruta])})."))

    conteo = {s: sum(x.severidad == s for x in hallazgos) for s in (ERROR, ADVERTENCIA, INFO)}
    commit = __import__("subprocess").run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                          text=True, cwd=RAIZ).stdout.strip()
    L = [
        "# Contrato de datos API / frontend: comparación (#61)",
        "",
        f"- **Fecha (UTC):** {fecha.isoformat(timespec='seconds')} · **Commit:** `{commit}`",
        f"- **Contrato de la API:** [`docs/06-requisitos/contrato_api/openapi.json`](../../../docs/06-requisitos/contrato_api/openapi.json)"
        f" (OpenAPI {spec.get('openapi')}, {len(rutas_api)} rutas, {len(componentes)} esquemas), generado desde `src/api/schemas.py`.",
        f"- **Tipos del frontend:** `frontend/src/api.ts` ({len(interfaces)} interfaces, {len(rutas_ts)} llamadas).",
        "- **Ejecutado con:** `scripts/qa_contrato_api.py`",
        "",
        f"**Resultado:** {conteo[ERROR]} errores · {conteo[ADVERTENCIA]} advertencias · {conteo[INFO]} observaciones.",
        "",
        "- **ERROR:** el frontend puede fallar o mostrar datos incorrectos (campo esperado que no llega, null no admitido, tipo distinto).",
        "- **ADVERTENCIA:** diferencia sin falla inmediata en la app, pero que deja el contrato incompleto (p. ej. errores no declarados en el OpenAPI).",
        "- **INFO:** diferencia inocua (campos que el frontend ignora, valores o nulos admitidos de forma defensiva, rutas sin uso).",
        "",
        "Criterio: la API serializa todos los campos de cada modelo, incluidos los que tienen valor por defecto "
        "(no usa `exclude_none` ni `exclude_unset`), así que un campo \"opcional\" en el esquema siempre llega, "
        "con su valor o `null`.",
        "",
        "## Endpoints, filtros y errores",
        "",
        "| Llamada del frontend | Ruta | Respuesta (API → frontend) | Filtros (obligatorio) | Errores posibles | Manejo en el frontend |",
        "|---|---|---|---|---|---|",
    ]
    for f in filas:
        filtros = ", ".join(f"`{k}`{' *' if req else ''}" for k, req in f["parametros"].items()) or "—"
        errores_txt = ", ".join(map(str, f["errores"])) or "—"
        if f["retry_after"]:
            errores_txt += " (503 con Retry-After: se reintenta)"
        L.append(f"| `api.{f['metodo']}` | `GET {f['ruta']}` | `{f['esquema_api']}` → `{f['tipo_frontend']}` | {filtros} | {errores_txt} | {f['manejo']} |")
    L += [
        "",
        "**Manejo común de errores del cliente** (`obtener` en `frontend/src/api.ts`):",
        "- Un 503 con `Retry-After` significa \"calculando\": el cliente espera y reintenta (hasta 30 veces).",
        "- Cualquier otro error se convierte en `ErrorApi` con el `detail` de la API. Cada vista decide si lo muestra o lo ignora (columna anterior).",
        "",
    ]
    for severidad, titulo in ((ERROR, "Errores"), (ADVERTENCIA, "Advertencias"), (INFO, "Observaciones")):
        grupo = [x for x in hallazgos if x.severidad == severidad]
        L += [f"## {titulo} ({len(grupo)})", ""]
        L += [f"- `{x.ruta}` · `{x.campo}`: {x.detalle}" for x in grupo] or ["- Ninguno."]
        L.append("")
    SALIDA_INFORME.mkdir(parents=True, exist_ok=True)
    (SALIDA_INFORME / "comparacion_api_frontend.md").write_text("\n".join(L), encoding="utf-8")
    (SALIDA_INFORME / "comparacion_api_frontend.json").write_text(json.dumps(
        {"fecha_utc": fecha.isoformat(timespec="seconds"), "commit": commit, "conteo": conteo,
         "endpoints": filas, "hallazgos": [asdict(x) for x in hallazgos]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{conteo} → {SALIDA_INFORME.relative_to(RAIZ)}/comparacion_api_frontend.md")
    return 1 if conteo[ERROR] else 0


if __name__ == "__main__":
    raise SystemExit(main())
