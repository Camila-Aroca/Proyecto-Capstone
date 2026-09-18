# EDA: `mart_urgencias_comuna_etario_monthly`

Reproducible mediante `python -m scripts.eda_mart_urgencias_comuna_etario`
(script de solo lectura; no modifica el mart). Resumen de apoyo en
[`eda_mart_urgencias_comuna_etario_resumen.csv`](eda_mart_urgencias_comuna_etario_resumen.csv).
Complementa el diccionario en
`reports/dictionary/diccionario_mart_urgencias_comuna_etario_monthly.md`.

## 1. Grano y cobertura

- Grano: `comuna_codigo` × `ano` × `mes` calendario × `grupo_etario_urgencia` (formato largo).
- Filas: 15.300 (= 51 comunas × 60 meses × 5 grupos etarios). Columnas: 14.
- Comunas únicas: 51/52 (falta Vitacura, `13132`, igual que en los demás marts comunales de Urgencias).
- Período: 2021-2025.
- Los 5 grupos etarios del contrato DEIS (`menores_1`, `de_1_a_4`,
  `de_5_a_14`, `de_15_a_64`, `de_65_y_mas`) están presentes en exactamente
  3.060 filas cada uno (una por combinación comuna×mes); no hay grupos
  adicionales ni faltantes.

## 2. Sin `total` ni sexo/género

- Se verificó por código sobre 2021-2025 (las 8 causas del contrato) que
  `total = menores_1 + de_1_a_4 + de_5_a_14 + de_15_a_64 + de_65_y_mas` en
  el 100% de los registros de origen, sin nulos; por eso este mart no
  incluye `total` junto a los grupos etarios (serían la misma cifra
  duplicada).
- Urgencias DEIS no contiene sexo ni género; este mart no lo incorpora ni lo
  infiere.

## 3. Nulos

Sin nulos en ninguna columna `atenciones_id*` (0 en las 8 columnas):
cuando una causa no tuvo atenciones en una comuna×mes×grupo etario, el
pivot produce 0, no una fila ausente.

## 4. Identidad causal ID36 = ID37+...+ID41, a nivel de grupo etario

Se verificó por código que la identidad `atenciones_id36 = atenciones_id37 +
atenciones_id38 + atenciones_id39 + atenciones_id40 + atenciones_id41` se
cumple **exactamente en el 100% de las 15.300 filas** del mart, es decir, la
jerarquía DEIS de causas se sostiene también dentro de cada grupo etario, no
solo a nivel agregado comunal. Esto respalda que la validación de jerarquía
causal (compartida con los demás marts de Urgencias) sea aplicable sin
relajaciones a este grano.

## 5. Distribución de ID36 (salud mental DEIS) por grupo etario, 2021-2025

| Grupo etario | Atenciones ID36 2021-2025 | % del total ID36 |
|---|---:|---:|
| `de_15_a_64` | 414.778 | 82,72% |
| `de_65_y_mas` | 49.428 | 9,86% |
| `de_5_a_14` | 34.922 | 6,96% |
| `de_1_a_4` | 1.846 | 0,37% |
| `menores_1` | 421 | 0,08% |

**Hecho observado:** la demanda de salud mental en Urgencias (ID36) está
concentrada en adultos (`de_15_a_64`, ~83%); los grupos de menor edad
(`menores_1`, `de_1_a_4`) son marginales. No se investiga aquí la causa de
esta distribución (fuera de alcance de este EDA).

## 6. Reconciliación etario → comuna

Sumar los 5 grupos etarios de este mart por `comuna_codigo`×`fecha_mes`
reconcilia **exactamente** con `mart_urgencias_comuna_monthly` para las 8
causas del contrato (ID1, ID35-41):

- Universo comuna×mes agregado desde grupos etarios: 3.060 combinaciones.
- Universo comuna×mes en el mart comunal de referencia: 3.060 combinaciones
  (idénticos).
- `DataFrame.equals` por cada columna `atenciones_id*`: `True` en las 8
  causas.

Es consistente por construcción: cada registro de origen se reparte en
exactamente uno de los 5 grupos etarios (no hay doble conteo), por lo que
sumar los 5 grupos reproduce exactamente el total sin desglosar.

## 7. Limitaciones

- Cobertura de 51/52 comunas RM (falta Vitacura, `13132`); no imputada.
- ID36 no equivale al capítulo CIE-10 F00-F99 estricto (incluye ID37,
  R45.8); ver advertencia en el diccionario.
- Sin sexo/género (Urgencias no lo publica) y sin población/tasas por grupo
  etario (no se construyó un denominador poblacional por grupo etario en
  este proyecto).
- No permite trazabilidad a nivel de paciente ni cruces con Egresos
  (restricción invariante del proyecto).
