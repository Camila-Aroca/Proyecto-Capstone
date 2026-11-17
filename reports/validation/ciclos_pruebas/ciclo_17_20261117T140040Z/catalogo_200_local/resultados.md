# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 10 casos · **Estado:** FORMAL
- **Commit:** `cd631ecceaa10689f0bac66257b5fad5174db62c` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`
- **Nota:** Docker Compose local tras docker compose restart api, datos del commit 2dc0150
- **Entorno:** LOCAL (API local con Uvicorn en 127.0.0.1) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-17T14:01:30+00:00 / 2026-11-17T14:01:30+00:00
- **Resultado:** 10 aprobados · 0 fallidos · 0 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-039 | Año de egreso no publicado | 2026-11-17T14:01:30+00:00 | APROBADO | GET /hospitalizaciones-residentes/RM?ano=1900 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-039_20261117_local.json`](EVIDENCIA/SAAD-CP-039_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-043 | Calendario con intervalo invertido | 2026-11-17T14:01:30+00:00 | APROBADO | GET /calendario-eventos?desde=2026-12-31&hasta=2026-01-01 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-043_20261117_local.json`](EVIDENCIA/SAAD-CP-043_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-044 | Límite exacto del calendario | 2026-11-17T14:01:30+00:00 | APROBADO | GET /calendario-eventos?desde=2020-01-01&hasta=2032-01-10 → HTTP 200 (esperado 200); GET /calendario-eventos?desde=2020-01-01&hasta=2032-01-11 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-044_20261117_local.json`](EVIDENCIA/SAAD-CP-044_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-048 | Límite inferior de semanas | 2026-11-17T14:01:30+00:00 | APROBADO | GET /series/RM?semanas=1 → HTTP 200 (esperado 200); GET /series/RM?semanas=0 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-048_20261117_local.json`](EVIDENCIA/SAAD-CP-048_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-049 | Límite superior de semanas | 2026-11-17T14:01:30+00:00 | APROBADO | GET /series/RM?semanas=520 → HTTP 200 (esperado 200); GET /series/RM?semanas=521 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-049_20261117_local.json`](EVIDENCIA/SAAD-CP-049_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-050 | Serie desconocida | 2026-11-17T14:01:30+00:00 | APROBADO | GET /series/NO_EXISTE → HTTP 404 (esperado 404) | [`EVIDENCIA/SAAD-CP-050_20261117_local.json`](EVIDENCIA/SAAD-CP-050_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-052 | Nivel fuera del dominio | 2026-11-17T14:01:30+00:00 | APROBADO | GET /pronosticos?nivel=hospital → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-052_20261117_local.json`](EVIDENCIA/SAAD-CP-052_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-053 | Semana DEIS fuera de dominio | 2026-11-17T14:01:30+00:00 | APROBADO | GET /caracterizacion/urgencias/region/RM?semanas=2026-54 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-053_20261117_local.json`](EVIDENCIA/SAAD-CP-053_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-054 | Defunciones no identifica establecimiento | 2026-11-17T14:01:30+00:00 | APROBADO | GET /caracterizacion/suicidios/establecimiento/109102?semanas=2025-1 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-054_20261117_local.json`](EVIDENCIA/SAAD-CP-054_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |
| SAAD-CP-055 | Comuna ajena a RM | 2026-11-17T14:01:30+00:00 | APROBADO | GET /caracterizacion/urgencias/comuna/05101?semanas=2025-1 → HTTP 404 (esperado 404) | [`EVIDENCIA/SAAD-CP-055_20261117_local.json`](EVIDENCIA/SAAD-CP-055_20261117_local.json) | Sin defecto registrado | Docker Compose local tras docker compose restart api, datos del commit 2dc0150 |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
