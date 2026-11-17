# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 11 casos · **Estado:** FORMAL
- **Commit:** `c2f1267614fb33f7eb10438450eb16c420743483` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`
- **Nota:** Ciclo final, segunda tanda de interfaz en LOCAL (Chrome headless CDP): navegación, orden de tabla, ayudas, comunas sin pronóstico, carrera de respuestas e intercepciones de /establecimientos-meta y contraste de egresos.
- **Entorno:** LOCAL (API local con Uvicorn en 127.0.0.1) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-17T15:32:41.425Z / 2026-11-17T15:34:48.731Z
- **Resultado:** 11 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-003 | Enlace a hospital por código | 2026-11-17T15:32:41.425Z | APROBADO | Hospital 114101 (Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto)) conserva su detalle tras recargar; hash=#/establecimientos?comuna=13201&id=114101 | [`EVIDENCIA/SAAD-CP-003.png`](EVIDENCIA/SAAD-CP-003.png) | Sin defecto registrado | — |
| SAAD-CP-007 | Foco al cambiar de vista | 2026-11-17T15:32:53.874Z | APROBADO | Tab (3 pasos) + Enter lleva a #/establecimientos; scroll=0; foco tras el cambio: MAIN:contenido | [`EVIDENCIA/SAAD-CP-007.png`](EVIDENCIA/SAAD-CP-007.png) | Sin defecto registrado | — |
| SAAD-CP-014 | Seleccionar polígono comunal | 2026-11-17T15:33:08.344Z | APROBADO | Polígono 13101 (GeoJSON: SANTIAGO) → #/tablero?territorio=13101; la serie y el título muestran Santiago | [`EVIDENCIA/SAAD-CP-014.png`](EVIDENCIA/SAAD-CP-014.png) | Sin defecto registrado | — |
| SAAD-CP-015 | Orden numérico y nulos al final | 2026-11-17T15:33:20.056Z | APROBADO | Pronóstico monótono en ambos sentidos (50 valores, 2 sin pronóstico al final en ascendente y descendente) | [`EVIDENCIA/SAAD-CP-015.png`](EVIDENCIA/SAAD-CP-015.png) | Sin defecto registrado | — |
| SAAD-CP-016 | Ayuda de tasa semanal | 2026-11-17T15:33:30.407Z | APROBADO | Ayuda: "Atenciones pronosticadas por 10.000 habitantes a la semana; no es prevalencia". 50 comunas comparadas con tasa_pronostico_por_10000: diferencia máxima 0.050 | [`EVIDENCIA/SAAD-CP-016.png`](EVIDENCIA/SAAD-CP-016.png) | Sin defecto registrado | — |
| SAAD-CP-017 | Temporalidad de pobreza y oferta | 2026-11-17T15:33:40.820Z | APROBADO | Pobreza: "PobrezaTasa de pobreza por ingresos, Casen 2022" · Oferta: "OfertaEstablecimientos de urgencia vigentes en la comuna; clic para verlos uno a uno"; ninguna usa el año del pronóstico | [`EVIDENCIA/SAAD-CP-017.png`](EVIDENCIA/SAAD-CP-017.png) | Sin defecto registrado | — |
| SAAD-CP-018 | Comuna sin serie modelable | 2026-11-17T15:34:02.614Z | APROBADO | La interfaz declara ausencia y motivo sin dibujar pronóstico cero. María Pinto (13504): aviso=true motivo=true /series=404 | Vitacura (13132): aviso=true motivo=true /series=404 | [`EVIDENCIA/SAAD-CP-018.png`](EVIDENCIA/SAAD-CP-018.png) | Sin defecto registrado | Observación: junto al motivo se muestra el texto genérico 'No se pudo consultar la API… Verifique que el backend esté corriendo' (mensaje confuso para una ausencia esperada). |
| SAAD-CP-021 | Respuesta tardía de comuna previa | 2026-11-17T15:34:21.912Z | APROBADO | Petición /series/13101 retenida 5 s y cambio inmediato a 13102 por el selector; desenlace de la petición tardía: net::ERR_ABORTED; la pantalla queda en Cerrillos (13102) sin datos de Santiago | [`EVIDENCIA/SAAD-CP-021.png`](EVIDENCIA/SAAD-CP-021.png) | Sin defecto registrado | — |
| SAAD-CP-026 | Aviso de pronóstico desactualizado | 2026-11-17T15:34:32.182Z | APROBADO | Con /establecimientos-meta vigente=false la vista muestra "Pronóstico desactualizado" y el motivo del fixture | [`EVIDENCIA/SAAD-CP-026.png`](EVIDENCIA/SAAD-CP-026.png) | Sin defecto registrado | — |
| SAAD-CP-040 | Ausencia de contraste opcional | 2026-11-17T15:34:43.370Z | APROBADO | Con contraste_camas=null en 1 respuesta(s) 200 de hospitalizaciones-residentes (200,200,200,200,200,200,200,200,200) el perfil de egresos se muestra y el módulo no se bloquea | [`EVIDENCIA/SAAD-CP-040.png`](EVIDENCIA/SAAD-CP-040.png) | Sin defecto registrado | Fixture inyectado por CDP (copia de la respuesta real sin el contraste); no se modificó el snapshot. |
| SAAD-CP-056 | Contrato y cliente frontend | 2026-11-17T15:34:48.731Z | APROBADO | Reporte comparacion_api_frontend.md: 0 errores · 12 advertencias · 9 observaciones; advertencias y errores 404/409/503 no declarados quedan listados en el reporte | [`EVIDENCIA/SAAD-CP-056.png`](EVIDENCIA/SAAD-CP-056.png) | Sin defecto registrado | — |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
