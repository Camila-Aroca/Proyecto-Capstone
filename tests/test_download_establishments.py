"""Pruebas unitarias para el módulo de descarga y validación de establecimientos DEIS."""

import tempfile
import unittest
from pathlib import Path

from src.data.download_establishments import (
    detect_csv_format,
    ensure_directory,
    validate_and_preview,
)


class TestDownloadEstablishments(unittest.TestCase):
    """Casos de prueba para validación y manejo de archivos de establecimientos."""

    def test_ensure_directory(self) -> None:
        """Verifica que ensure_directory cree carpetas anidadas correctamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "nested" / "deis"
            self.assertFalse(target_path.exists())
            ensure_directory(target_path)
            self.assertTrue(target_path.exists())

    def test_detect_csv_format_semicolon(self) -> None:
        """Verifica la detección de codificación y delimitador punto y coma."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write("col1;col2;col3\nval1;val2;val3\n")
            tmp_path = Path(tmp.name)

        try:
            encoding, delimiter = detect_csv_format(tmp_path)
            self.assertEqual(encoding, "utf-8")
            self.assertEqual(delimiter, ";")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_validate_and_preview_success(self) -> None:
        """Verifica que validate_and_preview devuelva los encabezados y filas truncados."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write("c1,c2,c3,c4,c5,c6\n1,2,3,4,5,6\n7,8,9,10,11,12\n")
            tmp_path = Path(tmp.name)

        try:
            headers, rows = validate_and_preview(tmp_path, max_rows=2, max_cols=3)
            self.assertEqual(headers, ["c1", "c2", "c3"])
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], ["1", "2", "3"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_validate_and_preview_empty_file(self) -> None:
        """Verifica que un archivo vacío lance ValueError."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with self.assertRaises(ValueError):
                validate_and_preview(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
