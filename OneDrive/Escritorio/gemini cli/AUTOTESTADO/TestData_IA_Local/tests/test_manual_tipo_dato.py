"""
Tests para el selector de tipo de dato en marcado manual.

Valida:
 1. La lista de opciones de tipo manual es completa y correcta.
 2. Un rect manual almacena el entity_type seleccionado (no siempre "MANUAL").
 3. El color del rect manual corresponde al COLORES_ENTIDAD del tipo elegido.
 4. info_reporte usa el entity_type real del rect manual.
 5. El acta genera la justificación legal específica, no la genérica de MANUAL.
 6. La nota "marcado manualmente" aparece en la motivación del acta.
"""
import sys
sys.path.insert(0, "src")

import pymupdf
import pytest
from legal_mapper import get_legal_justification, LEGAL_MAPPING


# ── Datos compartidos con ui_validator (simulados sin GUI) ────────────────────

# Replicamos COLORES_ENTIDAD mínimo para los tests (igual que en ui_validator)
COLORES_ENTIDAD = {
    "MX_CURP":      "#c0392b",
    "MX_RFC_PF":    "#c0392b",
    "MX_INE":       "#c0392b",
    "PERSON":       "#e67e22",
    "Persona":      "#e67e22",
    "Menor":        "#e74c3c",
    "MX_CLABE":     "#8e44ad",
    "MX_TEL":       "#2980b9",
    "MX_EMAIL":     "#2980b9",
    "MX_DOMICILIO": "#1abc9c",
    "MX_NSS":       "#8e44ad",
    "MX_DIAGNOSTICO":"#e74c3c",
    "Diagnóstico":  "#16a085",
    "MANUAL":       "#8e44ad",
}
COLOR_DEFAULT = "#d4ac0d"
COLOR_DESELECCIONADO = "#aaaaaa"

# Opciones que debe tener el combobox manual (label → entity_type)
OPCIONES_TIPO_MANUAL: dict[str, str] = {
    "Nombre / Persona":   "PERSON",
    "CURP":               "MX_CURP",
    "RFC":                "MX_RFC_PF",
    "NSS / IMSS":         "MX_NSS",
    "INE / Credencial":   "MX_INE",
    "Domicilio":          "MX_DOMICILIO",
    "Teléfono":           "MX_TEL",
    "Correo electrónico": "MX_EMAIL",
    "Diagnóstico / Salud":"MX_DIAGNOSTICO",
    "Bancario / CLABE":   "MX_CLABE",
    "Menor de edad":      "Menor",
    "Otro dato personal": "MANUAL",
}


def _hacer_rect_manual(entity_type: str, pagina: int = 0) -> dict:
    """Simula la creación de un rect manual como lo haría _on_canvas_release."""
    return {
        "rect":        pymupdf.Rect(10, 10, 100, 25),
        "pagina":      pagina,
        "seleccionado": True,
        "entity_type": entity_type,  # campo nuevo
    }


def _color_para_rect_manual(rm: dict) -> str:
    """Lógica de coloreo que debe usar _redibujar_entidades para rects manuales."""
    if not rm.get("seleccionado", True):
        return COLOR_DESELECCIONADO
    return COLORES_ENTIDAD.get(rm["entity_type"], COLOR_DEFAULT)


def _build_info_reporte(rects_manuales: list[dict], pagina: int) -> list[dict]:
    """Simula la parte de info_reporte que construye _on_click_aplicar_todo."""
    resultado = []
    for rm in rects_manuales:
        if rm["pagina"] == pagina and rm.get("seleccionado", True):
            resultado.append({
                "entity_type": rm["entity_type"],  # tipo real, no fijo "MANUAL"
                "pagina":      pagina,
                "y0":          rm["rect"].y0,
                "manual":      True,  # bandera para que el acta lo note
            })
    return resultado


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestOpcionesTipoManual:

    def test_opciones_no_vacias(self):
        assert len(OPCIONES_TIPO_MANUAL) >= 8

    def test_todos_los_entity_types_existen_en_legal_mapper(self):
        """Cada entity_type del combobox debe tener entrada en legal_mapper."""
        for label, et in OPCIONES_TIPO_MANUAL.items():
            r = get_legal_justification(et)
            # No debe caer en UNKNOWN (a menos que sea el propio MANUAL/UNKNOWN)
            if et not in ("MANUAL", "UNKNOWN"):
                assert r is not LEGAL_MAPPING["UNKNOWN"], (
                    f"Opción '{label}' → '{et}' no tiene entrada en legal_mapper"
                )

    def test_option_manual_como_fallback(self):
        """La opción 'Otro dato personal' debe mapear a 'MANUAL' como fallback."""
        assert "Otro dato personal" in OPCIONES_TIPO_MANUAL
        assert OPCIONES_TIPO_MANUAL["Otro dato personal"] == "MANUAL"

    def test_curp_rfc_nss_ine_presentes(self):
        entity_types_incluidos = set(OPCIONES_TIPO_MANUAL.values())
        for et in ("MX_CURP", "MX_RFC_PF", "MX_NSS", "MX_INE"):
            assert et in entity_types_incluidos, f"{et} no está en las opciones de tipo manual"


class TestRectManualConTipo:

    def test_rect_manual_almacena_entity_type(self):
        rm = _hacer_rect_manual("MX_CURP")
        assert rm["entity_type"] == "MX_CURP"

    def test_rect_manual_fallback_usa_manual(self):
        rm = _hacer_rect_manual("MANUAL")
        assert rm["entity_type"] == "MANUAL"

    def test_rect_manual_default_no_es_manual_si_tipo_elegido(self):
        """Si el usuario seleccionó MX_DOMICILIO, el rect no debe ser MANUAL."""
        rm = _hacer_rect_manual("MX_DOMICILIO")
        assert rm["entity_type"] != "MANUAL"


class TestColorRectManual:

    def test_color_curp_es_rojo(self):
        rm = _hacer_rect_manual("MX_CURP")
        assert _color_para_rect_manual(rm) == "#c0392b"

    def test_color_domicilio_es_verde_agua(self):
        rm = _hacer_rect_manual("MX_DOMICILIO")
        assert _color_para_rect_manual(rm) == "#1abc9c"

    def test_color_diagnostico(self):
        rm = _hacer_rect_manual("MX_DIAGNOSTICO")
        assert _color_para_rect_manual(rm) == "#e74c3c"

    def test_color_tipo_desconocido_usa_default(self):
        rm = _hacer_rect_manual("TIPO_RARÍSIMO")
        assert _color_para_rect_manual(rm) == COLOR_DEFAULT

    def test_color_deseleccionado_es_gris(self):
        rm = _hacer_rect_manual("MX_CURP")
        rm["seleccionado"] = False
        assert _color_para_rect_manual(rm) == COLOR_DESELECCIONADO


class TestInfoReporteConTipoReal:

    def test_info_reporte_usa_entity_type_real(self):
        rects = [_hacer_rect_manual("MX_CURP", pagina=0)]
        info = _build_info_reporte(rects, pagina=0)
        assert len(info) == 1
        assert info[0]["entity_type"] == "MX_CURP"

    def test_info_reporte_bandera_manual(self):
        rects = [_hacer_rect_manual("MX_TEL", pagina=0)]
        info = _build_info_reporte(rects, pagina=0)
        assert info[0].get("manual") is True

    def test_info_reporte_no_incluye_deseleccionados(self):
        rm = _hacer_rect_manual("MX_EMAIL", pagina=0)
        rm["seleccionado"] = False
        info = _build_info_reporte([rm], pagina=0)
        assert len(info) == 0

    def test_info_reporte_filtra_por_pagina(self):
        rects = [
            _hacer_rect_manual("MX_CURP",  pagina=0),
            _hacer_rect_manual("MX_EMAIL", pagina=1),
        ]
        info = _build_info_reporte(rects, pagina=0)
        assert len(info) == 1
        assert info[0]["entity_type"] == "MX_CURP"


class TestActaConTipoManualReal:

    def _generar_acta(self, entity_type: str, manual: bool = True) -> str:
        """Genera el acta y devuelve el texto completo (acta insertada al final)."""
        import report_generator
        doc = pymupdf.open()
        doc.new_page()
        info = [{
            "entity_type": entity_type,
            "pagina": 0,
            "y0": 100.0,
            "manual": manual,
        }]
        report_generator.generate_justification_page(doc, info, "test.pdf")
        return "".join(doc[i].get_text() for i in range(doc.page_count))

    def test_acta_curp_manual_cita_renapo(self):
        texto = self._generar_acta("MX_CURP")
        assert "CURP" in texto or "Población" in texto, (
            f"El acta no menciona CURP/Población para marcado manual de CURP: {texto[:400]!r}"
        )

    def test_acta_diagnostico_manual_cita_sensible(self):
        texto = self._generar_acta("MX_DIAGNOSTICO")
        assert "sensible" in texto.lower() or "LGPDPPSO" in texto, (
            f"El acta no menciona dato sensible para MX_DIAGNOSTICO manual: {texto[:400]!r}"
        )

    def test_acta_nss_manual_cita_seguro_social(self):
        texto = self._generar_acta("MX_NSS")
        assert "Seguro" in texto or "NSS" in texto or "IMSS" in texto, (
            f"El acta no menciona NSS/Seguro Social para marcado manual: {texto[:400]!r}"
        )

    def test_acta_manual_nota_marcado_manualmente(self):
        texto = self._generar_acta("MX_CURP", manual=True)
        assert "manual" in texto.lower(), (
            f"El acta no indica que fue marcado manualmente: {texto[:400]!r}"
        )

    def test_acta_tipo_manual_puro_usa_fundamento_generico(self):
        """'Otro dato personal' (MANUAL) usa la justificación genérica de LGPDPPSO."""
        texto = self._generar_acta("MANUAL")
        assert "116" in texto or "LGTAIP" in texto, (
            f"El acta MANUAL no cita Art. 116 LGTAIP: {texto[:300]!r}"
        )
