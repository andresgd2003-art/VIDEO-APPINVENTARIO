# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from legal_mapper import get_legal_justification


def test_nuevoleon_personal_curp():
    res = get_legal_justification("MX_CURP", estado="nuevo_leon")
    fund = res["fundamento"]
    # Conserva el fundamento federal
    assert "LGTAIP" in fund
    assert "LGPDPPSO" in fund
    # Capa estatal de Nuevo León con la fracción X (dato personal)
    assert "Nuevo León" in fund
    assert "Art. 3, fracción X" in fund
    assert "fracción XI" not in fund


def test_nuevoleon_sensible_diagnostico():
    res = get_legal_justification("MX_DIAGNOSTICO", estado="nuevo_leon")
    fund = res["fundamento"]
    # Conserva el fundamento federal
    assert "LGPDPPSO" in fund
    # Capa estatal de Nuevo León con la fracción XI (dato sensible) y consentimiento Art. 22
    assert "Nuevo León" in fund
    assert "Art. 3, fracción XI" in fund
    assert "consentimiento expreso y por escrito" in fund
    assert "Art. 22" in fund
