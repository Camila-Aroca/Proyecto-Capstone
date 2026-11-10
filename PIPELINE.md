# Guía de Ejecución del Pipeline (PIPELINE.md)

Este documento centraliza las instrucciones para ejecutar el pipeline de datos de manera reproducible, ordenada e idempotente.

## Caracterización en la web

`/api/v1/caracterizacion/{fuente}/{nivel}/{codigo}` es una vista de consulta,
no un nuevo artefacto del DAG. Suma los desgloses etarios publicados por
`clean_urgencias` (ID36/ID42) y cuenta sexo/edad de `clean_defunciones`
(X60–X84, residencia), exclusivamente en las claves año/semana DEIS observadas
que envía el gráfico. No lee RAW, escribe outputs ni entrena modelos. La región
usa el mismo universo de comunas que el panel servido, también en historia;
no suma las comunas excluidas del gráfico por falta de cobertura. Rechaza una
desagregación etaria que no concilia por registro; la web exige además que las
sumas coincidan con la línea observada antes de mostrarla.

Urgencias no registra sexo. El usuario puede activar un **escenario hipotético**:
`N_s = N * C_s / sum(C_s)`, con los conteos nacionales por sexo de
`egresos_intento_suicida_sexo_anio` de `normalize_contexto_genero`. Se elige el
último año publicado no posterior al primer año de la ventana; los restos
mayores conservan exactamente N al redondear. Al activarlo se muestran fuente,
año, conteos, fórmula y supuesto. Transportar la composición nacional de egresos
por intento suicida a las urgencias seleccionadas **no está validado** y no
acredita precisión del reparto. No caracteriza sexo × edad ni identidad de
género. No hay enlaces individuales, FK ni nuevas features; el contexto se
mantiene independiente. Sin referencia se conserva la edad sin escenario.
REM-20 no publica sexo/edad individual para caracterizar la ocupación de camas.

QA sintético: `tests/test_api_caracterizacion.py`. QA de marts reales:
`SAAD_QA_DATOS=1 python -m pytest tests/test_caracterizacion_integridad.py`.
No hay cambios de entidades canónicas, persistencia ni SQL; ERD y UML no requieren
modificaciones. Los productores de los inputs ya pertenecen al pipeline.

## 1. Requisitos
Para preparar el entorno antes de correr el pipeline:

```bash
# 1. Crear entorno virtual
python -m venv .venv
# 2. Activar entorno virtual
.venv\Scripts\activate   # (Windows)
# source .venv/bin/activate # (Mac/Linux)
# 3. Instalar dependencias
pip install -r requirements.txt
```

## 2. Ejecución Completa

Para correr todo el pipeline (saltará automáticamente las etapas que ya tengan los datos generados):

```bash
python scripts/run_pipeline.py
```

## 3. Ejecución desde una Etapa

`--stage` (por defecto `all`) selecciona el stage y todos sus descendientes transitivos en `PIPELINE_ORDER`; no ejecuta ni reconstruye sus upstream. Para bootstrap desde cero se usa la ejecución completa, que evalúa los stages en el orden de la sección 5. Una ejecución parcial exige que los demás inputs ya estén disponibles. `--help` muestra las opciones implementadas: `--stage`, `--force`, `--year` y `--refresh-current-urgencias`. El refresh no se combina con un stage específico ni con `--year`.

Ejemplo:

```bash
python scripts/run_pipeline.py --stage clean_urgencias
```

Si los outputs pasan `check_outputs_exist` y ningún upstream se ejecutó en esta invocación, las etapas correspondientes realizan `SKIP`. Esto acredita reutilización de outputs, no ejecución de sus productores ni vigencia general frente a cambios anteriores de código o inputs.

Para actualizar manualmente Urgencias del año calendario actual de Chile:

```bash
python scripts/run_pipeline.py --refresh-current-urgencias
```

El comando consulta nuevamente el ZIP oficial mutable, valida el CSV extraído en
staging y compara su SHA256 con el RAW local. Registra URL, instante UTC real de
descarga, tamaños y hashes del ZIP y del CSV en `data/raw/provenance_manifest.json`.
Si el CSV es idéntico, conserva el RAW; si además el Parquet anual declara ese hash y los outputs evaluados son válidos, las etapas downstream hacen `SKIP`. Los outputs faltantes o inválidos aún pueden provocar su ejecución.
No duplica una entrada de provenance ya registrada; si el RAW era legado y
carecía de registro, documenta únicamente la descarga recién verificada.
Si cambia, reemplaza el RAW tras la validación y regenera solo el Parquet del
año en curso y `eda_urgencias`; no recalcula los marts históricos cerrados.
`--force` combinado con refresh se aplica solo a `download_deis`; la regeneración downstream depende de publicación o desalineación del Parquet, o de outputs faltantes/inválidos. Ante una descarga o validación fallida, el
RAW previo se conserva y el comando falla. Este mismo comando puede programarse
más adelante; no requiere una API de hora.

**Ejecución programada en contenedor.** `src/cloud/pipeline_task.py` es el punto de
entrada de la imagen `saad-pipeline` (target `pipeline` del `Dockerfile`). En
`--modo semanal` ejecuta `--refresh-current-urgencias` y luego
`--stage forecast_demanda_sm --force`: el pronóstico se fuerza porque usa las
semanas del año en curso, pero su vigencia solo vigila el mart cerrado y la
selección del modelo. En `--modo completo` ejecuta el pipeline completo. Sin
`SAAD_S3_BUCKET` opera sobre el disco local; con esa variable baja `data/` y
`reports/` desde S3, ejecuta el modo, sube solo los archivos nuevos o modificados
(los borrados locales no se propagan) y, si cambió algo y están `SAAD_ECS_CLUSTER`
y `SAAD_ECS_SERVICE`, fuerza un nuevo despliegue de la API. Si un paso falla no
sube nada, de modo que S3 conserva el último estado completo. Sus pruebas están
en `tests/test_pipeline_task.py`.

`run_date` es la fecha civil de `America/Santiago`; `data_cutoff_date` es la
fecha máxima observada en el CSV. El comando informa `data_lag_days`, el
desfase entre ambas fechas. Una fuente atrasada conserva su fecha real: no se
agregan días hasta ayer. `tzdata` ya está declarado para disponer de la zona
IANA en Windows. El refresh no ejecuta benchmark, holdout ni serving del
forecast; la actualización de esos componentes downstream corresponde a su
responsable y debe hacerse después según sus contratos.

Cada Parquet `urgencias_rm_<año>.parquet` declara en su metadato `raw_sha256` el
SHA256 del RAW desde el que se generó. Si el snapshot descargado es idéntico al
RAW pero el Parquet no declara ese mismo hash (por ejemplo, una limpieza anterior
falló tras publicar el RAW, o el Parquet es anterior a este metadato), el refresh
regenera `clean_urgencias` del año corriente y `eda_urgencias` aunque
`published` sea `false`. La verificación lee solo el footer del Parquet.

El orquestador considera exitoso un stage solo si el proceso termina con código 0
y sus outputs declarados existen y son válidos (`check_outputs_exist`); en caso
contrario termina con código distinto de cero. Con `--refresh-current-urgencias`
se valida el RAW del año corriente. `clean_egresos` exige el RAW de todos los años
2020-2025 y falla, sin generar outputs parciales, si falta alguno.

Con `--force`, la etapa seleccionada se regenera y el cambio se propaga únicamente a sus dependencias downstream, sin ejecutar ramas no relacionadas.

Por ejemplo, `--stage clean_urgencias --force` evalúa, en orden: `clean_urgencias`, `eda_urgencias`, `profile_urgencias_sm_coverage`, `build_urgencias_comuna_marts`, `build_urgencias_establecimiento_mart`, `build_urgencias_establecimiento_weekly_mart`, `eda_mart_urgencias_establecimiento_weekly`, `build_urgencias_comuna_etario_mart`, `build_dim_oferta_urgencia_rm`, `build_dim_camas_psiquiatria_hospital_rm`, `build_capa_oferta_urgencia_rm`, `resolve_coordenadas_establecimientos`, `build_cobertura_urgencia_comuna`, `build_mart_mvp_territorial_comuna`, `eda_series_demanda_sm`, `benchmark_demanda_sm`, `evaluate_holdout_demanda_sm` y `forecast_demanda_sm`. Puede reconstruir marts y resultados de modelado: no es una comprobación local aislada.

## 4. Forzar Regeneración (Force)

Si deseas regenerar una etapa ignorando su condición normal de `SKIP`, utiliza `--force`.

Cuando se combina con `--stage`, se fuerza la etapa seleccionada y la regeneración se propaga únicamente a sus dependencias downstream.

Ejemplo:

```bash
python scripts/run_pipeline.py --stage clean_urgencias --force
```

Para regenerar un único Parquet anual de Urgencias sin evaluar downstream ni
reprocesar otros años, usar el contrato particionado:

```bash
python scripts/run_pipeline.py --stage clean_urgencias --year 2026
```

`--year` se valida contra los años soportados y el RAW local correspondiente.
La validación de `SKIP` se restringe a ese Parquet; `--force` conserva el mismo
alcance anual. La ejecución sin `--year` mantiene el comportamiento histórico
del stage completo y su propagación downstream.

Para forzar la evaluación completa del pipeline puede utilizarse:

```bash
python scripts/run_pipeline.py --force
```

--force debe utilizarse deliberadamente, especialmente en etapas de descarga, porque las fuentes del año en curso pueden ser mutables y producir un snapshot distinto.

## 5. Orden de Ejecución (DAG)

La lógica reutilizable de ingesta, descarga, limpieza y normalización se organiza principalmente en `src/data/`, mientras que los ejecutables de análisis y orquestación se mantienen en `scripts/`. `scripts/run_pipeline.py` coordina las dependencias entre estas etapas.

### Rama de Defunciones: RAW, EDA y consolidación

```bash
python scripts/run_pipeline.py --stage download_defunciones
```

Evalúa la rama de Defunciones hasta el pronóstico de suicidios. En un arranque
sin snapshot preliminar se consulta el catálogo oficial; si los outputs ya
existen se reutilizan. Para consultar de nuevo el catálogo y actualizar:

```bash
python scripts/run_pipeline.py --stage download_defunciones --force
```

Para consolidar los RAW existentes sin volver a descargar
ni generar el EDA histórico completo:

```bash
python scripts/run_pipeline.py --stage clean_defunciones
```

`download_defunciones` (`src/data/download_defunciones.py`) no tiene upstream y
sus downstream son `eda_defunciones` y `clean_defunciones`. Los inputs son los ZIP oficiales:

- [Cifras oficiales 1990–2023](https://repositoriodeis.minsal.cl/DatosAbiertos/VITALES/DEFUNCIONES_FUENTE_DEIS_1990_2023_CIFRAS_OFICIALES.zip).
- El paquete preliminar por causa anunciado por la tabla Datos Abiertos de [DEIS](https://deis.minsal.cl/), descubierto al iniciar desde cero o al solicitar `--force`.

Publica cuatro archivos: el CSV original y el XLSX
`Diccionario de Datos y Manual de Uso BBDD-COVID19 liberada.xlsx` de cada ZIP,
en `data/raw/defunciones/1990_2023/` y en un directorio identificado por el
periodo y fecha del paquete preliminar. Los nombres y bytes
se conservan; los diccionarios homónimos no se sobrescriben entre paquetes.
Descarga con TLS estándar a `.cache/downloads/defunciones/`, comprueba tamaño de
transporte si se publica `Content-Length`, miembros exactos y sin duplicados,
ausencia de enlaces/cifrado, tamaños extraídos y CRC de cada miembro. Antes de
publicar recorre **todas** las filas del CSV, validando las 27 columnas exactas,
rectangularidad y pertenencia del año al rango configurado, y comprueba la
legibilidad y hojas del diccionario. No exige que todo año tenga filas: el EDA
reporta años esperados ausentes. Límites explícitos: ZIP 512 MiB, expansión y
CSV 2 GiB. El perfil no certifica exhaustividad del registro nacional.

El CSV y diccionario se publican con reemplazo atómico por archivo y rollback
conjunto si falla cualquier publicación o el registro del manifiesto. El
historial común `data/raw/provenance_manifest.json` usa los identificadores
`deis_defunciones_1990_2023` y `deis_defunciones_<periodo>_<fecha>`, y sus variantes
con sufijo `_dictionary`: guarda URL, hora real UTC de descarga, SHA256 y tamaño
del ZIP y de cada archivo RAW, miembro del ZIP y Last-Modified/ETag observados.
El ZIP se elimina **solo después** de validar y publicar RAW y procedencia;
ante fallo queda únicamente en cache para diagnóstico, y el RAW anterior se
conserva. Las dos fuentes se intentan independientemente; cualquier error
termina la etapa con código distinto de cero. Cada publicación preliminar se
conserva en el equipo que la descargó; la consolidación usa solo la más reciente
registrada y valida los hashes de las anteriores que estén presentes, evitando
sumar cortes superpuestos. Un clon nuevo no necesita los CSV históricos ausentes;
un hash por sí solo no permite reconstruirlos.

El orquestador hace `SKIP` si los cuatro archivos existen y pasan sus contratos
mínimos: cabecera exacta y hasta 100 filas del CSV, y hojas/legibilidad del XLSX.
Esto no equivale al escaneo completo de ingesta ni verifica vigencia frente a
ediciones manuales previas. `--force` consulta la tabla, exige un único enlace
preliminar del dominio y formato oficiales y rechaza retrocesos; solo vuelve a
descargar el paquete preliminar. No se construye una URL suponiendo la fecha de
publicación. Un contenido idéntico ya registrado no reemplaza RAW ni duplica el
historial. El paquete es preliminar y su corte real se obtiene de `FECHA_DEF`;
la fecha máxima no garantiza registro completo. Pruebas: `tests/test_download_defunciones.py`.

`eda_defunciones` (`scripts/eda_defunciones.py`) depende únicamente de la descarga
y no tiene downstream. Lee los cuatro RAW y el manifiesto sin modificarlos;
requiere coincidencia de los hashes con el último snapshot registrado. Publica
`reports/eda/eda_defunciones_raw.md` y
`reports/eda/eda_defunciones_raw_resumen.json`, mediante temporales y reemplazo
atómico por archivo. Escanea ambos CSV completos por streaming, sin muestreo,
con memoria acotada a agregados: cobertura anual/mensual y fechas, ausencias
por columna, marcadores `*`, sexo, región, lugar de defunción, edad por unidad,
forma del código comunal y resolución/formato diagnóstico por año. Registra
anomalías sin corregir ni eliminar registros. Los códigos históricos numéricos
no se homologan a CIE-10. Incluye una sección reproducible de salud mental:
conteos anuales nacionales y RM por residencia para DIAG1 F00–F99 (por forma,
sin certificar catálogo), suicidio DIAG2 X60–X84, secuelas Y87.0 e intención
no determinada Y10–Y34, conservadas por separado. La composición de categorías
F, glosas publicadas, sexo y edad usa la ventana descriptiva explícita 2021–2025;
solo agrupa edad cuando su unidad publicada es años, conservando el resto
separado. No interpreta los conteos como tasas ni acredita cierre 2024–2025.
Si existe localmente el Parquet independiente
`data/processed/contexto_genero/suicidio_ratio_hm_tasas_nacional_regional.parquet`,
contrasta sus conteos Total nacionales/RM por año contra X60–X84 en DIAG2,
registra su SHA256 y conserva todas las discrepancias. Es un input opcional
de comprobación agregada, sin join individual, descarga ni ejecución de esa
rama; su ausencia se informa y no impide el EDA. Documenta las discrepancias entre el diccionario
(título 2016–2020 y algunos nombres antiguos) y el esquema actual. No hace
joins, filtros clínicos, tasas ni modelos. `SKIP` exige informe con título
esperado y JSON con ambas fuentes, hashes y conteos reconciliados, incluyendo
la nueva sección de salud mental. La disponibilidad/hash del input contextual
opcional participa en SKIP; no comprueba automáticamente otros cambios previos
de inputs/código. `--force` regenera ambos
reportes y una descarga ejecutada fuerza el EDA en la misma invocación.
Pruebas: `tests/test_eda_defunciones.py`.

`clean_defunciones` (`src/data/clean_defunciones.py`) depende únicamente de
`download_defunciones`, su único downstream es `build_mart_suicidios_comuna_weekly`
(rama de suicidios, ver más abajo) y publica **un solo Parquet**,
`data/processed/defunciones/defunciones_nacional.parquet`, con Zstandard. Sus
otros outputs son el EDA `reports/eda/eda_defunciones_consolidadas.md`, el
resumen verificable `reports/eda/eda_defunciones_consolidadas.json` y el
diccionario `reports/dictionary/diccionario_defunciones_nacional.md`.

El periodo, encoding, formatos de fecha, tamaño de bloque y rutas se definen
en `src/data/defunciones_config.json`: inicio explícito y fin nulo para llegar
al último dato de los lotes disponibles. La lógica no contiene años ni nombres
de CSV fijados: descubre los CSV mediante los últimos snapshots registrados
con `dataset=defunciones` y exige que coincidan exactamente con los archivos
de la carpeta RAW, hashes SHA256 incluidos. Rechaza archivos repetidos,
cabeceras distintas de las 27 columnas esperadas, registros no rectangulares,
años no interpretables y solapamiento de años seleccionados entre lotes.

Concatena verticalmente conservando todas las causas, territorios y
repeticiones del periodo. Normaliza nombres, espacios exteriores y tipos;
blancos analíticos son nulos, sin recodificar `*`, 0, 99 ni 999. Conserva el
código comunal publicado y agrega una representación de cinco dígitos solo
si tiene 4/5 dígitos ASCII y mantiene el valor entero; esto no acredita validez
CUT ni corrige 99999. Fechas o edades no interpretables quedan nulas en la
columna tipada, con el texto original y excepciones por fila. Las fechas
ausentes se conservan mediante el año declarado. No imputa glosas, fechas,
edades ni territorio ni cruza otras fuentes.

Añade procedencia por identificador, ruta relativa y ordinal de registro CSV;
el footer contiene configuración, hashes SHA256 de los RAW y del productor,
conteos por fuente/año y nulos. Las repeticiones completas se auditan por
SHA256, en SQLite temporal en disco, sin deduplicar ni cargar todos los datos
en memoria. Tras escribir se relee el Parquet completo, comparando las 36
columnas mediante hash secuencial, conteos, nulos, excepciones y multiplicidad
de hashes originales y normalizados. Se verifican otra vez los RAW antes de
publicar. El JSON registra hashes de los tres artefactos restantes.

La publicación usa temporales fuera de RAW y rollback conjunto de los cuatro
outputs. `SKIP` requiere esquema, compresión, conteos del footer y coincidencia
de configuración, código, RAW y hashes de los artefactos; no relee todas las
filas en cada `SKIP`. `--force` regenera solo esta etapa al seleccionarla. No
modifica RAW ni su manifiesto. Se representa en el ERD lógico como dataset
independiente; no se añade tabla SQL, relación con el MVP ni clase conceptual
de plataforma. Pruebas sintéticas y de integración independiente fila a fila:
`tests/test_clean_defunciones.py` (`-m data_integration` para los RAW reales).

### Resto de ramas y orden global

> [!WARNING]
> La serie de atenciones del año en curso es una fuente mutable. El DEIS sobrescribe periódicamente el ZIP sin versionado. La ejecución normal del pipeline usa el RAW local; el comando de actualización manual anterior vuelve a consultar la fuente. El historial de hashes en `data/raw/provenance_manifest.json` identifica snapshots obtenidos, aunque una URL y un hash no permiten reconstruir una versión antigua si el DEIS ya la sustituyó.

La cartografía del Censo 2024 corresponde a un año cerrado: un RAW válido hace `SKIP` en la operación normal y `--force` constituye la solicitud explícita y registrada para sustituir ese snapshot. El maestro de establecimientos no representa un año cerrado sino el catálogo publicado como actualizado por DEIS; también hace `SKIP` mientras el RAW sea válido y `--force` solicita un nuevo snapshot. Ambas ingestas descargan y validan fuera de `data/raw/`, publican sólo candidatos validados y agregan al historial URL, timestamp UTC, hash, tamaño, ruta RAW y metadata de transporte en el mismo manifest.

`download_censo` descarga a staging (`.cache/downloads/censo/`) un único ZIP nacional de cartografía censal ("GEOPARQUET/Cartografia_censo2024_Pais.zip"), lo valida como transporte íntegro y publica en `data/raw/censo/` únicamente los 5 miembros relevantes para el proyecto — `Cartografia_censo2024_Pais_Comunal.parquet`, `Cartografia_censo2024_Pais_Distrital.parquet`, `Cartografia_censo2024_Pais_Zonal.parquet`, `Cartografia_censo2024_Pais_Entidades.parquet`, `Cartografia_censo2024_Pais_Manzanas.parquet` — más `Diccionario_variables_geograficas_CPV24.xlsx` (diccionario oficial, solo documenta las variables geográficas/llaves, no las variables demográficas `n_*`). El ZIP también contiene Aldeas, Limite_Urbano, Localidades, Provincial y Regional, que no se publican por no ser necesarios en este alcance. Cada uno de los 6 objetivos se valida y publica de forma independiente (mismo criterio SKIP/`--force` por objetivo: si ya es válido no se reemplaza; si falta o es inválido, se descarga el ZIP una sola vez y se republica solo lo pendiente), con su propio `source_id` y snapshot en `provenance_manifest.json`. Todas las capas comparten CRS `SIRGAS 2000 (EPSG:4674)` y geometría `MultiPolygon`.

`clean_censo` depende de `download_censo` y publica en `data/processed/censo/` un GeoParquet RM por capa (`Cartografia_censo2024_RM_<Capa>.parquet`), filtrando `COD_REGION=13` vía predicate pushdown (sin cargar el Parquet nacional completo en memoria) y validando por capa: dominio de `CUT` dentro de las 52 comunas RM, llave del grano sin nulos ni duplicados (`CUT` en Comunal; `ID_DISTRITO` en Distrital; `ID_ZONA` en Zonal; `MANZENT` en Entidades y Manzanas), geometría WKB legible (nulidad e invalidez topológica reportadas, no corregidas), jerarquía `ID_DISTRITO` contra el conjunto de distritos RM válidos (Zonal, Entidades, Manzanas) y no negatividad de `n_per`/`n_hombres`/`n_mujeres` cuando la capa las incluye. No todas las capas cubren las 52 comunas RM por construcción de la fuente, no por un error de filtrado: Zonal es exclusivamente urbana (ausente en 13505, San Pedro, sin zonas urbanas) y Entidades es exclusivamente rural dispersa (ausente en las comunas totalmente urbanizadas). La igualdad `n_hombres + n_mujeres = n_per` se reporta pero no se exige: en Entidades RM existen 2 filas con `n_per` informado y sexo nulo. Manzanas incluye bloques con `MZ_BASE_CENSO=0` (`n_per=0`, no nulo); con los datos disponibles no es posible determinar si corresponden a manzanas efectivamente deshabitadas o a supresión estadística, por lo que no se imputan ni se excluyen. Sumar Manzanas + Entidades no equivale a la población comunal oficial (`dim_poblacion_comuna_censo2024`): para RM se observó una brecha reproducible de 108.997 personas (98,52% de cobertura), distribuida de forma aproximadamente uniforme entre las 52 comunas (no concentrada en outliers), cuya causa exacta no es determinable con esta fuente. Por este motivo `clean_censo` no combina capas ni construye un denominador poblacional subcomunal; esa decisión queda pendiente para la futura capa de cobertura poblacional de isócronas (ver `reports/eda/eda_cartografia_censo2024_subcomunal.md`).

El productor puede informar `validacion_exitosa=False` por geometrías inválidas sin salir con error; si los outputs pasan el contrato mínimo, el orquestador los acepta. Este límite de validación no garantiza topología válida de todas las capas.

`download_censo_poblacion` descarga a staging (`.cache/downloads/censo_poblacion/`) el tabulado oficial INE `D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx` (censo2024.ine.gob.cl), valida que sea un XLSX legible con las hojas "1" (regional) y "2" (comunal) antes de publicarlo en `data/raw/censo/`, y registra URL, timestamp UTC, hash y tamaño en `data/raw/provenance_manifest.json`. Es un año cerrado: RAW válido hace `SKIP`, `--force` solicita explícitamente un nuevo snapshot. `clean_censo_poblacion` depende de esta descarga, lee únicamente la hoja "2" (grano comuna) filtrando `región=13`, valida que las 52 comunas RM coincidan exactamente con el CUT oficial (sin duplicados, sin población nula o no positiva) y contrasta la suma comunal contra el total regional independiente publicado en la hoja "1" del mismo workbook antes de publicar `data/processed/censo/dim_poblacion_comuna_censo2024.parquet` (escritura atómica). Esta dimensión es un insumo poblacional estático de 2024, separado de los marts temporales de Urgencias; no se usa como proxy poblacional para otros años ni se cruza aquí con series históricas.

`download_poblacion_proyecciones` descarga a staging (`.cache/downloads/poblacion_proyecciones/`) el cuadro oficial INE "Estimaciones y Proyecciones de la Población de Chile a nivel comunal 2002-2035" (base Censo 2017, documento metodológico de noviembre 2019; `estimaciones-y-proyecciones-2002-2035-comunas.xlsx`), valida que sea un XLSX legible con la hoja "Est. y Proy. de Pob. Comunal" y dimensiones mínimas esperadas antes de publicarlo en `data/raw/poblacion/`, y registra URL, timestamp UTC, hash y tamaño en `data/raw/provenance_manifest.json`. Es un producto demográfico ya cerrado en su base (Censo 2017): RAW válido hace `SKIP`, `--force` solicita explícitamente un nuevo snapshot. El cuadro publica población residente habitual por sexo (1=Hombre, 2=Mujer), edad simple (0 a 80, top-coded "80 y más") y comuna, al 30 de junio de cada año 2002-2035; los años 2021-2025 corresponden en su totalidad al tramo de proyección (posterior al Censo 2017 usado como ancla), no al tramo de estimación intercensal 2002-2017. Las columnas de texto de región/comuna del workbook presentan corrupción de codificación irrecuperable (U+FFFD); el CUT numérico no está afectado.

`clean_poblacion_proyecciones` depende de `download_poblacion_proyecciones` y de `clean_censo_poblacion` (reutiliza sus glosas comunales validadas, ya que el texto del workbook de proyecciones está corrupto). Filtra `región=13`, valida que sexo esté en {1,2} y edad en [0,80], suma población por comuna×año sobre todas las combinaciones sexo×edad (sin fila "total" en la fuente, por lo que no hay doble conteo), valida cobertura exacta de 52 comunas × 5 años (260 filas), sin nulos ni valores no positivos, y publica `data/processed/censo/dim_poblacion_comuna_anual.parquet` (escritura atómica) con columnas `comuna_codigo`, `comuna_glosa`, `ano`, `poblacion`, `fuente`, `tipo_poblacion` (constante `"proyeccion"` para 2021-2025). Esta dimensión es independiente de `dim_poblacion_comuna_censo2024.parquet`: una es población proyectada (residente habitual, base Censo 2017) y la otra es población efectivamente censada en 2024; no deben usarse como proxy una de la otra y la diferencia observada entre ambas para 2024 no se corrige ni se fuerza a coincidir.

`download_pobreza_comunal` descarga a staging (`.cache/downloads/pobreza_comunal/`) el cuadro oficial del Ministerio de Desarrollo Social y Familia (MDS), Observatorio Social, "Estimaciones de Tasa de Pobreza por Ingresos por Comuna" (Encuesta Casen 2022, Metodología de Estimación para Áreas Pequeñas — SAE, Fay-Herriot; `Estimaciones_Tasa_Pobreza_Ingresos_Comunas_2022.xlsx`), valida que sea un XLSX legible con la hoja "Estimaciones" y dimensiones mínimas esperadas antes de publicarlo en `data/raw/pobreza/`, y registra URL, timestamp UTC, hash y tamaño en `data/raw/provenance_manifest.json`. Es un producto ya cerrado (ronda Casen 2022): RAW válido hace `SKIP`, `--force` solicita explícitamente un nuevo snapshot. El cuadro publica, para las 346 comunas del país, el porcentaje de personas en situación de pobreza por ingresos 2022 con su intervalo de confianza, la presencia de la comuna en la muestra Casen y el tipo de estimación SAE (directa+sintética Fay-Herriot, o sintética pura cuando la comuna no cumple los criterios de inclusión muestral).

`clean_pobreza_comunal` depende de `download_pobreza_comunal` y de `clean_censo_poblacion` (reutiliza sus glosas comunales validadas para mantener consistencia de nombres entre dimensiones). Filtra `región=13`, valida cobertura exacta de las 52 comunas RM contra el CUT oficial sin duplicados, exige que cada comuna RM tenga presencia en la muestra Casen, valida que la tasa esté en el dominio [0,1] y que el intervalo de confianza publicado contenga la tasa, y publica `data/processed/pobreza/dim_vulnerabilidad_comuna.parquet` (escritura atómica) con columnas `comuna_codigo`, `comuna_glosa`, `ano_referencia` (2022, constante), `indicador_vulnerabilidad` (tasa de pobreza por ingresos, proporción 0-1), `nombre_indicador`, `fuente`, `direccion_indicador` (constante `"mayor_valor_mayor_vulnerabilidad"`), `intervalo_confianza_inferior`, `intervalo_confianza_superior` y `tipo_estimacion_sae`. Es un indicador/proxy oficial de vulnerabilidad socioeconómica comunal (tasa de pobreza por ingresos), no un índice general ni compuesto de vulnerabilidad, y un indicador estático de un único período (Casen 2022): no se replica artificialmente por semana/mes ni se combina aquí con demanda de Urgencias o Egresos para construir un puntaje de riesgo compuesto.

`download_dotacion_camas` (`src/data/download_dotacion_camas.py`) no tiene upstream ni downstream por ahora. Descarga a staging (`.cache/downloads/camas/`) dos libros XLSX oficiales del DEIS y la División de Gestión de la Red Asistencial (DIGERA) y publica en `data/raw/camas/`: `dotacion_camas_snss_2010_2025.xlsx` (establecimientos públicos del SNSS; una hoja `2010-2025` por Servicio de Salud, establecimiento y área funcional, con una columna por año) y `dotacion_camas_no_snss_2019_2025.xlsx` (establecimientos privados; una hoja por año `2019` a `2025`, que la propia fuente rotula "dato referencial" y atribuye también a la Superintendencia de Salud). Es dotación anual declarada (stock de camas por año), no ocupación ni disponibilidad en tiempo real, por lo que no contradice la restricción de no gestionar cupos. Ambos libros cubren hasta 2025, año cerrado: un RAW válido hace `SKIP` sin consultar la fuente y `--force` solicita explícitamente un nuevo snapshot. La URL del libro SNSS incluye el sufijo `01-12-2025`, que se conserva literal en el manifiesto sin interpretarlo; si el DEIS publica una versión con otro rango de años (se infiere que lo hará con otro nombre de archivo, por el patrón de las dos URLs actuales, pero no está comprobado), se incorpora cambiando la configuración `CAMAS_SOURCES`, no sobrescribiendo en silencio. Cada fuente se valida y publica de forma independiente (si una falla, la otra igual se publica y la etapa termina con error). Antes de publicar valida que el XLSX sea legible, que existan las hojas esperadas, que el encabezado (fila 3) coincida con el esperado, que estén todos los años (columnas 2010-2025 en el libro SNSS; hojas 2019-2025 con `Total <año>` coherente con la hoja en el no SNSS) y un mínimo de filas; la validación es estructural y no juzga el contenido. Si la descarga o la validación fallan, el RAW previo no se toca; si falla el registro de procedencia, se restaura el RAW anterior. Cada snapshot agrega a `data/raw/provenance_manifest.json` (`source_id` `deis_dotacion_camas_snss` y `deis_dotacion_camas_no_snss`) URL, timestamp UTC, tamaño, SHA256 y las cabeceras HTTP `Last-Modified` y `ETag` observadas; con `--force` y contenido idéntico no se reemplaza el RAW ni se duplica el historial. A diferencia de otras descargas, usa verificación TLS estándar (el endpoint la supera). El orquestador valida ambos libros con el mismo contrato y realiza `SKIP` cuando los dos son válidos. Sus pruebas están en `tests/test_download_dotacion_camas.py`. Observado en el RAW, que se conserva sin modificar: el libro SNSS tiene 8 filas de nota al pie y mezcla en las mismas columnas filas de detalle por área funcional con filas `Total` por establecimiento (198 filas con etiqueta de total, incluida una `Total País`); el libro no SNSS tiene una fila `TOTAL` por hoja, notas al pie solo en las hojas 2023 (1), 2024 (3) y 2025 (4), y 10 celdas con el texto `ok` en la columna 12 de las hojas 2024 y 2025 (5 en cada una) cuyo significado no está documentado: no es posible determinarlo con los datos disponibles. Por la estructura de las primeras filas del libro no SNSS (una fila con el total del establecimiento seguida de sus filas por área), sumar una columna sin distinguir totales de detalle probablemente duplicaría camas; es una inferencia no verificada sobre todo el libro. La etapa `clean_dotacion_camas` los resuelve sin imputar ni descartar nada (ver más abajo).

`clean_dotacion_camas` (`src/data/clean_dotacion_camas.py`) depende de `download_dotacion_camas`, no tiene downstream por ahora y publica en `data/processed/camas/` un Parquet por libro: `dotacion_camas_snss.parquet` (las columnas del libro SNSS: Servicio de Salud, código, tipo y nombre del establecimiento, código y nombre del área funcional y una columna `camas_AAAA` por año 2010-2025; 1.694 filas, una por fila del libro, incluida la fila `Total` de cada hospital) y `dotacion_camas_no_snss.parquet` (las siete hojas anuales 2019-2025 apiladas con una columna `ano`; 4.631 filas). Diccionario en `reports/dictionary/diccionario_dotacion_camas.md`. Solo contienen datos de dotación: las notas al pie, las marcas que remiten a ellas y los totales nacionales publicados quedan fuera del Parquet y siguen en el RAW; los totales nacionales se usan para validar (la suma de los totales por hospital debe coincidir con el total nacional del libro; una discrepancia se informa en el log, nunca se corrige). No imputa ni corrige: un blanco queda nulo y no es un cero (el cero explícito del origen se conserva), una celda con marca de nota en lugar de una cifra queda nula, los nombres se normalizan solo en espacios y asteriscos finales y un hospital repetido en una hoja no se elimina (se informa en el log). Clasifica cada fila del origen por patrón y **falla si una fila no responde a ninguno, si hay datos fuera de las columnas contempladas, si un valor no es un entero no negativo o si dos filas repiten la llave lógica**, para no perder ni elegir datos en silencio; las filas de área se asocian a su hospital por contigüidad, no por nombre. Valida la estructura de ambos libros con los mismos validadores de la descarga y escribe los dos archivos de forma atómica (temporales y reemplazo conjunto con rollback) con compresión `zstd`; el footer de cada Parquet registra solo el SHA256 del libro de origen (`raw_sha256`). El orquestador valida el esquema de las dos salidas y realiza `SKIP` cuando son válidas; `--force` las regenera. Es dotación anual declarada, no ocupación ni disponibilidad en tiempo real. No se enlaza con Egresos (que no identifica el establecimiento); el vínculo con `dim_oferta_urgencia_rm` por `establecimiento_codigo` es solo lógico y parcial (44 de sus 174 establecimientos tienen registro de camas). La dimensión derivada `dim_camas_psiquiatria_hospital_rm` (stage `build_dim_camas_psiquiatria_hospital_rm`) materializa ese vínculo para los hospitales de la oferta. Sus pruebas están en `tests/test_clean_dotacion_camas.py` y la verificación de que no se perdieron datos de dotación contra los libros reales, con una lectura independiente del parser, en `tests/test_dotacion_camas_integridad.py` (`pytest -m data_integration`).

`download_estadisticas_hospitalarias` (`src/data/download_estadisticas_hospitalarias.py`) no tiene upstream; sus downstream son `clean_estadisticas_hospitalarias` y, a través de ella, `eda_estadisticas_hospitalarias`. Descarga a staging (`.cache/downloads/estadisticas_hospitalarias/`) los libros XLSX oficiales del repositorio REM-20 del DEIS y publica en `data/raw/estadisticas_hospitalarias/` dos familias: «Indicadores Hospitalarios según Servicio de Salud» (SNSS, por establecimiento y nivel de cuidado: días cama disponibles y ocupados, días de estada, egresos, fallecidos, traslados y sus razones, con acumulado y un valor por mes) en `indicadores_hospitalarios_2014_2023.xlsx` (una hoja por año), `indicadores_hospitalarios_2024.xlsx`, `indicadores_hospitalarios_2025.xlsx` e `indicadores_hospitalarios_AAAA.xlsx` para cada año en curso, y «Categorización de Pacientes Hospitalizados Según Riesgo Dependencia» (CUDYR) en `categorizacion_riesgo_dependencia_AAAA_tN.xlsx`, un libro por trimestre (2024-T1 a 2025-T4). Publica además `diccionario_rem20.xlsx`, el diccionario de datos REM-20 que el DEIS publica en datos.gob.cl (definición de días cama, egresos, traslados e índices; describe el conjunto en formato largo de ese portal, con nombres de campo propios, y no cubre la categorización); se valida su título, su encabezado y que traiga los 11 campos de indicadores. URLs, años y trimestres de los libros cerrados se declaran en `src/data/estadisticas_hospitalarias_config.json`, porque sus nombres no siguen un patrón (`año 2025-_16042026`, `SegundoTrimestre`). **Año en curso sin mes fijo:** para cada año desde `en_curso.primer_ano` hasta el año civil de Chile se consulta (HEAD) la plantilla de URL observada, `{ano}/Estadísticas Hospitalarias {mes} {ano}.xlsx`, de diciembre a enero, y se toma el último mes publicado; los trimestres de categorización del año se buscan igual, y uno no publicado no es error. Que el DEIS mantenga esa plantilla es una inferencia de las URLs observadas: si no se encuentra ningún mes de un año ya pasado la etapa termina con error, y si es el año civil (p. ej., en enero, antes del primer corte) solo lo advierte; en ningún caso toca el RAW vigente. Un corte con menos meses que el RAW vigente no lo reemplaza. El RAW del año en curso se reemplaza con cada corte nuevo y el mes de corte (`corte_mes`) queda en el historial. Antes de publicar valida el año del título de cada hoja (no el nombre de la hoja, que varía), el encabezado exacto, que los meses sean los esperados (12 en años cerrados; los del nombre del corte en el año en curso) y un mínimo de filas; la categorización exige además el año del título. Cada libro se valida y publica de forma independiente, con rollback del RAW previo si falla el registro de procedencia (`source_id` `deis_rem20_<archivo>`: URL, timestamp UTC, tamaño, SHA256, `Last-Modified` y `ETag`); un contenido idéntico no duplica el historial. Usa verificación TLS estándar. **`SKIP` y `--force`:** el orquestador exige los libros cerrados y los de años en curso ya pasados; el del año civil, solo cuando ya existe (en enero el DEIS aún no publica ningún mes). Con todos válidos hace `SKIP` sin consultar la fuente. Para incorporar un corte mensual nuevo del año en curso hay que pedirlo explícitamente con `python scripts/run_pipeline.py --stage download_estadisticas_hospitalarias --force`, que vuelve a consultar todas las fuentes y propaga a sus downstream. Cuando el DEIS publique el libro consolidado de un año en curso, se agrega a `cerrados` y se avanza `primer_ano`. Pruebas: `tests/test_download_estadisticas_hospitalarias.py`.

`clean_estadisticas_hospitalarias` (`src/data/clean_estadisticas_hospitalarias.py`) depende de `download_estadisticas_hospitalarias`; su downstream es `eda_estadisticas_hospitalarias`. Publica en `data/processed/estadisticas_hospitalarias/` un Parquet por familia, con las columnas de su libro y los libros apilados por año: `indicadores_hospitalarios_snss.parquet` (2014 al año en curso; llave `ano, servicio_salud_codigo, establecimiento_codigo, nivel_cuidado_codigo, indicador`) y `categorizacion_riesgo_dependencia.parquet` (la jerarquía región > Servicio de Salud > establecimiento > nivel de cuidado aplanada, con `ano`, `trimestre`, total y las 12 categorías A1-D3). Diccionario en `reports/dictionary/diccionario_estadisticas_hospitalarias.md`. **Filas agregadas del origen:** cada hoja de indicadores intercala con el detalle filas `Datos País`, `Datos Servicio Salud` y `Datos Establecimiento` en las mismas columnas. El Parquet conserva **solo el detalle** (un nivel de cuidado de un establecimiento), porque sumar ambos contaría lo mismo dos o tres veces, y las agregadas se usan para conciliar: la suma del detalle debe reconstruir cada agregado publicado en conteos y en cada mes, y el acumulado de cada conteo debe ser la suma de sus meses. Las discrepancias se informan en el log y nunca se corrigen; el acumulado anual del promedio de camas disponibles se informa aparte, porque no es aditivo entre áreas. En la categorización se valida que el total de cada fila sea la suma de sus 12 categorías. No imputa ni corrige: un blanco queda nulo y los meses aún no publicados del año en curso quedan nulos, no en cero. Falla si una fila no responde a un patrón conocido, si un indicador no es uno de los 11 conocidos, si un valor no es numérico, si hay datos fuera de las columnas contempladas, si una llave se repite o si dos libros declaran el mismo año. Escribe ambos archivos de forma atómica (temporales, relectura y reemplazo conjunto con rollback) con `zstd`; el footer registra `raw_sha256_por_archivo` (ruta y SHA256 de cada RAW). El contrato de `SKIP` exige el esquema exacto y que esos hashes coincidan con los RAW vigentes, de modo que un corte mensual nuevo invalida el Parquet; `--force` lo regenera. Pruebas sintéticas en `tests/test_clean_estadisticas_hospitalarias.py` y verificación contra los RAW reales con una lectura independiente (`pandas.read_excel`) en `tests/test_estadisticas_hospitalarias_integridad.py` (`pytest -m data_integration`).

`eda_estadisticas_hospitalarias` (`scripts/eda_estadisticas_hospitalarias.py`) depende de `clean_estadisticas_hospitalarias` y de `clean_dotacion_camas`, y no tiene downstream. Relee los RAW con el parser de la limpieza y exige que los hashes del footer de ambos Parquet coincidan con ellos y que tengan las mismas filas. Publica `reports/eda/eda_estadisticas_hospitalarias.md` y `reports/eda/eda_estadisticas_hospitalarias_resumen.json` con reemplazo atómico. Reporta archivos y corte, estructura y filas agregadas del origen, conciliación detalle/agregados, la definición observada de cada razón publicada por año, días cama ocupados por sobre los disponibles, psiquiatría de la Región Metropolitana, coherencia con la dotación de camas (misma llave de establecimiento y área) y la categorización CUDYR, citando a González et al. (2024) para la lectura de las categorías. Incluye las definiciones del diccionario oficial REM-20, leídas del RAW, junto a la fórmula observada de cada indicador; la correspondencia campo-glosa es por nombre y se declara como inferencia. Distingue hechos, inferencias y lo que no es determinable; no corrige datos. `SKIP` exige el título del informe y que los hashes del resumen coincidan con los Parquet vigentes; `--force` lo regenera. Pruebas: `tests/test_eda_estadisticas_hospitalarias.py`.

El siguiente listado representa el orden topológico actual del DAG. El orquestador ejecuta únicamente las etapas necesarias según los outputs existentes, las dependencias, el `--stage` solicitado y el uso de `--force`

For Egresos, `download_deis` publishes the CSV in each ZIP through the
deterministic RAW contract `data/raw/egresos/egresos_<year>.csv`. The original
name of the CSV member published by DEIS is recorded in
`data/raw/provenance_manifest.json`, so `clean_egresos` does not depend on
historical filename variants.

La etapa `build_egresos_f00_f99` depende de `clean_egresos`, no tiene downstream por ahora y publica `data/processed/egresos/egresos_f00_f99_nacional_2020_2025.parquet` (218.794 filas, alcance **nacional**, 2020-2025) junto con `data/processed/egresos/catalogo_cie10_f00_f99.csv` (407 subcategorías CIE-10 del capítulo F00-F99, extraídas en tiempo de ejecución de `data/raw/egresos/Diccionario BD egresos hospitalario.xlsx`, hoja "codigo CIE-10"; no de un hardcode). Su grano es 1 fila = 1 registro de egreso publicado (dataset disociado, sin identificador de paciente ni de establecimiento; no se deduplica). Filtra `diag1` contra ese catálogo oficial (verificado por código idéntico, sin discrepancias, a `diag1` que comienza con "F" sobre los 9.379.787 egresos nacionales 2020-2025) y agrega la columna derivada `residente_rm` (booleana, nula si `region_residencia` es nulo en origen). Agrega además cuatro columnas armonizadas, sin modificar las originales: `sexo_armonizado` (lee los códigos 1/2/3 de 2021 como el texto de los otros años, con la convención de códigos del DEIS en Defunciones y la distribución estable entre años como respaldo), `grupo_edad_armonizado` (tramos decenales comunes; `80 y más` une `80 a 89` y `90 y más` porque el `85 A MAS` de 2021 se solapa con ambos) y `dias_estada_acotado_anual`/`estadia_mayor_a_un_ano` (acota en 365 los días cama que un egreso aporta a su año, porque Egresos publica el año y no la fecha). Un valor de sexo o edad sin regla de armonización hace fallar la etapa en vez de filtrar directamente a RM: se prioriza el alcance nacional porque `region_residencia`/`comuna_residencia` son residencia del paciente, no ubicación del hospital, y F00-F99 ya es solo 2,33% del total nacional (ver `reports/dictionary/diccionario_egresos_f00_f99_nacional.md` para la decisión completa). Se confirmó contra el diccionario oficial DEIS que `pertenencia_establecimiento_salud` (`PERTENENCIA_ESTABLECIMIENTO_SALU` en el CSV, nombre truncado a 32 caracteres) representa la pertenencia del **establecimiento** al SNSS ("Tipo de pertenencia (Perteneciente o No perteneciente al SNSS)"), no del paciente ni de su residencia; Egresos no tiene identificador único de establecimiento, por lo que cualquier relación con Urgencias o con `dim_oferta_urgencia_rm` es necesariamente ecológica/territorial, nunca a nivel de registro individual (a diferencia de Urgencias, que sí identifica cada establecimiento por `establecimiento_codigo`). No se homologan `sexo` ni `grupo_edad` entre años: 2021 publica ambos campos con un esquema propio (sexo como código numérico en texto; grupo_edad quinquenal/fino) incompatible con el esquema de 2020/2022-2025, sin evidencia documental para construir un cruce reproducible (ver diccionario y EDA). Antes de publicar valida: `diag1` 100% dentro del catálogo F00-F99; años observados = {2020..2025} exactos; el conteo final coincide con la suma filtrada año-por-año y con un recuento independiente por un camino de código distinto (multi-archivo `pyarrow.dataset`); `dias_estada` sin nulos ni valores ≤0; y los campos categóricos (`sexo`, `pertenencia_establecimiento_salud`, `grupo_edad`, `glosa_prevision`, `prevision`, `condicion_egreso`) restringidos a los dominios ya documentados 2020-2025 (un valor nuevo hace fallar la etapa). El orquestador valida existencia/esquema de ambos outputs y realiza `SKIP` cuando son válidos; `--force` los regenera. Sus pruebas están en `tests/test_build_egresos_f00_f99.py`. No cruza con Urgencias ni por paciente ni por establecimiento (restricción invariante del proyecto); no implementa modelamiento causal, regresión, ni análisis de factores asociados a duración de estadía (pendiente, fuera de alcance de esta etapa).

1. `download_censo` → (Descarga a RAW las 5 capas de cartografía Censo 2024 -- Comunal, Distrital, Zonal, Entidades, Manzanas -- y su diccionario oficial de variables geográficas)
2. `download_censo_poblacion` → (Descarga a RAW el tabulado comunal oficial INE de población censada 2024)
3. `download_poblacion_proyecciones` → (Descarga a RAW el cuadro comunal oficial INE de estimaciones/proyecciones de población 2002-2035)
4. `download_pobreza_comunal` → (Descarga a RAW el cuadro comunal oficial MDS/Casen 2022 de tasa de pobreza por ingresos, SAE)
5. `download_dotacion_camas` → (Descarga a RAW los dos libros oficiales DEIS de dotación de camas hospitalarias: establecimientos SNSS 2010-2025 y no SNSS 2019-2025)
6. `download_estadisticas_hospitalarias` → (Descarga a RAW los libros REM-20 del DEIS: indicadores hospitalarios mensuales por establecimiento y nivel de cuidado, 2014 al último corte del año en curso, y categorización CUDYR trimestral)
7. `download_defunciones` → (Descarga y extrae a RAW los paquetes DEIS 1990–2023 y 2024–2026, con sus diccionarios)
8. `eda_defunciones` → (EDA nacional de solo lectura sobre ambos paquetes RAW, sin generar processed)
9. `clean_defunciones` → (Consolidación nacional en un Parquet tipado, con procedencia, excepciones y validación de preservación)
10. `download_deis` → (Descarga Urgencias y Egresos a RAW)
11. `download_establishments` → (Descarga Maestro Establecimientos a RAW)
12. `download_contexto_genero` → (Descarga RAW de cuatro cuadros XLSX de Estadísticas de Género)
13. `normalize_contexto_genero` → (Normalización independiente de los cuatro cuadros contextuales)
14. `build_mart_contexto_genero_indicador_sexo` → (Mart canónico de serving MVP, contextual e independiente)
15. `clean_establishments` → (Limpieza y filtrado RM)
16. `clean_censo` → (Filtro espacial RM para las 5 capas de cartografía Censo 2024: Comunal, Distrital, Zonal, Entidades, Manzanas)
17. `clean_censo_poblacion` → (Dimensión de población censada 2024 por comuna RM)
18. `clean_poblacion_proyecciones` → (Dimensión anual de población comunal RM 2021-2025, INE proyecciones base Censo 2017)
19. `clean_pobreza_comunal` → (Dimensión de vulnerabilidad socioeconómica comunal RM, MDS/Casen 2022, tasa de pobreza por ingresos SAE)
20. `clean_dotacion_camas` → (Un Parquet por libro de dotación anual de camas hospitalarias, con las columnas del libro: camas por área funcional y año, y total por hospital)
21. `clean_estadisticas_hospitalarias` → (Un Parquet por familia REM-20: indicadores hospitalarios solo con el detalle por nivel de cuidado, conciliado con los agregados del origen, y categorización CUDYR aplanada)
22. `eda_estadisticas_hospitalarias` → (EDA de los RAW y Parquet REM-20: agregados, definición de las razones, sobreocupación, psiquiatría RM, coherencia con la dotación y CUDYR)
23. `build_catalogs` → (Creación de catálogo F00-F99)
24. `clean_urgencias` → (Limpieza de Urgencias desde 2020 hasta el año corriente y unión territorial)
25. `clean_egresos` → (Normalización reproducible de Egresos Hospitalarios 2020-2025)
26. `build_egresos_f00_f99` → (Dataset canónico nacional de Egresos F00-F99, 2020-2025, con flag de residencia RM)
27. `eda_establishments` → (Validación EDA de Establecimientos)
28. `eda_urgencias` → (Generación de tablas base del EDA de Urgencias)
29. `profile_urgencias_sm_coverage` → (Perfil comuna×semana ID 36 para cobertura 2021–2025)
30. `build_urgencias_comuna_marts` → (Marts históricos comunales semanal y mensual de Urgencias, 2021–2025, con tasas por 10.000 habitantes)
31. `build_urgencias_establecimiento_mart` → (Mart histórico establecimiento×mes de Urgencias, 2021–2025, sin población ni tasas)
32. `build_urgencias_establecimiento_weekly_mart` → (Mart histórico establecimiento×semana DEIS de Urgencias, 2021–2025, con ID42: hospitalizaciones derivadas desde urgencia por F00-F99)
33. `eda_mart_urgencias_establecimiento_weekly` → (EDA del mart semanal por establecimiento: cobertura, volumen modelable y estabilidad de ID42)
34. `build_urgencias_comuna_etario_mart` → (Mart histórico comuna×mes×grupo_etario de Urgencias, 2021–2025, formato largo)
35. `build_dim_oferta_urgencia_rm` → (Dimensión canónica de oferta territorial de urgencia RM: snapshot actual, no serie histórica)
36. `build_dim_camas_psiquiatria_hospital_rm` → (Dimensión hospital ↔ camas de psiquiatría: une los hospitales de la oferta de urgencia con la dotación SNSS del último año y marca los que alimentaron el modelo)
37. `build_mart_ocupacion_psiquiatria_hospital_rm` → (Mart mensual de ocupación de camas de psiquiatría por área y hospital de la oferta RM, REM-20, con brecha de capacidad y verificación de la identidad promedio = días / días del mes)
38. `eda_mart_ocupacion_psiquiatria_hospital_rm` → (EDA del mart de ocupación: identidad, saturación por área, sobre la capacidad y coherencia con la dotación)
39. `build_mart_egresos_f00_f99_rm` → (Perfil anual de hospitalizaciones F00-F99 de residentes RM, por región y comuna de residencia: tasa, estadía, sexo, edad, diagnóstico y previsión)
40. `build_contraste_camas_psiquiatria_rm` → (Contraste anual de camas de psiquiatría ocupadas: Egresos frente a REM-20)
41. `build_capa_oferta_urgencia_rm` → (Capa de puntos GeoParquet EPSG:4674 de la oferta de urgencia, con join espacial a comuna contrastado con la comuna declarada)
42. `resolve_coordenadas_establecimientos` → (Lista final de establecimientos con coordenada faltante o anómala, con resolución justificada: exclusión o geocodificación requerida; no imputa)
43. `build_cobertura_urgencia_comuna` → (MVP de cobertura territorial simple: distancia en línea recta de la población censal 2024 a la oferta de urgencia, por comuna, con reporte de limitaciones)
44. `build_mart_mvp_territorial_comuna` → (Mart canónico MVP territorial comunal: integra demanda 2025, población 2025/2024, vulnerabilidad 2022 y oferta actual en una fila por comuna RM)
45. `eda_contexto_genero` → (EDA reproducible de los cuatro cuadros contextuales)
46. `eda_mart_contexto_genero_indicador_sexo` → (EDA reproducible del mart contextual de serving)
47. `eda_series_demanda_sm` → (EDA de series temporales previo al modelo de demanda: calendario, estacionariedad, autocorrelación, régimen, heterogeneidad y baseline estacional)
48. `benchmark_demanda_sm` → (Backtesting rolling origin de los modelos de demanda: baselines, modelo global LightGBM y variantes reconciliadas)
49. `evaluate_holdout_demanda_sm` → (Evaluación del modelo seleccionado en el período posterior al entrenamiento, con el snapshot del año en curso identificado por SHA256)
50. `forecast_demanda_sm` → (Pronóstico vigente persistido con su manifiesto de procedencia, para que la API no lo recalcule en cada arranque)
51. `benchmark_establecimientos_sm` → (Backtesting del pronóstico por establecimiento para atenciones de salud mental, ID36, y hospitalizaciones derivadas desde urgencia, ID42, con la misma regla de selección del modelo comunal)
52. `evaluate_holdout_establecimientos_sm` → (Evaluación en el año en curso de las selecciones congeladas del pronóstico por establecimiento, con universo fijo y snapshot identificado por SHA256)
53. `forecast_establecimientos_sm` → (Pronóstico vigente por establecimiento persistido con su manifiesto, incluida la identidad del snapshot del año en curso)
54. `build_mart_suicidios_comuna_weekly` → (Mart semanal de suicidios, defunciones X60-X84, por comuna de residencia RM y semana DEIS, con días por semana, población y marca de registro incompleto)
55. `eda_mart_suicidios_comuna_weekly` → (EDA del mart de suicidios: conciliación, calendario DEIS verificado contra Urgencias, registro final, cambio de nivel, estacionalidad, dispersión, ceros y heterogeneidad comunal)
56. `benchmark_suicidios` → (Backtesting del pronóstico semanal de suicidios en región y comunas: baseline, modelos del registro y GLM de Poisson estacional con reparto comunal de Bayes empírico; selección por RMSSE)
57. `evaluate_holdout_suicidios` → (Evaluación en el año en curso de la selección congelada del pronóstico de suicidios)
58. `forecast_suicidios` → (Pronóstico vigente de suicidios persistido con su manifiesto de vigencia)

La etapa `build_dim_oferta_urgencia_rm` depende de `clean_establishments` y `clean_urgencias`, sus consumidores directos son `build_capa_oferta_urgencia_rm`, `resolve_coordenadas_establecimientos`, `build_cobertura_urgencia_comuna` y `build_mart_mvp_territorial_comuna`, y publica `data/processed/geo/dim_oferta_urgencia_rm.parquet`. Distingue dos temporalidades: el universo y criterio de inclusión son un snapshot ACTUAL del catálogo de establecimientos (no una serie histórica) — incluye establecimientos vigentes cuyo `tipo_establecimiento_glosa` es `Hospital` o termina en el acrónimo DEIS `(SAPU)`, `(SAR)` o `(SUR)`, más una excepción documentada y detectada dinámicamente contra Urgencias (establecimientos que reportan `tipo_establecimiento_urgencia="CEAR"` sin caer en el tipo anterior) —; la evidencia de reporte (`reporto_id1_periodo`, `reporto_id36_periodo`, `ultimo_ano_reporte_id36`, `tipo_urgencia_reportado`) usa en cambio el período canónico CERRADO 2021-2025, excluyendo 2020 (discontinuidad metodológica de salud mental) y 2026 (año parcial/mutable); es información temporal complementaria, no el criterio de inclusión ni un filtro. No usa `tiene_servicio_urgencia` ni `tipo_urgencia` del maestro como criterio de inclusión (se comprobó que no son confiables: ver `reports/eda/eda_dim_oferta_urgencia_rm.md`) ni exige actividad `ID36>0` para pertenecer a la oferta. Antes de publicar valida unicidad de `establecimiento_codigo`, dominio de `criterio_inclusion_oferta` + coherencia con el tipo, vigencia, formato de `comuna_codigo`, nulidad conjunta de coordenadas, bounding box geográfico de la RM y coherencia entre los flags de reporte. El orquestador valida existencia/esquema del Parquet y realiza `SKIP` cuando es válido; `--force` lo regenera. Sus pruebas están en `tests/test_build_dim_oferta_urgencia_rm.py`. No implementa OSM/GTFS ni isócronas; es únicamente el insumo de oferta para esa capa futura de accesibilidad territorial.

La etapa `build_dim_camas_psiquiatria_hospital_rm` (`src/data/build_dim_camas_psiquiatria_hospital_rm.py`) depende de `clean_dotacion_camas` y `build_dim_oferta_urgencia_rm`, no tiene downstream en el DAG (la API la lee como capa opcional para la línea de camas del tablero) y publica `data/processed/camas/dim_camas_psiquiatria_hospital_rm.parquet`, documentado en `reports/dictionary/diccionario_dim_camas_psiquiatria_hospital_rm.md`. Grano: 1 fila = 1 hospital de la oferta de urgencia (`tipo_establecimiento = "Hospital"`), unido a la dotación SNSS por `establecimiento_codigo` (la misma llave entera en ambas fuentes; no se une por nombre ni por el código textual `NN-NNN` de Urgencias). `camas_psiquiatria` suma las áreas funcionales de psiquiatría (nombre con «Psiquiatr», sin la fila `Total` ni el área sociosanitaria) del último año con columna `camas_AAAA`, detectado dinámicamente; es dotación anual declarada, no ocupación ni disponibilidad. Conserva todos los hospitales de la oferta: `en_dotacion_snss = False` o sin cifra de psiquiatría dejan `camas_psiquiatria` nula, nunca en cero. Hereda `reporto_id36_periodo` de la oferta para identificar los hospitales que alimentaron el modelo de demanda; los totales territoriales (API) suman solo esos. Antes de publicar valida que no se pierda ningún hospital de la oferta, unicidad de `establecimiento_codigo`, formato `13xxx` de la comuna, un único `ano_camas`, camas no negativas, que un hospital fuera de la dotación no tenga camas y la coherencia entre `camas_psiquiatria` y `n_areas_psiquiatria`; falla si la dotación repite un área de psiquiatría por establecimiento. Escribe de forma atómica con compresión `zstd`. El orquestador valida el esquema del Parquet y realiza `SKIP` cuando es válido; `--force` lo regenera. Sus pruebas están en `tests/test_build_dim_camas_psiquiatria_hospital_rm.py` y las del endpoint en `tests/test_api.py`.

La etapa `build_mart_ocupacion_psiquiatria_hospital_rm` (`src/data/build_mart_ocupacion_psiquiatria_hospital_rm.py`) depende de `clean_estadisticas_hospitalarias` y `build_dim_oferta_urgencia_rm`; su downstream es `eda_mart_ocupacion_psiquiatria_hospital_rm`. Publica `data/processed/marts/mart_ocupacion_psiquiatria_hospital_rm.parquet` (diccionario en `reports/dictionary/diccionario_mart_ocupacion_psiquiatria_hospital_rm.md`): una fila por **área de psiquiatría** de un hospital de la oferta de urgencia y mes publicado del REM-20 (mismo criterio de área que `dim_camas_psiquiatria_hospital_rm`), con días cama ocupados y disponibles, sus promedios diarios (`días / días del mes`), las camas libres por día (la brecha; negativa = sobre la capacidad) y el índice ocupacional. El grano es el área porque el total del hospital puede ocultar un área saturada; el total se obtiene sumando días cama (`por_hospital`), nunca promediando índices. Antes de publicar **verifica la identidad que sustenta el cálculo**: el «Promedio Cama Disponibles» que el DEIS publica para cada área y mes debe coincidir con `días cama disponibles / días del mes` dentro del redondeo de la fuente (±0,005 por área); si no, falla. También falla si un área tiene un mes publicado a medias o si se repite la llave `establecimiento_codigo, nivel_cuidado_codigo, ano, mes`. Los meses aún no publicados no generan filas (no son cero). Escribe de forma atómica con `zstd`. El orquestador valida el esquema y hace `SKIP`; `--force` lo regenera, y un corte nuevo del REM-20 lo regenera por propagación. `eda_mart_ocupacion_psiquiatria_hospital_rm` (`scripts/eda_mart_ocupacion_psiquiatria_hospital_rm.py`) depende del mart y de `build_dim_camas_psiquiatria_hospital_rm`; publica `reports/eda/eda_mart_ocupacion_psiquiatria_hospital_rm.md` y su resumen JSON. Recalcula la identidad desde el insumo, sin pasar por el mart, y reporta cobertura, saturación por área en los últimos 12 meses (meses sin holgura, con menos de una cama libre por día, y meses sobre la capacidad, ambos solo en meses con camas disponibles), ocupación agregada por año, último mes por hospital, el **nivel de colapso** de cada hospital (ocupación de sus camas de psiquiatría en los últimos 12 meses publicados, como razón de sumas: holgura < 85 %, presión 85-90 %, saturación ≥ 90 %, y «sobre la capacidad» si algún área superó sus camas disponibles; umbrales de la literatura: Royal College of Psychiatrists y Bagust et al., BMJ 1999), las áreas sin dotación declarada con su causa observada (libro sin cifra, área habilitada después del último año del libro o ausente sin causa determinable) y un backtest que mide si las camas disponibles del REM-20 reproducen la dotación declarada (en psiquiatría, 60 % de acierto exacto y 69 % a ±1 cama: insuficiente para imputarla, por lo que no se imputa), además de la relación con el pronóstico de hospitalizaciones. Lee la dotación SNSS para esas dos secciones. Lee como entrada opcional el Parquet del pronóstico por establecimiento, sin depender de su etapa. `SKIP` exige el título y que el resumen registre el SHA256 del mart vigente. Pruebas: `tests/test_build_mart_ocupacion_psiquiatria_hospital_rm.py`. La API lo expone en `/api/v1/establecimientos/{codigo}` (`ocupacion_psiquiatria`: total mensual del hospital, y `areas_psiquiatria`: saturación, dotación declarada del último año o la causa de su ausencia, y serie mensual de cada área, todo en la ventana de la historia semanal) y en `/api/v1/establecimientos` (`colapso_psiquiatria`: nivel de colapso de cada hospital, con la misma función `nivel_colapso` que el EDA) como capa opcional: sin el mart, el detalle responde sin ocupación. Es estadística mensual consolidada, no ocupación en tiempo real.

La etapa `build_mart_egresos_f00_f99_rm` (`src/data/build_mart_egresos_f00_f99_rm.py`) depende de `build_egresos_f00_f99` y `clean_poblacion_proyecciones` y publica dos tablas sobre los egresos con diagnóstico principal F00-F99 de los residentes de la RM. `data/processed/marts/mart_egresos_f00_f99_rm_anual.parquet` (grano territorio × año, para la región y las 52 comunas de residencia): egresos, población INE, tasa por 10.000 habitantes, días de estada (mediana y p90), proporción en hospitales del SNSS y de estadías de más de un año. `data/processed/marts/mart_egresos_f00_f99_rm_desglose.parquet` (grano territorio × año × dimensión × categoría): egresos por sexo y grupo de edad armonizados, bloque diagnóstico CIE-10 (F00-F09 a F99) y previsión agrupada. Es el complemento de Urgencias: Urgencias cuenta el establecimiento donde se atendió la persona y Egresos la comuna donde vive; no se enlazan por registro. Una comuna sin egresos tiene cero explícito (el registro es exhaustivo) y estadía nula; la proyección de población comunal empieza en 2021, así que la tasa de 2020 queda nula. Valida que las comunas sumen la región, que la región reconcilie con los egresos de residentes y que cada desglose sume su total. La API lo sirve en `/api/v1/hospitalizaciones-residentes/{series_id}` y el tablero comunal lo muestra en el panel «Hospitalizaciones de quienes viven en…». Pruebas: `tests/test_mart_egresos_f00_f99_rm.py` y `tests/test_api_hospitalizaciones.py`.

La etapa `build_contraste_camas_psiquiatria_rm` (`src/data/build_contraste_camas_psiquiatria_rm.py`) depende de `build_egresos_f00_f99` y `build_mart_ocupacion_psiquiatria_hospital_rm` y publica `data/processed/marts/contraste_camas_psiquiatria_rm.parquet`: por año con ambas fuentes completas (12 meses de REM-20), las camas ocupadas en promedio según los egresos de residentes RM (`dias_estada_acotado_anual` / días del año; total y solo SNSS) y según REM-20 (días cama ocupados de las áreas de psiquiatría de la oferta / días del año; total y sin las áreas forenses 423-426), con la razón Egresos SNSS / REM-20 sin forense. En 2020-2025 la razón va de 0,84 a 1,05 (0,95-1,05 desde 2022): dos fuentes independientes dan la misma escala, lo que respalda la base de la propuesta de camas por área. No deben coincidir exactamente (Egresos acota en el año sin conocer la fecha, incluye camas no psiquiátricas y ubica por residencia; REM-20 incluye las forenses y ubica por hospital) y la tabla publica las variantes que explican la brecha. El tablero lo muestra para la región, dentro del panel de hospitalizaciones.

La etapa `build_capa_oferta_urgencia_rm` (módulo `src/geo/`) depende de `clean_censo` y `build_dim_oferta_urgencia_rm`, tiene como consumidor directo `build_cobertura_urgencia_comuna` y publica `data/processed/geo/capa_oferta_urgencia_rm.parquet`: GeoParquet 1.1 de puntos (WKB) con grano 1 fila = 1 establecimiento de `dim_oferta_urgencia_rm`. No duplica los atributos de la dimensión (se unen por `establecimiento_codigo`); solo agrega `geometry`, `comuna_codigo_espacial` y `resultado_join_comuna`. El CRS publicado es el mismo PROJJSON de `Cartografia_censo2024_RM_Comunal.parquet`, SIRGAS 2000 (EPSG:4674), sin reproyección; las coordenadas del maestro DEIS no declaran datum y se interpretan en EPSG:4674 porque SIRGAS 2000 y WGS 84 difieren en menos de 1 m, por debajo de la precisión publicada (supuesto declarado en `src/geo/capas.py`). La capa comunal se carga con `src.geo.capas.cargar_comunas`, que exige EPSG:4674, 52 comunas con `comuna_codigo` 13xxx únicos y geometrías válidas no nulas (una geometría inválida hace fallar la carga; no se repara), y normaliza el `CUT` entero al `comuna_codigo` texto de los marts. El join punto-en-comuna usa `intersects` y nunca corrige la comuna declarada: `resultado_join_comuna` toma los valores `coincide`, `difiere`, `fuera_de_rm`, `limite_ambiguo` (punto sobre un límite compartido, sin elegir una comuna arbitrariamente) o `sin_coordenadas`. En el snapshot documentado al implementar esta capa, los 175 establecimientos tienen coordenadas y todos resultan `coincide`; por eso los establecimientos sin coordenadas del catálogo completo (NEXT-030; 87 de 1.187 en el snapshot vigente) no afectan a la oferta de urgencia. `src.geo.capas.unir_atributos_comunales` es el join territorial comunal reutilizable: conserva las 52 comunas, deja en nulo (no en cero) las que no tienen atributo y falla ante códigos duplicados, fuera de la RM o columnas repetidas. Antes de publicar valida grano, unicidad, dominio de `resultado_join_comuna` y su coherencia con los códigos; el orquestador valida esquema y CRS EPSG:4674 y realiza `SKIP` cuando el output es válido; `--force` lo regenera. Sus pruebas están en `tests/test_geo_capas.py`. No calcula distancias, áreas, cobertura ni isócronas.

La etapa `resolve_coordenadas_establecimientos` (`src/geo/resolver_coordenadas_establecimientos.py`) depende de `clean_establishments`, `clean_censo` y `build_dim_oferta_urgencia_rm`, no tiene downstream por ahora y publica `data/processed/geo/establecimientos_coordenadas_resolucion.csv` (tabla pequeña para inspección humana). Grano: 1 fila = 1 establecimiento del maestro RM cuya coordenada no es utilizable. Mide el problema con `src.geo.capas` sobre el maestro completo (`establecimientos_rm_clean.parquet`) y lo clasifica en `problema_coordenadas` = `sin_coordenadas`, `fuera_de_rm`, `difiere` (cae en otra comuna que la declarada; no se puede determinar si falla la coordenada o la comuna) o `limite_ambiguo`. La `resolucion` sigue una precedencia fija: `requiere_geocodificacion` si el establecimiento integra `dim_oferta_urgencia_rm` (su coordenada es insumo de accesibilidad); `excluir_no_vigente` si ya no opera; `excluir_fuera_de_oferta` si está vigente pero fuera de la oferta de urgencia. La etapa **no geocodifica, no imputa ni corrige**: las coordenadas se publican tal como vienen de DEIS, sin reemplazos por centroides, y cada fila lleva su `justificacion`. Geocodificar requiere una fuente externa verificable que este pipeline no incluye; solo es obligatorio si un establecimiento de la oferta llega a figurar como `requiere_geocodificacion` (la etapa lo informa como advertencia). Antes de publicar valida unicidad, dominios, justificación no vacía, que todo establecimiento sin coordenadas del maestro esté cubierto y que `requiere_geocodificacion` coincida exactamente con la pertenencia a la oferta. El orquestador valida esquema y realiza `SKIP` cuando el output es válido; `--force` lo regenera. Sus pruebas están en `tests/test_geo_resolver_coordenadas.py`.

En el snapshot documentado al implementar esta etapa (1.187 establecimientos), la lista tiene 95 filas: 87 `sin_coordenadas` (todos Cerrado, `excluir_no_vigente`) y 8 vigentes con coordenada anómala (1 `fuera_de_rm`: Clínica Los Maitenes, código 110270, en La Araucanía pese a declararse en Melipilla; 7 `difiere`), todos `excluir_fuera_de_oferta`. Ninguno pertenece a la oferta de urgencia: los 175 establecimientos de `dim_oferta_urgencia_rm` tienen coordenada y caen en su comuna declarada, de modo que no hay casos `requiere_geocodificacion` ni bloqueo para accesibilidad. **Discrepancia con la documentación histórica:** `reports/eda/eda_establecimientos_rm.md` y `reports/eda/registros_sin_coordenadas.csv` reportan 96 sin coordenadas, 9 de ellos vigentes (incluido el SUR Juan Pablo II, código 202306), y recomiendan geocodificarlo; el snapshot de esa implementación tiene 87, todos Cerrado, y el SUR 202306 ya publica coordenadas. Esos reportes corresponden a un snapshot anterior y no se regeneraron en esta etapa; la fuente de verdad es el output reproducible de esta etapa.

La etapa `build_cobertura_urgencia_comuna` (`src/geo/build_cobertura_urgencia_comuna.py`) depende de `clean_censo`, `clean_censo_poblacion`, `build_dim_oferta_urgencia_rm` y `build_capa_oferta_urgencia_rm`, no tiene downstream por ahora y publica `data/processed/geo/cobertura_urgencia_comuna.parquet` (52 filas, una por comuna RM) junto con el reporte `reports/geo/cobertura_urgencia_comuna.md` (método, resultados RM, tabla comunal y limitaciones), documentado en `reports/dictionary/diccionario_cobertura_urgencia_comuna.md`. Es el MVP de cobertura territorial simple (NEXT-032): mide **proximidad en línea recta, no accesibilidad**. La población se representa con las manzanas y entidades del Censo 2024 con `n_per > 0` (sin solape de `MANZENT`, lo que se valida), cada una como un punto interior (`point_on_surface`) ponderado por `n_per`; las geometrías inválidas de la fuente no se reparan y usan su centroide. Para cada punto se calcula la distancia haversine al establecimiento más cercano de `capa_oferta_urgencia_rm` (de cualquier comuna RM) y, como variante, al más cercano que reportó ID36 en 2021-2025 (`reporto_id36_periodo`). Por comuna publica distancia media, mediana y percentil 90 ponderados por población, proporción de población a ≤ 2, 5 y 10 km (umbrales descriptivos, no normativos), establecimientos en la comuna y habitantes por establecimiento (NULL si no hay oferta). No usa `pyproj` ni proyecciones: la haversine evita una dependencia nueva y su error es despreciable a esta escala. La población de las unidades censales no cuadra exactamente con la oficial (brecha documentada en `clean_censo`); no se imputa: se publica `proporcion_poblacion_representada` y las proporciones de cobertura usan la población de las unidades como denominador. Antes de publicar valida 52 comunas únicas, ninguna sin unidades pobladas, distancias no negativas, proporciones en [0, 1] y crecientes con el umbral, mediana ≤ p90, mediana ID36 ≥ mediana general y reconciliación del total de establecimientos con la oferta. Un establecimiento de la oferta sin coordenadas publicadas (típicamente uno recién incorporado al maestro DEIS) cuenta en su comuna pero no entra a las distancias, sin imputarse, y el reporte lo lista con nombre y código; la etapa falla si alguno reportó ID36, porque alteraría la métrica principal, o si son más de `MAX_OFERTA_SIN_COORDENADAS` (3). Así un rezago puntual de georreferenciación del DEIS no detiene el pipeline completo; la solución de fondo es geocodificarlo desde una fuente verificable. El orquestador valida el esquema del Parquet y el encabezado del reporte y realiza `SKIP` cuando ambos son válidos; `--force` los regenera. Sus pruebas están en `tests/test_geo_cobertura.py`. No calcula rutas, tiempos de viaje ni isócronas (NEXT-033/NEXT-034), ni capacidad de los establecimientos.

La etapa `build_mart_mvp_territorial_comuna` depende de `clean_censo_poblacion`, `clean_poblacion_proyecciones`, `clean_pobreza_comunal`, `clean_urgencias`, `build_urgencias_comuna_marts` y `build_dim_oferta_urgencia_rm`; no tiene downstream por ahora y publica `data/processed/marts/mart_mvp_territorial_comuna.parquet` (52 filas, una por comuna RM). El universo de comunas proviene de `dim_poblacion_comuna_censo2024` (dimensión ya validada contra el CUT oficial), no de Urgencias, por lo que una comuna sin ninguna atención reportada en 2025 (Vitacura, `13132`, según evidencia observada en `mart_urgencias_comuna_monthly`) permanece en el mart con `tiene_reporte_urgencias=False` y todas sus métricas de demanda en NULL, nunca en cero. La demanda 2025 se agrega sumando los 12 meses de `mart_urgencias_comuna_monthly` (nunca sumando ni promediando tasas ya calculadas) y las tasas por 10.000 habitantes se recalculan desde ese conteo anual y `poblacion_2025`; los establecimientos reportantes únicos anuales se derivan directamente de `urgencias_rm_2025.parquet` (un `nunique` mensual no puede sumarse entre meses sin duplicar establecimientos). El mart distingue explícitamente `poblacion_2025` (INE, proyección) de `poblacion_censada_2024` (Censo), y trata la vulnerabilidad (Casen 2022, `ano_vulnerabilidad=2022`) y la oferta (`dim_oferta_urgencia_rm`, `oferta_temporalidad="snapshot_actual"`) como información de período/temporalidad propia, no como 2025. No implementa accesibilidad, centroides, distancias, isócronas, cobertura poblacional ni scores compuestos. Antes de publicar valida grano (52 filas, 52 CUT únicos), positividad poblacional, cobertura completa de vulnerabilidad, reconciliación exacta de la oferta agregada contra los 174 establecimientos de `dim_oferta_urgencia_rm`, reconciliación de la demanda agregada contra `mart_urgencias_comuna_monthly`, recálculo correcto de tasas y el tratamiento NULL (no cero) de comunas sin reporte de Urgencias. El orquestador valida existencia/esquema del Parquet y realiza `SKIP` cuando es válido; `--force` lo regenera. Sus pruebas están en `tests/test_build_mart_mvp_territorial_comuna.py`.


La etapa `eda_series_demanda_sm` depende de `build_urgencias_comuna_marts`, no tiene downstream por ahora y publica `reports/eda/eda_series_demanda_sm.md` junto con `reports/eda/eda_series_demanda_sm_resumen.csv`. Es un script de **solo lectura** (`scripts/eda_series_demanda_sm.py`): no modifica marts ni genera datasets canónicos. Corresponde a la fase de *Data Understanding* (CRISP-DM) previa al modelo de demanda y cubre lo que los EDA descriptivos existentes no abordan: integridad del calendario semanal DEIS, estacionariedad (ADF y KPSS sobre nivel y primera diferencia), autocorrelación (ACF/PACF hasta el rezago estacional + 8), fuerza de tendencia y estacionalidad vía STL robusta, estabilidad de régimen contrastada contra la cobertura de reporte, heterogeneidad de las series comunales y el error de referencia del **baseline estacional ingenuo** (`y[t] = y[t-52]`) para los horizontes 4 a 8 semanas comprometidos en el alcance, tanto en la serie RM agregada como en cada comuna.

El contrato analítico que fija este EDA para la etapa de modelado es: grano **jerárquico** (RM agregada + comunas con reconciliación), target **conteo `atenciones_id36`** (las tasas se derivan dividiendo por población, no se modelan directamente), **ID37 incluido** (se usa el agregado ID36 oficial de DEIS, cuantificando qué fracción aporta ID37 para que cualquier comparación futura con el F00-F99 de Egresos pueda descontarla) y período **2021-2025** (2020 excluido por la discontinuidad documentada de captura de salud mental). Las semanas `semana = 53` del calendario DEIS son fragmentos de pocos días en el límite entre años, no semanas completas: el EDA las identifica, cuantifica su peso y las excluye de los análisis estacionales de forma explícita, sin imputarlas ni fusionarlas con semanas vecinas.

Todas las cifras del informe se calculan en tiempo de ejecución y la prosa se construye desde esos mismos valores, de modo que regenerar el report no puede producir una contradicción entre el texto y las tablas. Las interpretaciones se derivan condicionalmente de los resultados obtenidos (por ejemplo, la lectura conjunta de ADF/KPSS depende de qué hipótesis se rechacen efectivamente), no de afirmaciones fijas. El orquestador valida existencia/tamaño de ambos outputs y realiza `SKIP` cuando son válidos; `--force` los regenera. Sus pruebas están en `tests/test_eda_series_demanda_sm.py`. No ajusta modelos ni produce pronósticos: el backtesting formal y la comparación contra el baseline pertenecen a la etapa de modelado.


La etapa `benchmark_demanda_sm` depende de `build_urgencias_comuna_marts` y de `clean_establishments` (el maestro define la jerarquía por Servicio de Salud), tiene como consumidores directos `evaluate_holdout_demanda_sm` y `forecast_demanda_sm` y publica `reports/modeling/benchmark_demanda_sm.md`, `reports/modeling/benchmark_demanda_sm_resumen.csv` y `reports/modeling/benchmark_demanda_sm_seleccion.json`. Ejecuta `scripts/run_demand_benchmark.py`, que corresponde a las fases de *Modeling* y *Evaluation* (CRISP-DM) y se apoya en el paquete `src/models/`.

`src/models/` se organiza en nueve módulos con responsabilidades separadas: `features.py` construye el panel jerárquico (51 comunas + agregado RM como una serie más, mismo esquema para ambos niveles) y la matriz supervisada por horizonte; `metrics.py` provee métricas puntuales y de intervalo; `backtesting.py` implementa el motor de orígenes deslizantes y el protocolo `DemandModel` que todos los modelos cumplen; `baseline.py` implementa el baseline estacional ingenuo y su variante con deriva; `linear_glm.py` implementa el GLM de Poisson global; `gradient_boosting.py` implementa el modelo global multi-serie con LightGBM; `hierarchy.py` implementa la reconciliación `bottom_up` y `top_down` entre el total regional y las comunas; `hybrid.py` compone un modelo por nivel jerárquico y los reconcilia; y `conformal.py` envuelve cualquier modelo que exponga pronóstico puntual por lotes (`fit_point`) y reemplaza sus intervalos por intervalos conformes.

**El GLM de Poisson cumple un rol de ablación, no decorativo.** Se incorporó tras comprobar que la mayor parte de la mejora sobre el baseline proviene de la ingeniería de features y no del algoritmo: un modelo lineal sobre la misma matriz captura casi toda esa ganancia a nivel comunal y **supera** al boosting en la serie regional agregada. Mantenerlo en el benchmark obliga a que cualquier modelo más complejo justifique su costo frente a él, en vez de asumirse superior. Sus intervalos se derivan de la distribución del conteo (binomial negativa con dispersión de Pearson estimada fuera de muestra) en lugar de cuantiles empíricos de residuos. La dispersión se estima **por serie**: el agregado regional es la suma de 51 series y su dispersión observada es un orden de magnitud mayor que la de una comuna típica, de modo que un valor agrupado producía intervalos regionales demasiado estrechos.

**El modelo híbrido** (`hybrid.py`) responde a que ningún modelo domina en ambos niveles: toma el pronóstico regional del modelo que gana en región y el detalle comunal del que gana en comunas, y los reconcilia **top-down** —no bottom-up, que descartaría justamente el pronóstico regional que se quiere conservar—. La composición es genérica: recibe dos objetos que cumplan `DemandModel`, no dos clases concretas.

**Ausencia de fuga temporal por construcción.** La matriz supervisada usa estrategia **directa**: para pronosticar `y[t]` a horizonte `h`, cada rezago base se traduce al rezago efectivo `h + base`, y las medias móviles se calculan sobre la serie ya desplazada `h` períodos. Por lo tanto una fila sólo contiene valores observados hasta `t - h`. Esto permite precalcular las features una sola vez sobre el panel completo sin relajar ninguna garantía: lo que sí se reentrena en cada origen es el modelo, usando exclusivamente `t <= origen`. Las pruebas en `tests/test_models_demanda.py` verifican esta invariante alterando los valores posteriores a un corte y comprobando que las features previas no cambian.

**Intervalos de predicción.** Son empíricos, no gaussianos, porque el target es un conteo asimétrico y una banda normal produciría límites inferiores negativos. En el modelo global se calibran **fuera de muestra**: se reservan los últimos períodos del entrenamiento, se ajusta un modelo que no los ve y los cuantiles se estiman sobre esos residuos; usar residuos in-sample producía intervalos demasiado estrechos y cobertura observada muy por debajo del nivel nominal. La cobertura empírica alcanzada se reporta explícitamente en el informe frente al nivel nominal declarado, y no se afirma que el nominal esté garantizado.

**Reproducibilidad.** La semilla del paquete (`src/models/RANDOM_SEED`) se propaga a todo componente estocástico; el submuestreo de LightGBM la recibe explícitamente. Todas las cifras del informe se calculan en tiempo de ejecución y la prosa se construye desde esos mismos valores, incluidas las comparaciones entre niveles y el veredicto sobre si el modelo supera al baseline, que se derivan condicionalmente de los resultados obtenidos en vez de afirmarse de antemano. El orquestador valida existencia/tamaño de ambos outputs y realiza `SKIP` cuando son válidos; `--force` los regenera. Sus pruebas están en `tests/test_models_demanda.py`.

**Jerarquía de tres niveles por Servicio de Salud.** `features.load_servicio_map` asigna cada comuna al Servicio de Salud Metropolitano con más establecimientos del maestro ubicados en ella. El maestro no trae la pertenencia administrativa de la comuna, sólo la de cada establecimiento, de modo que la asignación es una aproximación reproducible y no un dato de la fuente. Sólo cuentan las glosas que son Servicios de Salud (se excluyen "SEREMI de Salud Metropolitana" y "Servicio de Salud No Aplica"), y se usa la glosa y no el código porque en el maestro el código `13` es compartido por la SEREMI y por el Servicio Metropolitano Sur. Un empate hace fallar la etapa en vez de resolverse en silencio. Con ese mapa, `build_panel(..., servicio_map=...)` agrega una serie por Servicio (suma de sus comunas) y la columna `servicio_id`; sin mapa, el panel de dos niveles no cambia. El motor de backtesting adjunta `nivel` y `servicio_id` a cada predicción, y la reconciliación (`hierarchy.py`) lee la estructura desde esas columnas: `bottom_up`, `top_down`, `middle_out` (conserva cada Servicio y lo reparte entre sus comunas) y `wls_structural` (mínimos cuadrados ponderados con pesos estructurales, la variante de MinT que no requiere estimar covarianzas). La reconciliación WLS rechaza explícitamente una jerarquía incompleta, porque un agregado sin comunas produciría NaN en silencio.

**Predicción conforme.** `ConformalWrapper` reserva el tramo final del entrenamiento como ventana de calibración, pronostica esa ventana con un modelo que no la vio, y construye el intervalo con los cuantiles de los residuos con signo, normalizados por `sqrt(y_pred)` y con la corrección de muestra finita `n + 1`. La calibración se hace por separado para cada nivel jerárquico (conforme Mondrian), porque la dispersión relativa del agregado regional es un orden de magnitud mayor que la de una comuna. No altera el pronóstico puntual del modelo base. La garantía exacta supone intercambiabilidad, que en una serie con tendencia sólo se cumple aproximadamente; por eso la cobertura se sigue midiendo en el backtesting en vez de darse por garantizada.

**Refactor verificado.** Para soportar la predicción conforme, el GLM y LightGBM separan el ajuste del pronóstico puntual (`fit_point`) y su calibración interna reutiliza ese mismo primitivo. Se verificó que el refactor no altera ningún resultado: las métricas de los modelos existentes coinciden exactamente (diferencia máxima 0,0 en las 1.820 filas del resumen).

**Regla de selección y significancia.** El informe no elige un ganador por MASE solamente. Un nivel se considera calibrado si su cobertura observada cae dentro de la tolerancia muestral alrededor del nominal (`metrics.coverage_tolerance`: 1,96 veces el error estándar binomial dado el número de evaluaciones; es una aproximación que supone independencia y por lo tanto es exigente con las comunas, que comparten orígenes). Entre los modelos que superan al baseline se recomienda el calibrado en región y comunas de menor MASE promedio; si existe un candidato más preciso pero no calibrado, se contrasta con una prueba de Wilcoxon pareada sobre los errores escalados de los mismos pronósticos (`metrics.paired_comparison`) y sólo una ventaja significativa se reporta como intercambio real. Los baselines se excluyen de los candidatos porque son la referencia y no una opción de producto. La comparación entre predicción conforme y jerarquía por Servicio se evalúa contra el objetivo de cada una: la primera por su efecto en cobertura y amplitud con el mismo pronóstico puntual, la segunda por pruebas pareadas contra el híbrido de dos niveles. Cuando varios modelos empatan exactamente en un nivel (variantes que comparten el pronóstico de su modelo base) el informe los nombra a todos en vez de elegir uno arbitrariamente.

El holdout se implementa en el stage siguiente. Permanecen pendientes: reconciliación MinT con covarianza completa (la matriz entre 58 series sería inestable con los orígenes disponibles; se usa la variante WLS estructural, que no la requiere), búsqueda de hiperparámetros y modelos SARIMAX/Prophet. El stage tarda del orden de nueve minutos porque ejecuta doce backtests completos; el `SKIP` evita repetirlo mientras sus outputs sean válidos. No persiste modelos entrenados: de la persistencia del pronóstico vigente se encarga `forecast_demanda_sm`.


La etapa `evaluate_holdout_demanda_sm` depende de `benchmark_demanda_sm`, `clean_urgencias` y `clean_poblacion_proyecciones`, no tiene downstream por ahora y publica `reports/modeling/holdout_demanda_sm.md` junto con `reports/modeling/holdout_demanda_sm_resumen.csv`. Evalúa el modelo que eligió el benchmark en los años que esa selección nunca vio. Los años de holdout **no están fijados en el código**: son los que tienen Urgencias procesadas posteriores al último año del período de entrenamiento (hoy, el año en curso).

**Selección congelada.** `benchmark_demanda_sm` publica además `reports/modeling/benchmark_demanda_sm_seleccion.json` con el modelo recomendado, el criterio y sus métricas de backtest. La evaluación lee ese archivo e instancia el modelo desde `src/models/registry.py`, la única fuente de verdad de las configuraciones evaluables, de modo que se evalúa exactamente lo que se eligió. Los resultados del holdout no vuelven a la selección; si lo hicieran, el holdout dejaría de serlo. El benchmark también instancia sus modelos desde ese registro; se verificó que el refactor no altera sus resultados.

**Snapshot identificado.** Como la fuente del año en curso es mutable, `src/models/holdout.snapshot_info` calcula el SHA256 del RAW y del Parquet procesado que efectivamente se evalúan y contrasta el RAW con `data/raw/provenance_manifest.json`. La etapa **no escribe** en el manifiesto: registrar procedencia corresponde a la ingesta. El informe declara si el snapshot está registrado, si difiere del registrado o si no tiene registro.

**Preparación sin imputar.** El semanal del holdout se construye con la misma carga y agregación que el mart de entrenamiento (`load_urgencias_source` y `load_rm_population` aceptan ahora un parámetro `years`, con los valores canónicos por defecto, de modo que los marts y la dimensión de población no cambian). Se excluyen, y se informan con su volumen, las semanas regulares con menos de 7 días (la última semana publicada suele estar truncada) y las comunas sin historia de entrenamiento, que no son pronosticables. El total regional se calcula sobre las mismas comunas del entrenamiento para que el target conserve su definición. Una comuna con historia ausente del holdout hace fallar la etapa en vez de rellenarse con ceros.

**Protocolo y lectura.** Orígenes deslizantes con paso 1 desde el último período de entrenamiento; en cada origen el modelo se reentrena con todo lo observado, como operaría en producción. MASE usa la misma escala que el benchmark y se verifica que el índice temporal del entrenamiento coincida con el suyo. Se evalúan el baseline de referencia y todos los modelos conformes del registro, no una selección a mano. El informe responde cuatro preguntas con pruebas explícitas: si el modelo supera al baseline fuera de muestra (Wilcoxon pareado por nivel), si sus intervalos siguen calibrados (tolerancia muestral), si se degradó respecto del backtest (habilidad sobre el baseline dentro de cada período, que controla por la dificultad del año) y si alguna alternativa habría sido significativamente mejor. El veredicto se deriva de esos cuatro criterios. El orquestador valida existencia y legibilidad de los outputs (incluido que los `.json` sean parseables) y realiza `SKIP` cuando son válidos; en una corrida general donde se ejecute `clean_urgencias`, la evaluación pierde su SKIP por dependencia ejecutada. El refresh acotado no evalúa este stage; no hay detección general de cambios de snapshot en corridas idempotentes. Sus pruebas están en `tests/test_models_holdout.py`.


La etapa `forecast_demanda_sm` depende de `benchmark_demanda_sm` y de `build_urgencias_comuna_marts`, no tiene downstream por ahora y publica `data/processed/modeling/pronostico_demanda_sm.parquet` junto con `data/processed/modeling/pronostico_demanda_sm_manifest.json`. Ambos archivos están versionados en Git (excepción explícita en `.gitignore`, ya que el resto de `data/processed/` es regenerable y no se versiona): un clon que reconstruya un mart semanal idéntico byte a byte reutiliza el pronóstico sin recalcularlo; si su mart difiere, el contrato de vigencia lo detecta y el orquestador lo regenera. Ajusta el modelo de la selección congelada sobre el panel vigente y guarda el pronóstico de los horizontes comprometidos: una fila por serie y horizonte, con el pronóstico puntual, su intervalo y la población proyectada del período objetivo. Ambos archivos se escriben con temporal y reemplazo atómico, y el manifiesto se escribe al final para que nunca describa un pronóstico inexistente.

La etapa `benchmark_establecimientos_sm` (`scripts/run_benchmark_establecimientos.py`, con el panel en `src/models/establecimientos.py`) depende de `build_urgencias_establecimiento_weekly_mart`, no tiene downstream por ahora y publica `reports/modeling/benchmark_establecimientos_sm.md`, `reports/modeling/benchmark_establecimientos_sm_resumen.csv`, `reports/modeling/benchmark_establecimientos_sm_universo.csv` y `reports/modeling/benchmark_establecimientos_sm_seleccion.json`. Evalúa dos objetivos con el mismo motor del modelo comunal (matriz supervisada sin fuga, modelos del registro único, backtesting con origen deslizante, reconciliación e intervalos): atenciones de salud mental (ID36) y hospitalizaciones derivadas desde urgencia (ID42, solo hospitales, con las atenciones de salud mental del establecimiento como covariable rezagada). La ventana parte en 2022, porque el Instituto Horwitz no reporta las primeras semanas de 2021 y la razón ID42/ID36 cambia de nivel entre 2021 y 2023. El universo exige todas las semanas de la ventana reportadas (una semana sin reporte no se imputa), un promedio semanal del objetivo de al menos 1 y de al menos 0,5 en cada año de la ventana (excluye series que empiezan a registrar a mitad de ventana, cuya escala MASE no es interpretable); el archivo de universo registra cada exclusión con su motivo. La serie total del panel es la suma de los establecimientos incluidos, no el total regional publicado. Aplica la regla de selección del benchmark comunal (supera al baseline y cobertura calibrada en el total y en los establecimientos), informa el contraste pareado contra el baseline y la habilidad del modelo por grupo de volumen semanal, y congela la selección por objetivo en el JSON. Para esto, `build_supervised_frame` omite `log_poblacion` si el panel no trae población y retira el valor contemporáneo de toda covariable fuera de `EXOGENOUS_COLUMNS` (solo entra rezagada); `prepare_supervised` acepta `exogenous`; y la reconciliación de `src/models/hierarchy.py` reconoce como hoja todo nivel que no sea región ni Servicio de Salud. Con el panel comunal, los tres cambios no alteran ningún resultado. El orquestador valida existencia de outputs y hace `SKIP` cuando son válidos; `--force` lo regenera. Pruebas: `tests/test_models_establecimientos.py`.

La etapa `evaluate_holdout_establecimientos_sm` (`scripts/evaluate_holdout_establecimientos.py`) depende de `benchmark_establecimientos_sm` y de `clean_urgencias`, no tiene downstream y publica `reports/modeling/holdout_establecimientos_sm.md` con `reports/modeling/holdout_establecimientos_sm_resumen.csv`. Evalúa, por objetivo, el modelo congelado en `benchmark_establecimientos_sm_seleccion.json` sobre los años posteriores al mart, detectados dinámicamente. Reutiliza el diseño de `evaluate_holdout_demanda_sm`: construye el semanal del año en curso con el mismo constructor del mart (`load_current_weekly`), excluye las semanas regulares incompletas, restringe el universo del benchmark a los establecimientos que reportan todas las semanas del holdout (`fixed_universe`; falla si lo excluido supera el 5% del volumen), verifica que el índice temporal coincida con el del benchmark, usa las escalas MASE de la historia previa a su primer origen y conserva solo los objetivos del año en curso. Compara contra el baseline y contra las alternativas conformes, mide la degradación respecto del backtest con habilidad relativa al baseline del mismo período e identifica el snapshot por SHA256 sin escribir en el manifiesto. El orquestador valida existencia de outputs y hace `SKIP` cuando son válidos; `--force` la regenera. Pruebas: `tests/test_models_establecimientos.py`.

La etapa `forecast_establecimientos_sm` (`scripts/run_forecast_establecimientos_sm.py`, con la lógica en `src/models/pronostico_establecimientos.py`) depende de `benchmark_establecimientos_sm` y de `clean_urgencias`, no tiene downstream por ahora y publica `data/processed/modeling/pronostico_establecimientos_sm.parquet` con `data/processed/modeling/pronostico_establecimientos_sm_manifest.json`. Para cada objetivo ajusta el modelo congelado sobre el mart más las semanas completas del año en curso, con el universo fijo del holdout, y guarda una fila por establecimiento y horizonte (columna `objetivo`). No publica la serie total del panel: cuando el modelo elegido no es jerárquico no reconcilia con los establecimientos, y la cifra regional la entrega el modelo comunal. Marca `fuera_de_rango` todo pronóstico que supere el doble del máximo observado por el establecimiento en las últimas 52 semanas, sin recortarlo, para que quien lo sirva no lo muestre. A diferencia de `forecast_demanda_sm`, su vigencia incluye la identidad del snapshot del año en curso (`raw_sha256` del footer de cada Parquet anual, que no depende del equipo que lo procesó) y detecta un año nuevo: una actualización de Urgencias lo deja desactualizado y el orquestador lo regenera. El contrato de output valida esquema y vigencia; con outputs vigentes hace `SKIP`. Pruebas: `tests/test_models_pronostico_establecimientos.py`.

La API lo sirve en `/api/v1/establecimientos` (listado con promedio reciente, pronóstico promedio y camas de psiquiatría por establecimiento), `/api/v1/establecimientos/{codigo}` (histórico semanal y pronóstico con intervalo por objetivo) y `/api/v1/establecimientos-meta` (modelo, horizontes, cobertura del holdout y advertencias de lectura), desde `src/api/establecimientos.py`. A diferencia del pronóstico comunal, la API nunca lo recalcula en memoria. Si falta responde 503 indicando que se ejecute `forecast_establecimientos_sm`. Si existe pero quedó desactualizado (por ejemplo, tras un snapshot nuevo de Urgencias) lo sigue sirviendo sin los horizontes que ya quedaron observados, y `/api/v1/establecimientos-meta` lo informa (`vigente: false` con el motivo y la etapa que lo actualiza); el tablero lo muestra con un aviso visible. Una actualización de datos no deja la vista vacía. Los horizontes marcados `fuera_de_rango` no se publican, y todo establecimiento sin pronóstico trae el motivo en lugar de un cero. Pruebas: `tests/test_api_establecimientos.py`.

**Rama de suicidios.** Toda la rama lee la base de defunciones ya consolidada; no se cruza con Urgencias ni con Egresos por persona (el territorio es la comuna de **residencia**) y Urgencias solo se lee para verificar el calendario.

- `build_mart_suicidios_comuna_weekly` (`src/data/build_mart_suicidios_comuna_weekly.py`). Inputs: `data/processed/defunciones/defunciones_nacional.parquet`, `data/processed/censo/dim_poblacion_comuna_censo2024.parquet` y la proyección INE (`load_rm_population`). Upstream: `clean_defunciones`, `clean_censo_poblacion`, `clean_poblacion_proyecciones`. Downstream: `eda_mart_suicidios_comuna_weekly`, `benchmark_suicidios` (y, por la selección, holdout y pronóstico). Output: `data/processed/marts/mart_suicidios_comuna_weekly.parquet` (diccionario en `reports/dictionary/diccionario_mart_suicidios_comuna_weekly.md`): una fila por comuna de residencia RM y semana DEIS, grilla completa con ceros registrados, `dias_semana` (las semanas de borde de año tienen 4 a 9 días) y `registro_completo` (False en semanas finales si el promedio diario semanal cae bajo 0,75 veces la mediana de las 8 semanas previas o si su último día cae bajo 0,5 veces la mediana de los 8 mismos días de semana anteriores; son alertas, no certifican completitud). Valida que la categoría X60-X84 coincida con el grupo publicado, que ningún residente RM tenga comuna fuera de las 52, la llave, la grilla y la conciliación exacta del total con la fuente; escribe de forma atómica con `zstd`. `SKIP` con esquema válido; `--force` lo regenera. Pruebas: `tests/test_build_mart_suicidios_comuna_weekly.py`.
- `eda_mart_suicidios_comuna_weekly` (`scripts/eda_mart_suicidios_comuna_weekly.py`). Upstream: el mart y `clean_urgencias` (calendario). Outputs: `reports/eda/eda_mart_suicidios_comuna_weekly.md` y `_resumen.json`. Recalcula la conciliación con la fuente, verifica `semana_deis` en todas las fechas de Urgencias, la regla de registro, el cambio de nivel 2020-2021 (prueba binomial exacta), la estacionalidad (LRT de armónicos en un GLM de Poisson con efecto de año), la dispersión, la autocorrelación de residuos, el exceso de ceros y la heterogeneidad comunal. `SKIP` exige título, claves del resumen, conciliación y cero discrepancias de calendario; `--force` lo regenera.
- `benchmark_suicidios` (`scripts/run_benchmark_suicidios.py`, lógica en `src/models/suicidios.py`). Upstream: el mart. Outputs: `reports/modeling/benchmark_suicidios.md`, `_resumen.csv` y `_seleccion.json`. Backtesting con el mismo motor del modelo de demanda (13 orígenes cada 4 semanas, horizontes 1-8, años cerrados desde 2022) del baseline estacional, los modelos del registro y `PoissonEstacionalJerarquico` (GLM de Poisson regional con un armónico, exposición en días y nivel ponderado por vida media 26/52/104 semanas, más un reparto top-down a comunas con tasas de Bayes empírico Gamma-Poisson; las comunas suman la región). Selecciona por **RMSSE** (con series casi siempre en cero, MAE/MASE premian pronosticar cero) entre los modelos que superan al baseline en ambos niveles y cuya cobertura es compatible con la declarada (en conteos, un intervalo de enteros no cubre exactamente 80%). `SKIP` con outputs válidos; `--force` lo regenera.
- `evaluate_holdout_suicidios` (`scripts/evaluate_holdout_suicidios.py`). Upstream: `benchmark_suicidios`. Outputs: `reports/modeling/holdout_suicidios.md` y `_resumen.csv`. Evalúa la selección congelada en las semanas completas del año en curso (un origen por semana), contra el baseline y las alternativas con Wilcoxon y ajuste de Holm. `SKIP`/`--force` como el benchmark.
- `forecast_suicidios` (`scripts/run_forecast_suicidios.py`). Upstream: `benchmark_suicidios`. Outputs: `data/processed/modeling/pronostico_suicidios.parquet` y `_manifest.json` (SHA256 del mart y de la selección). La vigencia es parte del contrato: si cambia el mart o la selección, deja de ser válido y el orquestador lo regenera. La API lo sirve en `/api/v1/suicidios/{series_id}` (`src/api/suicidios.py`) sin recalcularlo: si falta o vence responde 503 indicando el stage. Pruebas: `tests/test_models_suicidios.py` y `tests/test_api_suicidios.py`.

**Por qué se persiste el pronóstico y no un modelo entrenado.** La interfaz de los modelos es `fit_predict(supervised, origin, horizon)`: ajustar y predecir son un solo paso y cada horizonte ajusta el suyo, de modo que no existe un objeto entrenado con `predict` que pueda reutilizarse después. El artefacto reutilizable es el pronóstico junto con su procedencia. Persistir estimadores exigiría separar `fit` de `predict` en los modelos del registro y, aun así, habría que reajustar cuando cambia el panel.

**Manifiesto y vigencia.** El manifiesto registra cuándo se generó (UTC y hora de Chile), el modelo, el nivel de intervalo, los horizontes y la semilla de la selección, la última semana observada, el recuento de series por nivel, las versiones de las librerías que condicionan el resultado numérico, y el SHA256 de sus dos entradas: el mart semanal y la selección congelada. Esa huella define la vigencia: `src/models/persistence.motivo_desactualizacion` compara los hashes registrados contra los archivos que el propio manifiesto declara. La vigencia es parte del contrato de output, de modo que un pronóstico generado sobre un panel que ya cambió no se considera válido y el orquestador lo regenera en lugar de conservarlo; el `SKIP` solo ocurre mientras siga vigente.

**Horizontes.** El benchmark evalua y calibra los horizontes 1 a 8. Los comprometidos por el objetivo APT son 4 a 8; 1 a 3 se agregaron porque entre la ultima semana completa publicada y el primer horizonte comprometido quedaban tres semanas sin dato observado ni pronostico. Cada horizonte se ajusta y calibra por separado, de modo que el desempeno de los nuevos se mide en el benchmark y en el holdout, no se supone.

**Semana en curso.** La semana parcial mas reciente (publicada pero con menos de siete dias) se sigue excluyendo del modelo, y debe seguir excluida: compararla con semanas completas exagera una caida inexistente. La API la expone aparte en `/meta` (`semana_en_curso`, dato regional) para que el producto pueda mostrarla etiquetada como provisional sin mezclarla con la serie observada.

**Consumo desde la API.** `ServicioDemanda` reutiliza el pronóstico persistido cuando está vigente, lo que reduce ese paso del arranque de decenas de segundos a milisegundos. Si falta o quedó desactualizado, lo recalcula en memoria para seguir respondiendo, lo informa en `/meta` mediante `origen_pronostico` y agrega una advertencia que indica ejecutar este stage. El cálculo vive en `src/models/persistence.calcular_pronostico`, única implementación que usan tanto el stage como la API, para que ambos sirvan exactamente lo mismo. Sus pruebas están en `tests/test_models_persistencia.py`.

## 6. Idempotencia y Validación de Outputs

Los resultados numéricos de snapshots documentados no sustituyen la validación local. En particular, no se garantiza que toda oferta local tenga coordenadas: el consumidor de cobertura rechaza puntos faltantes antes de calcular distancias. La verificación dirigida del HEAD y sus bloqueos está en el apéndice C de [`reports/project/PROJECT_STATUS_AUDIT_2026-08-31.md`](reports/project/PROJECT_STATUS_AUDIT_2026-08-31.md#apéndice-c-verificación-dirigida-de-42-y-41-14-10-2026).

El orquestador evita recomputaciones innecesarias y no considera válido un output únicamente porque exista.

Antes de ejecutar una etapa, `scripts/run_pipeline.py` valida sus outputs esperados mediante controles apropiados al formato, que pueden incluir:

- existencia del archivo;
- tamaño válido;
- legibilidad mínima de CSV;
- legibilidad de Parquet/GeoParquet;
- metadata y esquema mínimo esperado cuando corresponda.

Si todos los outputs son válidos y ningún upstream de la etapa se ejecutó durante la invocación actual, la etapa realiza `SKIP`.

La propagación general registra ejecución, no diferencias de bytes: `run_stage` devuelve `True` tras ejecutar y validar el subprocess, aunque el productor conserve sus archivos. El downstream pierde su SKIP a nivel de orquestador, pero solo recibe `--force` si es target explícito (o se usa `--force` con `all`); sus módulos pueden tener SKIP interno. El refresh es una excepción: propaga publicación o desalineación del hash RAW/processed. No existe invalidación general por cambios históricos de inputs/código ni comparación de hashes para todos los stages.

Estos controles mínimos no equivalen a validar todas las filas, integridad de todos los row groups, grano o invariantes de negocio. Para Parquet se lee el esquema del footer, sin exigir filas positivas; para CSV el control genérico lee la cabecera y los contratos conocidos comprueban muestras (o todas las filas en casos específicos). Los formatos no tratados solo tienen control de existencia/tamaño más un contrato si está registrado. Las validaciones profundas corresponden a productores y tests. Una corrida idempotente con SKIP no demuestra que el bootstrap ni todos los productores se hayan ejecutado.

El uso de `--force` obliga a ejecutar la etapa seleccionada y propaga la regeneración por su rama downstream, sin ejecutar ramas independientes.

Los módulos de `src/data/` encapsulan la lógica de procesamiento, pero `scripts/run_pipeline.py` es el punto de entrada oficial para generar outputs canónicos del proyecto.

La rama `download_contexto_genero` → `normalize_contexto_genero` conserva cuatro Parquet processed independientes. `build_mart_contexto_genero_indicador_sexo` depende de esa normalización y publica `data/processed/marts/mart_contexto_genero_indicador_sexo.parquet` como capa de serving del MVP. Su grano es una observación publicada de un indicador de contexto de salud mental por sexo, fuente, ámbito geográfico y período; concatena los cuatro contratos sin joins, agregaciones ni enriquecimiento. Valida schema, los cuatro `source_id`, reconciliación exacta de filas por fuente, unicidad lógica de `source_id`+`source_sheet`+`geography_level`+`geography`+`region_code`+`period`+`sex`+`indicator`+`unit`, preservación de `period`, `year`, `value_text` y del símbolo `-`. El output válido hace `SKIP`; `--force` lo regenera con escritura atómica. `eda_contexto_genero` perfila las fuentes y `eda_mart_contexto_genero_indicador_sexo` perfila el mart. Toda la rama es contexto interpretativo: no tiene FK, joins automáticos ni features hacia Urgencias/Egresos, aunque coincidan sexo, año, período o territorio. La descarga conserva cada XLSX original en `data/raw/contexto_genero/`, valida el workbook antes de publicarlo y agrega URL, fecha/hora UTC, tamaño y SHA256 al historial de `data/raw/provenance_manifest.json`. En operación normal los RAW válidos hacen `SKIP`; `--force` solicita explícitamente un snapshot nuevo.

La etapa `profile_urgencias_sm_coverage` depende de `clean_urgencias`, no tiene downstream por ahora y publica `data/processed/urgencias/perfil_cobertura_sm_comuna_semanal_2021_2025.parquet`. Lee únicamente los Parquet 2021–2025 y las columnas necesarias: usa `id_causa=1` para conservar el calendario semanal DEIS y el universo de comunas con reporte general, e `id_causa=36` como único insumo de atenciones de salud mental. Una semana con fila ID 36 y total agregado cero es observada; una semana sin fila ID 36 se reporta como ausencia, sin imputarla. El perfil no incluye 2026 ni crea `mart_urgencias_comuna_weekly`. El orquestador valida que el Parquet exista, tenga tamaño de archivo positivo y esquema legible (no exige filas positivas); en operación normal realiza `SKIP` cuando pasa ese control y `--force` lo regenera. Su contrato se prueba en `tests/test_profile_urgencias_sm_coverage.py` y el registro del stage en `tests/test_pipeline_orchestration.py`.

La etapa `build_urgencias_comuna_marts` depende de `clean_urgencias` y de `clean_poblacion_proyecciones`; sus consumidores directos son `build_urgencias_establecimiento_mart`, `build_urgencias_establecimiento_weekly_mart`, `build_urgencias_comuna_etario_mart`, `build_mart_mvp_territorial_comuna`, `eda_series_demanda_sm`, `benchmark_demanda_sm` y `forecast_demanda_sm` y publica `data/processed/marts/mart_urgencias_comuna_weekly.parquet` y `data/processed/marts/mart_urgencias_comuna_monthly.parquet`. Sus inputs son los Parquet de Urgencias RM 2021–2025, con filtros de columnas e IDs 1, 35, 36 y 37–41. Cada métrica es un conteo agregado de atenciones; el mensual se agrega desde `fecha` diaria y el semanal conserva `ano`, `semana` y el mínimo `fecha` publicado como `fecha_inicio_semana`, sin convertir al calendario ISO. No imputa semanas, meses ni causas ausentes. Incluye los conteos reportantes ID1 e ID36; no incorpora el catálogo de establecimientos actual porque es un snapshot no histórico. Antes de publicar, valida grano, no negatividad, jerarquía ID36, ratios, reportantes y reconciliación anual semanal→mensual; ambos Parquet se escriben con temporal y reemplazo atómico. El orquestador valida existencia, tamaño y esquema, realiza `SKIP` cuando ambos outputs son válidos y los regenera con `--force`. Las pruebas están en `tests/test_build_urgencias_comuna_marts.py`.

Ambos marts unen `data/processed/censo/dim_poblacion_comuna_anual.parquet` por `comuna_codigo`+`ano` (join `many_to_one`, 100% de cobertura exigida: cualquier comuna×año sin denominador hace fallar la etapa) y publican `poblacion_anual` junto con `tasa_atenciones_id1_por_10000`, `tasa_atenciones_id35_por_10000` y `tasa_atenciones_id36_por_10000`. Como la fuente poblacional es anual, el mart mensual reutiliza la misma `poblacion_anual` para los 12 meses del año y el semanal la reutiliza para todas las semanas del año, sin interpolar. Estas tasas cuantifican atenciones (evento) por 10.000 habitantes; no son porcentaje de población atendida ni deben interpretarse como prevalencia o incidencia de personas.

`src/data/build_urgencias_comuna_marts.py` expone además las funciones reutilizables de carga (`load_urgencias_source`, con `extra_columns` para pedir columnas adicionales), agregación (`aggregate_grain`, generalizada con `attribute_columns` e `include_reporters`), ratios (`add_ratios`), escritura atómica (`atomic_write`) y validación de jerarquía causal (`validate_non_negative`, `validate_causal_hierarchy`, `validate_ratios`), que consumen los dos stages siguientes para no duplicar esa lógica entre marts de Urgencias.

La etapa `build_urgencias_establecimiento_mart` depende de `clean_urgencias` y de `build_urgencias_comuna_marts` (esta última solo como referencia de validación, no como insumo de datos), no tiene downstream por ahora y publica `data/processed/marts/mart_urgencias_establecimiento_monthly.parquet` (152 establecimientos con reporte de Urgencias en 2021-2025, 8.857 filas, 2021-2025). Su grano es `establecimiento_codigo`×`ano`×`mes`; incorpora `comuna_codigo`, `comuna_glosa`, `establecimiento_glosa` y `tipo_establecimiento_urgencia` como atributos del grano porque se verificó que cada establecimiento reporta un único valor de cada uno en todas las causas del contrato 2021-2025 (regla determinista, sin fragmentar el grano). No incorpora población ni tasas por establecimiento: la población comunal no representa la población atendida de un establecimiento individual. Antes de publicar valida grano único, no negatividad, jerarquía causal (ID36=ID37+...+ID41, ID36≤ID1), ratios en [0,1], período estrictamente 2021-2025, y reconciliación exacta al sumar por `comuna_codigo`×`fecha_mes` contra `mart_urgencias_comuna_monthly` (para eso lee ese Parquet ya publicado). El orquestador valida existencia/esquema y realiza `SKIP` cuando es válido; `--force` lo regenera. Sus pruebas están en `tests/test_build_urgencias_establecimiento_mart.py`.

La etapa `build_urgencias_establecimiento_weekly_mart` (`src/data/build_urgencias_establecimiento_weekly_mart.py`) depende de `clean_urgencias` y de `build_urgencias_comuna_marts` (este último solo como referencia de validación), su consumidor directo es `eda_mart_urgencias_establecimiento_weekly` y publica `data/processed/marts/mart_urgencias_establecimiento_weekly.parquet`. Su grano es `establecimiento_codigo`×`ano`×`semana` con la semana publicada por DEIS, 2021–2025, y es el insumo del pronóstico por establecimiento. Lee las causas del contrato comunal (ID1 y ID35–ID41) más **ID42**, hospitalizaciones derivadas desde la urgencia por F00-F99, que no es componente de ID36; para eso `load_urgencias_source` acepta ahora un parámetro `causes`, con el contrato comunal por defecto, de modo que los demás marts no cambian. Cuando un establecimiento reporta una semana publica todas esas causas, con cero si corresponde; una semana sin filas es ausencia de reporte y no se imputa. Antes de publicar valida grano único, llaves sin nulos, no negatividad, jerarquía causal de ID36, razones en [0, 1], período 2021–2025 y reconciliación exacta con `mart_urgencias_comuna_weekly` al sumar por `comuna_codigo`×`ano`×`semana` (mismo universo y mismos valores de ID1 y ID35–ID41). El orquestador valida existencia y esquema, incluido `atenciones_id42`, y hace `SKIP` cuando es válido; `--force` lo regenera. Diccionario: `reports/dictionary/diccionario_mart_urgencias_establecimiento_weekly.md`. Pruebas: `tests/test_build_urgencias_establecimiento_weekly_mart.py`.

La etapa `eda_mart_urgencias_establecimiento_weekly` (`scripts/eda_mart_urgencias_establecimiento_weekly.py`) depende de `build_urgencias_establecimiento_weekly_mart`, no tiene downstream y publica `reports/eda/eda_mart_urgencias_establecimiento_weekly.md` con su tabla `reports/eda/eda_mart_urgencias_establecimiento_weekly_resumen.csv`. Solo lee el mart y responde lo que el pronóstico por establecimiento necesita antes de modelar: cobertura semanal por establecimiento, cuántos superan cada umbral de volumen y la evolución de ID42 frente a ID36. Toda cifra del informe se calcula al ejecutarlo; `--force` lo regenera.

La etapa `build_urgencias_comuna_etario_mart` depende de `clean_urgencias` y de `build_urgencias_comuna_marts` (misma razón: solo referencia de validación), no tiene downstream por ahora y publica `data/processed/marts/mart_urgencias_comuna_etario_monthly.parquet` (51 comunas RM, 15.300 filas, 2021-2025) en formato largo, grano `comuna_codigo`×`ano`×`mes`×`grupo_etario_urgencia`, usando exclusivamente los cinco grupos etarios publicados por DEIS en Urgencias (`menores_1`, `de_1_a_4`, `de_5_a_14`, `de_15_a_64`, `de_65_y_mas`). No incluye `total` junto a los grupos etarios (se verificó que `total` equivale exactamente a su suma en el origen) ni sexo/género (Urgencias no lo publica). Antes de publicar valida grano único, no negatividad, dominio de `grupo_etario_urgencia`, jerarquía causal por fila (ID36=ID37+...+ID41, verificado también a nivel de grupo etario), período estrictamente 2021-2025, y reconciliación exacta al sumar los 5 grupos etarios por `comuna_codigo`×`fecha_mes` contra `mart_urgencias_comuna_monthly`. El orquestador valida existencia/esquema y realiza `SKIP` cuando es válido; `--force` lo regenera. Sus pruebas están en `tests/test_build_urgencias_comuna_etario_mart.py`.

Ambos marts nuevos son estrictamente Urgencias: no cruzan con Egresos ni afectan la restricción invariante de mantener ambas fuentes a nivel ecológico/territorial, no de paciente. Urgencias sí se relaciona con establecimientos individuales por `establecimiento_codigo` (es su llave natural); es Egresos el que no tiene identificador de establecimiento, por lo que cualquier relación entre ambas fuentes sigue siendo ecológica/territorial, nunca a nivel de registro.

## 7. Informes Históricos y Protegidos

Los reportes curados no declarados como outputs de un productor se conservan; por ejemplo, `eda_urgencias` genera las tablas CSV de su EDA. Hay reportes Markdown reproducibles que sí se sobrescriben al ejecutar su productor: los EDA de contexto y del mart contextual, `eda_series_demanda_sm`, benchmark, holdout y el reporte de cobertura geográfica declarado en el DAG. Además, `clean_urgencias` sin `--year` reescribe `reports/eda/eda_urgencias_normalizacion.md` (efecto adicional del módulo, no declarado en `STAGES`); con `--year` no lo reescribe. No existe una protección general de todos los Markdown de `reports/eda/` en el orquestador.

## 8. Ejecutar Pruebas (Tests)

Para ejecutar las pruebas unitarias y de validación de arquitectura:

```bash
python -m pytest tests/
```

`pytest.ini` excluye por defecto las pruebas marcadas `data_integration`, que
comprueban snapshots oficiales RAW o procesados disponibles localmente. La suite
habitual usa fixtures sintéticos mínimos versionados y puede ejecutarse sin
datasets masivos ni descargas. Los archivos de prueba se generan en temporales.

Para ejecutar solo las integraciones, con los snapshots requeridos disponibles:

```bash
python -m pytest tests/ -m data_integration
```

Para ejecutar toda la suite, incluidas las integraciones:

```bash
python -m pytest tests/ -o addopts=
```

Si el entorno restringe el temporal del sistema, se puede agregar
`--basetemp=.cache/pytest-tests` usando una carpeta dedicada: pytest puede
reemplazar su contenido. El método de aislamiento sin datasets y la evidencia
de cierre de #40 están en
[`reports/validation/issue40_fixtures.md`](reports/validation/issue40_fixtures.md).

### Escenario anual de capacidad por área de psiquiatría

Reutiliza el mart de ocupación y la dotación SNSS sin cambiar sus esquemas.
`propuesta_camas` calcula `techo(max(O_m / D_m) / 0,85)` sobre los últimos
12 meses consecutivos publicados. Es continuidad de carga, sin crecimiento
supuesto, para el año siguiente a la fecha de corte explícita (fecha de consulta
en la API). Calcula cada área de psiquiatría por separado. Fuera de corta estadía
418/421, el 85% es un supuesto explícito de escenario y no un estándar específico
validado para forense, intensivos o mediana/larga estadía. La aritmética racional
evita camas extra por redondeo.
Incluye sensibilidad al 90%, brecha frente a disponibles del último mes,
habilitación potencial de dotación existente y ampliación entera positiva
respecto de la declarada. Datos faltantes, cierres, duplicados o antigüedad
mayor a 12 meses producen abstención. Sin dotación declarada usa las camas
disponibles por día calculadas del último REM-20 como base explícita: el aumento
es capacidad adicional estimada, sin distinguir camas nuevas de rehabilitación.
La ventana gráfica no altera la historia usada para dimensionar.

El QA forma parte de `eda_mart_ocupacion_psiquiatria_hospital_rm`, con los
mismos upstream/downstream y outputs: tabla de propuestas, identidades de
capacidad mínima, diagnóstico retrospectivo con cortes anuales no solapados
y SHA256 de dotación. `SKIP` exige además fecha de corte y hash de dotación
vigentes; `--force` regenera ambos informes. No requiere stages ni dependencias
nuevos. Reproducción:
`python scripts/run_pipeline.py --stage eda_mart_ocupacion_psiquiatria_hospital_rm --force`.
Tests: `tests/test_propuesta_camas.py`, API, mart y orquestador.
La API expone `areas_psiquiatria[].propuesta_camas`. El frontend muestra dotación
y aumento junto a las métricas y referencia verde a **base + aumento**,
solo con aumento positivo. No compensa camas entre áreas.
Sin selección de área muestra desde el inicio el total hospitalario como suma
de los aumentos por área; si falta soporte en alguna, identifica el subtotal
como parcial y detalla las exclusiones. La holgura de un área nunca resta
la ampliación necesaria en otra. Regresiones de esta presentación:
`node --experimental-strip-types --test frontend/tests/propuestaCamas.test.mjs` (Node 22.6+).

El [85% del Royal College of Psychiatrists](https://mentalhealthwatch.rcpsych.ac.uk/indicators/bed-occupancy-across-mental-health-trust)
no es una norma chilena ni garantía de disponibilidad diaria.
[Pratt y Wood (2021)](https://pubmed.ncbi.nlm.nih.gov/34219171/) advierten que
el objetivo depende del tamaño, especialidad y tolerancia al desborde.
No es un pronóstico anual validado ni acredita presupuesto, personal, espacio
o plazos. No observa espera, demanda rechazada ni picos diarios. La evaluación
retrospectiva mide cumplimiento del promedio mensual, no disponibilidad diaria.
