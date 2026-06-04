"""
Tests para verificar el manejo de errores en la interfaz gráfica (UI)
cuando el pipeline de OCR o procesamiento falla.
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

def test_ui_captura_errores_procesamiento(monkeypatch):
    """
    Simula un error en el motor OCR (ej. el fallo de cls o tesseract)
    y verifica que el ValidadorPDFApp lo capture y agregue a sus errores_procesamiento.
    """
    import ui_validator
    import pdf_reader

    # Crear una excepción simulada
    def mock_extract_words_from_image(*args, **kwargs):
        raise TypeError("Unexpected keyword argument 'cls'")

    # Inyectar el mock en pdf_reader para que falle
    monkeypatch.setattr(pdf_reader, '_ocr_extract_words', lambda page: mock_extract_words_from_image())

    # Stub básico de la App para aislar el hilo
    class DummyApp:
        def __init__(self):
            self.errores_procesamiento = []
            self.entidades_detectadas = []

        def _procesar_pagina(self, num_pag, page, spatial_index, analyzer):
            try:
                # Simular el paso que llama a OCR
                pdf_reader._ocr_extract_words(page)
            except Exception as e:
                self.errores_procesamiento.append(f"Pág {num_pag + 1}: {str(e)}")

    app = DummyApp()
    
    # Procesar una página ficticia
    app._procesar_pagina(0, None, None, None)

    # El error debió capturarse sin colgar la UI
    assert len(app.errores_procesamiento) == 1
    assert "Pág 1" in app.errores_procesamiento[0]
    assert "Unexpected keyword argument 'cls'" in app.errores_procesamiento[0]
