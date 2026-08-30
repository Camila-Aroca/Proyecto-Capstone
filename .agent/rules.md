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
- Formatos de almacenamiento de datos:
  - Conservar en `data/raw/` los archivos de datos y documentación en el formato original contenido en la fuente. Los contenedores de transporte (`.zip`, `.gz`, `.tar`, etc.) no constituyen RAW canónico cuando su único propósito es transportar archivos que pueden extraerse y validarse.
  - Para datasets tabulares procesados, intermedios o analíticos de tamaño relevante, preferir **Parquet** sobre CSV cuando no exista una necesidad explícita de interoperabilidad en texto.
  - Para datos geoespaciales procesados, preferir **GeoParquet** cuando sea compatible con el flujo.
  - Utilizar CSV principalmente para:
    - tablas pequeñas destinadas a inspección humana;
    - catálogos simples;
    - outputs de reports;
    - intercambio con herramientas que no soporten Parquet.
  - Evitar generar simultáneamente CSV y Parquet con el mismo contenido salvo que exista una necesidad concreta y documentada.
  - Al leer Parquet, seleccionar únicamente las columnas necesarias cuando sea posible para reducir I/O y consumo de memoria.
  - No cargar datasets completos en memoria cuando el análisis pueda resolverse mediante lectura selectiva, filtros, particionado o procesamiento por bloques.

## 4. Gestión de Contexto y Eficiencia de Tokens

- Consultar `PROJECT_CONTEXT.md` antes de realizar cambios sustantivos en código, datos o arquitectura.

- `PROJECT_CONTEXT.md` funciona como índice de contexto estable, NO como fuente primaria de métricas volátiles.

- No leer automáticamente todos los archivos de `reports/`, `data/`, `src/` o `PIPELINE.md`.
  Inspeccionar únicamente los archivos necesarios para la tarea actual.

- Consultar `PIPELINE.md` cuando la tarea:
  - cree o modifique código ejecutable;
  - agregue o modifique stages;
  - cambie inputs, outputs o dependencias del DAG.

- Consultar reports únicamente cuando sean evidencia necesaria para la tarea actual.

- Reutilizar resultados ya validados y documentados. No repetir auditorías completas salvo que:
  1. haya cambiado un input upstream;
  2. haya cambiado el código que produce el resultado;
  3. exista una contradicción;
  4. el usuario solicite explícitamente reauditar.

- Preferir búsquedas dirigidas, lectura de rangos y metadata antes que recorrer archivos masivos completos.

- No generar `implementation_plan.md`, `task.md`, `walkthrough.md` u otros artefactos de planificación dentro del repositorio salvo solicitud explícita.

- Mantener respuestas operativas concisas:
  - cambios realizados;
  - evidencia;
  - tests;
  - estado Git;
  - bloqueos reales.

- Al finalizar una tarea o fase, actualizar `PROJECT_CONTEXT.md` únicamente cuando cambie:
  - `Estado Actual`;
  - `Decisiones y Supuestos Clave`.

- No copiar logs extensos, transcripts ni resultados EDA completos a `PROJECT_CONTEXT.md`.

- En análisis de datos grandes, evitar lecturas completas cuando no sean necesarias. Priorizar metadata, esquemas, conteos, selección de columnas, filtros y procesamiento por bloques antes de cargar datasets completos.

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
- En código Python, nunca hardcodear la ubicación absoluta de la raíz del repositorio.
  Las rutas deben construirse con `pathlib.Path` usando rutas relativas al proyecto
  o una raíz obtenida dinámicamente desde `__file__`.
- Una ruta absoluta generada dinámicamente en runtime mediante `Path.resolve()`
  es válida; lo prohibido es almacenar una ruta personal literal en código,
  configuración, documentación o outputs versionados.

## 7. Reproducibilidad y Registro Obligatorio en el Pipeline

- `scripts/run_pipeline.py` es el punto de entrada oficial para generar outputs canónicos y `PIPELINE.md` documenta el DAG.

- Ningún código permanente de descarga, ingesta, transformación, limpieza, validación, construcción de catálogos o generación reproducible de outputs puede considerarse terminado si queda fuera del DAG cuando forma parte del flujo oficial.

- Antes de crear un nuevo archivo `.py`, verificar si la lógica puede incorporarse a un módulo o stage existente para evitar duplicación.

- Todo nuevo stage debe declarar:
  1. nombre;
  2. inputs;
  3. outputs;
  4. upstream;
  5. downstream;
  6. validación de outputs;
  7. condición de `SKIP`;
  8. comportamiento con `--force`;
  9. tests.

- Todo nuevo stage debe registrarse en:
  - `scripts/run_pipeline.py`;
  - `PIPELINE.md`;
  - `tests/`.

- Si un upstream cambia efectivamente, regenerar únicamente sus dependencias downstream.

- Los outputs canónicos de `data/processed/` deben generarse mediante `scripts/run_pipeline.py`.

- No ejecutar directamente módulos permanentes de `src/data/` para regenerar outputs oficiales. La ejecución directa solo se permite para tests, mocks o diagnósticos controlados que no modifiquen outputs canónicos.

- Los EDA que generen tablas o artefactos utilizados posteriormente deben formar parte del DAG. Los informes Markdown curados manualmente no deben sobrescribirse automáticamente.

- `scratch/` nunca puede contener lógica indispensable. El código permanente debe vivir en `src/`, `scripts/` o `tests/`.

- Para outputs grandes o costosos de regenerar utilizar escritura segura:
  archivo temporal → cierre y validación → reemplazo atómico.

- Si una tarea ejecuta `pip install`:
  - una dependencia necesaria para código o tests versionados debe registrarse en `requirements.txt`;
  - una dependencia usada exclusivamente por una auditoría temporal de `scratch/` no debe añadirse automáticamente.

- Antes de considerar completa una tarea que modifica código ejecutar:
  - `python scripts/run_pipeline.py --help`;
  - `pytest tests/`;
  - `git status --short`;
  - verificar si cambiaron el DAG, `PIPELINE.md` o `requirements.txt`.

- Ninguna tarea está completa si su reproducción requiere recordar manualmente una secuencia de scripts que no esté representada por el DAG.

- No modificar silenciosamente el significado, nombre, tipo o unidad de una variable procesada. Todo cambio de esquema que pueda afectar etapas downstream debe estar respaldado por evidencia, reflejarse en los tests correspondientes y propagarse únicamente mediante el pipeline.

## 8. Datos RAW, Descargas y Archivos Temporales

- `data/raw/` contiene snapshots fieles de las fuentes externas y debe tratarse como **solo lectura para todas las etapas downstream**. Únicamente los stages oficiales de ingesta/descarga pueden crear o actualizar snapshots RAW conforme a la política temporal definida en esta sección.

- Nunca utilizar `data/raw/` como directorio de salida temporal durante una descarga o extracción. Los archivos incompletos deben permanecer fuera de `data/raw/` hasta superar las validaciones requeridas. En `data/raw/` solo entran archivos que ya superaron la ingestión.

- Ninguna etapa de limpieza, normalización, EDA, modelado o generación de features puede modificar, corregir, sobrescribir o eliminar archivos existentes en `data/raw/`.

- Los archivos comprimidos utilizados únicamente como contenedores de transporte (`.zip`, `.gz`, `.tar`, etc.) son artefactos temporales y NO deben conservarse permanentemente cuando ya exista una copia RAW extraída y validada.

- El flujo recomendado para fuentes comprimidas es:

  1. descargar el archivo comprimido a una ubicación temporal;
  2. validar integridad del archivo comprimido;
  3. calcular y registrar su SHA256;
  4. extraer los archivos esperados a una ubicación temporal;
  5. validar que los archivos extraídos sean legibles y correspondan a lo esperado;
  6. calcular y registrar SHA256 de los archivos RAW extraídos;
  7. mover de forma segura los archivos validados a `data/raw/`;
  8. eliminar el archivo comprimido temporal.

- Siempre que sea posible, los archivos comprimidos deben descargarse en `.cache/downloads/` o en otra ubicación temporal relativa al proyecto, NO directamente en `data/raw/`.

- `.cache/` y otros artefactos temporales de descarga deben estar excluidos de Git.

- Nunca eliminar el archivo comprimido antes de comprobar que la extracción y validación finalizaron correctamente.

- Si una descarga, extracción o validación falla, no reemplazar ni dañar un RAW válido existente.

- Los diccionarios, catálogos u otros archivos entregados por la fuente que sean necesarios para interpretar los datos sí deben conservarse en `data/raw/`, aunque hayan venido dentro del ZIP.

- Solo los stages oficiales de ingesta/descarga pueden crear un nuevo snapshot RAW. Las etapas downstream solo pueden leerlo.

- Distinguir siempre entre fuentes de **años cerrados** y fuentes del **año en curso**.

- Los RAW correspondientes a años cerrados se consideran snapshots consolidados y no deben sobrescribirse durante la operación normal del pipeline.

- Los RAW correspondientes al año en curso pueden ser actualizados exclusivamente por el stage oficial de ingesta/descarga, porque la fuente externa puede incorporar nuevos registros durante el año.

- La condición de "año en curso" debe determinarse dinámicamente cuando sea posible; no hardcodear reglas de mutabilidad específicas para `2026`, `2027` u otro año concreto.

- Cuando una fuente del año en curso sea actualizada:
  1. descargar y validar primero el nuevo artefacto en ubicación temporal;
  2. registrar URL, fecha/hora real de descarga, tamaño y SHA256;
  3. extraer y validar los archivos RAW resultantes;
  4. registrar también el SHA256 del RAW extraído;
  5. reemplazar el RAW anterior únicamente después de completar todas las validaciones;
  6. realizar el reemplazo de forma segura/atómica cuando sea técnicamente posible;
  7. eliminar posteriormente el archivo comprimido temporal.

- Nunca sobrescribir silenciosamente un snapshot RAW del año en curso. El cambio debe quedar registrado en provenance antes de que etapas downstream utilicen el nuevo snapshot.

- Cuando finalice el año calendario, ese RAW pasa a considerarse un año cerrado y deja de actualizarse automáticamente.

- Si excepcionalmente una fuente oficial modifica retrospectivamente datos de un año cerrado, no reemplazarla automáticamente. Requerir una actualización explícita y documentar el cambio de snapshot y hashes antes de sustituir el RAW existente.

- El provenance debe conservar historial de snapshots/hashes y no únicamente el último estado conocido.

- `data/processed/` es regenerable; `data/raw/` no debe utilizarse como espacio de trabajo temporal.

- La optimización de formato pertenece a las capas procesadas. No reemplazar un archivo RAW original por Parquet, GeoParquet u otro formato optimizado únicamente para mejorar rendimiento.

- Distinguir entre reproducibilidad del pipeline y reproducibilidad del snapshot:
  - el código, configuración y orden de ejecución deben ser reproducibles desde Git;
  - los resultados de datos son exactamente reproducibles cuando se dispone del mismo snapshot RAW identificado por provenance y SHA256;
  - si una fuente externa mutable no conserva versiones históricas, no afirmar que un snapshot antiguo puede reconstruirse únicamente desde su URL y hash.

## 9. Reproducibilidad entre Entornos

- Un clon limpio del repositorio debe poder reconstruir los outputs reproducibles utilizando únicamente código versionado, dependencias declaradas y fuentes externas documentadas.

- No depender de archivos, configuraciones, paquetes o estados existentes únicamente en el computador de un desarrollador.

- Las carpetas necesarias deben ser creadas automáticamente por el código cuando no existan.

- Las configuraciones no sensibles necesarias para reproducir el proyecto deben estar versionadas.

- Secretos, tokens y credenciales nunca deben incluirse en el repositorio; deben recibirse mediante variables de entorno. Si en el futuro son necesarias, proporcionar `.env.example` sin valores sensibles.

- Todo algoritmo estocástico utilizado en modelamiento, validación o muestreo debe definir una semilla reproducible cuando técnicamente corresponda.

- Nunca asumir que una librería está instalada solo porque existe en el entorno local; toda dependencia permanente debe estar declarada en `requirements.txt`.