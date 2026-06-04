import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from validators import ine_valido

def test_ine_valido_falla():
    assert ine_valido("GADA92023001M123") == False
    assert ine_valido("GADA92043101M123") == False
    assert ine_valido("GADA92030599M123") == False
