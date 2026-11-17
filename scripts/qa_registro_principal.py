"""Genera el registro principal de pruebas del catálogo SAAD-CP v2.1 (200 casos).

Lee todos los archivos resultados.json rastreados por Git en
reports/validation/ciclos_pruebas/ y construye un registro unificado.

Regla de consolidación: por cada caso y cada categoría de entorno
(FIXTURE / LOCAL / AWS), conserva el último resultado *ejecutado*
(APROBADO o FALLIDO). Un NO EJECUTADO posterior nunca oculta un resultado.

Salidas:
  reports/validation/registro_principal_pruebas.md
  reports/validation/registro_principal_pruebas.csv
  docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx

Uso:
    .venv/bin/python scripts/qa_registro_principal.py [--raiz RAIZ] [--sin-enlaces]
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

RAIZ: Final[Path] = Path(__file__).resolve().parents[1]
SALIDA_MD: Final[Path] = RAIZ / "reports/validation/registro_principal_pruebas.md"
SALIDA_CSV: Final[Path] = RAIZ / "reports/validation/registro_principal_pruebas.csv"
SALIDA_XLSX: Final[Path] = (
    RAIZ / "docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx"
)
CICLOS_BASE: Final[Path] = RAIZ / "reports/validation/ciclos_pruebas"

# IDs del catálogo CAT70 sin equivalente en el catálogo de 200 casos
CAT70_EXCLUSIVOS: Final[frozenset[str]] = frozenset({
    "CP-SAAD-010", "CP-SAAD-011", "CP-SAAD-012", "CP-SAAD-014", "CP-SAAD-015",
    "CP-SAAD-016", "CP-SAAD-025", "CP-SAAD-046", "CP-SAAD-052", "CP-SAAD-054",
    "CP-SAAD-055", "CP-SAAD-056", "CP-SAAD-057", "CP-SAAD-063", "CP-SAAD-064",
    "CP-SAAD-065", "CP-SAAD-069",
})

# Casos que no se pueden ejecutar en el ciclo final y su motivo
NO_EJECUTABLES: Final[dict[str, str]] = {
    "SAAD-CP-009": "Requiere usuario piloto institucional (#90 sin cerrar)",
    "SAAD-CP-037": "Requiere usuario piloto institucional (#90 sin cerrar)",
    "SAAD-CP-046": "Requiere usuario piloto institucional (#90 sin cerrar)",
    "SAAD-CP-074": "Requiere WebKit (solo Chrome y Firefox instalados)",
    "SAAD-CP-078": "Requiere usuario piloto institucional (#90 sin cerrar)",
    "SAAD-CP-079": "Sesión exploratoria de 30 min; requiere coordinación con cliente",
    "SAAD-CP-080": "Requiere usuario piloto institucional (#90 sin cerrar)",
}


# Carpetas de ciclo que son duplicados no canónicos y deben excluirse del registro.
_CICLOS_EXCLUIDOS: Final[frozenset[str]] = frozenset({
    "ciclo_02_20261112T142133Z",
    "ciclo_03_20261112T152058Z",
})


def _archivos_rastreados(raiz: Path = RAIZ) -> set[Path]:
    """Devuelve los paths de resultados.json válidos bajo CICLOS_BASE.

    Incluye tanto los rastreados por Git como los que ya existen en disco pero
    aún no están commiteados (p. ej. el ciclo actual), excepto los duplicados
    listados en _CICLOS_EXCLUIDOS.
    """
    ciclos_base = raiz / "reports/validation/ciclos_pruebas"
    try:
        # Primero los rastreados por Git
        out = subprocess.check_output(
            ["git", "ls-files", str(ciclos_base)], cwd=raiz, text=True
        )
        rastreados = {raiz / p for p in out.splitlines() if p.endswith("resultados.json")}
    except subprocess.CalledProcessError:
        rastreados = set()
    # Incluye además los no-commiteados que no estén en la lista de excluidos
    for ciclo_dir in ciclos_base.iterdir():
        if not ciclo_dir.is_dir():
            continue
        if ciclo_dir.name in _CICLOS_EXCLUIDOS:
            continue
        for json_path in ciclo_dir.glob("**/resultados.json"):
            rastreados.add(json_path)
    return rastreados


def _categoria_entorno(entorno: str, subcarpeta: str) -> str:
    """Normaliza el entorno a FIXTURE / LOCAL / AWS."""
    sub = subcarpeta.lower()
    if "aws" in sub:
        return "AWS"
    if "local" in sub:
        return "LOCAL"
    env = entorno.upper()
    if "FIXTURE" in env or "PYTEST" in env:
        return "FIXTURE"
    if "LOCAL" in env:
        return "LOCAL"
    if "AWS" in env:
        return "AWS"
    return entorno


def _ciclo_numero(ciclo_dir: str) -> int:
    """Extrae el número de ciclo del nombre de la carpeta (p. ej. 'ciclo_17_...' → 17)."""
    try:
        return int(ciclo_dir.split("_")[1])
    except (IndexError, ValueError):
        return 0


def cargar_resultados_200(raiz: Path = RAIZ) -> dict[str, dict[str, dict[str, Any]]]:
    """Lee todos los catalogo_200* resultados.json rastreados.

    Devuelve {case_id: {categoria_entorno: registro_del_caso}}.
    La regla es: último ejecutado por (caso, entorno); NO EJECUTADO no reemplaza.
    """
    rastreados = _archivos_rastreados(raiz)
    ciclos_base = raiz / "reports/validation/ciclos_pruebas"
    patron = "ciclo_*/catalogo_200*/resultados.json"
    archivos = sorted(ciclos_base.glob(patron))

    # (ciclo_numero, timestamp_carpeta) → orden cronológico
    def _orden(p: Path) -> tuple[int, str]:
        ciclo_dir = p.parts[-3]  # ciclo_17_20261117T140040Z
        subcarpeta = p.parts[-2]  # catalogo_200_aws
        return (_ciclo_numero(ciclo_dir), ciclo_dir, subcarpeta)

    archivos.sort(key=_orden)

    mejor: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for archivo in archivos:
        if archivo not in rastreados:
            # Excluye los duplicados no rastreados (ciclo_02/ciclo_03 extra)
            continue
        ciclo_dir = archivo.parent.parent.name  # ciclo_17_20261117T140040Z
        subcarpeta = archivo.parent.name         # catalogo_200_aws
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        casos = datos.get("casos", [])
        for caso in casos:
            cid = caso.get("id", "")
            if not cid.startswith("SAAD-CP-"):
                continue
            cat = _categoria_entorno(caso.get("entorno", ""), subcarpeta)
            estado = caso.get("estado", "")
            ya = mejor[cid].get(cat)
            if estado in ("APROBADO", "FALLIDO"):
                mejor[cid][cat] = {
                    **caso,
                    "_ciclo_dir": ciclo_dir,
                    "_subcarpeta": subcarpeta,
                    "_entorno_cat": cat,
                }
            elif ya is None:
                # Solo guarda NO EJECUTADO si no hay nada todavía
                mejor[cid][cat] = {
                    **caso,
                    "_ciclo_dir": ciclo_dir,
                    "_subcarpeta": subcarpeta,
                    "_entorno_cat": cat,
                }
    return mejor


def cargar_resultados_cat70(raiz: Path = RAIZ) -> dict[str, dict[str, dict[str, Any]]]:
    """Lee resultados del catálogo CAT70 (IDs CP-SAAD-NNN) para los 17 exclusivos."""
    rastreados = _archivos_rastreados(raiz)
    ciclos_base = raiz / "reports/validation/ciclos_pruebas"
    patron = "ciclo_*/*/*/resultados.json"
    archivos = sorted(ciclos_base.glob(patron))

    def _orden(p: Path) -> tuple[int, str, str]:
        ciclo_dir = p.parts[-4]
        env_dir = p.parts[-3]
        ts_dir = p.parts[-2]
        return (_ciclo_numero(ciclo_dir), ciclo_dir, ts_dir)

    archivos.sort(key=_orden)

    mejor: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for archivo in archivos:
        if archivo not in rastreados:
            continue
        ciclo_dir = archivo.parts[-4]
        env_dir = archivo.parts[-3]  # local | aws
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        casos = datos.get("casos", [])
        for caso in casos:
            cid = caso.get("id", "")
            if cid not in CAT70_EXCLUSIVOS:
                continue
            cat = "LOCAL" if env_dir.lower() == "local" else "AWS"
            estado = caso.get("estado", "")
            ya = mejor[cid].get(cat)
            if estado in ("APROBADO", "FALLIDO"):
                mejor[cid][cat] = {
                    **caso,
                    "_ciclo_dir": ciclo_dir,
                    "_entorno_cat": cat,
                }
            elif ya is None:
                mejor[cid][cat] = {
                    **caso,
                    "_ciclo_dir": ciclo_dir,
                    "_entorno_cat": cat,
                }
    return mejor


def estado_global(entornos: dict[str, dict[str, Any]]) -> str:
    """FALLIDO si algún entorno falló; APROBADO si al menos uno aprobó; si no, NO EJECUTADO."""
    estados = [v.get("estado", "") for v in entornos.values()]
    if "FALLIDO" in estados:
        return "FALLIDO"
    if "APROBADO" in estados:
        return "APROBADO"
    return "NO EJECUTADO"


def _enlace_evidencia(caso: dict[str, Any], raiz: Path = RAIZ) -> str:
    """Devuelve un enlace Markdown relativo a la evidencia, o vacío si no hay."""
    evidencia = caso.get("evidencia")
    if not evidencia:
        return ""
    ciclo_dir = caso.get("_ciclo_dir", "")
    subcarpeta = caso.get("_subcarpeta", "")
    ruta = Path(f"reports/validation/ciclos_pruebas/{ciclo_dir}/{subcarpeta}/{evidencia}")
    abs_ruta = raiz / ruta
    if abs_ruta.exists():
        return f"[evidencia]({ruta.as_posix()})"
    # Intentar con Path.stem si tiene extensión adicional
    for ext in (".json", ".png", ".md"):
        alt = abs_ruta.with_suffix(ext)
        if alt.exists():
            return f"[evidencia]({ruta.with_suffix(ext).as_posix()})"
    return f"[evidencia (falta)]({ruta.as_posix()})"


def _ciclo_link(caso: dict[str, Any]) -> str:
    ciclo_dir = caso.get("_ciclo_dir", "")
    if not ciclo_dir:
        return ""
    num = ciclo_dir.split("_")[1] if "_" in ciclo_dir else ""
    return f"[{num}](reports/validation/ciclos_pruebas/{ciclo_dir}/)"


def verificar_enlaces(resultados: dict[str, dict[str, dict[str, Any]]], raiz: Path = RAIZ) -> list[str]:
    """Devuelve la lista de evidencias que no existen en disco."""
    problemas = []
    for cid, entornos in resultados.items():
        for cat, caso in entornos.items():
            evidencia = caso.get("evidencia")
            if not evidencia:
                continue
            ciclo_dir = caso.get("_ciclo_dir", "")
            subcarpeta = caso.get("_subcarpeta", "")
            ruta = raiz / f"reports/validation/ciclos_pruebas/{ciclo_dir}/{subcarpeta}/{evidencia}"
            if not ruta.exists():
                problemas.append(f"{cid} [{cat}]: evidencia no encontrada: {ruta.relative_to(raiz).as_posix()}")
    return problemas


def generar_md(
    resultados_200: dict[str, dict[str, dict[str, Any]]],
    resultados_cat70: dict[str, dict[str, dict[str, Any]]],
    raiz: Path = RAIZ,
) -> str:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ids_200 = [f"SAAD-CP-{n:03d}" for n in range(1, 201)]

    # Conteos
    global_estados = {cid: estado_global(resultados_200.get(cid, {})) for cid in ids_200}
    n_aprobado = sum(1 for e in global_estados.values() if e == "APROBADO")
    n_fallido = sum(1 for e in global_estados.values() if e == "FALLIDO")
    n_no_ej = sum(1 for e in global_estados.values() if e == "NO EJECUTADO")

    lineas = [
        "# Registro principal de pruebas — SAAD-CP v2.1",
        "",
        f"> Generado el {ahora}. Los 200 casos del catálogo se consolidan aquí; "
        "para cada caso se conserva el último resultado ejecutado por entorno.",
        "",
        "## Resumen ejecutivo",
        "",
        f"| Estado | Casos |",
        f"|---|---|",
        f"| APROBADO | {n_aprobado} |",
        f"| FALLIDO | {n_fallido} |",
        f"| NO EJECUTADO | {n_no_ej} |",
        f"| **Total** | **200** |",
        "",
        "## Matriz de pruebas — catálogo de 200 casos",
        "",
        "| ID | Título | Módulo | Estado global | FIXTURE | LOCAL | AWS | Ciclo | Defecto | Evidencia |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for cid in ids_200:
        entornos = resultados_200.get(cid, {})
        eg = global_estados[cid]
        # Mejor ciclo (el más reciente con resultado ejecutado)
        ciclo_txt = ""
        defecto_txt = ""
        evidencia_txt = ""
        for cat_pref in ("AWS", "LOCAL", "FIXTURE"):
            caso = entornos.get(cat_pref)
            if caso and caso.get("estado") in ("APROBADO", "FALLIDO"):
                ciclo_txt = _ciclo_link(caso)
                defecto_txt = caso.get("defecto", "") or ""
                evidencia_txt = _enlace_evidencia(caso, raiz)
                break

        # Estado por entorno
        def _st(cat: str) -> str:
            c = entornos.get(cat)
            if not c:
                return "—"
            st = c.get("estado", "")
            if st == "APROBADO":
                return "✓"
            if st == "FALLIDO":
                return "✗"
            return "—"

        titulo = ""
        for cat in ("FIXTURE", "LOCAL", "AWS"):
            if cat in entornos:
                titulo = entornos[cat].get("titulo", "")
                break

        modulo = ""
        for cat in ("FIXTURE", "LOCAL", "AWS"):
            if cat in entornos:
                modulo = entornos[cat].get("modulo", "")
                break

        defecto_limpio = defecto_txt.replace("Sin defecto registrado", "").strip()

        lineas.append(
            f"| {cid} | {titulo} | {modulo} | {eg} | {_st('FIXTURE')} | {_st('LOCAL')} | {_st('AWS')} "
            f"| {ciclo_txt} | {defecto_limpio} | {evidencia_txt} |"
        )

    # Casos no ejecutables
    lineas += [
        "",
        "### Casos no ejecutados en el ciclo final",
        "",
        "| ID | Motivo |",
        "|---|---|",
    ]
    for cid, motivo in NO_EJECUTABLES.items():
        lineas.append(f"| {cid} | {motivo} |")

    # Pruebas complementarias CAT70
    lineas += [
        "",
        "## Pruebas complementarias — catálogo CAT70 (casos sin equivalente en 200)",
        "",
        "Los 17 casos del catálogo CP-SAAD (70 casos) que no tienen equivalente en el catálogo "
        "de 200 casos. Se mantienen con sus IDs originales `CP-SAAD-NNN`.",
        "",
        "| ID | Nombre | Estado LOCAL | Estado AWS | Ciclo | Evidencia |",
        "|---|---|---|---|---|---|",
    ]
    for cid in sorted(CAT70_EXCLUSIVOS):
        entornos = resultados_cat70.get(cid, {})

        def _st70(cat: str) -> str:
            c = entornos.get(cat)
            if not c:
                return "—"
            st = c.get("estado", "")
            if st == "APROBADO":
                return "✓ APROBADO"
            if st == "FALLIDO":
                return "✗ FALLIDO"
            return "— NO EJECUTADO"

        nombre = ""
        ciclo70 = ""
        ev70 = ""
        for cat in ("LOCAL", "AWS"):
            caso = entornos.get(cat)
            if caso:
                nombre = caso.get("nombre", cid)
                ciclo70 = _ciclo_link(caso)
                break

        lineas.append(f"| {cid} | {nombre} | {_st70('LOCAL')} | {_st70('AWS')} | {ciclo70} | {ev70} |")

    # Leyenda
    lineas += [
        "",
        "## Leyenda",
        "",
        "| Símbolo | Significado |",
        "|---|---|",
        "| ✓ | APROBADO en ese entorno |",
        "| ✗ | FALLIDO en ese entorno |",
        "| — | No ejecutado o no aplica para ese entorno |",
        "",
        "**Esquemas de ID:**",
        "- `SAAD-CP-NNN` — catálogo de 200 casos (SAAD-CP v2.1, 2026).",
        "- `CP-SAAD-NNN` — catálogo original de 70 casos. Los 17 listados no tienen equivalente en el de 200.",
        "",
        "**Entornos:**",
        "- **FIXTURE** — pytest con `tmp_path`/`monkeypatch`, sin red ni datos reales.",
        "- **LOCAL** — API local (Uvicorn 127.0.0.1) o HTTP contra Docker Compose.",
        "- **AWS** — URL desplegada en CloudFront/ECS (host redactado en evidencias).",
        "",
        "Ver [registro de defectos](ciclos_pruebas/registro_defectos.md) para el detalle de cada defecto.",
    ]

    return "\n".join(lineas) + "\n"


def generar_filas_csv(
    resultados_200: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, str]]:
    ids_200 = [f"SAAD-CP-{n:03d}" for n in range(1, 201)]
    filas = []
    for cid in ids_200:
        entornos = resultados_200.get(cid, {})
        eg = estado_global(entornos)
        titulo = modulo = ""
        for cat in ("FIXTURE", "LOCAL", "AWS"):
            if cat in entornos:
                titulo = entornos[cat].get("titulo", "")
                modulo = entornos[cat].get("modulo", "")
                break

        def _st(cat: str) -> str:
            c = entornos.get(cat)
            return c.get("estado", "NO EJECUTADO") if c else "NO EJECUTADO"

        def _ciclo(cat: str) -> str:
            c = entornos.get(cat)
            return c.get("_ciclo_dir", "").split("_")[1] if c and "_ciclo_dir" in c else ""

        filas.append({
            "id": cid,
            "titulo": titulo,
            "modulo": modulo,
            "estado_global": eg,
            "estado_fixture": _st("FIXTURE"),
            "estado_local": _st("LOCAL"),
            "estado_aws": _st("AWS"),
            "ciclo_fixture": _ciclo("FIXTURE"),
            "ciclo_local": _ciclo("LOCAL"),
            "ciclo_aws": _ciclo("AWS"),
        })
    return filas


def escribir_csv(filas: list[dict[str, str]], ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)


def escribir_xlsx(
    resultados_200: dict[str, dict[str, dict[str, Any]]],
    resultados_cat70: dict[str, dict[str, dict[str, Any]]],
    ruta: Path,
) -> None:
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("openpyxl no instalado; se omite el .xlsx", file=sys.stderr)
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Registro 200 casos"

    VERDE = PatternFill("solid", fgColor="C6EFCE")
    ROJO = PatternFill("solid", fgColor="FFC7CE")
    GRIS = PatternFill("solid", fgColor="EDEDED")
    CABECERA = PatternFill("solid", fgColor="2F4F8F")
    CABECERA_FONT = Font(bold=True, color="FFFFFF")

    cabeceras = ["ID", "Título", "Módulo", "Estado Global", "FIXTURE", "LOCAL", "AWS",
                 "Ciclo", "Defecto", "Resultado real (AWS o LOCAL)"]
    ws.append(cabeceras)
    for cell in ws[1]:
        cell.fill = CABECERA
        cell.font = CABECERA_FONT
        cell.alignment = Alignment(horizontal="center")

    ids_200 = [f"SAAD-CP-{n:03d}" for n in range(1, 201)]
    for cid in ids_200:
        entornos = resultados_200.get(cid, {})
        eg = estado_global(entornos)
        titulo = modulo = resultado_real = ciclo_txt = defecto = ""
        for cat in ("AWS", "LOCAL", "FIXTURE"):
            if cat in entornos:
                titulo = entornos[cat].get("titulo", "")
                modulo = entornos[cat].get("modulo", "")
                if entornos[cat].get("estado") in ("APROBADO", "FALLIDO"):
                    resultado_real = entornos[cat].get("resultado_real", "")
                    ciclo_txt = entornos[cat].get("_ciclo_dir", "").split("_")[1]
                    defecto = entornos[cat].get("defecto", "") or ""
                    defecto = defecto.replace("Sin defecto registrado", "").strip()
                break

        def _st(cat: str) -> str:
            c = entornos.get(cat)
            return c.get("estado", "NO EJECUTADO") if c else "NO EJECUTADO"

        fila = [cid, titulo, modulo, eg, _st("FIXTURE"), _st("LOCAL"), _st("AWS"),
                ciclo_txt, defecto, resultado_real]
        ws.append(fila)
        row = ws.max_row
        fill = VERDE if eg == "APROBADO" else (ROJO if eg == "FALLIDO" else GRIS)
        ws.cell(row, 4).fill = fill

    # Ajustar anchos
    for i, ancho in enumerate([12, 50, 20, 15, 12, 12, 12, 8, 30, 50], 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = ancho

    # Hoja CAT70
    ws2 = wb.create_sheet("CAT70 exclusivos")
    ws2.append(["ID", "Nombre", "Estado LOCAL", "Estado AWS", "Ciclo"])
    for cell in ws2[1]:
        cell.fill = CABECERA
        cell.font = CABECERA_FONT
    for cid in sorted(CAT70_EXCLUSIVOS):
        entornos = resultados_cat70.get(cid, {})
        nombre = ciclo70 = ""
        for cat in ("LOCAL", "AWS"):
            caso = entornos.get(cat)
            if caso:
                nombre = caso.get("nombre", cid)
                ciclo70 = caso.get("_ciclo_dir", "").split("_")[1]
                break

        def _st70(cat: str) -> str:
            c = entornos.get(cat)
            return c.get("estado", "NO EJECUTADO") if c else "NO EJECUTADO"

        ws2.append([cid, nombre, _st70("LOCAL"), _st70("AWS"), ciclo70])

    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", default=str(RAIZ), help="Raíz del repositorio")
    parser.add_argument("--sin-enlaces", action="store_true",
                        help="No verifica que los enlaces de evidencia existan")
    args = parser.parse_args(argv)
    raiz = Path(args.raiz)

    print("Cargando resultados del catálogo de 200 casos…")
    r200 = cargar_resultados_200(raiz)
    print(f"  {len(r200)} casos con al menos un resultado.")

    print("Cargando resultados CAT70 exclusivos…")
    r70 = cargar_resultados_cat70(raiz)
    print(f"  {len(r70)} de {len(CAT70_EXCLUSIVOS)} casos CAT70 exclusivos con resultado.")

    if not args.sin_enlaces:
        problemas = verificar_enlaces(r200, raiz)
        if problemas:
            print("Evidencias faltantes:", file=sys.stderr)
            for p in problemas:
                print(f"  - {p}", file=sys.stderr)
            # No aborta: continúa generando el registro con los datos disponibles

    ids_200 = [f"SAAD-CP-{n:03d}" for n in range(1, 201)]
    estados = {cid: estado_global(r200.get(cid, {})) for cid in ids_200}
    n_a = sum(1 for e in estados.values() if e == "APROBADO")
    n_f = sum(1 for e in estados.values() if e == "FALLIDO")
    n_ne = sum(1 for e in estados.values() if e == "NO EJECUTADO")
    print(f"Estado global: {n_a} APROBADO, {n_f} FALLIDO, {n_ne} NO EJECUTADO de 200.")

    md = generar_md(r200, r70, raiz)
    out_md = raiz / "reports/validation/registro_principal_pruebas.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    print(f"  Markdown: {out_md.relative_to(raiz)}")

    filas = generar_filas_csv(r200)
    out_csv = raiz / "reports/validation/registro_principal_pruebas.csv"
    escribir_csv(filas, out_csv)
    print(f"  CSV: {out_csv.relative_to(raiz)}")

    out_xlsx = raiz / "docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx"
    escribir_xlsx(r200, r70, out_xlsx)
    print(f"  XLSX: {out_xlsx.relative_to(raiz)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
