import pytest
import pymupdf
import sys
import os
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from sanitizer import _PADDING_RIGHT

def test_padding_invade_signos_de_puntuacion():
    """
    Test para demostrar cómo un _PADDING_RIGHT muy grande invade signos
    de puntuación pegados a una palabra (e.g. comas o puntos).
    """
    # Supongamos una letra 'A' que termina en x=40.0 pt
    # y una coma ',' que empieza en x=40.5 pt (gap de 0.5 pt).
    A_x1 = 40.0
    coma_x0 = 40.5
    
    # El mapper determina que la entidad a redactar llega solo hasta la 'A'.
    # El sanitizer aplica un _PADDING_RIGHT.
    redacted_x1 = A_x1 + _PADDING_RIGHT
    
    # Verificamos si el recuadro invadió la coma
    invadido = redacted_x1 >= coma_x0
    
    # Queremos que la redacción NO invada el signo
    assert not invadido, f"El recuadro redactado ({redacted_x1}pt) roza o invade el signo de puntuación en {coma_x0}pt!"
