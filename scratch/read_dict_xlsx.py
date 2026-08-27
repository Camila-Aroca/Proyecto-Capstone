import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

DICT_PATH = Path("data/raw/urgencias/DICCIONARIO_ATENCIONES_DE_URGENCIA.xlsx")

def read_xlsx_xml(path):
    with zipfile.ZipFile(path, 'r') as z:
        # Read shared strings
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                t = si.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                shared_strings.append(t.text if t is not None else "")

        # Read workbook to get sheet names
        wb_tree = ET.fromstring(z.read('xl/workbook.xml'))
        sheets = wb_tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet')
        
        print("Hojas encontradas:")
        for idx, sheet in enumerate(sheets, 1):
            name = sheet.attrib.get('name')
            r_id = sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            sheet_file = f'xl/worksheets/sheet{idx}.xml'
            print(f"\n--- Hoja {idx}: {name} ({sheet_file}) ---")
            
            if sheet_file in z.namelist():
                s_tree = ET.fromstring(z.read(sheet_file))
                rows = s_tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
                print(f"Total filas: {len(rows)}")
                for r in rows[:35]: # print first 35 rows
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
                    print(" | ".join(row_vals))

read_xlsx_xml(DICT_PATH)
