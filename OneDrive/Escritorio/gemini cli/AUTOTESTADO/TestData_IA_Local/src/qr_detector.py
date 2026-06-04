"""
Detección automática de códigos QR en páginas PDF (nativas o escaneadas).

La detección es basada en imagen: se rasteriza la página con PyMuPDF y se busca
el QR con OpenCV. El mismo código funciona para documentos nativos y escaneados
(ambos se renderizan igual), a diferencia de la detección de texto que depende
del índice espacial.

Los QR en documentos oficiales (CSF, INE, actas) codifican datos personales del
titular (CURP, RFC, nombre, domicilio, URL de verificación), por lo que deben
testarse. Se devuelven entidades con el mismo shape que mapper.map_entities()
para integrarse sin fricción en el pipeline.
"""
import logging

import pymupdf

logger = logging.getLogger(__name__)

# Zoom de render para la detección. 3.0x ≈ 216 DPI: buen recall sin saturar RAM.
_ZOOM = 3.0
# Padding (pt PDF) alrededor del QR para cubrir su "quiet zone" (margen blanco).
_PADDING_PT = 2.0


def _pixmap_a_gris(pix):
    """Convierte un pymupdf.Pixmap a una imagen en escala de grises (numpy)."""
    import numpy as np
    import cv2

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:  # gris (n == 1)
        return img.reshape(pix.h, pix.w)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _puntos_a_rect(quad, zoom: float) -> pymupdf.Rect:
    """Convierte los 4 vértices (px) de un QR a un pymupdf.Rect en espacio PDF."""
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0 = min(xs) / zoom - _PADDING_PT
    y0 = min(ys) / zoom - _PADDING_PT
    x1 = max(xs) / zoom + _PADDING_PT
    y1 = max(ys) / zoom + _PADDING_PT
    return pymupdf.Rect(x0, y0, x1, y1)


def _detectar_cv2(gray, zoom: float):
    """Detección base con cv2.QRCodeDetector. Devuelve [(rect, texto), ...]."""
    import cv2

    det = cv2.QRCodeDetector()
    try:
        ok, infos, puntos, _ = det.detectAndDecodeMulti(gray)
    except cv2.error:
        return []
    if not ok or puntos is None:
        return []
    salida = []
    for i, quad in enumerate(puntos):
        rect = _puntos_a_rect(quad, zoom)
        texto = infos[i] if i < len(infos) else ""
        salida.append((rect, texto))
    return salida


def detectar_qr(page: pymupdf.Page, zoom: float = _ZOOM) -> list[dict]:
    """
    Detecta códigos QR en una página y los devuelve como entidades testables.

    Returns:
        Lista de dicts [{entity_type:"MX_QR", score, text, rects:[pymupdf.Rect]}].
        Coordenadas en espacio PDF. Lista vacía si no hay QR o falla la detección.
    """
    try:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        gray = _pixmap_a_gris(pix)
    except Exception:
        logger.exception("No se pudo rasterizar la página para detección de QR")
        return []

    detecciones = _detectar_cv2(gray, zoom)

    entidades: list[dict] = []
    for rect, texto in detecciones:
        # Descarta detecciones degeneradas (área nula)
        if rect.width <= 0 or rect.height <= 0:
            continue
        # Recorta la página por si el padding sacó el rect de los límites
        rect = rect & page.rect
        if rect.is_empty:
            continue
        texto_limpio = (texto or "").strip()
        entidades.append({
            "entity_type": "MX_QR",
            "score": 1.0,
            "text": texto_limpio[:80] if texto_limpio else "[Código QR]",
            "rects": [rect],
        })

    entidades = _deduplicar(entidades)
    return entidades


def _deduplicar(entidades: list[dict]) -> list[dict]:
    """Elimina QR cuyo rect coincide (mismo bbox redondeado)."""
    vistos = set()
    salida = []
    for e in entidades:
        r = e["rects"][0]
        clave = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(e)
    return salida
