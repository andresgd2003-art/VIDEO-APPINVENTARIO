# -*- coding: utf-8 -*-
"""
Test-first de la REORGANIZACIÓN coherente (colores, acta, afiliación, consistencia
de las 4 listas) conforme a la Ley General de Transparencia y la LGPDPPSO vigentes.

Codifica el ESTADO OBJETIVO. Se escribe ANTES de aplicar los cambios (regla del
usuario: test antes de aplicar). Falla hasta que la reorganización esté hecha.
"""
import os, sys, re
import pytest
import pymupdf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ════════════════════════════════════════════════════════════════════════════
# 1. COLORES: agrupación coherente (sin duplicados incoherentes)
# ════════════════════════════════════════════════════════════════════════════
def _colores():
    import ui_validator
    return ui_validator.COLORES_ENTIDAD


class TestColoresAgrupacion:
    def test_lugar_y_fecha_nac_con_persona(self):
        c = _colores()
        assert c["MX_LUGAR_NAC"] == c["PERSON"], "Lugar de nacimiento debe ir con Persona"
        assert c["MX_FECHA_NAC"] == c["PERSON"], "Fecha de nacimiento debe ir con Persona"
        assert c["MX_EDAD"] == c["PERSON"], "Edad debe ir con Persona"
        assert c["MX_NOMBRE"] == c["PERSON"]

    def test_diagnostico_distinto_de_opinion_politica(self):
        c = _colores()
        assert c["MX_DIAGNOSTICO"] != c["MX_OPINION_POLITICA"], \
            "Diagnóstico (salud) y Opinión política NO deben compartir color"

    def test_diagnostico_gliner_igual_a_mx_diagnostico(self):
        c = _colores()
        assert c["Diagnóstico"] == c["MX_DIAGNOSTICO"], \
            "El mismo concepto (diagnóstico) debe tener un solo color"

    def test_firma_qr_misma_categoria(self):
        c = _colores()
        assert c["MX_FIRMA"] == c["MX_QR"], "Firma, QR y códigos de barra (MX_QR) misma categoría visual"

    def test_preferencia_sexual_no_con_identificadores(self):
        c = _colores()
        assert c["MX_PREFERENCIA_SEXUAL"] != c["MX_CURP"], \
            "Preferencia sexual (sensible) no debe agruparse con identificadores (CURP/RFC)"

    def test_religion_no_con_bancarios(self):
        c = _colores()
        assert c["MX_RELIGION"] != c["MX_CLABE"], "Religión (sensible) no debe ir con datos bancarios"

    def test_escolar_no_con_bancarios(self):
        c = _colores()
        assert c["MX_ESCOLAR"] != c["MX_CLABE"], "Dato escolar no debe ir con datos bancarios"

    def test_biometrico_no_con_fecha(self):
        c = _colores()
        assert c["MX_BIOMETRICO"] != c["MX_FECHA_NAC"], "Biométrico (sensible) no debe ir con fecha/edad"

    def test_sensibles_cada_uno_distinguible(self):
        """Las 6 categorías sensibles deben tener colores DISTINTOS entre sí."""
        c = _colores()
        sensibles = {
            "MX_DIAGNOSTICO": c["MX_DIAGNOSTICO"],
            "MX_ORIGEN_ETNICO": c["MX_ORIGEN_ETNICO"],
            "MX_RELIGION": c["MX_RELIGION"],
            "MX_OPINION_POLITICA": c["MX_OPINION_POLITICA"],
            "MX_PREFERENCIA_SEXUAL": c["MX_PREFERENCIA_SEXUAL"],
            "MX_BIOMETRICO": c["MX_BIOMETRICO"],
        }
        assert len(set(sensibles.values())) == 6, \
            f"Las 6 categorías sensibles deben tener 6 colores distintos: {sensibles}"


# ════════════════════════════════════════════════════════════════════════════
# 2. ACTA: sin Presidio/GLiNER, ubicaciones por PÁGINA (sin renglón)
# ════════════════════════════════════════════════════════════════════════════
class TestActa:
    @pytest.fixture(scope="class")
    def acta_doc(self):
        import report_generator
        doc = pymupdf.open()
        doc.new_page()
        info = [
            {"entity_type": "MX_CURP", "pagina": 0, "y0": 100, "manual": False},
            {"entity_type": "MX_CURP", "pagina": 0, "y0": 300, "manual": False},
            {"entity_type": "PERSON",  "pagina": 1, "y0": 150, "manual": False},
        ]
        report_generator.generate_justification_page(doc, info, "test.pdf")
        texto = " ".join(p.get_text() for p in doc)
        return texto

    def test_no_menciona_presidio_ni_gliner(self, acta_doc):
        assert "presidio" not in acta_doc.lower(), "El acta NO debe mencionar Presidio"
        assert "gliner" not in acta_doc.lower(), "El acta NO debe mencionar GLiNER"

    def test_ubicaciones_solo_pagina_sin_renglon(self, acta_doc):
        # Debe haber "p.1"/"p.2" (página) y NO "r." (renglón)
        assert re.search(r"\bp\.\s?\d", acta_doc), "El acta debe indicar la página (p.N)"
        assert not re.search(r"\br\.\s?\d", acta_doc), \
            "El acta NO debe mostrar el renglón (r.N), solo la página"


# ════════════════════════════════════════════════════════════════════════════
# 3. CONSISTENCIA de las 4 listas: detección / color / manual / acta
# ════════════════════════════════════════════════════════════════════════════
class TestConsistencia4Listas:
    def test_todo_tipo_detectado_tiene_color_y_acta(self):
        import detector, ui_validator, legal_mapper
        # tipos MX_ que el detector registra (de entidades_validas)
        import inspect
        src = inspect.getsource(detector.build_analyzer)
        tipos_det = set(re.findall(r'"(MX_[A-Z_]+)"', src))
        colores = set(ui_validator.COLORES_ENTIDAD)
        acta = set(legal_mapper.LEGAL_MAPPING)
        faltan_color = tipos_det - colores
        faltan_acta = tipos_det - acta
        assert not faltan_color, f"Tipos detectados SIN color: {faltan_color}"
        assert not faltan_acta, f"Tipos detectados SIN fundamento en acta: {faltan_acta}"

    def test_manual_existe_en_color_y_acta(self):
        import ui_validator, legal_mapper
        for et in ui_validator.OPCIONES_TIPO_MANUAL.values():
            if et in ("MANUAL", "CUSTOM"):
                continue
            assert et in ui_validator.COLORES_ENTIDAD, f"Manual {et} sin color"
            assert et in legal_mapper.LEGAL_MAPPING, f"Manual {et} sin fundamento en acta"


# ════════════════════════════════════════════════════════════════════════════
# 4. AFILIACIÓN: detección bajo MX_OPINION_POLITICA
# ════════════════════════════════════════════════════════════════════════════
class TestAfiliacion:
    @pytest.fixture(scope="module")
    def analyzer(self):
        import detector
        return detector.build_analyzer()

    @pytest.mark.parametrize("texto", [
        "Afiliacion sindical: Sindicato Nacional de Trabajadores de la Educacion",
        "El trabajador esta sindicalizado al Sindicato Unico de Trabajadores",
        "Afiliacion politica: militante del Partido Accion Nacional",
    ])
    def test_afiliacion_detectada(self, analyzer, texto):
        import detector
        res = detector.analyze_page(analyzer, texto)
        tipos = {r.entity_type for r in res}
        assert "MX_OPINION_POLITICA" in tipos, \
            f"Afiliación/sindicato debe detectarse como MX_OPINION_POLITICA. Detectado: {tipos}"
