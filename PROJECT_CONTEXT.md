# Contexto operativo del proyecto APT

## 1. Alcance y restricciones invariantes

La Definicion Proyecto APT final aprobada por el equipo es la autoridad normativa sobre alcance y objetivos. El codigo, datos, tests y reports vigentes son la autoridad sobre implementacion y resultados tecnicos; este archivo no reemplaza esas evidencias.

El proyecto desarrolla y valida una plataforma analitica web/API para la Region Metropolitana que integre:

- Demanda de urgencias en salud mental a 4-8 semanas, con metricas, intervalos de prediccion, backtesting y comparacion contra baseline estacional ingenuo.
- Accesibilidad territorial mediante establecimientos, georreferenciacion, OSM/GTFS, cobertura poblacional y vulnerabilidad/brechas por comuna.
- Hospitalizacion psiquiatrica con egresos F00-F99, duracion de estadia y factores asociados, incluyendo sexo, prevision y pertenencia al SNSS.
- Plataforma funcional, reproducible, probada, desplegada, documentada y validada en utilidad/comprension con docente o cliente piloto.

Restricciones que no deben relajarse:

- No gestionar cupos en tiempo real ni reducir el producto a un dashboard meramente descriptivo.
- Urgencias y Egresos no se enlazan por paciente. Toda relacion entre fuentes es ecologica/territorial y mantiene sus granularidades distintas.
- Los indicadores externos de Estadisticas de Genero son solo contexto interpretativo: no se cruzan automaticamente con Urgencias/Egresos ni se convierten automaticamente en features.

## 2. Decisiones y supuestos estables

- No procesar datos personales identificables.
- `REGION_RESIDENCIA` y `COMUNA_RESIDENCIA` en Egresos representan residencia del paciente, no ubicacion del hospital. Egresos no tiene un identificador inequívoco del establecimiento hospitalario.
- `DIAG1` es diagnostico principal y `DIAG2` causa externa; el analisis hospitalario se restringe a F00-F99.
- No imputar ni corregir valores sin evidencia y regla reproducible; conservar las glosas de fuente sin reconstruccion arbitraria.
- En indicadores de genero: PHQ-4 conserva `period` y `year = null`; sintomas depresivos conserva los periodos `2003`, `2009-10` y `2016-17`; el valor publicado `-` de ratios regionales se conserva como texto.

## 3. Reproducibilidad y fuentes de evidencia

- `scripts/run_pipeline.py` es la entrada oficial para outputs permanentes.
- `PIPELINE.md` es la fuente del DAG, stages, dependencias y ejecucion.
- Codigo, tests y reports contienen el detalle tecnico, cuantitativo y de validacion; `data/raw/` se trata como snapshot/provenance y no como espacio de trabajo downstream.
- Las fuentes del año en curso pueden ser mutables; sus snapshots deben identificarse mediante provenance para mantener reproducibilidad.
- Este archivo resume contexto estable y no debe duplicar metricas volatiles, logs, resultados de una ejecucion aislada ni el contenido de PIPELINE/reports.

## 4. Estado actual

- **Base de datos y pipeline:** implementada la ingesta/normalizacion reproducible de establecimientos, Censo RM, Urgencias 2020-2026, Egresos 2020-2025 y cuatro indicadores contextuales de salud mental por sexo; tambien existen catalogos y EDA de Urgencias. Se agrego `dim_poblacion_comuna_anual` (INE, estimaciones/proyecciones 2002-2035 base Censo 2017) como denominador poblacional anual 2021-2025 por comuna RM, distinto de la poblacion censada 2024; los marts comunales de Urgencias (weekly/monthly) ya incorporan tasas de atenciones por 10.000 habitantes (ID1, ID35, ID36) usando esa dimension.
- **Preparacion analitica:** pendiente el perfilado/auditoria F00-F99 de Egresos y la consolidacion de evidencias de validacion donde corresponda. No afirmar completitud global del pipeline.
- **Pendientes principales:** forecasting 4-8 semanas; accesibilidad OSM/GTFS, cobertura y brechas; analisis de duracion de estadia y factores asociados; integracion web/API; pruebas tecnicas integrales, validacion con usuario piloto, despliegue y documentacion final.
- **Siguiente frente logico aproximado:** completar la auditoria analitica de Egresos F00-F99 y, en paralelo segun dependencias, preparar las bases para forecasting y accesibilidad.

## 5. Mantenimiento de este contexto

Actualizar `PROJECT_CONTEXT.md` solo cuando cambie informacion estable del proyecto: alcance formal, decisiones/supuestos metodologicos o `Estado actual`. No actualizarlo por cada test, log, metrica temporal o resultado aislado. Cada actualizacion debe mantenerlo breve y permitir recuperar rapidamente el estado sin leer todo el repositorio.
