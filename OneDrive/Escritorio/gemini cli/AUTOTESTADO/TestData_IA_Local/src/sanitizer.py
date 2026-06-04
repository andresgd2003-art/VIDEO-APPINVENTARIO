import math
import pymupdf

_PADDING_LEFT  = 0.2   # Reducido para no rozar signos o palabras adyacentes
_PADDING_RIGHT = 0.2   # Reducido para no invadir signos de puntuacion
_PADDING_Y     = 1.0   # Ceñido vertical: evita rozar los renglones de arriba/abajo


def sanitize_page(page: pymupdf.Page, rects: list[pymupdf.Rect], fill_color=(0, 0, 0)):
    """
    Rasteriza la página completa, pinta los rects en negro sobre el pixmap
    y reemplaza el contenido de la página con la imagen resultante.

    Este enfoque preserva el layout (no toca el content stream de texto de forma
    selectiva) y es forensicamente seguro (el texto subyacente queda eliminado
    al reemplazar todo el contenido de la página por una imagen).

    Args:
        page: Página PDF a sanitizar (se modifica in-place).
        rects: Coordenadas en espacio PDF de las áreas a redactar.
        fill_color: Color de relleno RGB normalizado (default negro).
    """
    if not rects:
        return

    # — 1. Renderizar la página a alta resolución —
    zoom = 2.0  # 144 DPI; suficiente calidad sin archivo gigante
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    # — 2. Pintar los rects directamente en el pixmap —
    fill_bytes = bytes(int(c * 255) for c in fill_color)
    for rect in rects:
        irect = pymupdf.IRect(
            math.floor((rect.x0 - _PADDING_LEFT)  * zoom),
            math.floor((rect.y0 - _PADDING_Y)      * zoom),
            math.ceil( (rect.x1 + _PADDING_RIGHT)  * zoom),
            math.ceil( (rect.y1 + _PADDING_Y)      * zoom),
        )
        pix.set_rect(irect, fill_bytes)

    png_bytes = pix.tobytes("png")

    # — 3. Vaciar el content stream de la página y reemplazar con la imagen —
    doc = page.parent
    for xref in page.get_contents():
        doc.update_stream(xref, b"")  # vacía cada content stream de la página
    page.insert_image(page.rect, stream=png_bytes, keep_proportion=False)
