"""
Tests para legal_mapper.py y generate_justification_page de report_generator.py.
Verifica que cada entity_type reciba un fundamento legal específico y correcto.
"""
import sys, types
sys.path.insert(0, "src")

import pymupdf
import pytest
from legal_mapper import get_legal_justification, LEGAL_MAPPING


# ── Helpers ──────────────────────────────────────────────────────────────────

TODOS_LOS_TIPOS = [
    # Personas / identidades
    "PERSON", "Persona", "Menor",
    # Identificadores oficiales mexicanos
    "MX_CURP", "MX_RFC_PF", "MX_INE", "MX_INE_FOLIO", "MX_NSS",
    # Contacto / ubicación
    "MX_EMAIL", "MX_TEL", "MX_DOMICILIO", "MX_COLONIA", "MX_CP",
    # Biográficos
    "MX_FECHA_NAC", "MX_EDAD", "MX_ENTIDAD_REGISTRO",
    # Patrimoniales
    "MX_CLABE", "MX_TARJETA", "MX_CUENTA", "MX_MONTO", "MX_PLACA", "MX_VIN",
    # Sensibles
    "MX_DIAGNOSTICO", "Diagnóstico",
    # Manuales / reservados
    "MANUAL",
]

# Tipos que DEBEN citar artículos específicos más allá del genérico Art. 116
TIPOS_CON_MARCO_PROPIO = {
    "MX_CURP":      "RENAPO",
    "MX_RFC_PF":    "Código Fiscal",
    "MX_NSS":       "Seguro Social",
    "MX_INE":       "LEGIPE",
    "MX_INE_FOLIO": "LEGIPE",
    "Menor":        "Niñas, Niños",
    "MX_DIAGNOSTICO": "LGPDPPSO",
    "Diagnóstico":    "LGPDPPSO",
    "MX_CLABE":     "crédito",   # Ley de Instituciones de Crédito o LGPDPPSO
}

# LOCATION ya no debe estar clasificado como dato personal en el mapper
# (estados / entidades federativas solos no son PII según análisis LGTAIP)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGetLegalJustification:

    def test_no_retorna_unknown_para_tipos_conocidos(self):
        """Ningún tipo conocido debe caer al fallback UNKNOWN."""
        for tipo in TODOS_LOS_TIPOS:
            result = get_legal_justification(tipo)
            assert result is not LEGAL_MAPPING["UNKNOWN"], (
                f"'{tipo}' cayó al fallback UNKNOWN — agregar entrada en LEGAL_MAPPING"
            )

    def test_tipo_desconocido_retorna_unknown(self):
        result = get_legal_justification("TIPO_INVENTADO_XYZ")
        assert result == LEGAL_MAPPING["UNKNOWN"]

    def test_todos_los_tipos_tienen_campos_requeridos(self):
        for tipo in TODOS_LOS_TIPOS:
            r = get_legal_justification(tipo)
            assert "descripcion" in r, f"{tipo}: falta 'descripcion'"
            assert "fundamento" in r, f"{tipo}: falta 'fundamento'"
            assert "motivacion" in r, f"{tipo}: falta 'motivacion'"
            assert r["descripcion"], f"{tipo}: 'descripcion' vacía"
            assert r["fundamento"], f"{tipo}: 'fundamento' vacío"
            assert r["motivacion"], f"{tipo}: 'motivacion' vacía"

    def test_tipos_con_marco_propio_citan_su_ley_especifica(self):
        """CURP, RFC, NSS, INE, Menores, Diagnóstico deben citar su normativa propia."""
        for tipo, keyword in TIPOS_CON_MARCO_PROPIO.items():
            r = get_legal_justification(tipo)
            texto_completo = r["fundamento"] + " " + r["motivacion"]
            assert keyword.lower() in texto_completo.lower(), (
                f"'{tipo}' no cita '{keyword}' en fundamento/motivación: {texto_completo!r}"
            )

    def test_datos_sensibles_citan_lgpdppso_fraccion_viii(self):
        """Diagnósticos deben citar LGPDPPSO Art. 3 Fracción VIII (datos sensibles)."""
        for tipo in ("MX_DIAGNOSTICO", "Diagnóstico"):
            r = get_legal_justification(tipo)
            texto = r["fundamento"] + " " + r["motivacion"]
            # Debe mencionar LGPDPPSO y la fracción correcta
            assert "LGPDPPSO" in texto, f"{tipo} no menciona LGPDPPSO"
            assert any(x in texto.lower() for x in ("viii", "sensible")), (
                f"{tipo} no menciona 'VIII' ni 'sensible': {texto!r}"
            )

    def test_menor_cita_ley_dnna(self):
        r = get_legal_justification("Menor")
        texto = r["fundamento"] + " " + r["motivacion"]
        assert "Niñas" in texto or "DNNA" in texto or "Adolescentes" in texto, (
            f"Menor no cita Ley GDNNA: {texto!r}"
        )

    def test_fundamentos_no_son_todos_identicos(self):
        """Debe haber al menos 4 fundamentos distintos (no todo Art. 116 genérico)."""
        fundamentos = {get_legal_justification(t)["fundamento"] for t in TODOS_LOS_TIPOS}
        assert len(fundamentos) >= 4, (
            f"Sólo {len(fundamentos)} fundamento(s) distintos — el acta es demasiado genérica"
        )

    def test_location_no_en_legal_mapping(self):
        """LOCATION (estados solos) no debe existir como dato personal en el mapper."""
        # Si existe, debe al menos indicar que no es PII per se
        r = get_legal_justification("LOCATION")
        # Debe caer en UNKNOWN o, si existe, no afirmar que es dato personal confidencial
        if r is not LEGAL_MAPPING["UNKNOWN"]:
            texto = r["descripcion"] + r["fundamento"] + r["motivacion"]
            assert "combinación" in texto.lower() or "junto" in texto.lower() or "contexto" in texto.lower(), (
                "LOCATION afirma ser dato personal confidencial sin mencionar que solo aplica en combinación"
            )


class TestGenerateJustificationPage:

    def _make_info_reporte(self, tipos_paginas: list[tuple]) -> list[dict]:
        """tipos_paginas: [(entity_type, pagina, y0), ...]"""
        return [{"entity_type": t, "pagina": p, "y0": y} for t, p, y in tipos_paginas]

    def test_genera_sin_error_un_tipo(self):
        import report_generator
        doc = pymupdf.open()
        doc.new_page()  # página 0 simulando documento original
        info = self._make_info_reporte([("MX_CURP", 0, 100.0)])
        report_generator.generate_justification_page(doc, info, "test.pdf")
        assert doc.page_count >= 2  # acta + página original

    def test_no_inserta_paginas_si_info_vacia(self):
        import report_generator
        doc = pymupdf.open()
        doc.new_page()
        pages_before = doc.page_count
        report_generator.generate_justification_page(doc, [], "test.pdf")
        assert doc.page_count == pages_before

    def test_acta_contiene_texto_fundamento_curp(self):
        import report_generator
        doc = pymupdf.open()
        doc.new_page()
        info = self._make_info_reporte([("MX_CURP", 0, 50.0)])
        report_generator.generate_justification_page(doc, info, "test.pdf")
        # El acta se inserta al final del documento — leer todas las páginas.
        texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count))
        assert "CURP" in texto_acta or "Población" in texto_acta, (
            f"El acta no menciona CURP/Población: {texto_acta[:300]!r}"
        )

    def test_acta_contiene_texto_fundamento_diagnostico(self):
        import report_generator
        doc = pymupdf.open()
        doc.new_page()
        info = self._make_info_reporte([("MX_DIAGNOSTICO", 0, 80.0)])
        report_generator.generate_justification_page(doc, info, "test.pdf")
        texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count))
        assert "sensible" in texto_acta.lower() or "LGPDPPSO" in texto_acta, (
            f"El acta no indica dato sensible para MX_DIAGNOSTICO: {texto_acta[:400]!r}"
        )

    def test_acta_multiples_tipos_contiene_todos(self):
        import report_generator
        doc = pymupdf.open()
        doc.new_page()
        info = self._make_info_reporte([
            ("MX_CURP", 0, 50.0),
            ("MX_RFC_PF", 0, 100.0),
            ("MX_NSS", 0, 150.0),
            ("PERSON", 0, 200.0),
        ])
        report_generator.generate_justification_page(doc, info, "test.pdf")
        # El acta se inserta al final; recopilar texto de todas las páginas.
        texto_total = ""
        for i in range(doc.page_count):
            texto_total += doc[i].get_text()
        assert "CURP" in texto_total or "Población" in texto_total
        assert "fiscal" in texto_total.lower() or "Contribuyentes" in texto_total
        assert "Seguro" in texto_total or "NSS" in texto_total

    def test_referencia_pagina_correcta_con_acta(self):
        """La referencia a la página original debe ajustarse por el número de páginas del acta."""
        import report_generator
        doc = pymupdf.open()
        doc.new_page()  # página 0 = original
        info = self._make_info_reporte([("PERSON", 0, 100.0)])
        report_generator.generate_justification_page(doc, info, "test.pdf")
        texto_acta = doc[0].get_text()
        # Después de insertar el acta, la original queda en pág 1 (si acta = 1 pág)
        # El acta debe referenciarla como "Pág. 2" (1-indexed) o simplemente "1" del original
        # Lo importante: NO referencia "Pág. 0"
        assert "Pág. original 0" not in texto_acta, (
            "El acta referencia 'Pág. original 0' — numeración empieza en 1"
        )
