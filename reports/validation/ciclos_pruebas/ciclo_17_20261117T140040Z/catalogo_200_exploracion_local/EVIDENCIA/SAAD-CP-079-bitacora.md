# Bitácora de exploración SAAD-CP-079 (LOCAL)

Inicio 2026-11-18T18:30:37Z · fin 2026-11-18T18:32:10Z · duración real 1.5 min. La exploración se hizo con un barrido automatizado con Chrome (CDP) de las comunas de mayor riesgo de mala interpretación; **no es la sesión humana de 30 minutos** que describe el caso.

## Selección
- Sin datos: María Pinto (13504), Vitacura (13132).
- Cero observado (más semanas en 0 entre las últimas 12 observadas): Tiltil (3), Calera de Tango (1), Las Condes (1).
- Baja confianza (menor promedio de las últimas 26 semanas): Alhué (3.5/sem), Tiltil (3.5/sem), Calera de Tango (4.3/sem).

## Los tres estados
| Estado | Comuna | Resultado | Cumple |
|---|---|---|---|
| Sin datos | María Pinto (13504) | Aviso «Pronóstico no disponible»: sí · motivo visible: sí · dibuja pronóstico cero: no | sí |
| Sin datos | Vitacura (13132) | Aviso «Pronóstico no disponible»: sí · motivo visible: sí · dibuja pronóstico cero: no | sí |
| Cero observado | Tiltil (13303) | API: 3 de las últimas 12 semanas observadas con 0 atenciones · tabla (20 filas): 3 filas «0 · Observado», 0 filas sin valor | sí |
| Cero observado | Calera de Tango (13403) | API: 1 de las últimas 12 semanas observadas con 0 atenciones · tabla (20 filas): 1 filas «0 · Observado», 0 filas sin valor | sí |
| Cero observado | Las Condes (13114) | API: 1 de las últimas 12 semanas observadas con 0 atenciones · tabla (20 filas): 1 filas «0 · Observado», 0 filas sin valor | sí |
| Baja confianza | Alhué (13502) | Promedio 3.5 atenciones/semana · intervalo declarado: sí · confiabilidad observada fuera de muestra visible: sí · advertencia «orientativos»: sí | sí |
| Baja confianza | Tiltil (13303) | Promedio 3.5 atenciones/semana · intervalo declarado: sí · confiabilidad observada fuera de muestra visible: sí · advertencia «orientativos»: sí | sí |
| Baja confianza | Calera de Tango (13403) | Promedio 4.3 atenciones/semana · intervalo declarado: sí · confiabilidad observada fuera de muestra visible: sí · advertencia «orientativos»: sí | sí |

## Pasos reproducibles
**Sin datos · María Pinto (13504)**
1. Abrir `#/tablero?territorio=13504` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer el aviso bajo el título
4. Comparar con el motivo de GET /territorios (Dejó de reportar desde la semana 19: ausencia de dato, no demanda cero.)

**Sin datos · Vitacura (13132)**
1. Abrir `#/tablero?territorio=13132` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer el aviso bajo el título
4. Comparar con el motivo de GET /territorios (Sin historia de reporte en el período de entrenamiento: no es pronosticable.)

**Cero observado · Tiltil (13303)**
1. Abrir `#/tablero?territorio=13303` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Abrir «Ver los datos en tabla» (últimas 12 semanas observadas y 8 de pronóstico)
4. Buscar filas con Atenciones = 0 y Tipo = Observado

**Cero observado · Calera de Tango (13403)**
1. Abrir `#/tablero?territorio=13403` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Abrir «Ver los datos en tabla» (últimas 12 semanas observadas y 8 de pronóstico)
4. Buscar filas con Atenciones = 0 y Tipo = Observado

**Cero observado · Las Condes (13114)**
1. Abrir `#/tablero?territorio=13114` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Abrir «Ver los datos en tabla» (últimas 12 semanas observadas y 8 de pronóstico)
4. Buscar filas con Atenciones = 0 y Tipo = Observado

**Baja confianza · Alhué (13502)**
1. Abrir `#/tablero?territorio=13502` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer la frase de pronóstico con su intervalo
4. Leer «Confiabilidad del intervalo»
5. Abrir «Cómo leer estas cifras»

**Baja confianza · Tiltil (13303)**
1. Abrir `#/tablero?territorio=13303` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer la frase de pronóstico con su intervalo
4. Leer «Confiabilidad del intervalo»
5. Abrir «Cómo leer estas cifras»

**Baja confianza · Calera de Tango (13403)**
1. Abrir `#/tablero?territorio=13403` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer la frase de pronóstico con su intervalo
4. Leer «Confiabilidad del intervalo»
5. Abrir «Cómo leer estas cifras»

## Hallazgos
### H-1 · Sin datos · María Pinto (13504)
**Pasos:**
1. Abrir `#/tablero?territorio=13504` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer el texto bajo «Pronóstico no disponible»

**Observado:** Junto al motivo se muestra «No se pudo consultar la API… Verifique que el backend esté corriendo (uvicorn src.api.main:app)…», un mensaje técnico de falla del sistema para una ausencia de dato esperada.

**Impacto:** Un usuario no técnico puede creer que el sistema está caído en lugar de entender que la comuna no se modela. No lleva a una conclusión clínica ni cambia ninguna cifra.

### H-1 · Sin datos · Vitacura (13132)
**Pasos:**
1. Abrir `#/tablero?territorio=13132` con la caché desactivada
2. Esperar a que cargue el panel de la comuna
3. Leer el texto bajo «Pronóstico no disponible»

**Observado:** Junto al motivo se muestra «No se pudo consultar la API… Verifique que el backend esté corriendo (uvicorn src.api.main:app)…», un mensaje técnico de falla del sistema para una ausencia de dato esperada.

**Impacto:** Un usuario no técnico puede creer que el sistema está caído en lugar de entender que la comuna no se modela. No lleva a una conclusión clínica ni cambia ninguna cifra.

Ninguna observación concluye sobre atención clínica individual.