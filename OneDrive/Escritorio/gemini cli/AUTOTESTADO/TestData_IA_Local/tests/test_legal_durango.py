# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from legal_mapper import get_legal_justification


def test_durango_personal():
    res = get_legal_justification("MX_CURP", estado="durango")
    fund = res["fundamento"]
    # Conserva el fundamento federal original
    assert "LGTAIP" in fund or "LGPDPPSO" in fund
    # Añade la capa estatal de Durango con la fracción correcta (personal = frac. IX)
    assert "Estado de Durango" in fund
    assert "fracción IX" in fund


def test_durango_sensible():
    res = get_legal_justification("MX_DIAGNOSTICO", estado="durango")
    fund = res["fundamento"]
    # Conserva el fundamento federal original
    assert "LGTAIP" in fund or "LGPDPPSO" in fund
    # Capa estatal sensible: frac. X, Art. 7 y Art. 15 último párrafo
    assert "Estado de Durango" in fund
    assert "fracción X" in fund
    assert "Art. 7" in fund
    assert "Art. 15" in fund
