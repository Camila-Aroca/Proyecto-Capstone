"""Exporta docs/11-manual-usuario/README.md a docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx (python-docx).

Uso: python scripts/export_manual_usuario_docx.py
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "docs/11-manual-usuario/README.md"
CAPTURAS = RAIZ / "docs/11-manual-usuario/capturas"
OUT = RAIZ / "docs/05-entregas/Fase_2_3/Manual_Usuario_SAAD.docx"

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("python-docx no instalado", file=sys.stderr)
    sys.exit(1)

doc = Document()

# Estilos básicos
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(11)

EN_LINEA = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def escribir(parrafo, texto):
    """Agrega el texto al párrafo convirtiendo negrita, cursiva, código y enlaces de Markdown."""
    for trozo in EN_LINEA.split(texto):
        if not trozo:
            continue
        if trozo.startswith("**") and trozo.endswith("**"):
            parrafo.add_run(trozo[2:-2]).bold = True
        elif trozo.startswith("`") and trozo.endswith("`"):
            parrafo.add_run(trozo[1:-1]).font.name = "Consolas"
        elif trozo.startswith("[") and "](" in trozo:
            parrafo.add_run(trozo[1:trozo.index("](")])
        elif trozo.startswith("*") and trozo.endswith("*") and len(trozo) > 2:
            parrafo.add_run(trozo[1:-1]).italic = True
        else:
            parrafo.add_run(trozo)
    return parrafo


def celda(c, texto, negrita=False):
    c.text = ""
    escribir(c.paragraphs[0], texto)
    if negrita:
        for r in c.paragraphs[0].runs:
            r.bold = True


def add_heading(text, level):
    p = doc.add_heading(text, level=level)
    return p

def add_para(text):
    return doc.add_paragraph(text)

def add_table_row(table, cells):
    row = table.add_row()
    for i, cell in enumerate(cells):
        row.cells[i].text = cell
    return row

IMG_RE = re.compile(r"!\[([^\]]*)\]\(capturas/([^)]+)\)")
TABLE_RE = re.compile(r"^\|(.+)\|$")
H1_RE = re.compile(r"^# (.+)$")
H2_RE = re.compile(r"^## (.+)$")
H3_RE = re.compile(r"^### (.+)$")
H4_RE = re.compile(r"^#### (.+)$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]+)`")

lines = SRC.read_text(encoding="utf-8").splitlines()

i = 0
while i < len(lines):
    line = lines[i]

    # Headings
    if m := H1_RE.match(line):
        doc.add_heading(m.group(1), 0)
        i += 1; continue
    if m := H2_RE.match(line):
        doc.add_heading(m.group(1), 1)
        i += 1; continue
    if m := H3_RE.match(line):
        doc.add_heading(m.group(1), 2)
        i += 1; continue
    if m := H4_RE.match(line):
        doc.add_heading(m.group(1), 3)
        i += 1; continue

    # Images
    if m := IMG_RE.search(line):
        img_path = CAPTURAS / m.group(2)
        if img_path.exists():
            try:
                doc.add_picture(str(img_path), width=Inches(5.5))
                cap = doc.add_paragraph(m.group(1))
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap.runs[0].italic = True
            except Exception as e:
                doc.add_paragraph(f"[Captura: {m.group(2)} — {e}]")
        else:
            doc.add_paragraph(f"[Captura no encontrada: {m.group(2)}]")
        i += 1; continue

    # Markdown tables
    if TABLE_RE.match(line):
        table_lines = []
        while i < len(lines) and TABLE_RE.match(lines[i]):
            table_lines.append(lines[i])
            i += 1
        # Parse headers
        headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
        n_cols = len(headers)
        tbl = doc.add_table(rows=1, cols=n_cols)
        tbl.style = "Table Grid"
        hdr_cells = tbl.rows[0].cells
        for j, h in enumerate(headers):
            celda(hdr_cells[j], h, negrita=True)
        for tl in table_lines[2:]:  # skip separator
            cells = [c.strip() for c in tl.strip("|").split("|")]
            row = tbl.add_row()
            for j in range(min(n_cols, len(cells))):
                celda(row.cells[j], cells[j])
        doc.add_paragraph()
        continue

    # Horizontal rules
    if line.strip() == "---":
        i += 1; continue

    # Blockquotes
    if line.startswith("> "):
        escribir(doc.add_paragraph(style="Quote"), line[2:])
        i += 1; continue

    # Bullet lists
    if re.match(r"^\s+- ", line):
        escribir(doc.add_paragraph(style="List Bullet 2"), line.strip()[2:])
        i += 1; continue
    if line.startswith("- "):
        escribir(doc.add_paragraph(style="List Bullet"), line[2:])
        i += 1; continue

    # Numbered lists
    if re.match(r"^\d+\. ", line):
        escribir(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\. ", "", line))
        i += 1; continue

    # Empty lines
    if not line.strip():
        i += 1; continue

    # Normal paragraph — strip inline markdown
    escribir(doc.add_paragraph(), line)
    i += 1

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT))
print(f"Guardado: {OUT}")
