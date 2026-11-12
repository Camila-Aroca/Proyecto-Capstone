# Registro de defectos — SAAD CP-SAAD-2026 (C-06)

Registra los defectos reales encontrados durante los ciclos de prueba del catálogo CP-SAAD-2026.
Solo se registran defectos reales: hallazgos observables en la plataforma, no suposiciones.

Columnas: **ID** · **Título** · **Criticidad** · **Entorno** · **Detectado en** · **Responsable** · **Corrección** · **Retest** · **Estado**

---

## Defectos de datos y outputs del pipeline

Estos defectos bloquean múltiples casos del catálogo porque la API responde 404 o 503 cuando
falta el archivo de entrada. La corrección depende de que se ejecute el pipeline con los stages
correspondientes y se publiquen los outputs con `subir_datos.sh`.

| ID | Título | Criticidad | Entorno | Detectado en | Responsable | Corrección | Retest | Estado |
|---|---|---|---|---|---|---|---|---|
| DEF-01 | `camas-psiquiatria` responde 404: falta `dim_camas_psiquiatria_hospital_rm` | Alta | LOCAL · AWS | Ciclo 1 (CP-025) | Felipe (pipeline) | Pipeline ejecutado con `--sin-evaluacion` (stage `build_dim_camas_psiquiatria_hospital_rm`); publicado con `subir_datos.sh`; API local y ECS reiniciados para tomar los datos | Ciclo 4: CP-025 APROBADO en LOCAL y AWS | **Cerrado** |
| DEF-02 | Establecimientos responde 503: falta `mart_urgencias_establecimiento_weekly` y su pronóstico | Alta | LOCAL · AWS | Ciclo 1 (CP-037) | Felipe (pipeline) / Cristopher (API) | Pipeline ejecutado con `--sin-evaluacion` (stage `build_urgencias_establecimiento_weekly_mart` y `forecast_establecimientos_sm`); publicado con `subir_datos.sh`; API redesplegada | Ciclo 4: CP-037 APROBADO en LOCAL y AWS | **Cerrado** |
| DEF-03 | Suicidios responde 503: falta `mart_suicidios_comuna_weekly` en el pronóstico persistido | Alta | LOCAL · AWS | Ciclo 1 (CP-047) | Felipe (pipeline) | Pipeline ejecutado con `--sin-evaluacion` (stage `build_mart_suicidios_comuna_weekly` y `forecast_suicidios`); publicado con `subir_datos.sh`; API local y ECS reiniciados | Ciclo 4: CP-047 APROBADO en LOCAL y AWS | **Cerrado** |
| DEF-04 | Pronóstico de urgencias desactualizado: JSON de selección no versionado en S3 | Alta | LOCAL · AWS | Ciclo 1 (meta `motivo_desactualizacion`) | Felipe (pipeline) / Cristopher (API) | Pipeline completo corrido el 2026-11-12 regenera los tres pronósticos con datos frescos; flag `SAAD_USAR_PRONOSTICO_DESACTUALIZADO` desactivado en el redespliegue (`95d00f8`). Causa raíz (JSON de selección no versionado en S3) sigue sin corregirse: si el pipeline no corre a tiempo, el pronóstico volverá a quedar desactualizado | Ciclo 4: pronóstico vigente, sin advertencia de desactualización | **Abierto (causa raíz pendiente; síntoma resuelto)** |

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

### Casos antes bloqueados por DEF-01 a DEF-03 (ya aprobados desde el ciclo 4)

| Defecto | Casos que estaban BLOCKED |
|---|---|
| DEF-01 (camas) | CP-SAAD-042, CP-SAAD-043, CP-SAAD-044, CP-SAAD-045, CP-SAAD-059 |
| DEF-02 (establecimientos) | CP-SAAD-038, CP-SAAD-039, CP-SAAD-040, CP-SAAD-041 |
| DEF-03 (suicidios) | CP-SAAD-048, CP-SAAD-050, CP-SAAD-052 |

**Contingencia (histórica, ciclos 1-3):** los casos BLOCKED se marcaban como tal en la matriz; no
se contabilizaban como aprobados ni fallidos. Desde el ciclo 4 corren con datos reales.

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

---

## Defectos de infraestructura y scripts (abiertos)

| ID | Título | Criticidad | Entorno | Detectado en | Responsable | Corrección propuesta | Retest | Estado |
|---|---|---|---|---|---|---|---|---|
| DEF-11 | `subir_datos.sh` no valida que los outputs del pipeline estén completos antes de publicar | Media | Equipo / AWS | Revisión de script | Catalina | Agregar verificación de los archivos esperados (marts, manifiestos y JSON de selección) antes de hacer `aws s3 sync` | Pendiente | **Abierto** |

---

## Bloqueo de CI en CodePipeline

El pipeline `saad-pr` y `saad-despliegue` están **BLOCKED** porque la conexión de CodeConnections
`saad-github` está en estado `PENDING`.

**Motivo:** para activarla, la dueña del repositorio (`Camila-Aroca`) debe instalar la app
*AWS Connector for GitHub* y aprobar la conexión desde la consola de AWS
(*Developer Tools → Settings → Connections → saad-github → Update pending connection*).
Requiere permisos de administración sobre el repositorio.

**Contingencia activa:** la misma verificación (pytest + CDK synth + cfn-lint) se ejecuta en el
equipo como parte del ciclo de pruebas local. Los resultados quedan en `ci_local.log` de cada
carpeta de ciclo.

---

## Resumen de estados

| Estado | Defectos |
|---|---|
| Abierto | DEF-11 |
| Abierto (causa raíz pendiente) | DEF-04 |
| Cerrado | DEF-01, DEF-02, DEF-03, DEF-05, DEF-06, DEF-07, DEF-08, DEF-09, DEF-10 |

DEF-01, DEF-02 y DEF-03 se cerraron en el ciclo 4 (2026-11-12) tras ejecutar el pipeline con
`--sin-evaluacion`, publicar los outputs con `subir_datos.sh` y reiniciar la API en ambos
entornos. DEF-04 queda con el síntoma resuelto (pronóstico vigente) pero la causa raíz (JSON de
selección sin versionar en S3) sigue pendiente. DEF-11 sigue abierto.
