# Presupuesto del proyecto — SAAD

**Estado:** estimación referencial, pendiente de validar con el equipo y la docente.
**Moneda:** CLP. Los costos cloud se expresan en USD y se convierten con un tipo de cambio referencial de **US$1 = $950 CLP**.
**Período:** semestre de 18 semanas (Definición del Proyecto APT, factibilidad).

> Desembolso real del equipo ≈ $0 durante el desarrollo; las cifras de RRHH son valores referenciales para dimensionar el costo del desarrollo. No hay presupuesto de infraestructura asignado (RO-02).

---

## Supuestos

| Supuesto | Valor | Fuente / criterio |
|---|---|---|
| Duración | 18 semanas | Definición del Proyecto APT |
| Integrantes | 4 | RO-01 (Especificación de Requisitos No Funcionales) |
| Dedicación semanal | 10 h por persona | Estimación; RO-01 solo indica "dedicación parcial". **Pendiente de validar** (ítem 8 de la Ficha) |
| Modalidad | Sin contrato | Sin relación laboral: no hay cotizaciones de empleador, vacaciones ni indemnizaciones |
| Valor hora | $3.500 CLP, igual para todos los roles | Piso de mercado: ingreso mínimo por hora (≈ $3.075) redondeado. Todos los integrantes son estudiantes sin experiencia profesional acreditada |
| Meses con nube activa | 2 | Despliegue to-be para pruebas y validación (S13–S16) y presentación final (S17–S18) |
| Contingencia | 5 % | Límite inferior del rango estándar (5–10 %), coherente con un alcance acotado |

### Referencias del valor hora (Chile, 2026)

| Referencia | Valor | Fuente |
|---|---|---|
| Ingreso mínimo mensual (desde 01-05-2026) | $553.553 | Ley N° 21.830, Diario Oficial 22-06-2026 |
| Jornada ordinaria (desde 26-04-2026) | 42 h semanales | Ley N° 21.561 (40 horas) |
| Ingreso mínimo por hora | $553.553 ÷ 30 × 28 ÷ (42 × 4) ≈ $3.075 | Cálculo de valor hora usado en Chile |
| Practicante de informática, sector público | $234.633 mensuales | Convocatoria Comisión Ingresa |
| Desarrollador junior, jornada completa | desde $1.100.000 mensuales (≈ $6.500/h) | Referencias de mercado 2026 |

El valor elegido ($3.500/h) queda apenas sobre el mínimo legal y muy por debajo de un sueldo junior, para que el proyecto se dimensione barato sin pagar bajo el piso legal por hora.

Software, licencias, datos y hardware no se presupuestan: todo el software es open source (Python, pandas, PostGIS, FastAPI, React, Leaflet, PlantUML, Git), las fuentes son públicas (DEIS, INE, MDS, OSM, GTFS) y el cómputo de producción corre en la nube.

---

## 1. Recursos humanos

Fórmula: horas/semana × semanas × valor hora.

| Ítem | Cantidad | Costo unitario | Total | Tipo |
|---|---|---|---|---|
| PM / Scrum Master | 10 h × 18 sem = 180 h | $3.500 / h | $630.000 | Único |
| Data Engineer | 180 h | $3.500 / h | $630.000 | Único |
| Data Scientist | 180 h | $3.500 / h | $630.000 | Único |
| Full Stack / Geoespacial | 180 h | $3.500 / h | $630.000 | Único |
| **Subtotal RRHH** | 720 h | | **$2.520.000** | |

Por integrante: $630.000 en el semestre (≈ $153.000 al mes en 4,1 meses).

---

## 2. Infraestructura cloud (OPEX)

Detalle y verificación en [costos_aws_verificacion.md](../08-arquitectura/costos_aws_verificacion.md) y en la sección 4 de la arquitectura to-be.

| Ítem | Cantidad | Costo unitario | Total | Tipo |
|---|---|---|---|---|
| AWS, total base (Fargate, ALB, IPv4, S3, ECR, CloudWatch; CloudFront en capa gratuita) | 2 meses | US$56,71 / mes (≈ $53.875) | US$113,42 (≈ $107.750) | Mensual |
| **Subtotal cloud** | | | **≈ $107.750** | |

Escenarios alternativos (no incluidos en el total):

| Escenario | US$/mes | CLP/mes |
|---|---|---|
| Base + Aurora Serverless v2 pausada | ≈ 60,41 | ≈ $57.390 |
| Base + Aurora Serverless v2 sin pausa | ≈ 100,61 | ≈ $95.580 |
| Total del AWS Pricing Calculator sin conciliar | 107,62 | ≈ $102.240 |

---

## 3. Contingencia

| Ítem | Base | % | Total | Tipo |
|---|---|---|---|---|
| Imprevistos (re-trabajo, variación de precios cloud, tipo de cambio) | $2.627.750 | 5 % | $131.388 | Único |

---

## Resumen

| Categoría | Tipo | Total CLP |
|---|---|---|
| Recursos humanos | Único (CAPEX) | $2.520.000 |
| Infraestructura cloud | Mensual (OPEX) × 2 meses | $107.750 |
| **Subtotal** | | **$2.627.750** |
| Contingencia (5 %) | | $131.388 |
| **Total valorizado del proyecto** | | **$2.759.138** |
| Desembolso real del equipo | | ≈ $0 (cloud solo si se aprueba el despliegue to-be: ≈ $107.750) |

Operación posterior al proyecto: ≈ US$57 al mes (≈ $53.875 CLP) mientras la plataforma siga desplegada.

---

## Pendientes

- Validar la dedicación semanal real por integrante y ajustar la tabla de RRHH.
- Confirmar con la docente si el presupuesto es valorizado (incluye horas del equipo) o solo de desembolso real.
- Confirmar si tiene plantilla propia o se integra como sección de la Ficha.
