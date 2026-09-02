# Contexto del Proyecto: Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental (RM)

## 1. Propósito y alcance

Desarrollar y validar una plataforma analítica web para la Región Metropolitana que:

1. proyecte demanda de urgencia en salud mental a 4–8 semanas;
2. identifique brechas territoriales de accesibilidad;
3. caracterice factores asociados a la duración de hospitalización en diagnósticos F00–F99;
4. integre estos resultados en una plataforma web funcional, probada, documentada y desplegable.

El producto apoya la planificación mediante evidencia reproducible; no es un sistema de gestión de cupos en tiempo real ni un dashboard meramente descriptivo.

Metodología: desarrollo ágil iterativo + ciclo de datos inspirado en CRISP-DM.

## 2. Componentes analíticos

### Demanda
- Fuente principal: Atenciones de Urgencia DEIS.
- Resolución objetivo: semanal por establecimiento.
- Horizonte: 4–8 semanas.
- Evaluación: backtesting, intervalos de predicción y baseline estacional ingenuo.
- RAW disponible 2020–2026.
- La serie principal para modelamiento comienza en 2021 debido a la discontinuidad observada en salud mental durante 2020.
- El año en curso es una fuente mutable y debe tratarse mediante snapshots reproducibles.

### Accesibilidad
- Establecimientos DEIS.
- Cartografía Censo 2024.
- Red vial OSM y transporte público GTFS.
- Objetivo: georreferenciación, isócronas, cobertura poblacional, vulnerabilidad y brechas comunales.

### Hospitalización
- Fuente: Egresos Hospitalarios DEIS 2020–2025.
- `DIAG1`: diagnóstico principal CIE-10.
- `DIAG2`: causa externa CIE-10.
- Población analítica: egresos con diagnóstico F00–F99.
- Objetivo: caracterizar la duración de estadía, analizar factores asociados y examinar diferencias según sexo, previsión y pertenencia al SNSS.
- Complementar la interpretación con indicadores oficiales de salud mental desagregados por sexo cuando corresponda.
- Edad, condición de egreso u otras variables disponibles pueden analizarse como factores adicionales si existe justificación analítica, sin sustituir los componentes exigidos por el objetivo APT.

## 3. Decisiones y Supuestos Clave

- No procesar datos personales identificables.
- Urgencias y Egresos no son enlazables por individuo.
- Egresos no posee identificador inequívoco del establecimiento hospitalario.
- `REGION_RESIDENCIA` y `COMUNA_RESIDENCIA` representan residencia del paciente, no ubicación del hospital.
- Cualquier relación Urgencias–Egresos será exclusivamente ecológico-territorial.
- Mantener explícitamente separadas sus granularidades en el modelo de datos.
- En Egresos 2024–2025 existen caracteres U+FFFD originados en la fuente en algunas glosas; los códigos territoriales y diagnósticos permanecen utilizables.
- No reconstruir glosas ni imputar valores sin evidencia o metodología explícita.
- En Urgencias, `ID 36` representa el total F00–F99 y cumple:
  `ID36 = ID37 + ID38 + ID39 + ID40 + ID41`.
- `ID35` e `ID42` están fuera de `ID36`.
- Los reports contienen el detalle cuantitativo validado; no duplicar aquí métricas volátiles.
- Ante conflicto entre documentación histórica y datos actuales, comprobar el dato y documentar la discrepancia.

## 4. Reproducibilidad

- `scripts/run_pipeline.py` es el punto de entrada oficial para generar outputs permanentes.
- `PIPELINE.md` documenta el DAG y su ejecución.
- `data/raw/` es inmutable durante procesamiento downstream.
- Todo código permanente debe estar en `src/`, `scripts/` o `tests/`.
- `scratch/` es exclusivamente temporal.
- Todas las rutas versionadas deben ser relativas o derivadas dinámicamente desde la raíz del repositorio.
- Los valores del año en curso deben obtenerse desde datos/provenance, no desde cifras copiadas en este archivo.
- Un clon limpio debe poder reproducir los outputs mediante código versionado, dependencias declaradas y fuentes documentadas.

## 5. Estado Actual

- [x] Ingesta y limpieza de establecimientos DEIS.
- [x] Validación de establecimientos RM.
- [x] Ingesta y procesamiento de Censo 2024 RM.
- [x] Ingesta RAW Urgencias 2020–2026.
- [x] Normalización y validación Urgencias RM.
- [x] Catálogo y auditoría F00–F99 de Urgencias.
- [x] EDA descriptivo de demanda de Urgencias.
- [x] Ingesta RAW Egresos 2020–2025.
- [x] Normalización reproducible de Egresos 2020–2025.
- [ ] Perfilado y auditoría F00–F99 de Egresos.
- [ ] Modelo de demanda 4–8 semanas.
- [ ] Capa de accesibilidad OSM/GTFS.
- [ ] Análisis de duración de estadía F00–F99.
- [ ] Integración plataforma web/API.
- [ ] Pruebas técnicas y validación con usuarios.
- [ ] Despliegue y documentación final.
- [x] Pipeline reproducible e idempotente.