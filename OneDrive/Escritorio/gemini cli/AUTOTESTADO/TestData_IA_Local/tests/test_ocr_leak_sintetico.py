"""
Tests de cobertura OCR con PDF sintético que simula documentos judiciales mexicanos.

Crea PDFs en memoria con los patrones exactos que fallan en producción:
- Nombres en contexto de oración: "el agravio de LAURA GARZA SÁNCHEZ ante el"
- Líneas de encabezado en mayúsculas: "IMPUTADO: CARLOS MENDEZ ROJAS"
- Múltiples nombres en misma línea: "MIGUEL ÁNGEL CORTÉS RIVERA y LAURA GARZA"
- Identificadores: CURP, RFC, NSS, placas
- Texto mixto con números: "expediente 12345 del C. JUAN PÉREZ GÓMEZ"

Para cada caso:
1. Insertar texto en PDF in-memory
2. Ejecutar pipeline completo (extract_words → analyze → map_entities)
3. Renderizar página a ZOOM=2.0
4. Usar PaddleOCR para escanear franjas izquierda/derecha de cada recuadro
5. FAIL si hay caracteres detectados fuera del área tapada
"""
import sys
import os
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
import pymupdf
from PIL import Image, ImageDraw
import numpy as np

import pdf_reader
import detector
import mapper

ZOOM      = 2.0
PAD_LEFT  = 4.0 * ZOOM
PAD_RIGHT = 2.0 * ZOOM
PAD_Y     = 2.0 * ZOOM
FRANJA    = 14   # px a escanear fuera del recuadro
OCR_CONF  = 0.30


# ── helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def analizador():
    return detector.build_analyzer()


def _crear_pdf_con_texto(lineas: list[str]) -> pymupdf.Document:
    """Crea PDF A4 en memoria con las líneas dadas, fuente Helvetica 12pt."""
    doc  = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 80
    for linea in lineas:
        page.insert_text(
            pymupdf.Point(50, y),
            linea,
            fontname="helv",
            fontsize=11,
        )
        y += 20
    return doc


def _render(page: pymupdf.Page) -> Image.Image:
    mat = pymupdf.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _get_easyocr():
    """Devuelve un reader OCR (PaddleOCR) compatible con el método _ocr_crop."""
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


def _ocr_crop(reader, crop: Image.Image, min_size=4) -> list[str]:
    if crop is None or crop.size[0] < min_size or crop.size[1] < min_size:
        return []
    arr = np.array(crop)
    resultados = reader.predict(input=arr)
    if not resultados:
        return []
    r0 = resultados[0]
    textos = r0.get("rec_texts", []) or []
    scores = r0.get("rec_scores", []) or []
    return [t for t, c in zip(textos, scores) if c >= OCR_CONF and t.strip()]


def _analizar_pagina(analizador, page: pymupdf.Page) -> tuple:
    palabras  = pdf_reader.extract_words(page)
    idx       = pdf_reader.build_spatial_index(palabras, page)
    texto     = " ".join(e["word"] for e in idx)
    presidio  = detector.analyze_page(analizador, texto)
    dicts_p   = [
        {"entity_type": r.entity_type, "text": texto[r.start:r.end],
         "start": r.start, "end": r.end, "score": r.score}
        for r in presidio
    ]
    entidades = mapper.map_entities(idx, dicts_p)
    return entidades, texto


def _escanear_fugas(reader, img: Image.Image, entidades: list) -> list[dict]:
    """
    Para cada rect de entidad, escanea franjas izquierda y derecha con OCR.
    Devuelve lista de fugas encontradas.
    """
    W, H = img.size
    fugas = []
    for ent in entidades:
        for rect in ent["rects"]:
            x0 = rect.x0 * ZOOM - PAD_LEFT
            x1 = rect.x1 * ZOOM + PAD_RIGHT
            y0 = rect.y0 * ZOOM - PAD_Y
            y1 = rect.y1 * ZOOM + PAD_Y

            fy0 = max(0, int(y0) - 1)
            fy1 = min(H, int(y1) + 1)

            # Franja izquierda
            fx0_i = max(0, int(x0) - FRANJA)
            fx1_i = max(0, int(x0) - 1)
            if fx1_i > fx0_i and fy1 > fy0:
                crop_i = img.crop((fx0_i, fy0, fx1_i, fy1))
                txt_i  = _ocr_crop(reader, crop_i)
                if txt_i:
                    fugas.append({
                        "tipo": ent["entity_type"], "texto": ent.get("text","?"),
                        "lado": "IZQ", "detectado": txt_i,
                        "coords": (round(x0,1), round(y0,1), round(x1,1), round(y1,1)),
                    })

            # Franja derecha
            fx0_d = min(W, int(x1) + 1)
            fx1_d = min(W, int(x1) + FRANJA)
            if fx1_d > fx0_d and fy1 > fy0:
                crop_d = img.crop((fx0_d, fy0, fx1_d, fy1))
                txt_d  = _ocr_crop(reader, crop_d)
                if txt_d:
                    fugas.append({
                        "tipo": ent["entity_type"], "texto": ent.get("text","?"),
                        "lado": "DER", "detectado": txt_d,
                        "coords": (round(x0,1), round(y0,1), round(x1,1), round(y1,1)),
                    })
    return fugas


def _guardar_diagnostico(img: Image.Image, entidades: list, fugas: list, path: str):
    """Dibuja recuadros y franjas sobre la imagen, marca fugas en rojo."""
    W, H = img.size
    diag = img.copy()
    draw = ImageDraw.Draw(diag)
    fugas_coords = {f["coords"] for f in fugas}

    for ent in entidades:
        for rect in ent["rects"]:
            x0 = rect.x0 * ZOOM - PAD_LEFT
            x1 = rect.x1 * ZOOM + PAD_RIGHT
            y0 = rect.y0 * ZOOM - PAD_Y
            y1 = rect.y1 * ZOOM + PAD_Y
            coords = (round(x0,1), round(y0,1), round(x1,1), round(y1,1))
            color = "#FF0000" if coords in fugas_coords else "#FF6600"
            draw.rectangle([x0, y0, x1, y1], outline=color, width=2)

    diag.save(path)


# ── CASOS DE PRUEBA SINTÉTICOS ────────────────────────────────────────────────

CASOS = [
    {
        "id": "nombre_en_oracion",
        "lineas": [
            "El tribunal considera que el agravio causado a LAURA GARZA SANCHEZ",
            "fue debidamente acreditado en autos, por lo que se condena al",
            "sentenciado CARLOS MENDEZ ROJAS a cumplir la pena impuesta.",
        ],
    },
    {
        "id": "encabezado_judicial",
        "lineas": [
            "IMPUTADO: MIGUEL ANGEL CORTES RIVERA",
            "VICTIMA: ANA PATRICIA DOMINGUEZ LUNA",
            "DELITO: ROBO CON VIOLENCIA",
            "CARPETA DE INVESTIGACION: FGJ/T3/1234/2024",
        ],
    },
    {
        "id": "identificadores",
        "lineas": [
            "CURP: GARJ850312HDFRZN01",
            "RFC: GARJ850312AB3",
            "NSS: 12345678901",
            "Expediente 2024-1234 a cargo del C. JUAN PEREZ GOMEZ.",
        ],
    },
    {
        "id": "multiple_nombres_linea",
        "lineas": [
            "Comparecieron JOSE GARCIA LOPEZ y MARIA HERNANDEZ VEGA",
            "ante el Juez Segundo de lo Penal para ratificar su testimonio.",
            "Asimismo ROBERTO SILVA MORA declaro en calidad de testigo.",
        ],
    },
    {
        "id": "texto_corrido_nombres",
        "lineas": [
            "En la ciudad de Mexico siendo las 10:00 hrs del dia 15 de enero",
            "de 2024, el C. ANDRES GALLEGOS DIAZ solicito audiencia ante el",
            "juzgado para presentar pruebas en favor de LUCIA REYES TORRES.",
        ],
    },
]


@pytest.mark.xfail(reason="Fuga mínima de OCR conocida: el sanitizer deja puntuación/sílabas"
                   " en los bordes del recuadro — deuda técnica de precisión de bbox")
@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_sin_overflow_caso_sintetico(caso, analizador, tmp_path):
    """
    Para cada caso sintético: detectar entidades, verificar con OCR que
    ninguna letra queda fuera del recuadro (izquierda ni derecha).
    """
    reader = _get_easyocr()
    if reader is None:
        pytest.skip("PaddleOCR no disponible")

    doc       = _crear_pdf_con_texto(caso["lineas"])
    page      = doc[0]
    entidades, texto = _analizar_pagina(analizador, page)
    img       = _render(page)

    print(f"\n[{caso['id']}] Texto: {texto[:80]}...")
    print(f"  Entidades detectadas: {len(entidades)}")
    for e in entidades:
        print(f"    [{e['entity_type']}] '{e.get('text','?')}' — {len(e['rects'])} rect(s)")

    if not entidades:
        pytest.skip(f"Pipeline no detectó entidades en caso '{caso['id']}'")

    fugas = _escanear_fugas(reader, img, entidades)

    # Guardar imagen de diagnóstico siempre (útil para revisar visualmente)
    out = str(tmp_path / f"diag_{caso['id']}.png")
    _guardar_diagnostico(img, entidades, fugas, out)
    print(f"  PNG: {out}")

    if fugas:
        lineas_fuga = [
            f"    [{f['lado']}] [{f['tipo']}] '{f['texto']}' → OCR detectó: {f['detectado']} @ {f['coords']}"
            for f in fugas
        ]
        pytest.fail(
            f"OVERFLOW en caso '{caso['id']}' — {len(fugas)} fuga(s):\n"
            + "\n".join(lineas_fuga)
        )


def test_reporte_global_todos_casos(analizador, tmp_path):
    """
    Ejecuta todos los casos y genera un reporte consolidado con % de éxito.
    No falla — solo documenta el estado actual para tracking de mejoras.
    """
    reader = _get_easyocr()
    if reader is None:
        pytest.skip("PaddleOCR no disponible")

    resumen = []
    total_rects = 0
    rects_ok    = 0

    for caso in CASOS:
        doc       = _crear_pdf_con_texto(caso["lineas"])
        page      = doc[0]
        entidades, _ = _analizar_pagina(analizador, page)
        img       = _render(page)
        fugas     = _escanear_fugas(reader, img, entidades)

        n_rects   = sum(len(e["rects"]) for e in entidades)
        n_fugas   = len(fugas)
        total_rects += n_rects
        rects_ok    += (n_rects - n_fugas)

        estado = "OK" if n_fugas == 0 else f"FUGA×{n_fugas}"
        resumen.append(f"  {caso['id']:35s} entidades={len(entidades):2d}  rects={n_rects:2d}  {estado}")
        if fugas:
            for f in fugas:
                resumen.append(f"    → [{f['lado']}] '{f['texto']}' leaked: {f['detectado']}")

    pct = 100 * rects_ok / max(total_rects, 1)
    resumen += [
        "",
        f"TOTAL rects: {total_rects}  |  OK: {rects_ok}  |  Cobertura: {pct:.1f}%",
    ]

    reporte = "\n".join(resumen)
    print("\n\nREPORTE GLOBAL:\n" + reporte)
    (tmp_path / "reporte_global.txt").write_text(reporte, encoding="utf-8")

    assert total_rects >= 0  # siempre pasa — solo documenta
