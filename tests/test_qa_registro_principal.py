from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "qa_registro_principal", RAIZ / "scripts/qa_registro_principal.py"
)
rp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rp)


@pytest.fixture
def ciclos(tmp_path: Path) -> Path:
    """Árbol mínimo de ciclos con un caso por entorno."""
    base = tmp_path / "reports/validation/ciclos_pruebas"

    def _caso(cid: str, estado: str, entorno: str, titulo: str = "Título", modulo: str = "M") -> dict:
        return {
            "id": cid, "titulo": titulo, "modulo": modulo,
            "estado": estado, "entorno": entorno,
            "resultado_real": "ok", "defecto": "", "evidencia": None,
            "run_id": "ciclo_01/catalogo_200",
        }

    def _run(carpeta: Path, casos: list[dict]) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "resultados.json").write_text(
            json.dumps({"run_id": "x", "ciclo": "x", "catalogo": "x",
                        "ejecutor_real": "x", "alcance": "x", "estado_corrida": "x",
                        "inicio_utc": None, "fin_utc": None, "commit": "x",
                        "arbol_versionado_limpio": True, "archivos_versionados_modificados": [],
                        "archivos_sin_rastrear": [], "entorno": casos[0]["entorno"] if casos else "",
                        "modo": "pytest", "nota": "", "version_desplegada": None,
                        "python": "3.12", "so": "Linux", "librerias": {},
                        "resumen": {}, "advertencias": [], "casos": casos}),
            encoding="utf-8",
        )

    _run(base / "ciclo_05_20261114T202918Z/catalogo_200", [
        _caso("SAAD-CP-081", "APROBADO", "FIXTURE (pytest)"),
        _caso("SAAD-CP-082", "FALLIDO", "FIXTURE (pytest)"),
    ])
    _run(base / "ciclo_17_20261117T140040Z/catalogo_200_local", [
        _caso("SAAD-CP-039", "APROBADO", "LOCAL (API local)"),
    ])
    _run(base / "ciclo_17_20261117T140040Z/catalogo_200_aws", [
        _caso("SAAD-CP-039", "APROBADO", "AWS (URL desplegada)"),
    ])
    return tmp_path


def _monkeypatch_rastreados(monkeypatch, ciclos: Path) -> None:
    """Hace que _archivos_rastreados devuelva todos los JSON del tmp_path."""
    todos = set(ciclos.glob("**/*.json"))
    monkeypatch.setattr(rp, "_archivos_rastreados", lambda raiz=None: todos)


def test_carga_resultados_200_basico(tmp_path, monkeypatch, ciclos):
    _monkeypatch_rastreados(monkeypatch, ciclos)
    r = rp.cargar_resultados_200(ciclos)
    assert "SAAD-CP-081" in r
    assert r["SAAD-CP-081"]["FIXTURE"]["estado"] == "APROBADO"


def test_no_ejecutado_no_oculta_aprobado(tmp_path, monkeypatch, ciclos):
    """Un NO EJECUTADO posterior no debe reemplazar un APROBADO anterior."""
    base = ciclos / "reports/validation/ciclos_pruebas"
    carpeta = base / "ciclo_99_20991231T000000Z/catalogo_200_fixture"
    carpeta.mkdir(parents=True, exist_ok=True)
    caso_ne = {
        "id": "SAAD-CP-081", "titulo": "T", "modulo": "M",
        "estado": "NO EJECUTADO", "entorno": "FIXTURE (pytest)",
        "resultado_real": "No ejecutado", "defecto": "", "evidencia": None,
        "run_id": "ciclo_99/catalogo_200_fixture",
    }
    (carpeta / "resultados.json").write_text(
        json.dumps({"run_id": "x", "ciclo": "x", "catalogo": "x",
                    "ejecutor_real": "x", "alcance": "x", "estado_corrida": "x",
                    "inicio_utc": None, "fin_utc": None, "commit": "x",
                    "arbol_versionado_limpio": True, "archivos_versionados_modificados": [],
                    "archivos_sin_rastrear": [], "entorno": "FIXTURE (pytest)",
                    "modo": "pytest", "nota": "", "version_desplegada": None,
                    "python": "3.12", "so": "Linux", "librerias": {},
                    "resumen": {}, "advertencias": [], "casos": [caso_ne]}),
        encoding="utf-8",
    )
    _monkeypatch_rastreados(monkeypatch, ciclos)
    r = rp.cargar_resultados_200(ciclos)
    assert r["SAAD-CP-081"]["FIXTURE"]["estado"] == "APROBADO"


def test_estado_global_fallido_si_alguno_falla():
    entornos = {
        "FIXTURE": {"estado": "APROBADO"},
        "AWS": {"estado": "FALLIDO"},
    }
    assert rp.estado_global(entornos) == "FALLIDO"


def test_estado_global_aprobado_si_todos_aprueban():
    entornos = {
        "FIXTURE": {"estado": "APROBADO"},
        "LOCAL": {"estado": "APROBADO"},
    }
    assert rp.estado_global(entornos) == "APROBADO"


def test_estado_global_no_ejecutado_si_vacio():
    assert rp.estado_global({}) == "NO EJECUTADO"


def test_main_genera_archivos(tmp_path, monkeypatch, ciclos):
    _monkeypatch_rastreados(monkeypatch, ciclos)

    # Redireccionar salidas al tmp_path
    md_out = ciclos / "reports/validation/registro_principal_pruebas.md"
    csv_out = ciclos / "reports/validation/registro_principal_pruebas.csv"
    xlsx_out = ciclos / "docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx"

    monkeypatch.chdir(ciclos)
    ret = rp.main(["--raiz", str(ciclos), "--sin-enlaces"])
    assert ret == 0
    assert md_out.exists()
    assert csv_out.exists()
    # xlsx puede fallar si openpyxl no está disponible; solo verificamos que no explota
