# QA de propuesta anual de camas y métricas de ocupación

Validación realizada el 2026-11-07. El método, fuentes, propuestas por área e
identidades numéricas están en el [EDA de ocupación](../eda/eda_mart_ocupacion_psiquiatria_hospital_rm.md)
y su JSON, generados por el pipeline. No es una validación de factibilidad de inversión.

## Regresión y reproducción

```powershell
.venv/Scripts/python.exe -m pytest tests/test_propuesta_camas.py tests/test_api_establecimientos.py tests/test_build_mart_ocupacion_psiquiatria_hospital_rm.py tests/test_pipeline_orchestration.py tests/test_pipeline_task.py tests/test_api.py tests/test_api_suicidios.py tests/test_api_caracterizacion.py --basetemp .cache/pytest-camas-entrega -q
.venv/Scripts/python.exe scripts/run_pipeline.py --stage eda_mart_ocupacion_psiquiatria_hospital_rm --force
.venv/Scripts/python.exe scripts/run_pipeline.py --stage eda_mart_ocupacion_psiquiatria_hospital_rm
.venv/Scripts/python.exe scripts/run_pipeline.py --help
```

Frontend: ejecutar `npm run build` desde `frontend/`. Pruebas analíticas cubren
aritmética exacta en el umbral, pico mensual, dotación suficiente, disponibilidad
REM-20 como base cuando falta dotación, cierres, nulos, antigüedad, duplicados,
áreas sin referencia aplicable, retrospectiva sin fuga temporal y conservación
del ciclo anual aunque cambie la ventana gráfica. El test de API comprueba el
contrato serializado para el caso sin dotación declarada.

Resultado: **149 pruebas aprobadas**, build de producción aprobado y pipeline
con `--force` y posterior `SKIP` válido. `git diff --check` sin errores.

## Comprobaciones de interfaz

Se verificó en Chrome headless con un montaje temporal de los componentes
reales y datos sintéticos; las capturas locales de QA no son outputs canónicos.
Diez comprobaciones pasaron: advertencias cerradas inicialmente y apertura al
pulsar; dotación total dinámica; dotación y aumento en la fila de métricas;
línea propuesta con aumento positivo; ausencia de desborde horizontal a 390 px;
cambio de dotación/aumento al seleccionar otra área; ausencia de línea con
aumento cero; capacidad REM-20 y aumento cuando falta dotación; línea verde
en ese caso. Se revisaron capturas de escritorio claro y móvil oscuro.

Para repetir la revisión manual en la vista de hospitalizaciones: seleccionar
un área de corta estadía, comparar las cinco métricas y la línea verde con los
campos `areas_psiquiatria[].propuesta_camas` de la respuesta de detalle, cambiar
de área y repetir. Verificar también un aumento cero y un área sin dotación,
con una ventana gráfica corta y otra larga. Las cifras de la propuesta deben
permanecer iguales al variar exclusivamente la ventana gráfica. En ambas vistas
que usan `AvisoLectura`, comprobar estado cerrado y apertura con teclado/clic.

También se consultó la API local con datos procesados reales: el establecimiento
114101 devolvió para corta estadía adulta dotación 39, pico mensual 1173/30,
objetivo 46 y aumento 7. Son cifras de este snapshot, no expectativas fijas
para otros hospitales ni fixtures de producción.

## Límites

El escenario calcula cada área de psiquiatría con su propia historia y supone
continuidad de carga, no crecimiento pronosticado. Fuera de corta estadía 418/421,
el 85% es un supuesto de escenario sin calibración específica por especialidad.
No mide espera ni picos diarios y no acredita personal,
presupuesto, espacio o plazos. Cuando la base es disponibilidad REM-20, el
aumento es capacidad adicional: no distingue construcción de rehabilitación.
La retrospectiva del EDA mide promedios mensuales, no garantía de cama diaria.
Se ejecutaron pruebas relacionadas y de API/orquestación, no la suite completa.
Los warnings de deprecación de TestClient y de tamaño de bundle no son errores
del cálculo. No se modificaron dependencias, esquemas canónicos ni persistencia.

## Regresión: propuesta inicial del hospital

La vista total ya no exige seleccionar un área para entregar una cifra. Suma
los aumentos de las áreas de psiquiatría, sin compensarlos con holgura de otras.
Un subtotal incompleto se identifica como parcial; nunca transforma ausencia
en cero. El desglose muestra la propuesta o motivo por cada área.

```powershell
node --experimental-strip-types --test frontend/tests/propuestaCamas.test.mjs
```

Estas cinco pruebas (Node 22.6+) cubren total inicial, hospital con una sola área,
base REM-20 sin dotación, subtotal parcial y diferencia entre cero y ausencia.
El test parametrizado Python verifica los once códigos de áreas psiquiátricas
del REM-20 (excluye 427, sociosanitaria).

Revalidación de esta corrección: 63 pruebas Python relacionadas y las cinco
pruebas Node aprobadas; build de producción aprobado; EDA regenerado mediante
el pipeline y posterior `SKIP` válido. Chrome verificó nueve condiciones con
datos reales del establecimiento 114101: total inicial +9 (línea 60), adulto +7
(línea 46), infanto +2 (línea 14), retorno al total, ausencia del bloqueo por
selección y ausencia de desborde móvil a 390 px. Son valores del snapshot usado,
no constantes de producción. No se ejecutó la suite completa.

## Etiquetas y leyenda de referencias

Las cifras «Dotación: N camas» y «Propuesta: N camas» ocupan una franja de flujo
normal sobre el área de trazado, con ajuste de línea en móvil. No se dibujan
encima de las series ni dependen de la distancia vertical entre referencias.
La leyenda incluye el trazo verde y el año de propuesta únicamente si esa línea
está visible. Conserva los tokens y estilo punteado existentes.

Validación: build de producción y cinco pruebas frontend aprobados. Chrome
aprobó nueve comprobaciones: cifras reales de dotación/propuesta, leyenda con
año, separación respecto del trazado y entre etiquetas, referencias casi iguales
con cifras grandes, separación y ausencia de recorte a 320 px, ausencia de
desborde, ocultación de etiqueta/leyenda verde sin línea y modo claro. Se
revisaron capturas de escritorio claro y móvil oscuro. Esta modificación es
de presentación; no cambia cálculos, contratos, dependencias ni DAG.
