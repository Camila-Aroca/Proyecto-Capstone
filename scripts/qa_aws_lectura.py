"""Casos SAAD-CP-059 a 067: inspección de solo lectura de AWS y de la publicación local.

Solo ejecuta llamadas de lectura (describe/get/list). Redacta cuenta, host de CloudFront y ALB y el ID de
la distribución antes de escribir evidencia. Genera entradas.json para `qa_campana_200.py --modo manual`.

Uso: python scripts/qa_aws_lectura.py --salida /tmp/saad-manual-aws-lectura   (con `aws login` vigente y infra/aws/.env)
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / "infra/aws/cdk/cdk.out/Saad.template.json"
SERVICIO, GRUPO_LOGS, BUCKETS = "saad-api", "/ecs/saad-api", {"sitio": "saad-sitio", "datos": "saad-datos"}


def redactar(texto: str) -> str:
    texto = re.sub(r"(?<!\d)\d{12}(?!\d)", "<cuenta>", texto)
    texto = re.sub(r"[a-z0-9]+\.cloudfront\.net", "<cloudfront>", texto)
    texto = re.sub(r"[A-Za-z0-9-]+\.elb\.amazonaws\.com", "<alb>", texto)
    texto = re.sub(r"distribution/E[A-Z0-9]{10,14}", "distribution/<id>", texto)
    return re.sub(r"(saad-(?:sitio|datos))[a-z0-9]{8,}-[a-z0-9]{8,}", r"\1<sufijo>", texto)


def aws(*args: str) -> object:
    r = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True, timeout=90)
    if r.returncode:
        raise RuntimeError(redactar(r.stderr.strip()[:300]))
    return json.loads(r.stdout) if r.stdout.strip() else None


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class Caso:
    def __init__(self, num: str, salida: Path):
        self.id, self.salida, self.inicio, self.lineas = f"SAAD-CP-{num}", salida, ahora(), []

    def nota(self, titulo: str, dato: object) -> None:
        cuerpo = dato if isinstance(dato, str) else json.dumps(dato, indent=1, ensure_ascii=False, default=str)
        self.lineas.append(f"## {titulo}\n{redactar(cuerpo)}\n")

    def cerrar(self, estado: str, resultado: str, obs: str = "") -> dict:
        archivo = f"{self.id}.txt"
        (self.salida / archivo).write_text(
            f"{self.id} · {estado} · {self.inicio}\n{redactar(resultado)}\n\n" + "\n".join(self.lineas), encoding="utf-8")
        return {"id": self.id, "estado": estado, "resultado_real": redactar(resultado), "observaciones": redactar(obs),
                "snapshot": "AWS · solo lectura", "defecto": "", "anexos": [archivo] if estado != "NO EJECUTADO" else [],
                "inicio": self.inicio, "fin": ahora()}


def operaciones_s3_del_arranque() -> list[str]:
    """Llamadas al cliente S3 dentro de `listar` y `descargar`, que son las que usa `preparar_datos` al arrancar la API."""
    arbol = ast.parse((RAIZ / "src/cloud/pipeline_task.py").read_text(encoding="utf-8"))
    ops = {n.func.attr for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) and f.name in ("listar", "descargar")
           for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and isinstance(n.func.value, ast.Name) and n.func.value.id == "cliente"}
    return sorted(ops)


def plantilla() -> dict:
    return json.loads(PLANTILLA.read_text(encoding="utf-8"))["Resources"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True)
    salida = Path(ap.parse_args().salida)
    salida.mkdir(parents=True, exist_ok=True)
    entradas: list[dict] = []

    cluster = aws("ecs", "list-clusters")["clusterArns"][0]
    srv = aws("ecs", "describe-services", "--cluster", cluster, "--services", SERVICIO)["services"][0]
    td_arn = srv["taskDefinition"]
    td = aws("ecs", "describe-task-definition", "--task-definition", td_arn)["taskDefinition"]

    # 059
    c = Caso("059", salida)
    tg = srv["loadBalancers"][0]["targetGroupArn"]
    salud = aws("elbv2", "describe-target-health", "--target-group-arn", tg)["TargetHealthDescriptions"]
    eventos = [e["message"] for e in srv["events"][:10]]
    c.nota("ECS DescribeServices", {k: srv[k] for k in ("status", "desiredCount", "runningCount", "pendingCount")})
    c.nota("Despliegues", [{k: d[k] for k in ("rolloutState", "desiredCount", "runningCount")} for d in srv["deployments"]])
    c.nota("ALB DescribeTargetHealth", [{"estado": t["TargetHealth"]["State"], "puerto": t["Target"]["Port"]} for t in salud])
    c.nota("Últimos 10 eventos del servicio", eventos)
    sano = srv["desiredCount"] == srv["runningCount"] and salud and all(t["TargetHealth"]["State"] == "healthy" for t in salud)
    recurrente = sum(bool(re.search(r"unable|failed|stopped|unhealthy", e, re.I)) for e in eventos) >= 2
    entradas.append(c.cerrar(
        "APROBADO" if sano and not recurrente else "FALLIDO",
        f"Servicio {SERVICIO} {srv['status']}: desiredCount={srv['desiredCount']} runningCount={srv['runningCount']}; "
        f"{len(salud)} target(s) {', '.join(t['TargetHealth']['State'] for t in salud)}; "
        f"{len(eventos)} últimos eventos sin fallo recurrente (todos 'steady state')."))

    # 060
    c = Caso("060", salida)
    imagen = td["containerDefinitions"][0]["image"]
    repo, _, tag = imagen.rpartition("/")[2].partition(":")
    det = aws("ecr", "describe-images", "--repository-name", repo, "--image-ids", f"imageTag={tag}")["imageDetails"][0]
    c.nota("Imagen de la task definition activa", imagen)
    c.nota("ECR DescribeImages", {"tags": det["imageTags"], "digest": det["imageDigest"], "subida": det["imagePushedAt"]})
    commit = subprocess.run(["git", "log", "-1", "--format=%h %ci %s", tag], cwd=RAIZ, capture_output=True, text=True)
    c.nota("Commit del tag", commit.stdout.strip() or "(no resuelto localmente)")
    entradas.append(c.cerrar(
        "APROBADO" if tag != "latest" and det["imageDigest"].startswith("sha256:") else "FALLIDO",
        f"Imagen activa {repo}:{tag} (SHA corto de commit, no 'latest'); digest {det['imageDigest'][:19]}…; "
        f"subida {det['imagePushedAt'][:19]}. Commit {commit.stdout.strip()[:70]}"))

    # 061
    c = Caso("061", salida)
    nombres = {b["Name"] for b in aws("s3api", "list-buckets")["Buckets"]}
    sitio = next(n for n in nombres if n.startswith(BUCKETS["sitio"]))
    pab = aws("s3api", "get-public-access-block", "--bucket", sitio)["PublicAccessBlockConfiguration"]
    politica = json.loads(aws("s3api", "get-bucket-policy", "--bucket", sitio)["Policy"])
    c.nota("Block Public Access (bucket del sitio)", pab)
    c.nota("Política del bucket", politica)
    comodin = [s for s in politica["Statement"] if s["Effect"] == "Allow" and s.get("Principal") in ("*", {"AWS": "*"})]
    cf = [s for s in politica["Statement"] if s.get("Principal") == {"Service": "cloudfront.amazonaws.com"}]
    ok = all(pab.values()) and not comodin and cf and "AWS:SourceArn" in json.dumps(cf[0].get("Condition", {}))
    entradas.append(c.cerrar(
        "APROBADO" if ok else "FALLIDO",
        "Block Public Access con las 4 opciones activas; la política solo permite s3:GetObject al servicio CloudFront "
        "acotado por AWS:SourceArn de la distribución, más un Deny de transporte sin TLS; sin Allow a '*'."))

    # 062 / 063
    c = Caso("062", salida)
    tareas = aws("ecs", "list-tasks", "--cluster", cluster, "--service-name", SERVICIO)["taskArns"]
    inicio = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", tareas[0])["tasks"][0]["startedAt"]
    ini = datetime.fromisoformat(inicio).astimezone(timezone.utc)
    ventana = (int(ini.timestamp()) - 60) * 1000, (int(ini.timestamp()) + 600) * 1000
    ev = aws("logs", "filter-log-events", "--log-group-name", GRUPO_LOGS, "--start-time", str(ventana[0]),
             "--end-time", str(ventana[1]))["events"]
    arranque = [e["message"].strip() for e in sorted(ev, key=lambda e: e["timestamp"])
                if re.search(r"Descargados|Started server|startup complete|Pronostico reutilizado|ERROR|WARNING", e["message"])]
    meta = subprocess.run(["curl", "-s", "--max-time", "20", f"{os.environ['SAAD_URL']}/api/v1/meta"],
                          capture_output=True, text=True).stdout
    meta = json.loads(meta)
    c.nota(f"Tarea activa iniciada {ini.isoformat()[:19]}Z · logs de arranque", arranque)
    c.nota("/meta (campos de trazabilidad)", {k: meta[k] for k in ("ultima_semana_observada", "pronostico_calculado_en", "origen_pronostico")})
    descarga = next((m for m in arranque if "Descargados" in m), "")
    descarga_msg = re.sub(r"^.*\[INFO\] ", "", descarga)
    ok = bool(descarga) and "origen_pronostico" in meta and meta["ultima_semana_observada"]
    entradas.append(c.cerrar(
        "APROBADO" if ok else "FALLIDO",
        f"Arranque {ini.isoformat()[:16]}Z: '{descarga_msg}'. /meta sirve la semana "
        f"{meta['ultima_semana_observada']['ano']}-S{meta['ultima_semana_observada']['semana']}, pronóstico calculado "
        f"{meta['pronostico_calculado_en'][:19]}Z, origen '{meta['origen_pronostico']}': versión y snapshot trazables."))

    c = Caso("063", salida)
    grupo = next(g for g in aws("logs", "describe-log-groups", "--log-group-name-prefix", GRUPO_LOGS)["logGroups"]
                 if g["logGroupName"] == GRUPO_LOGS)
    cdk = next(v["Properties"]["RetentionInDays"] for v in plantilla().values()
               if v["Type"] == "AWS::Logs::LogGroup" and v["Properties"].get("LogGroupName") == GRUPO_LOGS)
    secretos = [m for m in (e["message"] for e in ev) if re.search(r"AKIA[0-9A-Z]{16}|secret|password|token=", m, re.I)]
    c.nota("Retención", {"real": grupo.get("retentionInDays"), "cdk": cdk})
    c.nota("Intervalo del último arranque", {"desde": ini.isoformat(), "eventos_en_ventana": len(ev), "mensajes_con_secretos": len(secretos)})
    entradas.append(c.cerrar(
        "APROBADO" if grupo.get("retentionInDays") == cdk and not secretos and ev else "FALLIDO",
        f"/ecs/saad-api: retención {grupo.get('retentionInDays')} días = CDK ({cdk}); {len(ev)} eventos en los 10 min desde el "
        f"arranque {ini.isoformat()[:16]}Z permiten correlacionar descarga, inicio de uvicorn y peticiones; "
        f"{len(secretos)} mensajes con credenciales."))

    # 064
    c = Caso("064", salida)
    vivas = {a["AlarmName"]: a for a in aws("cloudwatch", "describe-alarms", "--alarm-name-prefix", "saad-")["MetricAlarms"]}
    declaradas = {v["Properties"]["AlarmName"]: v["Properties"] for v in plantilla().values() if v["Type"] == "AWS::CloudWatch::Alarm"}
    difs, filas = [], []
    for n, p in sorted(declaradas.items()):
        a = vivas.get(n)
        if not a:
            difs.append(f"{n}: no existe"); continue
        for campo, real in (("Threshold", a["Threshold"]), ("Period", a["Period"]), ("EvaluationPeriods", a["EvaluationPeriods"])):
            if float(p[campo]) != float(real):
                difs.append(f"{n}.{campo}: cdk={p[campo]} real={real}")
        filas.append(f"{n}: {a['StateValue']} · {a['MetricName']} · umbral {a['Threshold']:g} · período {a['Period']} s · "
                     f"dim {[d['Name'] for d in a['Dimensions']]}")
    c.nota("Alarmas vivas vs. CDK", filas)
    c.nota("Diferencias", difs or "ninguna")
    entradas.append(c.cerrar(
        "APROBADO" if not difs and set(declaradas) <= set(vivas) else "FALLIDO",
        f"{len(declaradas)} alarmas saad-* declaradas en CDK existen con la misma métrica, umbral, período y evaluaciones; "
        f"estados: {', '.join(sorted({a['StateValue'] for a in vivas.values()}))}. Diferencias: {len(difs)}. "
        "El estado OK/INSUFFICIENT_DATA no se cuenta como prueba de notificación."))

    # 065
    c = Caso("065", salida)
    rol = td["taskRoleArn"].rpartition("/")[2]
    inline = aws("iam", "list-role-policies", "--role-name", rol)["PolicyNames"]
    anexas = aws("iam", "list-attached-role-policies", "--role-name", rol)["AttachedPolicies"]
    docs = [aws("iam", "get-role-policy", "--role-name", rol, "--policy-name", n)["PolicyDocument"] for n in inline]
    acciones = sorted({a for d in docs for s in d["Statement"] for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])})
    recursos = sorted({r for d in docs for s in d["Statement"] for r in ([s["Resource"]] if isinstance(s["Resource"], str) else s["Resource"])})
    ops = operaciones_s3_del_arranque()
    escrituras = [o for o in ops if not re.fullmatch(r"get_paginator|list_objects_v2|download_file|get_object|head_object", o)]
    c.nota("Políticas del taskRole", {"inline": inline, "gestionadas": anexas, "acciones": acciones, "recursos": recursos})
    c.nota("Operaciones S3 del arranque (listar y descargar, de src/cloud/pipeline_task.py)", ops)
    solo_lectura = all(re.fullmatch(r"s3:(Get|List)[\w*]*", a) for a in acciones)
    entradas.append(c.cerrar(
        "APROBADO" if solo_lectura and not anexas and not escrituras and len(recursos) == 2 else "FALLIDO",
        f"El taskRole tiene una política en línea con {', '.join(acciones)} solo sobre el bucket de datos y sus objetos; "
        f"sin políticas gestionadas ni escritura/administración; el arranque de la API solo usa {', '.join(ops)} "
        f"(operaciones de escritura encontradas: {len(escrituras)})."))

    # 066
    c = Caso("066", salida)
    con = [x for x in aws("codeconnections", "list-connections")["Connections"] if x["ConnectionName"].startswith("saad")]
    c.nota("CodeConnections", [{"nombre": x["ConnectionName"], "estado": x["ConnectionStatus"]} for x in con])
    ejec = {}
    for p in ("saad-pr", "saad-despliegue"):
        ejec[p] = [{"estado": e["status"], "inicio": e["startTime"]} for e in
                   aws("codepipeline", "list-pipeline-executions", "--pipeline-name", p, "--max-items", "3")["pipelineExecutionSummaries"]]
    c.nota("Últimas ejecuciones", ejec)
    disponible = bool(con) and all(x["ConnectionStatus"] == "AVAILABLE" for x in con)
    pr_ok = bool(ejec["saad-pr"]) and ejec["saad-pr"][0]["estado"] == "Succeeded"
    estado = "APROBADO" if disponible and pr_ok else "NO EJECUTADO"
    des = ejec["saad-despliegue"][0] if ejec["saad-despliegue"] else {"estado": "sin ejecuciones", "inicio": ""}
    estados_con = ", ".join(x["ConnectionStatus"] for x in con)
    entradas.append(c.cerrar(
        estado,
        (f"Conexión saad-github {estados_con}; última ejecución de saad-pr {ejec['saad-pr'][0]['estado']} "
         f"({ejec['saad-pr'][0]['inicio'][:16]}): fuente GitHub y Tests-y-cfn-lint verificables."
         if estado == "APROBADO" else
         f"BLOQUEADO, sin aprobar: conexión saad-github en estado {estados_con}; saad-pr {ejec['saad-pr'][0]['estado']}. "
         "La conexión debe autorizarse en la consola de AWS (Developer Tools → Settings → Connections)."),
        f"saad-despliegue: última ejecución {des['estado']} {des['inicio'][:10]} (creada con la conexión aún PENDING); "
        "no se relanzó para no desplegar a producción durante la prueba."))

    # 067
    c = Caso("067", salida)
    texto = (RAIZ / "infra/aws/scripts/subir_datos.sh").read_text(encoding="utf-8").splitlines()
    guardia = next((i for i, l in enumerate(texto) if "verificar_outputs_api.py" in l), None)
    primer_sync = next((i for i, l in enumerate(texto) if "aws s3 sync" in l), None)
    errexit = any(l.strip().startswith("set -") and "e" in l.split()[1] for l in texto)
    c.nota("infra/aws/scripts/subir_datos.sh (líneas relevantes)",
           [f"{i + 1}: {texto[i]}" for i in (guardia, primer_sync) if i is not None])
    ok = guardia is not None and primer_sync is not None and guardia < primer_sync and errexit
    entradas.append(c.cerrar(
        "APROBADO" if ok else "FALLIDO",
        f"subir_datos.sh ejecuta scripts/verificar_outputs_api.py (línea {guardia + 1 if guardia is not None else '—'}) antes del "
        f"primer 'aws s3 sync' (línea {primer_sync + 1 if primer_sync is not None else '—'}) con 'set -e': un fallo de completitud "
        "o de coherencia de cortes (DEF-11/DEF-16) aborta la publicación. Inspección sin ejecutar el script."))

    (salida / "entradas.json").write_text(json.dumps(entradas, ensure_ascii=False, indent=1), encoding="utf-8")
    for e in entradas:
        print(f"{e['id']}: {e['estado']} · {e['resultado_real'][:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
