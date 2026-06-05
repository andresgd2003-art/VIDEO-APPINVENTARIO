# -*- coding: utf-8 -*-
"""
GUARDA ANTI-REGRESIÓN a nivel documento sobre PDFs reales.

Lógica de prevención de regresiones (dos invariantes por documento):
  1. MUST-DETECT  → datos que SIEMPRE deben testarse (guard anti-bajo-detección).
                    Si una mejora futura deja de detectar uno, este test falla.
  2. MUST-NOT-DETECT → texto que NUNCA debe testarse: autoridades de gobierno,
                    servidores públicos y trampas de instrucción genérica
                    (guard anti-falso-positivo / sobre-testado).

A diferencia de un snapshot exacto (frágil), estas invariantes semánticas
sobreviven a refactors: solo fallan ante una regresión real de comportamiento.

Los PDFs viven fuera del repo (carpeta personal del usuario); si no están
presentes, el test se omite (skip) en vez de fallar.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

_DOCS_DIR = r"C:\Users\user\OneDrive\Escritorio\mis docs"
BRUTAL = os.path.join(_DOCS_DIR, "PRUEBA_BRUTAL_ANONIMA.pdf")
INE    = os.path.join(_DOCS_DIR, "IDENTIFICACION OFICIAL.pdf")
CURP   = os.path.join(_DOCS_DIR, "curp.pdf")


@pytest.fixture(scope="module")
def analyzer():
    """Analyzer REAL e inmune a contaminación de otros tests.

    Varios tests de UI hacen `sys.modules["easyocr"] = MagicMock()` a nivel de
    módulo, lo que envenena `easyocr` para TODA la sesión: el OCR del INE recibe
    un mock y devuelve vacío. Para que esta guardia mida el comportamiento REAL,
    se restaura el `easyocr` real en sys.modules, se re-vincula en ocr_engine y
    se resetean los singletons del reader y del analyzer.
    """
    import sys
    # 1. Restaurar el módulo easyocr real si quedó mockeado
    mod = sys.modules.get("easyocr")
    if mod is not None and not hasattr(mod, "__file__"):  # MagicMock no tiene __file__
        del sys.modules["easyocr"]
    try:
        import easyocr as _real_easyocr
        import ocr_pipeline.ocr_engine as _oe
        _oe.easyocr = _real_easyocr           # re-vincular el nombre que usa _get_easyocr_reader
        _oe._easyocr_reader = None            # limpiar reader cacheado (posible mock)
    except Exception:
        pass
    # 2. Reconstruir el analyzer real (por si otro test mockeó el singleton)
    import detector
    for _attr in ("_analyzer_singleton", "_ANALYZER", "_analyzer"):
        if hasattr(detector, _attr):
            setattr(detector, _attr, None)
    return detector.build_analyzer()


def _detectar(analyzer, pdf_path):
    """Devuelve lista de (entity_type, texto) detectados en todo el PDF."""
    import pdf_reader, detector, mapper
    import pymupdf
    doc = pymupdf.open(pdf_path)
    pares = []
    for i in range(doc.page_count):
        page = doc[i]
        idx = pdf_reader.build_spatial_index(pdf_reader.extract_words(page), page)
        texto = " ".join(e["word"] for e in idx)
        dicts = [
            {"entity_type": r.entity_type, "text": texto[r.start:r.end],
             "start": r.start, "end": r.end, "score": r.score}
            for r in detector.analyze_page(analyzer, texto)
        ]
        for e in mapper.map_entities(idx, dicts):
            pares.append((e["entity_type"], e["text"]))
    doc.close()
    return pares


def _contiene(pares, subtexto):
    """True si algún span detectado contiene `subtexto` (case-insensitive)."""
    s = subtexto.lower()
    return any(s in txt.lower() for _, txt in pares)


def _tipo_para(pares, subtexto):
    s = subtexto.lower()
    return [et for et, txt in pares if s in txt.lower()]


# ── Identificadores con CHECKSUM VÁLIDO que SIEMPRE deben detectarse ──────────
_MUST_BRUTAL = [
    "GADA030721HDGLZNA8",       # CURP
    "GADA0307211L8",            # RFC PF
    "CAF900901IB8",             # RFC PM
    "014200012345678900",       # CLABE
    "4111 1111 1111 1111",      # Tarjeta
    "1HGBH41JXMN109186",        # VIN
    "ANDRES GALLEGOS DIAZ",     # Nombre (etiqueta Titular/Imputado)
    "Eva Gallegos Diaz",        # Nombre Title Case tras 'Víctima:'
    "andres.gallegos@gmail.com",
    "GALLEG03072110H001",       # Clave de elector
]

# ── Trampas: autoridades, servidores públicos e instrucciones genéricas ───────
# Estas cadenas NO deben quedar bajo ningún recuadro de testado.
_MUST_NOT_BRUTAL = [
    "Instituto Nacional Electoral",
    "Instituto Nacional de Migracion",
    "Secretaria de Relaciones Exteriores",
    "Roberto Rubio Cantu",       # el Juez (servidor público)
    "Maria Fernandez Torres",    # la Secretaria (servidor público)
    "concepto general",          # 'Universidad como concepto general...' (relleno)
]


@pytest.mark.skipif(not os.path.exists(BRUTAL), reason="PDF brutal no disponible")
class TestDocBrutal:
    @pytest.fixture(scope="class")
    def pares(self, analyzer):
        return _detectar(analyzer, BRUTAL)

    @pytest.mark.parametrize("dato", _MUST_BRUTAL)
    def test_must_detect(self, pares, dato):
        assert _contiene(pares, dato), (
            f"REGRESIÓN (bajo-detección): '{dato}' dejó de detectarse en el doc brutal"
        )

    @pytest.mark.parametrize("trampa", _MUST_NOT_BRUTAL)
    def test_must_not_detect(self, pares, trampa):
        hit = [(et, t) for et, t in pares if trampa.lower() in t.lower()]
        assert not hit, (
            f"REGRESIÓN (falso positivo): '{trampa}' NO debe testarse, pero se detectó: {hit}"
        )


@pytest.mark.skipif(not os.path.exists(CURP), reason="curp.pdf no disponible")
class TestDocCurp:
    @pytest.fixture(scope="class")
    def pares(self, analyzer):
        return _detectar(analyzer, CURP)

    @pytest.mark.parametrize("dato", ["GADA030721HDGLZNA8", "GALLEGOS DIAZ", "DURANGO"])
    def test_must_detect(self, pares, dato):
        assert _contiene(pares, dato), f"REGRESIÓN: '{dato}' dejó de detectarse en curp.pdf"

    def test_servidor_publico_no_testado(self, pares):
        # La firmante (Secretaria de Gobernación) es servidora pública → NO testar
        assert not _contiene(pares, "ROSA ICELA"), (
            "REGRESIÓN: la firmante servidora pública fue testada en curp.pdf"
        )


@pytest.mark.skipif(not os.path.exists(INE), reason="INE no disponible")
class TestDocINE:
    @pytest.fixture(scope="class")
    def pares(self, analyzer):
        return _detectar(analyzer, INE)

    @pytest.mark.parametrize("dato", ["GALLEGOS", "DIAZ", "ANDRES"])
    def test_nombre_detectado(self, pares, dato):
        assert _contiene(pares, dato), (
            f"REGRESIÓN: el nombre INE '{dato}' dejó de detectarse (OCR/credencial)"
        )

    def test_curp_o_clave_detectada(self, pares):
        # El OCR puede variar; al menos CURP o clave de elector deben salir
        assert _contiene(pares, "GADA") or _contiene(pares, "GLDZ") or _contiene(pares, "GALLEG"), (
            "REGRESIÓN: ni CURP ni clave de elector se detectaron en la INE"
        )
