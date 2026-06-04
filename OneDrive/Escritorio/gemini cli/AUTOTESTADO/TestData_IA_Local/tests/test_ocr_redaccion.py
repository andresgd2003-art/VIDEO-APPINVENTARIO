"""
Test de integración end-to-end del flujo ESCANEADO (OCR):

    PDF imagen → PaddleOCR → detector → mapper → recuadros → sanitize_page → re-OCR

Verifica que, sobre un PDF realmente escaneado:
  1. La reconstrucción de palabras OCR permite detectar el nombre completo
     (regresión del bug donde los acentos partidos rompían el NER).
  2. Los recuadros de redacción TAPAN efectivamente la palabra: tras aplicar
     sanitize_page, un segundo pase de OCR ya no encuentra el texto sensible.

Es un test lento (PaddleOCR en CPU, ~40-80 s). Se omite automáticamente si
PaddleOCR no está disponible o si el PDF escaneado de prueba no existe.
"""
import os
import sys
import unicodedata

import pytest
import pymupdf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pdf_reader
import detector
import mapper
import sanitizer

# PDF escaneado de prueba (imagen pura, 2 páginas). Ruta relativa al repo.
_SCAN = os.path.join(os.path.dirname(__file__), "..", "docs", "CASO SIMULADO 2_scan.pdf")


def _norm(s: str) -> str:
    """Normaliza para comparación robusta: sin acentos, mayúsculas."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()


def _ocr_texto_pagina(page) -> str:
    return " ".join(w[4] for w in pdf_reader._ocr_extract_words(page))


@pytest.mark.slow
def test_redaccion_escaneado_tapa_el_nombre():
    if not os.path.exists(_SCAN):
        pytest.skip(f"PDF escaneado de prueba no encontrado: {_SCAN}")
    if not hasattr(pdf_reader, "_get_paddle") or pdf_reader._get_paddle() is None:
        pytest.skip("PaddleOCR no disponible")

    analizador = detector.build_analyzer()
    doc = pdf_reader.open_pdf(_SCAN)
    page = doc[0]
    assert pdf_reader.es_pagina_escaneada(page), "La página de prueba debe ser escaneada"

    # 1. Pipeline completo de detección sobre la página escaneada
    words = pdf_reader.extract_words(page)
    idx = pdf_reader.build_spatial_index(words, page)
    texto = " ".join(e["word"] for e in idx)
    crudo = detector.analyze_page(analizador, texto)
    dicts = [
        {"entity_type": r.entity_type, "text": texto[r.start:r.end],
         "start": r.start, "end": r.end, "score": r.score}
        for r in crudo
    ]
    entidades = mapper.map_entities(idx, dicts)

    # Regresión del fix de acentos: el nombre completo debe aparecer en el OCR
    # (antes salía fragmentado como "MIGUEL Á NGEL CORT É S" y no se detectaba).
    assert "MIGUEL" in _norm(texto), "El OCR debería reconstruir el nombre completo"

    personas = [e for e in entidades if e["entity_type"] in ("Persona", "PERSON")]
    assert any("MIGUEL" in _norm(e.get("text", "")) for e in personas), \
        f"Se esperaba detectar a MIGUEL como Persona. Detectadas: {[e.get('text') for e in personas]}"

    # 2. Aplicar redacción con TODOS los rects detectados
    rects = [r for e in entidades for r in e["rects"]]
    assert rects, "Debe haber al menos un recuadro de redacción"
    sanitizer.sanitize_page(page, rects)

    # 3. Segundo pase de OCR: el nombre ya no debe ser legible → el recuadro tapó la palabra
    texto_redactado = _ocr_texto_pagina(page)
    assert "MIGUEL" not in _norm(texto_redactado), (
        "Tras redactar, el nombre sigue siendo legible por OCR — "
        "el recuadro no cubrió correctamente la palabra"
    )
