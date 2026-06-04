"""Tests for src/pdf_reader.py — Hito 1"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import pymupdf
from pdf_reader import open_pdf, extract_words, build_spatial_index


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_test_pdf(text: str) -> pymupdf.Document:
    """Create an in-memory PDF with the given text on page 0."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=11)
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_open_pdf_not_found():
    """open_pdf must raise FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError):
        open_pdf("no_existe.pdf")


def test_extract_words_tuple_structure():
    """Each word tuple must have 8 elements with correct types."""
    doc = _make_test_pdf("Hola mundo prueba")
    page = doc[0]
    words = extract_words(page)

    assert len(words) > 0, "Se esperaban palabras en el PDF de prueba"

    for w in words:
        assert len(w) == 8, f"Se esperaban 8 elementos, se obtuvieron {len(w)}"
        # Coordenadas (x0, y0, x1, y1)
        for i in range(4):
            assert isinstance(w[i], float), f"Elemento [{i}] debe ser float, es {type(w[i])}"
        # Palabra
        assert isinstance(w[4], str), f"Elemento [4] debe ser str, es {type(w[4])}"
        # block_no, line_no, word_no
        for i in range(5, 8):
            assert isinstance(w[i], int), f"Elemento [{i}] debe ser int, es {type(w[i])}"


def test_build_spatial_index_keys():
    """Cada dict del indice debe tener las claves word, start_idx, end_idx, rect."""
    doc = _make_test_pdf("Hola mundo prueba")
    page = doc[0]
    words = extract_words(page)
    index = build_spatial_index(words)

    assert len(index) > 0, "El indice no debe estar vacio"
    for entry in index:
        assert "word" in entry
        assert "start_idx" in entry
        assert "end_idx" in entry
        assert "rect" in entry


def test_build_spatial_index_ordering():
    """Los start_idx deben ser estrictamente crecientes."""
    doc = _make_test_pdf("alfa beta gamma delta")
    page = doc[0]
    words = extract_words(page)
    index = build_spatial_index(words)

    assert len(index) > 1, "Se necesitan al menos 2 entradas para verificar orden"
    for i in range(1, len(index)):
        assert index[i]["start_idx"] > index[i - 1]["start_idx"], (
            f"start_idx no creciente en posicion {i}: "
            f"{index[i - 1]['start_idx']} >= {index[i]['start_idx']}"
        )


def test_build_spatial_index_disambiguation():
    """
    Hito 1 — test critico: la palabra 'Juan' repetida 3 veces debe generar
    3 entradas separadas en el indice, cada una con start_idx distinto.
    El indice NO debe colapsar duplicados.
    """
    doc = _make_test_pdf("Juan vio a Juan y Juan sonrio")
    page = doc[0]
    words = extract_words(page)
    index = build_spatial_index(words)

    juan_entries = [e for e in index if e["word"] == "Juan"]
    assert len(juan_entries) == 3, (
        f"Se esperaban 3 entradas para 'Juan', se encontraron {len(juan_entries)}"
    )

    start_indices = [e["start_idx"] for e in juan_entries]
    assert len(set(start_indices)) == 3, (
        f"Los start_idx de 'Juan' deben ser todos distintos: {start_indices}"
    )
