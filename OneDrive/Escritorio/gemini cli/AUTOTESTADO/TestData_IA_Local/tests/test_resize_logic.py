"""
test_resize_logic.py — Pruebas UNITARIAS puras para la lógica de resize.
No requiere Tkinter ni ninguna ventana. Prueba solo matemáticas y estructuras.
"""
import sys
import math
import pytest
import pymupdf  # PyMuPDF

# ---------------------------------------------------------------------------
# Lógica extraída (mirrors de lo que se implementará en ui_validator.py)
# Estas funciones deben poder importarse INDEPENDIENTEMENTE de Tkinter.
# ---------------------------------------------------------------------------

TOL_PX = 10  # píxeles de tolerancia para detectar esquina (a zoom 1.25)

def _esquina_rect_en_canvas(rect: pymupdf.Rect, zoom: float):
    """Devuelve las 4 esquinas del rect en coordenadas canvas."""
    return {
        "tl": (rect.x0 * zoom, rect.y0 * zoom),
        "tr": (rect.x1 * zoom, rect.y0 * zoom),
        "bl": (rect.x0 * zoom, rect.y1 * zoom),
        "br": (rect.x1 * zoom, rect.y1 * zoom),
    }

def _detectar_esquina(cx: float, cy: float, rect: pymupdf.Rect, zoom: float, tol: float = TOL_PX):
    """Devuelve el nombre de la esquina ('tl','tr','bl','br') o None."""
    esquinas = _esquina_rect_en_canvas(rect, zoom)
    for nombre, (ex, ey) in esquinas.items():
        if math.hypot(cx - ex, cy - ey) <= tol:
            return nombre
    return None

def _calcular_nuevo_rect(orig: pymupdf.Rect, corner: str, xp: float, yp: float) -> pymupdf.Rect | None:
    """Calcula el nuevo Rect al arrastrar una esquina. Retorna None si es inválido (<5x5)."""
    if corner == "tl":
        new = pymupdf.Rect(xp, yp, orig.x1, orig.y1)
    elif corner == "tr":
        new = pymupdf.Rect(orig.x0, yp, xp, orig.y1)
    elif corner == "bl":
        new = pymupdf.Rect(xp, orig.y0, orig.x1, yp)
    elif corner == "br":
        new = pymupdf.Rect(orig.x0, orig.y0, xp, yp)
    else:
        return None
    # Validar mínimo 5×5
    if abs(new.x1 - new.x0) < 5 or abs(new.y1 - new.y0) < 5:
        return None
    # Normalizar (asegurar x0<x1, y0<y1)
    return pymupdf.Rect(
        min(new.x0, new.x1), min(new.y0, new.y1),
        max(new.x0, new.x1), max(new.y0, new.y1)
    )


# ===========================================================================
# TESTS
# ===========================================================================

ZOOM = 1.25
RECT = pymupdf.Rect(50, 100, 200, 130)  # rect base de prueba


# --- Detección de esquinas ---

def test_detectar_esquina_tl():
    """Punto exacto en esquina tl → 'tl'."""
    cx, cy = RECT.x0 * ZOOM, RECT.y0 * ZOOM
    assert _detectar_esquina(cx, cy, RECT, ZOOM) == "tl"

def test_detectar_esquina_tr():
    """Punto exacto en esquina tr → 'tr'."""
    cx, cy = RECT.x1 * ZOOM, RECT.y0 * ZOOM
    assert _detectar_esquina(cx, cy, RECT, ZOOM) == "tr"

def test_detectar_esquina_bl():
    """Punto exacto en esquina bl → 'bl'."""
    cx, cy = RECT.x0 * ZOOM, RECT.y1 * ZOOM
    assert _detectar_esquina(cx, cy, RECT, ZOOM) == "bl"

def test_detectar_esquina_br():
    """Punto exacto en esquina br → 'br'."""
    cx, cy = RECT.x1 * ZOOM, RECT.y1 * ZOOM
    assert _detectar_esquina(cx, cy, RECT, ZOOM) == "br"

def test_detectar_esquina_dentro_tolerancia():
    """Punto a 8px de esquina br (dentro de TOL=10) → 'br'."""
    cx = RECT.x1 * ZOOM - 6
    cy = RECT.y1 * ZOOM + 6
    assert _detectar_esquina(cx, cy, RECT, ZOOM, tol=10) == "br"

def test_no_esquina_interior():
    """Centro del rect → None."""
    cx = (RECT.x0 + RECT.x1) / 2 * ZOOM
    cy = (RECT.y0 + RECT.y1) / 2 * ZOOM
    assert _detectar_esquina(cx, cy, RECT, ZOOM) is None

def test_no_esquina_exterior_lejos():
    """Punto a 50px fuera → None."""
    cx = RECT.x1 * ZOOM + 50
    cy = RECT.y1 * ZOOM + 50
    assert _detectar_esquina(cx, cy, RECT, ZOOM) is None


# --- Cálculo de nuevo rect ---

def test_resize_br_ampliar():
    """Drag 'br' hacia abajo-derecha → rect más grande."""
    new = _calcular_nuevo_rect(RECT, "br", 250.0, 160.0)
    assert new is not None
    assert new.x1 == pytest.approx(250.0)
    assert new.y1 == pytest.approx(160.0)
    assert new.x0 == RECT.x0
    assert new.y0 == RECT.y0

def test_resize_tl_reducir():
    """Drag 'tl' hacia adentro → rect más pequeño."""
    new = _calcular_nuevo_rect(RECT, "tl", 80.0, 110.0)
    assert new is not None
    assert new.x0 == pytest.approx(80.0)
    assert new.y0 == pytest.approx(110.0)
    assert new.x1 == RECT.x1
    assert new.y1 == RECT.y1

def test_resize_tr_esquina():
    """Drag 'tr' → solo cambia x1 e y0."""
    new = _calcular_nuevo_rect(RECT, "tr", 220.0, 95.0)
    assert new is not None
    assert new.x1 == pytest.approx(220.0)
    assert new.y0 == pytest.approx(95.0)

def test_resize_bl_esquina():
    """Drag 'bl' → solo cambia x0 e y1."""
    new = _calcular_nuevo_rect(RECT, "bl", 40.0, 140.0)
    assert new is not None
    assert new.x0 == pytest.approx(40.0)
    assert new.y1 == pytest.approx(140.0)

def test_resize_minimo_invalido_rechazado():
    """Drag 'br' a posición que crea rect <5×5 → None."""
    # Drag br a casi la misma posición que tl
    new = _calcular_nuevo_rect(RECT, "br", RECT.x0 + 2, RECT.y0 + 2)
    assert new is None

def test_resize_preserva_datos_entidad():
    """El dict de entidad conserva entity_type y seleccionada tras simular resize."""
    entidad = {
        "entity_type": "MX_MONTO",
        "seleccionada": True,
        "text": "$72,633.55",
        "rects": [pymupdf.Rect(50, 100, 200, 130)],
    }
    # Simular resize: reemplazar el rect 0
    nuevo_rect = _calcular_nuevo_rect(entidad["rects"][0], "br", 250.0, 150.0)
    entidad["rects"][0] = nuevo_rect
    # La entidad no debe haber perdido sus metadatos
    assert entidad["entity_type"] == "MX_MONTO"
    assert entidad["seleccionada"] is True
    assert entidad["text"] == "$72,633.55"
    assert entidad["rects"][0].x1 == pytest.approx(250.0)

def test_resize_rect_manual_preserva_metadata():
    """Un rect manual conserva pagina, entity_type y seleccionado tras resize."""
    rm = {
        "rect": pymupdf.Rect(30, 50, 180, 80),
        "pagina": 2,
        "seleccionado": True,
        "entity_type": "Persona",
    }
    nuevo = _calcular_nuevo_rect(rm["rect"], "tl", 10.0, 30.0)
    rm["rect"] = nuevo
    assert rm["pagina"] == 2
    assert rm["seleccionado"] is True
    assert rm["entity_type"] == "Persona"
    assert rm["rect"].x0 == pytest.approx(10.0)
