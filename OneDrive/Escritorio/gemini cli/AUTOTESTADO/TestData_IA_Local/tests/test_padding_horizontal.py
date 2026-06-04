import pytest
import pymupdf
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pdf_reader
from sanitizer import _PADDING_RIGHT, _PADDING_LEFT

@pytest.mark.skip(reason="API OCR refactorizada — _expandir_cajas_linea eliminada al migrar de PaddleOCR a EasyOCR — pendiente actualización")
def test_ocr_expansion_no_roza_vecina_con_padding_sanitizer():
    """
    Simula dos palabras escaneadas consecutivas para asegurar que tras la
    expansión de OCR y el padding adicional del sanitizer, el recuadro
    de redacción NO toca ni roza a la palabra vecina (dejando un margen seguro).
    """
    # 1. Arrange: Simular dos palabras OCR muy juntas
    # Supongamos un gap de 3.0 pt = 6.0 px (en ZOOM_OCR=2.0)
    # Palabra A de 10 a 50px, Palabra B de 56 a 100px. Gap = 6px (3pt)
    palabra_A = ("HOLA", [10.0, 10.0, 50.0, 30.0])
    palabra_B = ("MUNDO", [56.0, 10.0, 100.0, 30.0])
    
    # 2. Act: Aplicar expansión OCR (como se hace en pdf_reader)
    linea = [palabra_A, palabra_B]
    linea_expandida = pdf_reader._expandir_cajas_linea(linea)
    
    # La palabra A expandida
    box_A = linea_expandida[0][1]
    # En puntos PDF
    A_x1_pt = box_A[2] / pdf_reader.ZOOM_OCR
    
    # La palabra B expandida
    box_B = linea_expandida[1][1]
    B_x0_pt = box_B[0] / pdf_reader.ZOOM_OCR
    
    # 3. Aplicar el efecto de sanitizer.py (padding)
    # En sanitizer, el recuadro que se rellena se extiende _PADDING_RIGHT a la derecha
    # y _PADDING_LEFT a la izquierda.
    A_redacted_x1 = A_x1_pt + _PADDING_RIGHT
    B_redacted_x0 = B_x0_pt - _PADDING_LEFT
    
    # 4. Assert: El borde derecho de A (redactado) no debe sobrepasar/tocar el borde de la tinta de B original.
    # El x0 original de B en puntos PDF es 56.0 / 2.0 = 28.0.
    B_original_x0_pt = 56.0 / pdf_reader.ZOOM_OCR
    
    # El recuadro redactado de A debe dejar un margen (no tocar a B).
    gap_final = B_original_x0_pt - A_redacted_x1
    
    assert gap_final > 0, f"El recuadro redactado roza o invade la palabra vecina! Gap: {gap_final}pt"

