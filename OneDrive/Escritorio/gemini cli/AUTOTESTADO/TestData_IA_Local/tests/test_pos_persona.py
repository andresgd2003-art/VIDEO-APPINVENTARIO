"""
Tests del filtro POS para PERSON/Persona (paso 4).

Verifica que spans detectados como PERSON pero que en realidad son frases
narrativas, sustantivos comunes, o roles legales son descartados gracias
al análisis POS de spaCy.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from detector import build_analyzer, analyze_page


@pytest.fixture(scope="module")
def analyzer():
    return build_analyzer()


def _personas_detectadas(analyzer, texto):
    """Devuelve la lista de fragmentos de tipo nombre detectados.

    Incluye MX_NOMBRE además de PERSON/Persona: un nombre tras una etiqueta legal
    ('IMPUTADO:', 'Víctima:', 'Titular:') se captura como MX_NOMBRE (mayor prioridad),
    que igualmente garantiza el testado del dato personal.
    """
    resultados = analyze_page(analyzer, texto)
    return [
        texto[r.start:r.end]
        for r in resultados
        if r.entity_type in ("PERSON", "Persona", "MX_NOMBRE")
    ]


# ── True positives: nombres reales SE detectan ────────────────────────────────

class TestNombresReales:
    def test_nombre_simple(self, analyzer):
        texto = "El acta fue firmada por Juan Pérez García en la oficina."
        nombres = _personas_detectadas(analyzer, texto)
        assert any("Juan" in n or "Pérez" in n for n in nombres), \
            f"Esperaba 'Juan Pérez García'. Detectado: {nombres}"

    def test_nombre_en_mayusculas(self, analyzer):
        texto = "IMPUTADO: MIGUEL ANGEL CORTES RIVERA"
        nombres = _personas_detectadas(analyzer, texto)
        assert any("MIGUEL" in n or "CORTES" in n for n in nombres), \
            f"Esperaba nombre en mayúsculas. Detectado: {nombres}"


# ── True negatives: frases comunes NO se detectan ─────────────────────────────

class TestNoDetectaFrasesComunes:
    def test_no_detecta_oracion_comun(self, analyzer):
        """Una frase narrativa sin nombres no debe activar PERSON."""
        texto = "El tribunal considera que el agravio fue debidamente acreditado."
        nombres = _personas_detectadas(analyzer, texto)
        # No debería detectarse "el tribunal" o "el agravio" como PERSON
        sospechosos = [n for n in nombres if n.lower().strip() in (
            "el tribunal", "tribunal", "agravio", "el agravio", "considera"
        )]
        assert not sospechosos, f"Detectó frases comunes como PERSON: {sospechosos}"

    def test_no_detecta_sustantivos_comunes(self, analyzer):
        """Sustantivos comunes en mayúsculas (encabezados) no son nombres."""
        texto = "RESULTANDO PRIMERO. CONSIDERANDO SEGUNDO. SENTENCIA DEFINITIVA."
        nombres = _personas_detectadas(analyzer, texto)
        sospechosos = [n for n in nombres if n.upper() in (
            "RESULTANDO PRIMERO", "CONSIDERANDO SEGUNDO", "SENTENCIA DEFINITIVA",
            "RESULTANDO", "CONSIDERANDO", "SENTENCIA"
        )]
        assert not sospechosos, f"Detectó encabezados como PERSON: {sospechosos}"

    def test_no_detecta_ocupaciones(self, analyzer):
        """Cadenas que describen ocupación o rol genérico."""
        texto = "Técnico Mecánico Automotriz con experiencia comprobada."
        nombres = _personas_detectadas(analyzer, texto)
        sospechosos = [n for n in nombres if "técnico" in n.lower() or "mecánico" in n.lower()]
        assert not sospechosos, f"Detectó ocupación como PERSON: {sospechosos}"
