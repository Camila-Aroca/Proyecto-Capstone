"""Script de auditoría profunda a nivel de bytes y textos para detectar encoding real y mojibake genuino."""

import csv
from pathlib import Path
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

def analyze_csv(path: Path):
    with open(path, "rb") as f:
        raw_header = f.readline()
        raw_sample = f.read(2000000) # 2 MB sample

    # Probar decodificaciones
    utf8_ok = False
    try:
        sample_utf8 = raw_sample.decode("utf-8")
        utf8_ok = True
    except UnicodeDecodeError as e:
        sample_utf8 = None
        utf8_err = str(e)

    latin1_ok = False
    try:
        sample_latin1 = raw_sample.decode("latin-1")
        latin1_ok = True
    except Exception:
        sample_latin1 = None

    # Detectar separador
    sep_counts = {";": raw_header.count(b";"), ",": raw_header.count(b","), "|": raw_header.count(b"|"), "\t": raw_header.count(b"\t")}
    sep = max(sep_counts, key=sep_counts.get)

    # Si se decodifica en UTF-8, ¿hay secuencias 'Ã', 'Â', '\ufffd'?
    mojibake_in_utf8 = False
    mojibake_in_latin1 = False
    
    # Mojibake real: secuencias como "Ã¡" (á), "Ã³" (ó), "Ã±" (ñ), "Ã©" (é), "Ã­" (í)
    mojibake_tokens = ["Ã¡", "Ã³", "Ã±", "Ã©", "Ã­", "Ã‰", "Ã“", "Ã‘", "Ãš", "Ãº", "Ã‘", "ï¿½", "\ufffd", "Ã "]
    
    if utf8_ok:
        for tok in mojibake_tokens:
            if tok in sample_utf8:
                mojibake_in_utf8 = True
                break

    if latin1_ok:
        for tok in mojibake_tokens:
            if tok in sample_latin1:
                mojibake_in_latin1 = True
                break

    # Determinar si el archivo es Latin-1 puro con tildes válidas
    # En Latin-1, 'ó' es byte 0xf3, 'í' es 0xed, 'á' es 0xe1, 'ñ' es 0xf1, 'é' es 0xe9
    has_latin1_accents = any(b in raw_sample for b in [b"\xe1", b"\xe9", b"\xed", b"\xf3", b"\xfa", b"\xf1", b"\xc1", b"\xc9", b"\xcd", b"\xd3", b"\xda", b"\xd1"])
    # En UTF-8, 'ó' es 0xc3 0xb3, 'ñ' es 0xc3 0xb1, 'á' es 0xc3 0xa1
    has_utf8_accents = any(b in raw_sample for b in [b"\xc3\xa1", b"\xc3\xa9", b"\xc3\xad", b"\xc3\xb3", b"\xc3\xba", b"\xc3\xb1", b"\xc3\x81", b"\xc3\x89", b"\xc3\x8d", b"\xc3\x93", b"\xc3\x9a", b"\xc3\x91"])

    # Conclusión de codificación
    if utf8_ok and not mojibake_in_utf8:
        encoding_conclusion = "UTF-8 legítimo (sin mojibake)"
    elif utf8_ok and mojibake_in_utf8:
        encoding_conclusion = "UTF-8 con texto mojibake preexistente de origen"
    elif not utf8_ok and has_latin1_accents and not mojibake_in_latin1:
        encoding_conclusion = "Latin-1 (ISO-8859-1 / Windows-1252) legítimo"
    elif not utf8_ok and mojibake_in_latin1:
        encoding_conclusion = "Latin-1 con mojibake previo"
    else:
        encoding_conclusion = "ASCII puro / Desconocido"

    # Verificar líneas y campos
    read_enc = "utf-8" if utf8_ok else "latin-1"
    with open(path, "r", encoding=read_enc, errors="replace") as f:
        reader = csv.reader(f, delimiter=sep)
        header = next(reader)
        cols_count = len(header)
        total_rows = 0
        mismatched_rows = 0
        for idx, row in enumerate(reader, start=2):
            total_rows += 1
            if len(row) != cols_count:
                mismatched_rows += 1

    return {
        "file": path.name,
        "path": path.as_posix(),
        "size_mb": round(path.stat().st_size / (1024*1024), 2),
        "total_rows": total_rows,
        "cols_count": cols_count,
        "sep": sep,
        "utf8_valid": utf8_ok,
        "has_utf8_accents": has_utf8_accents,
        "has_latin1_accents": has_latin1_accents,
        "mojibake_in_utf8": mojibake_in_utf8,
        "mojibake_in_latin1": mojibake_in_latin1,
        "encoding_conclusion": encoding_conclusion,
        "read_enc": read_enc,
        "mismatched_rows": mismatched_rows,
        "header": header
    }

print("=== AUDITORÍA ATENCIONES DE URGENCIA ===")
for p in sorted(Path("data/raw/urgencias").glob("AtencionesUrgencia*.csv")):
    res = analyze_csv(p)
    print(f"{res['file']:28s} | {res['size_mb']:7.2f} MB | Filas: {res['total_rows']:9,d} | Cols: {res['cols_count']:2d} | Sep: '{res['sep']}' | UTF-8: {res['utf8_valid']} | Enc: {res['encoding_conclusion']} | Mismatched: {res['mismatched_rows']}")

print("\n=== AUDITORÍA EGRESOS HOSPITALARIOS ===")
for p in sorted(Path("data/raw/egresos").glob("*.csv")):
    res = analyze_csv(p)
    print(f"{res['file']:28s} | {res['size_mb']:7.2f} MB | Filas: {res['total_rows']:9,d} | Cols: {res['cols_count']:2d} | Sep: '{res['sep']}' | UTF-8: {res['utf8_valid']} | Enc: {res['encoding_conclusion']} | Mismatched: {res['mismatched_rows']}")
