"""Pruebas de las funciones puras del script de prueba E2E local/AWS."""

from __future__ import annotations

from pathlib import Path

from scripts.qa_e2e_local_vs_aws import Redactor, Respuesta, comparar, intervalos_ordenados, leer_env, resumen_api


def test_leer_env_ignora_comentarios_y_lineas_vacias(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comentario\n\nSAAD_URL=https://x.example\nVACIA=\nCON=igual=adentro\n", encoding="utf-8")
    assert leer_env(env) == {"SAAD_URL": "https://x.example", "VACIA": "", "CON": "igual=adentro"}


def test_leer_env_sin_archivo(tmp_path: Path) -> None:
    assert leer_env(tmp_path / "no-existe") == {}


def test_redactor_reemplaza_en_textos_listas_y_diccionarios() -> None:
    redactar = Redactor({"URL_AWS": "https://abc.cloudfront.net", "URL_AWS_HOST": "abc.cloudfront.net",
                         "AWS_ACCOUNT_ID": "123456789012", "VACIO": ""})
    datos = {"url": "GET https://abc.cloudfront.net/api", "cuenta": ["arn:aws:iam::123456789012:x"],
             "host": "abc.cloudfront.net", "otro": 5}
    assert redactar(datos) == {"url": "GET <URL_AWS>/api", "cuenta": ["arn:aws:iam::<AWS_ACCOUNT_ID>:x"],
                               "host": "<URL_AWS_HOST>", "otro": 5}


def test_comparar_lista_solo_diferencias() -> None:
    assert comparar({"estado": 200, "n": 52}, {"estado": 200, "n": 52}) == []
    assert comparar({"estado": 200, "n": 52}, {"estado": 503}) == ["estado: local=200 aws=503", "n: local=52 aws=None"]


def test_intervalos_ordenados_detecta_puntos_fuera() -> None:
    puntos = [
        {"series_id": "RM", "horizonte": 1, "pronostico": 10, "limite_inferior": 8, "limite_superior": 12},
        {"series_id": "13101", "horizonte": 2, "pronostico": 15, "limite_inferior": 8, "limite_superior": 12},
    ]
    assert intervalos_ordenados(puntos) == ["13101 h2"]


def test_resumen_api_por_endpoint() -> None:
    territorios = [{"series_id": "RM", "tiene_pronostico": True}, {"series_id": "13101", "tiene_pronostico": False}]
    assert resumen_api("territorios", Respuesta(200, 1.0, territorios)) == {
        "estado": 200, "n": 2, "ids": ["13101", "RM"], "con_pronostico": 1}
    assert resumen_api("salud", Respuesta(503, 1.0, {})) == {"estado": 503}
    assert resumen_api("geo_comunas", Respuesta(200, 1.0, {"type": "FeatureCollection", "features": [1, 2]})) == {
        "estado": 200, "tipo": "FeatureCollection", "n_features": 2}
