# QA de caracterización en la web

Revisión: 2026-11-07. Alcance: desplegables de Urgencias ID36, hospitalizaciones
desde urgencia ID42 y suicidios X60–X84; selección de territorio, establecimiento
y semanas observadas. No incluye validación clínica del escenario por sexo.

## Implementación y criterio de conciliación

- La consulta recibe las claves año/semana DEIS de la historia visible. No incluye
  pronósticos ni el punto de semana parcial, y conserva los fragmentos del calendario.
- Urgencias suma las cinco columnas etarias publicadas, con comprobación de su
  igualdad al total por registro. Suicidios usa residencia, causa externa y edad
  con su unidad; conserva los faltantes en «Sin dato».
- El agregado regional de Urgencias respeta el universo comunal del panel servido.
  El QA detectó que sumar todas las comunas del processed incorporaba eventos
  ajenos a la línea regional; se corrigió el filtro y se añadió una regresión HTTP.
- La web rechaza desgloses cuyas sumas no coincidan con el total de la historia.
  No ajusta los conteos para ocultar una diferencia entre snapshots.
- El reparto opcional por sexo es un escenario, no un dato observado: transporta
  la proporción nacional de egresos por intento suicida al total seleccionado,
  mediante cuotas racionales y restos mayores. Conserva exactamente el total,
  pero esa igualdad no valida el supuesto ni cuantifica su error. Fuente, año,
  conteos y supuesto se muestran al activarlo. No se estima identidad de género.

## Verificación reproducible

Desde la raíz, con las dependencias declaradas y outputs existentes del pipeline:

```powershell
$env:SAAD_QA_DATOS = '1'
python -m pytest tests/test_api_caracterizacion.py tests/test_api.py tests/test_api_establecimientos.py tests/test_api_suicidios.py tests/test_caracterizacion_integridad.py -q --basetemp=.cache/pytest-caracterizacion-qa
python scripts/run_pipeline.py --help
cd frontend
npm run build
```

Resultados observados: **87 pruebas aprobadas**, ayuda del pipeline correcta y
compilación de producción correcta. Advertencias: deprecación de HTTPX en el
TestClient de Starlette y chunk JavaScript mayor de 500 kB de Vite. No se ejecutó
la suite completa del repositorio ni el pipeline completo; no se modificaron
datasets, dependencias o contratos canónicos.

## Navegador y presentación

Se revisó con Edge/Playwright contra la API local y datos reales, en escritorio
1440 px y móvil 390 px, modos claro y oscuro. Las herramientas de navegador y
capturas se mantuvieron en caché local, fuera de los artefactos canónicos.

Flujos comprobados: abrir ambos desplegables comunales; activar el escenario;
cambiar de región a Santiago; cambiar de 52 a 26 semanas; abrir la caracterización
por establecimiento y cambiar de Atenciones a Hospitalizaciones. Se comprobó la
ausencia de errores JavaScript y de desbordamiento horizontal móvil, y se
inspeccionaron las capturas. Las barras tienen origen en cero, nombre, color,
conteo y porcentaje persistentes en una tabla HTML; no requieren hover. Se
conservaron los estilos de panel, tipografía y desplegables existentes. No se
afirma una auditoría WCAG integral ni validación de utilidad con usuario piloto.

Conciliaciones de la ejecución local (dependen del snapshot y ventana):

| Vista | Ventana comprobada | Total observado y caracterizado |
|---|---|---:|
| Urgencias, región | 52 semanas, 2025-09-21 a 2026-09-26 | 112.939 |
| Suicidios, región, semanas visibles en su línea observada | 2025-09-21 a 2026-10-17 | 573 |
| Urgencias, Santiago | 52 semanas | 3.627 |
| Urgencias, Santiago | 26 semanas | 1.854 |
| Urgencias, Instituto Psiquiátrico Dr. José Horwitz Barak | 52 semanas | 19.162 |
| Hospitalizaciones desde urgencia, mismo establecimiento | 52 semanas | 1.664 |

Los cortes distintos de Urgencias y suicidios son propios de cada fuente: la
caracterización sigue la historia visible de su gráfico, no impone el corte del
otro. REM-20 conserva un aviso de ausencia de sexo/edad individual; las áreas
adultas e infanto-adolescentes no se presentan como edades exactas de pacientes.

## Pipeline y modelo de datos

La consulta es serving de solo lectura sobre outputs ya reproducibles del DAG,
sin nuevos archivos processed ni modelos. Método e inputs documentados en
`PIPELINE.md`. Se evaluó la sincronización ERD/DDL/UML: no requiere cambios al
no modificar entidades canónicas, grano, persistencia ni relaciones. La referencia
contextual permanece separada de los datos observados y de las features.
