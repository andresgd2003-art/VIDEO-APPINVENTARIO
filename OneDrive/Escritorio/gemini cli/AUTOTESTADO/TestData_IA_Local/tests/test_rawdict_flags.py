"""
Propuesta 7: Comparar x0 de palabras extraídas con flags=0 vs
flags=pymupdf.TEXT_PRESERVE_WHITESPACE en _words_from_rawdict.

El test PASA si:
  - No se encuentra ningún PDF accesible → skip.
  - Se encuentra un PDF → compara x0 de las primeras 5 palabras entre los
    dos conjuntos de flags. Pasa incondicionalmente (es un test de
    descubrimiento / instrumentación), e imprime las diferencias.
"""
import glob
import os
import sys

import pytest
import pymupdf

# Asegurar que src/ esté en el path
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ── Buscar un PDF accesible ────────────────────────────────────────────────────

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATES = (
    glob.glob(os.path.join(_BASE, "tests", "*.pdf"))
    + glob.glob(os.path.join(_BASE, "tests", "data", "*.pdf"))
    + glob.glob(os.path.join(_BASE, "docs", "*.pdf"))
)
_PDF_PATH = _CANDIDATES[0] if _CANDIDATES else None


def _extract_words_with_flags(page: pymupdf.Page, flags: int) -> list[tuple]:
    """Replica la lógica de _words_from_rawdict con flags configurables."""
    resultado: list[tuple] = []
    blocks = page.get_text("rawdict", flags=flags)["blocks"]
    for b_no, block in enumerate(blocks):
        for l_no, line in enumerate(block.get("lines", [])):
            for span in line.get("spans", []):
                chars = span.get("chars", [])
                if not chars:
                    continue
                word_chars: list[dict] = []
                w_no = 0
                for ch in chars:
                    c = ch.get("c", "")
                    if c in (" ", "\t", "\n", "\r", "\xa0"):
                        if word_chars:
                            x0 = min(c["bbox"][0] for c in word_chars)
                            y0 = min(c["bbox"][1] for c in word_chars)
                            x1 = max(c["bbox"][2] for c in word_chars)
                            y1 = max(c["bbox"][3] for c in word_chars)
                            word = "".join(c["c"] for c in word_chars)
                            resultado.append((x0, y0, x1, y1, word, b_no, l_no, w_no))
                            w_no += 1
                            word_chars = []
                    else:
                        word_chars.append(ch)
                if word_chars:
                    x0 = min(c["bbox"][0] for c in word_chars)
                    y0 = min(c["bbox"][1] for c in word_chars)
                    x1 = max(c["bbox"][2] for c in word_chars)
                    y1 = max(c["bbox"][3] for c in word_chars)
                    word = "".join(c["c"] for c in word_chars)
                    resultado.append((x0, y0, x1, y1, word, b_no, l_no, w_no))
    resultado.sort(key=lambda w: (round(w[1] / 5), w[0]))
    return resultado


@pytest.mark.skipif(_PDF_PATH is None, reason="No hay PDFs disponibles en tests/ ni docs/")
def test_rawdict_flags_comparacion():
    """Compara x0 con flags=0 vs TEXT_PRESERVE_WHITESPACE. Siempre pasa (descubrimiento)."""
    doc = pymupdf.open(_PDF_PATH)
    page = doc[0]

    words_flags0 = _extract_words_with_flags(page, flags=0)
    words_flagsW = _extract_words_with_flags(
        page, flags=pymupdf.TEXT_PRESERVE_WHITESPACE
    )

    n = min(5, len(words_flags0), len(words_flagsW))
    print(f"\nPDF: {os.path.basename(_PDF_PATH)}")
    print(f"{'Palabra':<20} {'x0 (flags=0)':>14} {'x0 (PRESERVE_WS)':>18} {'diff':>8}")
    print("-" * 65)

    diferencias_encontradas = 0
    for i in range(n):
        w0 = words_flags0[i]
        wW = words_flagsW[i]
        diff = wW[0] - w0[0]
        if diff != 0.0:
            diferencias_encontradas += 1
        print(f"{w0[4]:<20} {w0[0]:>14.4f} {wW[0]:>18.4f} {diff:>+8.4f}")

    doc.close()

    print(f"\nPalabras comparadas: {n}")
    print(f"Con x0 diferente entre flags: {diferencias_encontradas}")
    # Test de descubrimiento: siempre pasa
    assert True
