"""Pruebas del ejecutor de casos del catálogo SAAD-CP v2.1 (`scripts/qa_campana_200.py`)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import docx
import pytest

from scripts import qa_campana_200 as q

AHORA = datetime(2026, 11, 14, 20, 0, 0, tzinfo=timezone.utc)


def _catalogo(ruta: Path) -> Path:
    d = docx.Document()
    d.add_heading("SAAD-CP-001  Caso automatizado", level=1)
    d.add_paragraph("Módulo  Navegación   ·   R07")
    d.add_paragraph("Entorno  Local aislado con fixtures de repositorio")
    d.add_paragraph("Procedimiento")
    d.add_paragraph("1. Revisar el selector.")
    d.add_paragraph("2. Ejecutar python -m pytest tests/test_x.py::test_a -q --junitxml=EVIDENCIA/SAAD-CP-001.xml; "
                    "crear EVIDENCIA dentro de la carpeta del run.")
    d.add_heading("SAAD-CP-002  Caso manual", level=1)
    d.add_paragraph("Módulo  Tablero comunal   ·   R04")
    d.add_paragraph("Entorno  AWS existente o local con mismo snapshot")
    d.add_paragraph("Procedimiento")
    d.add_paragraph("2. Abrir el navegador y comparar la selección.")
    d.add_heading("SAAD-CP-003  Parámetro inválido", level=1)
    d.add_paragraph("Módulo  Contratos HTTP   ·   R04")
    d.add_paragraph("Entorno  AWS existente o local con mismo snapshot")
    d.add_paragraph("2. GET /caracterizacion/urgencias/comuna/05101?semanas=2025-1.")
    d.add_paragraph("Resultado esperado  HTTP 404 informa que la comuna no pertenece a RM")
    d.add_heading("SAAD-CP-004  Límite del calendario", level=1)
    d.add_paragraph("Módulo  Suicidios y calendario   ·   R03")
    d.add_paragraph("Entorno  Local aislado")
    d.add_paragraph("2. En local consultar desde=2020-01-01 con hasta=desde+4392 días y luego +4393 días calculados por datetime.")
    d.add_paragraph("Resultado esperado  4392 días no se rechazan por longitud; 4393 devuelve 422 por MAX_DIAS")
    d.save(str(ruta))
    return ruta


def _junit(ruta: Path, tests: int = 1, failures: int = 0, skipped: int = 0) -> None:
    casos = "".join(f'<testcase classname="tests.test_x" name="test_a[{i}]"/>' for i in range(tests))
    ruta.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{tests}" failures="{failures}" '
        f'errors="0" skipped="{skipped}">{casos}</testsuite></testsuites>', encoding="utf-8")


@pytest.fixture(autouse=True)
def _sin_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(q, "git", lambda *a: "abc123" if a[:1] == ("rev-parse",) else "")


def _falso_pytest(monkeypatch: pytest.MonkeyPatch, codigo: int = 0, **junit: int) -> None:
    def falso(selector: str, xml: Path) -> tuple[int, str]:
        _junit(xml, **junit)
        return codigo, "ok"
    monkeypatch.setattr(q, "correr_pytest", falso)


def test_parsear_casos_rangos_sin_repetidos() -> None:
    assert q.parsear_casos("081-083, 090,082") == ["081", "082", "083", "090"]


@pytest.mark.parametrize("texto", ["010-005", "0", "201", "200-201"])
def test_parsear_casos_rechaza_rangos_invalidos(texto: str) -> None:
    with pytest.raises(ValueError):
        q.parsear_casos(texto)


def test_leer_catalogo_extrae_selector_y_marca_el_manual(tmp_path: Path) -> None:
    c = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))
    assert c["001"]["selector"] == "tests/test_x.py::test_a"
    assert (c["001"]["titulo"], c["001"]["modulo"]) == ("Caso automatizado", "Navegación")
    assert c["002"]["selector"] is None and c["002"]["entorno"].startswith("AWS")


def test_carpeta_ciclo_reutiliza_la_existente(tmp_path: Path) -> None:
    existente = tmp_path / "ciclo_05_20261101T000000Z"
    existente.mkdir()
    assert q.carpeta_ciclo(tmp_path, 5, AHORA) == existente
    assert q.carpeta_ciclo(tmp_path, 6, AHORA).name == "ciclo_06_20261114T200000Z"


def test_caso_aprobado_registra_los_campos_del_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falso_pytest(monkeypatch, tests=3)
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["001"]
    r = q.ejecutar_caso("001", info, {"run_id": "ciclo_05/catalogo_200", "ejecutor": "Ana Pérez", "sha": "abc123"},
                        ev, "20261114")
    assert r["estado"] == q.APROBADO and r["ejecutor_real"] == "Ana Pérez" and r["sha"] == "abc123"
    assert r["evidencia"] == "EVIDENCIA/SAAD-CP-001_20261114_fixture.xml" and (ev / Path(r["evidencia"]).name).exists()
    assert len(r["evidencia_sha256"]) == 64 and r["defecto"] == "Sin defecto registrado"
    assert r["hash_input"] == {"archivo": "tests/test_x.py", "git_blob": "abc123"}
    assert "3 instancias" in r["resultado_real"] and r["fecha_hora_utc"]["inicio"] <= r["fecha_hora_utc"]["fin"]


@pytest.mark.parametrize(("codigo", "junit"), [
    (1, {"failures": 1}),   # un fallo
    (0, {"skipped": 1}),    # omitido: no cuenta como aprobado
    (0, {"tests": 0}),      # sin instancias
    (1, {}),                # exit code distinto de cero
])
def test_caso_no_aprobado_si_falla_se_omite_o_no_corre(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, codigo: int, junit: dict[str, int]) -> None:
    _falso_pytest(monkeypatch, codigo, **junit)
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["001"]
    r = q.ejecutar_caso("001", info, {"run_id": "x", "ejecutor": "A", "sha": "s"}, ev, "20261114")
    assert r["estado"] == q.FALLIDO and "salida_cola" in r


def test_caso_sin_selector_queda_no_ejecutado_con_motivo(tmp_path: Path) -> None:
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["002"]
    r = q.ejecutar_caso("002", info, {"run_id": "x", "ejecutor": "A", "sha": "s"}, tmp_path, "20261114")
    assert r["estado"] == q.NO_EJECUTADO and r["evidencia"] is None and "interfaz" in r["observaciones"]


def test_main_escribe_resultados_y_no_sobrescribe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falso_pytest(monkeypatch, tests=2)
    cat = _catalogo(tmp_path / "c.docx")
    base = tmp_path / "ciclos"
    otro = base / "ciclo_05_20261101T000000Z"
    otro.mkdir(parents=True)
    (otro / "resumen.md").write_text("de otro", encoding="utf-8")
    argv = ["--ciclo", "5", "--ejecutor", "Ana Pérez", "--casos", "001-002", "--catalogo", str(cat),
            "--salida", str(base)]
    assert q.main(argv) == 0
    destino = otro / "catalogo_200"
    meta = json.loads((destino / "resultados.json").read_text(encoding="utf-8"))
    assert meta["resumen"] == {"aprobados": 1, "fallidos": 0, "no_ejecutados": 1}
    assert meta["ejecutor_real"] == "Ana Pérez" and meta["alcance"] == "2 casos"
    assert "Ana Pérez" in (destino / "resultados.md").read_text(encoding="utf-8")
    assert (otro / "resumen.md").read_text(encoding="utf-8") == "de otro"   # no toca lo ajeno
    with pytest.raises(SystemExit):                                           # repetir exige otro ciclo
        q.main(argv)


def test_main_rechaza_casos_ajenos_al_catalogo(tmp_path: Path) -> None:
    cat = _catalogo(tmp_path / "c.docx")
    with pytest.raises(SystemExit):
        q.main(["--ciclo", "5", "--ejecutor", "A", "--casos", "150", "--catalogo", str(cat),
                "--salida", str(tmp_path / "ciclos")])
    assert not (tmp_path / "ciclos").exists()


def test_main_devuelve_error_si_algun_caso_falla(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falso_pytest(monkeypatch, 1, failures=1)
    cat = _catalogo(tmp_path / "c.docx")
    assert q.main(["--ciclo", "5", "--ejecutor", "A", "--casos", "001", "--catalogo", str(cat),
                   "--salida", str(tmp_path / "ciclos")]) == 1


# --------------------------------------------------------------------------
# Modo HTTP
# --------------------------------------------------------------------------

def _falsa_api(monkeypatch: pytest.MonkeyPatch, codigos: dict[str, int], meta_ok: bool = True) -> list[str]:
    llamadas: list[str] = []

    def falso(url_base: str, ruta: str, timeout: int = 60) -> dict[str, object]:
        llamadas.append(ruta)
        if ruta == "/meta":
            cuerpo = json.dumps({"ultima_semana_observada": {"fecha_inicio": "2026-11-01"},
                                 "pronostico_calculado_en": "2026-11-12T14:53:07Z", "origen_pronostico": "persistido"})
            return {"url": url_base + "/api/v1/meta", "codigo": 200 if meta_ok else 503, "cabeceras": {},
                    "cuerpo": cuerpo, "inicio": "t0", "fin": "t1"}
        codigo = next((c for k, c in codigos.items() if k in ruta), 200)
        return {"url": url_base + "/api/v1" + ruta, "codigo": codigo, "cabeceras": {}, "cuerpo": "{}",
                "inicio": "t0", "fin": "t1"}
    monkeypatch.setattr(q, "consultar", falso)
    return llamadas


def test_peticiones_http_simple_y_rango_y_no_soportado() -> None:
    assert q.peticiones_http("2. GET /a/b?x=1.", "HTTP 422 informa algo") == [{"ruta": "/a/b?x=1", "esperado": 422}]  # sin el punto final
    rango = q.peticiones_http("2. En local consultar desde=2020-01-01 con hasta=desde+4392 días y luego +4393 días",
                              "4392 no se rechazan")
    assert [p["esperado"] for p in rango] == [200, 422]
    assert [p["ruta"] for p in rango] == [
        "/calendario-eventos?desde=2020-01-01&hasta=2032-01-10",   # 2020-01-01 + 4392 días
        "/calendario-eventos?desde=2020-01-01&hasta=2032-01-11",   # + 4393 días
    ]
    assert q.peticiones_http("2. Abrir el navegador", "algo") == [] and q.peticiones_http(None, "") == []


def test_entorno_http_distingue_local_de_aws() -> None:
    assert q.entorno_http("http://127.0.0.1:8000")[1] == "local"
    assert q.entorno_http("http://localhost:8000")[1] == "local"
    assert q.entorno_http("https://algo.cloudfront.net")[1] == "aws"


def test_caso_http_aprobado_si_el_codigo_coincide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falsa_api(monkeypatch, {"05101": 404})
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["003"]
    snapshot, meta = q.snapshot_http("http://127.0.0.1:8000")
    assert "2026-11-01" in snapshot and "persistido" in snapshot
    ctx = {"run_id": "x", "ejecutor": "A", "sha": "s", "url_base": "http://127.0.0.1:8000", "sufijo": "local",
           "entorno": q.ENTORNO_LOCAL, "snapshot": snapshot, "nota": "bandera X", "estado_inicial": {"meta": meta}}
    r = q.ejecutar_caso_http("003", info, ctx, ev, "20261114")
    assert r["estado"] == q.APROBADO and r["evidencia"] == "EVIDENCIA/SAAD-CP-003_20261114_local.json"
    assert r["peticiones"] == [{"ruta": "/caracterizacion/urgencias/comuna/05101?semanas=2025-1",
                                "esperado": 404, "obtenido": 404}]
    guardado = json.loads((ev / "SAAD-CP-003_20261114_local.json").read_text(encoding="utf-8"))
    assert guardado["peticiones"][0]["respuesta"]["codigo"] == 404 and r["observaciones"] == "bandera X"


def test_caso_http_fallido_si_el_codigo_difiere_o_no_responde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["003"]
    ctx = {"run_id": "x", "ejecutor": "A", "sha": "s", "url_base": "http://127.0.0.1:8000", "sufijo": "local",
           "entorno": q.ENTORNO_LOCAL, "snapshot": "s", "nota": "", "estado_inicial": {}}
    _falsa_api(monkeypatch, {"05101": 200})
    assert q.ejecutar_caso_http("003", info, ctx, ev, "20261114")["estado"] == q.FALLIDO
    monkeypatch.setattr(q, "consultar", lambda *a, **k: {"url": "u", "codigo": None, "error": "x", "cuerpo": "",
                                                          "cabeceras": {}, "inicio": "t0", "fin": "t1"})
    r = q.ejecutar_caso_http("003", info, ctx, ev, "20261114")
    assert r["estado"] == q.FALLIDO and "sin respuesta" in r["resultado_real"]


def test_caso_http_aws_redacta_la_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falsa_api(monkeypatch, {"05101": 404})
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["003"]
    ctx = {"run_id": "x", "ejecutor": "A", "sha": "s", "url_base": "https://secreto.cloudfront.net", "sufijo": "aws",
           "entorno": q.ENTORNO_AWS, "snapshot": "s", "nota": "", "estado_inicial": {}}
    q.ejecutar_caso_http("003", info, ctx, ev, "20261114")
    texto = (ev / "SAAD-CP-003_20261114_aws.json").read_text(encoding="utf-8")
    assert "secreto.cloudfront.net" not in texto and "<url-base>" in texto


def test_main_modo_http_registra_resultados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas = _falsa_api(monkeypatch, {"05101": 404, "hasta=2032-01-11": 422})
    cat = _catalogo(tmp_path / "c.docx")
    base = tmp_path / "ciclos"
    codigo = q.main(["--ciclo", "6", "--ejecutor", "Ana Pérez", "--casos", "002-004", "--modo", "http",
                     "--url-base", "http://127.0.0.1:8000", "--nota", "bandera X", "--catalogo", str(cat),
                     "--salida", str(base)])
    destino = next(base.glob("ciclo_06_*")) / "catalogo_200"
    meta = json.loads((destino / "resultados.json").read_text(encoding="utf-8"))
    estados = {c["id"]: c["estado"] for c in meta["casos"]}
    assert estados == {"SAAD-CP-002": q.NO_EJECUTADO, "SAAD-CP-003": q.APROBADO, "SAAD-CP-004": q.APROBADO}
    assert meta["modo"] == "http" and meta["entorno"] == q.ENTORNO_LOCAL and meta["nota"] == "bandera X"
    assert "/meta" in llamadas
    assert len(list((destino / "EVIDENCIA").glob("SAAD-CP-00[34]_*_local.json"))) == 2
    assert "bandera X" in (destino / "resultados.md").read_text(encoding="utf-8")
    assert codigo == 0


def test_main_http_exige_url_base(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        q.main(["--ciclo", "6", "--ejecutor", "A", "--casos", "003", "--modo", "http",
                "--catalogo", str(_catalogo(tmp_path / "c.docx")), "--salida", str(tmp_path / "ciclos")])


def test_advertencias_segun_el_modo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falsa_api(monkeypatch, {"05101": 404})
    cat = _catalogo(tmp_path / "c.docx")
    q.main(["--ciclo", "6", "--ejecutor", "A", "--casos", "003", "--modo", "http", "--url-base",
            "http://127.0.0.1:8000", "--catalogo", str(cat), "--salida", str(tmp_path / "ciclos")])
    meta = json.loads(next((tmp_path / "ciclos").glob("ciclo_06_*/catalogo_200/resultados.json")).read_text(encoding="utf-8"))
    assert any("consultas HTTP" in a for a in meta["advertencias"]) and not any("fixtures" in a for a in meta["advertencias"])


# --------------------------------------------------------------------------
# Modo manual (casos hechos con navegador u otra persona)
# --------------------------------------------------------------------------

def _entradas(tmp_path: Path) -> Path:
    anexos = tmp_path / "anexos"
    anexos.mkdir()
    (anexos / "SAAD-CP-001_20261114_aws.json").write_text('{"ok": true}', encoding="utf-8")
    (anexos / "SAAD-CP-001_20261114_aws_01.png").write_bytes(b"\x89PNG")
    ruta = anexos / "entradas.json"
    ruta.write_text(json.dumps([
        {"id": "SAAD-CP-001", "estado": "APROBADO", "inicio": "2026-11-14T20:00:00+00:00",
         "fin": "2026-11-14T20:01:00+00:00", "snapshot": {"corte": "2026-11-07"},
         "resultado_real": "Se observó X", "observaciones": "Hallazgo Y",
         "anexos": ["SAAD-CP-001_20261114_aws.json", "SAAD-CP-001_20261114_aws_01.png"],
         "hash_input": {"script_sha256": "abc"}},
        {"id": "SAAD-CP-002", "estado": "NO EJECUTADO", "resultado_real": "No ejecutado",
         "observaciones": "Requiere persona piloto"},
    ]), encoding="utf-8")
    return ruta


def test_registrar_manual_copia_anexos_con_hash(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["001"]
    entrada = json.loads(ruta.read_text(encoding="utf-8"))[0]
    ctx = {"run_id": "x", "ejecutor": "A", "entorno": q.ENTORNO_AWS, "sha": "s", "version_desplegada": q.VERSION_AWS_NO_CONFIRMADA}
    r = q.registrar_manual("001", info, entrada, ctx, ev, ruta.parent)
    assert r["estado"] == q.APROBADO and r["snapshot"] == '{"corte":"2026-11-07"}'
    assert [a["archivo"] for a in r["anexos"]] == ["EVIDENCIA/SAAD-CP-001_20261114_aws.json",
                                                    "EVIDENCIA/SAAD-CP-001_20261114_aws_01.png"]
    assert all(len(a["sha256"]) == 64 for a in r["anexos"]) and (ev / "SAAD-CP-001_20261114_aws_01.png").exists()
    assert r["evidencia_sha256"] == r["anexos"][0]["sha256"] and r["hash_input"] == {"script_sha256": "abc"}
    assert r["version_desplegada"].startswith("No confirmada") and r["defecto"] == "Sin defecto registrado"


def test_registrar_manual_rechaza_estado_invalido_y_anexo_ausente(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["001"]
    ctx = {"run_id": "x", "ejecutor": "A", "entorno": "e", "sha": "s"}
    with pytest.raises(ValueError):
        q.registrar_manual("001", info, {"estado": "OK"}, ctx, ev, ruta.parent)
    with pytest.raises(FileNotFoundError):
        q.registrar_manual("001", info, {"estado": "APROBADO", "anexos": ["no_existe.png"]}, ctx, ev, ruta.parent)


def test_registrar_manual_sin_anexos_queda_sin_evidencia(tmp_path: Path) -> None:
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["002"]
    r = q.registrar_manual("002", info, {"estado": "NO EJECUTADO", "observaciones": "Requiere persona piloto"},
                           {"run_id": "x", "ejecutor": "A", "entorno": "e", "sha": "s"}, tmp_path, tmp_path)
    assert r["estado"] == q.NO_EJECUTADO and r["evidencia"] is None and r["anexos"] == []


def test_main_modo_manual_escribe_resultados(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    cat = _catalogo(tmp_path / "c.docx")
    base = tmp_path / "ciclos"
    codigo = q.main(["--ciclo", "7", "--ejecutor", "Ana Pérez", "--casos", "001-002", "--modo", "manual",
                     "--entradas", str(ruta), "--entorno", "aws", "--catalogo", str(cat), "--salida", str(base)])
    destino = next(base.glob("ciclo_07_*")) / "catalogo_200"
    meta = json.loads((destino / "resultados.json").read_text(encoding="utf-8"))
    assert codigo == 0 and meta["resumen"] == {"aprobados": 1, "fallidos": 0, "no_ejecutados": 1}
    assert meta["entorno"] == q.ENTORNO_AWS and meta["version_desplegada"].startswith("No confirmada")
    md = (destino / "resultados.md").read_text(encoding="utf-8")
    assert "Versión desplegada" in md and "(+1 anexos" in md
    assert len(list((destino / "EVIDENCIA").iterdir())) == 2


def test_main_manual_exige_entradas_y_entorno(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        q.main(["--ciclo", "7", "--ejecutor", "A", "--casos", "001", "--modo", "manual",
                "--catalogo", str(_catalogo(tmp_path / "c.docx")), "--salida", str(tmp_path / "c")])


def test_main_manual_falla_si_falta_el_veredicto_de_un_caso(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    with pytest.raises(SystemExit):
        q.main(["--ciclo", "7", "--ejecutor", "A", "--casos", "003", "--modo", "manual", "--entradas", str(ruta),
                "--entorno", "aws", "--catalogo", str(_catalogo(tmp_path / "c.docx")), "--salida", str(tmp_path / "c")])


def test_un_fallo_no_deja_carpeta_que_bloquee_el_reintento(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    (ruta.parent / "SAAD-CP-001_20261114_aws.json").unlink()      # anexo ausente: falla a mitad de la corrida
    cat = _catalogo(tmp_path / "c.docx")
    base = tmp_path / "ciclos"
    argv = ["--ciclo", "7", "--ejecutor", "A", "--casos", "001", "--modo", "manual", "--entradas", str(ruta),
            "--entorno", "aws", "--catalogo", str(cat), "--salida", str(base)]
    with pytest.raises(FileNotFoundError):
        q.main(argv)
    assert not list(base.glob("ciclo_07_*"))                       # no queda ni la carpeta del ciclo
    (ruta.parent / "SAAD-CP-001_20261114_aws.json").write_text("{}", encoding="utf-8")
    assert q.main(argv) == 0                                       # y el reintento funciona


def test_modo_manual_usa_el_periodo_de_las_ejecuciones(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    q.main(["--ciclo", "7", "--ejecutor", "A", "--casos", "001-002", "--modo", "manual", "--entradas", str(ruta),
            "--entorno", "local", "--catalogo", str(_catalogo(tmp_path / "c.docx")), "--salida", str(tmp_path / "c")])
    meta = json.loads(next((tmp_path / "c").glob("ciclo_07_*/catalogo_200/resultados.json")).read_text(encoding="utf-8"))
    assert (meta["inicio_utc"], meta["fin_utc"]) == ("2026-11-14T20:00:00+00:00", "2026-11-14T20:01:00+00:00")


# --------------------------------------------------------------------------
# Saltos de línea: el SHA256 registrado debe coincidir en cualquier sistema
# --------------------------------------------------------------------------

def test_sha256_de_texto_no_depende_de_los_saltos_de_linea(tmp_path: Path) -> None:
    con_crlf = tmp_path / "a.json"
    con_crlf.write_bytes(b'{"x": 1}\r\n{"y": 2}\r\n')
    solo_lf = tmp_path / "b.json"
    solo_lf.write_bytes(b'{"x": 1}\n{"y": 2}\n')
    assert q.sha256(con_crlf) == q.sha256(solo_lf)
    assert con_crlf.read_bytes() == b'{"x": 1}\n{"y": 2}\n'   # y el archivo queda en LF


def test_los_binarios_no_se_modifican(tmp_path: Path) -> None:
    png = tmp_path / "c.png"
    datos = b"\x89PNG\r\n\x1a\n\x00\r\n"
    png.write_bytes(datos)
    q.sha256(png)
    assert png.read_bytes() == datos


def test_los_anexos_de_texto_se_registran_en_lf(tmp_path: Path) -> None:
    ruta = _entradas(tmp_path)
    (ruta.parent / "SAAD-CP-001_20261114_aws.json").write_bytes(b'{"ok": true}\r\n')
    ev = tmp_path / "EVIDENCIA"
    ev.mkdir()
    info = q.leer_catalogo(_catalogo(tmp_path / "c.docx"))["001"]
    entrada = json.loads(ruta.read_text(encoding="utf-8"))[0]
    r = q.registrar_manual("001", info, entrada, {"run_id": "x", "ejecutor": "A", "entorno": "e", "sha": "s"}, ev, ruta.parent)
    guardado = (ev / "SAAD-CP-001_20261114_aws.json").read_bytes()
    assert b"\r" not in guardado
    assert r["anexos"][0]["sha256"] == __import__("hashlib").sha256(guardado).hexdigest()


def test_resultados_se_escriben_con_lf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _falso_pytest(monkeypatch, tests=1)
    q.main(["--ciclo", "5", "--ejecutor", "A", "--casos", "001", "--catalogo", str(_catalogo(tmp_path / "c.docx")),
            "--salida", str(tmp_path / "c")])
    carpeta = next((tmp_path / "c").glob("ciclo_05_*/catalogo_200"))
    for nombre in ("resultados.json", "resultados.md"):
        assert b"\r" not in (carpeta / nombre).read_bytes()


def test_las_rutas_locales_y_el_usuario_se_ocultan_en_la_evidencia(tmp_path: Path) -> None:
    casa = Path.home().as_posix()
    xml = tmp_path / "j.xml"
    xml.write_text(f"<system-out>[SKIP] válido: {casa}/AppData/Local/Temp/pytest-of-Ana Perez/pytest-1/t</system-out>",
                   encoding="utf-8")
    h = q.sha256(xml)
    texto = xml.read_text(encoding="utf-8")
    assert casa not in texto and "pytest-of-Ana" not in texto
    assert "<tmp>/pytest-of-<usuario>/pytest-1/t" in texto and "Perez" not in texto   # nombre con espacio incluido
    assert h == __import__("hashlib").sha256(xml.read_bytes()).hexdigest()   # el hash es el del archivo ya limpio


def test_los_binarios_no_pasan_por_la_redaccion(tmp_path: Path) -> None:
    png = tmp_path / "c.png"
    datos = Path.home().as_posix().encode() + b"\x00\xff"
    png.write_bytes(datos)
    q.sha256(png)
    assert png.read_bytes() == datos
