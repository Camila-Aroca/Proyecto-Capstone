# Diccionario de datos: `mart_ocupacion_psiquiatria_hospital_rm`

- **Ruta:** `data/processed/marts/mart_ocupacion_psiquiatria_hospital_rm.parquet`.
- **Constructor:** `src/data/build_mart_ocupacion_psiquiatria_hospital_rm.py`, stage `build_mart_ocupacion_psiquiatria_hospital_rm` (upstream: `clean_estadisticas_hospitalarias`, `build_dim_oferta_urgencia_rm`). EDA: `reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm.md`.
- **Propósito:** ocupación mensual de las camas de psiquiatría de los hospitales de la oferta de urgencia RM, para mostrar junto al pronóstico de hospitalizaciones por establecimiento (gráfico compañero, no en el mismo eje) y medir la brecha de capacidad.
- **Fuente:** detalle de `indicadores_hospitalarios_snss` (REM-20, DEIS). Solo establecimientos del SNSS.

**Grano:** una fila por área de psiquiatría de un hospital y mes publicado. El grano es el área, no el hospital, porque un área puede estar saturada aunque el total del hospital no lo esté (en el snapshot vigente hay 88 área-mes sobre la capacidad, pero solo 6 hospital-mes al sumar). El total del hospital se obtiene sumando días cama de sus áreas (`por_hospital`). **Llave lógica verificada:** `establecimiento_codigo, nivel_cuidado_codigo, ano, mes`.

| Columna | Tipo | Semántica |
|---|---|---|
| `establecimiento_codigo` | int64 | Hospital de `dim_oferta_urgencia_rm` (`tipo_establecimiento = "Hospital"`). |
| `nivel_cuidado_codigo` | int32 | Área de psiquiatría: nivel de cuidado cuyo nombre contiene «Psiquiatr» (mismo criterio que `dim_camas_psiquiatria_hospital_rm`; excluye el área sociosanitaria 427). Mismo catálogo que `area_funcional_codigo` de la dotación. |
| `nivel_cuidado` | string | Glosa del área tal como la publica el REM-20 ese año. |
| `ano`, `mes` | int32 | Mes publicado. Un mes aún no publicado no genera fila: no es cero. |
| `fecha_inicio_mes` | date32 | Primer día del mes. |
| `dias_mes` | int32 | Días del mes (considera años bisiestos). |
| `dias_cama_ocupados` | float64 | Días cama ocupados del área en el mes (REM-20). |
| `dias_cama_disponibles` | float64 | Días cama disponibles del área en el mes (REM-20). |
| `camas_ocupadas_promedio` | float64 | `dias_cama_ocupados / dias_mes`: pacientes en cama por día, en promedio del mes. |
| `camas_disponibles_promedio` | float64 | `dias_cama_disponibles / dias_mes`. |
| `camas_libres_promedio` | float64 | `camas_disponibles_promedio − camas_ocupadas_promedio`: la brecha. Negativa = más días cama ocupados que disponibles. |
| `indice_ocupacional` | float64 | `100 · ocupados / disponibles`. Nulo si el área no tuvo camas disponibles ese mes. |

## Por qué el cálculo es exacto

Según el diccionario REM-20, los días cama ocupados de un mes son la cantidad de días en que cada cama estuvo ocupada; sumados sobre el área equivalen a la suma diaria de camas con paciente, `O = Σ_d o_d`. Dividir por los días del mes da el promedio diario exacto, `Ō = O / D`, sin supuestos de distribución. Igual con los disponibles. Que la fuente use esa misma definición se **verifica** en cada ejecución: el «Promedio Cama Disponibles» que publica el DEIS por área y mes debe coincidir con `dias_cama_disponibles / dias_mes` dentro del redondeo de 2 decimales (±0,005). Si un área-mes no cumple, la etapa falla. En el snapshot vigente, la mayor diferencia es 0,0048 en 3.444 área-mes.

Al agregar áreas (hospital, región) se suman días cama y se recalculan promedio e índice; nunca se promedian índices, porque eso pondera igual un área de 4 camas que una de 230.

## Saturación (API y EDA)

Calculada con `resumen_areas` sobre un período (la ventana del gráfico en la API; los últimos 12 meses en el EDA):

- **Sin holgura:** menos de 1 cama libre por día en promedio del mes (`UMBRAL_HOLGURA_CAMAS`). El umbral es en camas y no en porcentaje, para leer igual un área de 4 camas y una de 230.
- **Sobre la capacidad:** camas libres < 0.
- Ambos se cuentan solo en los meses **con camas disponibles**. Un área con 0 días cama disponibles no estuvo habilitada (cerrada o sin camas): no está saturada. En el snapshot vigente hay 76 área-mes así.
- La API agrega a cada área su **dotación declarada** del último año del libro de dotación (mismo código de área funcional). La suma de las áreas coincide con `dim_camas_psiquiatria_hospital_rm` por construcción.

## Nivel de colapso por hospital (API y EDA)

`nivel_colapso` resume cada hospital en una ventana común, los últimos 12 meses publicados, para que los niveles sean comparables:

- **Índice:** `100 · Σ ocupados / Σ disponibles` sobre los área-mes con camas disponibles (razón de sumas).
- **Niveles:** holgura (< 85 %), presión (85 % a < 90 %), saturación (≥ 90 %) y sobre la capacidad (algún área-mes de la ventana con más días cama ocupados que disponibles; prima sobre los demás porque es un hecho observado).
- **Umbrales de la literatura, no ajustados a estos datos.** 85 % es la ocupación máxima recomendada para salas de psiquiatría por el Royal College of Psychiatrists, y desde ella Bagust, Place y Posnett (*BMJ* 1999;319:155-8) observan riesgos discernibles. Con 90 % o más de ocupación media, ese estudio espera escasez regular de camas y crisis periódicas. El estudio simula un hospital de agudos sin pacientes psiquiátricos: es una referencia, no una calibración local.
- El nivel resume al hospital: un área puede estar saturada aunque el hospital no (p. ej., el área infanto-adolescente del Hospital San Borja Arriarán, al 100 % todo el año, en un hospital en «presión»).

## Dotación ausente

La API y el EDA informan, para cada área sin dotación declarada en el último año del libro, la causa observada: el libro lista el área sin cifra; el área aparece en el REM-20 después del último año del libro (caso del área 428 del Hospital El Carmen, habilitada en 2026 con libro hasta 2025); o el área no figura en el libro, sin causa determinable. **No se imputa la dotación faltante.** Un backtest sobre las áreas-año con ambas cifras muestra que las camas disponibles del REM-20 la reproducen con exactitud solo en el 60 % de los casos de psiquiatría (69 % a ±1 cama, con el mejor estimador), insuficiente para publicarla como dato. En esos casos el tablero usa las camas disponibles como capacidad observada y explica la causa.

## Advertencias de interpretación

- **Es un piso de la demanda de camas.** Un paciente que espera cama en la urgencia, en camilla, silla o sillón, no ocupa una cama de un área de hospitalización y no queda registrado aquí. Es una inferencia de la definición del indicador; la fuente no cuantifica esa espera.
- **Promedio mensual, no tiempo real.** Un mes sin holgura puede incluir días con camas libres y días sobre la capacidad. El último mes es el último publicado por el DEIS.
- **Stock, no flujo.** Cuenta pacientes en cama de cualquier origen. No es comparable uno a uno con el ID42 de Urgencias (hospitalizaciones indicadas por semana en la urgencia de origen).
- **Disponibles no es dotación.** Las disponibles del REM-20 descuentan camas no habilitadas. Puede haber un área con dotación declarada y sin camas disponibles (p. ej., el área 420 del Instituto Horwitz desde mayo de 2026), o un área con ocupación y sin cifra en el libro de dotación (sección «Dotación ausente»).
