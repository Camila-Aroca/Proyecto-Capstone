# Diccionario de datos: `egresos_f00_f99_nacional_2020_2025`

- **Ruta:** `data/processed/egresos/egresos_f00_f99_nacional_2020_2025.parquet`
- **Catálogo asociado:** `data/processed/egresos/catalogo_cie10_f00_f99.csv` (407 subcategorías CIE-10 del capítulo F00-F99, extraídas en tiempo de ejecución de `data/raw/egresos/Diccionario BD egresos hospitalario.xlsx`, hoja "codigo CIE-10").
- **Constructor:** `src/data/build_egresos_f00_f99.py` (`build_dataset`), stage `build_egresos_f00_f99` en `PIPELINE.md`.
- **Grano:** una fila = un registro de egreso hospitalario publicado por DEIS. El dataset está **disociado y anonimizado** (sin identificador de paciente); no se deduplica por coincidencia de atributos — dos filas idénticas en todas las columnas son dos egresos distintos que coinciden por azar, no un error del pipeline.
- **Cobertura observada:** 218.794 filas, **alcance nacional**, 2020-2025 (los 6 años disponibles de `clean_egresos`; no existe `egresos_2026`). 72.922 filas (33,3%) corresponden a `residente_rm=True`; 137.335 (62,8%) a `residente_rm=False`; 8.537 (3,9%) a `residente_rm` nulo (residencia no informada en origen).
- **Fuente:** DEIS/MINSAL, Egresos Hospitalarios 2020-2025 ya normalizados por `clean_egresos` (`data/processed/egresos/egresos_<año>.parquet`), sin re-parsear el CSV/RAW.

## Decisión de alcance: nacional con flag, no filtrado a RM

Se decidió publicar el dataset con **alcance nacional** y una columna derivada `residente_rm`, en vez de filtrar directamente a Región Metropolitana, por tres razones:

1. `region_residencia`/`comuna_residencia` son residencia del paciente, **no ubicación del establecimiento hospitalario** (decisión estable de `PROJECT_CONTEXT.md`). Un residente de RM puede egresar de un hospital fuera de RM y viceversa; filtrar a RM por residencia no equivale a "hospitalizado en RM".
2. El capítulo F00-F99 ya es un subconjunto pequeño (2,33% de los 9.379.787 egresos nacionales 2020-2025); filtrar además a residencia RM reduciría la muestra a un tercio adicional sin necesidad, y descartaría permanentemente la posibilidad de comparar RM contra el resto del país.
3. Mantener el universo nacional preserva más información útil sin romper el alcance RM: cualquier análisis RM se obtiene con un simple filtro `residente_rm == True`, mientras que lo inverso (reconstruir el universo nacional desde un extracto ya filtrado a RM) no sería posible sin volver a la fuente.

## Construcción/derivación

- Filtra `diag1` (diagnóstico principal) contra el catálogo oficial CIE-10 de 407 subcategorías del capítulo F00-F99 (columna `CAPITULO` = "F00-F99" en el diccionario DEIS). Se verificó por código que este filtro es **idéntico**, sin una sola discrepancia, a `diag1` que comienza con la letra "F" sobre las 9.379.787 filas nacionales 2020-2025.
- `diag2` (causa externa) no se usa para el filtro y está vacío (`""`) en el 100% de los registros F00-F99 observados: no aporta contexto adicional en este subconjunto, se conserva solo por completitud/trazabilidad del contrato de Egresos.
- No se homologan `sexo` ni `grupo_edad` entre años (ver advertencias). No se modifica `dias_estada`, `condicion_egreso`, `prevision` ni `pertenencia_establecimiento_salud`: se preservan exactamente como los publica `clean_egresos` (que a su vez preserva el valor crudo del CSV DEIS, sin recodificar).
- Antes de publicar, valida: `diag1` 100% dentro del catálogo F00-F99; años observados = {2020..2025} exactos; el conteo final coincide con la suma de conteos filtrados año-por-año **y** con un recuento independiente vía un camino de código distinto (multi-archivo `pyarrow.dataset`), para detectar duplicación/pérdida introducida por el pipeline; `dias_estada` sin nulos ni valores ≤0; y los campos categóricos (`sexo`, `pertenencia_establecimiento_salud`, `grupo_edad`, `glosa_prevision`, `prevision`, `condicion_egreso`) no contienen ningún valor fuera de los dominios ya documentados (un valor nuevo hace fallar la etapa, forzando su documentación explícita en vez de pasar silenciosamente).

## Semántica confirmada: `pertenencia_establecimiento_salud` (SNSS)

**Confirmado por el diccionario oficial DEIS** (`data/raw/egresos/Diccionario BD egresos hospitalario.xlsx`, hoja "Hoja1"): la variable `PERTENENCIA_ESTABLECIMIENTO_SALU` (nombre truncado a 32 caracteres en el CSV/diccionario fuente; el código maneja este truncamiento) se describe textualmente como **"Tipo de pertenencia (Perteneciente o No perteneciente al SNSS)"**. Esto confirma, con respaldo documental y no por inferencia del nombre/valores, que la columna indica si el **establecimiento** de salud donde ocurrió el egreso pertenece o no al Sistema Nacional de Servicios de Salud (SNSS) — la red pública de hospitales/servicios de salud.

**Límite de esta confirmación:** el diccionario confirma el *tipo de pertenencia institucional* del establecimiento, pero Egresos no tiene un identificador único de establecimiento (decisión estable de `PROJECT_CONTEXT.md`). Es decir, se sabe *si* el egreso ocurrió en un establecimiento SNSS o no, pero no *cuál* establecimiento ni su ubicación. `pertenencia_establecimiento_salud` no debe interpretarse como ubicación geográfica ni como identificador de establecimiento.

## Columnas

| Columna | Tipo | Semántica |
|---|---|---|
| `ano_egreso` | int32 | Año del egreso. |
| `sexo` | string | Sexo del paciente, valor crudo. **2021 publica códigos numéricos como texto** (`"1"`,`"2"`,`"3"`); el resto de los años publica texto (`"HOMBRE"`,`"MUJER"`,`"INTERSEX (INDETERMINDADO)"`) más el marcador `"*"`. El diccionario oficial no incluye una tabla de códigos para `SEXO`; no existe evidencia documental para mapear los códigos de 2021 a las categorías de texto, por lo que **no se homologa**. |
| `grupo_edad` | string | Grupo etario del paciente al ingreso, valor crudo. **2021 usa un esquema distinto** (quinquenal/fino, mayúsculas, con tramos de días/meses para menores de 1 año) al resto de los años (decenal, minúsculas). Ver advertencias. |
| `region_residencia` | int32 (nulo si `"*"` en origen) | Código de región de residencia del paciente (1-16, o 99 fuera de este subconjunto a nivel nacional completo). **No es la región del hospital.** |
| `glosa_region_residencia` | string | Nombre de la región de residencia. Mojibake U+FFFD documentado en 2024-2025 (ver `reports/eda/eda_egresos_encoding_detalle.md`); no se corrige. |
| `comuna_residencia` | int32 (nulo si `"*"` en origen) | Código CUT de comuna de residencia del paciente. **No es la comuna del hospital.** |
| `glosa_comuna_residencia` | string | Nombre de la comuna de residencia. Mismo mojibake documentado que `glosa_region_residencia`. |
| `prevision` | int32 (nulo si `"*"` en origen) | Código de previsión de salud (1=FONASA, 2=ISAPRE, 3=CAPREDENA, 4=DIPRECA, 5=SISA, 96=NINGUNA, 99=DESCONOCIDO). |
| `glosa_prevision` | string | Glosa de previsión; consistente en las 6 categorías + `"*"` en los 6 años. |
| `pertenencia_establecimiento_salud` | string | Pertenencia del establecimiento al SNSS (confirmado por diccionario, ver sección dedicada arriba); valores: `"Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS"`, `"No Pertenecientes al Sistema Nacional de Servicios de Salud, SNSS"`, `"*"`. **2021 no tiene ningún valor `"*"`** (anomalía documentada, ver EDA). |
| `diag1` | string | Diagnóstico principal, código CIE-10 (4 caracteres). Restringido a F00-F99 por construcción de este dataset. |
| `diag2` | string | Causa externa, código CIE-10. Vacío (`""`) en el 100% de las filas F00-F99 observadas. |
| `dias_estada` | int32 | Días de estada total. Sin nulos ni valores ≤0 en F00-F99 (min=1, max=22.239 — outlier extremo verificado en la fuente, no corregido). |
| `condicion_egreso` | int32 | 1=Vivo, 2=Fallecido (según diccionario oficial). |
| `interv_q` | int32 (mayormente nulo) | Flag técnico sin documentación en el diccionario oficial DEIS disponible. **Solo presente en 2020**; nulo en 2021-2025 (columna ausente del CSV esos años). Se preserva sin interpretar su semántica. |
| `proced` | int32 (mayormente nulo) | Igual que `interv_q`: sin documentación oficial, solo presente en 2020. |
| `error` | int32 (mayormente nulo) | Flag técnico sin documentación en el diccionario oficial DEIS disponible. **Solo presente en 2025** (0/1); nulo en 2020-2024. Un único registro F00-F99 2025 tiene `error=1`; no se excluye por falta de semántica documentada (ver EDA). |
| `residente_rm` | bool (nulo si `region_residencia` es nulo) | **Columna derivada** (no publicada por DEIS): `True` si `region_residencia == 13`, `False` si es una región distinta y conocida, nulo si `region_residencia` es nulo en origen (no se asume residencia). No representa ubicación del hospital. |

## Advertencias e interpretación

- **`sexo` no es comparable entre 2021 y el resto de los años** sin una regla de homologación respaldada por diccionario, que no existe actualmente. No inferir que `"1"`=HOMBRE/`"2"`=MUJER sin evidencia documental adicional.
- **`grupo_edad` no es comparable entre 2021 y el resto de los años.** El tramo `"85 A MAS"` de 2021 no puede homologarse sin ambigüedad al esquema decenal de los otros años porque se solaparía entre `"80 a 89"` y `"90 y más"`.
- **ID de establecimiento inexistente:** ni `pertenencia_establecimiento_salud` ni ninguna otra columna identifican un establecimiento específico. No enlazar por establecimiento con Urgencias ni con `dim_oferta_urgencia_rm`.
- **No enlazar con Urgencias por paciente ni por establecimiento** (restricción invariante del proyecto, `AGENTS.md`). Cualquier relación con Urgencias debe ser ecológica/territorial (por ejemplo, agregando por `residente_rm`/comuna), nunca a nivel de registro individual.
- **`diag2` no sustituye a `diag1`** y está vacío en el 100% de las filas de este dataset; no usar como fuente de contexto clínico en F00-F99.
- **Duplicados exactos esperables:** ~11,9% de las filas participan en algún duplicado exacto (todas las columnas salvo `residente_rm`); es un artefacto esperado de un dataset disociado sobre una población grande, no un error de pipeline. No se deduplica.
- **`interv_q`/`proced`/`error` no están documentados en el diccionario oficial DEIS disponible** (no aparecen en la hoja "Hoja1"); se preservan como flags técnicos originales para trazabilidad, sin asumir su significado.
- El diccionario `Diccionario BD egresos hospitalario.xlsx` no tiene entrada de procedencia (URL/SHA256) en `data/raw/provenance_manifest.json`, a diferencia de otros XLSX de este proyecto; es una limitación observada, no corregida en este trabajo.
