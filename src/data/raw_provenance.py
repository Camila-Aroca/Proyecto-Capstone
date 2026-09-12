"""Utilidades compartidas para registrar snapshots RAW en el manifest existente."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("data/raw/provenance_manifest.json")


def file_sha256(path: Path) -> str:
    """Calcula SHA256 sin cargar el archivo completo en memoria."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_raw_snapshot(
    source_id: str,
    source_url: str,
    raw_path: Path,
    *,
    transport: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
    manifest_path: Path = MANIFEST_PATH,
    downloaded_at: str | None = None,
) -> None:
    """Añade un snapshot validado al manifest común, preservando el historial."""
    manifest: list[dict[str, Any]] = []
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("El manifest de provenance debe ser una lista JSON.")
        manifest = payload

    entry = next((item for item in manifest if item.get("source_id") == source_id), None)
    if entry is None:
        entry = {"source_id": source_id, "snapshots": []}
        manifest.append(entry)
    if source_metadata:
        for key, value in source_metadata.items():
            entry.setdefault(key, value)

    snapshot: dict[str, Any] = {
        "source_url": source_url,
        "downloaded_at": downloaded_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "raw_path": raw_path.as_posix(),
        "raw_filename": raw_path.name,
        "raw_size": raw_path.stat().st_size,
        "raw_sha256": file_sha256(raw_path),
    }
    if transport:
        snapshot["transport"] = transport
    entry.setdefault("snapshots", []).append(snapshot)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.parent / f".{manifest_path.name}.tmp"
    try:
        temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
