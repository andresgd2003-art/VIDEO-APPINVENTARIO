"""
Tests funcionales para el fix critico en mapper.map_entities:
- Soporta tanto dicts como objetos RecognizerResult via _get(r, field)
"""
import os
import sys
import pytest
import pymupdf
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import mapper


# ---------------------------------------------------------------------------
# Fixture compartida: analyzer (costoso de construir)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def analyzer():
    from detector import build_analyzer
    return build_analyzer()


# ---------------------------------------------------------------------------
# Fixture: spatial_index de 3 palabras comun a varios tests
# ---------------------------------------------------------------------------
@pytest.fixture
def spatial_index_3():
    return [
        {"word": "GADA0307211L8",        "start_idx": 0,  "end_idx": 13, "rect": pymupdf.Rect(10, 10, 100, 20)},
        {"word": "CURP:",                 "start_idx": 14, "end_idx": 19, "rect": pymupdf.Rect(10, 30, 50,  40)},
        {"word": "GADA030721HDGLZNA8",    "start_idx": 20, "end_idx": 38, "rect": pymupdf.Rect(55, 30, 200, 40)},
    ]


# ---------------------------------------------------------------------------
# 1. map_entities con dicts (como devuelve llm_auditor)
# ---------------------------------------------------------------------------
def test_map_entities_con_dicts(spatial_index_3):
    analyzer_results = [
        {"entity_type": "MX_RFC_PF", "text": "GADA0307211L8",        "start": 0,  "end": 13, "score": 0.85},
        {"entity_type": "MX_CURP",   "text": "GADA030721HDGLZNA8",   "start": 20, "end": 38, "score": 0.85},
    ]
    mapped = mapper.map_entities(spatial_index_3, analyzer_results)
    assert len(mapped) == 2
    assert mapped[0]["entity_type"] == "MX_RFC_PF"
    assert len(mapped[0]["rects"]) == 1
    assert mapped[1]["entity_type"] == "MX_CURP"
    assert len(mapped[1]["rects"]) == 1


# ---------------------------------------------------------------------------
# 2. map_entities con objetos SimpleNamespace (backward compat)
# ---------------------------------------------------------------------------
def test_map_entities_con_objetos(spatial_index_3):
    result_obj = SimpleNamespace(entity_type="MX_CURP", start=20, end=38, score=0.85)
    mapped = mapper.map_entities(spatial_index_3, [result_obj])
    assert len(mapped) == 1
    assert mapped[0]["entity_type"] == "MX_CURP"
    assert len(mapped[0]["rects"]) >= 1


# ---------------------------------------------------------------------------
# 3. Pipeline completo sobre csf.pdf sin LLM
# ---------------------------------------------------------------------------
def test_pipeline_completo_csf_sin_llm(analyzer):
    from pdf_reader import extract_words, build_spatial_index
    from detector import analyze_page
    from mapper import map_entities

    pdf_path = r'c:/Users/user/OneDrive/Escritorio/gemini cli/AUTOTESTADO/csf.pdf'
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    words = extract_words(page)
    spatial_index = build_spatial_index(words)
    text = " ".join(e["word"] for e in spatial_index)
    presidio_raw = analyze_page(analyzer, text)

    # Convertir a dicts (como hace ui_validator / llm_auditor)
    presidio_dicts = [
        {
            "entity_type": r.entity_type,
            "text":        text[r.start:r.end],
            "start":       r.start,
            "end":         r.end,
            "score":       r.score,
        }
        for r in presidio_raw
    ]

    # Pasar dicts directamente a mapper (esto fallaba antes del fix)
    mapped = map_entities(spatial_index, presidio_dicts)

    assert isinstance(mapped, list)
    assert len(mapped) > 0, "Se esperan entidades en csf.pdf"

    # RFC debe estar presente
    rfc_entities = [m for m in mapped if "RFC" in m["entity_type"]]
    assert len(rfc_entities) > 0, "RFC debe detectarse en csf.pdf"

    # Cada entidad debe tener rects validos
    for m in mapped:
        assert len(m["rects"]) > 0, f"Entidad {m['entity_type']} sin rects"
        for rect in m["rects"]:
            assert rect.x0 < rect.x1, f"rect invalido: x0={rect.x0} >= x1={rect.x1}"
            assert rect.y0 < rect.y1, f"rect invalido: y0={rect.y0} >= y1={rect.y1}"

    doc.close()


# ---------------------------------------------------------------------------
# 4. ui_validator importa con modo claro y titulo ANONIMA
# ---------------------------------------------------------------------------
def test_ui_validator_import_y_titulo():
    source = open('src/ui_validator.py', encoding='utf-8').read()
    assert 'ANONIMA' in source,       "Titulo ANONIMA no encontrado en ui_validator.py"
    assert 'light' in source,           "Modo claro ('light') no encontrado en ui_validator.py"
    assert 'ValidadorPDFApp' in source, "Clase ValidadorPDFApp no encontrada en ui_validator.py"


# ---------------------------------------------------------------------------
# 5. map_entities con listas vacias retorna [] sin exception
# ---------------------------------------------------------------------------
def test_mapper_no_crash_lista_vacia():
    result = mapper.map_entities([], [])
    assert result == []


# ---------------------------------------------------------------------------
# 6. Entidad con rango fuera del indice espacial retorna lista vacia
# ---------------------------------------------------------------------------
def test_mapper_entidad_sin_match():
    spatial_index = [
        {"word": "Hola", "start_idx": 0, "end_idx": 4, "rect": pymupdf.Rect(0, 0, 10, 10)}
    ]
    result = {"entity_type": "MX_CURP", "start": 100, "end": 118, "score": 0.85}
    mapped = mapper.map_entities(spatial_index, [result])
    assert mapped == [], f"Se esperaba [], se obtuvo {mapped}"
