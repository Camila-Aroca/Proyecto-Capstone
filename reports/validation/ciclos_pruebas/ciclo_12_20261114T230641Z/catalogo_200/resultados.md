# Ciclo 12 · Catálogo SAAD-CP v2.1 (200 casos): Felipe Rivera

- **Ejecutor real:** Felipe Rivera · **Alcance:** 3 casos · **Estado:** FORMAL
- **Commit:** `7a43e659aab2e27d54dbe34ca7ae68dd63f87cba` · árbol versionado limpio: sí
- **Archivos sin rastrear al ejecutar:** `reports/modeling/factibilidad_pronosticos_hospitalizaciones_defunciones.md`, `reports/validation/ciclos_pruebas/ciclo_05_20261114T202918Z/`, `reports/validation/ciclos_pruebas/ciclo_06_20261114T205836Z/`, `reports/validation/ciclos_pruebas/ciclo_07_20261114T211303Z/`, `reports/validation/ciclos_pruebas/ciclo_08_20261114T220553Z/`, `reports/validation/ciclos_pruebas/ciclo_09_20261114T220556Z/`, `reports/validation/ciclos_pruebas/ciclo_10_20261114T225227Z/`, `reports/validation/ciclos_pruebas/ciclo_11_20261114T225642Z/`, `scripts/qa_campana_200.py`, `tests/test_qa_campana_200.py`
- **Entorno:** FIXTURE (pytest con tmp_path/monkeypatch, aislado de RAW y AWS) · Python 3.12.6 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-14T23:06:41+00:00 / 2026-11-14T23:06:56+00:00
- **Resultado:** 3 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-100 | Reglas explícitas de armonización | 2026-11-14T23:06:42+00:00 | APROBADO | 1 instancias, 0 fallidas, 0 omitidas; exit code 0 | [`EVIDENCIA/SAAD-CP-100_20261114_fixture.xml`](EVIDENCIA/SAAD-CP-100_20261114_fixture.xml) | Sin defecto registrado | — |
| SAAD-CP-101 | Tramo abierto de edad sin asignación ambigua | 2026-11-14T23:06:47+00:00 | APROBADO | 1 instancias, 0 fallidas, 0 omitidas; exit code 0 | [`EVIDENCIA/SAAD-CP-101_20261114_fixture.xml`](EVIDENCIA/SAAD-CP-101_20261114_fixture.xml) | Sin defecto registrado | — |
| SAAD-CP-102 | Categoría nueva sin regla detiene salida | 2026-11-14T23:06:51+00:00 | APROBADO | 1 instancias, 0 fallidas, 0 omitidas; exit code 0 | [`EVIDENCIA/SAAD-CP-102_20261114_fixture.xml`](EVIDENCIA/SAAD-CP-102_20261114_fixture.xml) | Sin defecto registrado | — |

## Límites

- Los tests unitarios verifican el código con fixtures; no acreditan los datos reales del snapshot vigente.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
