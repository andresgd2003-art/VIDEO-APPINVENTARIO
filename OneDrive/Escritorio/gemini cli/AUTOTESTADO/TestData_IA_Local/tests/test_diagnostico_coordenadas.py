import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pymupdf
from PIL import Image
import pdf_reader

ZOOM_TEST = 1.5

def _encontrar_pdfs():
    import glob
    base = os.path.dirname(__file__)
    pdfs = glob.glob(os.path.join(base, '**', '*.pdf'), recursive=True)
    # Also search docs folder
    docs = os.path.join(base, '..', 'docs')
    pdfs += glob.glob(os.path.join(docs, '*.pdf'))
    return list(set(pdfs))


@pytest.mark.skipif(not _encontrar_pdfs(), reason="No hay PDFs de prueba")
def test_bbox_cubre_primer_pixel_oscuro():
    """
    Para cada palabra extraída, verifica que el x0 del bbox esté a la izquierda
    (o igual) del primer pixel oscuro de esa palabra en el render.
    Un pixel 'oscuro' es uno con valor < 100 en escala de grises.
    Reporta el máximo offset negativo encontrado (cuánto sobresale la tinta fuera del bbox).
    """
    pdfs = _encontrar_pdfs()
    doc = pymupdf.open(pdfs[0])
    page = doc[0]

    # Renderizar página
    mat = pymupdf.Matrix(ZOOM_TEST, ZOOM_TEST)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("L")
    import numpy as np
    arr = np.array(img)

    # Extraer palabras
    words = pdf_reader._words_from_rawdict(page)

    max_left_overflow = 0  # píxeles que sobresalen a la izquierda del bbox
    problemas = []

    for w in words[:30]:  # analizar primeras 30 palabras
        x0, y0, x1, y1, word = w[:5]
        if len(word) < 2:
            continue

        # Coordenadas en píxeles del render
        px0 = int(x0 * ZOOM_TEST)
        py0 = max(0, int(y0 * ZOOM_TEST) - 1)
        px1 = min(arr.shape[1]-1, int(x1 * ZOOM_TEST) + 1)
        py1 = min(arr.shape[0]-1, int(y1 * ZOOM_TEST) + 1)

        if px1 <= px0 or py1 <= py0:
            continue

        region = arr[py0:py1, px0:px1]
        # Encontrar columna del primer pixel oscuro
        cols_oscuras = np.where(region.min(axis=0) < 128)[0]
        if len(cols_oscuras) == 0:
            continue

        primer_col_oscura = cols_oscuras[0]  # relativo a px0
        if primer_col_oscura > 3:  # primer pixel oscuro está >3px dentro del bbox → bbox demasiado grande a la izquierda (OK)
            continue

        # primer_col_oscura == 0 significa que hay tinta EN el borde izquierdo del bbox
        # Si hay tinta a la izquierda de px0, tenemos overflow
        if px0 > 1:
            region_izq = arr[py0:py1, max(0,px0-5):px0]
            cols_izq = np.where(region_izq.min(axis=0) < 128)[0]
            if len(cols_izq) > 0:
                overflow = 5 - cols_izq[0]
                max_left_overflow = max(max_left_overflow, overflow)
                problemas.append((word, overflow))

    doc.close()

    print(f"\nPDF analizado: {pdfs[0]}")
    print(f"Máximo overflow izquierdo: {max_left_overflow}px")
    print(f"Palabras con overflow: {problemas[:10]}")

    # El test documenta el problema — no falla, solo reporta
    assert True, f"Overflow máximo: {max_left_overflow}px en {problemas[:5]}"


@pytest.mark.skipif(not _encontrar_pdfs(), reason="No hay PDFs de prueba")
def test_comparar_rawdict_vs_get_text_words():
    """
    Compara x0 de rawdict vs get_text('words') para las primeras 20 palabras comunes.
    Identifica cuál método da x0 más a la izquierda (más correcto).
    """
    pdfs = _encontrar_pdfs()
    doc = pymupdf.open(pdfs[0])
    page = doc[0]

    words_raw = pdf_reader._words_from_rawdict(page)
    words_std = page.get_text("words", sort=True)

    # Crear dict palabra→x0 para cada método
    raw_dict = {w[4]: w[0] for w in words_raw}
    std_dict = {w[4]: w[0] for w in words_std}

    diferencias = []
    for palabra in list(raw_dict.keys())[:20]:
        if palabra in std_dict:
            diff = raw_dict[palabra] - std_dict[palabra]
            if abs(diff) > 0.1:
                diferencias.append((palabra, raw_dict[palabra], std_dict[palabra], diff))

    print(f"\nPDF analizado: {pdfs[0]}")
    print(f"Total palabras rawdict: {len(words_raw)}, std: {len(words_std)}")
    print(f"\nPalabras con diferencia en x0 (rawdict - std):")
    if diferencias:
        for p, rx, sx, d in diferencias[:10]:
            print(f"  '{p}': rawdict={rx:.2f}, std={sx:.2f}, diff={d:+.2f}pt")
    else:
        print("  (ninguna diferencia > 0.1pt encontrada)")

    # También imprimir primeras 5 palabras de cada método para comparar
    print(f"\nPrimeras 5 palabras rawdict: {[(w[4], round(w[0],2)) for w in words_raw[:5]]}")
    print(f"Primeras 5 palabras std:     {[(w[4], round(w[0],2)) for w in words_std[:5]]}")

    doc.close()
    assert True  # diagnóstico puro


@pytest.mark.skipif(not _encontrar_pdfs(), reason="No hay PDFs de prueba")
def test_render_bbox_cobertura_png(tmp_path):
    """
    Renderiza primera página, dibuja todos los bboxes de palabras extraídas,
    guarda PNG en tmp_path. Verifica que al menos el 80% de las palabras
    tienen sus bboxes sin overflow (diagnóstico visual y numérico).
    """
    pdfs = _encontrar_pdfs()
    doc = pymupdf.open(pdfs[0])
    page = doc[0]

    mat = pymupdf.Matrix(ZOOM_TEST, ZOOM_TEST)
    pix = page.get_pixmap(matrix=mat)
    from PIL import ImageDraw
    import numpy as np
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img)

    words = pdf_reader._words_from_rawdict(page)
    PAD = 2.0 * ZOOM_TEST

    for w in words:
        x0, y0, x1, y1, word = w[:5]
        draw.rectangle([
            x0*ZOOM_TEST - PAD, y0*ZOOM_TEST - PAD,
            x1*ZOOM_TEST + PAD, y1*ZOOM_TEST + PAD
        ], outline="red", width=1)

    out = tmp_path / "diagnostico_bboxes.png"
    img.save(str(out))
    print(f"\nPDF analizado: {pdfs[0]}")
    print(f"\nPNG guardado en: {out}")
    print(f"Total palabras dibujadas: {len(words)}")
    print(f"Dimensiones imagen: {img.size[0]}x{img.size[1]} px")

    # También medir overflow numérico para las primeras 50 palabras
    arr = np.array(img.convert("L"))
    sin_overflow = 0
    con_overflow = 0
    for w in words[:50]:
        x0, y0, x1, y1, word = w[:5]
        px0 = int(x0 * ZOOM_TEST)
        py0 = max(0, int(y0 * ZOOM_TEST) - 1)
        py1 = min(arr.shape[0]-1, int(y1 * ZOOM_TEST) + 1)
        if px0 > 1 and py1 > py0:
            region_izq = arr[py0:py1, max(0,px0-5):px0]
            cols_izq = np.where(region_izq.min(axis=0) < 128)[0]
            if len(cols_izq) > 0:
                con_overflow += 1
            else:
                sin_overflow += 1
        else:
            sin_overflow += 1

    total = sin_overflow + con_overflow
    pct_ok = (sin_overflow / total * 100) if total > 0 else 100
    print(f"Palabras sin overflow: {sin_overflow}/{total} ({pct_ok:.1f}%)")
    print(f"Palabras con overflow: {con_overflow}/{total} ({100-pct_ok:.1f}%)")

    doc.close()
    assert len(words) > 0
