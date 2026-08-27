import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

DICT_PATH = Path("data/raw/urgencias/DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx")

def dump_sheet3(path):
    with zipfile.ZipFile(path, 'r') as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                t = si.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                shared_strings.append(t.text if t is not None else "")

        sheet_file = 'xl/worksheets/sheet3.xml'
        s_tree = ET.fromstring(z.read(sheet_file))
        rows = s_tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
        print(f"=== TODAS LAS CAUSAS EN DICCIONARIO OFICIAL DEIS (Total filas: {len(rows)}) ===")
        for r in rows:
            row_vals = []
            for c in r.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                t_type = c.attrib.get('t')
                if v is not None:
                    val = v.text
                    if t_type == 's' and val.isdigit():
                        val = shared_strings[int(val)]
                    row_vals.append(val)
                else:
                    row_vals.append("")
            if any(row_vals):
                print(" | ".join(row_vals))

dump_sheet3(DICT_PATH)
