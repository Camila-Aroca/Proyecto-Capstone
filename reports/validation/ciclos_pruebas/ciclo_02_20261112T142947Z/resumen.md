# Ciclo 2 de pruebas de SAAD (C-06)

- **Fecha (UTC):** 2026-11-12T14:29:47+00:00 · **Commit:** `3f1fd84`
- **Ejecutado con:** `scripts/qa_ciclo_pruebas.py --ciclo 2`
- **Registro de defectos:** [`../registro_defectos.md`](../registro_defectos.md)

## Resultado por entorno

| Verificación | Entorno | Estado | Detalle | Evidencia |
|---|---|---|---|---|
| Tests de Python (`pytest`) | Equipo | **APROBADO** | 858 aprobados, 0 fallidos, 8 omitidos, 29 deseleccionados (marcados `data_integration`) | [`pytest.xml`](pytest.xml) · [`pytest.log`](pytest.log) |
| Verificación del CI: síntesis CDK y cfn-lint | Equipo (contingencia) | **APROBADO** | 2 plantillas sintetizadas; cfn-lint sin errores, 4 advertencias de recursos internos de CDK | [`ci_local.log`](ci_local.log) |
| CI en CodePipeline (`saad-pr`, `saad-despliegue`) | AWS | **BLOCKED** | Conexión con GitHub en estado `PENDING`: falta que la dueña del repositorio la apruebe. Contingencia: la misma verificación se ejecuta en local (fila anterior). | — |
| Línea base (Docker Compose) | LOCAL | **FALLIDO** | 10 de 14 casos aprobados | [`local/20261112T143146Z/informe.md`](local/20261112T143146Z/informe.md) |
| E2E CloudFront → ALB → ECS, contrastada con local | AWS | **FALLIDO** | 20 aprobados, 4 fallidos, 7 no ejecutados | [`aws/20261112T143156Z/informe.md`](aws/20261112T143156Z/informe.md) |
| Contrato API/frontend | Código | **APROBADO** | 0 errores, 12 advertencias, 9 observaciones | [`comparacion_api_frontend.md`](../../contrato_api/comparacion_api_frontend.md) |

## Catálogo CP-SAAD-2026 (70 casos)

| Entorno | Aprobados | Fallidos | BLOCKED | No ejecutados | No aplica |
|---|---|---|---|---|---|
| LOCAL | 11 | 3 | 12 | 26 | 18 |
| AWS | 20 | 4 | 12 | 33 | 1 |

- **No ejecutado:** prueba manual de interfaz u operación que este ciclo no automatiza, o caso que no aplica al diseño desplegado (el motivo está en la nota). No cuenta como aprobado.
- **BLOCKED:** no se puede ejecutar por un defecto abierto; la nota indica cuál.
- **—:** el caso no aplica a ese entorno (p. ej. CloudFront o ECS en local).

| Caso | Prueba | LOCAL | AWS | Nota |
|---|---|---|---|---|
| CP-SAAD-001 | Portal publicado mediante HTTPS y CloudFront | — | APROBADO |  |
| CP-SAAD-002 | Rutas hash al refrescar y al compartir | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-003 | Enrutamiento CloudFront /api/* al ALB | — | APROBADO |  |
| CP-SAAD-004 | Bucket del frontend privado y distribución autorizada | — | APROBADO |  |
| CP-SAAD-005 | Salud de targets ALB y tareas ECS | — | APROBADO |  |
| CP-SAAD-006 | Lectura de outputs en API después de arranque Fargate | — | APROBADO | Cubierto por CP-SAAD-020. |
| CP-SAAD-007 | Imagen ECR identificable y versión de despliegue trazable | — | APROBADO |  |
| CP-SAAD-008 | Registro de solicitudes y errores en CloudWatch | — | APROBADO |  |
| CP-SAAD-009 | Inventario S3 de RAW, processed, reports y manifest | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-010 | Permisos del rol de tarea pipeline | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-011 | Ejecución manual controlada del refresh semanal | — | NO EJECUTADO | No aplica en Fargate: el pipeline corre en el equipo y se publica con subir_datos.sh (cambio de alcance de C-42). |
| CP-SAAD-012 | EventBridge Scheduler dispara tarea esperada | — | NO EJECUTADO | No aplica: no hay tarea programada (pipeline local). |
| CP-SAAD-013 | Falla de etapa no promueve artefactos incompletos | — | NO EJECUTADO | No aplica en AWS: el pipeline no corre en Fargate. |
| CP-SAAD-014 | Nuevos outputs visibles tras redespliegue de API | — | NO EJECUTADO | Requiere publicar datos nuevos con subir_datos.sh; no se hizo en esta corrida. |
| CP-SAAD-015 | Estado temporal 503 y Retry-After durante inicialización | — | NO EJECUTADO | No observable desde fuera: el despliegue mantiene la tarea anterior hasta que la nueva está sana. Cubierto por pruebas unitarias de la API (tests/test_api.py). |
| CP-SAAD-016 | Insuficiencia de almacenamiento efímero del pipeline | — | NO EJECUTADO | No aplica: el pipeline no corre en Fargate. |
| CP-SAAD-017 | GET /api/v1/salud reporta estados reales | APROBADO | APROBADO |  |
| CP-SAAD-018 | GET /api/v1/meta: trazabilidad y advertencias | APROBADO | APROBADO |  |
| CP-SAAD-019 | GET /api/v1/territorios conserva 52 comunas y región | APROBADO | APROBADO |  |
| CP-SAAD-020 | GET /api/v1/series/{series_id} para RM | APROBADO | APROBADO |  |
| CP-SAAD-021 | Serie inexistente y parámetros fuera de rango | APROBADO | APROBADO |  |
| CP-SAAD-022 | GET /api/v1/pronosticos filtrado por nivel y horizonte | APROBADO | APROBADO |  |
| CP-SAAD-023 | GET /api/v1/resumen-comunal consistente con series | APROBADO | APROBADO |  |
| CP-SAAD-024 | GET /api/v1/geo/comunas devuelve GeoJSON válido | APROBADO | APROBADO |  |
| CP-SAAD-025 | GET /api/v1/camas-psiquiatria/{series_id} | FALLIDO | FALLIDO | HTTP 404 (se esperaba 200); detalle de la API: Falta la dotacion de camas: ejecute el stage `build_dim_camas_psiquiatria_hospital_rm` del pipeline. |
| CP-SAAD-026 | GET /api/v1/calendario-eventos | APROBADO | APROBADO |  |
| CP-SAAD-027 | Caracterización: combinaciones admitidas y rechazadas | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-028 | Landing SAAD y alcance comunicado | APROBADO | — |  |
| CP-SAAD-029 | Navegar landing → tablero → establecimientos | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-030 | Gráfico regional: historia, pronóstico e intervalo | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-031 | Cambio de comuna actualiza toda la vista | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-032 | Comuna sin pronóstico: no representarla como cero | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-033 | Mapa de concentración y cambio de métrica | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-034 | Tooltip y tabla comunal sincronizados | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-035 | Ventanas de semanas y fechas de corte | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-036 | Carga, error y recuperación visible | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-037 | Listado de establecimientos y métricas disponibles | FALLIDO | FALLIDO | HTTP 503 (se esperaba 200); detalle de la API: data/processed/marts/mart_urgencias_establecimiento_weekly.parquet; HTTP 503 (se esperaba 200); detalle de la API: data/processed/marts/mart_urgencias_es |
| CP-SAAD-038 | Búsqueda, filtro por tipo y por comuna | BLOCKED | BLOCKED | DEF-02: sin datos de establecimientos (mart semanal y pronóstico no publicados) |
| CP-SAAD-039 | Atenciones SM ID36 por establecimiento | BLOCKED | BLOCKED | DEF-02: sin datos de establecimientos (mart semanal y pronóstico no publicados) |
| CP-SAAD-040 | Hospitalizaciones ID42 solo en hospitales | BLOCKED | BLOCKED | DEF-02: sin datos de establecimientos (mart semanal y pronóstico no publicados) |
| CP-SAAD-041 | Establecimiento sin pronóstico o fuera de rango | BLOCKED | BLOCKED | DEF-02: sin datos de establecimientos (mart semanal y pronóstico no publicados) |
| CP-SAAD-042 | Ocupación mensual REM-20 en hospitales | BLOCKED | BLOCKED | DEF-01: sin dotación ni ocupación de camas de psiquiatría |
| CP-SAAD-043 | Niveles de presión, saturación y sobrecapacidad | BLOCKED | BLOCKED | DEF-01: sin dotación ni ocupación de camas de psiquiatría |
| CP-SAAD-044 | Dotación anual vs disponibilidad mensual vs capacidad | BLOCKED | BLOCKED | DEF-01: sin dotación ni ocupación de camas de psiquiatría |
| CP-SAAD-045 | Propuesta de camas como estimación condicionada | BLOCKED | BLOCKED | DEF-01: sin dotación ni ocupación de camas de psiquiatría |
| CP-SAAD-046 | Caracterización por sexo y edad del flujo | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-047 | Suicidios: pronóstico y tasa por residencia | FALLIDO | FALLIDO | HTTP 503 (se esperaba 200); detalle de la API: El pronóstico de suicidios está desactualizado (falta la entrada 'mart_suicidios_comuna_weekly' (data/processed/marts/mart_suicidios_comuna_weekly.parque |
| CP-SAAD-048 | Calendario y marcas del gráfico de suicidios | BLOCKED | BLOCKED | DEF-03: sin mart ni pronóstico de suicidios |
| CP-SAAD-049 | Pronóstico suicidios desactualizado o ausente | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-050 | Alineación temporal entre suicidios y urgencias | BLOCKED | BLOCKED | DEF-03: sin mart ni pronóstico de suicidios |
| CP-SAAD-051 | Mensajes de prevención e interpretación responsable | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-052 | Semanas con recuento muy bajo no parecen picos artificiales | BLOCKED | BLOCKED | DEF-03: sin mart ni pronóstico de suicidios |
| CP-SAAD-053 | Horizontes ofertados corresponden a modelo y meta | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-054 | Orden lógico de intervalos de predicción | APROBADO | APROBADO | Cubierto por CP-SAAD-022. |
| CP-SAAD-055 | Cobertura holdout declarada sin engaño | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-056 | Semana parcial no sustituye semana cerrada | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-057 | Tasas y denominadores territoriales | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-058 | Trazabilidad de datos DEIS y fecha del modelo | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-059 | Diferenciar hospitalizaciones ID42 de ocupación REM-20 | BLOCKED | BLOCKED | DEF-01: sin dotación ni ocupación de camas de psiquiatría |
| CP-SAAD-060 | Cifrado TLS y respuesta HTTP→HTTPS | — | APROBADO |  |
| CP-SAAD-061 | Acceso público de solo lectura sin autenticar (según MVP) | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-062 | IAM mínimo en servicio API y bucket de datos | — | APROBADO |  |
| CP-SAAD-063 | Ausencia de secretos en frontend, logs y configuración | — | APROBADO |  |
| CP-SAAD-064 | Cache CloudFront tras nueva versión | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-065 | Recuperación después de reemplazo de tarea ECS | — | NO EJECUTADO | Se ejecuta con --reinicio porque reemplaza la tarea en servicio. |
| CP-SAAD-066 | Error HTTP/timeout no deja frontend con datos cruzados | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-067 | Navegación por teclado y foco visible | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-068 | Diseño y lectura en móvil y escritorio | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-069 | Presupuesto, etiquetas y costo del ambiente de evaluación | NO EJECUTADO | NO EJECUTADO | Prueba manual de interfaz o de operación; no automatizada en este ciclo. |
| CP-SAAD-070 | Ciclo completo AWS y comparación con baseline local | — | FALLIDO | Ciclo completo ejecutado y comparado con local; 4 casos fallan en ambos entornos (ver casos fallidos). |

## Casos fallidos (para el registro de defectos)

- **CP-SAAD-025 · GET /api/v1/camas-psiquiatria/{series_id}** (LOCAL FALLIDO, AWS FALLIDO): HTTP 404 (se esperaba 200); detalle de la API: Falta la dotacion de camas: ejecute el stage `build_dim_camas_psiquiatria_hospital_rm` del pipeline.
- **CP-SAAD-037 · Listado de establecimientos y métricas disponibles** (LOCAL FALLIDO, AWS FALLIDO): HTTP 503 (se esperaba 200); detalle de la API: data/processed/marts/mart_urgencias_establecimiento_weekly.parquet; HTTP 503 (se esperaba 200); detalle de la API: data/processed/marts/mart_urgencias_establecimiento_weekly
- **CP-SAAD-047 · Suicidios: pronóstico y tasa por residencia** (LOCAL FALLIDO, AWS FALLIDO): HTTP 503 (se esperaba 200); detalle de la API: El pronóstico de suicidios está desactualizado (falta la entrada 'mart_suicidios_comuna_weekly' (data/processed/marts/mart_suicidios_comuna_weekly.parquet)): ejecute el stag
- **CP-SAAD-070 · Ciclo completo AWS y comparación con baseline local** (LOCAL —, AWS FALLIDO): Ciclo completo ejecutado y comparado con local; 4 casos fallan en ambos entornos (ver casos fallidos).
