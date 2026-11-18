# Verificación de costos AWS — SAAD

**Región:** us-east-1  
**Fuente:** AWS Pricing API (precios de lista)  
**Actualización:** 15-11-2026, costeo del despliegue as-built (pilas CDK `Saad` y `SaadCi`)  
**Verificación original:** 12-10-2026, estimación to-be (ATB-SAAD-2026, sección 4)

> El total vigente es el del despliegue as-built: **≈ US$59,27 al mes**. La estimación to-be original
> (US$56,71) se conserva más abajo como antecedente, junto con la evidencia del AWS Pricing Calculator.

---

## Costos del despliegue actual (as-built)

Recursos tomados de `infra/aws/cdk/saad_stack.py` y `infra/aws/cdk/ci_stack.py`, con el tamaño de
tarea en servicio (0,5 vCPU, 2 GB). Diagrama: `docs/07-diagramas/despliegue_aws_as_built.drawio`.

### Diferencias con la estimación to-be

| Cambio | Efecto mensual (US$) |
|---|---|
| No se desplegó la tarea Fargate del pipeline ni EventBridge: el pipeline corre en el equipo y sus outputs se suben a S3 con `subir_datos.sh` (C-42 pendiente) | −1,05 (tarea e IP temporal) |
| Sin dominio propio: no hay certificado de ACM (CloudFront usa `*.cloudfront.net`) | 0,00 |
| Volumen real en S3: los outputs publicados suman ≈ 0,3 GB, no 12,5 GB | −0,24 |
| ECR conserva solo las 5 imágenes más recientes (regla de ciclo de vida de `publicar_imagen.sh`) | +0,09 |
| Se agregaron 7 alarmas de CloudWatch y 1 métrica personalizada (`SAAD/ErroresApi`) con aviso por SNS | +1,00 |
| Se agregó la pila de CI/CD (CodePipeline V2 y CodeBuild) | +2,76 |

### Precios unitarios verificados (15-11-2026)

| Servicio | Dimensión | API (US$) | Unidad |
|---|---|---|---|
| Fargate (Linux x86) | vCPU | 0,04048 | vCPU·h |
| Fargate (Linux x86) | Memoria | 0,004445 | GB·h |
| Application Load Balancer | Por hora | 0,0225 | h |
| Application Load Balancer | LCU usada | 0,008 | LCU·h |
| IPv4 pública | Por hora | 0,005 | IP·h |
| S3 Standard | Almacenamiento (0–50 TB) | 0,023 | GB-mes |
| ECR | Almacenamiento de imágenes | 0,10 | GB-mes |
| CloudWatch Logs | Ingestión / almacenamiento | 0,50 / 0,03 | GB |
| CloudWatch | Alarma estándar | **0,10** | alarma-mes |
| CloudWatch | Métrica personalizada (primeras 10.000) | **0,30** | métrica-mes |
| CodeBuild | `general1.small` Linux (`STANDARD_7_0`, `SMALL`) | **0,005** | minuto |
| CodePipeline V2 | Minuto de ejecución de acción | **0,002** | minuto |

En negrita, los precios nuevos respecto de la verificación del 12-10-2026. Servicios consultados:
`AmazonECS`, `AWSELB`, `AmazonVPC`, `AmazonS3`, `AmazonECR`, `AmazonCloudWatch`, `CodeBuild`,
`AWSCodePipeline`.

### Tabla de costos mensuales

| Servicio | Configuración | US$/mes |
|---|---|---|
| Fargate · tarea `saad-api` | 0,5 vCPU · 2 GB · 730 h | 21,27 |
| Application Load Balancer | 730 h · 1 LCU | 22,27 |
| IPv4 públicas | 3 IPs fijas (2 del ALB en dos zonas + 1 de la tarea) × 730 h | 10,95 |
| Amazon CloudFront | Capa gratuita permanente (<1 TB salida, <10 M solicitudes) | 0,00 |
| Amazon S3 Standard | ≈ 2 GB (datos ≈ 0,3 GB con versiones anteriores, sitio y assets de CDK) | 0,05 |
| Amazon ECR | 5 imágenes × ≈ 0,87 GB (cota superior, tamaño sin comprimir) | 0,44 |
| CloudWatch Logs | 1 GB ingerido + 1 GB almacenado (API y CodeBuild, retención de 2 semanas) | 0,53 |
| CloudWatch alarmas | 7 alarmas estándar | 0,70 |
| CloudWatch métrica personalizada | `SAAD/ErroresApi` (filtro de logs) | 0,30 |
| CodeBuild | ≈ 384 min/mes (supuesto de uso, ver cálculo 9) | 1,92 |
| CodePipeline V2 | ≈ 422 min de acción/mes (`saad-despliegue` y `saad-pr`) | 0,84 |
| SNS (correo de alarmas) | <1.000 notificaciones por correo | 0,00 |
| Parameter Store, CodeConnections, CloudFormation | Parámetros estándar, conexión y pilas sin costo | 0,00 |
| **Total** | | **59,27** |
| Aurora Serverless v2 (pausada, no desplegada) | 0,5 ACU · 60 h/mes + 1 GB | ≈3,70 |
| Aurora Serverless v2 (sin pausa, no desplegada) | 0,5 ACU · 730 h/mes + 1 GB | ≈43,90 |
| Tarea Fargate del pipeline (si se implementa C-42) | 4 vCPU · 16 GB · 4,35 h/mes + IP temporal | ≈1,05 |

Las alarmas, la métrica personalizada, CodeBuild y CodePipeline se cobran a precio de lista sin
descontar su capa gratuita (10 alarmas, 10 métricas, 100 min de CodeBuild `general1.small` y 100 min de
acción de CodePipeline V2 al mes). Así el total no depende de las condiciones de la cuenta; con la capa
gratuita las alarmas y la métrica quedan en US$0, CodeBuild baja a US$1,42 (284 min) y CodePipeline a
US$0,64 (322 min), y el total a ≈ US$57,57. CloudFront se mantiene en su capa
gratuita, como en la estimación original.

**Uso actual de CI:** desde el 17-11 la conexión `saad-github` está `AVAILABLE` y los pipelines se
ejecutan con cada push que los dispara (`saad-pr` en ramas distintas de `main`; `saad-despliegue` en `main`
cuando cambian `infra/aws/**` o `frontend/**`). En un mes sin ejecuciones, CodeBuild y CodePipeline cuestan
US$0 y el total es ≈ US$56,51; cada ejecución suma minutos según el detalle de abajo.

### Detalle de cálculos

1. **Fargate api:** (0,5 × $0,04048 × 730) + (2 × $0,004445 × 730) = $14,775 + $6,497 = **$21,27**
2. **ALB:** ($0,0225 × 730) + ($0,008 × 1 × 730) = $16,43 + $5,84 = **$22,27**
3. **IPv4:** 3 × $0,005 × 730 = **$10,95**. El ALB público ocupa una IP por zona (dos zonas) y la tarea
   usa IP pública porque la VPC no tiene NAT Gateway. Durante un redespliegue convive una segunda tarea
   unos minutos; su costo es despreciable.
4. **S3:** 2 × $0,023 = **$0,046 ≈ $0,05**. Lo que sube `subir_datos.sh` suma 252 MB de
   `data/processed/`, 35 MB de `reports/` y 11 MB de `data/raw/poblacion/`. El bucket es versionado, por
   lo que cada publicación conserva la versión anterior; 2 GB deja margen para varias publicaciones.
5. **ECR:** 4,4 × $0,10 = **$0,44**. Cota superior: ECR guarda las capas comprimidas, más livianas que
   los 866 MB que reporta Docker.
6. **CloudWatch Logs:** (1 × $0,50) + (1 × $0,03) = **$0,53**
7. **Alarmas:** 7 × $0,10 = **$0,70** (`api-sin-tareas-sanas`, `api-errores-5xx`, `alb-errores-5xx`,
   `api-memoria-alta`, `api-cpu-alta`, `api-errores-en-logs`, `cloudfront-errores-5xx`). Las métricas de
   ECS, ALB y CloudFront que usan son gratuitas.
8. **Métrica personalizada:** 1 × $0,30 = **$0,30**
9. **CodeBuild:** supuesto de 30 verificaciones (push a ramas, `saad-pr`) y 8 despliegues (push a
   `main` que toque `infra/aws/**` o `frontend/**`) al mes; `saad-verificar` ≈ 8 min y `saad-desplegar` ≈
   10 min. (30 × 8) + (8 × (8 + 10)) = 384 min × $0,005 = **$1,92**
10. **CodePipeline V2:** mismas ejecuciones, sumando ≈ 1 min de la acción de fuente.
    (30 × 9) + (8 × 19) = 422 min × $0,002 = **$0,84**
11. **Aurora pausada:** (0,5 × $0,12 × 60) + (1 × $0,10) = **$3,70**
12. **Aurora sin pausa:** (0,5 × $0,12 × 730) + (1 × $0,10) = **$43,90**

---

## Estimación to-be original (12-10-2026, antecedente)

Costeo del diseño to-be antes del despliegue. Todos los precios unitarios y totales coincidieron con la
AWS Pricing API a esa fecha. Incluía la tarea Fargate del pipeline programada con EventBridge, que no se
desplegó.

| Servicio | Configuración | US$/mes |
|---|---|---|
| Fargate · tarea api | 0,5 vCPU · 2 GB · 730 h | 21,27 |
| Fargate · tarea pipeline | 4 vCPU · 16 GB · 4,35 h/mes · 30 GiB efímeros extra | 1,03 |
| Application Load Balancer | 730 h · 1 LCU | 22,27 |
| IPv4 públicas | 3 IPs fijas × 730 h + 1 IP pipeline × 4,35 h | 10,97 |
| Amazon CloudFront | Capa gratuita (<1 TB salida, <10 M req.) | 0,00 |
| Amazon S3 Standard | 12,5 GB | 0,29 |
| Amazon ECR | 3,5 GB | 0,35 |
| CloudWatch Logs | 1 GB ingerido + 1 GB almacenado | 0,53 |
| EventBridge Scheduler | ~4 invocaciones/mes (capa gratuita) | 0,00 |
| AWS Certificate Manager | Certificados públicos (sin costo) | 0,00 |
| **Total base to-be** | | **56,71** |

Fargate pipeline: (4 × $0,04048 × 4,35) + (16 × $0,004445 × 4,35) + (30 × $0,000111 × 4,35) = $0,704 +
$0,309 + $0,014 = $1,03. Almacenamiento efímero sobre 20 GiB: $0,000111 por GiB·h.

### Evidencia del AWS Pricing Calculator

Enlace: <https://calculator.aws/#/estimate?id=1da7b171122c6261d3c64797db55485928d23129>

Archivos: [estimacion-costos-aws.pdf](estimacion-costos-aws.pdf) y [estimacion-costos-aws.csv](estimacion-costos-aws.csv) (exportados el 12-10-2026, us-east-1).

El calculador entrega **US$107,62/mes** con todos los servicios cargados. Corresponde al diseño to-be y
no incluye las alarmas ni la pila de CI del as-built.

| Servicio | Calculador (US$) | To-be (US$) | Causa de la diferencia |
|---|---|---|---|
| Fargate · api | 21,27 | 21,27 | Coincide |
| Fargate · pipeline | 4,97 | 1,03 | Calculador: 4 vCPU, **8 GB**, 5 h × 5/mes = 25 h, 30 GB efímeros. To-be: 16 GB, 4,35 h |
| ALB | 22,27 | 22,27 | Coincide |
| IPv4 públicas | no incluida | 10,97 | Faltó agregar Public IPv4 en el calculador |
| CloudFront | 10,50 | 0,00 | El calculador no aplicó la capa gratuita permanente |
| S3 / ECR | 0,29 / 0,35 | 0,29 / 0,35 | Coincide |
| CloudWatch | 1,26 | 0,53 | El calculador incluyó eventos OTEL móviles y logs entregados a S3, fuera del diseño |
| EventBridge / ACM | 0,00 | 0,00 | Coincide |
| Aurora (opcional) | 46,71 | 3,70 – 43,90 | Calculador con 1 ACU; el diseño usa 0,5 ACU |

Conciliación: 107,62 − 46,71 (Aurora) − 10,50 (CloudFront, capa gratuita) − 0,73 (CloudWatch fuera de diseño) − 3,94 (pipeline: 4,97 vs 1,03) + 10,97 (IPv4 faltante) = **56,71**.
