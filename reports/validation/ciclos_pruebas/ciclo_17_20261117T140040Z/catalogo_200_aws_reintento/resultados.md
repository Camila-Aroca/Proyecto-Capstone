# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 2 casos · **Estado:** FORMAL
- **Commit:** `8f7dd49bfc2740fb6c2ce1b12cd8ff12fbe64e20` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`
- **Versión desplegada:** No confirmada: /meta no expone el SHA ni el digest de la imagen desplegada (la última corrida AWS registrada en el ciclo 4 usó la imagen 95d00f8).
- **Nota:** Reintento tras autorizar saad-github, ejecutar saad-pr y publicar los datos con subir_datos.sh.
- **Entorno:** AWS (URL desplegada; host redactado) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-17T22:28:18+00:00 / 2026-11-17T22:31:16.462735+00:00
- **Resultado:** 2 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-066 | Estado de conexión CI | 2026-11-17T22:31:04.433009+00:00 | APROBADO | Conexión saad-github AVAILABLE; última ejecución de saad-pr Succeeded (2026-11-17T19:21): fuente GitHub y Tests-y-cfn-lint verificables. | [`EVIDENCIA/SAAD-CP-066.txt`](EVIDENCIA/SAAD-CP-066.txt) | Sin defecto registrado | saad-despliegue: última ejecución Failed 2026-11-12 (creada con la conexión aún PENDING); no se relanzó para no desplegar a producción durante la prueba. |
| SAAD-CP-068 | Paridad local y AWS por snapshot | 2026-11-17T22:28:18+00:00 | APROBADO | Tras publicar los datos con subir_datos.sh (commit 8f7dd49) el primer pronóstico de /series/RM coincide en LOCAL y AWS (2026-S46). qa_e2e_local_vs_aws.py --sin-capturas: 24 aprobados, 0 fallidos; 13 endpoints equivalentes y las comprobaciones de infraestructura y seguridad de AWS aprobadas. | [`EVIDENCIA/SAAD-CP-068.md`](EVIDENCIA/SAAD-CP-068.md) | Sin defecto registrado | La corrida anterior (misma jornada) quedó bloqueada por snapshot: AWS servía el pronóstico desde 2026-S40. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
