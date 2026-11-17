# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 7 casos · **Estado:** FORMAL
- **Commit:** `cd631ecceaa10689f0bac66257b5fad5174db62c` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `.gitattributes`, `docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx`, `docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx`, `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `docs/11-manual-usuario/`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`, `reports/validation/registro_principal_pruebas.csv`, `reports/validation/registro_principal_pruebas.md`, `scripts/qa_registro_principal.py`, `scripts/qa_ui_campana.mjs`, `scripts/qa_ui_cdp.mjs`, `tests/test_qa_registro_principal.py`
- **Nota:** Casos no ejecutables en el ciclo final por restricciones del entorno. Ver observaciones por caso.
- **Entorno:** LOCAL (API local con Uvicorn en 127.0.0.1) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-17T15:06:50+00:00 / 2026-11-17T15:06:50+00:00
- **Resultado:** 0 aprobados · 0 fallidos · 7 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-009 | Comprender propósito predictivo | — | NO EJECUTADO | No ejecutado en el ciclo final. Requiere usuario piloto institucional (#90 sin cerrar). | — | Sin defecto registrado | Requiere usuario piloto institucional (#90 sin cerrar) |
| SAAD-CP-037 | Explicar residencia frente a atención | — | NO EJECUTADO | No ejecutado en el ciclo final. Requiere usuario piloto institucional (#90 sin cerrar). | — | Sin defecto registrado | Requiere usuario piloto institucional (#90 sin cerrar) |
| SAAD-CP-046 | Interpretar bandas y festividades | — | NO EJECUTADO | No ejecutado en el ciclo final. Requiere usuario piloto institucional (#90 sin cerrar). | — | Sin defecto registrado | Requiere usuario piloto institucional (#90 sin cerrar) |
| SAAD-CP-074 | Motores de navegador | — | NO EJECUTADO | No ejecutado en el ciclo final. Requiere WebKit (solo Chrome y Firefox instalados). | — | Sin defecto registrado | Requiere WebKit (solo Chrome y Firefox instalados) |
| SAAD-CP-078 | Interpretación de propuesta de camas | — | NO EJECUTADO | No ejecutado en el ciclo final. Requiere usuario piloto institucional (#90 sin cerrar). | — | Sin defecto registrado | Requiere usuario piloto institucional (#90 sin cerrar) |
| SAAD-CP-079 | Sesión guiada por riesgo territorial | — | NO EJECUTADO | No ejecutado en el ciclo final. Sesión exploratoria de 30 min; requiere coordinación con cliente. | — | Sin defecto registrado | Sesión exploratoria de 30 min; requiere coordinación con cliente |
| SAAD-CP-080 | Recorrido de planificación completo | — | NO EJECUTADO | No ejecutado en el ciclo final. Requiere usuario piloto institucional (#90 sin cerrar). | — | Sin defecto registrado | Requiere usuario piloto institucional (#90 sin cerrar) |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
