"""Pruebas de las funciones del script de línea base local (sin Docker)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import qa_baseline_local as base


def test_sin_rutas_locales_quita_repo_y_home() -> None:
    texto = f"{base.RAIZ}/data/x.parquet y {Path.home()}/.aws"
    assert base.sin_rutas_locales(texto) == "<repo>/data/x.parquet y <home>/.aws"


def test_inventario_dataset_lista_hash_y_excluye_validacion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "data/processed").mkdir(parents=True)
    (tmp_path / "data/processed/a.parquet").write_bytes(b"abc")
    (tmp_path / "reports/validation").mkdir(parents=True)
    (tmp_path / "reports/validation/informe.md").write_text("no entra")
    (tmp_path / "reports/m.json").write_text("{}")
    monkeypatch.setattr(base, "RAIZ", tmp_path)

    resumen = base.inventario_dataset(tmp_path / "dataset.csv")
    filas = list(csv.DictReader((tmp_path / "dataset.csv").open(encoding="utf-8")))

    assert [f["ruta"] for f in filas] == ["data/processed/a.parquet", "reports/m.json"]
    assert filas[0]["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert resumen["archivos"] == 2 and len(resumen["huella_sha256"]) == 64
