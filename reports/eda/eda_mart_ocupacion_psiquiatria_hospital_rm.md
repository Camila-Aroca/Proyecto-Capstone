# EDA: `mart_ocupacion_psiquiatria_hospital_rm`

Generado por `scripts/eda_mart_ocupacion_psiquiatria_hospital_rm.py` (stage `eda_mart_ocupacion_psiquiatria_hospital_rm`). No editar a mano. Diccionario: `reports/dictionary/diccionario_mart_ocupacion_psiquiatria_hospital_rm.md`.

## 1. Cobertura

3.444 filas área-mes: 28 áreas de psiquiatría de 14 hospitales de la oferta de urgencia RM, de 2014-01 a 2026-09 (último mes publicado por el DEIS). 31 hospitales de la oferta no tienen áreas de psiquiatría en el REM-20 (o no son del SNSS) y no aparecen.

## 2. Verificación del cálculo

`camas_ocupadas_promedio = días cama ocupados / días del mes` es exacto: los días cama del mes son la suma diaria de camas (diccionario REM-20). Como prueba de que la fuente usa esa misma definición, se recalcula `días cama disponibles / días del mes` en cada área y mes, y se compara con el «Promedio Cama Disponibles» que el DEIS publica para esa área (2 decimales):

- Área-mes comparados: 3.444; diferencia máxima 0,0048 camas (tolerancia de redondeo 0,005); fuera de tolerancia: **0**.
- `camas_libres_promedio = (días disponibles − días ocupados) / días del mes`: misma identidad. Negativa = más días cama ocupados que disponibles registrados en el mes.

## 3. Saturación por área

Últimos 12 meses publicados. **Sin holgura**: menos de 1 cama libre por día en promedio del mes (umbral en camas, comparable entre áreas chicas y grandes). **Sobre la capacidad**: más días cama ocupados que disponibles. Ambos se cuentan solo en los meses **con camas disponibles**: un área con 0 días cama disponibles no estuvo habilitada, no saturada. Índice del período como razón de sumas.

| Hospital | Área | Camas disponibles (prom.) | Camas libres (prom. diario) | Índice | Meses sin holgura | Meses sobre la capacidad |
|---|---|---:|---:|---:|---:|---:|
| Hospital Clínico San Borja Arriarán | 421 - Área Psiquiatría Infanto-adolescente corta estadía | 4,4 | 0,00 | 100,0 % | 12 de 12 | 0 |
| Hospital Clínico de Niños Dr. Roberto del Río (Santiago, Independencia) | 421 - Área Psiquiatría Infanto-adolescente corta estadía | 12,0 | 0,02 | 99,8 % | 12 de 12 | 0 |
| Hospital Clínico de Niños Dr. Roberto del Río (Santiago, Independencia) | 422 - Área Psiquiatría Infanto-adolescente mediana estadía | 3,9 | 0,02 | 99,6 % | 12 de 12 | 0 |
| Hospital Del Salvador de Santiago | 418 - Área Psiquiatría Adulto Corta estadía | 20,0 | 0,10 | 99,5 % | 12 de 12 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 423 - Área Psiquiatría Forense Adulto evaluación e inicio tto. | 39,0 | 0,33 | 99,2 % | 12 de 12 | 0 |
| Hospital de Niños Dr. Luis Calvo Mackenna | 429 - Área de Hospitalización de Cuidados Intensivos en Psiquiatría Infanto Adolescente | 7,5 | 0,27 | 96,4 % | 12 de 12 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 424 - Área Psiquiatría Forense Adulto tratamiento | 40,0 | 0,32 | 99,2 % | 11 de 12 | 0 |
| Hospital Clínico Metropolitano La Florida Dra. Eloísa Díaz Insunza | 418 - Área Psiquiatría Adulto Corta estadía | 18,0 | 0,55 | 96,9 % | 11 de 12 | 0 |
| Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto) | 421 - Área Psiquiatría Infanto-adolescente corta estadía | 11,9 | 0,67 | 94,4 % | 11 de 12 | 0 |
| Hospital El Pino (Santiago, San Bernardo) | 418 - Área Psiquiatría Adulto Corta estadía | 16,0 | 0,63 | 96,0 % | 8 de 12 | 0 |
| Hospital  Félix Bulnes Cerda | 421 - Área Psiquiatría Infanto-adolescente corta estadía | 12,0 | 0,94 | 92,1 % | 8 de 12 | 0 |
| Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto) | 418 - Área Psiquiatría Adulto Corta estadía | 37,8 | 1,11 | 97,1 % | 7 de 12 | 0 |
| Hospital Clínico Metropolitano El Carmen Doctor Luis Valentín Ferrada | 428 - Área de Hospitalización de Cuidados Intensivos en Psiquiatría Adulto | 20,9 | 0,72 | 96,5 % | 7 de 9 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 420 - Área Psiquiatría Adulto Larga estadía | 7,7 | 0,41 | 94,7 % | 7 de 7 | 0 |
| Hospital Barros Luco Trudeau (Santiago, San Miguel) | 418 - Área Psiquiatría Adulto Corta estadía | 28,0 | 1,11 | 96,0 % | 6 de 12 | 0 |
| Hospital Dr. Exequiel González Cortés (Santiago, San Miguel) | 421 - Área Psiquiatría Infanto-adolescente corta estadía | 12,0 | 1,17 | 90,3 % | 6 de 12 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 426 - Área Psiquiatría Forense Infanto Adolescente tratamiento | 12,0 | 1,20 | 90,1 % | 5 de 12 | 0 |
| Hospital Clínico San Borja Arriarán | 418 - Área Psiquiatría Adulto Corta estadía | 10,6 | 2,14 | 79,7 % | 2 de 12 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 418 - Área Psiquiatría Adulto Corta estadía | 229,4 | 10,55 | 95,4 % | 0 de 12 | 0 |
| Hospital Psiquiátrico El Peral (Santiago, Puente Alto) | 420 - Área Psiquiatría Adulto Larga estadía | 55,6 | 5,99 | 89,2 % | 0 de 12 | 0 |
| Hospital  Félix Bulnes Cerda | 418 - Área Psiquiatría Adulto Corta estadía | 28,0 | 4,00 | 85,7 % | 0 de 12 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 428 - Área de Hospitalización de Cuidados Intensivos en Psiquiatría Adulto | 16,0 | 6,68 | 58,3 % | 0 de 12 | 0 |
| Hospital Psiquiátrico El Peral (Santiago, Puente Alto) | 419 - Área Psiquiatría Adulto Mediana estadía | 38,3 | 17,07 | 55,5 % | 0 de 12 | 0 |
| Hospital Comunitario de Til Til | 421 - Área Psiquiatría Infanto-adolescente corta estadía | 10,0 | 6,43 | 35,5 % | 0 de 12 | 0 |

Área-mes sin camas disponibles en todo el período (excluidos de la saturación): 76.

Lectura: el total de un hospital puede ocultar áreas saturadas (las camas libres de un área no sirven a pacientes de otra, por ejemplo entre forense y corta estadía). Los días cama ocupados cuentan pacientes en camas de áreas de hospitalización: quien espera en la urgencia en camilla, silla o sillón no ocupa una de esas camas y no queda registrado. Por definición del indicador, la ocupación observada es entonces un piso de la demanda de camas; la fuente no cuantifica esa espera, así que su magnitud no es determinable con estos datos.

En todo el período hay **88 área-mes sobre la capacidad**, pero solo 6 hospital-mes al sumar las áreas: el agregado compensa un área desbordada con camas libres de otra. Por área:

| Hospital | Área | Meses sobre la capacidad | Primero | Último | Índice máximo |
|---|---:|---:|---|---|---:|
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 424 | 44 | 2014-01 | 2017-12 | 132,8 % |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 423 | 19 | 2014-01 | 2018-11 | 101,4 % |
| Hospital Clínico San Borja Arriarán | 421 | 14 | 2016-04 | 2019-10 | 106,2 % |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 426 | 4 | 2014-07 | 2019-04 | 118,8 % |
| Hospital Dr. Exequiel González Cortés (Santiago, San Miguel) | 421 | 4 | 2018-09 | 2019-05 | 101,7 % |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 425 | 1 | 2015-02 | 2015-02 | 107,1 % |
| Hospital Clínico San Borja Arriarán | 418 | 1 | 2015-12 | 2015-12 | 100,8 % |
| Hospital Psiquiátrico El Peral (Santiago, Puente Alto) | 419 | 1 | 2015-06 | 2015-06 | 126,0 % |

## 4. Ocupación agregada de los hospitales del mart

Razón de sumas (`100 · Σ ocupados / Σ disponibles`), no promedio de índices:

| Año | Índice ocupacional |
|---|---:|
| 2014 | 88,5 % |
| 2015 | 88,4 % |
| 2016 | 87,5 % |
| 2017 | 86,9 % |
| 2018 | 88,2 % |
| 2019 | 88,2 % |
| 2020 | 81,6 % |
| 2021 | 80,0 % |
| 2022 | 80,8 % |
| 2023 | 84,0 % |
| 2024 | 89,6 % |
| 2025 | 89,4 % |
| 2026 | 91,2 % |

## 5. Último mes por hospital

| Hospital | Código | Hasta | Meses (huecos) | Ocupadas / disponibles (prom. diario) | Índice | Dotación declarada | En pronóstico de hospitalizaciones |
|---|---:|---|---:|---:|---:|---:|---|
| Hospital Clínico de Niños Dr. Roberto del Río (Santiago, Independencia) | 109101 | 2026-09 | 153 (0) | 15,6 / 15,6 | 100,0 % | 16 | sí |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 109102 | 2026-09 | 153 (0) | 315,2 / 337,6 | 93,4 % | 408 | sí |
| Hospital Comunitario de Til Til | 109104 | 2026-09 | 141 (0) | 4,5 / 10,0 | 45,0 % | 10 | no |
| Hospital  Félix Bulnes Cerda | 110120 | 2026-09 | 153 (0) | 35,6 / 40,0 | 88,9 % | 40 | no |
| Hospital Clínico San Borja Arriarán | 111100 | 2026-09 | 153 (0) | 10,2 / 15,1 | 67,8 % | 17 | no |
| Hospital Clínico Metropolitano El Carmen Doctor Luis Valentín Ferrada | 111101 | 2026-09 | 9 (0) | 19,7 / 20,0 | 98,3 % | — | sí |
| Hospital Del Salvador de Santiago | 112100 | 2026-09 | 153 (0) | 20,0 / 20,0 | 100,0 % | 20 | sí |
| Hospital de Niños Dr. Luis Calvo Mackenna | 112102 | 2026-09 | 153 (0) | 9,1 / 9,2 | 99,3 % | 9 | sí |
| Hospital Barros Luco Trudeau (Santiago, San Miguel) | 113100 | 2026-09 | 153 (0) | 26,9 / 28,0 | 96,1 % | 28 | sí |
| Hospital Dr. Exequiel González Cortés (Santiago, San Miguel) | 113130 | 2026-09 | 117 (0) | 11,3 / 12,0 | 94,4 % | 12 | no |
| Hospital Psiquiátrico El Peral (Santiago, Puente Alto) | 113170 | 2026-09 | 153 (0) | 66,6 / 84,0 | 79,3 % | 98 | no |
| Hospital El Pino (Santiago, San Bernardo) | 113180 | 2026-09 | 153 (0) | 15,8 / 16,0 | 98,8 % | 16 | sí |
| Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto) | 114101 | 2026-09 | 153 (0) | 50,3 / 51,7 | 97,3 % | 51 | sí |
| Hospital Clínico Metropolitano La Florida Dra. Eloísa Díaz Insunza | 114105 | 2026-09 | 153 (0) | 17,5 / 18,0 | 97,0 % | 18 | sí |

- Hospitales con ocupación en el REM-20 pero **sin cifra de dotación** de psiquiatría: 111101. Hecho observado; la causa (área habilitada después del libro de dotación, diferencia de registro u otra) no es determinable con estos datos.

## 6. Nivel de colapso por hospital

Ocupación de las camas de psiquiatría de cada hospital en la ventana común 2025-10 a 2026-09 (últimos 12 meses publicados), como razón de sumas sobre los área-mes con camas habilitadas. **Holgura** < 85 %; **presión** de 85 a 90 %; **saturación** ≥ 90 %; **sobre la capacidad** si algún área registró más días cama ocupados que disponibles en la ventana. Umbrales de la literatura, no ajustados a estos datos: 85 % es la ocupación máxima recomendada para salas de psiquiatría (Royal College of Psychiatrists) y desde la que Bagust, Place y Posnett (BMJ 1999;319:155-8) observan riesgos discernibles; con 90 % o más de ocupación media ese estudio espera escasez regular de camas y crisis periódicas. Ese estudio simula un hospital de agudos sin pacientes psiquiátricos: es una referencia, no una calibración local.

| Hospital | Nivel | Ocupación | Meses | Área-mes sobre la capacidad |
|---|---|---:|---:|---:|
| Hospital Clínico de Niños Dr. Roberto del Río (Santiago, Independencia) | Saturación | 99,7 % | 12 | 0 |
| Hospital Del Salvador de Santiago | Saturación | 99,5 % | 12 | 0 |
| Hospital Clínico Metropolitano La Florida Dra. Eloísa Díaz Insunza | Saturación | 96,9 % | 12 | 0 |
| Hospital Clínico Metropolitano El Carmen Doctor Luis Valentín Ferrada | Saturación | 96,5 % | 9 | 0 |
| Hospital de Niños Dr. Luis Calvo Mackenna | Saturación | 96,4 % | 12 | 0 |
| Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto) | Saturación | 96,4 % | 12 | 0 |
| Hospital Barros Luco Trudeau (Santiago, San Miguel) | Saturación | 96,0 % | 12 | 0 |
| Hospital El Pino (Santiago, San Bernardo) | Saturación | 96,0 % | 12 | 0 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | Saturación | 94,3 % | 12 | 0 |
| Hospital Dr. Exequiel González Cortés (Santiago, San Miguel) | Saturación | 90,3 % | 12 | 0 |
| Hospital  Félix Bulnes Cerda | Presión | 87,6 % | 12 | 0 |
| Hospital Clínico San Borja Arriarán | Presión | 85,6 % | 12 | 0 |
| Hospital Psiquiátrico El Peral (Santiago, Puente Alto) | Holgura | 75,5 % | 12 | 0 |
| Hospital Comunitario de Til Til | Holgura | 35,5 % | 12 | 0 |

Lectura: el nivel resume al hospital; un área puede estar saturada aunque el hospital no (sección 3).

## 7. Áreas sin dotación declarada

| Hospital | Área | En el REM-20 desde | Causa observada |
|---|---|---:|---|
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 421 · Área Psiquiatría Infanto-adolescente corta estadía | 2014 | El libro de dotación 2025 lista el área sin cifra. |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 425 · Área Psiquiatría Forense Infanto Adolescente evaluación e inicio tto. | 2015 | El área no figura en el libro de dotación 2025; la causa no es determinable con estos datos. |
| Hospital Clínico Metropolitano El Carmen Doctor Luis Valentín Ferrada | 428 · Área de Hospitalización de Cuidados Intensivos en Psiquiatría Adulto | 2026 | El área se habilitó en 2026, después del último año del libro de dotación (2025): aún no tiene dotación declarada. |
| Hospital de Niños Dr. Luis Calvo Mackenna | 421 · Área Psiquiatría Infanto-adolescente corta estadía | 2014 | El libro de dotación 2025 lista el área sin cifra. |
| Hospital Clínico Metropolitano La Florida Dra. Eloísa Díaz Insunza | 428 · Área Hospitalización de Cuidados Intensivos en Psiquiatría Adulto | 2022 | El área no figura en el libro de dotación 2025; la causa no es determinable con estos datos. |

¿Se puede estimar la dotación faltante con las camas disponibles del REM-20? Se prueba en todas las áreas-año que tienen ambas cifras, estimando la dotación con la mediana o el máximo del promedio mensual de camas disponibles del año:

| Estimador | Alcance | Áreas-año | Acierto exacto | A ±1 cama | Error absoluto medio |
|---|---|---:|---:|---:|---:|
| mediana | todas | 13.048 | 58,4 % | 68,7 % | 3,19 camas |
| mediana | psiquiatría | 807 | 56,8 % | 66,7 % | 2,82 camas |
| maximo | todas | 13.048 | 55,0 % | 66,3 % | 3,94 camas |
| maximo | psiquiatría | 807 | 59,9 % | 69,0 % | 2,78 camas |

Lectura: las camas disponibles no reproducen la dotación declarada con la precisión necesaria para publicarla como dato (en psiquiatría, una de cada tres áreas-año difiere en más de una cama). Por eso no se imputa la dotación faltante: el tablero muestra las camas disponibles del REM-20 como capacidad observada y explica la causa de la ausencia.

## 8. Relación con el pronóstico de hospitalizaciones

De los 12 hospitales con pronóstico de hospitalizaciones (ID42), 9 tienen ocupación de psiquiatría en este mart; sin ella: 109100, 110150, 113150 (sin áreas de psiquiatría en el REM-20).

Lectura: son magnitudes distintas. El ID42 cuenta, por semana, hospitalizaciones indicadas en la urgencia (un flujo, registrado donde ocurrió la urgencia). Este mart cuenta, por mes, pacientes en cama de psiquiatría en promedio por día (un stock, de cualquier origen). Por eso el tablero los muestra en gráficos separados y no en un mismo eje.

## Advertencias

- No es ocupación en tiempo real: es el último mes publicado por el DEIS.
- Es un promedio mensual: un mes sin holgura puede incluir días con camas libres y días sobre la capacidad.
- Disponibles (REM-20) no es dotación (libro de camas): la primera descuenta las camas no habilitadas.
