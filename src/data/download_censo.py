"""Script to download Censo 2024 comunal cartography and extract it."""

import argparse
import datetime
import hashlib
import json
import logging
from pathlib import Path
import ssl
import urllib.request
import zipfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

URL_CENSO = "https://storage.googleapis.com/bktdescargascenso2024/Cartografia/GEOPARQUET/Cartografia_censo2024_Pais.zip"
DEST_DIR = Path("data/raw/censo")
ZIP_TEMP_PATH = DEST_DIR / "Cartografia_censo2024_Pais.zip"
TARGET_FILE_NAME = "Cartografia_censo2024_Pais_Comunal.parquet"
FINAL_OUTPUT_PATH = DEST_DIR / TARGET_FILE_NAME


def update_manifest(source_url, zip_path, year=2024):
    manifest_path = Path("data/raw/provenance_manifest.json")
    manifest = []
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
    # Calculate SHA256
    sha256_hash = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    entry = {
        "source_url": source_url,
        "filename": zip_path.name,
        "year": year,
        "downloaded_at": datetime.datetime.now().isoformat(),
        "file_size": zip_path.stat().st_size,
        "sha256": sha256_hash.hexdigest()
    }
    
    # Update if exists, else append
    for i, e in enumerate(manifest):
        if e["filename"] == entry["filename"]:
            manifest[i] = entry
            break
    else:
        manifest.append(entry)
        
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def download_censo_zip() -> None:
    """Downloads the Censo 2024 cartography ZIP file."""
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting download of Censo 2024 ZIP from: %s", URL_CENSO)

    req = urllib.request.Request(
        URL_CENSO,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            total_bytes = int(response.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024 * 5

            with open(ZIP_TEMP_PATH, "wb") as out_file:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)

        logger.info("ZIP downloaded successfully to: %s", ZIP_TEMP_PATH)
        update_manifest(URL_CENSO, ZIP_TEMP_PATH, 2024)
    except Exception as exc:
        logger.error("Failed to download ZIP from %s: %s", URL_CENSO, exc)
        raise RuntimeError("Download failed") from exc


def extract_target_file() -> None:
    """Extracts only the Comunal Parquet file from the ZIP and cleans up."""
    if not ZIP_TEMP_PATH.exists():
        raise FileNotFoundError(f"ZIP file not found at {ZIP_TEMP_PATH}")

    logger.info("Opening ZIP archive to extract: %s", TARGET_FILE_NAME)
    try:
        with zipfile.ZipFile(ZIP_TEMP_PATH, "r") as z:
            namelist = z.namelist()
            matched_file = None
            for name in namelist:
                if Path(name).name == TARGET_FILE_NAME:
                    matched_file = name
                    break

            if not matched_file:
                raise FileNotFoundError(f"Target file {TARGET_FILE_NAME} not found inside the ZIP.")

            logger.info("Found file inside ZIP: %s. Extracting...", matched_file)
            
            with z.open(matched_file) as source, open(FINAL_OUTPUT_PATH, "wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)

            logger.info("Extracted successfully to: %s", FINAL_OUTPUT_PATH)
    except Exception as exc:
        logger.error("Failed to extract file: %s", exc)
        raise
    finally:
        if ZIP_TEMP_PATH.exists():
            logger.info("Removing temporary ZIP file: %s", ZIP_TEMP_PATH)
            ZIP_TEMP_PATH.unlink()


def main() -> None:
    """Main execution block."""
    parser = argparse.ArgumentParser(description="Descarga de Censo.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        download_censo_zip()
        extract_target_file()
        logger.info("Censo download and extraction completed successfully.")
    except Exception as exc:
        logger.error("Censo task failed: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
