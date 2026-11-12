"""Prueba end-to-end de SAAD en AWS contrastada con la línea base local (C-44, CP-SAAD-070).

Ejecuta los mismos casos de API sobre dos entornos y verificaciones de infraestructura y
seguridad propias de AWS, y deja la evidencia en `reports/validation/e2e_local_aws/<UTC>/`:
`informe.md`, `resultados.json` y capturas de pantalla.

- LOCAL: Docker Compose (`http://localhost:8080` por defecto), mismo commit y mismos datos.
- AWS: CloudFront → ALB → ECS Fargate, con la URL tomada de `infra/aws/.env` (SAAD_URL).

La URL, el número de cuenta, los buckets, el DNS del ALB y el secreto se reemplazan por
marcadores en todo lo que se escribe, porque la evidencia se versiona en un repositorio
público. Los IDs de caso siguen el catálogo CP-SAAD-2026 (docs/05-entregas/Fase_2_2/Pruebas/).

Estados: APROBADO, FALLIDO, BLOQUEADO (el entorno no permite ejecutarlo), NO EJECUTADO
(fuera de esta corrida, con motivo). Un caso no ejecutado nunca cuenta como aprobado.

Uso:
    .venv/bin/python scripts/qa_e2e_local_vs_aws.py [--local URL] [--sin-capturas] [--reinicio]

`--reinicio` fuerza un nuevo despliegue del servicio ECS y mide la recuperación (CP-SAAD-065);
no se ejecuta por defecto porque reemplaza la tarea en servicio.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Final

import httpx

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
ENV_AWS: Final[Path] = RAIZ / "infra/aws/.env"
SALIDA_BASE: Final[Path] = RAIZ / "reports/validation/e2e_local_aws"
PILA: Final[str] = "Saad"
TIMEOUT: Final[float] = 60.0

APROBADO, FALLIDO, BLOQUEADO, NO_EJECUTADO = "APROBADO", "FALLIDO", "BLOQUEADO", "NO EJECUTADO"


# --------------------------------------------------------------------------- utilidades

def leer_env(ruta: Path = ENV_AWS) -> dict[str, str]:
    """Pares CLAVE=valor de un archivo .env, ignorando comentarios y líneas vacías."""
    valores: dict[str, str] = {}
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                valores[clave.strip()] = valor.strip()
    return valores


class Redactor:
    """Reemplaza datos de la cuenta por marcadores antes de escribir evidencia."""

    def __init__(self, sensibles: dict[str, str]) -> None:
        # Los valores más largos primero, para no reemplazar un fragmento de otro.
        self.pares = sorted(((v, k) for k, v in sensibles.items() if v), key=lambda p: -len(p[0]))

    def __call__(self, texto: Any) -> Any:
        if isinstance(texto, str):
            for valor, marcador in self.pares:
                texto = texto.replace(valor, f"<{marcador}>")
            return texto
        if isinstance(texto, list):
            return [self(x) for x in texto]
        if isinstance(texto, dict):
            return {self(k): self(v) for k, v in texto.items()}
        return texto


@dataclass
class Respuesta:
    estado: int | None
    ms: float | None
    cuerpo: Any = None
    encabezados: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def pedir(cliente: httpx.Client, url: str, **kwargs: Any) -> Respuesta:
    inicio = time.perf_counter()
    try:
        r = cliente.get(url, timeout=TIMEOUT, **kwargs)
    except httpx.HTTPError as error:
        return Respuesta(None, None, error=f"{type(error).__name__}: {error}")
    ms = round((time.perf_counter() - inicio) * 1000, 1)
    try:
        cuerpo: Any = r.json()
    except ValueError:
        cuerpo = r.text
    return Respuesta(r.status_code, ms, cuerpo, dict(r.headers))


@dataclass
class Caso:
    id: str
    nombre: str
    entorno: str
    estado: str
    detalle: str
    evidencia: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------- comprobaciones de API

def resumen_api(nombre: str, r: Respuesta) -> dict[str, Any]:
    """Valores comparables de una respuesta: lo que debería coincidir entre entornos."""
    c = r.cuerpo
    if r.estado != 200:
        return {"estado": r.estado}
    if nombre == "salud":
        return {"estado": 200, "estado_datos": c["estado_datos"], "estado_pronostico": c["estado_pronostico"]}
    if nombre == "meta":
        return {"estado": 200, "modelo": c.get("modelo"), "ultima_semana_observada": c.get("ultima_semana_observada"),
                "horizontes": c.get("horizontes"), "comunas_con_pronostico": c.get("comunas_con_pronostico")}
    if nombre == "territorios":
        return {"estado": 200, "n": len(c), "ids": sorted(t["series_id"] for t in c),
                "con_pronostico": sum(bool(t["tiene_pronostico"]) for t in c)}
    if nombre == "serie_rm":
        hist, pron = c.get("historico") or [], c.get("pronostico") or []
        return {"estado": 200, "n_historico": len(hist), "ultima_semana": hist[-1] if hist else None,
                "n_pronostico": len(pron), "primer_pronostico": pron[0] if pron else None}
    if nombre == "geo_comunas":
        return {"estado": 200, "tipo": c.get("type"), "n_features": len(c.get("features", []))}
    if isinstance(c, list):
        return {"estado": 200, "n": len(c)}
    return {"estado": 200}


def intervalos_ordenados(pronosticos: list[dict[str, Any]]) -> list[str]:
    """Filas cuyo intervalo no cumple inferior ≤ puntual ≤ superior (CP-SAAD-054)."""
    malas = []
    for p in pronosticos:
        inf, pt, sup = p.get("limite_inferior"), p.get("pronostico"), p.get("limite_superior")
        if None not in (inf, pt, sup) and not (inf <= pt <= sup):
            malas.append(f"{p.get('series_id')} h{p.get('horizonte')}")
    return malas


def comparar(local: dict[str, Any], aws: dict[str, Any]) -> list[str]:
    """Diferencias entre los resúmenes de ambos entornos (vacío si son equivalentes)."""
    return [f"{k}: local={local.get(k)!r} aws={aws.get(k)!r}"
            for k in sorted(set(local) | set(aws)) if local.get(k) != aws.get(k)]


ENDPOINTS: Final[list[tuple[str, str, str, int]]] = [
    # (caso, nombre, ruta, estado esperado)
    ("CP-SAAD-017", "salud", "/api/v1/salud", 200),
    ("CP-SAAD-018", "meta", "/api/v1/meta", 200),
    ("CP-SAAD-019", "territorios", "/api/v1/territorios", 200),
    ("CP-SAAD-020", "serie_rm", "/api/v1/series/RM", 200),
    ("CP-SAAD-021", "serie_inexistente", "/api/v1/series/99999", 404),
    ("CP-SAAD-022", "pronosticos", "/api/v1/pronosticos", 200),
    ("CP-SAAD-023", "resumen_comunal", "/api/v1/resumen-comunal", 200),
    ("CP-SAAD-024", "geo_comunas", "/api/v1/geo/comunas", 200),
    ("CP-SAAD-025", "camas_rm", "/api/v1/camas-psiquiatria/RM", 200),
    ("CP-SAAD-026", "calendario", "/api/v1/calendario-eventos?desde=2025-11-01&hasta=2026-12-31", 200),
    ("CP-SAAD-037", "establecimientos", "/api/v1/establecimientos", 200),
    ("CP-SAAD-037", "establecimientos_meta", "/api/v1/establecimientos-meta", 200),
    ("CP-SAAD-047", "suicidios_rm", "/api/v1/suicidios/RM", 200),
]


def casos_api(local: str, aws: str) -> tuple[list[Caso], dict[str, Any]]:
    casos: list[Caso] = []
    crudo: dict[str, Any] = {}
    with httpx.Client(follow_redirects=False) as cliente:
        for caso, nombre, ruta, esperado in ENDPOINTS:
            r_local, r_aws = pedir(cliente, local + ruta), pedir(cliente, aws + ruta)
            res_local, res_aws = resumen_api(nombre, r_local), resumen_api(nombre, r_aws)
            crudo[nombre] = {"local": r_local, "aws": r_aws}
            fallas = [f"{e}: HTTP {r.estado or r.error} (se esperaba {esperado})"
                      for e, r in (("LOCAL", r_local), ("AWS", r_aws)) if r.estado != esperado]
            if nombre == "pronosticos" and r_aws.estado == 200:
                fallas += [f"intervalo desordenado {m}" for m in intervalos_ordenados(r_aws.cuerpo)]
            if nombre == "territorios" and r_aws.estado == 200 and res_aws["n"] != 53:
                fallas.append(f"AWS devuelve {res_aws['n']} territorios; se esperaban 52 comunas + RM")
            diferencias = comparar(res_local, res_aws)
            estado = APROBADO if not fallas and not diferencias else FALLIDO
            detalle = "; ".join(fallas + [f"difiere {d}" for d in diferencias]) or "Igual en LOCAL y AWS"
            casos.append(Caso(caso, f"GET {ruta}", "LOCAL+AWS", estado, detalle, {
                "local": {"http": r_local.estado, "ms": r_local.ms, **res_local},
                "aws": {"http": r_aws.estado, "ms": r_aws.ms, **res_aws},
            }))
    return casos, crudo


# ------------------------------------------------------------ comprobaciones de AWS

def aws_cli(*args: str) -> Any:
    salida = subprocess.run(["aws", *args, "--region", "us-east-1", "--output", "json"],
                            capture_output=True, text=True, check=True).stdout
    return json.loads(salida) if salida.strip() else None


def salidas_pila() -> dict[str, str]:
    pila = aws_cli("cloudformation", "describe-stacks", "--stack-name", PILA)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in pila.get("Outputs", [])}


def dns_alb() -> str:
    recursos = aws_cli("cloudformation", "describe-stack-resources", "--stack-name", PILA)["StackResources"]
    arn = next(r["PhysicalResourceId"] for r in recursos
               if r["ResourceType"] == "AWS::ElasticLoadBalancingV2::LoadBalancer")
    return aws_cli("elbv2", "describe-load-balancers", "--load-balancer-arns", arn)["LoadBalancers"][0]["DNSName"]


def casos_infra(aws: str, salidas: dict[str, str], commit: str) -> list[Caso]:
    casos: list[Caso] = []
    with httpx.Client(follow_redirects=False) as cliente:
        r = pedir(cliente, aws + "/")
        ok = r.estado == 200 and isinstance(r.cuerpo, str) and "<div id=\"root\"" in r.cuerpo
        casos.append(Caso("CP-SAAD-001", "Portal por HTTPS y CloudFront", "AWS", APROBADO if ok else FALLIDO,
                          f"HTTP {r.estado}, certificado TLS validado por el cliente, servido por "
                          f"{r.encabezados.get('via', 'sin encabezado Via')}" if r.estado else r.error or "",
                          {"http": r.estado, "ms": r.ms, "x-cache": r.encabezados.get("x-cache")}))

        r = pedir(cliente, aws.replace("https://", "http://", 1) + "/")
        destino = r.encabezados.get("location", "")
        ok = r.estado in (301, 302, 307, 308) and destino.startswith("https://")
        casos.append(Caso("CP-SAAD-060", "HTTP redirige a HTTPS", "AWS", APROBADO if ok else FALLIDO,
                          f"HTTP {r.estado} → {destino or 'sin Location'}", {"http": r.estado}))

        r = pedir(cliente, aws + "/api/v1/salud")
        ok = r.estado == 200 and "json" in r.encabezados.get("content-type", "")
        casos.append(Caso("CP-SAAD-003", "CloudFront enruta /api/* al ALB", "AWS", APROBADO if ok else FALLIDO,
                          f"HTTP {r.estado}, content-type {r.encabezados.get('content-type')}, "
                          f"cache {r.encabezados.get('x-cache')}", {"http": r.estado, "ms": r.ms}))

        for caso, nombre, bucket in (("CP-SAAD-004", "Bucket del sitio privado", salidas.get("BucketSitio")),
                                     ("CP-SAAD-062", "Bucket de datos privado", salidas.get("BucketDatos"))):
            r = pedir(cliente, f"https://{bucket}.s3.amazonaws.com/")
            ok = r.estado == 403
            casos.append(Caso(caso, nombre + " (acceso anónimo directo a S3)", "AWS", APROBADO if ok else FALLIDO,
                              f"Acceso anónimo: HTTP {r.estado} (se esperaba 403)", {"http": r.estado}))

    alb = dns_alb()
    try:
        socket.create_connection((alb, 80), timeout=8).close()
        estado, detalle = FALLIDO, "El ALB acepta conexiones directas desde fuera de CloudFront"
    except OSError as error:
        estado, detalle = APROBADO, f"Conexión directa al ALB rechazada o sin respuesta ({type(error).__name__})"
    casos.append(Caso("CP-SAAD-062", "ALB inaccesible salvo desde CloudFront", "AWS", estado, detalle))

    servicio = aws_cli("ecs", "describe-services", "--cluster", salidas["Cluster"],
                       "--services", salidas["Servicio"])["services"][0]
    tareas = aws_cli("ecs", "list-tasks", "--cluster", salidas["Cluster"],
                     "--service-name", salidas["Servicio"])["taskArns"]
    ok = servicio["runningCount"] == servicio["desiredCount"] >= 1
    casos.append(Caso("CP-SAAD-005", "Tareas ECS en ejecución", "AWS", APROBADO if ok else FALLIDO,
                      f"running={servicio['runningCount']} desired={servicio['desiredCount']}, "
                      f"despliegue {servicio['deployments'][0]['rolloutState']}",
                      {"tareas": len(tareas)}))

    definicion = aws_cli("ecs", "describe-task-definition", "--task-definition",
                         servicio["taskDefinition"])["taskDefinition"]
    contenedor = definicion["containerDefinitions"][0]
    etiqueta = contenedor["image"].rsplit(":", 1)[-1]
    entorno = {e["name"]: e["value"] for e in contenedor.get("environment", [])}
    casos.append(Caso("CP-SAAD-007", "Imagen ECR trazable a un commit", "AWS",
                      APROBADO if re.fullmatch(r"[0-9a-f]{7,}", etiqueta) else FALLIDO,
                      f"Imagen saad-api:{etiqueta}; commit del repositorio al probar: {commit}. "
                      f"Tarea {definicion['cpu']} CPU / {definicion['memory']} MiB",
                      {"etiqueta": etiqueta, "cpu": definicion["cpu"], "memoria": definicion["memory"],
                       "pronostico_desactualizado": entorno.get("SAAD_USAR_PRONOSTICO_DESACTUALIZADO")}))

    eventos = aws_cli("logs", "filter-log-events", "--log-group-name", "/ecs/saad-api",
                      "--start-time", str(int((time.time() - 3600) * 1000)), "--max-items", "200")
    lineas = [e["message"] for e in (eventos or {}).get("events", [])]
    errores = [l for l in lineas if "[ERROR]" in l or "Traceback" in l]
    casos.append(Caso("CP-SAAD-008", "Solicitudes y errores registrados en CloudWatch", "AWS",
                      APROBADO if lineas else FALLIDO,
                      f"{len(lineas)}{'+' if len(lineas) >= 200 else ''} eventos en la última hora "
                      f"(se leen hasta 200); {len(errores)} con [ERROR] o Traceback",
                      {"errores": errores[:5]}))

    alarmas = aws_cli("cloudwatch", "describe-alarms", "--alarm-name-prefix", "saad-")["MetricAlarms"]
    estados = {a["AlarmName"]: a["StateValue"] for a in alarmas}
    casos.append(Caso("CP-SAAD-008", "Alarmas de CloudWatch configuradas", "AWS",
                      APROBADO if alarmas else FALLIDO,
                      f"{len(alarmas)} alarmas; en ALARM: {[n for n, e in estados.items() if e == 'ALARM'] or 'ninguna'}",
                      {"alarmas": estados}))
    return casos


def caso_secretos_frontend(aws: str, sensibles: dict[str, str]) -> Caso:
    """Busca datos de la cuenta y secretos en el HTML y los JS publicados (CP-SAAD-063)."""
    with httpx.Client() as cliente:
        html = cliente.get(aws + "/", timeout=TIMEOUT).text
        scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
        textos = [html] + [cliente.get(aws + s, timeout=TIMEOUT).text for s in scripts]
    patrones = {"clave de acceso AWS": r"AKIA[0-9A-Z]{16}"}
    hallazgos = [nombre for nombre, valor in sensibles.items()
                 if nombre in ("AWS_ACCOUNT_ID", "SAAD_ORIGIN_SECRET", "SAAD_BUCKET_DATOS")
                 and valor and any(valor in t for t in textos)]
    hallazgos += [n for n, p in patrones.items() if any(re.search(p, t) for t in textos)]
    return Caso("CP-SAAD-063", "Sin secretos en el frontend publicado", "AWS",
                APROBADO if not hallazgos else FALLIDO,
                f"Revisados index.html y {len(scripts)} archivos JS: "
                + ("sin coincidencias" if not hallazgos else f"aparecen {hallazgos}"))


def caso_reinicio(salidas: dict[str, str], aws: str) -> Caso:
    """Fuerza un nuevo despliegue y mide cuánto tarda en volver a servir datos (CP-SAAD-065)."""
    inicio = time.time()
    aws_cli("ecs", "update-service", "--cluster", salidas["Cluster"], "--service", salidas["Servicio"],
            "--force-new-deployment")
    no_disponible = 0
    with httpx.Client() as cliente:
        while time.time() - inicio < 1200:
            servicio = aws_cli("ecs", "describe-services", "--cluster", salidas["Cluster"],
                               "--services", salidas["Servicio"])["services"][0]
            r = pedir(cliente, aws + "/api/v1/salud")
            no_disponible += r.estado != 200
            if servicio["deployments"][0]["rolloutState"] == "COMPLETED" and len(servicio["deployments"]) == 1:
                listo = r.estado == 200 and r.cuerpo.get("estado_pronostico") == "listo"
                return Caso("CP-SAAD-065", "Recuperación tras reemplazo de tarea ECS", "AWS",
                            APROBADO if listo else FALLIDO,
                            f"Nuevo despliegue completo en {time.time() - inicio:.0f} s; "
                            f"{no_disponible} sondeos sin respuesta 200 durante el cambio",
                            {"segundos": round(time.time() - inicio)})
            time.sleep(15)
    return Caso("CP-SAAD-065", "Recuperación tras reemplazo de tarea ECS", "AWS", FALLIDO,
                "El despliegue no terminó en 20 minutos")


NO_EJECUTADOS: Final[list[tuple[str, str, str]]] = [
    ("CP-SAAD-011", "Refresh semanal manual",
     "No aplica en Fargate: el pipeline corre en el equipo y se publica con subir_datos.sh (cambio de alcance de C-42)."),
    ("CP-SAAD-012", "EventBridge dispara la tarea", "No aplica: no hay tarea programada (pipeline local)."),
    ("CP-SAAD-013", "Falla de etapa no promueve artefactos", "No aplica en AWS: el pipeline no corre en Fargate."),
    ("CP-SAAD-014", "Nuevos outputs visibles tras redespliegue",
     "Requiere publicar datos nuevos con subir_datos.sh; no se hizo en esta corrida."),
    ("CP-SAAD-015", "503 y Retry-After durante la inicialización",
     "No observable desde fuera: el despliegue mantiene la tarea anterior hasta que la nueva está sana. "
     "Cubierto por pruebas unitarias de la API (tests/test_api.py)."),
    ("CP-SAAD-016", "Almacenamiento efímero del pipeline", "No aplica: el pipeline no corre en Fargate."),
]


# ------------------------------------------------------------------------- capturas

def capturar(url: str, destino: Path) -> str | None:
    """Captura con Chrome sin interfaz; devuelve el error o None."""
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        return "No se encontró Chrome/Chromium"
    with tempfile.TemporaryDirectory() as perfil:
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            f"--user-data-dir={perfil}", "--window-size=1440,1000",
                            "--virtual-time-budget=20000", f"--screenshot={destino}", url],
                           capture_output=True, text=True, timeout=120)
    return None if destino.is_file() else (r.stderr.strip()[-300:] or "sin captura")


# ---------------------------------------------------------------------------- informe

def escribir_informe(carpeta: Path, meta: dict[str, Any], casos: list[Caso], capturas: list[str],
                     redactar: Redactor) -> None:
    conteo = {e: sum(c.estado == e for c in casos) for e in (APROBADO, FALLIDO, BLOQUEADO, NO_EJECUTADO)}
    lineas = [
        "# Prueba end-to-end AWS contrastada con línea base local (C-44)",
        "",
        f"- **Fecha (UTC):** {meta['fecha_utc']}",
        f"- **Commit del repositorio:** `{meta['commit']}`",
        f"- **Imagen en servicio:** `saad-api:{meta.get('imagen_aws', 'desconocida')}`",
        f"- **LOCAL:** {meta['local']} (Docker Compose)",
        "- **AWS:** CloudFront → ALB → ECS Fargate, región us-east-1. La URL existe y está "
        "registrada para el equipo, pero no se publica en el repositorio.",
        f"- **Ejecutado con:** `{meta['comando']}`",
        "",
        f"**Resultado:** {conteo[APROBADO]} aprobados · {conteo[FALLIDO]} fallidos · "
        f"{conteo[BLOQUEADO]} bloqueados · {conteo[NO_EJECUTADO]} no ejecutados. "
        "Los no ejecutados no cuentan como aprobados.",
        "",
        "## Casos",
        "",
        "| Caso | Prueba | Entorno | Estado | Detalle |",
        "|---|---|---|---|---|",
    ]
    for c in casos:
        lineas.append(f"| {c.id} | {c.nombre} | {c.entorno} | **{c.estado}** | {c.detalle.replace('|', '/')} |")
    comparativos = [c for c in casos if c.entorno == "LOCAL+AWS"]
    lineas += ["", "## Comparación LOCAL / AWS por endpoint", "",
               "| Endpoint | HTTP local | HTTP AWS | ms local | ms AWS | ¿Equivalentes? |",
               "|---|---|---|---|---|---|"]
    for c in comparativos:
        l, a = c.evidencia["local"], c.evidencia["aws"]
        iguales = "sí" if not comparar({k: v for k, v in l.items() if k not in ("ms",)},
                                      {k: v for k, v in a.items() if k not in ("ms",)}) else "no"
        lineas.append(f"| `{c.nombre[4:]}` | {l['http']} | {a['http']} | {l['ms']} | {a['ms']} | {iguales} |")
    if capturas:
        lineas += ["", "## Capturas", ""] + [f"![{n}](capturas/{n})" for n in capturas]
    lineas += ["", "## Defectos para C-06", ""]
    fallidos = [c for c in casos if c.estado == FALLIDO]
    lineas += [f"- **{c.id} · {c.nombre}:** {c.detalle}" for c in fallidos] or ["- Ninguno en esta corrida."]
    lineas += ["", "Evidencia completa por caso en `resultados.json`.", ""]
    (carpeta / "informe.md").write_text(redactar("\n".join(lineas)), encoding="utf-8")
    datos = {"meta": meta, "conteo": conteo, "casos": [asdict(c) for c in casos]}
    (carpeta / "resultados.json").write_text(
        json.dumps(redactar(json.loads(json.dumps(datos, default=str))), ensure_ascii=False, indent=2),
        encoding="utf-8")


# ------------------------------------------------------------------------------ main

def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba E2E de SAAD en AWS contra la línea base local.")
    parser.add_argument("--local", default="http://localhost:8080", help="URL del Docker Compose local")
    parser.add_argument("--sin-capturas", action="store_true", help="No sacar capturas con Chrome")
    parser.add_argument("--reinicio", action="store_true", help="Forzar redespliegue y medir recuperación (CP-SAAD-065)")
    parser.add_argument("--salida", type=Path, default=SALIDA_BASE, help="Carpeta base de la evidencia")
    args = parser.parse_args()

    env = {**leer_env(), **{k: v for k, v in os.environ.items() if k.startswith(("SAAD_", "AWS_ACCOUNT"))}}
    aws = env.get("SAAD_URL", "").rstrip("/")
    if not aws:
        parser.error(f"Falta SAAD_URL en {ENV_AWS.relative_to(RAIZ)}")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

    salidas = salidas_pila()
    alb = dns_alb()
    sensibles = {"URL_AWS": aws, "URL_AWS_HOST": aws.split("://", 1)[1], "ALB": alb,
                 "AWS_ACCOUNT_ID": env.get("AWS_ACCOUNT_ID", ""),
                 "SAAD_ORIGIN_SECRET": env.get("SAAD_ORIGIN_SECRET", ""),
                 "SAAD_BUCKET_DATOS": salidas.get("BucketDatos", ""),
                 "SAAD_BUCKET_SITIO": salidas.get("BucketSitio", ""),
                 "SAAD_DISTRIBUCION_ID": salidas.get("DistribucionId", "")}
    redactar = Redactor(sensibles)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=RAIZ).stdout.strip()
    fecha = datetime.now(timezone.utc)
    carpeta = args.salida / fecha.strftime("%Y%m%dT%H%M%SZ")
    (carpeta / "capturas").mkdir(parents=True, exist_ok=True)

    casos: list[Caso] = []
    pasos: list[tuple[str, Callable[[], list[Caso]]]] = [
        ("API local/AWS", lambda: casos_api(args.local, aws)[0]),
        ("Infraestructura AWS", lambda: casos_infra(aws, salidas, commit)),
        ("Secretos en frontend", lambda: [caso_secretos_frontend(aws, sensibles)]),
    ]
    for nombre, paso in pasos:
        print(f"→ {nombre}…", flush=True)
        try:
            casos += paso()
        except Exception as error:  # noqa: BLE001 - un paso caído queda registrado, no detiene el resto
            casos.append(Caso("—", nombre, "AWS", BLOQUEADO, f"{type(error).__name__}: {error}"))
    if args.reinicio:
        print("→ Reinicio de la tarea ECS (puede tardar varios minutos)…", flush=True)
        casos.append(caso_reinicio(salidas, aws))
    else:
        casos.append(Caso("CP-SAAD-065", "Recuperación tras reemplazo de tarea ECS", "AWS", NO_EJECUTADO,
                          "Se ejecuta con --reinicio porque reemplaza la tarea en servicio."))
    casos += [Caso(i, n, "AWS", NO_EJECUTADO, m) for i, n, m in NO_EJECUTADOS]

    capturas: list[str] = []
    if not args.sin_capturas:
        print("→ Capturas…", flush=True)
        for entorno, base in (("local", args.local), ("aws", aws)):
            for vista, ruta in (("inicio", "/"), ("tablero", "/#/tablero"), ("establecimientos", "/#/establecimientos")):
                archivo = f"{entorno}_{vista}.png"
                error = capturar(base + ruta, carpeta / "capturas" / archivo)
                if error is None:
                    capturas.append(archivo)
                else:
                    print(f"   sin captura {archivo}: {error}")

    imagen = next((c.evidencia.get("etiqueta") for c in casos if c.id == "CP-SAAD-007"), None)
    meta = {"fecha_utc": fecha.isoformat(timespec="seconds"), "commit": commit, "imagen_aws": imagen,
            "local": args.local, "comando": "scripts/qa_e2e_local_vs_aws.py" + (" --reinicio" if args.reinicio else "")}
    escribir_informe(carpeta, meta, casos, capturas, redactar)
    print(f"Informe: {carpeta / 'informe.md'}")
    return 0 if not any(c.estado == FALLIDO for c in casos) else 1


if __name__ == "__main__":
    raise SystemExit(main())
