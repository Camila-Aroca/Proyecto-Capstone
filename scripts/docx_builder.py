"""Utilidades de construcción de documentos Word (.docx) para la documentación del proyecto.

Provee una capa delgada sobre `python-docx` con estilos, portadas, tablas e índices
consistentes, de modo que los documentos formales del proyecto sean reproducibles
mediante código versionado.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# Paleta institucional del documento
COLOR_H1 = RGBColor(0x1F, 0x3B, 0x63)
COLOR_H2 = RGBColor(0x2E, 0x5E, 0x8C)
COLOR_H3 = RGBColor(0x44, 0x54, 0x6A)
COLOR_TEXT = RGBColor(0x1A, 0x1A, 0x1A)
COLOR_MUTED = RGBColor(0x59, 0x59, 0x59)
SHADE_HEADER = "1F3B63"
SHADE_SOFT = "EAF0F6"
SHADE_NOTE = "FFF4E5"

BODY_FONT = "Calibri"
MONO_FONT = "Consolas"


# --------------------------------------------------------------------------------------
# Infraestructura de bajo nivel (OOXML)
# --------------------------------------------------------------------------------------
def _set_cell_background(cell, hex_fill: str) -> None:
    """Aplica un color de fondo sólido a una celda de tabla."""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _repeat_header_row(row) -> None:
    """Marca una fila como encabezado que se repite en cada página."""
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _add_field(paragraph, instruction: str) -> None:
    """Inserta un campo dinámico de Word (por ejemplo, PAGE o TOC)."""
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    for element in (fld_begin, instr, fld_sep, fld_end):
        run._r.append(element)


def _enable_update_fields(document: Document) -> None:
    """Solicita a Word que actualice los campos (índice, páginas) al abrir el archivo."""
    try:
        settings = document.settings.element
    except (AttributeError, KeyError):
        return
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


# --------------------------------------------------------------------------------------
# Texto enriquecido
# --------------------------------------------------------------------------------------
_INLINE_PATTERN = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def add_rich_text(paragraph, text: str, size: Optional[float] = None) -> None:
    """Escribe texto admitiendo marcas simples: **negrita** y `monoespaciado`."""
    for token in _INLINE_PATTERN.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = MONO_FONT
            run.font.size = Pt((size or 10.5) - 0.5)
        else:
            run = paragraph.add_run(token)
        if size is not None and run.font.size is None:
            run.font.size = Pt(size)


# --------------------------------------------------------------------------------------
# Documento y estilos base
# --------------------------------------------------------------------------------------
def new_document(footer_text: str) -> Document:
    """Crea un documento con márgenes, tipografía, estilos y pie de página del proyecto."""
    document = Document()

    section = document.sections[0]
    section.page_width = Cm(21.59)
    section.page_height = Cm(27.94)
    section.left_margin = Cm(1.9)
    section.right_margin = Cm(1.9)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.0)

    normal = document.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = COLOR_TEXT
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for style_name, size, color, space_before in (
        ("Heading 1", 16, COLOR_H1, 18),
        ("Heading 2", 13, COLOR_H2, 14),
        ("Heading 3", 11.5, COLOR_H3, 10),
    ):
        style = document.styles[style_name]
        style.font.name = BODY_FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style.paragraph_format.space_before = Pt(space_before)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True

    _build_footer(section, footer_text)
    _enable_update_fields(document)
    return document


def _build_footer(section, footer_text: str) -> None:
    """Construye el pie de página con identificación del documento y numeración."""
    paragraph = section.footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(f"{footer_text}  |  Página ")
    run.font.size = Pt(8)
    run.font.color.rgb = COLOR_MUTED
    _add_field(paragraph, " PAGE ")
    run = paragraph.add_run(" de ")
    run.font.size = Pt(8)
    run.font.color.rgb = COLOR_MUTED
    _add_field(paragraph, " NUMPAGES ")
    for run in paragraph.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = COLOR_MUTED


# --------------------------------------------------------------------------------------
# Bloques de contenido
# --------------------------------------------------------------------------------------
def add_cover(
    document: Document,
    title: str,
    subtitle: str,
    project: str,
    meta_rows: Sequence[Tuple[str, str]],
) -> None:
    """Genera la portada del documento."""
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(48)

    para = document.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(project.upper())
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = COLOR_MUTED

    para = document.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(18)
    run = para.add_run(title)
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = COLOR_H1

    para = document.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after = Pt(36)
    run = para.add_run(subtitle)
    run.font.size = Pt(12)
    run.font.color.rgb = COLOR_H2

    add_table(document, ["Campo", "Detalle"], meta_rows, [Cm(5.0), Cm(12.7)], font_size=10)
    document.add_page_break()


def add_toc(document: Document, title: str = "Tabla de contenidos") -> None:
    """Inserta un índice automático que Word actualiza al abrir el documento."""
    heading = document.add_paragraph(title, style="Heading 1")
    heading.paragraph_format.space_before = Pt(0)
    para = document.add_paragraph()
    _add_field(para, r' TOC \o "1-2" \h \z \u ')
    note = document.add_paragraph()
    run = note.add_run(
        "Si el índice no se muestra actualizado, seleccionarlo y presionar F9 en Microsoft Word."
    )
    run.font.size = Pt(8.5)
    run.font.italic = True
    run.font.color.rgb = COLOR_MUTED
    document.add_page_break()


def h1(document: Document, text: str) -> None:
    document.add_paragraph(text, style="Heading 1")


def h2(document: Document, text: str) -> None:
    document.add_paragraph(text, style="Heading 2")


def h3(document: Document, text: str) -> None:
    document.add_paragraph(text, style="Heading 3")


def p(document: Document, text: str, italic: bool = False, size: float = 10.5) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_rich_text(paragraph, text, size=size)
    if italic:
        for run in paragraph.runs:
            run.font.italic = True


def bullets(document: Document, items: Iterable[str], size: float = 10.5) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(3)
        add_rich_text(paragraph, item, size=size)


def numbered(document: Document, items: Iterable[str], size: float = 10.5) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(3)
        add_rich_text(paragraph, item, size=size)


def note(document: Document, text: str, fill: str = SHADE_NOTE) -> None:
    """Cuadro destacado para notas, advertencias o supuestos."""
    table = document.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    _set_cell_background(cell, fill)
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(4)
    add_rich_text(paragraph, text, size=10)
    document.add_paragraph().paragraph_format.space_after = Pt(2)


def add_table(
    document: Document,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Optional[Sequence[Cm]] = None,
    font_size: float = 9.0,
    first_col_bold: bool = False,
) -> None:
    """Inserta una tabla con encabezado destacado, filas cebra y ancho fijo por columna."""
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = widths is None

    header_cells = table.rows[0].cells
    for index, text in enumerate(headers):
        cell = header_cells[index]
        _set_cell_background(cell, SHADE_HEADER)
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(2)
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(text)
        run.bold = True
        run.font.size = Pt(font_size)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    _repeat_header_row(table.rows[0])

    for row_index, row_values in enumerate(rows):
        cells = table.add_row().cells
        for col_index, value in enumerate(row_values):
            cell = cells[col_index]
            if row_index % 2 == 1:
                _set_cell_background(cell, SHADE_SOFT)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(2)
            paragraph.paragraph_format.space_after = Pt(2)
            add_rich_text(paragraph, str(value), size=font_size)
            for run in paragraph.runs:
                run.font.size = Pt(font_size)
                if first_col_bold and col_index == 0:
                    run.bold = True

    if widths:
        for row in table.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = width

    document.add_paragraph().paragraph_format.space_after = Pt(4)


def add_definition_block(document: Document, title: str, lines: Sequence[Tuple[str, str]]) -> None:
    """Bloque etiqueta-valor usado en casos de uso y fichas de requisito."""
    h3(document, title)
    add_table(
        document,
        ["Elemento", "Detalle"],
        lines,
        [Cm(4.2), Cm(13.5)],
        font_size=9.5,
        first_col_bold=True,
    )


def save(document: Document, path: Path) -> Path:
    """Guarda el documento creando el directorio destino si es necesario."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    return path
