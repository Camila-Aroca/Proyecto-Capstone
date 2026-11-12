"""Pruebas del comparador de contrato API/frontend (#61)."""

from __future__ import annotations

from scripts.qa_contrato_api import (
    API_TS, ERROR, comparar, leer_rutas_ts, leer_tipos_ts, normalizar_openapi, normalizar_ts,
)

TS = '''
export type Nivel = "region" | "comuna";
export interface Punto { valor: number; fecha: string | null }
export interface Serie {
  id: string;
  nivel: Nivel;
  puntos: Punto[];
  extra?: { nota: string } | null;
}
export const api = {
  serie: (id: string, s: number) => obtener<Serie>(`/series/${id}?semanas=${s}`),
};
'''

COMPONENTES = {
    "Punto": {"type": "object", "required": ["valor", "fecha"], "properties": {
        "valor": {"type": "number"}, "fecha": {"anyOf": [{"type": "string"}, {"type": "null"}]}}},
    "Serie": {"type": "object", "required": ["id", "nivel", "puntos"], "properties": {
        "id": {"type": "string"},
        "nivel": {"type": "string", "enum": ["region", "comuna"]},
        "puntos": {"type": "array", "items": {"$ref": "#/components/schemas/Punto"}},
        "extra": {"anyOf": [{"type": "object", "properties": {"nota": {"type": "string"}}}, {"type": "null"}]}}},
}


def _comparar(componentes: dict) -> list:
    interfaces, alias = leer_tipos_ts(TS)
    api = normalizar_openapi({"$ref": "#/components/schemas/Serie"}, componentes)
    return comparar(api, normalizar_ts("Serie", interfaces, alias), "/series/{}")


def test_contrato_identico_no_tiene_errores() -> None:
    assert [h for h in _comparar(COMPONENTES) if h.severidad == ERROR] == []


def test_detecta_campo_esperado_que_la_api_no_envia() -> None:
    sin_id = {**COMPONENTES, "Serie": {**COMPONENTES["Serie"], "properties": {
        k: v for k, v in COMPONENTES["Serie"]["properties"].items() if k != "id"}}}
    assert any(h.campo == "id" and h.severidad == ERROR for h in _comparar(sin_id))


def test_detecta_null_no_admitido_y_tipo_distinto() -> None:
    punto = {"type": "object", "required": ["valor", "fecha"], "properties": {
        "valor": {"anyOf": [{"type": "string"}, {"type": "null"}]}, "fecha": {"type": "string"}}}
    errores = {h.campo for h in _comparar({**COMPONENTES, "Punto": punto}) if h.severidad == ERROR}
    assert "puntos[].valor" in errores


def test_detecta_valor_de_enum_que_el_frontend_no_conoce() -> None:
    serie = {**COMPONENTES["Serie"], "properties": {**COMPONENTES["Serie"]["properties"],
             "nivel": {"type": "string", "enum": ["region", "comuna", "pais"]}}}
    assert any(h.campo == "nivel" and h.severidad == ERROR for h in _comparar({**COMPONENTES, "Serie": serie}))


def test_lee_rutas_y_parametros_del_frontend() -> None:
    assert leer_rutas_ts(TS) == [{"metodo": "serie", "ruta": "/api/v1/series/{}", "tipo": "Serie", "consulta": ["semanas"]}]


def test_api_ts_real_se_lee_completo() -> None:
    texto = API_TS.read_text(encoding="utf-8")
    interfaces, alias = leer_tipos_ts(texto)
    rutas = leer_rutas_ts(texto)
    assert len(rutas) == 14
    externos = [r["tipo"] for r in rutas if normalizar_ts(r["tipo"], interfaces, alias)["tipo"] == "externo"]
    assert externos == ["GeoJSON.FeatureCollection"]
