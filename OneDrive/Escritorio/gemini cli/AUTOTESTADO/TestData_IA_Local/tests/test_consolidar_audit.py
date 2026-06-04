import pymupdf
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from mapper import _consolidar_rects_por_linea


def test_x0_minimo_preservado():
    """El x0 del rect consolidado debe ser el mínimo de todos los rects de la línea."""
    rects = [
        pymupdf.Rect(100, 50, 130, 65),  # primera palabra (x0=100 es el mínimo real)
        pymupdf.Rect(135, 50, 180, 65),
        pymupdf.Rect(185, 50, 230, 65),
    ]
    resultado = _consolidar_rects_por_linea(rects)
    assert len(resultado) == 1
    assert resultado[0].x0 == 100.0, f"x0 esperado 100, obtenido {resultado[0].x0}"
    assert resultado[0].x1 == 230.0, f"x1 esperado 230, obtenido {resultado[0].x1}"


def test_orden_no_afecta_x0():
    """Mismo resultado aunque los rects lleguen en orden inverso."""
    rects = [
        pymupdf.Rect(185, 50, 230, 65),
        pymupdf.Rect(135, 50, 180, 65),
        pymupdf.Rect(100, 50, 130, 65),  # x0 mínimo, pero llega al final
    ]
    resultado = _consolidar_rects_por_linea(rects)
    assert resultado[0].x0 == 100.0


def test_tolerancia_boundary():
    """Dos rects con y0 en el límite exacto de tolerancia no se deben fusionar si están en líneas distintas."""
    _TOL = 4.0
    r1 = pymupdf.Rect(10, 0,   100, 15)   # key=0
    r2 = pymupdf.Rect(10, 100, 100, 115)  # key=25 → línea distinta
    resultado = _consolidar_rects_por_linea([r1, r2])
    assert len(resultado) == 2, f"Deben ser 2 líneas, se obtuvieron {len(resultado)}"
