# Manual de implementación — SAAD

> Fase 2.2 · C-16 · Corte del 18 de noviembre de 2026 (UTC). Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental para la Región Metropolitana. Guía para instalar, desplegar, verificar y recuperar la aplicación. La evidencia se identifica por fecha, entorno y versión.

**Documento de entrega.** [Manual de implementación en Word](Manual_Implementacion_SAAD.docx).

## Índice

1. [Estado de validación](#1-estado-de-validación)
2. [Arquitectura y requisitos](#2-arquitectura-y-requisitos)
3. [Configuración por entorno](#3-configuración-por-entorno)
4. [Instalación y actualización local](#4-instalación-y-actualización-local)
5. [Despliegue y publicación en AWS](#5-despliegue-y-publicación-en-aws)
6. [Validación y registro de evidencia](#6-validación-y-registro-de-evidencia)
7. [Diagnóstico y recuperación](#7-diagnóstico-y-recuperación)
8. [Pendientes de cierre](#8-pendientes-de-cierre)

## 1. Estado de validación

| Procedimiento | Estado y evidencia |
|---|---|
| Instalación local con Docker Compose | **Ejecutada** el 12-11 en Ubuntu 24.04 sobre `f51f7f5`. La primera corrida registró 10 de 14 casos aprobados. Los cuatro casos fallidos se revalidaron en el ciclo 4 tras publicar las salidas faltantes. [Línea base local](../../reports/validation/baseline_local/20261112T135538Z/informe.md) · [Registro de defectos](../../reports/validation/ciclos_pruebas/registro_defectos.md) |
| Instalación con Python en Windows | **Ejecutada** el 10-11 sobre `e7a55db` con cambios locales. `pip check` sin conflictos y 867 pruebas aprobadas. La instalación limpia en un segundo equipo se informó el 08-10 y queda sin evidencia archivada. [Revalidación del 10-11](../../reports/validation/c08_revalidacion_20261110.md) · [README del proyecto](../../README.md) |
| Pipeline y pruebas automatizadas | **Ejecución parcial** del pipeline el 15-11 con `--sin-evaluacion --force`. En la misma revalidación se registraron 920 pruebas ordinarias y 29 de integración aprobadas sobre `5c341c5` con cambios locales. Los benchmarks y holdouts quedan pendientes para el snapshot actualizado. [Informe C-08](../../reports/validation/c08_revalidacion_20261115T161029Z/informe.md) |
| Despliegue de API y frontend en AWS | **Ejecutado**. La prueba E2E del 12-11 registró 21 aprobados, 4 fallidos por salidas faltantes y 6 sin ejecutar. La lectura AWS del ciclo 17 registró una tarea sana y la imagen `saad-api:95d00f8`, identificada por su digest. [Informe E2E del 12-11](../../reports/validation/e2e_local_aws/20261112T131720Z/informe.md) · [Lectura AWS del ciclo 17](../../reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_lectura/resultados.md) |
| Verificación de interfaz en AWS | **48 aprobados y 0 fallidos** en la corrida de interfaz del ciclo 17 (Chrome). La ejecución de **SAAD-CP-074** confirmó que el recorrido por Santiago y el Hospital Clínico San Borja Arriarán mostró los mismos datos en Chromium, Firefox y WebKit con el snapshot 2026-S45. [Corrida de interfaz](../../reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_manual_aws/resultados.md) · [Evidencia de compatibilidad](../../reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_compatibilidad/EVIDENCIA/SAAD-CP-074.md) |
| Publicación de datos y paridad local–AWS | **SAAD-CP-068 aprobado** en el reintento del 17-11. La primera comparación estuvo bloqueada porque `/meta` informaba 2026-S45 en AWS, pero `/series/RM` empezaba a pronosticar en 2026-S40. Tras publicar los datos del commit `8f7dd49`, `/series/RM` empezó en 2026-S46 en ambos entornos. La corrida registró 13 endpoints equivalentes, 24 comprobaciones aprobadas, 0 fallidas y 7 sin ejecutar. [Evidencia de paridad](https://github.com/Camila-Aroca/Proyecto-Capstone/blob/be1fd85503963e3b9b6d1d636b5a251041a3cc02/reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/EVIDENCIA/SAAD-CP-068.md) |
| Defectos y automatización | **DEF-01 a DEF-16 cerrados** según el registro. DEF-11 se verificó con pruebas del publicador, DEF-12 a DEF-14 con retests de interfaz y DEF-15 a DEF-16 con evidencias de datos. En el reintento, **SAAD-CP-066 aprobado**. La conexión `saad-github` quedó en `AVAILABLE` y `saad-pr` ejecutó con éxito. `saad-despliegue` conserva su fallo histórico del 12-11 y no se volvió a lanzar. [Registro de defectos](../../reports/validation/ciclos_pruebas/registro_defectos.md) · [Reintento del ciclo 17](https://github.com/Camila-Aroca/Proyecto-Capstone/blob/be1fd85503963e3b9b6d1d636b5a251041a3cc02/reports/validation/ciclos_pruebas/ciclo_17_20261117T140040Z/catalogo_200_aws_reintento/resultados.md) |

**Catálogo de 200 casos.** Tras SAAD-CP-074, el registro consolida 194 aprobados, 0 fallidos y 6 sin ejecutar. Los seis están pendientes de una sesión con un piloto o de coordinación con el cliente. Las cifras de las corridas individuales corresponden a su propia cobertura. [Registro principal de pruebas](../../reports/validation/registro_principal_pruebas.md)

La certificación de octubre corresponde al código y a los datos de ese corte. Registre por separado el commit utilizado para los comandos, la imagen desplegada y el snapshot de datos servido.

## 2. Arquitectura y requisitos

| Componente | Implementación |
|---|---|
| Aplicación local | FastAPI en el puerto 8000. Vite en 5173 durante desarrollo, o nginx en 8080 con Docker Compose. nginx reenvía `/api` a la API. |
| Aplicación en AWS | CloudFront entrega el sitio desde un bucket S3 privado y enruta `/api` al ALB y a ECS Fargate. La configuración predeterminada de CDK para la API es 0,5 vCPU, 2 GB y una tarea. |
| Almacenamiento y operación | ECS lee el bucket de datos al iniciar. ECR conserva imágenes; CloudWatch recibe logs y alarmas; SNS entrega avisos cuando la suscripción está confirmada. La API lee archivos Parquet y reportes. PostgreSQL y PostGIS quedan fuera del despliegue. |
| Pipeline | Se ejecuta en el equipo mediante Python o el perfil `pipeline` de Compose. Escribe en `data/` y `reports/`. La publicación a AWS se hace mediante un procedimiento independiente. |

### 2.1 Requisitos del equipo

- Para instalar sin contenedores, disponga de Git, Python 3.12 y Node.js 22 con npm. Use `requirements.txt` y `frontend/package-lock.json` como referencias de versiones. Para Compose, disponga de Docker con el complemento `docker compose`, un motor activo y puertos de host disponibles. Las imágenes fijan Python 3.12, Node.js 22 y nginx 1.27.
- Para generar los datos desde cero, disponga de acceso a las fuentes oficiales y espacio para el RAW, descargas temporales, salidas y contenedores. El inventario documenta unos 12 GB de RAW. [Fuentes de datos](../09-fuentes-de-datos/README.md)
- Para desplegar en AWS, use Bash en un entorno con Python 3, Node.js/npm, Git, Docker y AWS CLI. Los scripts esperan entornos virtuales con `.venv/bin/` y el despliegue usa OpenSSL si necesita generar el secreto de origen. En Windows, ejecute los scripts AWS en un entorno Linux como WSL con estas dependencias disponibles.

### 2.2 Permisos para la operación en AWS

| Identidad | Acceso requerido |
|---|---|
| Operador de despliegue | Identidad autenticada en la cuenta del proyecto. Acceso para publicar la imagen en ECR, consultar la lista administrada de CloudFront en EC2, desplegar CloudFormation vía CDK y usar los roles de bootstrap. Para una cuenta nueva también se requiere autorización para crear dichos recursos. |
| Operador de datos | Lectura de salidas de la pila, listado y escritura en los prefijos de datos del bucket, y consulta y actualización del servicio ECS para reiniciarlo y esperar su estabilización. |
| Operador de verificación | Lectura de CloudFormation, ECS, ALB, ECR, S3 y CloudWatch según los controles que ejecutará. La verificación de CodeConnections requiere acceso de lectura a la conexión. |
| Rol de la tarea de API | Lectura del bucket de datos para listar y descargar archivos. El rol de ejecución de ECS obtiene la imagen de ECR y escribe logs. |
| Responsable de la conexión GitHub | Autoriza la conexión `saad-github` y el acceso de la aplicación de GitHub al repositorio. |

La pila define los permisos de la tarea. El detalle de las políticas efectivas de los operadores y su validación en la cuenta se documentan en [C-45](https://github.com/Camila-Aroca/Proyecto-Capstone/issues/145). [Infraestructura CDK](../../infra/aws/cdk/README.md)

## 3. Configuración por entorno

| Entorno | Configuración |
|---|---|
| Python y Vite | El proxy de desarrollo usa `SAAD_API_URL` con destino predeterminado `http://127.0.0.1:8000`. La lista `SAAD_CORS_ORIGINS` de la API admite los dos orígenes locales de Vite por defecto. Copie `frontend/.env.example` a `frontend/.env.local` si necesita `VITE_CARTO_API_KEY`. Como queda incluida en el JavaScript del cliente, restrinja su uso por dominio en CARTO. |
| Docker Compose | `SAAD_API_PORT` y `SAAD_WEB_PORT` permiten ajustar los puertos 8000 y 8080 del host. La API recibe montajes de solo lectura para `data/` y `reports/`. El perfil `pipeline` usa montajes con escritura. |
| AWS, configuración del operador | Use `infra/aws/.env.example` como base para `infra/aws/.env`, que está fuera de Git. Los valores de la terminal tienen prioridad cuando están definidos. La región de la pila CDK es `us-east-1`. Los scripts obtienen la cuenta de la identidad AWS activa mediante STS. Para el despliegue estándar use la pila `Saad` y el repositorio `saad-api`. `SAAD_STACK` elige la pila que consulta el publicador de datos. |
| AWS, configuración de la tarea | CDK asigna `SAAD_S3_BUCKET` y un `SAAD_S3_PREFIX` vacío. `SAAD_API_CPU`, `SAAD_API_MEMORY` y `SAAD_ALARM_EMAIL` configuran recursos y avisos del despliegue manual. `SAAD_ORIGIN_SECRET` se genera en el primer despliegue si falta y se guarda fuera de Git. |

Para el pronóstico regional y comunal de demanda, `SAAD_USAR_PRONOSTICO_DESACTUALIZADO=0` reutiliza el pronóstico vigente y permite recalcular en memoria si falta o quedó desactualizado. Con `1`, puede servir el persistido desactualizado si existen el archivo y su manifiesto. La API informa una advertencia de vista temporal. Durante la preparación, los endpoints que necesitan el pronóstico pueden responder `503` con `Retry-After`. [Configuración del frontend](../../frontend/vite.config.ts) · [Servicio de pronóstico](../../src/api/service.py) · [Configuración AWS de ejemplo](../../infra/aws/.env.example)

## 4. Instalación y actualización local

### 4.1 Preparar Python y generar los datos

**Prerrequisitos.** Git, Python 3.12, espacio y acceso a las fuentes según la sección 2.

**Pasos.** Clone el repositorio con `git clone https://github.com/Camila-Aroca/Proyecto-Capstone.git` y entre a `Proyecto-Capstone/`. Sitúese en el commit que va a verificar. Cree el entorno con `python -m venv .venv`. Actívelo con `.\.venv\Scripts\Activate.ps1` en PowerShell o con `source .venv/bin/activate` en Bash. Luego instale las dependencias y ejecute el pipeline.

```text
python -m pip install -r requirements.txt
python -m pip check
python scripts/run_pipeline.py
python scripts/verificar_outputs_api.py
```

**Resultado esperado.** El pipeline valida y publica los archivos necesarios en `data/processed/` y `reports/`. La primera ejecución también descarga los insumos RAW.

**Comprobación.** `pip check` informa ausencia de conflictos, el pipeline termina con código 0 y el verificador confirma que están las salidas de la API, que las huellas de los manifiestos coinciden y que los cortes de demanda y establecimientos están alineados. Conserve el log y el commit. [Guía del pipeline](../../PIPELINE.md#2-ejecución-completa)

### 4.2 Iniciar la API y el frontend sin contenedores

**Prerrequisitos.** Entorno Python instalado, datos verificados, Node.js 22 y puertos 8000 y 5173 disponibles.

**Pasos.** En una terminal con el entorno Python activo, desde la raíz, ejecute `python -m uvicorn src.api.main:app --reload`. En otra terminal, entre a `frontend/` y ejecute `npm ci` y luego `npm run dev`.

**Resultado esperado.** La API queda disponible en `http://127.0.0.1:8000` y Vite muestra la dirección de desarrollo, normalmente `http://localhost:5173`.

**Comprobación.** Abra la aplicación y el tablero regional. Consulte `http://127.0.0.1:8000/api/v1/salud` y ejecute los controles de la sección 6. Conserve el estado de arranque que reporte cada servicio.

### 4.3 Iniciar la aplicación con Docker Compose

**Prerrequisitos.** Motor Docker activo, complemento Compose instalado, puertos disponibles y salidas verificadas en los directorios de trabajo.

**Pasos.** Ejecute los comandos desde la raíz.

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8080/api/v1/salud
```

**Resultado esperado.** La API queda sana y nginx sirve el frontend en `http://localhost:8080` con acceso a la API por el mismo origen. Ajuste la URL si cambió el puerto del host. En PowerShell puede usar `curl.exe` en lugar de `curl`.

**Comprobación.** Verifique `healthy` en la API, ambos estados `listo` en el JSON de salud y la carga del tablero regional en el navegador. Consulte los criterios de la sección 6. Ante un error, revise `docker compose logs --tail 100 api web`.

### 4.4 Actualizar datos y pronósticos

**Prerrequisitos.** Entorno de la sección 4.1. El modo sin evaluación requiere las selecciones de modelos ya publicadas y las ejecuciones parciales requieren sus insumos upstream.

**Pasos.** Elija el comando adecuado y conserve su log. El modo `--refresh-current-urgencias` se ejecuta por separado de `--sin-evaluacion`.

| Comando | Cuándo usarlo |
|---|---|
| `python scripts/run_pipeline.py` | Primer arranque o evaluación completa. Ejecuta las etapas pendientes y reutiliza las salidas que valida. |
| `python scripts/run_pipeline.py --sin-evaluacion` | Actualizar datos y pronósticos con las selecciones existentes, omitiendo benchmarks, holdouts, diagnósticos y calibraciones de evaluación. |
| `python scripts/run_pipeline.py --refresh-current-urgencias` | Consultar el ZIP mutable de Urgencias del año en curso y actualizar su RAW y salidas afectadas cuando corresponda. El refresco por sí solo deja pendiente el pronóstico. |
| `python scripts/run_pipeline.py --stage <etapa>` | Ejecutar la etapa y sus descendientes con los insumos ya disponibles. Agregue `--force` si necesita reconstruir salidas existentes. |
| `docker compose --profile pipeline run --rm pipeline` | Ejecutar el pipeline completo en contenedor sobre los volúmenes locales. |
| `docker compose --profile pipeline run --rm pipeline python -m src.cloud.pipeline_task --modo semanal` | Refrescar Urgencias y regenerar el pronóstico de demanda en contenedor. Compruebe la alineación con establecimientos antes de publicar. |

**Resultado esperado.** Se generan o reutilizan las salidas que corresponden al modo seleccionado. Conserve la fecha de corte y, si aplicó el refresh, los hashes del manifiesto de procedencia.

**Comprobación.** Ejecute `python scripts/verificar_outputs_api.py` y revise el log del pipeline. Reinicie la API local para que vuelva a cargar los datos mediante `docker compose restart api` o reiniciando Uvicorn según el entorno. Compruebe el corte y la serie después del arranque. [Modalidades de ejecución](../../PIPELINE.md#3-ejecución-desde-una-etapa)

## 5. Despliegue y publicación en AWS

### 5.1 Preparar la cuenta y el entorno de CDK

**Prerrequisitos.** Acceso autorizado a la cuenta del equipo y a los roles de bootstrap, requisitos de la sección 2 y configuración de la sección 3. Trabaje desde la raíz del repositorio.

**Pasos.** Autentíquese con el método asignado a su cuenta. Compruebe la identidad, cree el entorno virtual de CDK y prepare la cuenta y región una vez si aún no están preparadas.

```bash
aws sts get-caller-identity
python3 -m venv infra/aws/cdk/.venv
infra/aws/cdk/.venv/bin/pip install -r infra/aws/cdk/requirements.txt
CUENTA_SAAD=$(aws sts get-caller-identity --query Account --output text)
npx --yes aws-cdk@2 bootstrap "aws://${CUENTA_SAAD}/us-east-1"
```

**Resultado esperado.** La cuenta coincide con la autorizada, las dependencias de CDK se instalan y el bootstrap queda disponible en `us-east-1`.

**Comprobación.** Verifique el código de salida de la instalación, la cuenta informada por STS y el estado exitoso de la pila de bootstrap. Registre el resultado sin exponer identificadores de cuenta o credenciales en la entrega.

### 5.2 Publicar la imagen y desplegar la aplicación

**Prerrequisitos.** Cuenta preparada, permisos de despliegue, Docker activo y código de la API en un commit con `src/`, `scripts/`, `requirements.txt` y `Dockerfile` sin cambios locales. Para la primera instalación, tenga listas las salidas del pipeline.

**Pasos.** Ejecute `bash infra/aws/scripts/publicar_imagen.sh` y copie la etiqueta impresa. Para crear la pila con la API apagada, ejecute `bash infra/aws/scripts/desplegar.sh <etiqueta> 0` y luego `bash infra/aws/scripts/subir_datos.sh --sin-reinicio`. Encienda la API con `bash infra/aws/scripts/desplegar.sh <etiqueta> 1`. En una pila operativa con datos compatibles se puede aplicar directamente este último comando para actualizar el código.

**Resultado esperado.** ECR contiene una imagen etiquetada con el SHA corto, la pila publica la URL de CloudFront y ECS inicia una tarea con la imagen seleccionada. El script de despliegue también construye y publica el frontend del árbol de trabajo actual.

**Comprobación.** Verifique etiqueta y digest en ECR, definición activa de tarea, tarea en ejecución y target sano. Abra la URL que devuelve la pila y ejecute los controles de la sección 6. Registre por separado el commit del frontend utilizado durante el despliegue. [Procedimiento CDK](../../infra/aws/cdk/README.md#despliegue)

### 5.3 Publicar datos en una pila en servicio

**Prerrequisitos.** Salidas coherentes, dependencias Python instaladas, identidad y región verificadas y permisos de publicación. Registre el conjunto a publicar y conserve una copia o referencia a las versiones del conjunto anterior, incluidos sus manifiestos.

**Pasos.** Desde la raíz y en Bash, ejecute `bash infra/aws/scripts/subir_datos.sh`. El script verifica las salidas antes de sincronizar `data/processed/`, `reports/` y `data/raw/poblacion/`. Después solicita el reemplazo de la tarea ECS y espera la estabilización. Use `--sin-reinicio` en la carga inicial con la API apagada o si la recuperación requiere conciliar el contenido antes de reiniciar. El RAW de Urgencias permanece en el equipo.

**Resultado esperado.** La nueva tarea carga desde S3 las salidas publicadas. El script realiza tres sincronizaciones independientes y conserva los objetos que se hayan quitado del árbol local.

**Comprobación.** Revise la salida del verificador, la estabilidad de ECS y los logs de arranque. Aplique la sección 6 y compare `/meta` y `/series/RM` con el mismo conjunto local. Una sincronización interrumpida puede dejar versiones mezcladas en S3. Si ocurre, complete o recupere el conjunto antes de reiniciar la API. [Script de publicación](../../infra/aws/scripts/subir_datos.sh)

## 6. Validación y registro de evidencia

### 6.1 Comprobar que la aplicación quedó operativa

**Prerrequisitos.** URL confirmada, API iniciada y fecha de corte esperada. Use el puerto local de la instalación o la URL de CloudFront registrada en la pila.

**Pasos.** Abra el tablero regional. Use la misma URL para consultar `/api/v1/salud`, `/api/v1/meta`, `/api/v1/series/RM`, `/api/v1/establecimientos-meta` y, si se actualizó esa rama, `/api/v1/suicidios/RM`.

**Resultado esperado.** `/salud` devuelve los estados `estado_datos` y `estado_pronostico` como `listo`. Las respuestas aplicables devuelven HTTP 200 y el tablero muestra el histórico y pronóstico del territorio seleccionado.

**Comprobación.** Compare la última semana observada de `/meta` y la primera semana pronosticada de `/series/RM` con los valores del snapshot que preparó. Registre el origen del pronóstico, las advertencias y los resultados observados. El código HTTP de `/salud` acredita respuesta del proceso y sus campos indican la disponibilidad de los datos. [Rutas de la API](../../src/api/routes.py)

### 6.2 Comparar local y AWS

**Prerrequisitos.** Ambos entornos accesibles y preparados con el mismo snapshot, URL local identificada y una identidad con acceso de lectura a los recursos AWS que inspecciona el script.

**Pasos.** Verifique primero el corte de ambos entornos, después ejecute desde la raíz `python scripts/qa_e2e_local_vs_aws.py --local http://localhost:8080 --sin-capturas`. Use el puerto de su frontend local si lo cambió.

**Resultado esperado.** La corrida compara las respuestas y registra los resultados de infraestructura y API. Si los cortes o manifiestos difieren, registre el caso como bloqueado por diferencia de snapshot.

**Comprobación.** Abra el informe generado y revise el resultado por endpoint. Para incorporar el retest al registro principal, anote el caso, ciclo, fecha, entorno, commit del ejecutor, imagen o digest, corte, resultado real y ruta de la evidencia. [Ejecutor de pruebas](../../scripts/qa_e2e_local_vs_aws.py) · [Registro principal](../../reports/validation/registro_principal_pruebas.md)

## 7. Diagnóstico y recuperación

### 7.1 Recuperar después de una falla de datos o del pipeline

**Prerrequisitos.** Log del fallo, acceso a los insumos y una copia o referencias verificables de la última publicación coherente.

**Pasos.** Identifique la etapa y salida que fallaron. Si el refresh de Urgencias fue rechazado, compruebe el RAW previo en el manifiesto de procedencia y reintente cuando la fuente esté disponible. Si falta una salida, ejecute su etapa y descendientes según `PIPELINE.md`. Use `--force` cuando deba regenerar una salida existente que no corresponde al snapshot. Por ejemplo, un `404` por falta de dotación psiquiátrica requiere revisar `build_dim_camas_psiquiatria_hospital_rm`.

**Resultado esperado.** La rama afectada produce salidas coherentes con los insumos y conserva los estados de ausencia de datos que define el contrato.

**Comprobación.** Verifique el código de salida y ejecute `python scripts/verificar_outputs_api.py`. Reinicie la API local o publique el conjunto validado según la sección 5.3. Confirme que el endpoint recuperado muestra el resultado esperado y registre el retest. [Hallazgos y retests](../../reports/validation/ciclos_pruebas/registro_defectos.md)

### 7.2 Recuperar la API o volver a una versión de código

**Prerrequisitos.** Acceso a logs y al servicio. Para volver a una versión anterior, identifique la última etiqueta de imagen válida en ECR y el commit de frontend compatible si también debe recuperarlo.

**Pasos.** En Compose, consulte `docker compose logs --tail 100 api` y use `docker compose restart api` cuando el problema sea de recarga. En AWS, revise los eventos ECS y `aws logs tail /ecs/saad-api --region us-east-1`. Si el problema es de recarga y el snapshot está verificado, asigne las salidas `Cluster` y `Servicio` de la pila a las variables del siguiente bloque y ejecute los comandos en Bash.

```bash
aws ecs update-service --region us-east-1 --cluster "$CLUSTER_SAAD" \
  --service "$SERVICIO_SAAD" --force-new-deployment
aws ecs wait services-stable --region us-east-1 --cluster "$CLUSTER_SAAD" \
  --services "$SERVICIO_SAAD"
```

Para revertir una versión de API use `bash infra/aws/scripts/desplegar.sh <etiqueta-anterior> 1`. Ejecute el script desde el commit del frontend que desea publicar.

**Resultado esperado.** La tarea inicia con la versión prevista y carga el conjunto de datos disponible. El rollback de ECS protege el despliegue de la tarea. La recuperación de datos se realiza mediante la sección 7.3.

**Comprobación.** Confirme definición de tarea, etiqueta o digest, target sano y resultados de la sección 6. Registre el evento y su evidencia. El reinicio para recargar datos está documentado en el ciclo 4. La reversión manual de imagen queda documentada como procedimiento pendiente de un retest archivado. [Operación de la pila](../../infra/aws/cdk/README.md#operación)

### 7.3 Recuperar una publicación de datos incompleta

**Prerrequisitos.** Permisos sobre el bucket de datos y una copia coherente del conjunto previo, o acceso a las versiones de sus objetos en S3. Identifique las versiones a partir de la publicación de referencia y sus manifiestos.

**Pasos.** Identifique las salidas que se publicaron y las que faltaron. Prepare el conjunto completo en una copia de trabajo con las rutas `data/` y `reports/` que espera el verificador. Si debe recuperarlo desde S3, consulte las versiones de los objetos con `aws s3api list-object-versions` y descargue cada versión requerida con `aws s3api get-object --version-id` a su ruta local correspondiente. Ejecute `python scripts/verificar_outputs_api.py` desde la raíz de esa copia. Con el operador autorizado, publique el conjunto completo con `bash infra/aws/scripts/subir_datos.sh --sin-reinicio`. Concilie los objetos que quedaron de la publicación incompleta y reinicie ECS según la sección 7.2 cuando el contenido esté verificado.

**Resultado esperado.** La API carga un conjunto con archivos y manifiestos compatibles entre sí.

**Comprobación.** Contraste hashes, corte y primera semana de pronóstico con la publicación de referencia. Confirme la recuperación con las comprobaciones de la sección 6. La recuperación completa de versiones S3 queda documentada para un ensayo controlado, pendiente de evidencia archivada. [Versionado del bucket en CDK](../../infra/aws/cdk/saad_stack.py) · [Manual operacional C-45](https://github.com/Camila-Aroca/Proyecto-Capstone/issues/145)

## 8. Pendientes de cierre

- Archivar una instalación desde un clon limpio, con versiones, comandos, fecha, commit y log de verificación.
- Completar la evaluación de modelos con el corte actualizado. La revalidación C-08 conserva su alcance parcial.
- Ejecutar y verificar `saad-despliegue` en una ventana autorizada. La conexión GitHub y `saad-pr` ya se verificaron en SAAD-CP-066.
- Registrar políticas efectivas, costos, alarmas y ensayos de recuperación en [C-45](https://github.com/Camila-Aroca/Proyecto-Capstone/issues/145). La ejecución programada en Fargate y EventBridge se sigue en [C-42](https://github.com/Camila-Aroca/Proyecto-Capstone/issues/142).
