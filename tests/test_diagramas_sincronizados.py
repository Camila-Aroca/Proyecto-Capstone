"""Sincronización de ERD lógico, ERD físico, DDL, UML y README (`.agents/rules.md`, sección 7).

Comprueba, sin necesidad de datos, que los artefactos del modelo de datos no se desfasen:
entidades, columnas, FK, bloques del README, SVG/PNG y cobertura de los outputs del DAG.
"""

from __future__ import annotations

import os
import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "07-diagramas" / "15-modelo-base-datos"
LOGICO, FISICO = D / "modelo_datos_logico", D / "modelo_datos_fisico_postgresql"
PUML = ROOT / "docs" / "07-diagramas" / "clases_saad"
DDL = ROOT / "db" / "schema_postgresql.sql"
README = D / "README.md"

# Entidades lógicas sin tabla física ni clase UML por decisión documentada en el README.
SIN_TABLA = {"defunciones_nacional"}
SIN_CLASE_UML = {"cartografia_distrital", "cartografia_zonal", "cartografia_entidades", "cartografia_manzanas"}
PREFIJO_FISICO = {
    "dim_poblacion_comuna_censo2024": "censo_", "dim_poblacion_comuna_anual": "censo_", "dim_vulnerabilidad_comuna": "pobreza_",
    "dim_oferta_urgencia_rm": "geo_", "cobertura_urgencia_comuna": "geo_", "capa_oferta_urgencia_rm": "geo_",
}
NOMBRE_FISICO = {
    "dim_camas_psiquiatria_hospital_rm": "camas_dim_psiquiatria_hospital_rm", "mart_mvp_territorial_comuna": "marts_mvp_territorial_comuna",
    "mart_ocupacion_psiquiatria_hospital_rm": "marts_ocupacion_psiquiatria_hospital_rm",
    "mart_suicidios_comuna_weekly": "marts_suicidios_comuna_weekly", "mart_egresos_f00_f99_rm_anual": "marts_egresos_f00_f99_rm_anual",
    "mart_egresos_f00_f99_rm_desglose": "marts_egresos_f00_f99_rm_desglose",
    "contraste_camas_psiquiatria_rm": "marts_contraste_camas_psiquiatria_rm",
    "mart_contexto_genero_indicador_sexo": "contexto_genero_indicador_por_sexo",
    "egresos_f00_f99_nacional_2020_2025": "egresos_f00_f99_nacional", "pronostico_demanda_sm": "modeling_pronostico_demanda_sm",
    "pronostico_establecimientos_sm": "modeling_pronostico_establecimientos_sm", "pronostico_suicidios": "modeling_pronostico_suicidios",
    "dotacion_camas_snss": "camas_dotacion_snss", "dotacion_camas_no_snss": "camas_dotacion_no_snss",
    "indicadores_hospitalarios_snss": "camas_indicadores_hospitalarios_snss",
    "categorizacion_riesgo_dependencia": "camas_categorizacion_riesgo_dependencia",
}
CLASE_UML = {
    "cartografia_comunal": "Comuna", "dim_poblacion_comuna_censo2024": "PoblacionComunaCenso2024",
    "dim_poblacion_comuna_anual": "PoblacionComunaAnual", "dim_vulnerabilidad_comuna": "VulnerabilidadComuna",
    "dim_oferta_urgencia_rm": "EstablecimientoUrgencia", "cobertura_urgencia_comuna": "CoberturaUrgenciaComuna",
    "capa_oferta_urgencia_rm": "CapaOfertaUrgencia", "mart_urgencias_comuna_weekly": "UrgenciasComunaWeekly",
    "mart_urgencias_comuna_monthly": "UrgenciasComunaMonthly", "mart_urgencias_comuna_etario_monthly": "UrgenciasComunaEtarioMonthly",
    "mart_urgencias_establecimiento_monthly": "UrgenciasEstablecimientoMonthly",
    "mart_urgencias_establecimiento_weekly": "UrgenciasEstablecimientoWeekly", "mart_mvp_territorial_comuna": "MartMVPTerritorialComuna",
    "mart_contexto_genero_indicador_sexo": "MartContextoGeneroIndicadorSexo", "egresos_f00_f99_nacional_2020_2025": "EgresoF00F99",
    "mart_egresos_f00_f99_rm_anual": "PerfilEgresosResidentesRM", "mart_egresos_f00_f99_rm_desglose": "DesgloseEgresosResidentesRM",
    "contraste_camas_psiquiatria_rm": "ContrasteCamasPsiquiatria", "dotacion_camas_snss": "DotacionCamasSNSS",
    "dotacion_camas_no_snss": "DotacionCamasNoSNSS", "dim_camas_psiquiatria_hospital_rm": "CamasPsiquiatriaHospital",
    "indicadores_hospitalarios_snss": "IndicadorHospitalarioSNSS", "categorizacion_riesgo_dependencia": "CategorizacionRiesgoDependencia",
    "mart_ocupacion_psiquiatria_hospital_rm": "OcupacionPsiquiatriaHospital", "defunciones_nacional": "DefuncionNacional",
    "mart_suicidios_comuna_weekly": "MartSuicidiosComunaWeekly", "pronostico_suicidios": "PronosticoSuicidios",
    "pronostico_demanda_sm": "PronosticoDemandaSM", "pronostico_establecimientos_sm": "PronosticoEstablecimientoSM",
}
# Outputs de data/processed fuera del modelo, con la expresión que debe citar el README para justificarlo.
EXCLUIDOS = {
    "contexto_genero/": "mart_contexto_genero_indicador_sexo", "egresos/egresos_20": "egresos_AAAA.parquet",
    "urgencias/urgencias_rm_20": "urgencias_rm_AAAA.parquet", "urgencias/tabla": "tabla1_*.csv",
    "perfil_cobertura": "perfil_cobertura_sm_comuna_semanal_2021_2025.parquet",
    "establecimientos_coordenadas_resolucion": "establecimientos_coordenadas_resolucion.csv",
    "establecimientos_rm_clean": "establecimientos_rm_clean.parquet", "establecimientos_salud_clean": "establecimientos_salud_clean.parquet",
    "catalogo": "Catálogo CIE-10",
}


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8").replace("\r\n", "\n")


def _entidades_mmd(ruta: Path) -> dict[str, list[str]]:
    entidades: dict[str, list[str]] = {}
    actual = None
    for linea in _leer(ruta).splitlines():
        s = linea.strip()
        m = re.match(r"^([a-z_0-9]+) \{$", s)
        if m:
            actual = m.group(1)
            entidades[actual] = []
        elif s == "}":
            actual = None
        elif actual and s and not s.startswith("%%"):
            entidades[actual].append(s.split()[1])
    return entidades


def _tablas_ddl() -> dict[str, list[str]]:
    texto = _leer(DDL)
    tablas = {}
    for m in re.finditer(r"CREATE TABLE ([a-z_]+\.[a-z_0-9]+) \((.*?)\n\);", texto, re.S):
        nombre, cuerpo = m.groups()
        items, prof, buf = [], 0, ""
        for ch in cuerpo:
            prof += (ch == "(") - (ch == ")")
            if ch == "," and prof == 0:
                items.append(buf)
                buf = ""
            else:
                buf += ch
        items.append(buf)
        cols = []
        for it in items:
            s = " ".join(re.sub(r"--.*", "", it).split())
            if s and not s.startswith(("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK")):
                cols.append(s.split()[0])
        tablas[nombre] = cols
    return tablas


def _entidad_de_tabla(tabla: str, entidades) -> str | None:
    esquema, _, nombre = tabla.partition(".")
    for cand in (f"{esquema}_{nombre}", f"{esquema}_{nombre.replace(esquema + '_', '', 1)}", f"{esquema}_{nombre.replace('mart_', '', 1)}"):
        if cand in entidades:
            return cand
    return None


def _fisico_de(logica: str) -> str | None:
    if logica in SIN_TABLA:
        return None
    if logica.startswith("cartografia_"):
        return "censo_" + logica
    if logica in PREFIJO_FISICO:
        return PREFIJO_FISICO[logica] + logica
    if logica.startswith("mart_urgencias_"):
        return logica.replace("mart_urgencias_", "urgencias_mart_")
    return NOMBRE_FISICO[logica]


def test_bloques_mermaid_del_readme_son_identicos_a_los_mmd() -> None:
    bloques = re.findall(r"```mermaid\n(.*?)```", _leer(README), re.S)
    assert len(bloques) == 2
    for bloque, base in zip(bloques, (LOGICO, FISICO)):
        assert bloque.strip() == _leer(base.with_suffix(".mmd")).strip(), base.name


def test_entidades_fisicas_columnas_y_ddl_coinciden() -> None:
    fisico = _entidades_mmd(FISICO.with_suffix(".mmd"))
    tablas = _tablas_ddl()
    assert len(fisico) == len(tablas)
    for tabla, columnas in tablas.items():
        entidad = _entidad_de_tabla(tabla, fisico)
        assert entidad, f"{tabla} no tiene entidad en el ERD físico"
        assert sorted(fisico[entidad]) == sorted(columnas), f"columnas de {tabla} difieren del ERD físico"


def test_fk_del_ddl_estan_dibujadas_como_relacion_solida() -> None:
    fisico = _entidades_mmd(FISICO.with_suffix(".mmd"))
    texto = _leer(DDL)
    fk = set()
    for m in re.finditer(r"CREATE TABLE ([a-z_]+\.[a-z_0-9]+) \((.*?)\n\);", texto, re.S):
        for r in re.finditer(r"FOREIGN KEY \([^)]*\)\s+REFERENCES ([a-z_]+\.[a-z_0-9]+)", m.group(2)):
            fk.add(frozenset((_entidad_de_tabla(m.group(1), fisico), _entidad_de_tabla(r.group(1), fisico))))
    solidas = set()
    for linea in _leer(FISICO.with_suffix(".mmd")).splitlines():
        m = re.match(r"\s+([a-z_0-9]+) (\S+) ([a-z_0-9]+) :", linea)
        if m and ".." not in m.group(2):
            solidas.add(frozenset((m.group(1), m.group(3))))
    assert fk == solidas


def test_cada_entidad_logica_tiene_tabla_fisica_y_clase_uml() -> None:
    logico = _entidades_mmd(LOGICO.with_suffix(".mmd"))
    fisico = _entidades_mmd(FISICO.with_suffix(".mmd"))
    uml = _leer(PUML.with_suffix(".puml"))
    for entidad in logico:
        destino = _fisico_de(entidad)
        if destino:
            assert destino in fisico, f"{entidad}: falta {destino} en el ERD físico"
        if entidad not in SIN_CLASE_UML:
            assert re.search(rf"class {CLASE_UML[entidad]} ", uml), f"{entidad}: falta la clase {CLASE_UML[entidad]}"
    assert {_fisico_de(e) for e in logico} - {None} == set(fisico)


def test_svg_contiene_todo_lo_declarado_y_png_corresponde_al_svg() -> None:
    for base in (LOGICO, FISICO):
        svg = _leer(base.with_suffix(".svg"))
        for entidad, columnas in _entidades_mmd(base.with_suffix(".mmd")).items():
            assert entidad in svg and all(c in svg for c in columnas), f"{base.name}: {entidad} desfasada en el SVG"
    for base in (LOGICO, FISICO, PUML):
        svg = _leer(base.with_suffix(".svg"))
        ancho_svg = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) [\d.]+"', svg).group(1))
        png = base.with_suffix(".png")
        assert png.stat().st_size > 10_000
        ancho_png = struct.unpack(">I", png.read_bytes()[16:20])[0]
        assert abs(ancho_png - ancho_svg) <= 3, f"{png.name} no corresponde a su SVG"
    uml = _leer(PUML.with_suffix(".puml"))
    svg = _leer(PUML.with_suffix(".svg"))
    for clase in re.findall(r"^\s*class ([A-Za-z0-9]+) ", uml, re.M):
        assert f'id="entity_{clase}"' in svg, f"clase {clase} desfasada en el SVG del UML"


def test_outputs_del_dag_estan_en_el_modelo_o_excluidos_y_justificados() -> None:
    from scripts import run_pipeline as rp

    logicas = set(_entidades_mmd(LOGICO.with_suffix(".mmd")))
    readme = _leer(README)
    salidas = {o for etapa in rp.PIPELINE_ORDER for o in rp.STAGES[etapa].get("outputs", [])
               if o.startswith("data/processed/") and o.endswith((".parquet", ".csv"))}
    for salida in sorted(salidas):
        stem = os.path.splitext(os.path.basename(salida))[0]
        if stem in logicas or stem.startswith("Cartografia"):
            continue
        justificado = any(patron in salida and cita in readme for patron, cita in EXCLUIDOS.items())
        assert justificado, f"{salida} no está en el ERD ni excluido y justificado en el README"


@pytest.mark.parametrize("ruta", [LOGICO, FISICO])
def test_cabecera_mermaid_usa_elk(ruta: Path) -> None:
    assert "layout: elk" in _leer(ruta.with_suffix(".mmd")).split("erDiagram")[0]
