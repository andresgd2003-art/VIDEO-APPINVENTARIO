import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from validators import ine_valido

def test_ine_valido_exito():
    assert ine_valido("GALDDA92030501M123") == True
    assert ine_valido("GAZZZA00022909HXYZ") == True
