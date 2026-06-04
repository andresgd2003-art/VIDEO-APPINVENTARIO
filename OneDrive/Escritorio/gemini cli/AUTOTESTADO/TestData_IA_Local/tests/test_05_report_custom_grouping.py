# -*- coding: utf-8 -*-
import sys, os, pymupdf
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from report_generator import generate_justification_page

def test_report_custom_grouping():
    info_reporte = [
        {"entity_type": "CUSTOM", "custom_label": "A", "custom_legal": "Ley A", "custom_motivacion": "Mot A", "pagina": 0, "y0": 10},
        {"entity_type": "CUSTOM", "custom_label": "B", "custom_legal": "Ley B", "custom_motivacion": "Mot B", "pagina": 0, "y0": 20},
        {"entity_type": "CUSTOM", "custom_label": "A", "custom_legal": "Ley A", "custom_motivacion": "Mot A", "pagina": 1, "y0": 30},
    ]
    doc = pymupdf.open()
    doc.new_page()
    generate_justification_page(doc, info_reporte, "test.pdf")
    
    text = doc[-1].get_text()
    assert "Ley A" in text
    assert "Ley B" in text
    doc.close()
