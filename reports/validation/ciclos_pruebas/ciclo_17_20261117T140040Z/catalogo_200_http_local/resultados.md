# Ciclo 17 · Catálogo SAAD-CP v2.1 (200 casos): Catalina Rodríguez

- **Ejecutor real:** Catalina Rodríguez · **Alcance:** 200 casos · **Estado:** FORMAL
- **Commit:** `cd631ecceaa10689f0bac66257b5fad5174db62c` · árbol versionado limpio: no
- **Archivos sin rastrear al ejecutar:** `.gitattributes`, `docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx`, `docs/05-entregas/Fase_2_3/Pruebas/Registro_Principal_Pruebas_SAAD.xlsx`, `docs/05-entregas/informe_avance_apt_catalina.md`, `docs/05-entregas/reflexion_monitoreo_apt.md`, `docs/07-diagramas/.$despliegue_aws_as_built.drawio.bkp`, `docs/11-manual-usuario/`, `package-lock.json`, `reports/validation/ciclos_pruebas/ciclo_02_20261112T142133Z/`, `reports/validation/ciclos_pruebas/ciclo_03_20261112T152058Z/`, `reports/validation/registro_principal_pruebas.csv`, `reports/validation/registro_principal_pruebas.md`, `scripts/qa_registro_principal.py`, `scripts/qa_ui_campana.mjs`, `scripts/qa_ui_cdp.mjs`, `tests/test_qa_registro_principal.py`
- **Nota:** Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16.
- **Entorno:** LOCAL (API local con Uvicorn en 127.0.0.1) · Python 3.12.3 · pytest 9.1.1
- **Inicio / fin (UTC):** 2026-11-17T15:05:21+00:00 / 2026-11-17T15:05:21+00:00
- **Resultado:** 10 aprobados · 0 fallidos · 190 no ejecutados

Evidencia por caso en `EVIDENCIA/` (JUnit en los casos de pytest; petición y respuesta en los HTTP), con su SHA256 y el hash del input (en `resultados.json`). Defectos: se registran en `../../registro_defectos.md`; el resumen del ciclo lo consolida quien lo coordina.

| ID | Prueba | Fecha/hora (UTC) | Estado | Resultado real | Evidencia | Defecto | Observaciones |
|---|---|---|---|---|---|---|---|
| SAAD-CP-001 | Abrir landing sin hash | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-002 | Enlace comunal compartido | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-003 | Enlace a hospital por código | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-004 | Establecimiento inválido en acceso directo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-005 | Retroceso entre vistas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-006 | Cambiar comuna sin inflar historial | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-007 | Foco al cambiar de vista | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-008 | Acceso al alcance del producto | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-009 | Comprender propósito predictivo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-010 | Preferencia de color del sistema | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-011 | Serie de región predeterminada | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-012 | Ventana histórica acotada | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-013 | Seleccionar comuna desde tabla | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-014 | Seleccionar polígono comunal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-015 | Orden numérico y nulos al final | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-016 | Ayuda de tasa semanal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-017 | Temporalidad de pobreza y oferta | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-018 | Comuna sin serie modelable | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-019 | Clasificación y ruido semanal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-020 | Fallo aislado de calendario | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-021 | Respuesta tardía de comuna previa | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-022 | Pasar de oferta a establecimientos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-023 | Filtro de comuna en establecimientos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-024 | Orden de nivel de colapso | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-025 | Cambiar de atenciones a hospitalizaciones | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-026 | Aviso de pronóstico desactualizado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-027 | Motivo por ausencia de pronóstico | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-028 | Seleccionar área de psiquiatría | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-029 | Separar flujo semanal y stock mensual | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-030 | Propuesta anual desde respuesta | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-031 | Subtotal parcial por área sin soporte | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-032 | Volver a territorio del hospital | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-033 | Perfil regional anual | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-034 | Año de desgloses | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-035 | Tasa nula de 2020 | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-036 | Suma de categorías por dimensión | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-037 | Explicar residencia frente a atención | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-038 | Contraste regional ausente en comuna | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-039 | Año de egreso no publicado | 2026-11-17T15:05:21+00:00 | APROBADO | GET /hospitalizaciones-residentes/RM?ano=1900 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-039_20261117_local.json`](EVIDENCIA/SAAD-CP-039_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-040 | Ausencia de contraste opcional | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-041 | Contexto de suicidios independiente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-042 | Alternar marcas de contexto | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-043 | Calendario con intervalo invertido | 2026-11-17T15:05:21+00:00 | APROBADO | GET /calendario-eventos?desde=2026-12-31&hasta=2026-01-01 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-043_20261117_local.json`](EVIDENCIA/SAAD-CP-043_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-044 | Límite exacto del calendario | 2026-11-17T15:05:21+00:00 | APROBADO | GET /calendario-eventos?desde=2020-01-01&hasta=2032-01-10 → HTTP 200 (esperado 200); GET /calendario-eventos?desde=2020-01-01&hasta=2032-01-11 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-044_20261117_local.json`](EVIDENCIA/SAAD-CP-044_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-045 | Fallo aislado de suicidios | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-046 | Interpretar bandas y festividades | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-047 | Disponibilidad con estado de negocio | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-048 | Límite inferior de semanas | 2026-11-17T15:05:21+00:00 | APROBADO | GET /series/RM?semanas=1 → HTTP 200 (esperado 200); GET /series/RM?semanas=0 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-048_20261117_local.json`](EVIDENCIA/SAAD-CP-048_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-049 | Límite superior de semanas | 2026-11-17T15:05:21+00:00 | APROBADO | GET /series/RM?semanas=520 → HTTP 200 (esperado 200); GET /series/RM?semanas=521 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-049_20261117_local.json`](EVIDENCIA/SAAD-CP-049_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-050 | Serie desconocida | 2026-11-17T15:05:21+00:00 | APROBADO | GET /series/NO_EXISTE → HTTP 404 (esperado 404) | [`EVIDENCIA/SAAD-CP-050_20261117_local.json`](EVIDENCIA/SAAD-CP-050_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-051 | Filtros de pronóstico | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-052 | Nivel fuera del dominio | 2026-11-17T15:05:21+00:00 | APROBADO | GET /pronosticos?nivel=hospital → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-052_20261117_local.json`](EVIDENCIA/SAAD-CP-052_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-053 | Semana DEIS fuera de dominio | 2026-11-17T15:05:21+00:00 | APROBADO | GET /caracterizacion/urgencias/region/RM?semanas=2026-54 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-053_20261117_local.json`](EVIDENCIA/SAAD-CP-053_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-054 | Defunciones no identifica establecimiento | 2026-11-17T15:05:21+00:00 | APROBADO | GET /caracterizacion/suicidios/establecimiento/109102?semanas=2025-1 → HTTP 422 (esperado 422) | [`EVIDENCIA/SAAD-CP-054_20261117_local.json`](EVIDENCIA/SAAD-CP-054_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-055 | Comuna ajena a RM | 2026-11-17T15:05:21+00:00 | APROBADO | GET /caracterizacion/urgencias/comuna/05101?semanas=2025-1 → HTTP 404 (esperado 404) | [`EVIDENCIA/SAAD-CP-055_20261117_local.json`](EVIDENCIA/SAAD-CP-055_20261117_local.json) | Sin defecto registrado | Ciclo final: consultas HTTP a API LOCAL (S45, post-DEF-16). Retest DEF-15/16. |
| SAAD-CP-056 | Contrato y cliente frontend | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-057 | HTTPS de CloudFront | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-058 | Ruteo de API por mismo origen | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-059 | Targets y tareas sanas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-060 | Digest de imagen en servicio | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-061 | Privacidad de bucket del sitio | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-062 | Datos descargados al arranque | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-063 | Retención y consulta de logs | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-064 | Alarmas sin provocar incidentes | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-065 | Mínimo privilegio del rol API | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-066 | Estado de conexión CI | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-067 | Revisión de DEF 11 en publicación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-068 | Paridad local y AWS por snapshot | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-069 | Recorrido solo con teclado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-070 | Lectura de gráficos y tablas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-071 | Viewport móvil estrecho | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-072 | Zoom al doscientos por ciento | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-073 | Contraste de texto y ayudas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-074 | Motores de navegador | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-075 | Medición moderada de latencia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-076 | Recuperación tras desconexión del cliente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-077 | API pública sin operaciones administrativas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-078 | Interpretación de propuesta de camas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-079 | Sesión guiada por riesgo territorial | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-080 | Recorrido de planificación completo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-081 | Grano semanal y jerarquía causal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-082 | Conciliación mensual contra semanal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-083 | Denominador anual constante entre meses | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-084 | Rechazo de jerarquía ID36 inconsistente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-085 | Causa ausente sin imputación silenciosa | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-086 | Grano etario comunal mensual | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-087 | Ausencia de sexo y doble conteo etario | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-088 | Dominio de grupos de edad DEIS | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-089 | Duplicado de clave etaria | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-090 | Reconciliación de cinco grupos etarios | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-091 | Comuna sin reporte conserva nulos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-092 | Reportantes anuales únicos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-093 | Tasa anual desde conteo y población | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-094 | Año de vulnerabilidad preservado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-095 | Total territorial de oferta reconciliado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-096 | Universo comunal incompleto rechazado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-097 | Filtro F00 F99 desde catálogo oficial | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-098 | Residencia RM y origen nulo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-099 | Diagnóstico ajeno a catálogo rechazado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-100 | Reglas explícitas de armonización | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-101 | Tramo abierto de edad sin asignación ambigua | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-102 | Categoría nueva sin regla detiene salida | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-103 | Suma comunal y cero de egresos explícito | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-104 | Tasa estadía y pertenencia SNSS | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-105 | Tasa de egresos sin denominador | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-106 | Totales reconciliados de desgloses | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-107 | Contraste ecológico en años completos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-108 | Cuatro fuentes contextuales preservadas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-109 | Publicación contextual atómica e idempotente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-110 | Dependencias de contexto en DAG | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-111 | Panel sin fragmento de semana 53 | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-112 | Coherencia regional del panel | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-113 | Panel con cobertura desigual rechazado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-114 | Perturbación futura sin fuga temporal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-115 | Rezagos sujetos al horizonte directo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-116 | Aislamiento de características entre series | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-117 | Separación de ajuste y objetivo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-118 | Referencia estacional del año anterior | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-119 | Límites no negativos y ordenados | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-120 | LightGBM reproducible con semilla fija | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-121 | Reconciliación con suma comunal cero | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-122 | Poisson con intervalo válido | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-123 | Persistencia conserva valores y esquema | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-124 | Manifiesto con modelo y procedencia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-125 | Hash de entrada modificada invalida vigencia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-126 | Entrada faltante invalida vigencia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-127 | Manifiesto incompleto rechazado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-128 | API reutiliza pronóstico vigente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-129 | Fallback de cálculo con advertencia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-130 | Origen de pronóstico publicado en meta | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-131 | Snapshot distinto al registrado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-132 | Holdout sin semanas truncadas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-133 | Exclusión excesiva detiene evaluación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-134 | Comparación significativa en ambos niveles | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-135 | Cuantiles discretos y cobertura nominal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-136 | Selección exige calibración | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-137 | Exposición proporcional a semana corta | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-138 | Nuevo snapshot invalida pronóstico de establecimiento | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-139 | Guardia de plausibilidad por máximo reciente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-140 | Volumen anual insuficiente excluye serie | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-141 | Contrato de historia y pronóstico sintético | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-142 | 503 transitorio y Retry After | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-143 | Error de datos comunicado por servicio | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-144 | Cambio de magnitud dentro del intervalo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-145 | Semana parcial separada del histórico | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-146 | Dotación sin cifra devuelve nulo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-147 | Promedio excluye horizonte retenido | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-148 | Motivo de retención por plausibilidad | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-149 | Ocupación ausente conservada como nulo | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-150 | Horizontes ya observados descartados | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-151 | Meta informa vigencia y etapa de recuperación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-152 | Contrato regional de egresos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-153 | Errores de territorio y año en egresos | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-154 | Mart de egresos ausente produce 503 | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-155 | Caracterización por semanas y causa | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-156 | Escenario contextual sin información futura | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-157 | Restos mayores conservan el total | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-158 | Suicidios vencido mantiene abstención | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-159 | Carga de suicidios solicita reintento | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-160 | Tasa reciente conserva bordes de año | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-161 | Refresh limitado a rama afectada | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-162 | Refresh idéntico no fuerza downstream | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-163 | Processed desalineado obliga reconstrucción | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-164 | Recuperación tras limpieza fallida | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-165 | Exit cero sin outputs no es éxito | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-166 | Parquet corrupto invalida SKIP | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-167 | Limpieza limitada a un año | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-168 | Modo sin evaluación respeta orden del DAG | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-169 | Cascada preservada sin benchmarks | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-170 | Arranque descarga data y reports | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-171 | Prefijo S3 respetado en arranque | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-172 | Modo local no utiliza S3 | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-173 | Bucket vacío y ausencia de datos explícita | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-174 | Falla de descarga impide arranque válido | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-175 | Uvicorn inicia después de preparación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-176 | CRS distinto rechazado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-177 | Geometría inválida sin reparación silenciosa | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-178 | Coordenada incompleta rechazada | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-179 | Discrepancia de comuna marcada | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-180 | Join territorial no unívoco rechazado | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-181 | Distancia haversine de referencia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-182 | Cuantil ponderado por población censal | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-183 | Exclusión espacial limitada y visible | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-184 | Ausencia de ubicación ID36 bloquea distancia | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-185 | Resolución sin imputar coordenadas | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-186 | Identidades de habilitación y ampliación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-187 | Dotación suficiente evita ampliación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-188 | Umbral exacto sin cama espuria | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-189 | Abstención por ventana área o duplicados | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-190 | Nulos cierres y antigüedad sin ceros ficticios | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-191 | Pico mensual gobierna escenario | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-192 | Escenario independiente para cada área | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-193 | Retrospectiva sin acceso al futuro | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-194 | Ventana gráfica no modifica escenario anual | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-195 | Grano de ocupación por área y mes | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-196 | Promedio diario desde días cama | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-197 | Total hospitalario sin sumar índices | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-198 | Mes ausente permanece ausente | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-199 | Identidad con promedio oficial obligatoria | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |
| SAAD-CP-200 | Clasificación en límites de ocupación | — | NO EJECUTADO | No ejecutado | — | Sin defecto registrado | El procedimiento no es una consulta HTTP automatizable en este modo. |

## Límites

- Las consultas HTTP verifican el contrato de la API en el entorno y snapshot indicados; no acreditan otros entornos ni otros datos.
- Los estados de ejecución del catálogo (.docx) no se modifican: esta corrida es la evidencia.
- Nombre de evidencia según el plan (SAAD-CP-NNN_fecha_entorno); el comando del catálogo propone SAAD-CP-NNN.xml.
