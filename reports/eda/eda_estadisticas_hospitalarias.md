# EDA: Estadísticas Hospitalarias REM-20 (DEIS)

Generado por `scripts/eda_estadisticas_hospitalarias.py` (stage `eda_estadisticas_hospitalarias`). No editar a mano. Diccionario: `reports/dictionary/diccionario_estadisticas_hospitalarias.md`.

Fuente: DEIS, repositorio REM-20, «Indicadores Hospitalarios según Servicio de Salud» (SNSS) y «Categorización de Pacientes Hospitalizados Según Riesgo Dependencia». Son estadísticas mensuales y trimestrales consolidadas por establecimiento, no gestión de camas en tiempo real.

## 1. Archivos y período

| RAW | SHA256 (12) |
|---|---|
| `data/raw/estadisticas_hospitalarias/indicadores_hospitalarios_2014_2023.xlsx` | `f4d00bc86086` |
| `data/raw/estadisticas_hospitalarias/indicadores_hospitalarios_2024.xlsx` | `4c4578b81f87` |
| `data/raw/estadisticas_hospitalarias/indicadores_hospitalarios_2025.xlsx` | `71e3a3a7c035` |
| `data/raw/estadisticas_hospitalarias/indicadores_hospitalarios_2026.xlsx` | `5fb17397c3f5` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2024_t1.xlsx` | `2e61da246b02` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2024_t2.xlsx` | `c87b1bad168e` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2024_t3.xlsx` | `ba021d76c4f2` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2024_t4.xlsx` | `c6d5c01da2e2` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2025_t1.xlsx` | `c88a6361d87d` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2025_t2.xlsx` | `cd8a4f3075a7` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2025_t3.xlsx` | `e40c07d32d63` |
| `data/raw/estadisticas_hospitalarias/categorizacion_riesgo_dependencia_2025_t4.xlsx` | `23f6de90a58d` |

Indicadores 2014–2026. Meses publicados por año: 2014: 12, 2015: 12, 2016: 12, 2017: 12, 2018: 12, 2019: 12, 2020: 12, 2021: 12, 2022: 12, 2023: 12, 2024: 12, 2025: 12, 2026: 9. El año en curso (2026) trae **9 meses**: los siguientes quedan nulos en el Parquet, no en cero. La categorización cubre 2024-T1, 2024-T2, 2024-T3, 2024-T4, 2025-T1, 2025-T2, 2025-T3, 2025-T4 (el trimestre viene del nombre de la publicación; el libro solo declara el año).

## 2. Estructura y filas agregadas del origen

Cada libro de indicadores intercala, en las mismas columnas, filas de **detalle** (un nivel de cuidado de un establecimiento) y filas **agregadas** que el origen rotula `Datos País`, `Datos Servicio Salud` y `Datos Establecimiento`. Sumar todas las filas cuenta el mismo dato dos o tres veces. El Parquet conserva solo el detalle; las agregadas se usan para conciliar (sección 3).

| Filas | Cantidad |
|---|---:|
| Detalle (Parquet) | 160.974 |
| Agregadas `establecimiento` (excluidas) | 24.845 |
| Agregadas `pais` (excluidas) | 78 |
| Agregadas `servicio` (excluidas) | 2.262 |

- 208 establecimientos en el período (192–203 por año), 29 Servicios de Salud y 29 niveles de cuidado.
- 0 combinaciones año-establecimiento figuran bajo más de un Servicio de Salud; la llave del Parquet incluye el Servicio.
- Un mismo código de nivel tiene hasta 3 glosas distintas entre años (por ejemplo, en 2014 sin el prefijo `NNN - `): agrupar por `nivel_cuidado_codigo`.
- Valores nulos en el detalle: acumulado 2.222; meses del año en curso aún no publicados incluidos (36.201 celdas mensuales nulas en total). Valores negativos: 0.

## 3. Conciliación del detalle con los agregados publicados

Se reconstruye cada fila agregada sumando el detalle, para los conteos (días cama disponibles y ocupados, días de estada, egresos, fallecidos, traslados) y el promedio de camas disponibles, mes a mes y en el acumulado.

- Agregados comparados: establecimiento 15.138, pais 78, servicio 2.262.
- **Discrepancias: 0.** El detalle reconstruye exactamente todos los agregados en conteos y en cada mes.
- Acumulado distinto de la suma de sus meses (conteos): 0.
- El **acumulado anual del promedio de camas disponibles no es aditivo entre áreas** (415 agregados no coinciden con la suma de sus áreas: establecimiento 245, pais 13, servicio 157). En años completos, el 97,1 % de las áreas cumple `promedio = días cama disponibles del año / días del año`; en el resto la fuente divide por los días de los meses en que el área funcionó. Para camas promedio de un período, recalcular desde los días cama disponibles.

## 4. Definición observada de las razones publicadas

Porcentaje de áreas-año cuya razón publicada coincide (±0,005) con cada fórmula, calculada desde los conteos de la misma fila:

**Indice Ocupacional**

| Año | `100 * ocupados / disponibles` |
|---|---:|
| 2014 | 100,0 % |
| 2015 | 100,0 % |
| 2016 | 100,0 % |
| 2017 | 100,0 % |
| 2018 | 100,0 % |
| 2019 | 100,0 % |
| 2020 | 100,0 % |
| 2021 | 100,0 % |
| 2022 | 100,0 % |
| 2023 | 100,0 % |
| 2024 | 100,0 % |
| 2025 | 100,0 % |
| 2026 | 100,0 % |

**Promedio Días de Estada**

| Año | `estada / (egresos + traslados)` | `estada / egresos` |
|---|---:|---:|
| 2014 | 100,0 % | 32,2 % |
| 2015 | 100,0 % | 31,6 % |
| 2016 | 100,0 % | 30,9 % |
| 2017 | 100,0 % | 31,1 % |
| 2018 | 100,0 % | 30,5 % |
| 2019 | 100,0 % | 29,0 % |
| 2020 | 100,0 % | 27,3 % |
| 2021 | 100,0 % | 26,4 % |
| 2022 | 100,0 % | 27,0 % |
| 2023 | 100,0 % | 26,2 % |
| 2024 | 100,0 % | 25,4 % |
| 2025 | 27,1 % | 100,0 % |
| 2026 | 26,2 % | 100,0 % |

**Letalidad**

| Año | `100 * fallecidos / (egresos + traslados)` | `100 * fallecidos / egresos` |
|---|---:|---:|
| 2014 | 100,0 % | 56,3 % |
| 2015 | 100,0 % | 56,1 % |
| 2016 | 100,0 % | 54,5 % |
| 2017 | 100,0 % | 56,7 % |
| 2018 | 100,0 % | 55,2 % |
| 2019 | 100,0 % | 53,4 % |
| 2020 | 100,0 % | 53,4 % |
| 2021 | 100,0 % | 50,6 % |
| 2022 | 100,0 % | 51,7 % |
| 2023 | 100,0 % | 51,8 % |
| 2024 | 100,0 % | 54,0 % |
| 2025 | 53,1 % | 100,0 % |
| 2026 | 55,4 % | 100,0 % |

**Indice de Rotación**

| Año | `(egresos + traslados) / promedio camas` | `egresos / promedio camas` |
|---|---:|---:|
| 2014 | 50,3 % | 17,2 % |
| 2015 | 54,1 % | 18,3 % |
| 2016 | 56,0 % | 18,8 % |
| 2017 | 54,8 % | 18,2 % |
| 2018 | 54,8 % | 17,7 % |
| 2019 | 55,3 % | 17,6 % |
| 2020 | 55,3 % | 18,0 % |
| 2021 | 55,0 % | 17,5 % |
| 2022 | 50,9 % | 15,5 % |
| 2023 | 49,5 % | 15,8 % |
| 2024 | 53,7 % | 15,2 % |
| 2025 | — | — |
| 2026 | — | — |

Tramos en que una fórmula explica al menos el 99 % de las áreas:

- **Indice Ocupacional**: 2014–2026: `100 * ocupados / disponibles`.
- **Promedio Días de Estada**: 2014–2024: `estada / (egresos + traslados)`; 2025–2026: `estada / egresos`.
- **Letalidad**: 2014–2024: `100 * fallecidos / (egresos + traslados)`; 2025–2026: `100 * fallecidos / egresos`.
- **Indice de Rotación**: 2014–2026: ninguna fórmula explica ≥99 %.

Lectura: cuando una razón cambia de fórmula entre tramos, **su serie publicada no es comparable entre años**; para series largas hay que recalcularla desde los conteos con una definición fija. En el índice de rotación ninguna fórmula explica el 99 % con ±0,005; con ±0,06, `(egresos + traslados) / promedio camas` explica entre 95,3 % y 97,2 % por año. Que la diferencia restante se deba al redondeo del promedio de camas es una hipótesis no verificada. El acumulado de esta razón no se publica en 2025, 2026 (de ahí los nulos del acumulado en la sección 2).

### Definiciones del diccionario oficial REM-20

`data/raw/estadisticas_hospitalarias/diccionario_rem20.xlsx` (SHA256 `6feebecdce70`), publicado en datos.gob.cl. Describe el conjunto en formato largo de ese portal (con `PERIODO` y `MES`), no los libros anchos que usa el pipeline: la correspondencia de cada campo con la glosa del libro es por nombre (inferencia). No cubre la categorización.

| Campo | Glosa del libro | Definición oficial | Fórmula observada |
|---|---|---|---|
| `DIAS_CAMAS_OCUPADAS` | Dias Cama Ocupados | Cantidad de Días en que una cama de un área funcional está siendo ocupada | — |
| `DIAS_CAMAS_DISPONIBLES` | Dias Cama Disponibles | Cantidad de Días en que una cama de un área funcional se encuentra disponible, para ser utilizada por un paciente. | — |
| `DIAS_ESTADA` | Dias de Estada | Total de días en el que los pacientes permanecen haciendo uso de una cama del área funcional | — |
| `NUMERO_EGRESOS` | Numero de Egresos | Total de egresos en el que el paciente abandona el recinto de una de las siguientes formas: - Dado de Alta - Derivado a otro establecimiento - Fallecido | — |
| `EGRESOS_FALLECIDOS` | Egresos Fallecidos | Egresos en el que el paciente abandona el recinto en condición de fallecido | — |
| `TRASLADOS` | Traslados | Movimiento del paciente, donde es transferido a otra área funcional del Establecimiento y no constituye un egreso hospitalario. | — |
| `INDICE_OCUPACIONAL` | Indice Ocupacional | Número de días camas ocupadas respecto a los días cama disponibles, durante un período de tiempo establecido, expresado en porcentaje | 2014–2026: `100 * ocupados / disponibles` |
| `PROMEDIO_CAMAS_DISPONIBLE` | Promedio Cama Disponibles | Promedio de días que una cama del Área Funcional permanece disponible | — |
| `PROMEDIO_DIAS_ESTADA` | Promedio Días de Estada | Promedio de días que un paciente permanece en el Área Funcional | 2014–2024: `estada / (egresos + traslados)`; 2025–2026: `estada / egresos` |
| `LETALIDAD` | Letalidad | Porcentaje de Egresos fallecidos contenidos en el total de Egresos | 2014–2024: `100 * fallecidos / (egresos + traslados)`; 2025–2026: `100 * fallecidos / egresos` |
| `INDICE_ROTACION` | Indice de Rotación | Número de pacientes que pasan por una cama hospitalaria en un período de tiempo determinado. | 2014–2026: sin fórmula exacta |

Lectura: el diccionario define la letalidad sobre el **total de egresos**, lo que coincide con lo publicado desde que cambia la fórmula, no con los años anteriores, que suman traslados al denominador. Define los traslados como movimientos a otra área del mismo establecimiento que **no constituyen egreso**. Sobre los días cama ocupados por sobre los disponibles (sección 5) el diccionario no dice nada.

## 5. Días cama ocupados por sobre los disponibles

- Área-meses con ocupados > disponibles: 1.955 de 172.317 (índice mensual máximo 2.700,00 %).
- Área-meses con ocupados > 0 y disponibles = 0: 17.
- En psiquiatría (418–429 sin el sociosanitario 427): 233 de 10.776 área-meses.

Hecho observado: el REM-20 registra días cama ocupados que superan los disponibles en una fracción pequeña de área-meses. **No es posible determinar con los datos disponibles** si corresponden a camas supletorias, a pacientes en camillas o sillas, a traslados internos o a errores de registro: la fuente no lo desagrega. Tampoco permite saber cuántos pacientes esperan cama en la urgencia (esa espera no es un día cama ocupado de un área de hospitalización).

## 6. Psiquiatría en la Región Metropolitana

Áreas 418–426, 428 y 429 de los Servicios de Salud `Metropolitano *` (se excluye el área sociosanitaria 427). El índice anual se calcula desde los conteos sumados, no promediando índices.

| Año | Días cama ocupados | Días cama disponibles | Índice ocupacional | Egresos + traslados |
|---|---:|---:|---:|---:|
| 2014 | 243.589 | 275.330 | 88,5 % | 6.831 |
| 2015 | 244.944 | 277.069 | 88,4 % | 7.094 |
| 2016 | 249.121 | 284.803 | 87,5 % | 6.942 |
| 2017 | 249.329 | 286.962 | 86,9 % | 7.044 |
| 2018 | 252.793 | 286.745 | 88,2 % | 7.591 |
| 2019 | 253.307 | 287.272 | 88,2 % | 7.432 |
| 2020 | 210.575 | 258.046 | 81,6 % | 5.762 |
| 2021 | 214.166 | 267.704 | 80,0 % | 6.321 |
| 2022 | 205.482 | 254.203 | 80,8 % | 6.542 |
| 2023 | 214.139 | 254.887 | 84,0 % | 7.653 |
| 2024 | 211.834 | 236.333 | 89,6 % | 8.154 |
| 2025 | 217.680 | 243.506 | 89,4 % | 8.367 |
| 2026 (parcial) | 170.997 | 187.537 | 91,2 % | 6.801 |

Por establecimiento, 2025 (último año completo):

| Establecimiento | Código | Índice ocupacional | Días ocupados / disponibles |
|---|---:|---:|---:|
| Hospital Del Salvador de Santiago | 112100 | 99,6 % | 7.270 / 7.300 |
| Hospital Clínico de Niños Dr. Roberto del Río (Santiago, Independencia) | 109101 | 96,7 % | 5.625 / 5.819 |
| Hospital El Pino (Santiago, San Bernardo) | 113180 | 95,5 % | 5.582 / 5.843 |
| Complejo Hospitalario Dr. Sótero del Río (Santiago, Puente Alto) | 114101 | 95,5 % | 17.261 / 18.070 |
| Hospital Barros Luco Trudeau (Santiago, San Miguel) | 113100 | 94,5 % | 9.643 / 10.203 |
| Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta) | 109102 | 94,0 % | 115.342 / 122.722 |
| Hospital Clínico Metropolitano La Florida Dra. Eloísa Díaz Insunza | 114105 | 90,1 % | 5.917 / 6.570 |
| Hospital Dr. Exequiel González Cortés (Santiago, San Miguel) | 113130 | 86,6 % | 3.795 / 4.380 |
| Hospital Clínico San Borja Arriarán | 111100 | 84,9 % | 4.687 / 5.521 |
| Hospital Félix Bulnes Cerda | 110120 | 82,8 % | 12.042 / 14.540 |
| Hospital Psiquiátrico El Peral (Santiago, Puente Alto) | 113170 | 74,8 % | 26.788 / 35.818 |
| Hospital de Niños Dr. Luis Calvo Mackenna | 112102 | 74,5 % | 2.286 / 3.070 |
| Hospital de Til Til | 109104 | 39,5 % | 1.442 / 3.650 |

Área-meses de psiquiatría RM con ocupados > disponibles: 88 de 3.444 (Hospital Clínico San Borja-Arriarán (Santiago, Santiago), Hospital Dr. Exequiel González Cortés (Santiago, San Miguel), Hospital Psiquiátrico El Peral (Santiago, Puente Alto), Instituto Psiquiátrico Dr José Horwitz Barak (Santiago, Recoleta), Instituto Psiquiátrico Dr. José Horwitz Barak (Santiago, Recoleta)).

## 7. Coherencia con la dotación de camas

Mismo `establecimiento_codigo` y mismo código de área funcional que `dotacion_camas_snss` (stage `clean_dotacion_camas`). Se compara el promedio anual de camas disponibles del REM-20 con la dotación declarada ese año:

- Áreas-año comparadas: 13.052; a 1 cama o menos: 59,8 %; promedio disponible más de 10 % bajo la dotación: 20,9 %.
- Psiquiatría: 807 áreas-año, a 1 cama o menos: 55,8 %.

Lectura: la dotación es un stock declarado; las camas disponibles del REM-20 descuentan las que no estuvieron habilitadas en el período. Son magnitudes distintas aunque cercanas.

## 8. Categorización según riesgo-dependencia (CUDYR)

El instrumento CUDYR clasifica a cada paciente hospitalizado por **riesgo** (A máximo, B alto, C mediano, D bajo) y **dependencia** (1 total, 2 parcial, 3 autosuficiencia parcial); se aplica a quienes ocupan una cama más de 8 horas. Siguiendo la agrupación de González et al. (2024), se lee como pacientes **críticos** A1, A2, A3, B1 y B2; de **cuidados medios** B3, C1 y C2; y de **cuidados básicos** C3, D1, D2 y D3. Fuente de la definición: González P, Kappes M, Gallardo-Vargas C. Cuidados según dependencia y riesgo en hospitales de baja complejidad del Servicio de Salud Reloncaví, Chile. *Ciencia y Enfermería*. 2024;30:31. doi:[10.29393/CE30-31CSPC30031](https://doi.org/10.29393/CE30-31CSPC30031).

| Trimestre | Filas | Establecimientos | Categorizaciones |
|---|---:|---:|---:|
| 2024-T1 | 1.113 | 192 | 1.708.566 |
| 2024-T2 | 1.106 | 191 | 1.733.438 |
| 2024-T3 | 1.104 | 191 | 1.834.643 |
| 2024-T4 | 1.099 | 191 | 1.799.047 |
| 2025-T1 | 1.106 | 190 | 1.739.425 |
| 2025-T2 | 1.107 | 191 | 1.841.772 |
| 2025-T3 | 1.101 | 191 | 1.826.893 |
| 2025-T4 | 1.098 | 191 | 1.771.480 |

- Total igual a la suma de las 12 categorías en todas las filas: sí. Libros trimestrales con contenido distinto entre sí (SHA256): sí.
- Distribución nacional: críticos 34,5 %, medios 51,2 %, básicos 14,3 %. Psiquiatría nacional: 22,0 % / 42,9 % / 35,1 %; psiquiatría RM: 13,5 % / 56,7 % / 29,8 %.
- El libro **no trae código de establecimiento**, solo nombres. Cruzando por año, Servicio de Salud y nombre exacto con los indicadores: 0 de 384 pares año-establecimiento sin código y 0 ambiguos.
- Categorizaciones del trimestre / días cama ocupados del mismo trimestre y nivel (mediana nacional): 0,93 en áreas no psiquiátricas y 0,70 en psiquiatría.

Inferencia (no declarada por la fuente): la cercanía de esa razón a 1 en las áreas generales es coherente con que cada categorización corresponda a un paciente-día categorizado, no a un paciente distinto; en psiquiatría la cobertura es menor. El libro no lo define: no es posible determinarlo con los datos disponibles.

## 9. Advertencias para el cálculo de utilización

- Usar solo el detalle (Parquet). Las filas agregadas del origen ya están excluidas.
- Sumar solo conteos. Recalcular índices desde los conteos sumados; no promediar ni sumar razones, ni usar el acumulado del promedio de camas entre áreas.
- El promedio de estada y la letalidad publicados cambian de definición entre años (sección 4).
- 2026 es parcial (9 meses) y el DEIS reemplaza el corte cada mes.
- Los días cama ocupados miden camas de áreas de hospitalización. No miden pacientes en espera en la urgencia ni hospitalizaciones en camillas fuera de esas áreas, salvo lo que el registro incluya sin distinguirlo (sección 5).
- Urgencias y estos indicadores comparten `establecimiento_codigo`, pero el ID42 cuenta indicaciones de hospitalización en la urgencia de origen, no ingresos al área de ese hospital: la relación es ecológica.
