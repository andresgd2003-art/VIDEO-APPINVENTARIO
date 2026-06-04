"""Tests para verificar DPI y ZOOM_OCR de pdf_reader — sin depender de ui_validator."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest


def test_zoom_ocr_pdf_reader():
    """ZOOM_OCR en pdf_reader debe estar entre 1.5 y 5.0."""
    import pdf_reader
    assert 1.5 <= pdf_reader.ZOOM_OCR <= 5.0


def test_zoom_ocr_valor():
    """ZOOM_OCR debe ser exactamente 2.0 (144 DPI — PaddleOCR maneja bien fuentes pequeñas)."""
    import pdf_reader
    assert pdf_reader.ZOOM_OCR == 2.0


def test_padding_asimetrico_sanitizer():
    """Si sanitizer.py tiene padding asimétrico, LEFT debe ser >= RIGHT."""
    try:
        import sanitizer
        left  = getattr(sanitizer, '_PADDING_LEFT',  getattr(sanitizer, '_PADDING_X', 2.0))
        right = getattr(sanitizer, '_PADDING_RIGHT', getattr(sanitizer, '_PADDING_X', 2.0))
        assert left >= right, f"LEFT padding ({left}) debe ser >= RIGHT padding ({right})"
    except ImportError:
        pytest.skip("sanitizer no disponible")


def test_zoom_constantes_en_fuente():
    """El fuente de ui_validator debe declarar _ZOOM_MIN y _ZOOM_MAX."""
    src = os.path.join(os.path.dirname(__file__), '..', 'src', 'ui_validator.py')
    source = open(src, encoding='utf-8').read()
    assert '_ZOOM_MIN' in source
    assert '_ZOOM_MAX' in source
    assert '_ZOOM_PASO' in source


def test_ui_validator_zoom_minimo_en_fuente():
    """ui_validator debe definir zoom mínimo >= 0.25."""
    src = os.path.join(os.path.dirname(__file__), '..', 'src', 'ui_validator.py')
    source = open(src, encoding='utf-8').read()
    # Buscar línea _ZOOM_MIN = X
    for line in source.splitlines():
        if '_ZOOM_MIN' in line and '=' in line:
            val_str = line.split('=')[1].strip()
            try:
                val = float(val_str)
                assert val >= 0.25
            except ValueError:
                pass
            break


def test_ui_validator_usa_self_zoom():
    """ui_validator debe usar self._zoom (no la constante ZOOM fija) para renderizar."""
    src = os.path.join(os.path.dirname(__file__), '..', 'src', 'ui_validator.py')
    source = open(src, encoding='utf-8').read()
    assert 'self._zoom' in source, "Debe usar self._zoom para zoom dinámico"
    assert '_zoom_in' in source
    assert '_zoom_out' in source
