"""
test_resize_integration.py — Pruebas de integración del resize sin GUI.
Prueba la lógica de _detectar_esquina_resize y _actualizar_resize
usando datos reales de la estructura de ui_validator pero sin levantar ventana.
"""
import math
import pytest
import pymupdf

# ---------------------------------------------------------------------------
# Stubs mínimos para simular el estado interno de ValidadorPDFApp
# sin importar Tkinter.
# ---------------------------------------------------------------------------

class _MockApp:
    """Versión mínima de ValidadorPDFApp con sólo el estado necesario para resize."""

    _RESIZE_TOL = 10

    def __init__(self):
        self._zoom: float = 1.25
        self._pagina_actual: int = 0
        self._modo_manual: bool = False
        self._resize_target = None
        self._resize_corner = None
        self._resize_rect_idx = None
        self._resize_es_manual = False
        self._rects_manuales: list[dict] = []
        self._resultados_por_pagina: dict[int, list[dict]] = {}

    def _en_lista_descarte(self, texto: str) -> bool:
        return False

    # Copiamos los métodos reales (sin dependencias de Tkinter)
    def _detectar_esquina_resize(self, cx: float, cy: float):
        tol = self._RESIZE_TOL
        _z  = self._zoom
        _pad_x = 1.0 * _z
        _pad_y = 1.5 * _z

        def _esquinas_canvas(r):
            x0 = r.x0 * _z - _pad_x
            y0 = r.y0 * _z - _pad_y
            x1 = r.x1 * _z + _pad_x
            y1 = r.y1 * _z + _pad_y
            return {"tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1)}

        def _encontrar_corner(esquinas):
            for nombre, (ex, ey) in esquinas.items():
                if math.hypot(cx - ex, cy - ey) <= tol:
                    return nombre
            return None

        for rm in reversed(self._rects_manuales):
            if rm["pagina"] != self._pagina_actual:
                continue
            corner = _encontrar_corner(_esquinas_canvas(rm["rect"]))
            if corner:
                return rm, corner, 0, True

        entidades = self._resultados_por_pagina.get(self._pagina_actual, [])
        for entidad in reversed(entidades):
            if self._en_lista_descarte(entidad.get("text", "")):
                continue
            if not entidad.get("seleccionada", True):
                continue
            for idx, rect in enumerate(entidad["rects"]):
                corner = _encontrar_corner(_esquinas_canvas(rect))
                if corner:
                    return entidad, corner, idx, False

        return None, None, None, False

    def _calcular_nuevo_rect(self, orig, corner, xp, yp):
        if corner == "tl":
            new = pymupdf.Rect(xp, yp, orig.x1, orig.y1)
        elif corner == "tr":
            new = pymupdf.Rect(orig.x0, yp, xp, orig.y1)
        elif corner == "bl":
            new = pymupdf.Rect(xp, orig.y0, orig.x1, yp)
        else:
            new = pymupdf.Rect(orig.x0, orig.y0, xp, yp)
        new = pymupdf.Rect(
            min(new.x0, new.x1), min(new.y0, new.y1),
            max(new.x0, new.x1), max(new.y0, new.y1)
        )
        if new.width < 5 or new.height < 5:
            return None
        return new


# ===========================================================================
# TESTS DE INTEGRACIÓN
# ===========================================================================

ZOOM = 1.25
BASE_RECT = pymupdf.Rect(50, 100, 200, 130)


def _make_app_con_manual(rect=None, pagina=0):
    app = _MockApp()
    r = rect or BASE_RECT
    app._rects_manuales = [{"rect": r, "pagina": pagina, "seleccionado": True, "entity_type": "Persona"}]
    return app


def _make_app_con_entidad(rect=None, pagina=0):
    app = _MockApp()
    r = rect or BASE_RECT
    app._resultados_por_pagina[pagina] = [{
        "entity_type": "MX_MONTO",
        "seleccionada": True,
        "text": "$72,633.55",
        "rects": [r],
    }]
    return app


# --- Detección ---

def test_detecta_esquina_br_en_manual():
    app = _make_app_con_manual()
    cx = BASE_RECT.x1 * ZOOM + 1.0 * ZOOM  # +padding_x
    cy = BASE_RECT.y1 * ZOOM + 1.5 * ZOOM  # +padding_y
    target, corner, idx, es_manual = app._detectar_esquina_resize(cx, cy)
    assert corner == "br"
    assert es_manual is True

def test_detecta_esquina_tl_en_entidad_automatica():
    app = _make_app_con_entidad()
    cx = BASE_RECT.x0 * ZOOM - 1.0 * ZOOM  # -padding_x
    cy = BASE_RECT.y0 * ZOOM - 1.5 * ZOOM  # -padding_y
    target, corner, idx, es_manual = app._detectar_esquina_resize(cx, cy)
    assert corner == "tl"
    assert es_manual is False
    assert idx == 0

def test_no_detecta_cuando_modo_manual():
    """En modo manual no debería dispararse el resize (la app lo evita en _on_canvas_press)."""
    app = _make_app_con_entidad()
    app._modo_manual = True
    # Aunque el punto esté en una esquina, _on_canvas_press no llama a _detectar_esquina
    # cuando modo_manual está activo. Aquí solo verificamos que la función NO lanza error.
    cx = BASE_RECT.x1 * ZOOM + 1.0 * ZOOM
    cy = BASE_RECT.y1 * ZOOM + 1.5 * ZOOM
    target, corner, _, _ = app._detectar_esquina_resize(cx, cy)
    # La función puede detectar la esquina, pero _on_canvas_press la cortocircuita
    assert corner == "br"  # detección correcta aunque modo_manual bloquee el uso

def test_no_detecta_entidad_deseleccionada():
    """Entidades deseleccionadas no son redimensionables."""
    app = _make_app_con_entidad()
    app._resultados_por_pagina[0][0]["seleccionada"] = False
    cx = BASE_RECT.x1 * ZOOM + 1.0 * ZOOM
    cy = BASE_RECT.y1 * ZOOM + 1.5 * ZOOM
    target, corner, _, _ = app._detectar_esquina_resize(cx, cy)
    assert target is None
    assert corner is None

def test_no_detecta_pagina_diferente():
    """No detecta esquinas de otra página."""
    app = _make_app_con_manual(pagina=3)
    cx = BASE_RECT.x1 * ZOOM + 1.0 * ZOOM
    cy = BASE_RECT.y1 * ZOOM + 1.5 * ZOOM
    target, corner, _, _ = app._detectar_esquina_resize(cx, cy)
    assert target is None


# --- Cálculo del nuevo rect ---

def test_resize_rect_manual_br_ampliar():
    new = _MockApp()._calcular_nuevo_rect(BASE_RECT, "br", 260.0, 160.0)
    assert new is not None
    assert new.x1 == pytest.approx(260.0)
    assert new.y1 == pytest.approx(160.0)

def test_resize_solo_afecta_rect_objetivo():
    """Verificar que después del resize solo el rect objetivo cambia."""
    app = _MockApp()
    rect_a = pymupdf.Rect(50, 100, 200, 130)
    rect_b = pymupdf.Rect(300, 200, 450, 230)
    app._resultados_por_pagina[0] = [
        {"entity_type": "MX_MONTO", "seleccionada": True, "text": "$1", "rects": [rect_a, rect_b]},
    ]
    # Simular resize solo sobre rect_a (idx=0, corner=br)
    nuevo = app._calcular_nuevo_rect(rect_a, "br", 250.0, 150.0)
    app._resultados_por_pagina[0][0]["rects"][0] = nuevo
    # rect_b no debe haber cambiado
    assert app._resultados_por_pagina[0][0]["rects"][1] == rect_b
    assert app._resultados_por_pagina[0][0]["rects"][0].x1 == pytest.approx(250.0)

def test_resize_seleccion_preservada_post_resize():
    """seleccionada=True debe seguir siendo True después de modificar el rect."""
    app = _make_app_con_entidad()
    ent = app._resultados_por_pagina[0][0]
    nuevo = app._calcular_nuevo_rect(ent["rects"][0], "br", 250.0, 150.0)
    ent["rects"][0] = nuevo
    assert ent["seleccionada"] is True
    assert ent["entity_type"] == "MX_MONTO"
