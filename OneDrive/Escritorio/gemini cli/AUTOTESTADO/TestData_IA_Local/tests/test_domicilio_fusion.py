"""Tests para fusión multi-pieza de domicilio (paso 3)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pymupdf
from mapper import _merge_domicilio_multipieza


def _ent(tipo, x0, y0, x1, y1, texto=""):
    return {
        "entity_type": tipo,
        "score":       0.85,
        "text":        texto,
        "rects":       [pymupdf.Rect(x0, y0, x1, y1)],
    }


def test_no_fusiona_un_solo_domicilio():
    """Una sola entidad de domicilio se mantiene como está."""
    ents = [_ent("MX_DOMICILIO", 50, 100, 200, 110, "Calle X 123")]
    resultado = _merge_domicilio_multipieza(ents)
    assert len(resultado) == 1
    assert resultado[0]["entity_type"] == "MX_DOMICILIO"


def test_fusiona_lineas_contiguas_misma_columna():
    """Vialidad + Colonia + CP en 3 líneas contiguas → 1 sola entidad con bbox grande."""
    ents = [
        _ent("MX_DOMICILIO", 50, 100, 250, 110, "Calle AMANECER 348"),
        _ent("MX_COLONIA",   50, 120, 220, 130, "BRISAS DIAMANTE"),
        _ent("MX_CP",        50, 140, 100, 150, "34235"),
    ]
    resultado = _merge_domicilio_multipieza(ents)
    assert len(resultado) == 1, f"Esperaba 1 entidad fusionada, hay {len(resultado)}"
    r = resultado[0]["rects"][0]
    # El bbox debe cubrir desde la primera línea hasta la última
    assert r.x0 <= 50 and r.x1 >= 250
    assert r.y0 <= 100 and r.y1 >= 150
    assert resultado[0]["entity_type"] == "MX_DOMICILIO"


def test_no_fusiona_si_distintas_columnas():
    """Dos domicilios en columnas separadas (sin solape horizontal) no se fusionan."""
    ents = [
        _ent("MX_DOMICILIO", 50, 100, 200, 110, "Dom 1"),
        _ent("MX_DOMICILIO", 400, 100, 550, 110, "Dom 2"),  # otra columna
    ]
    # Tampoco están en la misma línea (no contiguos verticalmente)
    ents[1]["rects"] = [pymupdf.Rect(400, 200, 550, 210)]
    resultado = _merge_domicilio_multipieza(ents)
    assert len(resultado) == 2


def test_no_fusiona_si_gap_vertical_grande():
    """Dos piezas separadas por más de _TOLERANCIA_DOMI_Y puntos no se fusionan."""
    ents = [
        _ent("MX_DOMICILIO", 50, 100, 200, 110),
        _ent("MX_COLONIA",   50, 250, 200, 260),  # gap de 140pt
    ]
    resultado = _merge_domicilio_multipieza(ents)
    assert len(resultado) == 2


def test_no_afecta_entidades_no_domicilio():
    """Entidades de otros tipos se preservan tal cual."""
    ents = [
        _ent("PERSON",       50, 50, 200, 60, "Juan Pérez"),
        _ent("MX_DOMICILIO", 50, 100, 250, 110, "Calle X"),
        _ent("MX_COLONIA",   50, 120, 220, 130, "Col Y"),
        _ent("MX_CURP",      50, 200, 250, 210),
    ]
    resultado = _merge_domicilio_multipieza(ents)
    # PERSON y CURP intactas; DOMICILIO+COLONIA fusionadas en 1
    tipos = [r["entity_type"] for r in resultado]
    assert tipos.count("PERSON") == 1
    assert tipos.count("MX_CURP") == 1
    assert tipos.count("MX_DOMICILIO") == 1  # la fusionada
    assert "MX_COLONIA" not in tipos        # fue absorbida


def test_bbox_envuelve_huecos():
    """El bbox resultante cubre el rango horizontal completo cuando hay solape."""
    ents = [
        _ent("MX_DOMICILIO",  50, 100, 250, 110, "Calle larga"),  # x0=50, x1=250
        _ent("MX_COLONIA",   200, 120, 320, 130, "Colonia"),       # x0=200, x1=320 (solapa 200..250)
    ]
    resultado = _merge_domicilio_multipieza(ents)
    assert len(resultado) == 1
    r = resultado[0]["rects"][0]
    # El bbox debe envolver ambas piezas, incluyendo el hueco vertical entre ellas
    assert r.x0 == 50 and r.x1 == 320
    assert r.y0 == 100 and r.y1 == 130


def test_no_fusiona_columnas_disjuntas():
    """Cajas en columnas verticalmente cercanas pero horizontalmente disjuntas no se fusionan."""
    ents = [
        _ent("MX_DOMICILIO", 50, 100, 100, 110, "Pieza izq"),    # columna izquierda
        _ent("MX_COLONIA",   400, 120, 500, 130, "Pieza der"),   # columna derecha (sin solape x)
    ]
    resultado = _merge_domicilio_multipieza(ents)
    assert len(resultado) == 2, "No debe fusionar columnas distintas"


def test_texto_concatenado():
    """El texto del resultado fusionado contiene las piezas separadas por '/'."""
    ents = [
        _ent("MX_DOMICILIO", 50, 100, 200, 110, "Calle X"),
        _ent("MX_COLONIA",   50, 120, 200, 130, "Col Y"),
        _ent("MX_CP",        50, 140, 100, 150, "12345"),
    ]
    resultado = _merge_domicilio_multipieza(ents)
    texto = resultado[0]["text"]
    assert "Calle X" in texto
    assert "Col Y" in texto
    assert "12345" in texto
