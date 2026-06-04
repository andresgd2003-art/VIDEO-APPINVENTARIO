# -*- coding: utf-8 -*-
"""
Criterio de aceptación principal: switchear la jurisdicción (Durango <-> Nuevo León)
debe cambiar SOLO el fundamento legal del acta (capa estatal), conservando el
fundamento federal y SIN alterar la estructura/maqueta de la tabla.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pymupdf
from legal_mapper import get_legal_justification


def test_mismo_tipo_distinto_fundamento_por_estado():
    dgo = get_legal_justification("MX_CURP", estado="durango")
    nl = get_legal_justification("MX_CURP", estado="nuevo_leon")

    # La descripción (estructura) es idéntica entre estados
    assert dgo["descripcion"] == nl["descripcion"]

    # Capa estatal correcta y distinta
    assert "Estado de Durango" in dgo["fundamento"]
    assert "Estado de Nuevo León" in nl["fundamento"]
    assert dgo["fundamento"] != nl["fundamento"]

    # Numeración corrida de NL para dato personal: fracción X (Durango: IX)
    assert "fracción IX" in dgo["fundamento"]
    assert "fracción X" in nl["fundamento"]

    # Se conserva el marco federal en ambos
    for r in (dgo, nl):
        assert ("LGTAIP" in r["fundamento"]) or ("LGPDPPSO" in r["fundamento"])


def test_sensible_cita_fraccion_estatal_correcta():
    dgo = get_legal_justification("MX_DIAGNOSTICO", estado="durango")
    nl = get_legal_justification("MX_DIAGNOSTICO", estado="nuevo_leon")
    # Durango sensible -> frac. X ; Nuevo León sensible -> frac. XI
    assert "fracción X" in dgo["fundamento"]
    assert "fracción XI" in nl["fundamento"]


def _info(tipos):
    return [{"entity_type": t, "pagina": 0, "y0": y} for t, y in tipos]


def _texto_acta(estado):
    import report_generator
    doc = pymupdf.open()
    doc.new_page()
    report_generator.generate_justification_page(
        doc, _info([("MX_CURP", 50.0), ("MX_DIAGNOSTICO", 120.0)]), "test.pdf", estado=estado
    )
    texto = "".join(doc[i].get_text() for i in range(doc.page_count))
    doc.close()
    return texto


def test_acta_refleja_estado_seleccionado():
    t_dgo = _texto_acta("durango")
    t_nl = _texto_acta("nuevo_leon")

    # El acta de cada estado nombra su ley estatal y no la del otro
    assert "Durango" in t_dgo and "Nuevo León" not in t_dgo
    assert "Nuevo León" in t_nl and "Durango" not in t_nl

    # La estructura del acta se conserva (mismo encabezado)
    for t in (t_dgo, t_nl):
        assert "Acta del Comité de Transparencia" in t
        assert "Marco legal aplicable" in t
