import logging
import os
import re

import pymupdf

# PaddlePaddle 3.3 tiene un bug en oneDNN al inicializar el detector de PP-OCRv5.
# Debe deshabilitarse ANTES de importar paddleocr.
os.environ.setdefault("FLAGS_use_mkldnn", "0")

# ── Normalización OCR: corrige confusiones O↔0 e I↔1 en identificadores ──────

_RE_CURP_BROAD = re.compile(
    r'\b([A-Z][AEIOUX][A-Z]{2})([0-9O]{2})([0-9O]{2})([0-9O]{2})'
    r'([HM][A-Z]{5})([A-Z0-9O]{2})\b'
)
_RE_RFC_BROAD = re.compile(
    r'\b([A-ZÑ]{4})([0-9O]{2})([0-9O]{2})([0-9O]{2})([A-Z0-9]{3})\b'
)
# Serial alfanumérico: 2-5 letras puras seguidas de al menos un dígito real
# Capturamos todo el bloque (incluye posible I antes del primer dígito real)
_RE_SERIAL = re.compile(r'\b([A-Z]{2,5}[0-9IO][0-9IO]{2,11})\b')
# Concatenación "CODEy" al final de palabra (ej: WBD1112y)
_RE_CONCAT_Y = re.compile(r'\b([A-Z0-9]{4,})(y)\b')

# INE clave de elector: 18 chars. EasyOCR a veces la corta en 2 tokens
# (ej: "GLDZANO30721" + "1OH400" = "GLDZANO307211OH400"). Cuando dos palabras
# adyacentes concatenadas dan 18 chars y matchean el patrón INE tolerante, las
# fusionamos en una sola palabra con bbox combinado para que el regex de
# Presidio pueda detectarla.
_RE_INE_FULL = re.compile(r'^[A-Z]{6}[OI0-9]{8}[A-Z0-9OI][OI0-9]{3}$')


def _merge_split_ine_tokens(palabras: list[tuple]) -> list[tuple]:
    """
    Fusiona pares de tokens OCR adyacentes cuando juntos forman una clave de
    elector INE de 18 chars. Combina los bboxes para que el redactor cubra
    ambas partes.
    """
    if len(palabras) < 2:
        return palabras
    out: list[tuple] = []
    i = 0
    while i < len(palabras):
        if i + 1 < len(palabras):
            w1 = palabras[i]
            w2 = palabras[i + 1]
            combined = w1[4] + w2[4]
            if len(combined) == 18 and _RE_INE_FULL.match(combined):
                x0 = min(w1[0], w2[0])
                y0 = min(w1[1], w2[1])
                x1 = max(w1[2], w2[2])
                y1 = max(w1[3], w2[3])
                out.append((x0, y0, x1, y1, combined, w1[5], w1[6], w1[7]))
                i += 2
                continue
        out.append(palabras[i])
        i += 1
    return out


def _normalizar_texto_ocr(texto: str) -> str:
    """
    Corrige confusiones típicas de OCR scanner en texto de documentos:
    - O (letra) → 0 (cero) en posiciones numéricas de CURPs y RFCs
    - I (letra) → 1 (uno) en posiciones numéricas de seriales
    - Separa concatenaciones como "WBD1112y" → "WBD1112 y"
    """
    # 1. Separar concatenaciones "CODEy" → "CODE y"
    texto = _RE_CONCAT_Y.sub(r'\1 \2', texto)

    # 2. Normalizar CURP: fix O→0 en las 3 partes de fecha + dígito final
    def _fix_curp(m):
        nombre = m.group(1)                   # 4 letras nombre
        aa = m.group(2).replace('O', '0')     # año
        mm = m.group(3).replace('O', '0')     # mes
        dd = m.group(4).replace('O', '0')     # día
        sexo_estado = m.group(5)              # [HM] + 5 letras estado
        digverif = m.group(6).replace('O', '0').replace('I', '1')  # 2 chars finales
        return nombre + aa + mm + dd + sexo_estado + digverif

    texto = _RE_CURP_BROAD.sub(_fix_curp, texto)

    # 3. Normalizar RFC: fix O→0 en las 3 partes de fecha
    def _fix_rfc(m):
        nombre = m.group(1)
        aa = m.group(2).replace('O', '0')
        mm = m.group(3).replace('O', '0')
        dd = m.group(4).replace('O', '0')
        homo = m.group(5)
        return nombre + aa + mm + dd + homo

    texto = _RE_RFC_BROAD.sub(_fix_rfc, texto)

    # 4. Normalizar seriales alfanuméricos: I→1, O→0 desde el primer dígito real
    def _fix_serial(m):
        word = m.group(1)
        # Encontrar el primer dígito real (0-9) → eso marca el inicio de la zona numérica
        boundary = len(word)
        for j, c in enumerate(word):
            if c.isdigit():
                boundary = j
                break
        # Retroceder sobre I inmediatamente antes del primer dígito real (I = "1" mal leído)
        while boundary > 0 and word[boundary - 1] == 'I':
            boundary -= 1
        letras   = word[:boundary]
        numerico = word[boundary:].replace('I', '1').replace('O', '0')
        return letras + numerico

    texto = _RE_SERIAL.sub(_fix_serial, texto)

    return texto

logger = logging.getLogger(__name__)

# Flag 512: fuerza a PyMuPDF a calcular el bbox de cada carácter trazando los
# drawing commands del glifo (hull de tinta real) en lugar del advance origin point.
# Esto incluye el left side-bearing real, eliminando el desplazamiento horizontal
# que deja letras fuera de los recuadros de redacción.
_FLAGS_INK_BBOX = pymupdf.TEXT_PRESERVE_LIGATURES | 512

# Reduce la altura del bbox al trazo real del glifo, evitando que los recuadros
# de redacción invadan líneas adyacentes.
pymupdf.TOOLS.set_small_glyph_heights(True)

# Umbral: si la página tiene menos caracteres embebidos, se considera escaneada
_UMBRAL_CHARS_ESCANEADO = 10

# Zoom para renderizar antes de OCR: 2.0x = 144 DPI (PaddleOCR no necesita más resolución
# y es ~2.25x más rápido que 3.0x; el modelo PP-OCRv5 maneja bien fuentes pequeñas)
ZOOM_OCR = 2.0

# Umbral de confianza mínima por palabra (PaddleOCR devuelve 0.0–1.0)
_CONF_MINIMA_OCR = 0.30

# Importamos nuestro nuevo pipeline OCR
import sys
# Asegurarnos de que el módulo ocr_pipeline sea localizable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ocr_pipeline.preprocessing import process_pipeline
from ocr_pipeline.ocr_engine import extract_words_from_image

def open_pdf(path: str) -> pymupdf.Document:
    if not os.path.exists(path):
        raise FileNotFoundError(f"PDF not found: {path}")
    return pymupdf.open(path)


def extract_text(page: pymupdf.Page) -> str:
    return page.get_text("text")

def es_pagina_escaneada(page: pymupdf.Page) -> bool:
    """
    True si la página debe ser enviada al pipeline de OCR (es imagen/escaneada).
    Detecta si la página es principalmente una imagen incrustada, incluso si tiene texto
    (para cubrir casos de PDFs híbridos con malos OCRs invisibles).
    """
    # 1. Verificar si hay imágenes grandes que cubran la mayor parte de la página
    page_area = page.rect.width * page.rect.height
    img_info = page.get_image_info()
    
    if img_info and page_area > 0:
        max_img_ratio = 0
        for img in img_info:
            bbox = img.get('bbox')
            if bbox:
                area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                ratio = area / page_area
                if ratio > max_img_ratio:
                    max_img_ratio = ratio
        # Si una sola imagen cubre más del 80% de la página, es un documento escaneado
        if max_img_ratio > 0.8:
            logger.info(f"Página clasificada como ESCANEADA (Imagen cubre {max_img_ratio:.0%} del área)")
            return True

    # 2. Si no hay imágenes gigantes, verificamos la capa de texto
    texto = page.get_text("text")
    if len(texto.strip()) < _UMBRAL_CHARS_ESCANEADO:
        logger.info("Página clasificada como ESCANEADA (Capa de texto insuficiente)")
        return True
    
    return False


def clasificar_documento(doc: pymupdf.Document) -> dict:
    """
    Clasifica un documento PDF según el tipo de sus páginas.

    Returns:
        {
          "tipo": "nativo" | "escaneado" | "hibrido",
          "paginas_nativas": [list of page indices],
          "paginas_escaneadas": [list of page indices],
          "total_paginas": int,
        }
    """
    nativas = []
    escaneadas = []
    for i, page in enumerate(doc):
        if es_pagina_escaneada(page):
            escaneadas.append(i)
        else:
            nativas.append(i)
    total = len(nativas) + len(escaneadas)
    if escaneadas and nativas:
        tipo = "hibrido"
    elif escaneadas:
        tipo = "escaneado"
    else:
        tipo = "nativo"
    return {
        "tipo": tipo,
        "paginas_nativas": nativas,
        "paginas_escaneadas": escaneadas,
        "total_paginas": total,
    }


def _ocr_jpeg_embebidos(page: pymupdf.Page, doc: pymupdf.Document) -> list[tuple] | None:
    """
    Si la página contiene imágenes embebidas que NO cubren la página completa
    (ej. credenciales INE, pasaportes escaneados colocados en hoja carta), rasteriza
    CADA imagen en su región exacta de la página y le aplica OCR individual.

    Estrategia (validada contra docs oficiales de PyMuPDF):
      - Se usa page.get_image_rects(xref, transform=True) para obtener el rect EXACTO
        de cada colocación de la imagen en la página (maneja rotación/flip/repetición).
      - Se rasteriza SOLO esa región con page.get_pixmap(clip=img_rect), de modo que el
        pixmap ya está en el espacio de coordenadas de la página: el mapeo pixel→punto
        PDF es un simple offset + división por el zoom, inmune a rotación.
      - El pixmap se procesa para EasyOCR SIN binarizar (grayscale + denoise + CLAHE);
        EasyOCR (CRAFT+CRNN) necesita la textura — binarizar degrada el reconocimiento.

    Retorna lista de palabras si aplica, None si debe usarse el flujo estándar.
    """
    import numpy as np
    import cv2
    from ocr_pipeline.preprocessing import add_padding

    imgs = page.get_images(full=True)
    if not imgs:
        return None

    page_area = page.rect.width * page.rect.height
    img_info = page.get_image_info()

    # Cobertura máxima de una sola imagen → si >85% es escáner full-page (flujo estándar)
    max_ratio = 0.0
    for info in img_info:
        bbox = info.get("bbox")
        if bbox:
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            max_ratio = max(max_ratio, area / page_area if page_area else 0)
    if max_ratio > 0.85:
        return None

    logger.info("Página con %d imagen(es) embebida(s) (<85%% cobertura) — OCR por imagen individual", len(imgs))

    ZOOM_EMB = 4.0   # ~288 DPI: credenciales pequeñas necesitan alta resolución
    PADDING = 20
    _PAD_OCR = 1.0
    todas_palabras: list[tuple] = []
    bloque_global = 0

    for img_meta in imgs:
        xref = img_meta[0]
        # Rect exacto de cada colocación de la imagen en la página (con matriz)
        try:
            rects = page.get_image_rects(xref, transform=True)
        except Exception:
            rects = []
        if not rects:
            continue

        for img_rect, _matrix in rects:
            if img_rect.is_empty or img_rect.is_infinite:
                continue

            # Rasterizar SOLO la región de la imagen, ya en espacio de página.
            try:
                mat = pymupdf.Matrix(ZOOM_EMB, ZOOM_EMB)
                pix = page.get_pixmap(matrix=mat, clip=img_rect, alpha=False)
            except Exception:
                continue
            if pix.width < 8 or pix.height < 8:
                continue

            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).copy()
            if pix.n >= 3:
                img_bgr = cv2.cvtColor(img_np[:, :, :3], cv2.COLOR_RGB2BGR)
            else:
                img_bgr = cv2.cvtColor(img_np[:, :, 0], cv2.COLOR_GRAY2BGR)

            # Preprocesamiento para EasyOCR: grayscale + denoise + CLAHE (NO binarizar).
            # CLAHE realza el texto sobre el fondo institucional de color (verde/rosa INE)
            # preservando la textura que el detector CRAFT necesita.
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            img_denoised = cv2.fastNlMeansDenoising(img_gray, h=10, templateWindowSize=7, searchWindowSize=21)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_clahe = clahe.apply(img_denoised)
            img_final = add_padding(img_clahe, bordersize=PADDING)

            # width_ths=0.5 evita fragmentar tokens largos (CURP, clave de elector)
            palabras_raw = extract_words_from_image(img_final, lang='spa', min_conf=25, width_ths=0.5)

            # Mapeo pixel(pixmap, con padding) → punto PDF de la página.
            # El pixmap cubre EXACTAMENTE img_rect escalado por ZOOM_EMB, con origen
            # en (img_rect.x0, img_rect.y0). Solo hay que quitar el padding, dividir
            # por el zoom y sumar el offset del rect. Inmune a rotación/flip.
            #
            # EasyOCR devuelve cajas con holgura vertical (CRAFT detecta con margen).
            # Para credenciales con renglones muy juntos (INE), eso hace que el
            # tachado roce las líneas de arriba/abajo. Se acota la altura al 78%
            # centrado y se usa padding vertical mínimo (el horizontal se mantiene).
            _SHRINK_Y = 0.78        # conservar 78% de la altura, centrado en el glifo
            _PAD_OCR_Y = 0.0        # sin padding vertical extra en la ruta OCR
            for p in palabras_raw:
                bx0 = p['bbox'][0] - PADDING
                by0 = p['bbox'][1] - PADDING
                bx1 = p['bbox'][2] - PADDING
                by1 = p['bbox'][3] - PADDING

                # X: mapeo directo + padding horizontal
                px0 = max(img_rect.x0, img_rect.x0 + bx0 / ZOOM_EMB - _PAD_OCR)
                px1 = min(img_rect.x1, img_rect.x0 + bx1 / ZOOM_EMB + _PAD_OCR)

                # Y: mapear, luego encoger hacia el centro para ceñir al renglón
                ay0 = img_rect.y0 + by0 / ZOOM_EMB
                ay1 = img_rect.y0 + by1 / ZOOM_EMB
                cy = (ay0 + ay1) / 2.0
                half = (ay1 - ay0) / 2.0 * _SHRINK_Y
                py0 = max(img_rect.y0, cy - half - _PAD_OCR_Y)
                py1 = min(img_rect.y1, cy + half + _PAD_OCR_Y)

                if px1 <= px0 or py1 <= py0:
                    continue

                texto_raw = _normalizar_texto_ocr(p['text'])
                if texto_raw.strip():
                    todas_palabras.append((px0, py0, px1, py1, texto_raw.strip(), bloque_global, 0, p['word_no']))

            bloque_global += 1

    if todas_palabras:
        logger.info("OCR por imagen individual extrajo %d palabras", len(todas_palabras))
        return _merge_split_ine_tokens(todas_palabras)
    return None


def _ocr_extract_words(page: pymupdf.Page) -> list[tuple]:
    """
    Rasteriza la página y usa EasyOCR (deep learning) para extraer palabras.
    Devuelve tuplas compatibles con page.get_text("words"):
    (x0, y0, x1, y1, word, block_no, line_no, word_no)
    Las coordenadas están en puntos PDF reales.
    """
    import numpy as np
    import cv2
    from ocr_pipeline.preprocessing import add_padding

    # Intentar primero el modo imagen-individual (credenciales, IDs en hoja carta)
    try:
        doc = page.parent
        resultado_individual = _ocr_jpeg_embebidos(page, doc)
        if resultado_individual is not None:
            return resultado_individual
    except Exception as e:
        logger.warning("Fallo OCR por imagen individual, usando flujo estándar: %s", e)

    # Renderizamos DIRECTAMENTE a 300 DPI para preservar todo el detalle
    RENDER_DPI = 300
    factor = RENDER_DPI / 72.0  # ~4.1667
    mat = pymupdf.Matrix(factor, factor)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # Para EasyOCR: escala de grises + ligero denoising
    # NO binarizar ni invertir — EasyOCR necesita la textura original
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    img_denoised = cv2.fastNlMeansDenoising(img_gray, h=10, templateWindowSize=7, searchWindowSize=21)

    PADDING = 20
    img_final = add_padding(img_denoised, bordersize=PADDING)

    palabras_raw = extract_words_from_image(img_final, lang='spa', min_conf=30)

    palabras: list[tuple] = []
    for p in palabras_raw:
        x0_up = p['bbox'][0] - PADDING
        y0_up = p['bbox'][1] - PADDING
        x1_up = p['bbox'][2] - PADDING
        y1_up = p['bbox'][3] - PADDING

        _PAD_OCR = 1.0
        px0 = max(0, x0_up / factor - _PAD_OCR)
        py0 = max(0, y0_up / factor - _PAD_OCR)
        px1 = min(page.rect.width, x1_up / factor + _PAD_OCR)
        py1 = min(page.rect.height, y1_up / factor + _PAD_OCR)

        if px1 <= px0 or py1 <= py0:
            continue

        texto_raw = _normalizar_texto_ocr(p['text'])
        if texto_raw.strip():
            palabras.append((px0, py0, px1, py1, texto_raw.strip(), p['block_no'], 0, p['word_no']))

    palabras = _merge_split_ine_tokens(palabras)
    logger.info("EasyOCR extrajo %d palabras de página escaneada", len(palabras))
    return palabras


_PAGE_CHAR_RECTS_CACHE = {}
_OCR_PAGES: set[int] = set()  # set de id(page) que fueron procesadas con OCR


def _words_from_rawdict(page: pymupdf.Page) -> list[tuple]:
    """
    Extrae palabras usando bboxes de caracteres individuales (rawdict).

    get_text("words") usa advance-widths para el bbox de cada carácter, que puede
    no incluir el side-bearing real del glifo. rawdict devuelve el bbox de la tinta
    real, garantizando cobertura completa del primer y último carácter de cada word.
    """
    parejas = []
    blocks = page.get_text("rawdict", flags=_FLAGS_INK_BBOX)["blocks"]
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
                            parejas.append((
                                (x0, y0, x1, y1, word, b_no, l_no, w_no),
                                [pymupdf.Rect(c["bbox"]) for c in word_chars]
                            ))
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
                    parejas.append((
                        (x0, y0, x1, y1, word, b_no, l_no, w_no),
                        [pymupdf.Rect(c["bbox"]) for c in word_chars]
                    ))
    parejas.sort(key=lambda item: (round(item[0][1] / 5), item[0][0]))
    resultado = [item[0] for item in parejas]
    char_rects_list = [item[1] for item in parejas]
    _PAGE_CHAR_RECTS_CACHE[id(page)] = char_rects_list
    return resultado


def extract_words(page: pymupdf.Page) -> list[tuple]:
    """
    Extrae palabras con coordenadas de la página.
    Para PDFs nativos usa rawdict (bboxes de tinta real).
    En páginas escaneadas activa PaddleOCR como fallback automático.
    """
    if es_pagina_escaneada(page):
        _OCR_PAGES.add(id(page))
        return _ocr_extract_words(page)
    _OCR_PAGES.discard(id(page))
    words = _words_from_rawdict(page)
    if not words:
        # Fallback: get_text("words") si rawdict no devuelve nada
        words = page.get_text("words", sort=True)
    return words


def _build_cell_index(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """
    Devuelve lista de rects de celdas de tabla detectadas en la página.
    Usado para expandir bboxes de palabras al área completa de la celda.
    """
    celdas: list[pymupdf.Rect] = []
    try:
        tablas = page.find_tables()
        for tabla in tablas:
            for fila in tabla.cells:
                for celda in fila:
                    if celda is not None:
                        r = pymupdf.Rect(celda)
                        if not r.is_empty:
                            celdas.append(r)
    except Exception:
        pass
    return celdas


def build_spatial_index(words: list[tuple], page: pymupdf.Page | None = None) -> list[dict]:
    """
    Convierte word-tuples a dicts con posición de carácter y rect espacial.

    Si se pasa `page`, detecta celdas de tabla y expande el rect de cada palabra
    al área completa de la celda que la contiene.
    """
    celdas = _build_cell_index(page) if page is not None else []
    char_rects_list = _PAGE_CHAR_RECTS_CACHE.pop(id(page), None) if page is not None else None
    es_ocr = id(page) in _OCR_PAGES if page is not None else False

    index: list[dict] = []
    cursor = 0
    for i, word in enumerate(words):
        word_str: str = word[4]
        start_idx = cursor
        end_idx = cursor + len(word_str)
        word_rect = pymupdf.Rect(word[:4])

        rect_final = word_rect
        for celda in celdas:
            if celda.contains(word_rect.tl) or celda.contains(word_rect.br):
                rect_final = celda
                break

        char_rects = char_rects_list[i] if char_rects_list and i < len(char_rects_list) else None
        if char_rects is None and not es_ocr and len(word_str) > 0:
            # Interpolación proporcional de bboxes de caracteres SOLO para nativo sin cache
            char_width = (rect_final.x1 - rect_final.x0) / len(word_str)
            char_rects = []
            for j in range(len(word_str)):
                cx0 = rect_final.x0 + j * char_width
                cx1 = cx0 + char_width
                char_rects.append(pymupdf.Rect(cx0, rect_final.y0, cx1, rect_final.y1))

        # Para OCR: no generar char_rects interpolados — el mapper usará el rect
        # completo de la palabra, evitando recortes imprecisos.

        index.append({
            "word":      word_str,
            "start_idx": start_idx,
            "end_idx":   end_idx,
            "rect":      rect_final,
            "char_rects": char_rects,  # None para OCR
        })
        cursor = end_idx + 1
    return index
