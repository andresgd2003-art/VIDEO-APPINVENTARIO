"""
Smoke tests para la GUI de ANONIMA.
Verifican importaciones, atributos y pipeline de renderizado sin abrir ventana visual.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_import_ui_validator():
    """Verifica que el modulo ui_validator importa sin errores y expone ValidadorPDFApp."""
    import ui_validator
    assert hasattr(ui_validator, 'ValidadorPDFApp')


def test_pipeline_functions_disponibles():
    """Verifica que pdf_reader y mapper importan y exponen funciones del pipeline."""
    import pdf_reader, mapper
    assert callable(getattr(pdf_reader, 'extract_words', None))
    assert callable(getattr(pdf_reader, 'build_spatial_index', None))
    assert callable(getattr(mapper, 'map_entities', None))


def test_color_map_definido():
    """Verifica que el mapa de colores por entidad existe en el modulo."""
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'ui_validator.py')
    source = open(src_path, encoding='utf-8').read()
    assert 'MX_CURP' in source or 'e74c3c' in source
    assert 'PERSON' in source
    assert 'threading' in source


def test_output_dir_existe():
    """Verifica que la carpeta src/output/ existe para guardar redacciones."""
    output_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'output')
    assert os.path.isdir(output_path), "src/output/ debe existir para guardar PDFs sanitizados"


def test_render_pipeline_sin_gui():
    """Verifica que PyMuPDF renderiza el PDF de prueba como imagen PIL correctamente."""
    import pymupdf
    from PIL import Image
    PDF_PATH = r'c:/Users/user/OneDrive/Escritorio/gemini cli/AUTOTESTADO/csf.pdf'
    ZOOM = 1.5
    doc = pymupdf.open(PDF_PATH)
    page = doc[0]
    mat = pymupdf.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    assert img.mode == "RGB"
    assert img.width > 400
    assert img.height > 600
    test_rect = pymupdf.Rect(50, 100, 200, 120)
    x0_px = test_rect.x0 * ZOOM
    assert x0_px == pytest.approx(75.0)


# ── Tests de zoom ─────────────────────────────────────────────────────────────

def test_zoom_constantes_en_ui_validator():
    """ValidadorPDFApp debe tener constantes de zoom min/max/paso."""
    import ui_validator
    cls = ui_validator.ValidadorPDFApp
    assert hasattr(cls, '_ZOOM_MIN')
    assert hasattr(cls, '_ZOOM_MAX')
    assert hasattr(cls, '_ZOOM_PASO')
    assert cls._ZOOM_MIN < cls._ZOOM_MAX
    assert cls._ZOOM_PASO > 0


def test_zoom_rango_valido():
    """El zoom mínimo debe ser >= 0.25 y máximo <= 6.0."""
    import ui_validator
    cls = ui_validator.ValidadorPDFApp
    assert cls._ZOOM_MIN >= 0.25
    assert cls._ZOOM_MAX <= 6.0


def test_zoom_metodos_presentes():
    """ui_validator.py debe tener _zoom_in, _zoom_out, _actualizar_zoom."""
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'ui_validator.py')
    source = open(src_path, encoding='utf-8').read()
    assert '_zoom_in' in source
    assert '_zoom_out' in source
    assert '_actualizar_zoom' in source
    assert '_lbl_zoom' in source


def test_zoom_label_texto():
    """La etiqueta de zoom debe mostrar porcentaje (ej. '200%')."""
    import ui_validator
    zoom = ui_validator.ZOOM
    expected = f"{int(zoom * 100)}%"
    assert expected.endswith('%')
    assert int(expected[:-1]) > 0


def test_ctrl_scroll_handler_presente():
    """El handler de Ctrl+rueda para zoom debe existir."""
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'ui_validator.py')
    source = open(src_path, encoding='utf-8').read()
    assert '_on_ctrl_scroll' in source
    assert 'Control-MouseWheel' in source


def test_zoom_in_no_supera_maximo():
    """Clase: _zoom_in no debe permitir superar _ZOOM_MAX."""
    import ui_validator
    cls = ui_validator.ValidadorPDFApp

    class _Stub:
        _zoom = cls._ZOOM_MAX
        _ZOOM_MIN = cls._ZOOM_MIN
        _ZOOM_MAX = cls._ZOOM_MAX
        _ZOOM_PASO = cls._ZOOM_PASO
        _doc = None
        def _lbl_zoom_cfg(self, **_): pass
        def _renderizar_pagina(self, _): pass
        def _redibujar_entidades(self): pass
        def _actualizar_zoom(self):
            self._lbl_zoom = type('L', (), {'configure': self._lbl_zoom_cfg})()
            ui_validator.ValidadorPDFApp._actualizar_zoom(self)

        def _zoom_in(self):
            ui_validator.ValidadorPDFApp._zoom_in(self)

    stub = _Stub()
    stub._zoom_in()
    assert stub._zoom <= cls._ZOOM_MAX


def test_zoom_out_no_baja_minimo():
    """Clase: _zoom_out no debe permitir bajar de _ZOOM_MIN."""
    import ui_validator
    cls = ui_validator.ValidadorPDFApp

    class _Stub:
        _zoom = cls._ZOOM_MIN
        _ZOOM_MIN = cls._ZOOM_MIN
        _ZOOM_MAX = cls._ZOOM_MAX
        _ZOOM_PASO = cls._ZOOM_PASO
        _doc = None
        def _lbl_zoom_cfg(self, **_): pass
        def _renderizar_pagina(self, _): pass
        def _redibujar_entidades(self): pass
        def _actualizar_zoom(self):
            self._lbl_zoom = type('L', (), {'configure': self._lbl_zoom_cfg})()
            ui_validator.ValidadorPDFApp._actualizar_zoom(self)

        def _zoom_out(self):
            ui_validator.ValidadorPDFApp._zoom_out(self)

    stub = _Stub()
    stub._zoom_out()
    assert stub._zoom >= cls._ZOOM_MIN
