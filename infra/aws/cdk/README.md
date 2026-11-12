# Infraestructura del SAAD con AWS CDK (Python)

Crea en `us-east-1`: una VPC sin NAT, el bucket de datos, el servicio ECS Fargate `saad-api` (0,5 vCPU, 2 GB) detrás de un ALB que solo acepta tráfico de CloudFront, el bucket del sitio y la distribución CloudFront con la URL `*.cloudfront.net`. Todo está descrito en [`saad_stack.py`](saad_stack.py).

El pipeline **no** corre en AWS: se ejecuta en el equipo y `subir_datos.sh` publica sus outputs.

## Requisitos (una vez)

```bash
aws login --region us-east-1        # o el método de la cuenta del equipo
aws sts get-caller-identity          # comprobar la cuenta

python3 -m venv infra/aws/cdk/.venv
infra/aws/cdk/.venv/bin/pip install -r infra/aws/cdk/requirements.txt

export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
npx --yes aws-cdk@2 bootstrap aws://$CDK_DEFAULT_ACCOUNT/us-east-1   # desde la raíz del repo, no desde infra/aws/cdk
```

El `bootstrap` prepara la cuenta para CDK (un bucket y roles propios de CDK). Se hace una sola vez por cuenta y región.

## Despliegue

Ejecutar desde la raíz del repositorio, con el venv de CDK activado (`source infra/aws/cdk/.venv/bin/activate`):

```bash
# 1. Imagen de la API en ECR, etiquetada con el commit (exige no tener cambios sin commit en el código)
infra/aws/scripts/publicar_imagen.sh            # imprime la etiqueta, p. ej. 8d81b38

# 2. Primera vez: crear la pila con la API apagada, porque el bucket de datos aún está vacío
infra/aws/scripts/desplegar.sh 8d81b38 0

# 3. Subir los datos que lee la API (sin reiniciar, porque todavía no hay tareas)
infra/aws/scripts/subir_datos.sh --sin-reinicio

# 4. Encender la API
infra/aws/scripts/desplegar.sh 8d81b38 1
```

La URL aparece en la salida `Url` del paso 4.

`desplegar.sh` también construye el frontend (`npm run build`) y lo publica en el bucket del sitio.

## Configuración local (`infra/aws/.env`)

Los datos propios de cada cuenta (número de cuenta, encabezado secreto CloudFront → ALB, nombres de buckets, URL) van en `infra/aws/.env`, que está fuera de Git. Copiar [`infra/aws/.env.example`](../.env.example) y completarlo; los scripts lo leen solos, y una variable definida en la terminal tiene prioridad. `desplegar.sh` genera `SAAD_ORIGIN_SECRET` la primera vez si falta. CDK escribe además `cdk.context.json` con datos de la cuenta; también queda fuera de Git.

## Operación

| Tarea | Comando |
|---|---|
| Publicar datos nuevos tras correr el pipeline en el equipo | `infra/aws/scripts/subir_datos.sh` (sube y reinicia la API) |
| Desplegar una versión nueva del código | `publicar_imagen.sh` y luego `desplegar.sh <etiqueta>` |
| Volver a la versión anterior | `desplegar.sh <etiqueta-anterior>` (ECR conserva las 5 últimas) |
| Apagar la API sin borrar nada (ahorra Fargate, no el ALB) | `desplegar.sh <etiqueta> 0` |
| Ver logs de la API | `aws logs tail /ecs/saad-api --follow` |
| Borrar todo entre demos | `aws cloudformation delete-stack --stack-name Saad --region us-east-1` (los buckets se vacían solos; el repositorio ECR y la preparación de CDK quedan) |

## Cómo obtiene sus datos la API

Al arrancar, el contenedor ejecuta `src/cloud/api_arranque.py`: si existe `SAAD_S3_BUCKET` (la pila lo define), baja `data/` y `reports/` del bucket de datos y luego inicia `uvicorn`. El rol de la tarea solo puede leer ese bucket. Si la descarga falla, la tarea termina con error en vez de servir una API sin datos. Sin `SAAD_S3_BUCKET` (Docker Compose) usa el volumen montado, como antes.
