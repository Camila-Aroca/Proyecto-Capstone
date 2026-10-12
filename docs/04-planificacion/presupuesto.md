# Presupuesto del proyecto — SAAD

**Estado:** estimación referencial (educated guess), pendiente de validar con el equipo y la docente.
**Moneda:** CLP. Los costos cloud se expresan en USD y se convierten con un tipo de cambio referencial de **US$1 = $950 CLP**.
**Período:** semestre de 18 semanas (Definición del Proyecto APT, factibilidad).

> Desembolso real del equipo ≈ $0 durante el desarrollo; las cifras de RRHH son valores de mercado referenciales para dimensionar el costo real del desarrollo.

---

## Supuestos

| Supuesto | Valor | Fuente / criterio |
|---|---|---|
| Duración | 18 semanas | Definición del Proyecto APT |
| Integrantes | 4 | Equipo APT |
| Dedicación semanal | 10 h por persona | Estimación: carga de una asignatura de titulación en paralelo a otras obligaciones; **pendiente de validar** (ítem 8 de la Ficha) |
| Valor hora | $5.500 – $6.000 CLP | Rango referencial Chile 2026 para perfil junior ($4.000 – $7.000 CLP/h) |
| Meses con nube activa | 2 | Despliegue to-be para pruebas y validación (S13–S16) y presentación final (S17–S18) |
| Contingencia | 10 % | Sobre el subtotal |

Software, licencias, datos y hardware no se presupuestan: todo el software es open source (Python, pandas, PostGIS, FastAPI, React, Leaflet, PlantUML, Git), las fuentes son públicas (DEIS, INE, MDS, OSM, GTFS) y el cómputo de producción corre en la nube.

---

## 1. Recursos humanos

Fórmula: horas/semana × semanas × valor hora.

| Ítem | Cantidad | Costo unitario | Total | Tipo |
|---|---|---|---|---|
| PM / Scrum Master | 10 h × 18 sem = 180 h | $6.000 / h | $1.080.000 | Único |
| Data Engineer | 180 h | $5.500 / h | $990.000 | Único |
| Data Scientist | 180 h | $6.000 / h | $1.080.000 | Único |
| Full Stack / Geoespacial | 180 h | $5.500 / h | $990.000 | Único |
| **Subtotal RRHH** | 720 h | | **$4.140.000** | |

Referencia mensual equivalente: ~$250.000 CLP por persona al mes (18 semanas ≈ 4,1 meses), consistente con ~1/4 de jornada (10 de 45 h) de un sueldo junior de jornada completa ($700.000 – $1.200.000 CLP).

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
| Imprevistos (re-trabajo, variación de precios cloud, tipo de cambio) | $4.247.750 | 10 % | $424.775 | Único |

---

## Resumen

| Categoría | Tipo | Total CLP |
|---|---|---|
| Recursos humanos | Único (CAPEX) | $4.140.000 |
| Infraestructura cloud | Mensual (OPEX) × 2 meses | $107.750 |
| **Subtotal** | | **$4.247.750** |
| Contingencia (10 %) | | $424.775 |
| **Total valorizado del proyecto** | | **$4.672.525** |
| Desembolso real del equipo | | ≈ $0 (cloud solo si se aprueba el despliegue to-be: ≈ $107.750) |

Operación posterior al proyecto: ≈ US$57 al mes (≈ $53.875 CLP) mientras la plataforma siga desplegada.

---

## Pendientes

- Validar la dedicación semanal real por integrante y ajustar la tabla de RRHH.
- Confirmar con la docente si el presupuesto es valorizado (incluye horas del equipo) o solo de desembolso real.
- Confirmar si tiene plantilla propia o se integra como sección de la Ficha.
