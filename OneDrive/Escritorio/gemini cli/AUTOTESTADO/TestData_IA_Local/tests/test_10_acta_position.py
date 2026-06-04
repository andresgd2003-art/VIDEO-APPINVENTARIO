# -*- coding: utf-8 -*-
import sys, os, pymupdf
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from report_generator import generate_justification_page

def test_acta_position():
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    initial_len = len(doc)
    
    info_reporte = [{"entity_type": "MX_CURP", "pagina": 0, "y0": 10}]
    generate_justification_page(doc, info_reporte, "test.pdf")
    
    assert len(doc) == initial_len + 1
    text = doc[-1].get_text()
    assert "Acta" in text or "Clasificaci" in text
    doc.close()
