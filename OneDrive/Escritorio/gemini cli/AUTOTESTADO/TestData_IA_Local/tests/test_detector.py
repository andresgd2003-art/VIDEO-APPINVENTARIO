"""Tests for src/detector.py — Hito 2"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from detector import build_analyzer, analyze_page


# ---------------------------------------------------------------------------
# Fixture — el analyzer se construye UNA vez por sesion de tests (spaCy es costoso)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def analyzer():
    return build_analyzer()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_analyzer_returns_engine():
    """build_analyzer() debe retornar un objeto con metodo analyze."""
    engine = build_analyzer()
    assert hasattr(engine, "analyze"), "El engine debe tener el metodo analyze"
    assert callable(engine.analyze)


def test_analyze_empty_text(analyzer):
    """analyze_page con texto vacio debe retornar lista vacia sin lanzar excepcion."""
    result = analyze_page(analyzer, "")
    assert result == [], f"Se esperaba lista vacia, se obtuvo: {result}"


def test_detect_curp_indices(analyzer):
    """
    Debe detectar MX_CURP y los indices start/end deben apuntar exactamente
    al string 'GOMC900514HDFRRR05' dentro del texto.
    """
    text = "Favor de proporcionar su CURP: GOMC900514HDFRRR05 para continuar."
    curp_str = "GOMC900514HDFRRR05"
    expected_start = text.index(curp_str)
    expected_end = expected_start + len(curp_str)

    results = analyze_page(analyzer, text)
    curp_results = [r for r in results if r.entity_type == "MX_CURP"]

    assert len(curp_results) >= 1, (
        f"Se esperaba al menos un resultado MX_CURP. Resultados: {results}"
    )

    match = next(
        (r for r in curp_results if r.start == expected_start and r.end == expected_end),
        None,
    )
    assert match is not None, (
        f"Ningun resultado MX_CURP apunta al rango [{expected_start}, {expected_end}]. "
        f"Resultados CURP: {[(r.start, r.end) for r in curp_results]}"
    )


def test_detect_rfc(analyzer):
    """Debe detectar al menos un resultado cuyo entity_type contenga 'RFC'."""
    text = "RFC del contribuyente: GOMC900514AB3"
    results = analyze_page(analyzer, text)
    rfc_results = [r for r in results if "RFC" in r.entity_type]

    assert len(rfc_results) >= 1, (
        f"Se esperaba al menos un resultado de tipo RFC. Resultados: {results}"
    )


def test_detect_email(analyzer):
    """Debe detectar el email juan.perez@example.com en el texto."""
    text = "Contacto: juan.perez@example.com para mas info"
    results = analyze_page(analyzer, text)

    email_results = [r for r in results if "EMAIL" in r.entity_type or "email" in r.entity_type.lower()]
    # Tambien aceptar la entidad propia del recognizer MX_EMAIL
    email_results_mx = [r for r in results if r.entity_type == "MX_EMAIL"]

    combined = email_results + [r for r in email_results_mx if r not in email_results]
    assert len(combined) >= 1, (
        f"Se esperaba deteccion de email. Resultados: {results}"
    )


def test_no_false_positive_short_number(analyzer):
    """
    Un numero corto (5 digitos) no debe disparar MX_CLABE (18 digitos)
    ni MX_NSS (11 digitos).
    """
    text = "El folio es 12345."
    results = analyze_page(analyzer, text)

    clabe_results = [r for r in results if r.entity_type == "MX_CLABE"]
    nss_results = [r for r in results if r.entity_type == "MX_NSS"]

    assert len(clabe_results) == 0, (
        f"Falso positivo MX_CLABE en numero corto: {clabe_results}"
    )
    assert len(nss_results) == 0, (
        f"Falso positivo MX_NSS en numero corto: {nss_results}"
    )

def test_detect_monto_texto(analyzer):
    """Debe detectar cantidades en pesos escritas con letra."""
    text = "la cantidad de Doscientos cuarenta y cinco mil pesos 00/100 M.N. es correcta"
    results = analyze_page(analyzer, text)
    monto_results = [r for r in results if r.entity_type == "MX_MONTO"]

    assert len(monto_results) >= 1, (
        f"Se esperaba deteccion de monto en texto. Resultados: {results}"
    )
    # Verificar que capturó la frase completa
    match = monto_results[0]
    matched_text = text[match.start:match.end]
    assert "Doscientos cuarenta y cinco mil pesos 00/100 M.N." in matched_text, (
        f"No capturó el texto completo: {matched_text}"
    )
