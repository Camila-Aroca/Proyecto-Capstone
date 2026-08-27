"""Pruebas unitarias para el módulo de limpieza y estandarización de establecimientos DEIS."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.clean_establishments import (
    audit_rm_quality,
    clean_establishments_data,
    detect_file_format,
    filter_region_metropolitana,
    normalize_column_names,
    parse_numeric_coordinate,
    process_and_save_establishments,
    to_snake_case,
)


class TestCleanEstablishments(unittest.TestCase):
    """Casos de prueba para el pipeline de establecimientos."""

    def test_to_snake_case(self) -> None:
        """Verifica la normalización a snake_case."""
        self.assertEqual(to_snake_case("EstablecimientoCodigo"), "establecimiento_codigo")
        self.assertEqual(to_snake_case("SeremiSaludCodigo_ServicioDeSaludCodigo"), "seremi_salud_codigo_servicio_de_salud_codigo")
        self.assertEqual(to_snake_case("TipoPertenenciaEstabGlosa"), "tipo_pertenencia_estab_glosa")
        self.assertEqual(to_snake_case("TelefonoMovil_TelefonoFijo"), "telefono_movil_telefono_fijo")

    def test_parse_numeric_coordinate(self) -> None:
        """Verifica conversión no destructiva de coordenadas a float."""
        self.assertAlmostEqual(parse_numeric_coordinate("-33.429013"), -33.429013, places=6)
        self.assertAlmostEqual(parse_numeric_coordinate("-70.655438"), -70.655438, places=6)
        self.assertAlmostEqual(parse_numeric_coordinate("-33,429013"), -33.429013, places=6)
        self.assertIsNone(parse_numeric_coordinate(""))
        self.assertIsNone(parse_numeric_coordinate(None))
        self.assertIsNone(parse_numeric_coordinate(np.nan))
        self.assertIsNone(parse_numeric_coordinate("No Aplica"))

    def test_normalize_column_names(self) -> None:
        """Verifica la normalización de columnas del DataFrame."""
        df = pd.DataFrame({"CodigoEstab": ["1"], "Latitud": ["-33.4"], "RegionCodigo": ["13"]})
        df_norm = normalize_column_names(df)
        self.assertListEqual(list(df_norm.columns), ["codigo_estab", "latitud", "region_codigo"])

    def test_filter_region_metropolitana(self) -> None:
        """Verifica el filtrado de la Región Metropolitana (código 13)."""
        df = pd.DataFrame({
            "region_codigo": ["13", "15", "13.0", "05", "13", None],
            "establecimiento_glosa": ["Hosp 1", "Hosp 2", "Hosp 3", "Hosp 4", "Hosp 5", "Hosp 6"],
        })
        df_rm = filter_region_metropolitana(df, region_col="region_codigo", region_code="13")
        self.assertEqual(len(df_rm), 3)
        self.assertListEqual(df_rm["establecimiento_glosa"].tolist(), ["Hosp 1", "Hosp 3", "Hosp 5"])

    def test_process_and_save_establishments_end_to_end(self) -> None:
        """Verifica el pipeline integral de guardado y auditoría."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_raw_path = Path(tmpdir) / "raw.csv"
            out_csv_rm = Path(tmpdir) / "establecimientos_rm_clean.csv"
            out_pq_rm = Path(tmpdir) / "establecimientos_rm_clean.parquet"
            out_pq_nac = Path(tmpdir) / "establecimientos_salud_clean.parquet"

            raw_content = (
                "EstablecimientoCodigo;RegionCodigo;RegionGlosa;EstablecimientoGlosa;ComunaGlosa;"
                "Latitud;Longitud;TipoAtencionEstabGlosa;TipoSistemaSaludGlosa;TieneServicioUrgencia;TipoUrgencia\n"
                "101011;15;Arica Parinacota;Hospital Arica;Arica;-18.484664;-70.303464;Atención Abierta-Ambulatoria;Público;NO;No Aplica\n"
                "109011;13;Metropolitana de Santiago;Hospital Santiago;Santiago;-33.428960;-70.655492;Atención Abierta-Ambulatoria;Público;SI;SAR\n"
                "109012;13;Metropolitana de Santiago;Clínica Conchalí;Conchalí;;;Atención Cerrada-Hospitalaria;Público;NO;No Aplica\n"
            )
            csv_raw_path.write_text(raw_content, encoding="utf-8")

            df_nac, df_rm, audit = process_and_save_establishments(
                raw_path=csv_raw_path,
                output_csv_path=out_csv_rm,
                output_parquet_path=out_pq_rm,
                output_nacional_path=out_pq_nac,
            )

            self.assertEqual(len(df_nac), 3)
            self.assertEqual(len(df_rm), 2)
            self.assertTrue(out_csv_rm.exists())
            self.assertTrue(out_pq_rm.exists())
            self.assertTrue(out_pq_nac.exists())
            self.assertEqual(audit["total_filas_rm"], 2)
            self.assertEqual(audit["coordenadas_validas"], 1)
            self.assertEqual(audit["coordenadas_nulas"], 1)
            self.assertTrue(audit["text_checks"]["atencion"])
            self.assertTrue(audit["text_checks"]["publico"])
            self.assertTrue(audit["text_checks"]["clinica"])
            self.assertTrue(audit["text_checks"]["conchali"])


if __name__ == "__main__":
    unittest.main()
