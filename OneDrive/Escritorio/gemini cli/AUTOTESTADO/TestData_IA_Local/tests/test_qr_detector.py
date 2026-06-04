# -*- coding: utf-8 -*-
"""Tests de detección automática de códigos QR (qr_detector.py)."""
import os
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
import qr_detector

CSF = r"C:\Users\user\OneDrive\Escritorio\mis docs\csf.pdf"


def _make_qr_pdf(data="CURP:GADA030721HDGLZNA8 NOMBRE:ANDRES"):
    """Crea un PDF de 1 página con un QR incrustado (vía qrcode si está, si no cv2)."""
    import numpy as np
    import cv2

    # Genera la matriz del QR con OpenCV (encoder disponible en 4.x)
    try:
        enc = cv2.QRCodeEncoder.create()
        qr_img = enc.encode(data)  # imagen binaria pequeña
    except Exception:
        return None
    # Escala a un tamaño cómodo y la pega en una página A4 blanca
    qr_img = cv2.resize(qr_img, (300, 300), interpolation=cv2.INTER_NEAREST)
    png = cv2.imencode(".png", qr_img)[1].tobytes()

    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(pymupdf.Rect(150, 200, 450, 500), stream=png)
    return doc


def test_pagina_sin_qr_devuelve_vacio():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Documento sin codigo QR alguno.")
    assert qr_detector.detectar_qr(page) == []


def test_detecta_qr_sintetico_con_coordenadas_validas():
    doc = _make_qr_pdf()
    if doc is None:
        pytest.skip("cv2.QRCodeEncoder no disponible en este build de OpenCV")
    page = doc[0]
    ents = qr_detector.detectar_qr(page)
    assert len(ents) >= 1, "No se detectó el QR sintético"
    e = ents[0]
    assert e["entity_type"] == "MX_QR"
    assert e["rects"], "La entidad QR no trae rects"
    r = e["rects"][0]
    # Coordenadas en espacio PDF (no en píxeles del zoom) y dentro de la página
    assert 0 <= r.x0 < r.x1 <= page.rect.width + 1
    assert 0 <= r.y0 < r.y1 <= page.rect.height + 1
    # El QR se insertó alrededor de (150,200)-(450,500): el rect debe caer cerca
    assert r.x0 > 100 and r.y0 > 150


@pytest.mark.skipif(not os.path.exists(CSF), reason="csf.pdf no disponible")
def test_csf_detecta_qr_en_ambas_paginas():
    doc = pymupdf.open(CSF)
    ents_p0 = qr_detector.detectar_qr(doc[0])
    assert len(ents_p0) >= 1, "No se detectó QR en la página 0 del CSF"
    # El QR de la pág. 0 decodifica la URL de verificación del SAT
    textos = " ".join(e["text"] for e in ents_p0).lower()
    assert "sat.gob.mx" in textos or "[código qr]" in textos
    if doc.page_count > 1:
        ents_p1 = qr_detector.detectar_qr(doc[1])
        assert len(ents_p1) >= 1, "No se detectó QR en la página 1 del CSF"


@pytest.mark.skipif(not os.path.exists(CSF), reason="csf.pdf no disponible")
def test_redaccion_tapa_el_qr():
    """Tras redactar el rect del QR, un segundo escaneo ya no lo detecta (prueba de fuga)."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
    import sanitizer

    doc = pymupdf.open(CSF)
    page = doc[0]
    ents = qr_detector.detectar_qr(page)
    assert ents, "Precondición: debe haber un QR en la pág. 0"
    rects = [r for e in ents for r in e["rects"]]
    sanitizer.sanitize_page(page, rects)
    # Re-escanear: el QR ya no debe detectarse
    ents_post = qr_detector.detectar_qr(page)
    assert ents_post == [], f"El QR sigue siendo detectable tras redactar: {ents_post}"
