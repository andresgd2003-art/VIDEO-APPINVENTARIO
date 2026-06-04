# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from legal_mapper import get_legal_justification

def test_legal_mapper_custom():
    res = get_legal_justification("CUSTOM", custom_label="Matricula", custom_legal="Art 116", custom_motivacion="Motivacion 123")
    assert res["type"] == "Matricula"
    assert res["fundamento"] == "Art 116"
    assert "Motivacion 123" in res["motivacion"]
