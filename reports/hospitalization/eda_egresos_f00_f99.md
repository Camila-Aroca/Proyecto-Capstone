# EDA: `egresos_f00_f99_nacional_2020_2025`

Reproducible mediante `python -m scripts.eda_egresos_f00_f99` (script de solo
lectura; no modifica el dataset). Resumen de apoyo en
[`eda_egresos_f00_f99_resumen.csv`](eda_egresos_f00_f99_resumen.csv).
Complementa el diccionario en
`reports/dictionary/diccionario_egresos_f00_f99_nacional.md`.

## 1. Forma, cobertura temporal y geográfica

- 218.794 filas, 18 columnas, alcance **nacional**, 2020-2025 (6 años; no
  existe `egresos_2026` en `clean_egresos`).
- F00-F99 es el 2,33% de los 9.379.787 egresos nacionales 2020-2025
  (verificado por código contra el catálogo oficial CIE-10).

| Año | Registros (nacional) | Registros (RM) | % RM sobre nacional |
|---:|---:|---:|---:|
| 2020 | 26.299 | 9.416 | 35,80% |
| 2021 | 29.446 | 10.446 | 35,48% |
| 2022 | 34.798 | 12.193 | 35,04% |
| 2023 | 39.874 | 13.122 | 32,91% |
| 2024 | 43.005 | 13.822 | 32,14% |
| 2025 | 45.372 | 13.923 | 30,69% |

**Hecho observado:** la cifra nacional crece de forma sostenida 2020→2025
(+72,6%), mientras que el peso relativo de RM sobre el total nacional baja
gradualmente (35,8%→30,7%). No se investiga aquí la causa (fuera de alcance
de este EDA; podría ser cambios en cobertura de registro, en la demanda
real, o ambos).

`residente_rm`: 72.922 `True` (33,3%), 137.335 `False` (62,8%), 8.537 nulo
(3,9% — `region_residencia` no informado en origen, `"*"`).

## 2. Duración de estadía (`dias_estada`)

| | Nacional | RM |
|---|---:|---:|
| n | 218.794 | 72.922 |
| media | 23,37 | 30,47 |
| mediana | 9 | 12 |
| p75 | 20 | 23 |
| p99 (nacional) | 182 | — |
| máximo | 22.239 | 22.239 |
| filas > 365 días | 1.052 | — |

**Hecho observado:** la distribución tiene una cola larga extrema (máximo
22.239 días ≈ 61 años), igual que en el Egresos general (no exclusivo de
F00-F99). No se corrige ni se excluye: no hay evidencia de que sea un error
de captura y no existe una regla reproducible para distinguir un caso
clínico extremo real de un error de digitación con los datos disponibles.
La estadía RM es mayor en mediana (12 vs 9 días) que la nacional.

## 3. Sexo — **anomalía crítica: 2021 no es comparable con el resto**

| Año | `*` | `1` | `2` | `3` | HOMBRE | INTERSEX (INDETERMINDADO) | MUJER |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 684 | | | | 11.914 | | 13.701 |
| 2021 | | 12.778 | 16.662 | 6 | | | |
| 2022 | 898 | | | | 14.217 | 2 | 19.681 |
| 2023 | 2.033 | | | | 15.813 | | 22.028 |
| 2024 | 2.259 | | | | 16.806 | | 23.940 |
| 2025 | 2.635 | | | | 17.725 | 1 | 25.011 |

**Hecho observado:** 2021 es el único año que publica `sexo` como código
numérico en texto (`"1"`,`"2"`,`"3"`), sin ningún `"*"`. El resto de los
años publica texto (`HOMBRE`/`MUJER`/`INTERSEX (INDETERMINDADO)`) más el
marcador `"*"`. El diccionario oficial DEIS (`Diccionario BD egresos
hospitalario.xlsx`, hoja "Hoja1") describe `SEXO` solo como "Código del
sexo biológico del paciente", **sin tabla de códigos**. No existe evidencia
documental para mapear `"1"`/`"2"`/`"3"` a las categorías de texto de los
demás años. **No se homologa.** Cualquier análisis por sexo que combine
2021 con otros años debe excluir 2021 o tratarlo por separado hasta que
exista una regla auditada.

## 4. Grupo etario — **anomalía crítica: 2021 usa un esquema distinto**

2021 (quinquenal/fino, mayúsculas): `1 A 4 AÑOS`, `5 A 9 AÑOS`, `10 A 14
AÑOS`, `15 A 19 AÑOS`, ..., `80 A 84 AÑOS`, `85 A MAS`, más tramos finos de
menores de 1 año (`menor a 7 días`, `7 A 27 DIAS`, `28 DIAS A 2 MES`, `2
MESES A MENOS DE 1 AÑO`).

2020, 2022-2025 (decenal, minúsculas): `1 a 9`, `10 a 19`, `20 a 29`, ...,
`80 a 89`, `90 y más`, `menor de un año`, más el marcador `*`. 2024-2025
presentan mojibake U+FFFD en `"90 y más"`→`"90 y m�s"` y `"menor de un
año"`→`"menor de un a�o"` (ya documentado en
`reports/eda/eda_egresos_encoding_detalle.md`).

**Hecho observado:** el tramo `"85 A MAS"` de 2021 (401 registros) no puede
homologarse sin ambigüedad al esquema decenal, porque se solaparía entre
`"80 a 89"` y `"90 y más"` de los demás años. **No se construye ningún
crosswalk.** `grupo_edad` no debe agregarse ni compararse entre 2021 y el
resto de los años sin resolver primero esta incompatibilidad.

## 5. Previsión de salud

| Previsión | Registros |
|---|---:|
| FONASA | 173.397 |
| ISAPRE | 29.083 |
| `*` (no informado) | 8.509 |
| SISA | 1.821 |
| CAPREDENA | 1.669 |
| DESCONOCIDO | 1.570 |
| NINGUNA | 1.523 |
| DIPRECA | 1.222 |

Dominio consistente en los 6 años (mismas 7 categorías + `*`); sin
anomalías de esquema como en sexo/grupo_edad.

## 6. Pertenencia del establecimiento al SNSS

| Pertenencia | Registros |
|---|---:|
| Pertenecientes al SNSS | 166.282 (76,0%) |
| No pertenecientes al SNSS | 44.003 (20,1%) |
| `*` (no informado) | 8.509 (3,9%) |

Semántica confirmada por el diccionario oficial DEIS: ver
`reports/dictionary/diccionario_egresos_f00_f99_nacional.md`, sección
dedicada. **2021 es el único año sin ningún valor `"*"`** en esta columna
(mismo patrón de "sin marcador de no informado" que se observa en `sexo` y
`grupo_edad` ese año — los tres campos con `"*"` en 2020/2022-2025
coinciden exactamente en 8.509 filas cada uno, sugiriendo que corresponden
al mismo subconjunto de registros con datos no informados, no a tres
anomalías independientes).

## 7. Condición de egreso

| Condición | Registros |
|---|---:|
| 1 = Vivo | 218.201 (99,73%) |
| 2 = Fallecido | 593 (0,27%) |

Sin nulos, dominio limpio en los 6 años.

## 8. Diagnósticos principales (`diag1`)

Top 5 subcategorías CIE-10 (de 218.794 registros):

| Código | Glosa | Registros |
|---|---|---:|
| F322 | Episodio depresivo grave sin síntomas psicóticos | 22.515 |
| F329 | Episodio depresivo, no especificado | 14.439 |
| F603 | Trastorno de la personalidad emocionalmente inestable | 10.714 |
| F209 | Esquizofrenia, no especificada | 8.751 |
| F609 | Trastorno de la personalidad, no especificado | 7.300 |

Participación por grupo CIE-10 (11 grupos del capítulo F00-F99):

| Grupo | Glosa | Registros | % |
|---|---|---:|---:|
| F30-F39 | Trastornos del humor [afectivos] | 70.602 | 32,27% |
| F20-F29 | Esquizofrenia, trastornos esquizotípicos y delirantes | 34.370 | 15,71% |
| F10-F19 | Trastornos por sustancias psicoactivas | 33.499 | 15,31% |
| F40-F48 | Trastornos neuróticos/estrés/somatomorfos | 27.275 | 12,47% |
| F60-F69 | Trastornos de la personalidad | 24.322 | 11,12% |
| F00-F09 | Trastornos mentales orgánicos | 12.753 | 5,83% |
| F90-F98 | Trastornos de niñez/adolescencia | 5.463 | 2,50% |
| F80-F89 | Trastornos del desarrollo psicológico | 4.029 | 1,84% |
| F50-F59 | Síndromes conductuales/fisiológicos | 3.857 | 1,76% |
| F70-F79 | Retraso mental | 2.182 | 1,00% |
| F99 | Trastorno mental no especificado | 442 | 0,20% |

## 9. Nulos por columna

| Columna | Nulos | % |
|---|---:|---:|
| `region_residencia` | 8.537 | 3,90% |
| `comuna_residencia` | 6.927 | 3,17% |
| `prevision` | 8.509 | 3,89% |
| `interv_q` | 192.495 | 88,0% (columna ausente en el CSV 2021-2025) |
| `proced` | 192.495 | 88,0% (columna ausente en el CSV 2021-2025) |
| `error` | 173.422 | 79,3% (columna ausente en el CSV 2020-2024) |
| `residente_rm` | 8.537 | 3,90% (igual a `region_residencia`, por construcción) |

El resto de las columnas (incluyendo `sexo`, `grupo_edad`,
`dias_estada`, `condicion_egreso`, `diag1`) no tiene nulos: los marcadores
de "no informado" se publican como texto (`"*"`), no como nulo, salvo en
las columnas numéricas territoriales/previsión donde `"*"` se convierte a
nulo en `clean_egresos`.

## 10. `diag2` y flags técnicos no documentados

- `diag2` está vacío (`""`) en el 100% de las 218.794 filas F00-F99: no
  aporta contexto adicional en este subconjunto.
- `interv_q`/`proced` solo existen en 2020 (26.299 valores no nulos cada
  uno); `error` solo existe en 2025 (45.372 valores no nulos, de los
  cuales solo 1 tiene `error=1`). Ninguno de los tres aparece en el
  diccionario oficial DEIS disponible; se preservan sin interpretar su
  semántica (ver diccionario).

## 11. Duplicados exactos

26.089 filas (11,92%) participan en algún duplicado exacto (todas las
columnas salvo la `residente_rm` derivada), formando 9.766 grupos
distintos. **No se deduplica**: el dataset es disociado y no tiene
identificador de paciente, por lo que coincidencias exactas de
sexo/edad/comuna/previsión/diagnóstico/estadía son esperables en una
población grande y no constituyen un error del pipeline (mismo criterio
que `reports/eda/eda_egresos_encoding_detalle.md`, sección 9).

## 12. Limitaciones

- `sexo` y `grupo_edad` de 2021 no son comparables con 2020/2022-2025 sin
  una regla de homologación que actualmente no existe (secciones 3 y 4).
- No hay identificador de establecimiento hospitalario; `pertenencia_establecimiento_salud`
  informa solo el tipo de pertenencia institucional (SNSS o no), nunca la
  ubicación ni la identidad del establecimiento.
- `region_residencia`/`comuna_residencia` son residencia del paciente, no
  ubicación del hospital; `residente_rm` hereda esa misma limitación.
- No se investigó en este EDA la causa de la caída del peso relativo de RM
  sobre el total nacional (sección 1) ni la de los valores extremos de
  `dias_estada` (sección 2): "No es posible determinarlo con los datos
  disponibles".
- No se realiza aquí modelamiento causal, regresión, ni cruce con
  Urgencias (fuera de alcance de este EDA; restricción invariante del
  proyecto para el cruce con Urgencias).
