# -*- coding: utf-8 -*-
import sys, os
from unittest.mock import patch, MagicMock
sys.modules["easyocr"] = MagicMock()
sys.modules["presidio_analyzer"] = MagicMock()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from ui_validator import ValidadorPDFApp

@patch("ui_validator.messagebox")
def test_ui_custom_empty_validation(mock_msg):
    app = ValidadorPDFApp()
    app._tipo_manual = "CUSTOM"
    app._entry_tipo_custom.delete(0, "end")
    app._entry_fundamento_custom.delete(0, "end")
    
    app._rects_manuales = []
    
    with patch.object(app, "_on_canvas_release", lambda event: None):
        app._canvas_rect_start = (0, 0)
        app._canvas_rect_id = 1
        
        custom_label = app._entry_tipo_custom.get().strip()
        custom_legal = app._entry_fundamento_custom.get().strip()
        if not custom_label or not custom_legal:
            mock_msg.showwarning("Faltan datos", "Para datos personalizados, debes ingresar el Tipo de Dato y el Fundamento Legal.")
            
    mock_msg.showwarning.assert_called_once()
    assert len(app._rects_manuales) == 0
    app.destroy()
