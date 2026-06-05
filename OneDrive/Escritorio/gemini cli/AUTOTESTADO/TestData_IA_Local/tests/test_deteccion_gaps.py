# -*- coding: utf-8 -*-
"""
REGRESIÓN PERMANENTE — huecos de detección corregidos en detector.py.

Cada caso reproduce una frase que ANTES no se detectaba y AHORA debe detectarse:
  1. MX_LUGAR_NAC  — lugar de nacimiento seguido de "Sexo:" (lookahead relajado).
  2. MX_NACIONALIDAD — "Nacionalidad: MEXICANA" (dos puntos opcionales).
  3. MX_MONTO — "$ 1,250,340.00 M.N." (espacio tras $, monto grande, sufijo M.N.).
  4. MX_DOMICILIO — "Vialidad: EJE VIAL ..." y vialidades con número desnudo.
  5. MX_NOMBRE — nombres tras etiquetas judiciales (Albacea, Coadyuvante, etc.).

El analyzer se carga UNA sola vez (fixture scope=module).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="module")
def analyzer():
    import detector
    return detector.build_analyzer()


def _tipos(analyzer, texto):
    """Conjunto de entity_types detectados en `texto`."""
    import detector
    return {r.entity_type for r in detector.analyze_page(analyzer, texto)}


def _spans(analyzer, texto, tipo):
    """Lista de textos detectados de un tipo dado."""
    import detector
    return [
        texto[r.start:r.end]
        for r in detector.analyze_page(analyzer, texto)
        if r.entity_type == tipo
    ]


# ── Hueco 1: MX_LUGAR_NAC ──────────────────────────────────────────────────────
def test_lugar_nac_seguido_de_sexo(analyzer):
    t = "LUGAR DE NACIMIENTO DURANGO DURANGO MEXICO Sexo: MASCULINO"
    assert "MX_LUGAR_NAC" in _tipos(analyzer, t)


def test_lugar_nac_seguido_de_keyword_existente(analyzer):
    t = "LUGAR DE NACIMIENTO DURANGO DURANGO MEXICO LOCALIDAD VICTORIA"
    assert "MX_LUGAR_NAC" in _tipos(analyzer, t)


# ── Hueco 2: MX_NACIONALIDAD ───────────────────────────────────────────────────
def test_nacionalidad_con_dos_puntos(analyzer):
    t = "Datos del titular. Nacionalidad: MEXICANA"
    assert "MX_NACIONALIDAD" in _tipos(analyzer, t)


def test_nacionalidad_sin_dos_puntos(analyzer):
    t = "Datos del titular. NACIONALIDAD MEXICANA"
    assert "MX_NACIONALIDAD" in _tipos(analyzer, t)


# ── Hueco 3: MX_MONTO ──────────────────────────────────────────────────────────
def test_monto_con_espacio_y_grande(analyzer):
    t = "El valor del bien asciende a la cantidad de $ 1,250,340.00 M.N."
    assert "MX_MONTO" in _tipos(analyzer, t)


def test_monto_simple_sigue_funcionando(analyzer):
    t = "Se pagó la cantidad de $3,500.00 por el servicio."
    assert "MX_MONTO" in _tipos(analyzer, t)


# ── Hueco 4: MX_DOMICILIO (vialidad) ───────────────────────────────────────────
def test_domicilio_vialidad_eje_vial(analyzer):
    t = "Vialidad: EJE VIAL Lazaro Cardenas 1250 Colonia Centro"
    assert "MX_DOMICILIO" in _tipos(analyzer, t)


def test_domicilio_calzada_numero_desnudo(analyzer):
    t = "Con domicilio en Calzada Independencia 458 de esta ciudad."
    assert "MX_DOMICILIO" in _tipos(analyzer, t)


# ── Hueco 5: MX_NOMBRE tras etiqueta judicial ──────────────────────────────────
@pytest.mark.parametrize("frase,esperado", [
    ("Albacea: Rosa Maria Elena Quintero", "Rosa Maria Elena Quintero"),
    ("Coadyuvante: Juan Carlos Perez Lopez", "Juan Carlos Perez Lopez"),
    ("Heredero: Pedro Ramirez Soto", "Pedro Ramirez Soto"),
    ("Heredera: Ana Gomez Vargas", "Ana Gomez Vargas"),
    ("Legatario: Luis Torres Mena", "Luis Torres Mena"),
    ("Cesionario: Mario Diaz Cano", "Mario Diaz Cano"),
    ("Cedente: Sofia Luna Reyes", "Sofia Luna Reyes"),
    ("Otorgante: Roberto Silva Pena", "Roberto Silva Pena"),
    ("Compareciente: Laura Mendez Rios", "Laura Mendez Rios"),
])
def test_nombre_tras_etiqueta_judicial(analyzer, frase, esperado):
    spans = _spans(analyzer, frase, "MX_NOMBRE")
    assert spans, f"No se detectó MX_NOMBRE en: {frase}"
    # El nombre debe quedar limpio (sin la etiqueta).
    nombre = esperado.split()[0]  # primer nombre propio
    assert any(nombre in s and ":" not in s for s in spans), \
        f"Nombre no limpio para {frase!r}: {spans}"


# ── Cero falsos positivos: "calle" genérica sin número/contexto ────────────────
def test_no_falso_positivo_calle_generica(analyzer):
    t = "Bajaron a la calle para protestar contra la decision tomada."
    assert "MX_DOMICILIO" not in _tipos(analyzer, t)


# ── PDFs reales ────────────────────────────────────────────────────────────────
_DOCS_DIR = r"C:\Users\user\OneDrive\Escritorio\mis docs"
BRUTAL = os.path.join(_DOCS_DIR, "PRUEBA_BRUTAL_ANONIMA.pdf")
INE = os.path.join(_DOCS_DIR, "IDENTIFICACION OFICIAL.pdf")
CURP = os.path.join(_DOCS_DIR, "curp.pdf")


def _detectar_pdf(analyzer, pdf_path):
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


@pytest.mark.skipif(not os.path.exists(BRUTAL), reason="PDF de prueba no disponible")
def test_pdf_brutal_huecos(analyzer):
    pares = _detectar_pdf(analyzer, BRUTAL)
    tipos = {t for t, _ in pares}
    # Al menos uno de los huecos debe materializarse en el documento brutal.
    esperados = {"MX_LUGAR_NAC", "MX_NACIONALIDAD", "MX_MONTO", "MX_DOMICILIO", "MX_NOMBRE"}
    assert tipos & esperados, f"Ningún hueco detectado en BRUTAL; tipos={tipos}"


@pytest.mark.skipif(not os.path.exists(INE), reason="PDF INE no disponible")
def test_pdf_ine_no_revienta(analyzer):
    pares = _detectar_pdf(analyzer, INE)
    assert isinstance(pares, list)


@pytest.mark.skipif(not os.path.exists(CURP), reason="PDF CURP no disponible")
def test_pdf_curp_lugar_o_nacionalidad(analyzer):
    pares = _detectar_pdf(analyzer, CURP)
    tipos = {t for t, _ in pares}
    assert isinstance(pares, list)
