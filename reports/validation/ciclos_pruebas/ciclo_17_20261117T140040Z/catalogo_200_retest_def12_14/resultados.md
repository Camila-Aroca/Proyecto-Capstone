# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 4 casos · **Estado:** FORMAL
- **Commit:** `cd631ecceaa10689f0bac66257b5fad5174db62c` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `.gitattributes`, `docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx`, `docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx`, `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `docs/11-manual-usuario/`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`, `reports/validation/registro_principal_pruebas.csv`, `reports/validation/registro_principal_pruebas.md`, `scripts/qa_registro_principal.py`, `scripts/qa_ui_campana.mjs`, `scripts/qa_ui_cdp.mjs`, `tests/test_qa_registro_principal.py`
- **Versión desplegada:** No confirmada: /meta no expone el SHA ni el digest de la imagen desplegada (la última corrida AWS registrada en el ciclo 4 usó la imagen 95d00f8).
- **Nota:** Formalización del retest de ciclo 15 (DEF-12, DEF-13, DEF-14) en AWS. Evidencia original en ciclo_15/retest_def12_def14.md.
- **Entorno:** AWS (URL desplegada; host redactado) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-17T15:06:37+00:00 / 2026-11-17T15:06:38+00:00
- **Resultado:** 4 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-004 | Establecimiento inválido en acceso directo | — | APROBADO | URL pasa a id=109102; no queda ningún role=alert. ID 999999999 inválido abre alternativa sin error persistente. | — | Sin defecto registrado | Retest DEF-12 en AWS. Evidencia en ciclo_15/retest_def12_def14.md. Commit 1c5c191. |
| SAAD-CP-071 | Viewport móvil estrecho | — | APROBADO | Documento 345px en 360x800; 625px en 640px. Sin desborde en tablero, establecimientos, landing. | — | Sin defecto registrado | Retest DEF-14 en AWS. Evidencia en ciclo_15/retest_def12_def14.md. Commit 1c5c191. |
| SAAD-CP-072 | Zoom al doscientos por ciento | — | APROBADO | Documento 625px en ventana 640px. Sin desborde en landing. | — | Sin defecto registrado | Retest DEF-14 en AWS. Evidencia en ciclo_15/retest_def12_def14.md. Commit 1c5c191. |
| SAAD-CP-073 | Contraste de texto y ayudas | — | APROBADO | Contraste claro: advertencias 6.36:1; en desarrollo 7.64:1. Oscuro: 10.63:1 y 9.18:1. Todos >=4.5:1. | — | Sin defecto registrado | Retest DEF-13 en AWS. Evidencia en ciclo_15/retest_def12_def14.md. Commit 1c5c191. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
