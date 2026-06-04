"""
Tests del filtro de contexto obligatorio para identificadores numéricos ambiguos.

Verifica que MX_NSS, MX_CUENTA, MX_INE_FOLIO genérico, MX_TEL y MX_CP solo
se disparan cuando hay palabras clave de contexto cercanas — eliminando
falsos positivos de folios/expedientes que cumplen el regex por longitud.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from detector import build_analyzer, analyze_page


@pytest.fixture(scope="module")
def analyzer():
    return build_analyzer()


def _tiene(resultados, tipo: str) -> bool:
    return any(r.entity_type == tipo for r in resultados)


# ── MX_NSS ────────────────────────────────────────────────────────────────────

def test_nss_con_contexto_se_detecta(analyzer):
    text = "NSS: 12345678901 del trabajador"
    assert _tiene(analyze_page(analyzer, text), "MX_NSS")


def test_nss_sin_contexto_se_descarta(analyzer):
    # 11 dígitos sin contexto NSS — debe quedar como folio, no NSS
    text = "Expediente 12345678901 ingresado el 5 de marzo"
    assert not _tiene(analyze_page(analyzer, text), "MX_NSS")


def test_nss_con_imss_se_detecta(analyzer):
    text = "Afiliación IMSS 12345678901 vigente"
    assert _tiene(analyze_page(analyzer, text), "MX_NSS")


# ── MX_CUENTA ─────────────────────────────────────────────────────────────────

def test_cuenta_con_contexto_se_detecta(analyzer):
    text = "Cuenta bancaria 1234567890 a nombre del titular"
    assert _tiene(analyze_page(analyzer, text), "MX_CUENTA")


def test_cuenta_sin_contexto_se_descarta(analyzer):
    text = "Folio 1234567890 de la solicitud presentada"
    assert not _tiene(analyze_page(analyzer, text), "MX_CUENTA")


# ── MX_TEL ────────────────────────────────────────────────────────────────────

def test_tel_con_prefijo_52_se_detecta(analyzer):
    text = "Comuníquese al +52 55 1234 5678 para atención"
    assert _tiene(analyze_page(analyzer, text), "MX_TEL")


def test_tel_con_contexto_se_detecta(analyzer):
    text = "Tel. 5512345678 oficina de atención"
    assert _tiene(analyze_page(analyzer, text), "MX_TEL")


def test_tel_10_digitos_sueltos_se_detecta(analyzer):
    """Número de 10 dígitos suelto sí se considera teléfono (regla de longitud)."""
    text = "Información disponible al 5512345678."
    assert _tiene(analyze_page(analyzer, text), "MX_TEL")


def test_tel_rango_anios_se_descarta(analyzer):
    text = "Periodo 2020-2023 reportado"
    assert not _tiene(analyze_page(analyzer, text), "MX_TEL")


# ── MX_CP ─────────────────────────────────────────────────────────────────────

def test_cp_con_contexto_postal_se_detecta(analyzer):
    text = "Domicilio en Colonia Roma, C.P. 06700 CDMX"
    assert _tiene(analyze_page(analyzer, text), "MX_CP")


def test_cp_sin_contexto_se_descarta(analyzer):
    """5 dígitos sueltos sin domicilio cerca no son CP."""
    text = "El pago de $34250 venció el viernes"
    # 34250 cumple regex de CP pero no tiene contexto postal cercano
    assert not _tiene(analyze_page(analyzer, text), "MX_CP")
