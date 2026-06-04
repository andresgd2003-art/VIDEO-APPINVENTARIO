"""
Diagnóstico OCR de fugas de texto alrededor de recuadros de redacción.

Para cada entidad detectada en la primera página de un PDF real:
1. Renderiza la página a ZOOM=2.0
2. Dibuja el recuadro de redacción (con padding actual)
3. Recorta franjas de FRANJA_PX píxeles a la IZQUIERDA y DERECHA del recuadro
4. Corre PaddleOCR sobre esas franjas
5. Reporta cualquier texto/carácter suelto encontrado fuera del área tapada

Si PaddleOCR encuentra letras/números en la franja → overflow confirmado.
"""
import sys
import os
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
import pymupdf
from PIL import Image, ImageDraw

import pdf_reader
import detector
import mapper

ZOOM        = 2.0
PAD_LEFT    = 4.0 * ZOOM
PAD_RIGHT   = 2.0 * ZOOM
PAD_Y       = 2.0 * ZOOM
FRANJA_PX   = 16          # píxeles a escanear fuera del recuadro en cada lado
OCR_CONF    = 0.25        # umbral de confianza PaddleOCR


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_pdf_path():
    base = os.path.dirname(__file__)
    for name in ("LGPDPPSO.pdf", "LGTAIP.pdf"):
        p = os.path.join(base, "..", "docs", name)
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def _render_page(page) -> Image.Image:
    mat = pymupdf.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _get_easyocr():
    """Devuelve un reader OCR (PaddleOCR) compatible con _ocr_tiene_texto."""
    try:
        import os
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        from paddleocr import PaddleOCR
        return PaddleOCR(
            lang="es",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    except ImportError:
        return None


def _franja(img: Image.Image, x0, y0, x1, y1, lado: str) -> Image.Image | None:
    """Recorta la franja de FRANJA_PX px a la izquierda o derecha del recuadro."""
    W, H = img.size
    if lado == "izq":
        fx0 = max(0, int(x0) - FRANJA_PX)
        fx1 = max(0, int(x0) - 1)
    else:  # "der"
        fx0 = min(W, int(x1) + 1)
        fx1 = min(W, int(x1) + FRANJA_PX)
    fy0 = max(0, int(y0) - 2)
    fy1 = min(H, int(y1) + 2)
    if fx1 <= fx0 or fy1 <= fy0:
        return None
    return img.crop((fx0, fy0, fx1, fy1))


def _ocr_tiene_texto(reader, crop: Image.Image) -> list[str]:
    """Devuelve lista de textos detectados con confianza >= OCR_CONF."""
    import numpy as np
    arr = np.array(crop)
    resultados = reader.predict(input=arr)
    if not resultados:
        return []
    r0 = resultados[0]
    textos = r0.get("rec_texts", []) or []
    scores = r0.get("rec_scores", []) or []
    return [txt for txt, conf in zip(textos, scores) if conf >= OCR_CONF and txt.strip()]


# ── fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pipeline_resultado():
    """Ejecuta el pipeline completo en la primera página del PDF real."""
    pdf_path = _get_pdf_path()
    if not pdf_path:
        pytest.skip("No hay PDFs en docs/")

    doc    = pymupdf.open(pdf_path)
    page   = doc[0]
    analizador = detector.build_analyzer()

    palabras  = pdf_reader.extract_words(page)
    idx_esp   = pdf_reader.build_spatial_index(palabras, page)
    texto     = " ".join(e["word"] for e in idx_esp)
    presidio  = detector.analyze_page(analizador, texto)
    dicts_p   = [
        {"entity_type": r.entity_type, "text": texto[r.start:r.end],
         "start": r.start, "end": r.end, "score": r.score}
        for r in presidio
    ]
    entidades = mapper.map_entities(idx_esp, dicts_p)
    img_base  = _render_page(page)

    doc.close()
    return entidades, img_base, pdf_path


# ── Tests de cobertura visual ─────────────────────────────────────────────────

def test_pipeline_detecta_entidades(pipeline_resultado):
    """El pipeline debe detectar al menos 1 entidad en la primera página."""
    entidades, _, pdf_path = pipeline_resultado
    assert len(entidades) > 0, f"No se detectaron entidades en {pdf_path}"
    print(f"\nEntidades detectadas: {len(entidades)}")
    for e in entidades:
        print(f"  [{e['entity_type']}] '{e.get('text','?')}' — {len(e['rects'])} rect(s)")


def test_rects_cubren_bbox_palabras(pipeline_resultado):
    """
    Cada rect de entidad, con padding aplicado, debe ser más grande que el
    bbox de la palabra original (x0 menor, x1 mayor).
    """
    entidades, img_base, _ = pipeline_resultado
    W, H = img_base.size
    problemas = []

    for ent in entidades:
        for rect in ent["rects"]:
            x0 = rect.x0 * ZOOM - PAD_LEFT
            x1 = rect.x1 * ZOOM + PAD_RIGHT
            y0 = rect.y0 * ZOOM - PAD_Y
            y1 = rect.y1 * ZOOM + PAD_Y

            # El recuadro no debe estar fuera de la imagen
            if x0 < 0:
                problemas.append(f"[{ent['entity_type']}] x0={x0:.1f} < 0 (sale de la página)")
            if x1 > W:
                problemas.append(f"[{ent['entity_type']}] x1={x1:.1f} > W={W}")
            # Debe tener ancho razonable (>2px)
            if (x1 - x0) < 2:
                problemas.append(f"[{ent['entity_type']}] ancho={x1-x0:.1f}px demasiado pequeño")

    if problemas:
        pytest.fail("Problemas de geometría en rects:\n" + "\n".join(problemas))


@pytest.mark.skipif(_get_easyocr() is None, reason="PaddleOCR no disponible")
def test_sin_overflow_izquierdo_ocr(pipeline_resultado, tmp_path):
    """
    OCR en franja izquierda (FRANJA_PX px antes del borde x0 del recuadro)
    no debe encontrar caracteres alfanuméricos — confirma que no hay letras sueltas.
    """
    entidades, img_base, _ = pipeline_resultado
    reader = _get_easyocr()
    fugas = []

    # Imagen de diagnóstico con las franjas marcadas
    diag = img_base.copy()
    draw = ImageDraw.Draw(diag)

    for ent in entidades:
        for rect in ent["rects"]:
            x0 = rect.x0 * ZOOM - PAD_LEFT
            x1 = rect.x1 * ZOOM + PAD_RIGHT
            y0 = rect.y0 * ZOOM - PAD_Y
            y1 = rect.y1 * ZOOM + PAD_Y

            # Dibujar recuadro principal
            draw.rectangle([x0, y0, x1, y1], outline="#FF6600", width=2)

            # Escanear franja izquierda
            crop_izq = _franja(img_base, x0, y0, x1, y1, "izq")
            if crop_izq and crop_izq.size[0] >= 3:
                # Marcar franja en imagen de diagnóstico (azul = zona escaneada)
                fx0 = max(0, int(x0) - FRANJA_PX)
                draw.rectangle([fx0, int(y0), int(x0)-1, int(y1)], outline="#0066FF", width=1)
                textos = _ocr_tiene_texto(reader, crop_izq)
                if textos:
                    fugas.append({
                        "tipo":  ent["entity_type"],
                        "texto_entidad": ent.get("text", "?"),
                        "lado":  "IZQUIERDA",
                        "chars": textos,
                        "rect":  (round(x0,1), round(y0,1), round(x1,1), round(y1,1)),
                    })
                    # Marcar en rojo en diagnóstico
                    draw.rectangle([fx0, int(y0), int(x0)-1, int(y1)], outline="#FF0000", width=2)

    out = tmp_path / "diagnostico_overflow_izq.png"
    diag.save(str(out))
    print(f"\nDiagnóstico guardado: {out}")

    if fugas:
        reporte = "\n".join(
            f"  [{f['tipo']}] '{f['texto_entidad']}' — izq leaked: {f['chars']} @ {f['rect']}"
            for f in fugas
        )
        pytest.fail(f"OVERFLOW IZQUIERDO detectado por OCR en {len(fugas)} recuadro(s):\n{reporte}")


@pytest.mark.skipif(_get_easyocr() is None, reason="PaddleOCR no disponible")
def test_sin_overflow_derecho_ocr(pipeline_resultado, tmp_path):
    """
    OCR en franja derecha (FRANJA_PX px después del borde x1 del recuadro)
    no debe encontrar caracteres alfanuméricos contiguos a la entidad.
    """
    entidades, img_base, _ = pipeline_resultado
    reader = _get_easyocr()
    fugas = []

    diag = img_base.copy()
    draw = ImageDraw.Draw(diag)

    for ent in entidades:
        for rect in ent["rects"]:
            x0 = rect.x0 * ZOOM - PAD_LEFT
            x1 = rect.x1 * ZOOM + PAD_RIGHT
            y0 = rect.y0 * ZOOM - PAD_Y
            y1 = rect.y1 * ZOOM + PAD_Y

            draw.rectangle([x0, y0, x1, y1], outline="#FF6600", width=2)

            crop_der = _franja(img_base, x0, y0, x1, y1, "der")
            if crop_der and crop_der.size[0] >= 3:
                fx1 = min(img_base.size[0], int(x1) + FRANJA_PX)
                draw.rectangle([int(x1)+1, int(y0), fx1, int(y1)], outline="#0066FF", width=1)
                textos = _ocr_tiene_texto(reader, crop_der)
                if textos:
                    fugas.append({
                        "tipo":  ent["entity_type"],
                        "texto_entidad": ent.get("text", "?"),
                        "lado":  "DERECHA",
                        "chars": textos,
                        "rect":  (round(x0,1), round(y0,1), round(x1,1), round(y1,1)),
                    })
                    draw.rectangle([int(x1)+1, int(y0), fx1, int(y1)], outline="#FF0000", width=2)

    out = tmp_path / "diagnostico_overflow_der.png"
    diag.save(str(out))
    print(f"\nDiagnóstico guardado: {out}")

    if fugas:
        reporte = "\n".join(
            f"  [{f['tipo']}] '{f['texto_entidad']}' — der leaked: {f['chars']} @ {f['rect']}"
            for f in fugas
        )
        pytest.fail(f"OVERFLOW DERECHO detectado por OCR en {len(fugas)} recuadro(s):\n{reporte}")


@pytest.mark.skipif(_get_easyocr() is None, reason="PaddleOCR no disponible")
def test_reporte_completo_fugas(pipeline_resultado, tmp_path):
    """
    Test combinado: genera PNG de diagnóstico con TODAS las fugas (izq+der)
    marcadas en rojo, y reporta el porcentaje de recuadros con problemas.
    No falla — solo reporta. Útil para medir mejora entre versiones.
    """
    entidades, img_base, pdf_path = pipeline_resultado
    reader = _get_easyocr()

    diag = img_base.copy()
    draw = ImageDraw.Draw(diag)

    total_rects  = 0
    rects_con_fuga = 0
    reporte_lineas = [f"PDF: {os.path.basename(pdf_path)}", ""]

    for ent in entidades:
        for rect in ent["rects"]:
            total_rects += 1
            x0 = rect.x0 * ZOOM - PAD_LEFT
            x1 = rect.x1 * ZOOM + PAD_RIGHT
            y0 = rect.y0 * ZOOM - PAD_Y
            y1 = rect.y1 * ZOOM + PAD_Y

            draw.rectangle([x0, y0, x1, y1], outline="#FF6600", width=2)

            fugas_este = []
            for lado in ("izq", "der"):
                crop = _franja(img_base, x0, y0, x1, y1, lado)
                if crop and crop.size[0] >= 3:
                    textos = _ocr_tiene_texto(reader, crop)
                    if textos:
                        fugas_este.append((lado, textos))

            if fugas_este:
                rects_con_fuga += 1
                draw.rectangle([x0-1, y0-1, x1+1, y1+1], outline="#FF0000", width=3)
                fugas_str = "; ".join(f"{l}: {t}" for l, t in fugas_este)
                reporte_lineas.append(
                    f"  FUGA [{ent['entity_type']}] '{ent.get('text','?')}' → {fugas_str}"
                )

    pct_ok = 100 * (total_rects - rects_con_fuga) / max(total_rects, 1)
    reporte_lineas += [
        "",
        f"Total recuadros: {total_rects}",
        f"Sin fuga: {total_rects - rects_con_fuga} ({pct_ok:.1f}%)",
        f"Con fuga: {rects_con_fuga}",
    ]

    out_png = tmp_path / "diagnostico_fugas_completo.png"
    out_txt = tmp_path / "reporte_fugas.txt"
    diag.save(str(out_png))
    out_txt.write_text("\n".join(reporte_lineas), encoding="utf-8")

    print("\n" + "\n".join(reporte_lineas))
    print(f"\nPNG: {out_png}")
    print(f"TXT: {out_txt}")

    # No falla — solo documenta
    assert total_rects >= 0
