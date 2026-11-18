# Registro de defectos — SAAD CP-SAAD-2026 (C-06)

Registra los defectos reales encontrados durante los ciclos de prueba del catálogo CP-SAAD-2026.
Solo se registran defectos reales: hallazgos observables en la plataforma, no suposiciones.
Desde el 2026-11-14 también registra los defectos del catálogo SAAD-CP v2.1 de 200 casos
(sección «Defectos de interfaz»), cuyos IDs son `SAAD-CP-NNN`, distintos de los `CP-SAAD-NNN` del
catálogo de 70 casos.

Columnas: **ID** · **Título** · **Criticidad** · **Entorno** · **Detectado en** · **Responsable** · **Corrección** · **Retest** · **Estado**

---

## Defectos de datos y outputs del pipeline (cerrados en el ciclo 4)

Estos defectos bloqueaban múltiples casos del catálogo porque la API respondía 404 o 503 cuando
faltaba el archivo de entrada. Se cerraron ejecutando el pipeline con los stages correspondientes
y publicando los outputs con `subir_datos.sh`.

| ID | Título | Criticidad | Entorno | Detectado en | Responsable | Corrección | Retest | Estado |
|---|---|---|---|---|---|---|---|---|
| DEF-01 | `camas-psiquiatria` responde 404: falta `dim_camas_psiquiatria_hospital_rm` | Alta | LOCAL · AWS | Ciclo 1 (CP-025) | Felipe (pipeline) | Pipeline ejecutado con `--sin-evaluacion` (stage `build_dim_camas_psiquiatria_hospital_rm`); publicado con `subir_datos.sh`; API local y ECS reiniciados para tomar los datos | Ciclo 4: CP-025 APROBADO en LOCAL y AWS | **Cerrado** |
| DEF-02 | Establecimientos responde 503: falta `mart_urgencias_establecimiento_weekly` y su pronóstico | Alta | LOCAL · AWS | Ciclo 1 (CP-037) | Felipe (pipeline) / Cristopher (API) | Pipeline ejecutado con `--sin-evaluacion` (stage `build_urgencias_establecimiento_weekly_mart` y `forecast_establecimientos_sm`); publicado con `subir_datos.sh`; API redesplegada | Ciclo 4: CP-037 APROBADO en LOCAL y AWS | **Cerrado** |
| DEF-03 | Suicidios responde 503: falta `mart_suicidios_comuna_weekly` en el pronóstico persistido | Alta | LOCAL · AWS | Ciclo 1 (CP-047) | Felipe (pipeline) | Pipeline ejecutado con `--sin-evaluacion` (stage `build_mart_suicidios_comuna_weekly` y `forecast_suicidios`); publicado con `subir_datos.sh`; API local y ECS reiniciados | Ciclo 4: CP-047 APROBADO en LOCAL y AWS | **Cerrado** |
| DEF-04 | Pronóstico de urgencias desactualizado: la selección de benchmark cambió sin regenerar el pronóstico | Alta | LOCAL · AWS | Ciclo 1 (meta `motivo_desactualizacion`) | Felipe (pipeline) / Cristopher (API) | El JSON de selección (`reports/modeling/benchmark_demanda_sm_seleccion.json`) ya se sube a S3 dentro de `reports/` con `subir_datos.sh`; la causa real era que alguien había actualizado la selección sin volver a ejecutar `forecast_demanda_sm`. Al correr el pipeline completo (`--sin-evaluacion`) el 2026-11-12, selección y pronóstico quedaron generados en la misma corrida y el SHA-256 vuelve a coincidir. Flag `SAAD_USAR_PRONOSTICO_DESACTUALIZADO` desactivado en el redespliegue (`95d00f8`) | Ciclo 4: pronóstico vigente, sin advertencia de desactualización | **Cerrado** |

**Nota operativa (no es un defecto de código):** el pronóstico y la selección de benchmark pueden
volver a desincronizarse si se modifica uno sin regenerar el otro. El pipeline detecta esto solo
(comparando el SHA-256 de la selección contra el manifiesto) y recalcula automáticamente al
correr sin `--sin-evaluacion` sobre la etapa de forecast, o con `--sin-evaluacion` si la selección
no cambió. Mientras el equipo mantenga esa disciplina, el pronóstico se mantiene vigente.

### Hallazgo del retest: reinicio manual requerido tras publicar datos nuevos

Al reintentar el ciclo 3 inmediatamente después de `subir_datos.sh`, los tres casos seguían
fallando pese a que los archivos ya estaban en S3 y en el disco local. Causa: tanto el contenedor
`api` local (Docker Compose) como la tarea ECS mantienen en memoria el estado leído al arrancar;
un archivo nuevo en disco o en S3 no se recarga solo. Fue necesario:
- Local: `docker compose restart api`.
- AWS: `aws ecs update-service --force-new-deployment` (ya lo hace `subir_datos.sh`, pero esa
  primera vez el task aún no había terminado de estabilizarse cuando se corrió el ciclo 3).

Con eso, el ciclo 4 confirmó los tres defectos cerrados. Se registra como nota operativa, no como
defecto nuevo: `subir_datos.sh` ya fuerza el redespliegue; falta solo esperar a que termine antes
de volver a probar.

### Casos antes bloqueados por DEF-01 a DEF-03 (desbloqueados desde el ciclo 4)

Con los datos publicados, estos casos dejaron de estar bloqueados, pero son pruebas manuales de
interfaz que el ciclo automatizado no ejecuta: desde el ciclo 16 figuran como NO EJECUTADO, no como
aprobados. Hasta el ciclo 15 el script los seguía marcando BLOCKED por una tabla sin actualizar. Los
de suicidios (048, 050 y 052) vuelven a estar BLOCKED, ahora por DEF-15.

| Defecto | Casos que estaban BLOCKED |
|---|---|
| DEF-01 (camas) | CP-SAAD-042, CP-SAAD-043, CP-SAAD-044, CP-SAAD-045, CP-SAAD-059 |
| DEF-02 (establecimientos) | CP-SAAD-038, CP-SAAD-039, CP-SAAD-040, CP-SAAD-041 |
| DEF-03 (suicidios) | CP-SAAD-048, CP-SAAD-050, CP-SAAD-052 |

**Contingencia (histórica, ciclos 1-3):** los casos BLOCKED se marcaban como tal en la matriz; no
se contabilizaban como aprobados ni fallidos.

---

## Defectos de código y configuración (cerrados)

| ID | Título | Criticidad | Entorno | Detectado en | Responsable | Corrección | Retest | Estado |
|---|---|---|---|---|---|---|---|---|
| DEF-05 | `test_clean_urgencias` fallaba por conteos dependientes de snapshot | Baja | Equipo | Ciclo 1 (`pytest`) | Catalina | Snapshot regenerado (`cff157e`) | Ciclo 2: 858 tests pasan | **Cerrado** |
| DEF-06 | `test_pipeline_task` dependía del espacio real del disco | Baja | Equipo | Ciclo 1 (`pytest`) | Catalina | Fixture `autouse` `_disco_suficiente` que monkeypatcha `shutil.disk_usage` (en esta entrega) | Ciclo 2: 858 tests pasan | **Cerrado** |
| DEF-07 | `publicar_imagen.sh` fallaba con `NoRegion` | Media | Equipo | Despliegue inicial | Catalina | Script `_entorno.sh` exporta `AWS_REGION` (`5417177`); imagen `90965fc` publicada con éxito | Verificado en despliegue | **Cerrado** |
| DEF-08 | ID de cuenta de AWS expuesto en `cdk.context.json` en el repositorio público | Media (seguridad) | Repositorio | Revisión de código | Catalina | Commit enmendado (`5417177`), datos movidos a `infra/aws/.env`, force-push; `cdk.context.json` en `.gitignore` (`b73228e`) | Repositorio verificado | **Cerrado** |
| DEF-09 | Pipeline `saad-pr` podía ser disparado por PR de forks externos | Alta (seguridad) | AWS | Revisión de configuración de CodePipeline | Catalina | Cambiado a push en ramas distintas de `main` (`0d39a7b`); verificado en AWS | Pipeline verificado | **Cerrado** |
| DEF-10 | El contrato OpenAPI no declara errores 404, 409 ni 503 | Baja | Código | Ciclo 1 (comparador de contrato) | — | Decisión de equipo documentada en `docs/06-requisitos/contrato_api/README.md` (`3f1fd84`); no se modifica el contrato | Ciclo 2: comparador da 0 errores | **Cerrado** |
| DEF-11 | `subir_datos.sh` no valida que los outputs del pipeline estén completos antes de publicar | Media | Equipo / AWS | Revisión de script | Catalina | `scripts/verificar_outputs_api.py` revisa, antes del `aws s3 sync`, que existan todos los archivos de las rutas que declara la API (`src/api/`) y que el SHA-256 de cada entrada de los tres manifiestos de pronóstico coincida con el archivo presente; si no, `subir_datos.sh` se detiene sin publicar. El script además espera a que ECS se estabilice tras el redespliegue (hallazgo del retest del ciclo 3) | 2026-11-15: 5 pruebas en `tests/test_verificar_outputs_api.py`; sobre los datos del repositorio el verificador bloqueó la publicación por un desfase real (DEF-15) | **Cerrado** |

---

## Defectos de datos (cerrados en el ciclo 17)

| ID | Título | Criticidad | Entorno | Detectado en | Responsable | Corrección | Retest | Estado |
|---|---|---|---|---|---|---|---|---|
| DEF-15 | Los pronósticos commiteados en `7e48f9a` no coinciden con las entradas del repositorio: los manifiestos registran el SHA-256 de los JSON de selección con finales de línea CRLF (corrida en Windows) y, en demanda, de una selección que no está en el historial; también cambió `urgencias_rm_2026.parquet` | Alta | LOCAL (Linux) · AWS | 2026-11-15, verificador de DEF-11; confirmado en el ciclo 16 | Felipe (pipeline) | Pipeline regenerado con `--sin-evaluacion` el 2026-11-16 (`2dc0150`); outputs publicados con `subir_datos.sh`; `.gitattributes` agrega `reports/modeling/*.json text eol=lf` para que el hash no dependa del sistema operativo | Ciclo 17: CP-SAAD-047 APROBADO en LOCAL y AWS; `scripts/verificar_outputs_api.py` sin problemas | **Cerrado** |
| DEF-16 | Pronóstico de demanda comunal desactualizado tras corrida interrumpida: `2dc0150` regeneró urgencias y establecimientos pero dejó el mart comunal en S39 (última semana observada) mientras establecimientos llegó a S45 | Alta | LOCAL · AWS | 2026-11-17, `scripts/verificar_outputs_api.py` (guard `cortes_desalineados`), ciclo 17 | Catalina (pipeline) | Reconstrucción forzada de `build_urgencias_comuna_marts` y `forecast_demanda_sm` el 2026-11-17; guard `cortes_desalineados()` añadido al verificador para prevenir la publicación cuando demanda y establecimientos difieren; outputs republicados con `subir_datos.sh` | Ciclo 17: `verificar_outputs_api.py` pasa sin errores; demanda y establecimientos cierran en la misma semana observada. Reprueba en AWS tras publicar: `/series/RM` empieza en 2026-S46 en LOCAL y AWS y `qa_e2e_local_vs_aws.py` da 24 aprobados, 0 fallidos (CP-068, [`catalogo_200_aws_reintento`](ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/resultados.md)) | **Cerrado** |

Detalle DEF-15: con LF, las selecciones de establecimientos y suicidios del repositorio dan
`f5fe27ab…` y `8195b1ff…`; con CRLF dan exactamente lo que registran los manifiestos (`e64950ef…` y
`05fd7c29…`). La de demanda no coincide con ninguna versión del historial, ni con LF ni con CRLF.
La regeneración completa del 2026-11-16 produjo manifiestos con LF, que el verificador ya acepta.

**Impacto confirmado en el ciclo 16 (2026-11-16):**
- CP-SAAD-047 FALLIDO en LOCAL y **en AWS**: `/api/v1/suicidios` responde 503 («El pronóstico de
  suicidios está desactualizado (cambió 'seleccion_benchmark')»). Lo que había en S3 tenía el mismo
  desfase.
- CP-SAAD-020 FALLIDO en AWS: el primer pronóstico de la serie RM difería entre LOCAL (semana 46) y
  AWS. Arrastraba a CP-SAAD-006 y CP-SAAD-070.
- CP-SAAD-048, 050 y 052 quedaban BLOCKED.
Todos cerrados en el ciclo 17 tras la republicación.

---

## Defectos de interfaz — campaña SAAD-CP v2.1

Hallados con el catálogo de 200 casos y registrados con su evidencia (cada archivo anexo lleva su
SHA256 en el `resultados.json` de su ciclo). La versión desplegada en AWS **no está confirmada**
(`/meta` no expone el SHA ni el digest de la imagen). La criticidad y el responsable son
propuestas hasta el triage; el responsable es un rol, no una asignación.

| ID | Título | Criticidad | Entorno | Detectado en | Responsable | Corrección propuesta | Retest | Estado |
|---|---|---|---|---|---|---|---|---|
| DEF-12 | El aviso «Pronóstico no disponible: el establecimiento no existe» persiste tras cargar el establecimiento alternativo (OBS-AWS-01 del plan de pruebas) | Media | AWS | [Ciclo 9](ciclo_09_20261114T220556Z/catalogo_200/resultados.md) (SAAD-CP-004) | Catalina | El fallo del detalle se guarda en un estado propio (`errorDetalle`) que se limpia al iniciar cada consulta de detalle; el error general queda solo para meta y listado (`VistaEstablecimientos.tsx`) | Local 2026-11-15 (Chrome headless, perfil nuevo): `#/establecimientos?id=999999999` abre el 109102 sin alertas. [Ciclo 15](ciclo_15_20261116T013931Z/retest_def12_def14.md) en AWS: aprobado | **Cerrado** |
| DEF-13 | Contraste insuficiente en tema claro: «· 4 advertencias» (4,09:1) y la etiqueta «en desarrollo» (4,26:1); el mínimo para texto normal es 4,5:1 | Media (accesibilidad) | AWS | [Ciclo 7](ciclo_07_20261114T211303Z/catalogo_200/resultados.md) y [ciclo 10](ciclo_10_20261114T225227Z/catalogo_200/resultados.md) (SAAD-CP-073) | Catalina | Se quita `opacity-80` del contador de advertencias (`AvisoLectura.tsx`) y la etiqueta pasa de `--ink-3` a `--ink-2` (`Alcance.tsx`) | Local 2026-11-15, contraste calculado sobre colores computados: claro 6,36:1 y 7,64:1; oscuro 10,63:1 y 9,18:1. [Ciclo 15](ciclo_15_20261116T013931Z/retest_def12_def14.md) en AWS: mismos valores, aprobado | **Cerrado** |
| DEF-14 | El tablero desborda en horizontal en AWS: el documento mide 533 px en una ventana de 360 px (desborde de 173 px) y 44 px a 640 px; la tabla de comunas no queda contenida en su contenedor desplazable | Media | AWS y local | [Ciclo 10](ciclo_10_20261114T225227Z/catalogo_200/resultados.md) (SAAD-CP-071; observación en SAAD-CP-072) | Catalina | Causa real: no era la tabla sino los tooltips (`Tip.tsx`). Ocultos con `visibility: hidden` seguían ocupando espacio, y los anclados cerca del borde derecho ensanchaban el documento. Ahora se ocultan con `display: none` (con `transition-discrete` y `@starting-style` para conservar el fundido) | Local 2026-11-15: el mismo código antes del cambio reproducía 533 px a 360 px; después, 0 px de desborde a 360 y 640 px en tablero, establecimientos y entrada. Los tooltips siguen abriendo con mouse y con foco de teclado. [Ciclo 15](ciclo_15_20261116T013931Z/retest_def12_def14.md) en AWS: 0 px de desborde en las cuatro vistas a 360 px y en el tablero a 640 px | **Cerrado** |

| Defecto | Casos fallidos | Evidencia principal |
|---|---|---|
| DEF-12 | SAAD-CP-004 | `ciclo_09_20261114T220556Z/catalogo_200/EVIDENCIA/SAAD-CP-004_20261114_aws.json` y capturas antes y después de recargar |
| DEF-13 | SAAD-CP-073 | `ciclo_07_20261114T211303Z/catalogo_200/EVIDENCIA/SAAD-CP-073_20261114_aws.json` (detalle por elemento) y las capturas manuales del ciclo 10 |
| DEF-14 | SAAD-CP-071 | `ciclo_10_20261114T225227Z/catalogo_200/EVIDENCIA/SAAD-CP-071_20261114_aws.json` y capturas de cada vista |

**Nota sobre DEF-14 y SAAD-CP-071.** En modo dispositivo móvil, Chrome amplía el ancho del layout a
533 px y encoge la página, por lo que no aparece barra de desplazamiento y la pantalla «se ve bien»;
el contenido sigue sin caber en 360 px. En el entorno local el mismo caso aprueba
([ciclo 8](ciclo_08_20261114T220553Z/catalogo_200/resultados.md)). El estado del caso depende de
cómo se lea el criterio «las tablas pueden desplazarse en su contenedor»; se registró según el ancho
del documento, que es lo que pide el procedimiento.

**Hallazgo sin caso fallido.** SAAD-CP-041 quedó aprobado con una observación: la interfaz no muestra
la fecha de corte de defunciones (solo la entrega la API). Si el equipo decide que debe ser visible,
el caso pasa a fallido y se abre un defecto.

---

## CI en CodePipeline

**Estado al 2026-11-17: desbloqueada.** La conexión de CodeConnections `saad-github` pasó de `PENDING` a
`AVAILABLE` y el pipeline `saad-pr` (fuente GitHub + `Tests-y-cfn-lint`) terminó en **Succeeded**
(CP-066, [`catalogo_200_aws_reintento`](ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/resultados.md)).
El pipeline `saad-despliegue`, que tenía una ejecución **Failed** del 2026-11-12 (conexión aún pendiente), se relanzó el
2026-11-18 y terminó en **Succeeded** (Fuente, Verificar y Desplegar): la pila `Saad` quedó en `UPDATE_COMPLETE`, la API sana
(1/1 tareas), las 7 alarmas en OK, `/api/v1/series/RM` pronosticando desde 2026-S46 y 6 casos de interfaz de humo aprobados
sobre el sitio desplegado.

**Historial:** hasta el 2026-11-16 ambos pipelines estaban bloqueados. Para activar la conexión, la dueña del
repositorio instaló la app *AWS Connector for GitHub* y aprobó la conexión en la consola de AWS
(*Developer Tools → Settings → Connections → saad-github → Update pending connection*).

**Contingencia anterior:** la misma verificación (pytest + CDK synth + cfn-lint) se ejecutó en el equipo; los
resultados quedan en `ci_local.log` de cada carpeta de ciclo.

---

## Resumen de estados

| Estado | Defectos |
|---|---|
| Abierto | — |
| Cerrado | DEF-01, DEF-02, DEF-03, DEF-04, DEF-05, DEF-06, DEF-07, DEF-08, DEF-09, DEF-10, DEF-11, DEF-12, DEF-13, DEF-14, DEF-15, DEF-16 |

DEF-01 a DEF-04 se cerraron en el ciclo 4 (2026-11-12). DEF-12 a DEF-14 se abrieron el 2026-11-14
y se cerraron el 2026-11-15 junto con DEF-11. DEF-15 se detectó el 2026-11-15 con el verificador
de DEF-11 y se cerró el 2026-11-16 regenerando el pipeline (`2dc0150`). DEF-16 se detectó el
2026-11-17 con el guard `cortes_desalineados()` añadido al verificador y se cerró ese mismo día
reconstruyendo las etapas de demanda y republicando con `subir_datos.sh`.
