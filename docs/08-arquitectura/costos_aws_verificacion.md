# Verificación de costos AWS — SAAD to-be

**Región:** us-east-1  
**Fuente:** AWS Pricing API (precios de lista)  
**Fecha de verificación:** 12-10-2026  
**Documento origen:** ATB-SAAD-2026, sección 4

> Todos los precios unitarios y los totales calculados del documento coinciden con la AWS Pricing API a la fecha de verificación.

---

## Precios unitarios verificados

| Servicio | Dimensión | Doc (US$) | API (US$) | Unidad |
|---|---|---|---|---|
| Fargate (Linux x86) | vCPU | 0,04048 | **0,04048** ✓ | vCPU·h |
| Fargate (Linux x86) | Memoria | 0,004445 | **0,004445** ✓ | GB·h |
| Fargate | Almacenamiento efímero (>20 GiB) | 0,000111 | **0,000111** ✓ | GiB·h |
| Application Load Balancer | Por hora | 0,0225 | **0,0225** ✓ | h |
| Application Load Balancer | LCU usada | 0,008 | **0,008** ✓ | LCU·h |
| IPv4 pública (en uso o inactiva) | Por hora | 0,005 | **0,005** ✓ | IP·h |
| S3 Standard | Almacenamiento (0–50 TB) | 0,023 | **0,023** ✓ | GB-mes |
| ECR | Almacenamiento de imágenes | 0,10 | **0,10** ✓ | GB-mes |
| CloudWatch Logs | Ingestión (Standard class) | 0,50 | **0,50** ✓ | GB ingerido |
| CloudWatch Logs | Almacenamiento | — | **0,03** ✓ | GB-mes |
| Aurora Serverless v2 (PostgreSQL) | ACU | 0,12 | **0,12** ✓ | ACU·h |

Servicios consultados: `AmazonECS`, `AWSELB`, `AmazonVPC`, `AmazonS3`, `AmazonECR`, `AmazonCloudWatch`, `AmazonRDS`.

---

## Tabla de costos mensuales

| Servicio | Configuración | US$/mes (doc.) | Verificado |
|---|---|---|---|
| Fargate · tarea api | 0,5 vCPU · 2 GB · 730 h | 21,27 | ✓ |
| Fargate · tarea pipeline | 4 vCPU · 16 GB · 4,35 h/mes · 30 GiB efímeros extra | 1,03 | ✓ |
| Application Load Balancer | 730 h · 1 LCU | 22,27 | ✓ |
| IPv4 públicas | 3 IPs fijas × 730 h + 1 IP pipeline × 4,35 h | 10,97 | ✓ |
| Amazon CloudFront | Capa gratuita (<1 TB salida, <10 M req.) | 0,00 | ✓ |
| Amazon S3 Standard | 12,5 GB | 0,29 | ✓ |
| Amazon ECR | 3,5 GB | 0,35 | ✓ |
| CloudWatch Logs | 1 GB ingerido + 1 GB almacenado | 0,53 | ✓ |
| EventBridge Scheduler | ~4 invocaciones/mes (capa gratuita) | 0,00 | ✓ |
| AWS Certificate Manager | Certificados públicos (sin costo) | 0,00 | ✓ |
| **Total base** | | **56,71** | **✓** |
| Aurora Serverless v2 (pausada, opcional) | 0,5 ACU · 60 h/mes + 1 GB | ≈3,70 | ✓ |
| Aurora Serverless v2 (sin pausa, opcional) | 0,5 ACU · 730 h/mes + 1 GB | ≈43,90 | ✓ |

---

## Detalle de cálculos

1. **Fargate api:** (0,5 × $0,04048 × 730) + (2 × $0,004445 × 730) = $14,775 + $6,497 = **$21,27**
2. **Fargate pipeline:** (4 × $0,04048 × 4,35) + (16 × $0,004445 × 4,35) + (30 × $0,000111 × 4,35) = $0,704 + $0,309 + $0,014 = **$1,03**
3. **ALB:** ($0,0225 × 730) + ($0,008 × 1 × 730) = $16,43 + $5,84 = **$22,27**
4. **IPv4:** (3 × $0,005 × 730) + (1 × $0,005 × 4,35) = $10,95 + $0,022 = **$10,97**
5. **S3:** 12,5 × $0,023 = **$0,2875 ≈ $0,29**
6. **ECR:** 3,5 × $0,10 = **$0,35**
7. **CloudWatch:** (1 × $0,50) + (1 × $0,03) = **$0,53**  
   El documento cita $0,50 como precio de ingestión; el $0,03 de almacenamiento (API confirmado) explica el total de $0,53.
8. **Aurora pausada:** (0,5 × $0,12 × 60) + (1 × $0,10) = $3,60 + $0,10 = **$3,70**
9. **Aurora sin pausa:** (0,5 × $0,12 × 730) + (1 × $0,10) = $43,80 + $0,10 = **$43,90**

---

## Evidencia del AWS Pricing Calculator

Enlace: <https://calculator.aws/#/estimate?id=1da7b171122c6261d3c64797db55485928d23129>

Archivos: [estimacion-costos-aws.pdf](estimacion-costos-aws.pdf) y [estimacion-costos-aws.csv](estimacion-costos-aws.csv) (exportados el 12-10-2026, us-east-1).

El calculador entrega **US$107,62/mes** con todos los servicios cargados. No es comparable directamente con el total base de US$56,71 por las diferencias de configuración de la tabla siguiente. Las tareas Fargate api, el ALB, S3 y ECR coinciden exactamente con el documento.

| Servicio | Calculador (US$) | Documento (US$) | Causa de la diferencia |
|---|---|---|---|
| Fargate · api | 21,27 | 21,27 | Coincide (1 tarea/día × 24 h; no 730 h por tarea) |
| Fargate · pipeline | 4,97 | 1,03 | Calculador: 4 vCPU, **8 GB**, 5 h × 5/mes = 25 h, 30 GB efímeros. Documento: 16 GB, 4,35 h |
| ALB | 22,27 | 22,27 | Coincide |
| IPv4 públicas | no incluida | 10,97 | Faltó agregar Public IPv4 en el calculador |
| CloudFront | 10,50 | 0,00 | El calculador no aplicó la capa gratuita permanente; se cargaron 100 GB de salida y 100 GB hacia el origen |
| S3 / ECR | 0,29 / 0,35 | 0,29 / 0,35 | Coincide |
| CloudWatch | 1,26 | 0,53 | El calculador incluyó eventos OTEL móviles y logs entregados a S3, fuera del diseño |
| EventBridge / ACM | 0,00 | 0,00 | Coincide |
| Aurora (opcional) | 46,71 | 3,70 – 43,90 | Calculador con 1 ACU; el diseño usa 0,5 ACU. Excluida del total base |

Conciliación: 107,62 − 46,71 (Aurora) − 10,50 (CloudFront, capa gratuita) − 0,73 (CloudWatch fuera de diseño) − 3,94 (pipeline: 4,97 vs 1,03) + 10,97 (IPv4 faltante) = **56,71**.

Pendiente de decisión: dimensionamiento de la tarea pipeline (4 vCPU/8 GB/25 h al mes en el calculador vs 16 GB/4,35 h en el documento). Con la configuración del calculador el total base sería ≈ US$60,65.
