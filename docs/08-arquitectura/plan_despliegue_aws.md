# Plan de despliegue en AWS: SAAD

**Fecha:** 2026-11-12 · **Base:** arquitectura to-be (`Arquitectura_ToBe_AWS.docx`, ATB-SAAD-2026) · **Issues:** C-36 a C-46

Este plan convierte el diseño to-be en pasos ejecutables. La infraestructura está en [`infra/aws/cdk/`](../../infra/aws/cdk/) (AWS CDK con Python) y los pasos de operación, en su [README](../../infra/aws/cdk/README.md).

---

## 1. Arquitectura que se despliega

```
Usuario ──HTTPS──▶ CloudFront (https://<id>.cloudfront.net, sin dominio propio)
                    ├── /*        ──▶ S3 privado · sitio (build de Vite), vía Origin Access Control
                    └── /api/*    ──▶ ALB (solo acepta CloudFront) ──▶ ECS Fargate · saad-api
                                                                    (0,5 vCPU · 2 GB, 1 tarea)
                                                                    al arrancar lee S3 · datos
Equipo: pipeline local ──subir_datos.sh──▶ S3 · datos ──▶ reinicio de saad-api
ECR: imagen saad-api etiquetada con el commit · CloudWatch Logs: /ecs/saad-api (14 días)
```

Región: `us-east-1`. El frontend ya llama a la API con la ruta relativa `/api/v1`, así que CloudFront sirve sitio y API bajo el mismo origen, sin CORS. Es el mismo esquema que hoy usa nginx en Docker Compose.

## 2. Decisiones respecto del to-be

| Tema | To-be original | Decisión para el despliegue | Motivo |
|---|---|---|---|
| Pipeline | Tarea semanal en Fargate con EventBridge | **Se ejecuta en el equipo.** `subir_datos.sh` publica los outputs en S3 y reinicia la API | Evita mover ~12 GB de RAW a la nube, la tarea de 4 vCPU y 16 GB y EventBridge. Afecta a C-42 y #99, que hay que replantear con Felipe. |
| Datos de la API | ~12 GB de RAW (R-01) | **~215 MB**: `data/processed/`, `reports/` y el Excel INE de `data/raw/poblacion/` | Según el código actual, la API ya no lee el RAW de Urgencias. Hay que confirmarlo en C-07. |
| Tamaño de la API | 0,5 vCPU · 2 GB | **Se mantiene** | Hay que medir con `docker stats` en C-07; si la tarea se reinicia por memoria, subir a 1 vCPU · 4 GB. |
| HTTPS | CloudFront y ALB con certificados de ACM | **Solo la URL `*.cloudfront.net`.** CloudFront → ALB por HTTP; el ALB admite solo la prefix list de CloudFront y exige un encabezado secreto | Sin dominio propio no se puede emitir un certificado para el ALB. |
| Infraestructura como código (R-03) | Pendiente | **AWS CDK con Python** (`infra/aws/cdk/`) | Reproducible, y `cdk destroy` borra todo entre demos (R-05). |
| Aurora / PostGIS | Opcional | **No se despliega** | La API no usa base de datos; C-17 pide no afirmarla. |

Hallazgos que siguen vigentes:

- **Health check.** `/api/v1/salud` responde 200 incluso mientras la API carga. La plantilla lo usa en el ALB, con 300 s de gracia.
- **Tiempo de espera.** CloudFront espera hasta 60 s al ALB (nginx hoy espera 300). Hay que medir el endpoint más lento en C-07.
- **Clave de CARTO.** `VITE_CARTO_API_KEY` queda dentro del JavaScript publicado. Hay que restringirla al dominio de CloudFront en CARTO.
- **Pronóstico.** Hay que subir a S3 un pronóstico vigente; si no, la API lo recalcula al arrancar, lo que con 0,5 vCPU puede tardar mucho (R-02).

## 3. Cómo lee sus datos la API (C-39)

`src/cloud/api_arranque.py` es el punto de entrada de la imagen `api`: con `SAAD_S3_BUCKET` baja `data/` y `reports/` del bucket y luego inicia `uvicorn`; sin esa variable usa el volumen de Docker Compose, como antes. Reutiliza `listar` y `descargar` de `src/cloud/pipeline_task.py` y tiene pruebas en `tests/test_api_arranque.py`. Falta verificarlo contra un bucket real.

## 4. Decisiones que hay que confirmar antes de desplegar (C-36)

1. **Tipo de cuenta.** ¿Es una cuenta propia o una de AWS Academy Learner Lab? En Learner Lab normalmente no se pueden crear roles IAM ni hacer `cdk bootstrap`, y algunos servicios están restringidos. **Es lo primero a verificar.**
2. **Presupuesto.** Con todo encendido el mes completo, unos US$57 al mes. Si se borra entre demos, pocos dólares. Hay que crear una alerta en AWS Budgets (gratuita) por, por ejemplo, US$20.
3. **Responsables.** C-39 (arranque desde S3) es de Felipe. Si lo hace Catalina, hay que reasignarlo. C-42 cambia de alcance por la decisión del pipeline local.
4. **Demostración mínima.** URL de CloudFront mostrando mapa, pronóstico, establecimientos y advertencias con datos leídos de S3, más la publicación de datos con `subir_datos.sh` como flujo de actualización.

## 5. Pasos y calendario

| Día | Issue | Paso | Resultado verificable |
|---|---|---|---|
| 12-11 | C-36 | Confirmar cuenta, permisos y presupuesto. `cdk bootstrap` | Cuenta registrada; bloqueos escalados |
| 12-11 | C-07 | Línea base local: `docker compose up`, `docker stats`, latencia del endpoint más lento, API montando solo los ~215 MB | Registro local con commit, versiones y logs |
| 13-11 | C-39 | Arranque de la API desde S3; prueba local con `SAAD_S3_BUCKET` | API carga datos desde S3 |
| 13-11 | C-38 | `publicar_imagen.sh` | Imagen en ECR con etiqueta = commit |
| 13-11 | C-37 | `desplegar.sh <tag> 0` y `subir_datos.sh --sin-reinicio` | Pila creada; datos en S3 |
| 14-11 | C-40 | `desplegar.sh <tag> 1` | `/api/v1/salud` vía CloudFront responde con datos listos |
| 14-11 | C-41 | Verificar el sitio en la URL de CloudFront | Navegación completa con datos de AWS |
| 16–18-11 | C-44, C-06 | Prueba de punta a punta contrastada con la línea base local; registro de defectos | Evidencia por entorno |
| 18-11 | C-46 | Ensayo de la demo; contingencia local | Roles y plan de recuperación |
| 18–25-11 | C-17, C-45 | Diagramas *as-built*; manual operacional (el README de CDK es la base) | Documentación coherente con lo desplegado |

## 6. Riesgos

- **Plazo.** Si al 18-11 no hay URL operativa, se presenta la demo local de forma transparente (C-44 y C-46 ya lo prevén).
- **Cuenta restringida.** Si no permite crear roles o CloudFront, el respaldo es una sola EC2 con Docker Compose (alternativa 4.1 del to-be), documentando el cambio.
- **Memoria.** Con 2 GB la API podría quedarse corta. Se detecta en los logs como reinicios de la tarea, y se corrige cambiando `cpu` y `memory_limit_mib` en `saad_stack.py`.
- **Costos.** Son estimaciones; se revisa la facturación al día siguiente del primer despliegue.
