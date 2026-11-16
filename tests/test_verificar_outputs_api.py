from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verificar_outputs_api", RAIZ / "scripts/verificar_outputs_api.py")
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)

ENTRADA = Path("reports/modeling/entrada.json")
URGENCIAS = Path("data/processed/urgencias")


def _escribir(raiz: Path, ruta: Path, contenido: bytes = b"x") -> None:
    (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
    (raiz / ruta).write_bytes(contenido)


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    _escribir(tmp_path, ENTRADA, b"{}\n")
    manifiesto = {"entradas": {"seleccion_benchmark": {
        "ruta": ENTRADA.as_posix(), "sha256": hashlib.sha256(b"{}\n").hexdigest()}}}
    for ruta in v.requeridos():
        contenido = json.dumps(manifiesto).encode() if ruta in v.MANIFIESTOS else b"x"
        _escribir(tmp_path, ruta, contenido)
    _escribir(tmp_path, URGENCIAS / "urgencias_rm_2026.parquet")
    return tmp_path


def test_outputs_completos_y_coherentes(outputs: Path) -> None:
    assert v.problemas(outputs) == []


def test_reporta_archivo_faltante(outputs: Path) -> None:
    (outputs / "reports/modeling/holdout_suicidios_resumen.csv").unlink()
    assert v.problemas(outputs) == ["falta reports/modeling/holdout_suicidios_resumen.csv"]


def test_reporta_urgencias_anuales_faltantes(outputs: Path) -> None:
    (outputs / URGENCIAS / "urgencias_rm_2026.parquet").unlink()
    assert v.problemas(outputs) == ["falta data/processed/urgencias/urgencias_rm_*.parquet"]


def test_reporta_entrada_que_cambio_despues_del_pronostico(outputs: Path) -> None:
    (outputs / ENTRADA).write_bytes(b"{}\r\n")
    encontrados = v.problemas(outputs)
    assert len(encontrados) == len(v.MANIFIESTOS)
    assert all("cambió después de generar el pronóstico" in p for p in encontrados)


def test_entrada_raw_sha256_se_compara_con_la_identidad_del_raw(outputs: Path, monkeypatch) -> None:
    manifiesto = outputs / v.MANIFIESTOS[0]
    datos = json.loads(manifiesto.read_text())
    datos["entradas"]["urgencias_2026"] = {"ruta": ENTRADA.as_posix(), "sha256": "raw-declarado", "tipo": "raw_sha256"}
    manifiesto.write_text(json.dumps(datos))
    monkeypatch.setattr(v, "processed_raw_sha256", lambda ruta: "raw-declarado")
    assert v.problemas(outputs) == []
    monkeypatch.setattr(v, "processed_raw_sha256", lambda ruta: "otro-raw")
    assert v.problemas(outputs) == [f"{v.MANIFIESTOS[0].name}: {ENTRADA.as_posix()} cambió después de generar el pronóstico"]


def test_incluye_marts_manifiestos_y_selecciones() -> None:
    rutas = {r.as_posix() for r in v.requeridos()}
    assert "data/processed/marts/mart_suicidios_comuna_weekly.parquet" in rutas
    assert "data/processed/modeling/pronostico_establecimientos_sm_manifest.json" in rutas
    assert {f"reports/modeling/benchmark_{n}_seleccion.json" for n in ("demanda_sm", "establecimientos_sm", "suicidios")} <= rutas
