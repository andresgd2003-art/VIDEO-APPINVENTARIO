import sys, os
from unittest.mock import MagicMock
sys.modules["easyocr"] = MagicMock()
sys.modules["presidio_analyzer"] = MagicMock()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from ui_validator import ValidadorPDFApp

def test_ui_custom_save():
    app = ValidadorPDFApp()
    app._tipo_manual = "CUSTOM"
    app._pagina_actual = 0
    app._entry_tipo_custom.insert(0, "Test Label")
    app._entry_fundamento_custom.insert(0, "Test Legal")
    app._entry_motivacion_custom.insert(0, "Test Motivacion")
    
    # Simulate a drag and release
    app._modo_manual = True
    app._drag_inicio = (10, 10)
    app._id_rect_temporal = 999
    app._zoom = 1.0
    
    evento = MagicMock()
    evento.x = 100
    evento.y = 100
    
    app._on_canvas_release(evento)
    
    assert len(app._rects_manuales) == 1
    assert app._rects_manuales[0]["custom_label"] == "Test Label"
    assert app._rects_manuales[0]["custom_legal"] == "Test Legal"
    assert app._rects_manuales[0]["custom_motivacion"] == "Test Motivacion"
    app.destroy()
