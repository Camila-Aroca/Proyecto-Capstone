# Manual de implementación reproducible de SAAD (Fase 2.2)

**Versión:** primera versión de Fase 2.2, redactada el 14 de noviembre de 2026 sobre `11056a6` y actualizada el 15-11 con la evidencia C-08 y una consulta de AWS.
**Alcance:** instalación local (Python y Docker Compose) y despliegue en AWS tal como está registrado en el repositorio.
**Pendiente:** los anexos operacionales definitivos de AWS (seguridad, costos, observabilidad y operación) se completan en C-45. La corrida parcial posterior al corte de octubre se registra en C-08; la evaluación de modelos sigue pendiente.

Este manual no certifica nada por sí solo. Cada sección indica si el paso fue **ejecutado y registrado**, **documentado sin registro de ejecución**, **fallido**, **bloqueado** o **pendiente**, y enlaza la evidencia cuando existe.

## 1. Estado de validación

| Elemento | Estado | Evidencia |
|---|---|---|
| Instalación local con Docker Compose (API + frontend) | **Ejecutado** el 12-11 en Ubuntu 24.04, commit `f51f7f5` | [`reports/validation/baseline_local/20261112T135538Z/informe.md`](../../reports/validation/baseline_local/20261112T135538Z/informe.md): 10 de 14 casos aprobados. Los 4 fallidos faltaban outputs de datos y se cerraron después (DEF-01 a DEF-03) |
| Reejecución local posterior a la publicación de outputs | **Ejecutado** el 12-11 (ciclo 4) | [`reports/validation/ciclos_pruebas/registro_defectos.md`](../../reports/validation/ciclos_pruebas/registro_defectos.md) |
| Instalación Python local (Windows) | **Ejecutado** el 10-11 sobre `e7a55db` con cambios sin commit: `pip check` sin conflictos y 867 pruebas aprobadas | [`reports/validation/c08_revalidacion_20261110.md`](../../reports/validation/c08_revalidacion_20261110.md). No es una ejecución desde un clon limpio |
| Instalación limpia en un segundo computador | **Confirmada por el equipo el 08-10; sin evidencia archivada** en el repositorio (comandos, versiones, logs) | Solo la menciona el `README.md` |
| Pipeline posterior al corte de octubre | **Ejecutado parcialmente** el 15-11 con `--sin-evaluacion --force`; los benchmarks y holdouts no se rehicieron | [Evidencia C-08](../../reports/validation/c08_revalidacion_20261115T161029Z/informe.md) |
| Suite automatizada | **Ejecutada** el 15-11: 920 pruebas ordinarias y 29 de integración aprobadas; commit base `5c341c5` con cambios locales | [Resultados y entorno C-08/U-39](../../reports/validation/c08_revalidacion_20261115T161029Z/informe.md) |
| API local en el árbol de trabajo del 14-11 (sin ejecutar el pipeline) | **Observación histórica:** la API recalculó demanda en memoria y `/suicidios/RM` respondió 503 por un pronóstico desactualizado. Los pronósticos se regeneraron el 15-11; esta observación no verifica el estado posterior | Comprobación manual de la sesión del 14-11, sin archivo de evidencia |
| Despliegue de la API y el frontend en AWS (CloudFront → ALB → ECS Fargate, `us-east-1`) | **Ejecutado y probado** el 12-11: 21 casos aprobados, 4 fallidos y 6 no ejecutados en la corrida E2E | [`reports/validation/e2e_local_aws/20261112T131720Z/informe.md`](../../reports/validation/e2e_local_aws/20261112T131720Z/informe.md). Los 4 fallidos fueron faltas de outputs, cerradas luego |
| Pipeline en Fargate programado con EventBridge | **No implementado.** Cambio de alcance: el pipeline corre en el equipo y se publica con `subir_datos.sh` | [`docs/08-arquitectura/plan_despliegue_aws.md`](../08-arquitectura/plan_despliegue_aws.md), sección 2. C-42 sigue abierto |
| CI/CD con CodePipeline y CodeBuild | **Bloqueado:** la conexión `saad-github` está en `PENDING` hasta que la dueña del repositorio la apruebe | Sección «Bloqueo de CI» de `registro_defectos.md`. La misma verificación se corre en el equipo |
| Defectos abiertos | DEF-11 (`subir_datos.sh` no valida outputs completos) y DEF-12 a DEF-14 (interfaz en AWS) | `registro_defectos.md` |

La URL pública de la aplicación es [SAAD en AWS](https://d1zg565jvf1c8p.cloudfront.net/#/). El número de cuenta, los nombres de buckets y las credenciales no se incluyen aquí; la configuración local de AWS permanece fuera de Git.

**Consulta de solo lectura del 15-11:** la portada, `/api/v1/salud`, `/api/v1/meta`, `/api/v1/establecimientos-meta` y `/api/v1/suicidios/RM` respondieron HTTP 200. Salud informó datos y pronóstico listos. `/meta` informó última semana observada 2026-S39 y pronóstico generado el 12-11; la corrida local C-08 llegó a 2026-S45. Esto verifica respuestas puntuales y muestra una diferencia de corte, no valida toda la interfaz ni identifica el commit desplegado.

## 2. Versiones

| Componente | Versión | Origen |
|---|---|---|
| Python | 3.12 (`python:3.12-slim` en la imagen; 3.12.6 en el equipo de la revalidación del 10-11) | `Dockerfile`, C-08 |
| Node.js | 22 (`node:22-alpine` en la imagen del frontend; v22.15.1 en la línea base local) | `frontend/Dockerfile`, línea base local |
| nginx | 1.27 (`nginx:1.27-alpine`) | `frontend/Dockerfile` |
| Docker / Compose | 29.6.1 / 5.3.1 (versiones usadas en la línea base local) | línea base local |
| Dependencias Python | Fijadas con `==` en `requirements.txt`. Entre ellas: FastAPI 0.141.1, pandas 3.0.5, NumPy 2.5.2, PyArrow 25.0.1, LightGBM 4.7.0 | `requirements.txt` |
| Dependencias del frontend | Fijadas en `frontend/package-lock.json` (React ^19.3.0, Vite ^6.4.3, TypeScript ^7.0.2) | `frontend/package.json` |
| AWS CDK | CLI `aws-cdk@2` con las librerías de `infra/aws/cdk/requirements.txt` | `infra/aws/cdk/README.md` |
| Región AWS | `us-east-1` | `infra/aws/cdk/README.md` |

## 3. Arquitectura y servicios

| Servicio | Qué hace | Dónde corre |
|---|---|---|
| `api` (`saad-api`) | FastAPI de solo lectura. Carga los outputs del pipeline al arrancar | Docker Compose (puerto 8000) o ECS Fargate (0,5 vCPU, 2 GB, 1 tarea) |
| `web` (`saad-web`) | Build de Vite servido por nginx; reenvía `/api` a la API | Docker Compose (puerto 8080) o S3 privado detrás de CloudFront |
| `pipeline` (`saad-pipeline`) | Tarea por lotes que descarga fuentes, genera marts y modelos y escribe en `data/` y `reports/` | **Solo en el equipo** (perfil `pipeline` de Compose o `python scripts/run_pipeline.py`) |
| CloudFront, ALB, S3 de datos y de sitio, ECR, CloudWatch, SNS | Entrada HTTPS, balanceo, almacenamiento, imágenes y observabilidad | Solo AWS. Definidos en `infra/aws/cdk/saad_stack.py` |

Aurora o PostGIS **no se despliegan**: la API no usa base de datos.

## 4. Configuración no secreta

| Variable | Dónde se usa | Efecto |
|---|---|---|
| `SAAD_API_PORT`, `SAAD_WEB_PORT` | `docker-compose.yml` | Puertos del host (por defecto 8000 y 8080) |
| `SAAD_USAR_PRONOSTICO_DESACTUALIZADO` | API, Compose y `desplegar.sh` | Con `1`, sirve el pronóstico guardado aunque no esté vigente, con una advertencia visible. Con `0`, lo recalcula al arrancar y mientras tanto responde `503` |
| `SAAD_CORS_ORIGINS` | `src/api/main.py` | Orígenes permitidos. Por defecto `http://localhost:5173` y `http://127.0.0.1:5173` |
| `SAAD_API_URL` | `frontend/vite.config.ts` | Destino del proxy de desarrollo (por defecto `http://127.0.0.1:8000`) |
| `VITE_CARTO_API_KEY` | `frontend/.env.local` (copiar de `frontend/.env.example`) | Clave de CARTO para el mapa base. Sin clave el mapa muestra solo los límites comunales. En producción queda dentro del JavaScript publicado, por lo que se debe restringir por dominio en CARTO |
| `SAAD_S3_BUCKET`, `SAAD_S3_PREFIX` | `src/cloud/api_arranque.py` y `src/cloud/pipeline_task.py` | Con bucket, bajan `data/` y `reports/` desde S3. Sin él, usan el disco local |
| `SAAD_ECS_CLUSTER`, `SAAD_ECS_SERVICE` | `src/cloud/pipeline_task.py` | Si están, fuerzan un nuevo despliegue de la API al terminar con cambios |
| `AWS_ACCOUNT_ID`, `AWS_REGION`, `SAAD_STACK`, `SAAD_ECR_REPO`, `SAAD_API_CPU`, `SAAD_API_MEMORY`, `SAAD_ALARM_EMAIL` | `infra/aws/.env` (copiar de `infra/aws/.env.example`) | Parámetros del despliegue en AWS |

`SAAD_ORIGIN_SECRET` (encabezado secreto CloudFront → ALB) también vive en `infra/aws/.env`, lo genera `desplegar.sh` la primera vez y **no debe copiarse a documentos, issues ni capturas**.

## 5. Instalación local

### 5.1 Requisitos previos

- Python 3.12, Node.js 22 y Git. Para el camino con contenedores: Docker con Compose v2.
- Espacio en disco: `data/raw/` pesa unos 12 GB (las Atenciones de Urgencia son 9,1 GB; ver [`docs/09-fuentes-de-datos`](../09-fuentes-de-datos/README.md)). Los outputs que lee la API ocupan alrededor de 215 MB.
- Acceso a internet a los sitios oficiales de DEIS/MINSAL, INE y datos.gob.cl para descargar las fuentes.

### 5.2 Python y pipeline (documentado; ver sección 1 para su validación)

```bash
git clone https://github.com/Camila-Aroca/Proyecto-Capstone.git
cd Proyecto-Capstone
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check                  # debe informar «No broken requirements found.»
python scripts/run_pipeline.py       # genera data/processed y reports/ (primera vez: descarga el RAW)
```

Las variantes del pipeline están en [`PIPELINE.md`](../../PIPELINE.md):

| Comando | Para qué |
|---|---|
| `python scripts/run_pipeline.py` | Evalúa todo el DAG. Hace `SKIP` de lo vigente y ejecuta lo pendiente, incluidos benchmarks y holdouts |
| `python scripts/run_pipeline.py --sin-evaluacion` | Actualiza datos y pronósticos sin rehacer benchmarks, holdouts ni diagnósticos. **No reemplaza la corrida completa** |
| `python scripts/run_pipeline.py --refresh-current-urgencias` | Vuelve a consultar el ZIP mutable de Urgencias del año en curso y regenera solo lo afectado |
| `python scripts/run_pipeline.py --stage <etapa>` | Una etapa y sus descendientes. Exige que sus insumos ya existan |

Los datos RAW del año en curso son mutables: tras un refresh cambian los hashes registrados en `data/raw/provenance_manifest.json`. No se enlazan registros de Urgencias con Egresos por paciente; la relación entre fuentes es solo territorial.

### 5.3 API y frontend sin contenedores (documentado)

```bash
# Terminal 1, desde la raíz: API en http://127.0.0.1:8000 (documentación en /docs)
uvicorn src.api.main:app --reload

# Terminal 2: frontend en http://localhost:5173
cd frontend && npm install && npm run dev
```

Durante el arranque, los endpoints de pronóstico pueden responder `503` con `Retry-After`; el frontend reintenta.

### 5.4 Docker Compose (**ejecutado y registrado** en la línea base local)

Requiere `data/` y `reports/` con los outputs del pipeline, porque no se copian en las imágenes: se montan en solo lectura en la API.

```bash
docker compose up -d --build          # API en :8000, frontend en :8080
docker compose ps                     # la API debe quedar «healthy»
curl http://localhost:8000/api/v1/salud
```

Pipeline en contenedor, que sí escribe en `data/` y `reports/`:

```bash
docker compose --profile pipeline run --rm pipeline                                              # modo completo
docker compose --profile pipeline run --rm pipeline python -m src.cloud.pipeline_task --modo semanal
```

**La API lee sus datos solo al arrancar.** Tras regenerar outputs hay que reiniciarla (`docker compose restart api`); si no, sigue sirviendo el estado anterior. Este hallazgo está en el registro de defectos.

## 6. Provisión de datos a la API

| Entorno | Estrategia | Estado |
|---|---|---|
| Local / Compose | Volumen `./data` y `./reports` montado en solo lectura | **Ejecutado** (línea base local) |
| AWS | Al arrancar, `src/cloud/api_arranque.py` baja `data/` y `reports/` del bucket de datos; el rol de la tarea solo puede leer ese bucket. Si la descarga falla, la tarea termina con error; si el bucket no contiene objetos, advierte y continúa sin datos | **Ejecutado** el 12-11: 150 archivos, 212 MB, API lista en unos 36 s (comentario de cierre de #140) |
| Publicación de datos nuevos | `infra/aws/scripts/subir_datos.sh` sube a S3 `data/processed/`, `reports/` y `data/raw/poblacion/` y fuerza un nuevo despliegue de la API. No usa `--delete` | **Ejecutado** el 12-11 |

Qué sube `subir_datos.sh`: solo outputs procesados, reportes y el cuadro INE de población. El RAW de Urgencias no se sube. **Limitación abierta (DEF-11):** el script no valida que los outputs esperados estén completos antes de sincronizar; hay que correr el pipeline completo y revisar el resultado antes de publicar.

## 7. Despliegue en AWS

Descrito en [`infra/aws/cdk/README.md`](../../infra/aws/cdk/README.md) y [`docs/08-arquitectura/plan_despliegue_aws.md`](../08-arquitectura/plan_despliegue_aws.md). Resumen de la secuencia, con su estado:

| Paso | Comando | Estado |
|---|---|---|
| 1. Preparar la cuenta (una vez) | `aws login`, `cdk bootstrap aws://<cuenta>/us-east-1` | **Ejecutado** (la pila `Saad` existe). La verificación de cuenta, permisos y plan ejecutable de C-36 (#136) sigue abierta |
| 2. Publicar la imagen en ECR | `infra/aws/scripts/publicar_imagen.sh` (etiqueta = SHA corto del commit; se niega si hay cambios sin commit en el código) | **Ejecutado:** imágenes `547a7e7` y `90965fc` |
| 3. Crear la pila con la API apagada | `infra/aws/scripts/desplegar.sh <etiqueta> 0` | **Ejecutado** |
| 4. Subir datos | `infra/aws/scripts/subir_datos.sh --sin-reinicio` | **Ejecutado** |
| 5. Encender la API | `infra/aws/scripts/desplegar.sh <etiqueta> 1` | **Ejecutado**; servicio con 1 tarea en servicio al 12-11 |
| 6. Actualizar datos | pipeline local → `infra/aws/scripts/subir_datos.sh` | **Ejecutado** el 12-11 con `--sin-evaluacion` |
| 7. Verificar | `scripts/qa_e2e_local_vs_aws.py` | **Ejecutado** el 12-11; ver sección 1 |
| 8. Crear la pila de CI (`SaadCi`) | `cdk deploy SaadCi` y activación de la conexión con GitHub | **Bloqueado:** conexión `PENDING` |
| 9. Ejecutar el pipeline en Fargate con EventBridge | — | **No implementado** (decisión de alcance) |

Una versión de AWS desplegada hoy no está confirmada contra el commit del repositorio: `/api/v1/meta` no expone el SHA ni el digest de la imagen (nota en `registro_defectos.md`). Para saber qué corre, consultar la etiqueta de la imagen en el servicio ECS.

La regeneración local de C-08 no publica automáticamente en AWS. Antes de actualizar el despliegue, verificar con el equipo propietario de la cuenta los outputs y la limitación DEF-11; después de una publicación autorizada, comprobar nuevamente `/api/v1/salud`, `/api/v1/meta` y los endpoints pertinentes. La consulta del 15-11 mostró un corte anterior al local.

Para desmontar el entorno entre demos: `aws cloudformation delete-stack --stack-name Saad --region us-east-1`. El repositorio ECR y la preparación de CDK quedan.

## 8. Permisos por rol

| Rol | Permisos | Fuente |
|---|---|---|
| Rol de la tarea de la API (ECS) | Solo lectura del bucket de datos | cierre de #137 |
| Rol de ejecución de la tarea | Descargar la imagen de ECR y escribir logs | cierre de #137 |
| Usuarios y claves de acceso | La pila no crea ninguno | cierre de #137 |
| ALB | Solo acepta tráfico de la prefix list de CloudFront y con el encabezado secreto; el resto recibe 403 | cierre de #137 y prueba E2E |
| Buckets de datos y de sitio | Sin acceso público; cifrado en reposo (SSE-S3); solo HTTPS. El de datos tiene versionado; el del sitio solo lo lee CloudFront | cierre de #137 |
| Quien despliega (equipo) | Credenciales AWS propias para `publicar_imagen.sh`, `desplegar.sh` y `subir_datos.sh`. El detalle de las políticas concretas no está documentado en este manual y se completa en C-45 | pendiente |
| Colaboradores del repositorio | Hacer push de ramas; las verificaciones de CI solo se activan por push, no por pull requests de forks | `infra/aws/cdk/README.md` |
| Dueña del repositorio | Instalar *AWS Connector for GitHub* y aprobar la conexión `saad-github` | `registro_defectos.md` |

## 9. Fallas conocidas y cómo reconocerlas

| Síntoma | Causa verificada | Acción |
|---|---|---|
| `503` en `/api/v1/establecimientos`, `/suicidios/RM` y otros | Falta un output del pipeline o está desactualizado | Ejecutar el pipeline y publicar; reiniciar la API |
| `404` en `/api/v1/camas-psiquiatria/RM` | Falta `dim_camas_psiquiatria_hospital_rm` | Ejecutar la etapa `build_dim_camas_psiquiatria_hospital_rm` |
| Advertencia «Vista temporal» y pronóstico no vigente | Cambió la selección del benchmark respecto del snapshot con que se generó el pronóstico | Regenerar con la etapa `forecast_demanda_sm`, o usar `SAAD_USAR_PRONOSTICO_DESACTUALIZADO=1` a sabiendas de que las cifras pueden no corresponder al modelo seleccionado |
| La API no muestra datos recién publicados | Lee al arrancar | Reiniciar (`docker compose restart api` o `force-new-deployment`; `subir_datos.sh` ya lo solicita) |
| La descarga falla y el RAW previo se conserva | Es el comportamiento esperado del refresh | Reintentar; no hay que reparar nada |

## 10. Limitaciones de este manual

- No incluye una reejecución desde un clon limpio realizada para este documento.
- No describe políticas IAM concretas del equipo de despliegue ni el procedimiento operacional definitivo (C-45).
- La corrida completa del pipeline con benchmarks y holdouts sobre los datos posteriores al 8 de octubre está pendiente. La corrida C-08 del 15-11 omitió esas evaluaciones. La certificación del 8 de octubre (`reports/validation/apt_certification_20261008T002147Z/`) corresponde a otra versión del código y los datos, y no certifica la versión vigente.
- El despliegue en AWS tiene DEF-12 a DEF-14 abiertos (interfaz) y la CI/CD bloqueada.
