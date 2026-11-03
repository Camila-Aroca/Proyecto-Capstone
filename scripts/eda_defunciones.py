"""EDA de solo lectura de los CSV RAW de Defunciones, mediante streaming."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
import platform
import re
from typing import Any

from src.chile_time import run_date_chile
from src.data.download_defunciones import (
    CSV_COLUMNS, DEFUNCIONES_SOURCES, DEST_DIR, DICTIONARY_FILENAME, MAX_RAW_BYTES,
    validate_dictionary,
)
from src.data.raw_provenance import MANIFEST_PATH, file_sha256


REPORT_PATH = Path("reports/eda/eda_defunciones_raw.md")
SUMMARY_PATH = Path("reports/eda/eda_defunciones_raw_resumen.json")
TITLE = "# EDA RAW de Defunciones DEIS"
HEALTH_YEARS = range(2021, 2026)  # Ventana descriptiva explícita; no filtra los RAW.
CONTEXT_PATH = Path("data/processed/contexto_genero/suicidio_ratio_hm_tasas_nacional_regional.parquet")
HEALTH_FIELDS = ("f_diag1", "self_diag2", "self_diag1", "sequela_diag2", "undetermined_diag2")
logger = logging.getLogger(__name__)


@lru_cache(maxsize=65536)
def _parse_date(value: str) -> dt.date | None:
    """Formatos explícitos, sin reemplazar la fecha publicada."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def profile_csv(path: Path, *, expected_years: range) -> dict[str, Any]:
    """Escaneo completo, memoria acotada a agregados de cardinalidad limitada.

    No publica filas ni combinaciones individuales. Blancos y asteriscos se
    cuentan por separado; otros códigos publicados conservan su significado
    no determinado. No elimina duplicados ni construye unidades de paciente.
    """
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_RAW_BYTES:
        raise ValueError("Se requiere un archivo CSV regular de hasta 2 GiB.")
    blank = Counter(dict.fromkeys(CSV_COLUMNS, 0))
    asterisk = Counter(dict.fromkeys(CSV_COLUMNS, 0))
    years: Counter[str] = Counter()
    months: Counter[str] = Counter()
    sexes: Counter[str] = Counter()
    regions: Counter[str] = Counter()
    age_types: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    diagnostic_year: dict[str, Counter[str]] = defaultdict(Counter)
    health_annual: dict[str, Counter[str]] = defaultdict(Counter)
    f_categories: Counter[str] = Counter()
    f_labels: dict[str, Counter[str]] = defaultdict(Counter)
    health_sex = {key: Counter() for key in ("f", "self")}
    health_age = {key: Counter() for key in ("f", "self")}
    age_summary: dict[str, dict[str, Any]] = {}
    communes: set[str] = set()
    result: dict[str, Any] = {
        "rows": 0, "invalid_dates": 0, "date_year_mismatch": 0, "future_dates": 0,
        "invalid_commune_shape": 0, "rm_commune_prefix_rows": 0,
        "diag1_f_prefix": 0, "diag1_numeric": 0, "diag1_cie10_shape": 0,
        "diag2_cie10_shape": 0, "diag1_other_shape": 0,
    }
    earliest: dt.date | None = None
    latest: dt.date | None = None
    today = run_date_chile()
    cie10_shape = re.compile(r"[A-Z][0-9]{2}(?:\.?[0-9A-Z])?", re.ASCII)
    with path.open(encoding="latin-1", newline="") as handle:
        reader = csv.reader(handle, delimiter=";", strict=True)
        if next(reader, None) != CSV_COLUMNS:
            raise ValueError("Cabecera inesperada en Defunciones.")
        for row in reader:
            if len(row) != len(CSV_COLUMNS):
                raise ValueError(f"Número de columnas inválido en registro {result['rows'] + 1}.")
            year, date, sex, age_type, age, commune, _, region = row[:8]
            if not year.isdigit() or int(year) not in expected_years:
                raise ValueError("Año fuera del periodo esperado; no se filtran registros.")
            result["rows"] += 1
            years[year] += 1
            sexes[sex] += 1
            regions[region] += 1
            age_types[age_type] += 1
            locations[row[26]] += 1
            for column, value in zip(CSV_COLUMNS, row):
                if not value.strip():
                    blank[column] += 1
                elif value.strip() == "*":
                    asterisk[column] += 1
            parsed = _parse_date(date)
            if parsed is None:
                result["invalid_dates"] += 1
            else:
                result["date_year_mismatch"] += int(parsed.year != int(year))
                result["future_dates"] += int(parsed > today)
                earliest = min(earliest, parsed) if earliest else parsed
                latest = max(latest, parsed) if latest else parsed
                months[parsed.strftime("%Y-%m")] += 1
            if re.fullmatch(r"[0-9]{5}", commune):
                communes.add(commune)
                result["rm_commune_prefix_rows"] += int(commune.startswith("13"))
            else:
                result["invalid_commune_shape"] += 1
            summary = age_summary.setdefault(age_type, {"numeric": 0, "non_numeric": 0,
                                                        "min": None, "max": None,
                                                        "negative": 0, "literal_999": 0})
            try:
                quantity = int(age)
                summary["numeric"] += 1
                summary["min"] = min(summary["min"], quantity) if summary["min"] is not None else quantity
                summary["max"] = max(summary["max"], quantity) if summary["max"] is not None else quantity
                summary["negative"] += int(quantity < 0)
                summary["literal_999"] += int(age == "999")
            except ValueError:
                summary["non_numeric"] += 1
            diag1, diag2 = row[8], row[17]
            numeric = diag1.isascii() and diag1.isdigit()
            shaped = cie10_shape.fullmatch(diag1) is not None
            result["diag1_numeric"] += int(numeric)
            result["diag1_cie10_shape"] += int(shaped)
            result["diag2_cie10_shape"] += int(cie10_shape.fullmatch(diag2) is not None)
            result["diag1_f_prefix"] += int(diag1.startswith("F"))
            result["diag1_other_shape"] += int(bool(diag1.strip()) and not numeric and not shaped)
            diagnostic_year[year].update({"numeric": int(numeric), "cie10_shape": int(shaped),
                                          "f_prefix": int(diag1.startswith("F"))})
            # Solo forma explícita: no homologa códigos históricos ni valida catálogo clínico.
            c1 = diag1.replace(".", "") if shaped else ""
            c2 = diag2.replace(".", "") if cie10_shape.fullmatch(diag2) else ""
            self1 = bool(c1 and c1[0] == "X" and 60 <= int(c1[1:3]) <= 84)
            self2 = bool(c2 and c2[0] == "X" and 60 <= int(c2[1:3]) <= 84)
            is_f = c1.startswith("F")
            flags = (is_f, self2, self1, c2 == "Y870",
                     bool(c2 and c2[0] == "Y" and 10 <= int(c2[1:3]) <= 34))
            rm = region == "Metropolitana de Santiago"
            for field, flag in zip(HEALTH_FIELDS, flags):
                health_annual[year][field] += int(flag)
                health_annual[year]["rm_" + field] += int(flag and rm)
            if int(year) in HEALTH_YEARS:
                if is_f:
                    f_categories[c1[:3]] += 1
                    f_labels[c1[:3]][row[14]] += 1
                for key, flag in (("f", is_f), ("self", self2)):
                    if not flag:
                        continue
                    health_sex[key][sex] += 1
                    band = "otra_unidad_o_no_interpretable"
                    if age_type == "1" and age.isascii() and age.isdigit():
                        value = int(age)
                        band = ("0-14" if value < 15 else "15-29" if value < 30 else
                                "30-44" if value < 45 else "45-64" if value < 65 else "65+")
                    health_age[key][band] += 1
            if (is_f and sum(len(values) for values in f_labels.values()) > 4096
                    or any(len(values) > 4096 for values in health_sex.values())):
                raise ValueError("Cardinalidad inesperada en agregados de salud mental.")
            # Ningún campo libre puede crecer sin límite como clave de Counter.
            if any(len(counter) > 4096 for counter in (sexes, regions, age_types, locations)) or len(communes) > 4096:
                raise ValueError("Cardinalidad inesperada: se detiene el perfil sin publicar valores libres.")
    if not result["rows"]:
        raise ValueError("CSV sin registros.")
    result.update({
        "columns": CSV_COLUMNS, "encoding": "latin-1", "delimiter": ";",
        "blank": dict(blank), "asterisk": dict(asterisk),
        "years": dict(sorted(years.items())), "months_by_valid_date": dict(sorted(months.items())),
        "sexes": dict(sexes), "regions": dict(regions), "age_types": dict(age_types),
        "age_quantity_by_type": age_summary, "locations": dict(locations),
        "unique_well_formed_communes": len(communes),
        "min_date": earliest.isoformat() if earliest else None,
        "max_date": latest.isoformat() if latest else None,
        "missing_expected_years": sorted(set(expected_years) - {int(year) for year in years}),
        "diagnostic_by_year": {year: dict(counts) for year, counts in sorted(diagnostic_year.items())},
        "scope": "complete_file_streaming_no_sampling",
        "mental_health": {
            "annual": dict(sorted(health_annual.items())),
            "f_categories": dict(f_categories),
            "f_category_labels": {code: dict(counts) for code, counts in f_labels.items()},
            "sex": health_sex, "age": health_age,
        },
    })
    return result


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    def escape(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
            *["| " + " | ".join(escape(value) for value in row) + " |" for row in rows], ""]


def _health_totals(payload: dict[str, Any]) -> dict[str, Any]:
    annual: dict[str, Counter[str]] = defaultdict(Counter)
    categories: Counter[str] = Counter()
    labels: dict[str, Counter[str]] = defaultdict(Counter)
    sex = {key: Counter() for key in ("f", "self")}
    age = {key: Counter() for key in ("f", "self")}
    for entry in payload["sources"].values():
        health = entry["profile"]["mental_health"]
        for year, counts in health["annual"].items():
            annual[year].update(counts)
        categories.update(health.get("f_categories", {}))
        for code, counts in health.get("f_category_labels", {}).items():
            labels[code].update(counts)
        for key in sex:
            sex[key].update(health.get("sex", {}).get(key, {}))
            age[key].update(health.get("age", {}).get(key, {}))
    return {"annual": annual, "categories": categories, "labels": labels, "sex": sex, "age": age}


def compare_suicide_context(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    """Contraste agregado opcional; no enlaza registros ni exige descargar otra fuente."""
    if not path.is_file():
        return {"status": "not_available", "path": path.as_posix()}
    import pyarrow.parquet as pq

    if path.is_symlink() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Fuente contextual fuera del límite de lectura.")
    frame = pq.read_table(path, columns=["year", "sex", "indicator", "geography_level",
                                         "region_code", "value"]).to_pandas()
    annual = _health_totals(payload)["annual"]
    comparisons = []
    seen: set[tuple[str, str]] = set()
    for row in frame.itertuples(index=False):
        if row.indicator != "defunciones_suicidio" or row.sex != "Total":
            continue
        scope = ("Nacional" if row.geography_level == "nacional" else
                 "RM" if row.geography_level == "regional" and row.region_code == 13 else None)
        year = str(int(row.year))
        if scope is None or year not in annual:
            continue
        if (year, scope) in seen:
            raise ValueError("Observaciones contextuales duplicadas para año y ámbito.")
        seen.add((year, scope))
        if row.value < 0 or not float(row.value).is_integer():
            raise ValueError("Conteo contextual no entero/no negativo.")
        comparisons.append({"year": year, "scope": scope,
                            "raw": annual[year]["self_diag2" if scope == "Nacional" else "rm_self_diag2"],
                            "context": int(row.value)})
    differences = [item for item in comparisons if item["raw"] != item["context"]]
    return {"status": "compared", "path": path.as_posix(), "sha256": file_sha256(path),
            "compared": len(comparisons), "matched": len(comparisons) - len(differences),
            "comparisons": comparisons, "differences": differences}


def _health_report(payload: dict[str, Any]) -> list[str]:
    totals = _health_totals(payload)
    annual, categories = totals["annual"], totals["categories"]
    period = Counter()
    for year in HEALTH_YEARS:
        period.update(annual.get(str(year), {}))

    def percent(numerator: int, denominator: int) -> str:
        return f"{100 * numerator / denominator:.1f}%" if denominator else "no calculable (sin registros)"

    sections = ["## Hallazgos de salud mental y suicidio", "",
        "Ventana descriptiva predefinida: 2021–2025 (AÑO publicado). Se mantienen todas las causas y años "
        "en el escaneo; esta ventana solo delimita las tablas de composición. No se certifica el cierre de "
        "2024–2025. Los conteos son registros publicados, no tasas ni estimaciones de riesgo.", "",
        "### Definiciones y territorio", "",
        "El manual DEIS incluido en cada paquete indica consultar DIAG1 para enfermedades y DIAG2 "
        "entre X60 y X84 para suicidio. Se cuenta F00–F99 por forma explícita en DIAG1, X60–X84 en DIAG2, "
        "Y87.0 por separado como secuelas y Y10–Y34 como intención no determinada, sin reclasificarla como suicidio. "
        "Se aceptan códigos de tres/cuatro caracteres y punto opcional, sin cambiar el RAW; no se valida cada "
        "subcategoría contra un catálogo. RM se define por NOMBRE_REGION igual a `Metropolitana de Santiago`, "
        "territorio de residencia según el diccionario; no se usa la ubicación de un hospital.", "",
        "[OMS: capítulo F00–F09 y demencias](https://icd.who.int/browse10/2019/en/GetConcept?ConceptId=F00-F09). "
        "[OMS: agrupaciones de mortalidad, X60–X84 y Y87.0](https://platform.who.int/mortality/about/list-of-causes-and-corresponding-icd-10-codes).", "",
        "### Conteos anuales nacionales y de residentes RM", ""]
    fields = ("f_diag1", "rm_f_diag1", "self_diag2", "rm_self_diag2")
    sections += _table(["Año", "F DIAG1 nacional", "F DIAG1 RM", "X60–X84 DIAG2 nacional", "X60–X84 DIAG2 RM"], [
        [year, *[annual.get(str(year), {}).get(field, 0) for field in fields]] for year in HEALTH_YEARS
    ] + [["Total 2021–2025", *[period[field] for field in fields]]])
    sections += ["### Composición de DIAG1 F00–F99", ""]
    sections += _table(["Categoría", "Glosa publicada (sin reconstruir)", "Registros 2021–2025"], [
        [code, label or "(blanco)", n] for code, _ in categories.most_common()
        for label, n in sorted(totals["labels"][code].items())
    ])
    dementia = categories["F01"] + categories["F03"]
    sections += [f"F01 y F03 reúnen {dementia} registros ({percent(dementia, period['f_diag1'])} del conjunto F). "
        f"Las edades publicadas de 65 años o más reúnen {totals['age']['f']['65+']} registros "
        f"({percent(totals['age']['f']['65+'], period['f_diag1'])}). "
        "El indicador agregado F refleja principalmente demencias en este snapshot; conviene distinguirlas "
        "de sustancias y otros trastornos. Un conteo DIAG1 F32 no equivale a todas las muertes de personas "
        "con depresión: no existe historia clínica completa en estos campos.", "",
        "### Sexo y edad: conjuntos separados", ""]
    for key, title in (("f", "DIAG1 F"), ("self", "DIAG2 X60–X84")):
        denominator = period["f_diag1" if key == "f" else "self_diag2"]
        sections += _table([f"{title}: sexo publicado", "Registros", "% del conjunto"], [
            [label or "(blanco)", n, percent(n, denominator)] for label, n in sorted(totals["sex"][key].items())])
        sections += _table([f"{title}: edad en años", "Registros"], [
            [label, n] for label, n in sorted(totals["age"][key].items())])
    sections += ["La edad solo se agrupa cuando EDAD_TIPO=1 y EDAD_CANT contiene un entero no negativo. "
        "Otras unidades/valores no interpretables se conservan en categoría separada; no se convierten meses "
        "a años ni se imputan edades.", "",
        f"En 2021–2025 se observan {period['self_diag1']} códigos X60–X84 en DIAG1 y "
        f"{period['self_diag2']} en DIAG2. Un filtro exclusivo F00–F99 en DIAG1 deja fuera la "
        "definición de suicidio del manual. Esta separación no permite inferir antecedentes psiquiátricos.", "",
        f"Y87.0 en DIAG2: {period['sequela_diag2']} registros nacionales y {period['rm_sequela_diag2']} RM. "
        f"Y10–Y34 en DIAG2: {period['undetermined_diag2']} nacionales y {period['rm_undetermined_diag2']} RM. "
        "No se suman los eventos de intención no determinada a suicidio.", "",
        "### Comparabilidad histórica", "",
        "Los códigos numéricos históricos no se interpretan como CIE-10; la ausencia de F/X con forma "
        "CIE-10 en esos años no acredita ausencia de casos. La siguiente tabla permite inspeccionar "
        "cambios en intención no determinada sin atribuirlos a cambios reales del riesgo:", ""]
    sections += _table(["Año", "X60–X84 DIAG2 nacional", "X60–X84 DIAG2 RM", "Y10–Y34 nacional", "Y10–Y34 RM"], [
        [year, *[counts.get(field, 0) for field in ("self_diag2", "rm_self_diag2", "undetermined_diag2", "rm_undetermined_diag2")]]
        for year, counts in sorted(annual.items())])
    sections += ["2026 es parcial; consultar el corte observado en las secciones por paquete. "
        "No comparar directamente años parciales y completos ni inferir tendencias de riesgo desde "
        "estos conteos: se requieren denominadores y ajustes apropiados. La causa de diferencias históricas "
        "y la magnitud del subregistro no son identificables aquí. No es posible determinarlo con los datos disponibles.", "",
        "### Contraste con Estadísticas de Género", ""]
    comparison = payload["suicide_context_comparison"]
    if comparison["status"] == "compared":
        sections += [f"Comprobación agregada opcional contra `{comparison['path']}` "
            f"(SHA256 `{comparison['sha256']}`). Coinciden {comparison['matched']} de "
            f"{comparison['compared']} comparaciones año × ámbito disponibles. "
            "Se comparan conteos Total nacionales y RM de defunciones_suicidio con X60–X84 en DIAG2; "
            "no se enlazan personas ni se incorporan variables al modelo.", ""]
        sections += _table(["Año", "Ámbito", "RAW X60–X84", "Contexto", "Coincide"], [
            [item["year"], item["scope"], item["raw"], item["context"], item["raw"] == item["context"]]
            for item in comparison["comparisons"]])
        sections += ["Las discrepancias se conservan; no se corrigen ni se atribuyen automáticamente a Y87.0, "
            "subregistro o revisiones. No es posible determinarlo con los datos disponibles.", ""]
    else:
        sections += ["Fuente contextual no disponible localmente: no se realizó el contraste. "
            "El stage no descarga ni genera esta fuente independiente.", ""]
    sections += ["### Alcance para el proyecto", "",
        "Defunciones puede aportar resultados de mortalidad territorial complementarios a atenciones de "
        "Urgencias y hospitalizaciones de Egresos, preservando sus distintos granos. No permite concluir "
        "que quienes consultaron posteriormente fallecieron ni enlazar trayectorias individuales. "
        "No se crea integración, feature ni modelo de mortalidad con este EDA.", ""]
    return sections


def build_report(payload: dict[str, Any]) -> str:
    sections = [TITLE, "", "## Alcance y método", "",
        "Perfil exploratorio nacional de los dos paquetes publicados por DEIS. "
        "Grano: una fila del CSV de defunciones disociadas publicado; no representa personas enlazables. "
        "Escaneo completo por streaming de los archivos, sin muestreo ni carga integral en memoria. "
        "Se conserva toda la fuente, sin filtrar RM, causas ni años, sin imputar ni deduplicar. "
        "No hay joins, modelos, tasas ni outputs processed.", "",
        f"Generado UTC: `{payload['generated_at']}`. Python: `{payload['python_version']}`. "
        "Parser estándar `csv`, delimitador `;`, lectura `latin-1` consistente con los bytes de la cabecera `AÑO`. "
        "No se recodifican los archivos. Límite por CSV: 2 GiB; campos categóricos y comunas: hasta 4.096 "
        "valores por agregado; caché de fechas: 65.536 valores. Los excesos detienen el proceso.", "",
        "Reproducción: `python scripts/run_pipeline.py --stage download_defunciones`; "
        "para regenerar solo el perfil: `python scripts/run_pipeline.py --stage eda_defunciones --force`.", "",
        "## Semántica y limitaciones de la documentación fuente", "",
        "Los XLSX incluidos se conservan íntegros, uno por paquete. Su título declara 2016–2020 "
        "y sus nombres `ANO_DEF`, `GLOSA_SEXO`, `CODIGO_COMUNA_RESIDENCIA`, "
        "`GLOSA_COMUNA_RESIDENCIA` y `GLOSA_REG_RES` difieren de los nombres actuales "
        "`AÑO`, `SEXO_NOMBRE`, `COD_COMUNA`, `COMUNA` y `NOMBRE_REGION`. La correspondencia "
        "por posición/tema es una interpretación para este perfil, no una homologación oficial del esquema. "
        "El diccionario describe territorio de residencia, no ubicación de un hospital.", "",
        "El manual distingue `DIAG1` (causa básica) de `DIAG2` (causa externa) y orienta a usar "
        "DIAG2 para causas externas. `EDAD_TIPO` expresa la unidad: 1 años, 2 meses, 3 días, "
        "4 horas y 0 ignorado. Por ello `EDAD_CANT` se describe por unidad y no se mezcla en un promedio. "
        "El diccionario llama a EDAD_CANT edad al ingreso, texto que resulta discordante con el tema "
        "de defunciones y se conserva sin corregir.", "",
        "La forma alfanumérica de un código no certifica pertenencia a un catálogo CIE-10. "
        "Los códigos numéricos históricos no se homologan ni se interpretan como CIE-10; "
        "no se ha verificado su clasificación con un catálogo específico. Los registros con prefijo F "
        "son únicamente un conteo textual exploratorio, no un dataset clínico F00–F99. "
        "La sección de salud mental añade reglas explícitas de forma y campo para F y suicidio.", "",
        "Se distinguen celdas blancas y el marcador literal `*`; no se asume que otros códigos "
        "como 0, 99 o 999 sean ausentes. `COD_COMUNA` se audita por forma de cinco dígitos, "
        "sin certificar vigencia territorial. El prefijo 13 se cuenta como indicador de formato RM "
        "sin cruzar con el catálogo territorial.", "",
        "El paquete 1990–2023 se rotula como cifras oficiales según su nombre. "
        "El paquete 2024–2026 es un snapshot fechado 27/10/2026: no se afirma que 2024 o 2025 "
        "estén consolidados y 2026 no constituye un año completo. La fecha máxima observada "
        "se calcula desde FECHA_DEF y no se deduce de la URL. No se comparan conteos parciales "
        "con años completos para inferir tendencias.", "",
        "La validación estructural no acredita exhaustividad respecto del registro nacional. "
        "No se auditan duplicados exactos ni identificadores únicos; filas idénticas pueden "
        "representar defunciones distintas y no se eliminan. El subregistro y las causas de "
        "ausencia/anomalías no son determinables con estos archivos por sí solos. "
        "No es posible determinarlo con los datos disponibles.", ""]
    for key, entry in payload["sources"].items():
        profile = entry["profile"]
        sections.extend([f"## Observaciones: {key}", "",
            f"Fuente: [ZIP oficial DEIS]({entry['source_url']}). RAW: `{entry['raw_path']}`.", "",
            f"Filas leídas: **{profile['rows']:,}**. Columnas: **{len(profile['columns'])}**. "
            f"Fechas válidas: `{profile['min_date']}` a `{profile['max_date']}`. "
            f"Años esperados sin filas: `{profile['missing_expected_years']}`.", "",
            f"SHA256 CSV: `{entry['raw_sha256']}`. Tamaño: {entry['raw_size']:,} bytes. "
            f"SHA256 diccionario: `{entry['dictionary_sha256']}`. "
            f"Procedencia coincide con el último snapshot registrado: **{entry['provenance_matches']}**.", ""])
        sections.extend(_table(["Control", "Registros"], [
            ["Fecha no interpretable con los tres formatos declarados", profile["invalid_dates"]],
            ["Año de FECHA_DEF distinto de AÑO", profile["date_year_mismatch"]],
            ["Fecha posterior a fecha civil de ejecución en Chile", profile["future_dates"]],
            ["COD_COMUNA sin forma de cinco dígitos (incluye blanco)", profile["invalid_commune_shape"]],
            ["COD_COMUNA de cinco dígitos con prefijo 13", profile["rm_commune_prefix_rows"]],
            ["Comunas distintas con forma de cinco dígitos", profile["unique_well_formed_communes"]],
            ["DIAG1 numérico", profile["diag1_numeric"]],
            ["DIAG1 con forma CIE-10, sin validar catálogo", profile["diag1_cie10_shape"]],
            ["DIAG1 no blanco con otra forma (incluye *)", profile["diag1_other_shape"]],
            ["DIAG1 con prefijo textual F", profile["diag1_f_prefix"]],
            ["DIAG2 con forma CIE-10, sin validar catálogo", profile["diag2_cie10_shape"]],
        ]))
        sections.extend(["### Cobertura anual y forma diagnóstica", ""])
        sections.extend(_table(["AÑO publicado", "Filas", "DIAG1 numérico", "DIAG1 forma CIE-10", "Prefijo F"], [
            [year, count, profile["diagnostic_by_year"][year]["numeric"],
             profile["diagnostic_by_year"][year]["cie10_shape"], profile["diagnostic_by_year"][year]["f_prefix"]]
            for year, count in profile["years"].items()
        ]))
        sections.extend(["### Ausencias y marcadores, sin recodificar", ""])
        sections.extend(_table(["Columna", "Blancos", "Blancos %", "Literal *"], [
            [column, profile["blank"][column], f"{100 * profile['blank'][column] / profile['rows']:.3f}",
             profile["asterisk"][column]] for column in CSV_COLUMNS
        ]))
        for title, field in (("Sexo publicado", "sexes"), ("Región publicada", "regions"),
                             ("Lugar de defunción publicado", "locations")):
            sections.extend([f"### {title}", ""])
            sections.extend(_table(["Valor agregado", "Filas"], [
                [value or "(blanco)", count] for value, count in sorted(profile[field].items())
            ]))
        sections.extend(["### Cantidad de edad por unidad publicada", ""])
        sections.extend(_table(["EDAD_TIPO", "Filas", "Mínimo", "Máximo", "No numérico", "Negativo", "Literal 999"], [
            [unit or "(blanco)", profile["age_types"][unit], stats["min"], stats["max"],
             stats["non_numeric"], stats["negative"], stats["literal_999"]]
            for unit, stats in sorted(profile["age_quantity_by_type"].items())
        ]))
    sections.extend(_health_report(payload))
    sections.extend(["## Evidencia complementaria", "",
        "`eda_defunciones_raw_resumen.json` contiene los mismos agregados, los conteos mensuales "
        "por fecha válida y los hashes de ambos archivos por paquete. Los agregados anuales usan "
        "AÑO; los mensuales usan FECHA_DEF válida, incluso si difiere de AÑO. "
        "No se crean tablas analíticas, integraciones con otras fuentes ni archivos processed.", ""])
    return "\n".join(sections)


def validate_summary(path: Path) -> None:
    """Contrato mínimo del resumen: dos fuentes, hashes y agregados reconciliados."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), dict):
        raise ValueError("Resumen EDA sin fuentes.")
    if set(payload["sources"]) != {source.key for source in DEFUNCIONES_SOURCES}:
        raise ValueError("Resumen EDA no contiene ambos paquetes configurados.")
    if not payload.get("generated_at") or not payload.get("python_version"):
        raise ValueError("Resumen EDA sin metadatos de ejecución.")
    if payload.get("mental_health_years") != list(HEALTH_YEARS):
        raise ValueError("Resumen EDA sin ventana de salud mental vigente.")
    comparison = payload.get("suicide_context_comparison", {})
    if comparison.get("status") not in {"compared", "not_available"}:
        raise ValueError("Resumen EDA sin estado del contraste contextual.")
    # El input opcional participa en la vigencia de SKIP, sin descargar otra rama.
    if CONTEXT_PATH.is_file():
        if comparison.get("sha256") != file_sha256(CONTEXT_PATH):
            raise ValueError("Contraste contextual desactualizado.")
    elif comparison.get("status") != "not_available":
        raise ValueError("Fuente contextual del resumen ya no está disponible.")
    for source in DEFUNCIONES_SOURCES:
        entry = payload["sources"][source.key]
        for field in ("raw_sha256", "dictionary_sha256"):
            if re.fullmatch(r"[0-9a-f]{64}", entry.get(field, "")) is None:
                raise ValueError("Resumen EDA sin hashes válidos.")
        profile = entry.get("profile", {})
        rows = profile.get("rows")
        if type(rows) is not int or rows <= 0 or not entry.get("provenance_matches"):
            raise ValueError("Resumen EDA sin registros/procedencia verificados.")
        if profile.get("columns") != CSV_COLUMNS or profile.get("scope") != "complete_file_streaming_no_sampling":
            raise ValueError("Resumen EDA sin esquema/alcance esperado.")
        if not profile.get("years") or sum(profile["years"].values()) != rows:
            raise ValueError("Conteos anuales del EDA no reconcilian.")
        health = profile.get("mental_health", {})
        annual = health.get("annual", {})
        if set(annual) != set(profile["years"]):
            raise ValueError("Años de salud mental no reconcilian con cobertura.")
        for year, counts in annual.items():
            expected = {*HEALTH_FIELDS, *("rm_" + field for field in HEALTH_FIELDS)}
            if set(counts) != expected or any(type(n) is not int or not 0 <= n <= profile["years"][year]
                                             for n in counts.values()):
                raise ValueError("Conteos anuales de salud mental inválidos.")
            if any(counts["rm_" + field] > counts[field] for field in HEALTH_FIELDS):
                raise ValueError("Conteos RM exceden el total nacional.")
        for key, field in (("f", "f_diag1"), ("self", "self_diag2")):
            total = sum(counts[field] for year, counts in annual.items() if int(year) in HEALTH_YEARS)
            for dimension in ("sex", "age"):
                if sum(health.get(dimension, {}).get(key, {}).values()) != total:
                    raise ValueError("Composición de salud mental no reconcilia.")
            if key == "f":
                if sum(health.get("f_categories", {}).values()) != total:
                    raise ValueError("Categorías F no reconcilian.")
                for code, n in health["f_categories"].items():
                    if sum(health.get("f_category_labels", {}).get(code, {}).values()) != n:
                        raise ValueError("Glosas F no reconcilian.")
        for field in ("sexes", "regions", "age_types", "locations"):
            if sum(profile.get(field, {}).values()) != rows:
                raise ValueError("Conteos categóricos del EDA no reconcilian.")
        for field in ("blank", "asterisk"):
            counts = profile.get(field, {})
            if set(counts) != set(CSV_COLUMNS) or any(type(count) is not int or not 0 <= count <= rows
                                                    for count in counts.values()):
                raise ValueError("Conteos de ausencias del EDA inválidos.")


def generate_report() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python_version": platform.python_version(), "sources": {},
        "mental_health_years": list(HEALTH_YEARS),
    }
    for source in DEFUNCIONES_SOURCES:
        raw = DEST_DIR / source.key / source.csv_filename
        dictionary = raw.parent / DICTIONARY_FILENAME
        validate_dictionary(dictionary)
        logger.info("Perfilando %s por streaming", raw.as_posix())
        profile = profile_csv(raw, expected_years=range(source.first_year, source.last_year + 1))
        raw_hash, dictionary_hash = file_sha256(raw), file_sha256(dictionary)
        matches = []
        for suffix, digest in (("", raw_hash), ("_dictionary", dictionary_hash)):
            entries = [entry for entry in manifest if entry.get("source_id") == source.source_id + suffix]
            snapshots = entries[0].get("snapshots", []) if entries else []
            matches.append(bool(snapshots and snapshots[-1].get("raw_sha256") == digest))
        if not all(matches):
            raise ValueError(f"RAW sin procedencia vigente: {source.key}")
        payload["sources"][source.key] = {
            "source_url": source.url, "raw_path": raw.as_posix(), "raw_size": raw.stat().st_size,
            "raw_sha256": raw_hash, "dictionary_sha256": dictionary_hash,
            "provenance_matches": all(matches), "profile": profile,
        }
    payload["suicide_context_comparison"] = compare_suicide_context(payload, CONTEXT_PATH)
    outputs = {REPORT_PATH: build_report(payload),
               SUMMARY_PATH: json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"}
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    logger.info("EDA publicado en %s", REPORT_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Aceptado por el orquestador; regenera el perfil.")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_report()


if __name__ == "__main__":
    main()
