# Fuentes de datos y procedimiento reproducible de obtención

Este documento registra de dónde salen los datos de SAAD, cómo se obtienen de forma reproducible y cómo se comprueba que lo obtenido coincide con lo registrado. Los datos **no se versionan en Git**: lo que se versiona es el código que los descarga y el manifest que identifica cada archivo obtenido.

La fuente de verdad del detalle de cada etapa es [PIPELINE.md](../../PIPELINE.md). Las URLs de este documento son las que usa el código (`src/data/download_*.py`); si el código cambia, este documento debe actualizarse.

## 1. Política de datos RAW

| Carpeta | Contenido | ¿Versionada? |
|---|---|---|
| `data/raw/` | Archivos tal como los publica la fuente | **No.** Solo se versionan `data/raw/.gitkeep` y `data/raw/provenance_manifest.json` |
| `data/processed/` | Salidas del pipeline, regenerables | **No**, salvo `.gitkeep` y el pronóstico vigente (`data/processed/modeling/pronostico_demanda_sm.parquet` y su manifiesto) |
| `.cache/` | Descargas temporales (ZIP de transporte) | **No** |
| `reports/` | Reportes y métricas del análisis | Sí |

Reglas:

- **RAW no se versiona** (regla de `.gitignore`: `data/raw/*`). Motivos verificables: tamaño (`data/raw/` pesa unos 12 GB; las Atenciones de Urgencia son 9,1 GB) y que cualquiera puede reconstruirlo desde la fuente oficial con el procedimiento de este documento.
- Se conserva en `data/raw/` el archivo en su formato original. Los contenedores de transporte (`.zip`) no son RAW canónico: se descargan a `.cache/downloads/`, se validan y solo se publica el archivo extraído.
- Una descarga solo llega a `data/raw/` si pasa la validación de formato y esquema mínimo; si falla, el RAW existente no se toca.
- Todo snapshot publicado queda registrado en `data/raw/provenance_manifest.json` con URL, fecha, tamaño y SHA256.

## 2. Fuentes oficiales

Todas las etapas de descarga viven en `src/data/` y se ejecutan con `scripts/run_pipeline.py` (sección 3).

### 2.1 DEIS / MINSAL — Atenciones de Urgencia

- **Etapa:** `download_deis`. **Destino:** `data/raw/urgencias/AtencionesUrgencia<AAAA>.csv`.
- **Período disponible:** 2020 hasta el año corriente (hoy 2026). El año corriente es **parcial y mutable** (ver sección 5).
- **URLs (un ZIP por año):**
  - 2020-2022: `https://repositoriodeis.minsal.cl/DatosAbiertos/AtencionesDeUrgencia/AtencionesUrgencia<AAAA>.zip`
  - 2023 en adelante: `https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia<AAAA>.zip`
- El diccionario oficial (`DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx`) viaja dentro de los ZIP y se extrae junto al CSV.

### 2.2 DEIS / MINSAL — Egresos hospitalarios

- **Etapa:** `download_deis`. **Destino:** `data/raw/egresos/egresos_<AAAA>.csv`.
- **Período disponible:** 2020-2025.
- **URL (un ZIP por año):** `https://repositoriodeis.minsal.cl/DatosAbiertos/EGRESOS/EGRESOS_<AAAA>.zip`
- El diccionario (`Diccionario BD egresos hospitalario.xlsx`) se extrae del ZIP.

### 2.3 Catálogo de establecimientos de salud (DEIS, vía datos.gob.cl)

- **Etapa:** `download_establishments`. **Destino:** `data/raw/deis/establecimientos_salud_actualizado.csv`.
- **Período:** snapshot del catálogo vigente al publicar (el archivo enlazado es `establecimientos_20260825.csv`). No es una serie histórica.
- **URL:** `https://datos.gob.cl/dataset/3bf4cf7c-f638-4735-9a01-f65faae4beca/resource/2c44d782-3365-44e3-aefb-2c8b8363a1bc/download/establecimientos_20260825.csv`
- La URL está fijada a un archivo con fecha: para usar un catálogo más nuevo hay que actualizar `DEIS_URL` en `src/data/download_establishments.py`.

### 2.4 INE — Censo 2024

- **Cartografía censal.** Etapa `download_censo`. Destino `data/raw/censo/`.
  - **Período:** Censo 2024 (año cerrado).
  - **URL (un ZIP nacional):** `https://storage.googleapis.com/bktdescargascenso2024/Cartografia/GEOPARQUET/Cartografia_censo2024_Pais.zip`
  - Del ZIP se publican 5 capas (`Cartografia_censo2024_Pais_Comunal`, `_Distrital`, `_Zonal`, `_Entidades`, `_Manzanas`, en Parquet) y el diccionario `Diccionario_variables_geograficas_CPV24.xlsx`. El resto de los miembros del ZIP no se usa.
- **Población censada por sexo y edad.** Etapa `download_censo_poblacion`.
  - **Período:** Censo 2024 (año cerrado).
  - **URL:** `https://censo2024.ine.gob.cl/wp-content/uploads/2025/03/D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx`
  - **Destino:** `data/raw/censo/D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx`.

### 2.5 INE — Estimaciones y proyecciones de población comunal

- **Etapa:** `download_poblacion_proyecciones`. **Destino:** `data/raw/poblacion/ine_estimaciones_proyecciones_2002_2035_comunas.xlsx`.
- **Período:** 2002-2035 (base Censo 2017).
- **URL:** `https://www.ine.gob.cl/docs/default-source/proyecciones-de-poblacion/cuadros-estadisticos/base-2017/estimaciones-y-proyecciones-2002-2035-comunas.xlsx`

### 2.6 Ministerio de Desarrollo Social y Familia — Pobreza comunal (Casen 2022)

- **Etapa:** `download_pobreza_comunal`. **Destino:** `data/raw/pobreza/mds_casen_2022_tasa_pobreza_ingresos_comunal.xlsx`.
- **Período:** Casen 2022 (estimación para áreas pequeñas, SAE; período único).
- **URL:** `https://observatorio.ministeriodesarrollosocial.gob.cl/storage/docs/pobreza-comunal/2022/Estimaciones_Tasa_Pobreza_Ingresos_Comunas_2022.xlsx`

### 2.7 Estadísticas de Género — contexto de salud mental por sexo

- **Etapa:** `download_contexto_genero`. **Destino:** `data/raw/contexto_genero/<source_id>.xlsx`. Son contexto interpretativo: no se cruzan con Urgencias ni Egresos.
- **Cuatro cuadros** (períodos tal como los publica cada cuadro, sin convertirlos a un año artificial):

| `source_id` | URL | Cobertura temporal |
|---|---|---|
| `egresos_intento_suicida_sexo_anio` | `https://www.estadisticasdegenero.cl/wp-content/uploads/2023/11/Distribucion-y-razon-egresos-intento-suicida-3.xlsx` | Años 2006-2025 (el título del cuadro declara 2006-2024; la fila 2025 se conserva y la discrepancia está documentada) |
| `suicidio_ratio_hm_tasas_nacional_regional` | `https://www.estadisticasdegenero.cl/wp-content/uploads/2021/12/Ratio-hombre-mujer-y-tasas-de-defuncion-por-sucidio-Nacional-y-regional-4.xlsx` | Años 1997-2023 |
| `ansiedad_depresion_sintomas_18_mas_sexo` | `https://www.estadisticasdegenero.cl/wp-content/uploads/2022/08/personas-de-18-anos-o-mas-que-presentan-sintomas-moderados-o-severos-de-ansiedad-yo-depresion-por-sexo.xlsx` | Rondas sin año único: julio 2020, junio-julio 2021, noviembre-diciembre 2020, noviembre 2021 |
| `prevalencia_sintomas_depresivos_sexo` | `https://www.estadisticasdegenero.cl/wp-content/uploads/2021/11/Prevalencia-de-sintomas-depresivos-Nacional-1.xlsx` | Año 2003; períodos 2009-10 y 2016-17 |

- La URL del cuadro de suicidio conserva la errata "sucidio" porque es la que enlaza la página oficial; la variante corregida devuelve 404.

### 2.8 DEIS y DIGERA — Dotación de camas hospitalarias

- **Etapa:** `download_dotacion_camas`. **Destino:** `data/raw/camas/` (dos libros XLSX, cada uno validado y publicado de forma independiente).
- **Qué es:** dotación anual de camas hospitalarias declarada por establecimiento y área funcional. No es ocupación ni disponibilidad en tiempo real.
- **Dos libros:**

| Archivo en RAW | URL | Cobertura | Estructura |
|---|---|---|---|
| `dotacion_camas_snss_2010_2025.xlsx` | `https://repositoriodeis.minsal.cl/ContenidoSitioWeb2020/Estadisticas/DOTACION_CAMAS/Dotaci%C3%B3n%20de%20camas%202010-2025%20Establecimientos%20Pertenecientes%20al%20SNSS_01-12-2025.xlsx` | Establecimientos públicos (SNSS), 2010-2025 | Una hoja `2010-2025`, una columna por año |
| `dotacion_camas_no_snss_2019_2025.xlsx` | `https://repositoriodeis.minsal.cl/ContenidoSitioWeb2020/Estadisticas/DOTACION_CAMAS/Dotaci%C3%B3n%20de%20camas%202019-2025%20Establecimientos%20No%20pertenecientes%20al%20SNSS.xlsx` | Establecimientos privados (no SNSS), 2019-2025; "dato referencial" según la fuente, con la Superintendencia de Salud | Una hoja por año, `2019` a `2025` |

- **Procesamiento:** la etapa `clean_dotacion_camas` los convierte en un Parquet por libro en `data/processed/camas/` (ver `reports/dictionary/diccionario_dotacion_camas.md`).
- El RAW conserva ambos libros tal como vienen. Observado: el libro SNSS tiene 8 filas de nota al pie y filas `Total` por establecimiento mezcladas con el detalle por área funcional; el libro no SNSS tiene una fila `TOTAL` por hoja, notas al pie solo desde la hoja 2023 y 10 celdas con el texto `ok` (hojas 2024 y 2025, columna 12) de significado no documentado.
- El libro SNSS declara un total nacional de camas por año en una fila `Total País`; esa cifra no se ha contrastado todavía con la suma por establecimiento.

## 3. Procedimiento de descarga

Requisitos: Python 3.12 y las dependencias de `requirements.txt`; acceso a internet; espacio en disco (unos 12 GB de RAW).

```bash
python -m pip install -r requirements.txt

# Pipeline completo: descarga lo que falta y procesa
python scripts/run_pipeline.py

# Solo una descarga
python scripts/run_pipeline.py --stage download_deis
python scripts/run_pipeline.py --stage download_establishments
python scripts/run_pipeline.py --stage download_censo
python scripts/run_pipeline.py --stage download_censo_poblacion
python scripts/run_pipeline.py --stage download_poblacion_proyecciones
python scripts/run_pipeline.py --stage download_pobreza_comunal
python scripts/run_pipeline.py --stage download_dotacion_camas
python scripts/run_pipeline.py --stage download_contexto_genero
```

Comportamiento:

- **Idempotente:** si el RAW ya existe y es válido, la etapa hace `SKIP` y no consulta la fuente.
- **`--force`:** solicita explícitamente un snapshot nuevo y propaga la regeneración solo a las etapas que dependen de él. Úsalo con cuidado en las fuentes mutables (sección 5).
- **`--refresh-current-urgencias`:** vuelve a consultar el ZIP del año corriente de Urgencias y actualiza solo la rama afectada.
- **Descarga segura:** cada fuente se descarga a `.cache/downloads/`, se valida (ZIP íntegro, columnas requeridas, hojas del XLSX, geometría legible) y recién entonces se publica en `data/raw/`.

## 4. Manifest y hashes

`data/raw/provenance_manifest.json` es una lista JSON con una entrada por `source_id`. Es el único archivo de `data/raw/` que se versiona. Hoy registra 27 fuentes.

Formato actual (una entrada con historial de snapshots; lo escribe `record_raw_snapshot` en `src/data/raw_provenance.py`):

```json
{
  "source_id": "deis_urgencias_2025",
  "year": 2025,
  "snapshots": [
    {
      "source_url": "https://repositoriodeis.minsal.cl/SistemaAtencionesUrgencia/AtencionesUrgencia2025.zip",
      "downloaded_at": "2026-10-07T22:07:58.042344+00:00",
      "zip_filename": "deis_urgencias_2025_AtencionesUrgencia2025.zip",
      "zip_size": 55181481,
      "zip_sha256": "108d69520c4a496282ec63d46815e61bf0a7d6f120b333be643e44e62fb35c1e",
      "archive_member": "AtencionesUrgencia2025.csv",
      "raw_path": "data/raw/urgencias/AtencionesUrgencia2025.csv",
      "raw_size": 1939175001,
      "raw_sha256": "e37f91f02d55d18e5e141a354313bac42ef12361579c11eb31e1fe71f96134bb"
    }
  ]
}
```

- `raw_sha256` / `raw_size`: hash y tamaño del archivo publicado en `data/raw/`. Los ZIP de DEIS agregan `zip_sha256` / `zip_size` del contenedor y `archive_member`; los demás XLSX/Parquet registran el contenedor en `transport`.
- `downloaded_at`: marca UTC de la descarga. Cada descarga nueva **agrega** un snapshot; no reemplaza el anterior.
- El manifest no registra un hash propio para los diccionarios extraídos de los ZIP DEIS; sí lo hace para el ZIP y el CSV.
- Los Parquet de Urgencias procesados guardan en su metadato `raw_sha256` el hash del RAW desde el que se generaron, de modo que se puede saber si un procesado quedó desactualizado.

### Verificar que el RAW local coincide con el manifest

Desde la raíz del repositorio (tarda 1-2 minutos por el tamaño de los archivos):

```bash
python - <<'EOF'
import hashlib, json
from pathlib import Path

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()

ultimo = {}
for entrada in json.loads(Path("data/raw/provenance_manifest.json").read_text(encoding="utf-8")):
    snap = entrada["snapshots"][-1] if "snapshots" in entrada else entrada
    ultimo[entrada["source_id"]] = (snap["raw_path"], snap.get("raw_sha256") or snap["sha256"])

fallas = 0
for source_id, (ruta, esperado) in sorted(ultimo.items()):
    p = Path(ruta)
    estado = "FALTA" if not p.is_file() else ("OK" if sha256(p) == esperado else "DISTINTO")
    fallas += estado != "OK"
    print(f"{estado:9s} {source_id}")
print(f"{len(ultimo)} fuentes, {fallas} con diferencias")
EOF
```

`OK` indica que el archivo es idéntico al registrado. `DISTINTO` es esperable en las fuentes mutables si se descargó un snapshot posterior (sección 5); en una fuente de año cerrado indica un archivo alterado o corrupto.

## 5. Fuentes mutables y límites de la reproducibilidad

- **Atenciones de Urgencia del año corriente** (hoy 2026): el DEIS sobrescribe periódicamente el ZIP sin versionarlo. Dos descargas en fechas distintas pueden dar archivos distintos.
- **Catálogo de establecimientos:** es el catálogo "actualizado" publicado por DEIS, no un año cerrado.
- **Años cerrados** (Urgencias 2020-2025, Egresos 2020-2025, Censo 2024, proyecciones INE, Casen 2022, dotación de camas 2010-2025 y 2019-2025, cuadros de género): se espera que el hash no cambie.

El manifest identifica **qué** snapshot se usó (URL, fecha y hash), pero una URL con un hash **no permite reconstruir** una versión antigua de una fuente mutable si el proveedor ya la reemplazó. Por eso el manifest se versiona: es la evidencia de qué snapshot respalda cada resultado.

## 6. Observaciones verificadas sobre el manifest

- Los cuatro cuadros de Estadísticas de Género aparecen **dos veces** en la lista, ambas en el formato anterior (campos planos `sha256`, `downloaded_at` y `raw_path` en lugar de `snapshots`): una descarga del 2026-09-03 y otra del 2026-10-07. Los demás `source_id` ya usan el formato con `snapshots`. El script de verificación de la sección 4 admite ambos formatos y toma la última entrada de cada `source_id`.
- Con el manifest actual, las 27 fuentes coinciden con el RAW local.
