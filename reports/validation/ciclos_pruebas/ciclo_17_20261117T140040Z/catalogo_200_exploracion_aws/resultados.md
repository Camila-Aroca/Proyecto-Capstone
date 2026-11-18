# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 1 casos · **Estado:** FORMAL
- **Commit:** `68f5a26d1664fd0b867deda5a516e2acea1b1f1a` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`, `scripts/qa_ui_exploracion.mjs`
- **Versión desplegada:** No confirmada: /meta no expone el SHA ni el digest de la imagen desplegada (la última corrida AWS registrada en el ciclo 4 usó la imagen 95d00f8).
- **Nota:** Exploración guiada por riesgo territorial con barrido automatizado (Chrome CDP): comunas sin datos, con cero observado y con baja confianza. No equivale a la sesión humana de 30 minutos del caso.
- **Entorno:** AWS (URL desplegada; host redactado) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-18T18:32:17.413Z / 2026-11-18T18:33:48.905Z
- **Resultado:** 1 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-079 | Sesión guiada por riesgo territorial | 2026-11-18T18:32:17.413Z | APROBADO | La interfaz distingue los tres estados: sin datos (2 comunas con aviso y motivo, sin pronóstico cero), cero observado (3 comunas con las semanas en 0 visibles como «0 · Observado») y baja confianza (3 comunas con intervalo, confiabilidad observada y advertencia). 2 hallazgo(s) de usabilidad en la bitácora. Duración real 1.5 min con barrido automatizado, no sesión humana de 30 min. | [`EVIDENCIA/SAAD-CP-079-bitacora.md`](EVIDENCIA/SAAD-CP-079-bitacora.md) (+3 anexos en `EVIDENCIA/`) | Sin defecto registrado | H-1: Junto al motivo se muestra «No se pudo consultar la API… Verifique que el backend esté corriendo (uvicorn src.api.main:app)…», un mensaje técnico de falla del sistema para una ausencia de dato esperada. H-1: Junto al motivo se muestra «No se pudo consultar la API… Verifique que el backend esté corriendo (uvicorn src.api.main:app)…», un mensaje técnico de falla del sistema para una ausencia de dato esperada. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
