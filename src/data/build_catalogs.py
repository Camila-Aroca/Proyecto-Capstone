"""Genera el catálogo oficial de salud mental (F00-F99 y causas asociadas) para Urgencias DEIS."""

from pathlib import Path
import pandas as pd

OUTPUT_PATH = Path("data/processed/urgencias/catalogo_f00_f99.csv")

catalogo_data = [
    {
        "id_causa": 36,
        "glosa_causa_estandar": "TOTAL CAUSAS DE TRASTORNOS MENTALES (F00-F99)",
        "tipo_registro": "Macro-agregador",
        "clasificacion_cie10": "F00-F99 (Agregado)",
        "capitulo_cie10": "Capítulo V: Trastornos mentales y del comportamiento",
        "categoria_salud_mental": "Total General Salud Mental",
        "es_subcausa_exclusiva": False,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Demostrable por suma interna 37+38+39+40+41)",
        "observaciones": "Corresponde a la suma exacta de las subcausas 37, 38, 39, 40 y 41. No debe sumarse con sus componentes para evitar doble conteo."
    },
    {
        "id_causa": 38,
        "glosa_causa_estandar": "Trastornos mentales y del comportamiento debidos al uso de sustancias psicoactivas (F10-F19)",
        "tipo_registro": "Causa Específica (Subcausa)",
        "clasificacion_cie10": "F10-F19",
        "capitulo_cie10": "Capítulo V: Trastornos mentales y del comportamiento",
        "categoria_salud_mental": "Trastornos por Sustancias Psicoactivas / Adicciones",
        "es_subcausa_exclusiva": True,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Código CIE-10 explícito en glosa y diccionario)",
        "observaciones": "Incluye intoxicaciones agudas, uso nocivo y síndrome de dependencia (alcohol, drogas)."
    },
    {
        "id_causa": 39,
        "glosa_causa_estandar": "Trastornos del Humor (Afectivos) (F30-F39)",
        "tipo_registro": "Causa Específica (Subcausa)",
        "clasificacion_cie10": "F30-F39",
        "capitulo_cie10": "Capítulo V: Trastornos mentales y del comportamiento",
        "categoria_salud_mental": "Trastornos del Ánimo / Afectivos",
        "es_subcausa_exclusiva": True,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Código CIE-10 explícito en glosa y diccionario)",
        "observaciones": "Incluye episodios depresivos mayores, trastorno afectivo bipolar y manía."
    },
    {
        "id_causa": 40,
        "glosa_causa_estandar": "Trastornos neuróticos, trastornos relacionados con el estrés y trastornos somatomorfos (F40-F48)",
        "tipo_registro": "Causa Específica (Subcausa)",
        "clasificacion_cie10": "F40-F48",
        "capitulo_cie10": "Capítulo V: Trastornos mentales y del comportamiento",
        "categoria_salud_mental": "Ansiedad, Estrés y Somatización",
        "es_subcausa_exclusiva": True,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Código CIE-10 explícito en glosa y diccionario)",
        "observaciones": "Incluye crisis de pánico (F41.0), trastorno de ansiedad generalizada y reacciones al estrés agudo."
    },
    {
        "id_causa": 41,
        "glosa_causa_estandar": "Otros trastornos mentales no contenidos en las categorías anteriores",
        "tipo_registro": "Causa Específica (Subcausa Residual)",
        "clasificacion_cie10": "F00-F09, F20-F29, F50-F99",
        "capitulo_cie10": "Capítulo V: Trastornos mentales y del comportamiento",
        "categoria_salud_mental": "Otros Trastornos Mentales (Esquizofrenia, Psicosis, Orgánicos, Infanto-juveniles)",
        "es_subcausa_exclusiva": True,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Demostrable por complementariedad de F00-F99)",
        "observaciones": "Categoría residual de salud mental que captura psicosis, esquizofrenia, demencias y trastornos infantojuveniles."
    },
    {
        "id_causa": 37,
        "glosa_causa_estandar": "Ideación Suicida (R45.8)",
        "tipo_registro": "Causa Específica (Síntoma / Signo)",
        "clasificacion_cie10": "R45.8",
        "capitulo_cie10": "Capítulo XVIII: Síntomas, signos y hallazgos anormales",
        "categoria_salud_mental": "Riesgo Suicida / Síntomas Emocionales",
        "es_subcausa_exclusiva": True,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Código CIE-10 explícito R45.8)",
        "observaciones": "El DEIS lo incluye en la suma de ID 36 pero formalmente es código R45.8, no F."
    },
    {
        "id_causa": 35,
        "glosa_causa_estandar": "Lesiones autoinfligidas intencionalmente (X60-X84)",
        "tipo_registro": "Causa Externa Asociada (Traumatismo/Lesión)",
        "clasificacion_cie10": "X60-X84",
        "capitulo_cie10": "Capítulo XX: Causas externas de morbilidad y de mortalidad",
        "categoria_salud_mental": "Intento de Suicidio / Autolesión Física",
        "es_subcausa_exclusiva": False,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Código CIE-10 explícito X60-X84)",
        "observaciones": "Agrupada en Sección 1 bajo Traumatismos (ID 18). Corresponde al correlato físico/traumático de autolesiones."
    },
    {
        "id_causa": 42,
        "glosa_causa_estandar": "Hospitalizaciones por trastornos mentales (F00-F99)",
        "tipo_registro": "Resultado Asistencial (Sección 2)",
        "clasificacion_cie10": "F00-F99 (Hospitalización)",
        "capitulo_cie10": "Capítulo V: Trastornos mentales y del comportamiento",
        "categoria_salud_mental": "Hospitalización Psiquiátrica Derivada desde Urgencia",
        "es_subcausa_exclusiva": False,
        "fuente_evidencia": "DEIS - Diccionario BD Atenciones de Urgencia (Anexo 1)",
        "nivel_confianza": "Alto (Subsección de Sección 2)",
        "observaciones": "Mide pacientes atendidos en urgencia que fueron derivados a hospitalización por causa de salud mental."
    }
]

def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_cat = pd.DataFrame(catalogo_data)
    df_cat.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Catálogo de Salud Mental guardado en {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
