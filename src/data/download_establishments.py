"""Script de descarga y validación de fuentes crudas de establecimientos de salud (DEIS)."""

import csv
import logging
from pathlib import Path
from typing import List, Tuple
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEIS_URL: str = (
    "https://datos.gob.cl/dataset/3bf4cf7c-f638-4735-9a01-f65faae4beca/"
    "resource/2c44d782-3365-44e3-aefb-2c8b8363a1bc/download/establecimientos_20260825.csv"
)
OUTPUT_DIR: Path = Path("data/raw/deis")
OUTPUT_FILE: Path = OUTPUT_DIR / "establecimientos_salud_actualizado.csv"


def ensure_directory(directory_path: Path) -> None:
    """Garantiza que el directorio especificado exista."""
    directory_path.mkdir(parents=True, exist_ok=True)
    logger.info("Directorio verificado: %s", directory_path)


def download_file(url: str, destination: Path) -> Path:
    """Descarga un archivo desde una URL remota hacia una ruta local.

    Args:
        url: URL de origen del archivo.
        destination: Ruta de destino en el sistema de archivos local.

    Returns:
        Path al archivo descargado.

    Raises:
        RuntimeError: Si ocurre un error durante la descarga.
    """
    ensure_directory(destination.parent)
    logger.info("Iniciando descarga desde: %s", url)

    # Configurar User-Agent para evitar bloqueos en servidores públicos
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    try:
        with urllib.request.urlopen(req) as response, open(destination, "wb") as out_file:
            data = response.read()
            out_file.write(data)
        logger.info("Archivo descargado exitosamente en: %s (%d bytes)", destination, destination.stat().st_size)
    except Exception as exc:
        logger.error("Error al descargar el archivo: %s", exc)
        raise RuntimeError(f"Fallo en la descarga desde {url}") from exc

    return destination


def detect_csv_format(file_path: Path) -> Tuple[str, str]:
    """Detecta la codificación y el delimitador de un archivo CSV.

    Args:
        file_path: Ruta del archivo a inspeccionar.

    Returns:
        Tupla con (encoding, delimiter).
    """
    encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
    sample_bytes: bytes

    with open(file_path, "rb") as f:
        sample_bytes = f.read(10000)

    detected_encoding = "utf-8"
    sample_text = ""
    for enc in encodings:
        try:
            sample_text = sample_bytes.decode(enc)
            detected_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    # Detectar delimitador común
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample_text, delimiters=[",", ";", "\t", "|"])
        delimiter = dialect.delimiter
    except Exception:
        # Fallback a detección por conteo
        comma_count = sample_text.count(",")
        semicolon_count = sample_text.count(";")
        delimiter = ";" if semicolon_count > comma_count else ","

    logger.info("Formato detectado - Codificación: %s, Delimitador: '%s'", detected_encoding, delimiter)
    return detected_encoding, delimiter


def validate_and_preview(
    file_path: Path,
    max_rows: int = 5,
    max_cols: int = 5,
) -> Tuple[List[str], List[List[str]]]:
    """Valida que el archivo no esté vacío y obtiene las primeras N columnas y filas.

    Args:
        file_path: Ruta del archivo a validar.
        max_rows: Cantidad máxima de filas a previsualizar.
        max_cols: Cantidad máxima de columnas a previsualizar.

    Returns:
        Tupla de (encabezados_seleccionados, filas_seleccionadas).

    Raises:
        ValueError: Si el archivo está vacío o no contiene datos válidos.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"El archivo no existe: {file_path}")

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"El archivo descargado está vacío (0 bytes): {file_path}")

    encoding, delimiter = detect_csv_format(file_path)

    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError(f"El archivo no contiene filas legibles: {file_path}")

        preview_headers = headers[:max_cols]
        preview_rows: List[List[str]] = []

        for row in reader:
            if not row:
                continue
            preview_rows.append(row[:max_cols])
            if len(preview_rows) >= max_rows:
                break

    if not preview_rows:
        raise ValueError(f"El archivo sólo contiene encabezados sin registros: {file_path}")

    return preview_headers, preview_rows


def main() -> None:
    """Función principal de ejecución del pipeline de ingesta inicial."""
    download_file(DEIS_URL, OUTPUT_FILE)
    headers, rows = validate_and_preview(OUTPUT_FILE, max_rows=5, max_cols=5)

    print("\n" + "=" * 80)
    print("VALIDACIÓN Y ESTRUCTURA DEL ARCHIVO DESCARGADO")
    print("=" * 80)
    print(f"Ruta: {OUTPUT_FILE}")
    print(f"Tamaño: {OUTPUT_FILE.stat().st_size:,} bytes")
    print(f"Primeras {len(headers)} columnas:")
    for idx, col in enumerate(headers, start=1):
        print(f"  {idx}. {col}")

    print(f"\nPrimeras {len(rows)} filas (truncadas a {len(headers)} columnas):")
    for r_idx, row in enumerate(rows, start=1):
        print(f"  Fila {r_idx}: {row}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
