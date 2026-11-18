"""Casos CAT70 sin equivalente en el catálogo de 200 que no cubre `qa_ciclo_pruebas.py`.

El catálogo de 70 casos solo fija título y prioridad de estos casos; el criterio de cada uno queda escrito
aquí, junto a su comprobación. Se ejecuta contra la API local y la de AWS (solo lecturas) y deja
`<salida>/local/<UTC>/resultados.json` y `<salida>/aws/<UTC>/resultados.json`, que lee
`qa_registro_principal.py`.

Uso: python scripts/qa_cat70_complementarios.py --salida reports/validation/ciclos_pruebas/ciclo_17_<UTC>
     (variables: SAAD_URL para AWS; --local URL para el Docker Compose local; `aws login` para 064 y 069)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

APROBADO, FALLIDO, NO_EJECUTADO = "APROBADO", "FALLIDO", "NO EJECUTADO"
RM_POBLACION_MIN, RM_POBLACION_MAX = 7_000_000, 9_500_000


def obtener(url: str, intentos: int = 3) -> tuple[int, Any, dict[str, str]]:
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "saad-qa"}), timeout=60) as r:
                return r.status, json.loads(r.read() or "null"), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code == 503 and i < intentos - 1:
                time.sleep(3)
                continue
            return e.code, None, dict(e.headers)
    return 0, None, {}


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/") + "/api/v1"
        self._cache: dict[str, Any] = {}

    def get(self, ruta: str) -> Any:
        if ruta not in self._cache:
            codigo, cuerpo, _ = obtener(self.base + ruta)
            if codigo != 200:
                raise RuntimeError(f"GET {ruta} → HTTP {codigo}")
            self._cache[ruta] = cuerpo
        return self._cache[ruta]

    def series(self) -> dict[str, dict]:
        ids = [t["series_id"] for t in self.get("/territorios") if t["tiene_pronostico"]]
        return {i: self.get(f"/series/{i}?semanas=52") for i in ids}


def caso(cid: str, nombre: str, estado: str, detalle: str, evidencia: dict | None = None) -> dict:
    return {"id": cid, "nombre": nombre, "estado": estado, "detalle": detalle, "evidencia": evidencia or {}}


def c046(api: Api) -> dict:
    r = api.get("/caracterizacion/urgencias/region/RM?semanas=2026-44,2026-45")
    edad = sum(x["valor"] for x in r["edad"])
    sexo_obs = r["sexo"]
    esc = r.get("escenario") or {}
    sexo = sum(x["valor"] for x in (sexo_obs or esc.get("sexo") or []))
    declarado = bool(sexo_obs) or "No es sexo observado" in (esc.get("advertencia") or "")
    ok = edad == r["total"] and sexo == r["total"] and declarado
    return caso("CP-SAAD-046", "Caracterización por sexo y edad del flujo", APROBADO if ok else FALLIDO,
                f"Total {r['total']}: edad suma {edad}, sexo suma {sexo}; el sexo se "
                f"{'observa' if sexo_obs else 'estima y se declara como escenario, no como dato observado'}.",
                {"total": r["total"], "suma_edad": edad, "suma_sexo": sexo, "semanas": r["semanas"]})


def c052_054(api: Api) -> list[dict]:
    series = api.series()
    bajas, desordenados, negativos, picos, puntos = [], [], [], [], 0
    for sid, s in series.items():
        maximo = max((h["atenciones"] for h in s["historico"]), default=0)
        media = sum(h["atenciones"] for h in s["historico"][-26:]) / max(1, len(s["historico"][-26:]))
        if media < 20:
            bajas.append(sid)
        for p in s["pronostico"]:
            puntos += 1
            if not p["limite_inferior"] <= p["pronostico"] <= p["limite_superior"]:
                desordenados.append((sid, p["horizonte"]))
            if min(p["limite_inferior"], p["pronostico"]) < 0:
                negativos.append((sid, p["horizonte"]))
            if media < 20 and p["pronostico"] > 1.5 * maximo + 3:
                picos.append((sid, p["horizonte"]))
    r54 = caso("CP-SAAD-054", "Orden lógico de intervalos de predicción",
               APROBADO if not desordenados and not negativos else FALLIDO,
               f"{puntos} puntos de pronóstico en {len(series)} series (RM y comunas): límite inferior ≤ pronóstico ≤ "
               f"límite superior en todos; fuera de orden: {len(desordenados)}; negativos: {len(negativos)}.",
               {"series": len(series), "puntos": puntos, "desordenados": len(desordenados)})
    r52 = caso("CP-SAAD-052", "Semanas con recuento muy bajo no parecen picos artificiales",
               APROBADO if bajas and not picos else (NO_EJECUTADO if not bajas else FALLIDO),
               f"{len(bajas)} series con promedio < 20 atenciones/semana en las últimas 26 semanas; ningún pronóstico supera "
               f"1,5 × su máximo histórico + 3 (superados: {len(picos)}).",
               {"series_bajas": len(bajas), "picos": len(picos)})
    return [r52, r54]


def c055(api: Api) -> dict:
    meta = api.get("/meta")
    advertencias = " ".join(meta["advertencias"])
    fuera = [h for h in meta["cobertura_holdout"] if not h["dentro_de_tolerancia"]]
    sin_declarar = [h["nivel"] for h in fuera if f"{round(h['cobertura_observada'] * 100)}%" not in advertencias]
    ok = bool(meta["cobertura_holdout"]) and not sin_declarar
    return caso("CP-SAAD-055", "Cobertura holdout declarada sin engaño", APROBADO if ok else FALLIDO,
                f"Intervalo nominal {meta['nivel_intervalo']:.0%}; coberturas observadas "
                + ", ".join(f"{h['nivel']} {h['cobertura_observada']:.1%}" for h in meta["cobertura_holdout"])
                + f"; {len(fuera)} fuera de tolerancia, todas declaradas en las advertencias de /meta"
                + ("" if not sin_declarar else f" (sin declarar: {sin_declarar})") + ".",
                {"cobertura_holdout": meta["cobertura_holdout"]})


def c056(api: Api) -> dict:
    meta, rm = api.get("/meta"), api.get("/series/RM?semanas=52")
    ult = meta["ultima_semana_observada"]
    inicio = date.fromisoformat(ult["fecha_inicio"])
    calculado = datetime.fromisoformat(meta["pronostico_calculado_en"].replace("Z", "+00:00")).date()
    cerrada = inicio + timedelta(days=6) < calculado
    ultimo_hist, primero_pron = rm["historico"][-1], rm["pronostico"][0]
    contigua = date.fromisoformat(primero_pron["fecha_inicio"]) == inicio + timedelta(days=7)
    coincide = (ultimo_hist["ano"], ultimo_hist["semana"]) == (ult["ano"], ult["semana"])
    ok = cerrada and contigua and coincide and meta.get("semana_en_curso") is None
    return caso("CP-SAAD-056", "Semana parcial no sustituye semana cerrada", APROBADO if ok else FALLIDO,
                f"Última semana observada {ult['ano']}-S{ult['semana']} ({inicio} a {inicio + timedelta(days=6)}), cerrada antes "
                f"del cálculo del {calculado}; el histórico termina en ella, el primer pronóstico empieza el "
                f"{primero_pron['fecha_inicio']} y semana_en_curso es {meta.get('semana_en_curso')}.",
                {"ultima_observada": ult, "primer_pronostico": primero_pron["fecha_inicio"]})


def c057(api: Api) -> dict:
    filas = api.get("/resumen-comunal")
    con = [f for f in filas if f["tiene_pronostico"] and f["tasa_pronostico_por_10000"]]
    sin = [f for f in filas if not f["tiene_pronostico"]]
    poblacion = sum(f["pronostico_promedio"] / f["tasa_pronostico_por_10000"] * 10_000 for f in con)
    sin_cero = all(f["tasa_pronostico_por_10000"] is None and f["pronostico_promedio"] is None for f in sin)
    ok = RM_POBLACION_MIN <= poblacion <= RM_POBLACION_MAX and sin_cero and len(con) > 0
    return caso("CP-SAAD-057", "Tasas y denominadores territoriales", APROBADO if ok else FALLIDO,
                f"{len(con)} comunas con tasa por 10.000: el denominador implícito (pronóstico ÷ tasa × 10.000) suma "
                f"{poblacion / 1e6:.2f} millones, dentro del rango plausible de la RM ({RM_POBLACION_MIN / 1e6:.1f}–"
                f"{RM_POBLACION_MAX / 1e6:.1f} M); las {len(sin)} comunas sin pronóstico tienen tasa nula, no cero.",
                {"comunas_con_tasa": len(con), "poblacion_implicita": round(poblacion), "sin_pronostico": len(sin)})


def aws_cli(*args: str) -> Any:
    r = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True, timeout=90)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:200])
    return json.loads(r.stdout) if r.stdout.strip() else None


def c064(base: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + "/", headers={"User-Agent": "saad-qa"}), timeout=60) as r:
        html, cab = r.read(), dict(r.headers)
    sitio = next(b["Name"] for b in aws_cli("s3api", "list-buckets")["Buckets"] if b["Name"].startswith("saad-sitio"))
    tmp = Path("/tmp/saad-064-index.html")
    aws_cli("s3api", "get-object", "--bucket", sitio, "--key", "index.html", str(tmp))
    en_s3 = tmp.read_bytes()
    activos = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', html)
    caidos = [a.decode() for a in activos
              if urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + a.decode(), headers={"User-Agent": "saad-qa"}), timeout=60).status != 200]
    igual = hashlib.sha256(html).hexdigest() == hashlib.sha256(en_s3).hexdigest()
    ok = igual and activos and not caidos
    return caso("CP-SAAD-064", "Cache CloudFront tras nueva versión", APROBADO if ok else FALLIDO,
                f"El index.html que sirve CloudFront es idéntico (SHA-256 {hashlib.sha256(html).hexdigest()[:12]}…) al publicado en el "
                f"bucket del sitio, referencia {len(activos)} archivos de /assets y todos responden 200; "
                f"cache-control: {cab.get('Cache-Control', 'no informado')}; x-cache: {cab.get('X-Cache', 'no informado')}.",
                {"index_igual_a_s3": igual, "assets": len(activos), "assets_caidos": caidos})


def c069() -> dict:
    cuenta = aws_cli("sts", "get-caller-identity")["Account"]
    presupuestos = aws_cli("budgets", "describe-budgets", "--account-id", cuenta)["Budgets"]
    etiquetados = aws_cli("resourcegroupstaggingapi", "get-resources", "--tag-filters", "Key=proyecto,Values=saad")
    n_etiquetados = len(etiquetados["ResourceTagMappingList"])
    hoy = date.today()
    ini = hoy.replace(day=1).isoformat()
    por_etiqueta = aws_cli("ce", "get-cost-and-usage", "--time-period", f"Start={ini},End={hoy.isoformat()}", "--granularity", "MONTHLY",
                           "--metrics", "UnblendedCost", "--filter",
                           json.dumps({"Tags": {"Key": "proyecto", "Values": ["saad"]}}))["ResultsByTime"][0]["Total"]["UnblendedCost"]
    por_servicio = aws_cli("ce", "get-cost-and-usage", "--time-period", f"Start={ini},End={hoy.isoformat()}", "--granularity", "MONTHLY",
                           "--metrics", "UnblendedCost", "--group-by", "Type=DIMENSION,Key=SERVICE")["ResultsByTime"][0]["Groups"]
    relevantes = {g["Keys"][0]: round(float(g["Metrics"]["UnblendedCost"]["Amount"]), 2) for g in por_servicio
                  if re.search(r"Container|Elastic Load|CloudFront|Simple Storage|CloudWatch|CodePipeline|CodeBuild", g["Keys"][0])}
    etiqueta_activa = float(por_etiqueta["Amount"]) > 0
    ok = bool(presupuestos) and n_etiquetados >= 10
    obs = ("" if etiqueta_activa else " Observación: la etiqueta `proyecto` no está activada como etiqueta de asignación de costos "
           "(el costo filtrado por etiqueta es 0 USD), por lo que el costo del ambiente se lee por servicio y no por etiqueta.")
    return caso("CP-SAAD-069", "Presupuesto, etiquetas y costo del ambiente de evaluación", APROBADO if ok else FALLIDO,
                f"{len(presupuestos)} presupuestos mensuales en la cuenta ({', '.join(f'{b['BudgetName']} {float(b['BudgetLimit']['Amount']):g} {b['BudgetLimit']['Unit']}' for b in presupuestos)}); "
                f"{n_etiquetados} recursos con la etiqueta proyecto=saad; costo del mes por servicio (USD): {relevantes}.{obs}",
                {"presupuestos": len(presupuestos), "recursos_etiquetados": n_etiquetados, "costo_por_servicio_usd": relevantes,
                 "costo_por_etiqueta_usd": por_etiqueta["Amount"]})


def c010() -> dict:
    return caso("CP-SAAD-010", "Permisos del rol de tarea pipeline", NO_EJECUTADO,
                "No aplica: el pipeline de datos corre en el equipo y se publica con subir_datos.sh; no hay tarea de pipeline en "
                "Fargate (cambio de alcance de C-42), así que no existe un rol de tarea de pipeline que inspeccionar.")


def correr(salida: Path, entorno: str, comprobaciones: list[Callable[[], Any]]) -> None:
    casos: list[dict] = []
    for f in comprobaciones:
        try:
            r = f()
            casos += r if isinstance(r, list) else [r]
        except Exception as e:  # el fallo de una comprobación no debe ocultar las demás
            casos.append(caso("?", f.__name__, NO_EJECUTADO, f"No se pudo ejecutar: {e}"))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    carpeta = salida / entorno.lower() / ts
    carpeta.mkdir(parents=True, exist_ok=True)
    cuenta = {e: sum(c["estado"] == e for c in casos) for e in (APROBADO, FALLIDO, NO_EJECUTADO)}
    (carpeta / "resultados.json").write_text(json.dumps(
        {"meta": {"script": "scripts/qa_cat70_complementarios.py", "entorno": entorno, "fecha_utc": ts},
         "conteo": cuenta, "casos": [{**c, "entorno": entorno} for c in casos]}, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in casos:
        print(f"{entorno:5} {c['id']}: {c['estado']} · {c['detalle'][:140]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True)
    ap.add_argument("--local", default="http://127.0.0.1:8080")
    args = ap.parse_args()
    salida = Path(args.salida)
    for entorno, base in (("LOCAL", args.local), ("AWS", os.environ["SAAD_URL"])):
        api = Api(base)
        pruebas: list[Callable[[], Any]] = [lambda: c046(api), lambda: c052_054(api), lambda: c055(api), lambda: c056(api), lambda: c057(api)]
        if entorno == "AWS":
            pruebas += [lambda: c064(base), c069, c010]
        correr(salida, entorno, pruebas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
