import pymupdf
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from report_generator import generate_justification_page

def test_generate_justification_page_empty():
    doc = pymupdf.open()
    doc.new_page()
    original_len = len(doc)
    
    generate_justification_page(doc, [], "test.pdf")
    
    assert len(doc) == original_len, "No debe añadir páginas si info_reporte está vacío."

def test_generate_justification_page_with_data():
    doc = pymupdf.open()
    doc.new_page()  # Página original
    original_len = len(doc)
    
    info_reporte = [
        {"entity_type": "PERSON", "pagina": 0, "y0": 100, "manual": False},
        {"entity_type": "MX_RFC", "pagina": 0, "y0": 200, "manual": True},
        {"entity_type": "MX_DOMICILIO", "pagina": 0, "y0": 300, "manual": False},
    ]
    
    generate_justification_page(doc, info_reporte, "test.pdf")
    
    assert len(doc) > original_len, "Debe añadir al menos una página de acta."
    
    text = ""
    for page in doc:
        text += page.get_text()

    low = text.lower()
    # El encabezado se muestra en versalitas vía CSS (text-transform); el texto
    # extraído conserva la capitalización original "Acta del Comité de Transparencia".
    assert "acta del comité" in low
    assert "transparencia" in low
    # Los datos marcados a mano se anotan con el indicador "(manual)" en la tabla.
    assert "(manual)" in text
    assert "test.pdf" in text
