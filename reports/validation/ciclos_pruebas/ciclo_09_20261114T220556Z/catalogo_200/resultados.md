# Ciclo 9 · Catálogo SAAD-CP v2.1 (200 casos): Felipe Rivera

- **Ejecutor real:** Felipe Rivera · **Alcance:** 1 casos · **Estado:** FORMAL
- **Commit:** `7a43e659aab2e27d54dbe34ca7ae68dd63f87cba` · árbol versionado limpio: sí
- **Archivos sin rastrear al ejecutar:** `reports/modeling/factibilidad_pronosticos_hospitalizaciones_defunciones.md`, `reports/validation/ciclos_pruebas/ciclo_05_20261114T202918Z/`, `reports/validation/ciclos_pruebas/ciclo_06_20261114T205836Z/`, `reports/validation/ciclos_pruebas/ciclo_07_20261114T211303Z/`, `reports/validation/ciclos_pruebas/ciclo_08_20261114T220553Z/`, `scripts/qa_campana_200.py`, `tests/test_qa_campana_200.py`
- **Versión desplegada:** No confirmada: /meta no expone el SHA ni el digest de la imagen desplegada (la última corrida AWS registrada en el ciclo 4 usó la imagen 95d00f8).
- **Nota:** Sitio desplegado consultado en solo lectura con Chrome headless en un contexto de navegador nuevo (host redactado). Los scripts de ejecución quedaron fuera del repositorio; su hash figura en hash_input.
- **Entorno:** AWS (URL desplegada; host redactado) · Python 3.12.6 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-14T22:05:14+00:00 / 2026-11-14T22:05:26+00:00
- **Resultado:** 0 aprobados · 1 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-004 | Establecimiento inválido en acceso directo | 2026-11-14T22:05:14+00:00 | FALLIDO | GET /establecimientos/999999999 → 404; la aplicación eligió 109102 ("Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta)") y normalizó la URL a #/establecimientos?id=109102; el detalle alternativo respondió 200 y el gráfico se muestra, pero el aviso "No se pudo consultar el pronóstico por establecimiento. El establecimiento no existe en los datos de Urgencias." PERSISTE tras recibir ese 200; al recargar el comportamiento es estable. | [`EVIDENCIA/SAAD-CP-004_20261114_aws.json`](EVIDENCIA/SAAD-CP-004_20261114_aws.json) (+2 anexos en `EVIDENCIA/`) | Incidencia reproducida (OBS-AWS-01 del plan); pendiente de registrar como DEF en registro_defectos.md (esta corrida no modifica ese registro) | Reproduce OBS-AWS-01 del plan de pruebas: queda un aviso general de error de pronóstico aunque la alternativa cargó bien. Es el criterio que no se cumple. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
