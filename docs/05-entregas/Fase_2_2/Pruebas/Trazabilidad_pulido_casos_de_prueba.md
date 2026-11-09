# Trazabilidad del pulido frente al catálogo CP-SAAD-2026

Relaciona las correcciones del ciclo de pulido (9 de noviembre de 2026) con los casos del
[Plan de Pruebas PP-SAAD-2026](SAAD_Plan_de_Pruebas_Fase_2_2_AWS.docx) y del
[Catálogo de 70 casos](SAAD_Casos_de_Prueba_70_Fase_2_2_AWS.docx).

**Alcance de este registro.** Es una pre-verificación en el entorno LOCAL (control) definido por
el plan, no la ejecución oficial. Ningún caso queda «Aprobado» por esta tabla: el plan exige
ejecutarlos en AWS-PRE con evidencia por caso. Sirve para llegar al ciclo 1 sin defectos ya
conocidos y para saber qué casos reejecutar después de cada corrección.

## Correcciones y casos que afectan

| Corrección | Casos | Qué cambió | Reejecutar |
|---|---|---|---|
| Pronóstico por establecimiento vencido ya no deja la vista sin datos | CP-014, CP-015, CP-036, CP-037, CP-041 | Si falta el pronóstico: 503 con la etapa a ejecutar (igual que antes). Si existe pero quedó desactualizado frente a los datos: se sirve sin los horizontes ya observados, `/establecimientos-meta` lo informa (`vigente: false`, motivo y etapa) y el tablero muestra un aviso visible y el estado «Pronóstico desactualizado». Nunca se presenta como vigente. | CP-014, CP-015, CP-036 |
| Suicidios mantiene el 503 con pronóstico vencido | CP-049 | Sin cambio, a propósito: CP-049 exige 503 informativo para suicidios, por la sensibilidad del dato. | — |
| Frescura del dato en establecimientos | CP-035, CP-056, CP-058 | «Datos hasta la semana X» sale de los datos cargados, no del manifiesto, y excluye la semana 53 de borde de año (el DEIS codifica el 1-3 de enero como semana 53 del año en curso). | CP-035, CP-058 |
| Landing y «Alcance» alineados con lo implementado | CP-028, CP-029 | La landing y el bloque de alcance siguen la cadena demanda → hospitalización → ocupación → propuesta, e incluyen ocupación REM-20, propuesta anual de camas y suicidios como contexto. Se retiró «Estimación de camas necesarias · en desarrollo», reemplazada por la propuesta publicada. Fuera del MVP: decisiones de inversión y ocupación en tiempo real. | CP-028 |
| Componentes divididos y estilo unificado | CP-037 a CP-046 (regresión) | `VistaEstablecimientos` (655 líneas) y `PanelOcupacion` (590) pasan a piezas de menos de 270 líneas en `components/establecimientos/` y `components/ocupacion/`, sin cambio visible. Comillas dobles en todo el frontend. `npm test` corre las pruebas del frontend. | CP-037 a CP-046 |

## Pre-verificación local de la API

Ejecutada contra la API local con los outputs regenerados el 9 de noviembre de 2026
(Urgencias hasta la semana 39 de 2026).

| Caso | Resultado local | Observado |
|---|---|---|
| CP-017 | OK | `/salud`: datos y pronóstico «listo». |
| CP-018 | OK | `/meta` con modelo, fecha de cálculo y 4 advertencias. |
| CP-019 | OK | 52 comunas más la región. |
| CP-020 | OK | Serie RM con 52 semanas de historia y pronóstico. |
| CP-021 | OK | Serie inexistente 404; `semanas=0` y `semanas=99999` responden 422. |
| CP-022 | OK | `/pronosticos` con 408 filas. |
| CP-023 | OK | Nivel reciente de Recoleta igual en el resumen y en la serie (358,8). |
| CP-024 | OK | GeoJSON `FeatureCollection` con 52 comunas. |
| CP-025 | OK | Camas de psiquiatría RM: 645. |
| CP-026 | OK | `/calendario-eventos` responde 200. |
| CP-053 | OK | Horizontes de la serie (1 a 8) iguales a los de la meta. |
| CP-054 | OK | 0 de 408 pronósticos con límites fuera de orden. |
| CP-037 / CP-058 | OK | Meta de establecimientos con vigencia, semana observada y fecha de generación. |

Las vistas (bloques D y E) se revisaron con capturas en Chrome a 1440 px: navegación landing →
tablero → establecimientos con parámetros en la URL, hospitalizaciones del Horwitz con ocupación
por área y propuesta de camas, sin errores de consola. CP-051 ya se cumple en el código: el bloque
de suicidios muestra la línea de prevención *4141.

## Hallazgos para el registro de defectos

| Severidad sugerida | Casos | Hallazgo |
|---|---|---|
| Alta → corregido | CP-011, CP-013 | El pipeline completo se detenía en `build_cobertura_urgencia_comuna`: el SUR Juan Pablo II (Lampa, código 202306) es nuevo (funciona desde julio de 2025, incorporado al maestro en mayo de 2026) y el DEIS no publica sus coordenadas. Corrección: la etapa lo cuenta en su comuna, lo excluye de las distancias sin imputarlo y lo nombra en el reporte; sigue fallando si el faltante reportó ID36 o si son más de 3. Verificado: `--stage all` termina sin errores y una segunda corrida hace `SKIP` en las 56 etapas. Pendiente: geocodificarlo desde una fuente verificable para incluirlo en las distancias. |
| Media | CP-014 | Cada snapshot nuevo de Urgencias vence los pronósticos persistidos. Con la corrección de arriba la vista de establecimientos ya no queda vacía, pero el refresh en AWS debe regenerar `forecast_establecimientos_sm` y `forecast_suicidios` en la misma ejecución. |
