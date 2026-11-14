# Ciclo 6 · Catálogo SAAD-CP v2.1 (200 casos): Felipe Rivera

- **Ejecutor real:** Felipe Rivera · **Alcance:** 5 casos · **Estado:** FORMAL
- **Commit:** `7a43e659aab2e27d54dbe34ca7ae68dd63f87cba` · árbol versionado limpio: sí
- **Archivos sin rastrear al ejecutar:** `reports/modeling/factibilidad_pronosticos_hospitalizaciones_defunciones.md`, `reports/validation/ciclos_pruebas/ciclo_05_20261114T202918Z/`, `scripts/qa_campana_200.py`, `tests/test_qa_campana_200.py`
- **Nota:** API local iniciada con SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1: sirve el pronóstico persistido como vista temporal (la selección del benchmark no coincide en hash por saltos de línea CRLF de Windows). Datos de Urgencias locales: corte del 14-11-2026.
- **Entorno:** LOCAL (API local con Uvicorn en 127.0.0.1) · Python 3.12.6 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-14T20:58:36+00:00 / 2026-11-14T20:58:37+00:00
- **Resultado:** 5 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-043 | Calendario con intervalo invertido | 2026-11-14T20:58:36+00:00 | APROBADO | GET /calendario-eventos?desde=2026-12-31&hasta=2026-01-01 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-043_20261114_local.json`](EVIDENCIA/SAAD-CP-043_20261114_local.json) | Sin defecto registrado | API local iniciada con SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1: sirve el pronóstico persistido como vista temporal (la selección del benchmark no coincide en hash por saltos de línea CRLF de Windows). Datos de Urgencias locales: corte del 14-11-2026. |
| SAAD-CP-044 | Límite exacto del calendario | 2026-11-14T20:58:36+00:00 | APROBADO | GET /calendario-eventos?desde=2020-01-01&hasta=2032-01-10 → HTTP 200 (esperado 200); GET /calendario-eventos?desde=2020-01-01&hasta=2032-01-11 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-044_20261114_local.json`](EVIDENCIA/SAAD-CP-044_20261114_local.json) | Sin defecto registrado | API local iniciada con SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1: sirve el pronóstico persistido como vista temporal (la selección del benchmark no coincide en hash por saltos de línea CRLF de Windows). Datos de Urgencias locales: corte del 14-11-2026. |
| SAAD-CP-053 | Semana DEIS fuera de dominio | 2026-11-14T20:58:36+00:00 | APROBADO | GET /caracterizacion/urgencias/region/RM?semanas=2026-54 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-053_20261114_local.json`](EVIDENCIA/SAAD-CP-053_20261114_local.json) | Sin defecto registrado | API local iniciada con SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1: sirve el pronóstico persistido como vista temporal (la selección del benchmark no coincide en hash por saltos de línea CRLF de Windows). Datos de Urgencias locales: corte del 14-11-2026. |
| SAAD-CP-054 | Defunciones no identifica establecimiento | 2026-11-14T20:58:37+00:00 | APROBADO | GET /caracterizacion/suicidios/establecimiento/109102?semanas=2025-1 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-054_20261114_local.json`](EVIDENCIA/SAAD-CP-054_20261114_local.json) | Sin defecto registrado | API local iniciada con SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1: sirve el pronóstico persistido como vista temporal (la selección del benchmark no coincide en hash por saltos de línea CRLF de Windows). Datos de Urgencias locales: corte del 14-11-2026. |
| SAAD-CP-055 | Comuna ajena a RM | 2026-11-14T20:58:37+00:00 | APROBADO | GET /caracterizacion/urgencias/comuna/05101?semanas=2025-1 → HTTP 404 (esperado 404) | [`EVIDENCIA/SAAD-CP-055_20261114_local.json`](EVIDENCIA/SAAD-CP-055_20261114_local.json) | Sin defecto registrado | API local iniciada con SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1: sirve el pronóstico persistido como vista temporal (la selección del benchmark no coincide en hash por saltos de línea CRLF de Windows). Datos de Urgencias locales: corte del 14-11-2026. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
