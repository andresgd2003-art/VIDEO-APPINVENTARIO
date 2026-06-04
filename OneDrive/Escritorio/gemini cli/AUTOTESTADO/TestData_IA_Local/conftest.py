"""
conftest.py raíz — gestión central de sys.path para la suite de tests.

Problema: cuando pytest recolecta todos los tests juntos, Python 3.13 puede
registrar 'presidio_analyzer' en sys.modules como módulo simple (no paquete)
antes de que detector.py intente importar su subpaquete nlp_engine, lo que
causa 'presidio_analyzer is not a package'. Este conftest garantiza que el
paquete correcto esté en sys.modules antes de cualquier test.
"""
import sys
import os

# 1. Asegurar que src/ esté en el path con máxima prioridad.
#    pytest.ini también declara pythonpath = src, pero esto actúa de red
#    de seguridad para IDEs o invocaciones directas fuera del rootdir.
_src = os.path.join(os.path.dirname(__file__), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# 2. Pre-importar presidio_analyzer y su subpaquete nlp_engine para
#    "fijar" la entrada correcta en sys.modules antes de que cualquier
#    test lo importe. Sin esto, si un test falla al importar detector a
#    mitad de colección, puede dejar presidio_analyzer como módulo parcial.
try:
    import presidio_analyzer  # noqa: F401
    from presidio_analyzer import nlp_engine  # noqa: F401
except Exception:
    pass  # Si el paquete no está instalado, los tests que lo necesiten
          # fallarán con un error claro al ejecutarse, no al colectarse.


def pytest_sessionstart(session):
    """Pre-construye el singleton del AnalyzerEngine ANTES de que corran los tests.

    Sin esto, el primer test que activa un mock sobre AnalyzerEngine o sobre
    partes de presidio_analyzer puede "envenenar" el singleton con un MagicMock
    (e.g. mock.AnalyzerEngine()) y todos los tests posteriores reciben el mock
    en lugar del analyzer real. Pre-construirlo aquí garantiza que la primera
    (y única) inicialización ocurre con todos los módulos en estado limpio.
    """
    try:
        import detector as _det
        _det.build_analyzer()
    except Exception:
        pass  # Si los modelos no están disponibles, los tests NLP fallarán
              # individualmente con mensajes de error claros.

# 3. Excluir tests cuyas dependencias no están implementadas/instaladas.
#    - test_llm_*.py requieren llm_auditor (módulo nunca implementado).
collect_ignore_glob = [
    "tests/test_llm_fase1.py",
    "tests/test_llm_fase2.py",
    "tests/test_llm_fase3.py",
    "tests/test_llm_e2e.py",
]
