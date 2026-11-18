# SAAD-CP-074 — Motores de navegador

**Resultado.** APROBADO en AWS (CloudFront, host redactado).

**Ejecución.** 2026-11-18T01:51:12.875Z a 2026-11-18T01:51:48.703Z · Playwright 1.65.0 · win32 10.0.26200 · sesión nueva por motor · 1440×900 · es-CL.

**Línea base.** La ruta de salud devolvió datos y pronóstico listos. El snapshot fue 2026-S45, con pronóstico persistido del 2026-11-17T14:44:07.753983Z. El HTML de entrada tuvo el mismo SHA-256 en los tres motores.

**Recorrido.** Desde el tablero, seleccionar Santiago (13101) en la tabla, abrir sus establecimientos y seleccionar Hospital Clínico San Borja Arriarán (111100). El hospital se eligió por menor código entre los de Santiago con pronóstico ID36 incluido. Se comprobó la selección activa y la presencia del gráfico de demanda en ambas vistas.

| Motor | Versión | Santiago | Hospital | Capturas |
|---|---|---|---|---|
| Chromium | 158.0.8127.18 | HTTP 200 | HTTP 200 | [Santiago](chromium-santiago.png) · [Hospital](chromium-hospital.png) |
| Firefox | 159.0 | HTTP 200 | HTTP 200 | [Santiago](firefox-santiago.png) · [Hospital](firefox-hospital.png) |
| WebKit | 27.2 | HTTP 200 | HTTP 200 | [Santiago](webkit-santiago.png) · [Hospital](webkit-hospital.png) |

- **Santiago.** Para la semana del 15 de noviembre de 2026 se esperan 73 atenciones, entre 58 y 89 con un intervalo de 80%.
- **Hospital.** Para la semana del 15 de noviembre de 2026 se esperan 8,3 atenciones, entre 3,6 y 14 con un intervalo de 80%.

Coincidieron las respuestas de las dos rutas, sus hashes y los resúmenes visibles. El snapshot se mantuvo estable y se registraron cero excepciones de JavaScript sin capturar. El [detalle técnico](SAAD-CP-074.json) conserva rutas redactadas, hashes y versiones.

**Alcance.** La ejecución cubre los tres motores del caso. Edge y las demás versiones exigidas por RNF-CMP-001 quedan fuera de esta corrida.
