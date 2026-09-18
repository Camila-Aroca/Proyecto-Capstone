# EDA: `mart_urgencias_establecimiento_monthly`

Reproducible mediante `python -m scripts.eda_mart_urgencias_establecimiento`
(script de solo lectura; no modifica el mart). Resumen de apoyo en
[`eda_mart_urgencias_establecimiento_resumen.csv`](eda_mart_urgencias_establecimiento_resumen.csv).
Complementa el diccionario en
`reports/dictionary/diccionario_mart_urgencias_establecimiento_monthly.md`.

## 1. Grano y cobertura

- Grano: `establecimiento_codigo` × `ano` × `mes` calendario.
- Filas: 8.857. Columnas: 22.
- Establecimientos únicos: 152. Comunas únicas: 51/52 (falta Vitacura, `13132`, igual que en los marts comunales).
- Período: 2021-2025.

**No todos los establecimientos reportan los 60 meses posibles del período**
(2021-2025 = 60 meses): 139 de 152 establecimientos sí reportan los 60
meses; los 13 restantes reportan un subconjunto (mínimo observado: 2 meses).

- **Hecho observado:** un establecimiento sin fila en un mes determinado no
  tuvo ninguna atención de las causas del contrato (ID1, ID35-41) en ese mes
  en el origen `urgencias_rm_<año>.parquet`, o no existía/reportaba aún en
  ese mes.
- **No se imputó** ningún mes ausente con cero: la ausencia de fila es
  distinta de una fila con conteo cero, siguiendo la misma convención que
  `mart_urgencias_comuna_monthly`.
- **Información no disponible:** no es posible determinar con este mart si
  la ausencia de meses corresponde a apertura/cierre del establecimiento,
  discontinuidad de reporte al REM/Urgencias DEIS, o ausencia real de
  atenciones; esa distinción requeriría el maestro histórico de vigencia de
  establecimientos, fuera de alcance de este EDA.

## 2. Tipo de establecimiento (`tipo_establecimiento_urgencia`)

Distribución de filas (establecimiento×mes) por tipo:

| Tipo | Filas | Establecimientos únicos |
|---|---:|---:|
| SAPU | 5.511 | 92 |
| Hospital | 1.557 | 26 |
| SAR | 1.210 | 23 |
| SUR | 544 | 10 |
| CEAR | 35 | 1 |

`tipo_establecimiento_urgencia` se incorporó como atributo del grano porque
se verificó por código que cada uno de los 152 `establecimiento_codigo`
reporta un único valor de este campo (y de `comuna_codigo`,
`comuna_glosa`, `establecimiento_glosa`) en las 8 causas del contrato
2021-2025, sin excepciones: es una regla determinista, no un supuesto.

## 3. Nulos

- **Columnas `atenciones_id*`:** sin nulos (0 en las 8 columnas); cuando una
  causa no tuvo atenciones en un establecimiento×mes presente, el pivot
  produce 0, no una fila ausente.
- **Ratios:** `proporcion_id36_sobre_id1` es nulo en 14 de 8.857 filas;
  cada `proporcion_id37..41_sobre_id36` es nulo en 497 filas (18,3%
  aproximadamente) — establecimiento×mes sin ninguna atención ID36 en ese
  período, consistente con el hecho de que la mayoría de los
  establecimientos de tipo SAPU/SAR/SUR reportan volúmenes bajos o nulos de
  salud mental en muchos meses.

## 4. Reconciliación establecimiento → comuna

Sumar el mart de establecimiento por `comuna_codigo`×`fecha_mes` reconcilia
**exactamente** con `mart_urgencias_comuna_monthly` para las 8 causas del
contrato (ID1, ID35-41):

- Universo comuna×mes agregado desde establecimiento: 3.060 combinaciones.
- Universo comuna×mes en el mart comunal de referencia: 3.060 combinaciones
  (idénticos).
- `DataFrame.equals` por cada columna `atenciones_id*`: `True` en las 8
  causas.

Esto es consistente por construcción: ambos marts derivan del mismo origen
filtrado por las mismas causas; sumar por establecimiento dentro de una
comuna×mes es aritméticamente equivalente a agregar directamente por
comuna×mes.

## 5. Totales de atenciones 2021-2025 por causa

| Causa | Atenciones totales 2021-2025 (mart de establecimiento) |
|---|---:|
| ID1 | 28.840.470 |
| ID35 | 12.685 |
| ID36 | 501.395 |
| ID37 | 28.197 |
| ID38 | 49.666 |
| ID39 | 42.520 |
| ID40 | 270.349 |
| ID41 | 110.663 |

Idénticos a los totales de `mart_urgencias_comuna_monthly` (ver
`reports/eda/eda_mart_urgencias_comuna.md`), como se espera de la
reconciliación exacta de la sección 4.

## 6. Limitaciones

- Cobertura de 51/52 comunas RM (falta Vitacura, `13132`); no imputada.
- No incorpora población ni tasas por establecimiento: la población
  comunal no representa la población atendida de un establecimiento
  individual (ver diccionario). Cualquier análisis de tasa por
  establecimiento requeriría un denominador distinto, no disponible en este
  proyecto.
- ID36 no equivale al capítulo CIE-10 F00-F99 estricto (incluye ID37,
  R45.8); ver advertencia en el diccionario.
- No permite trazabilidad a nivel de paciente ni cruces con Egresos
  (restricción invariante del proyecto).
