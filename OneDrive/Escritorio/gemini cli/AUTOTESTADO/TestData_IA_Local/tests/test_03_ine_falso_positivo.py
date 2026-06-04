import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from validators import ine_valido

def test_ine_valido_longitud():
    # Longitud incorrecta
    assert ine_valido("GALDDA92030501M12") == False # 17 chars
    assert ine_valido("GALDDA92030501M1234") == False # 19 chars
    assert ine_valido("") == False
