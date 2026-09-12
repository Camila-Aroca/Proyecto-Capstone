"""Tests for the stable Egresos RAW contract published by DEIS downloads."""

from pathlib import Path
import zipfile

import pytest

from src.data.download_deis_sources import (
    canonical_egresos_raw_path,
    extract_canonical_egresos_csv,
)


@pytest.mark.parametrize(
    ("year", "published_name"),
    [
        (2020, "EGRE_DATOS_ABIERTOS_2020.csv"),
        (2024, "EGR_DATOS_ABIERTO_2024.csv"),
    ],
)
def test_extract_egresos_uses_canonical_name_for_deis_variants(
    tmp_path: Path, year: int, published_name: str
) -> None:
    archive_path = tmp_path / f"EGRESOS_{year}.zip"
    content = "ANO_EGRESO;DIAG1\n2024;F32\n".encode("utf-8")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(published_name, content)
        archive.writestr("Diccionario BD egresos hospitalario.xlsx", b"dictionary")

    result = extract_canonical_egresos_csv(archive_path, year, tmp_path)

    expected_path = tmp_path / canonical_egresos_raw_path(year).name
    assert result["raw_path"] == expected_path
    assert result["archive_member"] == published_name
    assert expected_path.read_bytes() == content


def test_extract_egresos_rejects_ambiguous_csv_members(tmp_path: Path) -> None:
    archive_path = tmp_path / "EGRESOS_2024.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("first.csv", b"a\n1\n")
        archive.writestr("second.csv", b"a\n2\n")

    with pytest.raises(ValueError, match="exactly one"):
        extract_canonical_egresos_csv(archive_path, 2024, tmp_path)
