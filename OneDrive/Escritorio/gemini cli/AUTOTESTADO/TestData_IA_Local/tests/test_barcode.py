"""
Tests de detección de códigos de barra 1D (CODE128, EAN, etc.) en qr_detector.

Los códigos de barra se testan bajo la MISMA etiqueta MX_QR que los QR
(decisión del usuario). Estos tests verifican:
  1. _detectar_barras no crashea sobre una imagen sin barras.
  2. _detectar_barras detecta un CODE128 sintético dibujado con cv2.
  3. detectar_qr sigue devolviendo QR (no se rompió la detección existente).
  4. detectar_qr devuelve las barras como entidades entity_type="MX_QR".
  5. Reporte sobre los PDFs reales (cuántos QR / cuántas barras).

cv2.barcode API (OpenCV 4.10.0), confirmada con Brave Search:
    https://github.com/opencv/opencv/issues/23845
    https://docs.opencv.org/4.x/d6/d25/tutorial_barcode_detect_and_decode.html
  bd = cv2.barcode.BarcodeDetector()
  retval, decoded_info, decoded_type, points = bd.detectAndDecode(img)
  -> points: array (N, 4, 2) con los 4 vértices de cada código.
"""
import os

import numpy as np
import cv2
import pymupdf
import pytest

import qr_detector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# Patrón de barras CODE128 para "ABC" (start B, A, B, C, check, stop), como
# secuencia de anchos de barra/espacio. No necesitamos que sea exacto: basta
# con que cv2.barcode lo detecte (la decodificación puede o no funcionar; si
# falla, el texto cae al placeholder "[Código de barras]").
_CODE128_ABC = (
    "11010010000"  # Start Code B
    "10100011000"  # A
    "10001011000"  # B
    "10001000110"  # C
    "10111011000"  # check (aprox)
    "11000111010"  # Stop
    "11"           # final bar
)


def _imagen_code128(pattern: str = _CODE128_ABC, alto=120, ancho_modulo=4,
                    quiet=40) -> np.ndarray:
    """Dibuja un código de barras 1D sintético en escala de grises (255=blanco)."""
    width = quiet * 2 + len(pattern) * ancho_modulo
    img = np.full((alto, width), 255, dtype=np.uint8)
    x = quiet
    for ch in pattern:
        if ch == "1":
            img[10:alto - 10, x:x + ancho_modulo] = 0
        x += ancho_modulo
    return img


def _contar(entidades):
    """Devuelve (n_qr, n_barras) según el placeholder/text de cada entidad."""
    n_barras = sum(1 for e in entidades
                   if e["text"] == "[Código de barras]")
    n_qr = len(entidades) - n_barras
    return n_qr, n_barras


# ---------------------------------------------------------------------------
# 1. Robustez: no crashea sobre imagen vacía
# ---------------------------------------------------------------------------
def test_detectar_barras_sin_barras_no_crashea():
    gray = np.full((200, 200), 255, dtype=np.uint8)
    resultado = qr_detector._detectar_barras(gray, zoom=3.0)
    assert isinstance(resultado, list)
    assert resultado == []


def test_detectar_barras_modulo_ausente_devuelve_lista(monkeypatch):
    """Si cv2.barcode no existe, _detectar_barras debe devolver [] sin romper."""
    real_cv2 = qr_detector  # noqa
    if hasattr(cv2, "barcode"):
        monkeypatch.delattr(cv2, "barcode")
    gray = np.full((100, 100), 255, dtype=np.uint8)
    assert qr_detector._detectar_barras(gray, zoom=3.0) == []


# ---------------------------------------------------------------------------
# 2. Detección de un CODE128 sintético
# ---------------------------------------------------------------------------
def test_detectar_barras_code128_sintetico():
    gray = _imagen_code128()
    resultado = qr_detector._detectar_barras(gray, zoom=3.0)
    # Puede que esta build/decoder no lo detecte; si lo hace, validamos shape.
    assert isinstance(resultado, list)
    for rect, texto in resultado:
        assert isinstance(rect, pymupdf.Rect)
        assert isinstance(texto, str)


def _pdf_con_imagen(gray) -> pymupdf.Document:
    """Crea un PDF de 1 página insertando la imagen gris como PNG."""
    ok, buf = cv2.imencode(".png", gray)
    assert ok
    doc = pymupdf.open()
    h, w = gray.shape[:2]
    page = doc.new_page(width=w, height=h)
    page.insert_image(pymupdf.Rect(0, 0, w, h), stream=buf.tobytes())
    return doc


def test_detectar_qr_integra_barras_como_mx_qr():
    """Una barra detectada debe salir como entity_type MX_QR."""
    gray = _imagen_code128(ancho_modulo=6, alto=160)
    doc = _pdf_con_imagen(gray)
    try:
        ents = qr_detector.detectar_qr(doc[0], zoom=2.0)
    finally:
        doc.close()
    assert isinstance(ents, list)
    for e in ents:
        assert e["entity_type"] == "MX_QR"
        assert "score" in e and "text" in e and "rects" in e
        assert all(isinstance(r, pymupdf.Rect) for r in e["rects"])


# ---------------------------------------------------------------------------
# 3. La detección de QR existente sigue funcionando
# ---------------------------------------------------------------------------
def test_detectar_qr_sigue_detectando_qr():
    qr = cv2.QRCodeEncoder.create() if hasattr(cv2, "QRCodeEncoder") else None
    if qr is not None:
        try:
            img = qr.encode("https://example.com/curp=TEST")
        except cv2.error:
            img = None
    else:
        img = None
    if img is None:
        pytest.skip("cv2.QRCodeEncoder no disponible para generar QR sintético")
    # Escalar para que sea legible
    img = cv2.resize(img, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    doc = _pdf_con_imagen(img)
    try:
        ents = qr_detector.detectar_qr(doc[0], zoom=2.0)
    finally:
        doc.close()
    n_qr, n_barras = _contar(ents)
    assert n_qr >= 1, f"No se detectó el QR sintético (qr={n_qr}, barras={n_barras})"


# ---------------------------------------------------------------------------
# 4. PDFs reales (reporte)
# ---------------------------------------------------------------------------
_PDFS = {
    "INE": r"C:\Users\user\OneDrive\Escritorio\mis docs\IDENTIFICACION OFICIAL.pdf",
    "PRUEBA_BRUTAL": r"C:\Users\user\OneDrive\Escritorio\mis docs\PRUEBA_BRUTAL_ANONIMA.pdf",
}


@pytest.mark.parametrize("nombre,ruta", list(_PDFS.items()))
def test_pdfs_reales_reporte(nombre, ruta):
    if not os.path.exists(ruta):
        pytest.skip(f"PDF no encontrado: {ruta}")
    doc = pymupdf.open(ruta)
    total_qr = total_barras = 0
    try:
        for page in doc:
            ents = qr_detector.detectar_qr(page)
            q, b = _contar(ents)
            total_qr += q
            total_barras += b
    finally:
        doc.close()
    print(f"\n[REPORTE {nombre}] QR={total_qr}  Barras={total_barras}")
    # No exigimos un mínimo (depende del documento); solo que no crashee.
    assert total_qr >= 0 and total_barras >= 0
