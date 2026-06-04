import sys, os
from unittest.mock import MagicMock
sys.modules["easyocr"] = MagicMock()
sys.modules["presidio_analyzer"] = MagicMock()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
import customtkinter as ctk
from ui_validator import ValidadorPDFApp

def test_ui_combobox_custom():
    app = ValidadorPDFApp()
    app._on_tipo_manual_cambio("Personalizado...")
    app.update_idletasks() # Let tkinter process the pack()
    assert bool(app._frame_custom.winfo_ismapped()) == True or bool(app._frame_custom.pack_info()) == True
    app.destroy()
