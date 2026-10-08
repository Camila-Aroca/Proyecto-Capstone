"""Contratos mínimos de outputs de datos usados por el orquestador para SKIP/éxito.

Los schemas Arrow explícitos se importan de sus productores. Para outputs creados
con pandas, solo se comprueban columnas y familias de tipos que el productor
construye de manera determinista; no se infiere un contrato desde archivos locales.
"""

from __future__ import annotations

import csv
import json
from itertools import islice
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def _type_matches(actual: pa.DataType, expected: pa.DataType | str) -> bool:
    if isinstance(expected, pa.DataType):
        if pa.types.is_string(expected):
            return pa.types.is_string(actual) or pa.types.is_large_string(actual)
        return actual.equals(expected)
    predicates = {
        "string": lambda value: pa.types.is_string(value) or pa.types.is_large_string(value),
        "integer": pa.types.is_integer,
        "floating": pa.types.is_floating,
        "boolean": pa.types.is_boolean,
        "binary": lambda value: pa.types.is_binary(value) or pa.types.is_large_binary(value),
    }
    return predicates[expected](actual)


def _require_parquet(path: Path, fields: dict[str, pa.DataType | str]) -> None:
    actual = pq.read_schema(path)
    for name, expected in fields.items():
        if name not in actual.names or not _type_matches(actual.field(name).type, expected):
            raise ValueError(f"{path.name}: columna/tipo esperado {name}: {expected}")


def _require_csv(path: Path, columns: set[str], *, delimiter: str = ",",
                 numeric: set[str] | None = None,
                 floating: set[str] | None = None,
                 text: set[str] | None = None,
                 not_null: set[str] | None = None,
                 all_rows: bool = False,
                 allow_empty: bool = False) -> None:
    with path.open("r", encoding="latin-1" if delimiter == ";" else "utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not columns.issubset(reader.fieldnames or []):
            raise ValueError(f"{path.name}: columnas faltantes: {sorted(columns - set(reader.fieldnames or []))}")
        rows = reader if all_rows else islice(reader, 32)
        seen = False
        for row in rows:
            seen = True
            if None in row or any(row.get(name) is None for name in columns):
                raise ValueError(f"{path.name}: fila con columnas inválidas")
            if any(not row[name].strip() for name in not_null or ()):
                raise ValueError(f"{path.name}: valor obligatorio vacío")
            for name in numeric or ():
                if row[name].strip():
                    int(row[name])
            for name in floating or ():
                if row[name].strip():
                    float(row[name])
            for name in text or ():
                if not row[name].strip():
                    raise ValueError(f"{path.name}: valor vacío en {name}")
        if all_rows and not seen and not allow_empty:
            raise ValueError(f"{path.name}: sin filas")


def _require_selection(path: Path) -> None:
    """Campos publicados por el benchmark y leídos por holdout/API."""
    selection = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        "modelo_recomendado": str,
        "construible": bool,
        "criterio": str,
        "nivel_intervalo": (int, float),
        "horizontes": list,
        "semilla": int,
        "periodo_backtest": dict,
        "metricas_backtest": dict,
    }
    if not isinstance(selection, dict):
        raise ValueError(f"{path.name}: selección no es objeto JSON")
    for name, kind in fields.items():
        if name not in selection:
            raise ValueError(f"{path.name}: campo inválido {name}")
        value = selection[name]
        if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
            raise ValueError(f"{path.name}: tipo inválido {name}")
    if not selection["modelo_recomendado"] or not selection["horizontes"] or not all(
        type(value) is int for value in selection["horizontes"]
    ):
        raise ValueError(f"{path.name}: modelo u horizontes inválidos")
    for name in ("ano_min", "ano_max", "origenes", "paso", "t_primer_origen", "t_ultimo_origen"):
        if type(selection["periodo_backtest"].get(name)) is not int:
            raise ValueError(f"{path.name}: período inválido {name}")
    for name in ("mase_region", "mase_comuna", "cobertura_region", "cobertura_comuna"):
        value = selection["metricas_backtest"].get(name)
        if type(value) not in (int, float):
            raise ValueError(f"{path.name}: métrica inválida {name}")


def _require_report(path: Path, title: str) -> None:
    if not path.read_text(encoding="utf-8").startswith(title):
        raise ValueError(f"{path.name}: encabezado inesperado")


def _require_forecast_manifest(path: Path) -> None:
    """Valida el manifiesto del pronóstico persistido, incluida su vigencia.

    La vigencia es parte del contrato: un pronóstico generado sobre un panel o una
    selección que ya cambiaron no es un output válido, y el orquestador debe
    regenerarlo en lugar de conservarlo.
    """
    from src.models.persistence import motivo_desactualizacion

    manifiesto = json.loads(path.read_text(encoding="utf-8"))
    requeridas = {"generado_en_utc", "modelo", "nivel_intervalo", "horizontes", "entradas", "filas"}
    faltantes = requeridas - set(manifiesto)
    if faltantes:
        raise ValueError(f"{path.name}: faltan claves {sorted(faltantes)}")
    motivo = motivo_desactualizacion(manifiesto)
    if motivo is not None:
        raise ValueError(f"{path.name}: pronóstico desactualizado ({motivo})")


def validate_expected_schema(path: Path) -> bool:
    """Valida outputs conocidos; False deja el control genérico al orquestador."""
    name = path.name
    parts = set(path.parts)

    reports = {
        "eda_series_demanda_sm.md": "# EDA de series temporales: demanda de urgencia en salud mental (RM)",
        "benchmark_demanda_sm.md": "# Benchmark de modelos de demanda de urgencia en salud mental (RM)",
        "holdout_demanda_sm.md": "# Evaluacion en holdout del modelo de demanda de urgencia en salud mental",
    }
    if name in reports:
        _require_report(path, reports[name])
        return True
    if name == "eda_series_demanda_sm_resumen.csv":
        _require_csv(path, {"metrica", "valor"}, floating={"valor"},
                     text={"metrica"}, all_rows=True)
        return True
    if name in {"benchmark_demanda_sm_resumen.csv", "holdout_demanda_sm_resumen.csv"}:
        _require_csv(path, {"series_id", "horizonte", "n", "mae", "rmse",
                            "mape_pct", "mase", "cobertura", "cobertura_nominal",
                            "amplitud_media", "modelo"},
                     numeric={"horizonte", "n"},
                     floating={"mae", "rmse", "mape_pct", "mase", "cobertura",
                               "cobertura_nominal", "amplitud_media"},
                     text={"series_id", "modelo"},
                     not_null={"horizonte", "n", "cobertura"}, all_rows=True)
        return True
    if name == "benchmark_demanda_sm_seleccion.json":
        _require_selection(path)
        return True
    if name == "pronostico_demanda_sm.parquet":
        from src.models.persistence import ESQUEMA
        _require_parquet(path, {campo.name: campo.type for campo in ESQUEMA})
        return True
    if name == "pronostico_demanda_sm_manifest.json":
        _require_forecast_manifest(path)
        return True

    if name.startswith("AtencionesUrgencia") and name.endswith(".csv"):
        from src.data.download_deis_sources import URGENCIAS_REQUIRED_COLUMNS
        _require_csv(path, URGENCIAS_REQUIRED_COLUMNS, delimiter=";",
                     numeric={"IdCausa", "Total", "semana"})
        return True
    if name.startswith("egresos_") and name.endswith(".csv") and "raw" in parts:
        _require_csv(path, {"ANO_EGRESO", "DIAG1"}, delimiter=";")
        return True
    if name == "establecimientos_salud_actualizado.csv":
        from src.data.download_establishments import validate_and_preview
        validate_and_preview(path)
        return True
    if name.endswith(".xlsx") and "raw" in parts:
        if name == "Diccionario_variables_geograficas_CPV24.xlsx":
            from src.data.download_censo import validate_censo_dictionary
            validate_censo_dictionary(path)
        elif name.startswith("D1_Poblacion-censada"):
            from src.data.download_censo_poblacion import validate_censo_poblacion_workbook
            validate_censo_poblacion_workbook(path)
        elif name.startswith("ine_estimaciones_proyecciones"):
            from src.data.download_poblacion_proyecciones import validate_poblacion_proyecciones_workbook
            validate_poblacion_proyecciones_workbook(path)
        elif name.startswith("mds_casen"):
            from src.data.download_pobreza_comunal import validate_pobreza_comunal_workbook
            validate_pobreza_comunal_workbook(path)
        elif "contexto_genero" in parts:
            from src.data.download_gender_statistics import validate_workbook
            validate_workbook(path)
        else:
            return False
        return True
    if name.startswith("Cartografia_censo2024_Pais_") and name.endswith(".parquet"):
        from src.data.download_censo import validate_censo_geoparquet
        validate_censo_geoparquet(path)
        _require_parquet(path, {"CUT": "integer", "COD_REGION": "integer", "SHAPE": "binary"})
        return True
    if name.startswith("Cartografia_censo2024_RM_") and name.endswith(".parquet"):
        layer = name.removesuffix(".parquet").rsplit("_", 1)[-1]
        keys = {"Comunal": "CUT", "Distrital": "ID_DISTRITO", "Zonal": "ID_ZONA",
                "Entidades": "MANZENT", "Manzanas": "MANZENT"}
        if layer not in keys:
            return False
        _require_parquet(path, {"CUT": "integer", "COD_REGION": "integer",
                                "SHAPE": "binary", keys[layer]: "integer" if layer == "Comunal" else "floating"})
        return True

    schemas: dict[str, pa.Schema] = {}
    if name.startswith("urgencias_rm_") and name.endswith(".parquet"):
        from src.data.clean_urgencias import OUTPUT_SCHEMA
        schemas[name] = OUTPUT_SCHEMA
    elif name.startswith("egresos_") and name.endswith(".parquet") and name.removesuffix(".parquet")[8:].isdigit():
        from src.data.clean_egresos import SCHEMA_PARQUET
        schemas[name] = SCHEMA_PARQUET
    elif name in {"dim_poblacion_comuna_censo2024.parquet", "dim_poblacion_comuna_anual.parquet",
                  "dim_vulnerabilidad_comuna.parquet", "dim_oferta_urgencia_rm.parquet",
                  "mart_mvp_territorial_comuna.parquet"}:
        from src.data import (build_dim_oferta_urgencia_rm, build_mart_mvp_territorial_comuna,
                              clean_censo_poblacion, clean_poblacion_proyecciones, clean_pobreza_comunal)
        schemas[name] = {
            "dim_poblacion_comuna_censo2024.parquet": clean_censo_poblacion.SCHEMA,
            "dim_poblacion_comuna_anual.parquet": clean_poblacion_proyecciones.SCHEMA,
            "dim_vulnerabilidad_comuna.parquet": clean_pobreza_comunal.SCHEMA,
            "dim_oferta_urgencia_rm.parquet": build_dim_oferta_urgencia_rm.SCHEMA,
            "mart_mvp_territorial_comuna.parquet": build_mart_mvp_territorial_comuna.SCHEMA,
        }[name]
    elif ((name.endswith(".parquet") and "contexto_genero" in parts)
          or name == "mart_contexto_genero_indicador_sexo.parquet"):
        from src.data.normalize_gender_statistics import SCHEMA
        schemas[name] = SCHEMA
    if schemas:
        _require_parquet(path, {field.name: field.type for field in schemas[name]})
        return True

    if name == "egresos_f00_f99_nacional_2020_2025.parquet":
        from src.data.build_egresos_f00_f99 import COLUMNS
        from src.data.clean_egresos import SCHEMA_PARQUET
        source_fields = {field.name: field.type for field in SCHEMA_PARQUET}
        _require_parquet(path, {**{column: source_fields[column] for column in COLUMNS}, "residente_rm": pa.bool_()})
        return True
    if name in {"establecimientos_rm_clean.parquet", "establecimientos_salud_clean.parquet"}:
        _require_parquet(path, {"establecimiento_codigo": "string", "region_codigo": "string",
                                "comuna_codigo": "string", "latitud": "floating", "longitud": "floating",
                                "seremi_salud_glosa_servicio_de_salud_glosa": "string"})
        return True
    if name == "perfil_cobertura_sm_comuna_semanal_2021_2025.parquet":
        _require_parquet(path, {"comuna_codigo": "string", "semanas_con_reporte": "integer",
                                "atenciones_sm_total": "integer", "proporcion_cobertura": "floating"})
        return True
    if name.startswith("mart_urgencias_") and name.endswith(".parquet"):
        from src.data.build_urgencias_comuna_marts import COUNT_COLUMNS
        fields: dict[str, str] = {column: "integer" for column in COUNT_COLUMNS}
        fields.update({"ano": "integer", "fecha_mes": "string"} if "monthly" in name
                      else {"ano": "integer", "semana": "integer", "fecha_inicio_semana": "string"})
        if "establecimiento" in name:
            fields["establecimiento_codigo"] = "integer"
        else:
            fields["comuna_codigo"] = "string"
            fields["comuna_glosa"] = "string"
        if "etario" in name:
            fields["grupo_etario_urgencia"] = "string"
        elif "establecimiento" not in name:
            fields.update({"poblacion_anual": "integer",
                           "n_establecimientos_reportantes_id36": "integer"})
        _require_parquet(path, fields)
        return True

    if name == "establecimientos_rm_clean.csv":
        _require_csv(path, {"establecimiento_codigo", "region_codigo", "comuna_codigo", "latitud", "longitud"},
                     floating={"latitud", "longitud"})
        return True
    if name == "registros_sin_coordenadas.csv":
        _require_csv(path, {
            "establecimiento_codigo", "establecimiento_codigo_antiguo",
            "establecimiento_glosa", "tipo_establecimiento_glosa",
            "ambito_funcionamiento", "comuna_codigo", "comuna_glosa",
            "latitud", "longitud", "estado_funcionamiento",
        }, floating={"latitud", "longitud"}, all_rows=True, allow_empty=True)
        return True
    if name == "catalogo_f00_f99.csv":
        from src.data.build_catalogs import catalogo_data
        _require_csv(path, set(catalogo_data[0]), numeric={"id_causa"})
        return True
    if name == "catalogo_cie10_f00_f99.csv":
        _require_csv(path, {"CODIGO SUBCATEGORIA", "CAPITULO"})
        return True
    if name == "tabla1_demanda_anual_rm.csv":
        _require_csv(path, {"ano", "atenciones_totales", "fecha_inicio", "fecha_termino"},
                     numeric={"ano", "atenciones_totales"})
        return True
    return False
