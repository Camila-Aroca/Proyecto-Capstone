"""Pruebas de la matriz de casos del ciclo de pruebas (C-06)."""

from __future__ import annotations

from scripts.qa_ciclo_pruebas import (
    APROBADO, BLOCKED, FALLIDO, NO_APLICA, NO_EJECUTADO, estados_por_entorno, matriz_catalogo,
)

CATALOGO = {"CP-SAAD-006": "Lectura de outputs", "CP-SAAD-020": "Serie RM", "CP-SAAD-025": "Camas",
            "CP-SAAD-038": "Búsqueda establecimientos", "CP-SAAD-060": "HTTPS",
            "CP-SAAD-067": "Teclado", "CP-SAAD-070": "Ciclo completo"}
LOCAL = {"casos": [
    {"id": "CP-SAAD-020", "estado": APROBADO, "detalle": "HTTP 200"},
    {"id": "CP-SAAD-025", "estado": FALLIDO, "detalle": "HTTP 404"},
]}
AWS = {"conteo": {APROBADO: 2, FALLIDO: 1}, "casos": [
    {"id": "CP-SAAD-020", "entorno": "LOCAL+AWS", "estado": APROBADO, "detalle": "Igual en LOCAL y AWS"},
    {"id": "CP-SAAD-025", "entorno": "LOCAL+AWS", "estado": FALLIDO, "detalle": "LOCAL: HTTP 404; AWS: HTTP 404"},
    {"id": "CP-SAAD-060", "entorno": "AWS", "estado": APROBADO, "detalle": "HTTP 301"},
]}


def _matriz(aws=AWS) -> dict[str, dict[str, str]]:
    filas = matriz_catalogo(CATALOGO, estados_por_entorno(LOCAL, aws), aws is not None,
                            aws["conteo"] if aws else None)
    return {f["caso"]: f for f in filas}


def test_estados_por_entorno_y_no_aplica() -> None:
    m = _matriz()
    assert (m["CP-SAAD-020"]["local"], m["CP-SAAD-020"]["aws"]) == (APROBADO, APROBADO)
    assert (m["CP-SAAD-025"]["local"], m["CP-SAAD-025"]["aws"]) == (FALLIDO, FALLIDO)
    assert (m["CP-SAAD-060"]["local"], m["CP-SAAD-060"]["aws"]) == (NO_APLICA, APROBADO)


def test_bloqueados_y_no_ejecutados_no_cuentan_como_aprobados() -> None:
    m = _matriz()
    assert m["CP-SAAD-038"]["aws"] == BLOCKED and "DEF-02" in m["CP-SAAD-038"]["nota"]
    assert m["CP-SAAD-067"]["local"] == NO_EJECUTADO


def test_derivados_y_ciclo_completo() -> None:
    m = _matriz()
    assert (m["CP-SAAD-006"]["local"], m["CP-SAAD-006"]["aws"]) == (NO_APLICA, APROBADO)
    assert m["CP-SAAD-070"]["aws"] == FALLIDO


def test_sin_aws_todo_aws_queda_blocked() -> None:
    m = _matriz(aws=None)
    assert m["CP-SAAD-020"]["aws"] == BLOCKED and m["CP-SAAD-020"]["local"] == APROBADO
