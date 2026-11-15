# EDA de los marts de egresos F00-F99 de residentes RM y del contraste de camas

Datasets: `data/processed/marts/mart_egresos_f00_f99_rm_anual.parquet`, `data/processed/marts/mart_egresos_f00_f99_rm_desglose.parquet` y `data/processed/marts/contraste_camas_psiquiatria_rm.parquet`
(diccionarios en `reports/dictionary/diccionario_mart_egresos_f00_f99_rm.md` y
`reports/dictionary/diccionario_contraste_camas_psiquiatria_rm.md`). Script:
`scripts/eda_mart_egresos_f00_f99_rm.py`. Los egresos son registros publicados, no pacientes únicos, y el
territorio es la comuna de **residencia**: no hay enlace por paciente ni por establecimiento.

## Forma y llaves (observado)

- Anual: 318 filas = 53 territorios (52 comunas y la región `RM`) x 6 años (2020-2025).
- Desglose: 7399 filas. Categorías por dimensión: {'grupo_diagnostico': 11, 'grupo_edad': 10, 'prevision': 5, 'sexo': 3}.
- Duplicados de la llave `series_id, ano`: 0. Duplicados de `series_id, ano, dimension, categoria`: 0.
- `(series_id, ano)` del desglose sin fila en el anual: 0.
- Filas con población nula por año: {2020: 53}; población y tasa nulas a la vez en todas las filas: True.

## Conciliación (observado)

- Las comunas suman la región en todos los años: True.
- La región iguala los egresos de residentes RM del dataset nacional en todos los años: True.
- Combinaciones territorio-año-dimensión cuya suma difiere del total: 0 de 1272.
- Máxima diferencia al recalcular `egresos / poblacion x 10.000` en comunas: 0.0.
- Filas con p90 de estadía menor que la mediana: 0.

## Región por año

| ano | egresos | poblacion | tasa_por_10000 | dias_estada_mediana | dias_estada_p90 | proporcion_snss |
|---|---|---|---|---|---|---|
| 2020 | 9416 |  |  | 13.0 | 47.0 | 0.539 |
| 2021 | 10446 | 8242459.0 | 12.673 | 14.0 | 43.0 | 0.559 |
| 2022 | 12193 | 8310984.0 | 14.671 | 12.0 | 42.0 | 0.535 |
| 2023 | 13122 | 8367790.0 | 15.682 | 12.0 | 41.0 | 0.607 |
| 2024 | 13822 | 8420729.0 | 16.414 | 11.0 | 41.0 | 0.606 |
| 2025 | 13923 | 8471244.0 | 16.436 | 10.0 | 39.0 | 0.63 |

## Volumen por comuna-año (observado)

- Comuna-años sin egresos: 0. Con menos de 10 egresos: 14 de 312.
- Egresos por comuna-año: mínimo 1, mediana 154, máximo 1266.

## Contraste de camas (observado)

| ano | egresos_residentes_rm | camas_equivalentes_egresos | camas_equivalentes_egresos_snss | camas_ocupadas_rem20 | camas_ocupadas_rem20_sin_forense | razon_egresos_snss_rem20_sin_forense |
|---|---|---|---|---|---|---|
| 2020 | 9416 | 610.8 | 413.7 | 575.3 | 494.2 | 0.837 |
| 2021 | 10446 | 650.8 | 434.3 | 586.8 | 505.9 | 0.858 |
| 2022 | 12193 | 708.3 | 464.2 | 563.0 | 482.9 | 0.961 |
| 2023 | 13122 | 712.0 | 475.9 | 586.7 | 501.3 | 0.949 |
| 2024 | 13822 | 764.1 | 514.7 | 578.8 | 492.4 | 1.045 |
| 2025 | 13923 | 735.4 | 504.7 | 596.4 | 508.5 | 0.992 |

- `egresos_residentes_rm` del contraste iguala los egresos de la región en cada año: True.

## Lectura (interpretación)

- Con pocos egresos por comuna-año, las tasas comunales son inestables; conviene leerlas junto con el conteo.
- La tasa de 2020 es nula por falta de denominador (la proyección comunal parte en 2021), no cero.
- Las camas equivalentes de Egresos son una cota superior (la estadía se acota al año) y no deben coincidir con REM-20; la razón solo respalda el orden de magnitud. Las causas de la brecha restante no son determinables con estos datos.
