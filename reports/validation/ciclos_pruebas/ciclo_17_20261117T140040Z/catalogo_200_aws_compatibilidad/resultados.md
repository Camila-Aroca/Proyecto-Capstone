# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Codex (automatización Playwright)

- **Ejecutor real:** Codex (automatización Playwright) · **Alcance:** 1 casos · **Estado:** FORMAL
- **Commit:** `e75c28bee7c0a37b3f8be48e46cbb2fa6070ad2c` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** ninguno
- **Versión desplegada:** No confirmada: /meta no expone el SHA ni el digest de la imagen desplegada (la última corrida AWS registrada en el ciclo 4 usó la imagen 95d00f8).
- **Nota:** Recorrido de compatibilidad en Chromium, Firefox y WebKit contra el mismo snapshot de AWS.
- **Entorno:** AWS (URL desplegada; host redactado) · Python 3.12.6 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-18T01:51:12.875Z / 2026-11-18T01:51:48.703Z
- **Resultado:** 1 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-074 | Motores de navegador | 2026-11-18T01:51:12.875Z | APROBADO | Santiago (13101) y Hospital Clínico San Borja Arriarán (111100) mostraron los mismos datos y controles utilizables en Chromium 158.0.8127.18, Firefox 159.0, WebKit 27.2. Ambas consultas respondieron HTTP 200 en los tres motores, con los mismos hashes y cifras visibles. | [`EVIDENCIA/SAAD-CP-074.md`](EVIDENCIA/SAAD-CP-074.md) (+7 anexos en `EVIDENCIA/`) | Sin defecto registrado | Playwright en Windows. Cobertura de los tres motores del caso. Edge queda fuera de esta corrida. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
