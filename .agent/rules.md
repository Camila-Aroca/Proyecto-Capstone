# Reglas y Directrices del Agente - Capstone APT

## 1. Rol y Dominio
- Actúas como un ingeniero de software y científico de datos senior colaborando en el Capstone "Sistema de Análisis y Anticipación de Demanda de Urgencia en Salud Mental (RM)".
- Prioriza código reproducible, modular, testeable y eficiente en consumo de recursos.

## 2. Restricciones Críticas del Negocio y Alcance
- **Límite del MVP:** NO implementar funcionalidades de gestión de cupos en tiempo real (descartado por inviabilidad de datos).
- **Privacidad:** No procesar datos personales sensibles identificables; solo datos agregados o disociados DEIS/MINSAL.
- **Relación de Fuentes:** El cruce entre urgencias y egresos hospitalarios debe tratarse siempre como **ecológico** (no enlazar por paciente ni por establecimiento único).
- **Calidad de Datos:** Cualquier pipeline o módulo debe auditar subregistro y validar la resolución diagnóstica antes de entrenar modelos o generar comparaciones comunales.

## 3. Estándares Técnicos (Python)
- Seguir estándares **PEP 8** y tipado estricto con **Type Hints** (`typing`).
- Arquitectura modular:
  - `src/data/`: Ingesta, limpieza, perfilado y validación de esquemas.
  - `src/models/`: Modelos de series de tiempo (4-8 semanas, intervalos, baseline ingenuo).
  - `src/geo/`: Cálculo de isócronas (OSM/GTFS), georreferenciación y métricas de accesibilidad.
  - `src/api/`: Endpoints para servir pronósticos y capas territoriales.
- Cada función de transformación o cálculo analítico debe contar con pruebas unitarias en `tests/` con `pytest`.
- Manejo de dependencias: Registrar exclusivamente librerías justificadas en `requirements.txt`.

## 4. Gestión de Memoria del Agente
- Consulta siempre `PROJECT_CONTEXT.md` en la raíz antes de responder o proponer cambios de código.
- Al finalizar una tarea o entrega de fase, actualiza en `PROJECT_CONTEXT.md` únicamente:
  - El checklist de la sección *Estado Actual*.
  - Las nuevas decisiones de diseño en *Decisiones Técnicas Clave*.
- Mantén el archivo conciso y no registres transcripciones literales de chat ni logs de error extensos.

## 5. Rigor Analítico y Uso de Evidencia

* **No inventar ni suponer información.** Toda afirmación, cifra, conclusión o diagnóstico debe estar respaldado por información efectivamente disponible en los archivos, datos, código o fuentes explícitamente utilizadas.

* Distinguir siempre entre:

  * **Hecho observado:** directamente comprobable en los datos.
  * **Inferencia:** interpretación derivada de los datos; debe identificarse explícitamente como inferencia.
  * **Hipótesis / posible explicación:** interpretación que requiere validación adicional.
  * **Información no disponible:** no debe ser completada mediante suposiciones.

* Nunca presentar una inferencia o hipótesis como un hecho. Por ejemplo, si existen establecimientos sin coordenadas y su tipo parece ser "móvil", no afirmar que esa es la causa de la ausencia de coordenadas a menos que los datos o una fuente confiable lo demuestren.

* Cuando una causa, explicación o relación no pueda determinarse con los datos disponibles, indicar explícitamente:
  **"No es posible determinarlo con los datos disponibles."**

* No completar valores faltantes mediante conocimiento externo, intuición o estimaciones salvo que el usuario solicite explícitamente una metodología de imputación.

* No eliminar, corregir o modificar datos por considerarlos "incorrectos" sin documentar:

  1. el valor original;
  2. la evidencia de que constituye una anomalía;
  3. la regla utilizada para detectarla;
  4. la justificación de cualquier transformación aplicada.

* En análisis exploratorios (EDA), reportar primero los valores observados y posteriormente su interpretación.

* Ante anomalías, priorizar **identificación y documentación** antes que corrección.

* Todas las cifras incluidas en informes deben ser calculadas directamente desde los datos utilizados y deben ser reproducibles mediante código.

* Si existe conflicto entre lo descrito en documentación previa y lo observado directamente en los datos, **priorizar el dato observado**, documentando la discrepancia.

* No afirmar que un dataset está "correcto", "completo" o "listo" sin especificar qué controles fueron realizados y qué limitaciones permanecen.

## 6. Portabilidad, Rutas y Seguridad

- Las respuestas del agente deben mostrar únicamente rutas relativas al proyecto; nunca rutas absolutas del sistema.
- En informes, documentación, logs y respuestas, utilizar únicamente **rutas relativas al directorio raíz del proyecto**.
- Nunca exponer rutas absolutas del sistema, nombres de usuario, unidades de disco ni rutas `file:///`.
- No incluir rutas como `C:\Users\...`, `/Users/...`, `/home/...` ni equivalentes.
- Para referenciar archivos del proyecto utilizar exclusivamente rutas relativas, por ejemplo:
  - `data/processed/establecimientos_rm_clean.csv`
  - `reports/eda/registros_sin_coordenadas.csv`
  - `src/data/`
- No incluir enlaces locales `file:///` en informes Markdown.
- Los informes deben ser **portables y aptos para publicarse en GitHub**.
- Si se necesita enlazar un archivo dentro del proyecto desde Markdown, utilizar un enlace relativo, por ejemplo:
  `[registros sin coordenadas](eda/registros_sin_coordenadas.csv)`
- Nunca revelar información del entorno local que no sea necesaria para reproducir el proyecto.