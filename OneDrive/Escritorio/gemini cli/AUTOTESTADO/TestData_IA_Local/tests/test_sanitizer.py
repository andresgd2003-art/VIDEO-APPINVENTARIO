import pytest
import pymupdf
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from sanitizer import sanitize_page

def test_sanitize_page():
    # 1. Arrange: Create a PDF with some text
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(pymupdf.Point(50, 50), "Mi RFC es VECJ881212XYZ")
    
    # Find the bounding box for "VECJ881212XYZ"
    words = page.get_text("words")
    secret_rect = None
    for w in words:
        if "VECJ881212XYZ" in w[4]:
            secret_rect = pymupdf.Rect(w[:4])
            break
            
    assert secret_rect is not None, "Failed to setup test pdf with secret text"
    assert "VECJ881212XYZ" in page.get_text("text"), "Secret text is not in original PDF"
    
    # 2. Act: Redact the secret_rect
    sanitize_page(page, [secret_rect])
    
    # 3. Assert: sanitize_page reemplaza la página completa con imagen (modelo forense),
    # por lo que get_text() queda vacío — ningún texto es extraíble, incluyendo el secreto.
    final_text = page.get_text("text")
    assert "VECJ881212XYZ" not in final_text, "Text was not successfully destroyed"
    # La página es ahora una imagen pura — no hay texto extraíble en absoluto
    assert final_text.strip() == "", "Página sanitizada debe ser imagen sin texto extraíble"


def test_sanitize_cubre_pixeles_de_la_palabra():
    """
    Verifica a nivel de PÍXEL que el recuadro de redacción realmente tapa la
    palabra: antes de redactar la zona del texto tiene tinta oscura; después
    queda completamente negra. Garantiza que "los recuadros tapan las palabras".
    """
    import numpy as np

    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text(pymupdf.Point(50, 100), "CONFIDENCIAL", fontsize=14)

    rect = None
    for w in page.get_text("words"):
        if "CONFIDENCIAL" in w[4]:
            rect = pymupdf.Rect(w[:4])
            break
    assert rect is not None, "No se ubicó la palabra de prueba"

    Z = 2.0

    def _nucleo(pg):
        """Píxeles del interior del rect (con margen para evitar bordes antialias)."""
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), alpha=False)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
        x0 = int(rect.x0 * Z) + 2
        x1 = int(rect.x1 * Z) - 2
        y0 = int(rect.y0 * Z) + 1
        y1 = int(rect.y1 * Z) - 1
        return img[y0:y1, x0:x1]

    antes = _nucleo(page)
    assert antes.min() < 100, "Antes de redactar debe haber tinta oscura (texto) en la zona"

    sanitize_page(page, [rect])

    despues = _nucleo(page)
    assert despues.max() < 30, (
        f"La zona de la palabra debe quedar negra tras redactar; "
        f"valor máximo de píxel = {despues.max()}"
    )
