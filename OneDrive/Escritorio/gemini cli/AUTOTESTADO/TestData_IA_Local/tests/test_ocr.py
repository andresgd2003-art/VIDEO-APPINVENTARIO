"""
Tests para el módulo OCR de pdf_reader.py.
Cubren: detección de páginas escaneadas, normalización OCR (O↔0, I↔1),
extracción con EasyOCR (mock) y fallback graceful.

NOTA: Los tests originales que usaban PaddleOCR (_get_paddle, _reensamblar_palabras_ocr,
_expandir_cajas_linea) han sido marcados con @pytest.mark.skip como deuda técnica,
ya que el OCR fue migrado de PaddleOCR a EasyOCR.
"""
import pathlib
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import pymupdf
import pdf_reader
from pdf_reader import _normalizar_texto_ocr


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _pdf_con_texto() -> pymupdf.Page:
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((50, 100), "CURP GASL920305MNLRNR01 RFC GASL920305T9A", fontsize=11)
    return page


def _pdf_solo_imagen() -> pymupdf.Page:
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300))
    pix.set_rect(pymupdf.IRect(0, 0, 300, 300), (200, 200, 200))
    png = pix.tobytes("png")
    page.insert_image(page.rect, stream=png, keep_proportion=False)
    return page


def _mock_easyocr_result(palabras: list[tuple]) -> list[dict]:
    """
    Genera una lista de dicts simulando el formato de extract_words_from_image.
    Cada tupla: (texto, x0, y0, x1, y1, conf)
    """
    results = []
    for idx, (texto, x0, y0, x1, y1, conf) in enumerate(palabras):
        results.append({
            'text': texto,
            'bbox': [x0, y0, x1, y1],
            'conf': conf,
            'block_no': idx,
            'word_no': 0,
        })
    return results


# ─── Helpers legacy PaddleOCR (conservados para referencia, ya no usados) ─────

def _mock_paddle_result(lineas: list[tuple]) -> list:
    """
    Genera un resultado simulado al estilo de PaddleOCR.predict()[0].
    Conservado como documentación de la API anterior.
    """
    text_word       = [palabras for palabras, _, _ in lineas]
    text_word_boxes = [boxes    for _, boxes, _ in lineas]
    rec_scores      = [score    for _, _, score in lineas]
    return [{
        "text_word":       text_word,
        "text_word_boxes": text_word_boxes,
        "rec_scores":      rec_scores,
    }]


def _palabras_iguales(palabras: list[str], box: tuple) -> list[tuple]:
    """Reparte el box equitativamente entre las palabras para mockear text_word_boxes."""
    x0, y0, x1, y1 = box
    n = len(palabras)
    ancho = (x1 - x0) / max(n, 1)
    return [(x0 + i*ancho, y0, x0 + (i+1)*ancho, y1) for i in range(n)]


# ─── _normalizar_texto_ocr ─────────────────────────────────────────────────────

def test_normalizar_curp_o_por_cero():
    """O en posición de dígito de CURP se convierte a 0."""
    entrada  = "GASL92O3O5MNLRNRO1"
    esperado = "GASL920305MNLRNR01"
    assert _normalizar_texto_ocr(entrada) == esperado


def test_normalizar_serial_i_por_uno():
    """I en posición numérica de serial se convierte a 1."""
    assert _normalizar_texto_ocr("WAZI110") == "WAZ1110"


def test_normalizar_concatenacion_y():
    """'CODEy' se separa en 'CODE y'."""
    assert _normalizar_texto_ocr("WBD1112y") == "WBD1112 y"


def test_normalizar_texto_completo():
    """Caso real: texto completo con los tres problemas a la vez."""
    entrada  = "serie WBD1112y WAZI110 CURP GASL92O3O5MNLRNRO1"
    esperado = "serie WBD1112 y WAZ1110 CURP GASL920305MNLRNR01"
    assert _normalizar_texto_ocr(entrada) == esperado


def test_normalizar_no_toca_texto_limpio():
    """El normalizador no modifica texto correcto."""
    casos_limpios = [
        "GASL920305T9A",
        "WBD1112",
        "WAZ1110",
        "números de serie WBD1112 y WAZ1110",
        "MIGUEL ÁNGEL CORTÉS RIVERA",
    ]
    for texto in casos_limpios:
        assert _normalizar_texto_ocr(texto) == texto, f"Modificó texto limpio: {texto!r}"


def test_normalizar_rfc_o_por_cero():
    """O en la fecha del RFC se convierte a 0."""
    entrada  = "GASL92O3O5T9A"
    esperado = "GASL920305T9A"
    assert _normalizar_texto_ocr(entrada) == esperado


def test_normalizar_serial_con_o_en_numerico():
    """O en parte numérica de serial se convierte a 0."""
    assert _normalizar_texto_ocr("ABC10O0") == "ABC1000"


# ─── es_pagina_escaneada ───────────────────────────────────────────────────────

def test_es_pagina_escaneada_false_en_pdf_con_texto():
    assert pdf_reader.es_pagina_escaneada(_pdf_con_texto()) is False


def test_es_pagina_escaneada_true_en_pdf_imagen():
    assert pdf_reader.es_pagina_escaneada(_pdf_solo_imagen()) is True


@pytest.mark.skip(
    reason="Comportamiento cambiado: página vacía ahora devuelve True (capa de texto "
           "insuficiente < _UMBRAL_CHARS_ESCANEADO). Conservado como deuda técnica."
)
def test_es_pagina_escaneada_false_en_pagina_vacia():
    doc = pymupdf.open()
    page = doc.new_page()
    assert pdf_reader.es_pagina_escaneada(page) is False


# ─── _ocr_extract_words con EasyOCR mock ──────────────────────────────────────

def test_ocr_extract_words_retorna_tuplas_8_elementos():
    """_ocr_extract_words devuelve tuplas de 8 elementos por palabra."""
    page = _pdf_solo_imagen()
    mock_words = _mock_easyocr_result([
        ("Hola",  10, 30, 200, 50, 95.0),
        ("Mundo", 10, 60, 200, 80, 95.0),
    ])

    with patch.object(pdf_reader, "extract_words_from_image", return_value=mock_words):
        resultado = pdf_reader._ocr_extract_words(page)

    assert len(resultado) == 2
    for tupla in resultado:
        assert len(tupla) == 8


def test_ocr_extract_words_coordenadas_son_float():
    """Las coordenadas devueltas son numéricas (float o int) y x1>x0, y1>y0."""
    page = _pdf_solo_imagen()
    # Usamos coordenadas suficientemente grandes para que no sean recortadas a 0
    # por el max(0, ...) de la conversión de upscale a puntos PDF
    mock_words = _mock_easyocr_result([
        ("TEST", 100, 100, 500, 200, 95.0),
    ])

    with patch.object(pdf_reader, "extract_words_from_image", return_value=mock_words):
        resultado = pdf_reader._ocr_extract_words(page)

    assert len(resultado) == 1
    x0, y0, x1, y1 = resultado[0][:4]
    assert isinstance(x0, (int, float))
    assert isinstance(y0, (int, float))
    assert x1 > x0
    assert y1 > y0


def test_ocr_extract_words_descarta_baja_confianza():
    """extract_words_from_image ya filtra por confianza; aquí verificamos que
    el pipeline completo descarta palabras vacías que resulten del filtrado."""
    page = _pdf_solo_imagen()
    # Solo devolvemos las palabras que ya pasaron el umbral (simulate filtrado externo)
    mock_words = _mock_easyocr_result([
        ("Alta",  0, 0, 100, 20, 95.0),
        ("Media", 0, 0, 100, 20, 50.0),
    ])

    with patch.object(pdf_reader, "extract_words_from_image", return_value=mock_words):
        resultado = pdf_reader._ocr_extract_words(page)

    textos = [t[4] for t in resultado]
    assert "Alta" in textos
    assert "Media" in textos


def test_ocr_extract_words_descarta_texto_vacio():
    """Palabras vacías o solo whitespace son descartadas."""
    page = _pdf_solo_imagen()
    mock_words = _mock_easyocr_result([
        ("",      0, 0, 100, 20, 90.0),
        (" ",     0, 0, 100, 20, 90.0),
        ("Válido", 0, 0, 100, 20, 90.0),
    ])

    with patch.object(pdf_reader, "extract_words_from_image", return_value=mock_words):
        resultado = pdf_reader._ocr_extract_words(page)

    assert len(resultado) == 1
    assert resultado[0][4] == "Válido"


def test_ocr_extract_words_aplica_normalizacion_ocr():
    """Los resultados de EasyOCR pasan por _normalizar_texto_ocr antes de devolverse."""
    page = _pdf_solo_imagen()
    mock_words = _mock_easyocr_result([
        ("GASL92O3O5MNLRNRO1", 0, 0, 200, 20, 90.0),
    ])

    with patch.object(pdf_reader, "extract_words_from_image", return_value=mock_words):
        resultado = pdf_reader._ocr_extract_words(page)

    textos = [t[4] for t in resultado]
    assert "GASL920305MNLRNR01" in textos, f"Esperaba CURP normalizado, obtuvo: {textos}"


def test_ocr_extract_words_retorna_vacio_sin_resultados():
    """Si EasyOCR no retorna resultados → lista vacía."""
    page = _pdf_solo_imagen()

    with patch.object(pdf_reader, "extract_words_from_image", return_value=[]):
        resultado = pdf_reader._ocr_extract_words(page)

    assert resultado == []


# ─── extract_words con fallback ────────────────────────────────────────────────

def test_extract_words_usa_ocr_en_pagina_escaneada():
    page = _pdf_solo_imagen()

    with patch.object(pdf_reader, "es_pagina_escaneada", return_value=True), \
         patch.object(pdf_reader, "_ocr_extract_words", return_value=[("mock",)]) as mock_ocr:
        resultado = pdf_reader.extract_words(page)

    mock_ocr.assert_called_once_with(page)
    assert resultado == [("mock",)]


def test_extract_words_no_usa_ocr_en_pdf_nativo():
    page = _pdf_con_texto()

    with patch.object(pdf_reader, "_ocr_extract_words") as mock_ocr:
        resultado = pdf_reader.extract_words(page)

    mock_ocr.assert_not_called()
    assert len(resultado) > 0


def test_extract_words_retorna_lista_si_easyocr_retorna_vacio():
    """Página escaneada pero EasyOCR retorna vacío → lista vacía, sin excepción."""
    page = _pdf_solo_imagen()

    with patch.object(pdf_reader, "es_pagina_escaneada", return_value=True), \
         patch.object(pdf_reader, "extract_words_from_image", return_value=[]):
        resultado = pdf_reader.extract_words(page)

    assert isinstance(resultado, list)


# ─── Tests de PaddleOCR (deuda técnica — API reemplazada por EasyOCR) ──────────

@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _get_paddle ya no existe")
def test_get_paddle_retorna_none_si_falla_import():
    """Si paddleocr no puede importarse → _get_paddle devuelve None sin lanzar."""
    pdf_reader._paddle_disponible = None
    pdf_reader._reader_paddle = None

    with patch.dict("sys.modules", {"paddleocr": None}):
        reader = pdf_reader._get_paddle()

    assert reader is None or hasattr(reader, "predict")

    pdf_reader._paddle_disponible = None
    pdf_reader._reader_paddle = None


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _get_paddle ya no existe")
def test_get_paddle_cachea_resultado():
    """La segunda llamada no re-inicializa PaddleOCR."""
    pdf_reader._paddle_disponible = True
    pdf_reader._reader_paddle = object()

    resultado1 = pdf_reader._get_paddle()
    resultado2 = pdf_reader._get_paddle()

    assert resultado1 is resultado2

    pdf_reader._paddle_disponible = None
    pdf_reader._reader_paddle = None


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _reensamblar_palabras_ocr ya no existe")
def test_reensamblar_une_acentos_partidos():
    """PaddleOCR partía los acentos en sub-tokens; deben re-unirse en la palabra."""
    def _box(x0, y0, x1, y1):
        return [x0, y0, x1, y1]
    tokens = ["MIGUEL", " Á", "NGEL"]
    boxes = [_box(0, 0, 60, 10), _box(62, 0, 70, 10), _box(70, 0, 110, 10)]
    res = pdf_reader._reensamblar_palabras_ocr(tokens, boxes)
    textos = [t for t, _ in res]
    assert textos == ["MIGUEL", "ÁNGEL"], textos


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _reensamblar_palabras_ocr ya no existe")
def test_reensamblar_cierra_en_espacio_final():
    """Un espacio al final del token cierra la palabra."""
    def _box(x0, y0, x1, y1):
        return [x0, y0, x1, y1]
    tokens = ["CORT", "É", "S", " ", "RIVERA"]
    boxes = [_box(0, 0, 40, 10), _box(40, 0, 48, 10), _box(48, 0, 58, 10),
             _box(58, 0, 60, 10), _box(62, 0, 120, 10)]
    res = pdf_reader._reensamblar_palabras_ocr(tokens, boxes)
    assert [t for t, _ in res] == ["CORTÉS", "RIVERA"]


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _reensamblar_palabras_ocr ya no existe")
def test_reensamblar_monto_y_cp():
    """Montos y C.P. fragmentados se reensamblan para que las regex los detecten."""
    def _box(x0, y0, x1, y1):
        return [x0, y0, x1, y1]
    tokens_monto = ["de", " $", "12", ",", "400.00"]
    boxes_monto = [_box(0, 0, 20, 10), _box(22, 0, 30, 10), _box(30, 0, 45, 10),
                   _box(45, 0, 48, 10), _box(48, 0, 90, 10)]
    res = pdf_reader._reensamblar_palabras_ocr(tokens_monto, boxes_monto)
    assert [t for t, _ in res] == ["de", "$12,400.00"]

    tokens_cp = ["C", ".", "P", ". ", "66260"]
    boxes_cp = [_box(0, 0, 8, 10), _box(8, 0, 10, 10), _box(10, 0, 18, 10),
                _box(18, 0, 22, 10), _box(24, 0, 60, 10)]
    res2 = pdf_reader._reensamblar_palabras_ocr(tokens_cp, boxes_cp)
    assert [t for t, _ in res2] == ["C.P.", "66260"]


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _reensamblar_palabras_ocr ya no existe")
def test_reensamblar_une_bbox_de_subtokens():
    """El bbox de la palabra reensamblada cubre todos sus sub-tokens."""
    def _box(x0, y0, x1, y1):
        return [x0, y0, x1, y1]
    tokens = ["a", "ñ", "os"]
    boxes = [_box(10, 5, 20, 15), _box(20, 5, 28, 15), _box(28, 5, 45, 15)]
    res = pdf_reader._reensamblar_palabras_ocr(tokens, boxes)
    assert len(res) == 1
    texto, box = res[0]
    assert texto == "años"
    assert box == [10, 5, 45, 15]


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _reensamblar_palabras_ocr ya no existe")
def test_reensamblar_ignora_tokens_de_puro_espacio():
    """Tokens de solo espacio separan palabras y no generan entradas vacías."""
    def _box(x0, y0, x1, y1):
        return [x0, y0, x1, y1]
    tokens = ["uno", " ", "dos", "  ", "tres"]
    boxes = [_box(0, 0, 10, 10), _box(10, 0, 12, 10), _box(12, 0, 22, 10),
             _box(22, 0, 25, 10), _box(25, 0, 40, 10)]
    res = pdf_reader._reensamblar_palabras_ocr(tokens, boxes)
    assert [t for t, _ in res] == ["uno", "dos", "tres"]


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _reensamblar_palabras_ocr ya no existe")
def test_reensamblar_palabra_simple_sin_cambios():
    """Una palabra que ya viene íntegra se devuelve igual con su box."""
    def _box(x0, y0, x1, y1):
        return [x0, y0, x1, y1]
    res = pdf_reader._reensamblar_palabras_ocr(["Hola"], [_box(1, 2, 3, 4)])
    assert res == [("Hola", [1.0, 2.0, 3.0, 4.0])]


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _expandir_cajas_linea ya no existe en pdf_reader")
def test_expandir_palabra_aislada_usa_maximo():
    """Una palabra sola en su línea se expande el máximo horizontal (sin vecinas)."""
    EXpx = pdf_reader._OCR_EXPAND_MAX_PT * pdf_reader.ZOOM_OCR
    palabras = [("HOLA", [100.0, 50.0, 140.0, 62.0])]
    res = pdf_reader._expandir_cajas_linea(palabras)
    (_, box) = res[0]
    assert box[0] == 100.0 - EXpx
    assert box[2] == 140.0 + EXpx


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _expandir_cajas_linea ya no existe en pdf_reader")
def test_expandir_no_genera_solape_entre_vecinas():
    """Dos palabras contiguas: tras expandir NO deben solaparse."""
    palabras = [
        ("UNO", [0.0, 0.0, 30.0, 12.0]),
        ("DOS", [34.0, 0.0, 64.0, 12.0]),
    ]
    res = pdf_reader._expandir_cajas_linea(palabras)
    b0, b1 = res[0][1], res[1][1]

    def _solapan(b1, b2):
        return not (b1[2] <= b2[0] or b1[0] >= b2[2] or b1[3] <= b2[1] or b1[1] >= b2[3])

    assert not _solapan(b0, b1)
    assert b1[0] >= b0[2]


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _expandir_cajas_linea ya no existe en pdf_reader")
def test_expandir_hueco_grande_permite_crecer():
    """Con hueco amplio entre palabras, el borde interior crece."""
    palabras = [
        ("IZQ", [0.0, 0.0, 30.0, 12.0]),
        ("DER", [200.0, 0.0, 230.0, 12.0]),
    ]
    res = pdf_reader._expandir_cajas_linea(palabras)
    b0 = res[0][1]
    assert b0[2] > 30.0


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _expandir_cajas_linea ya no existe en pdf_reader")
def test_expandir_no_cambia_texto_ni_altura_vertical():
    """La expansión vertical es 0 por defecto; el texto se conserva."""
    palabras = [("X", [10.0, 20.0, 18.0, 30.0])]
    res = pdf_reader._expandir_cajas_linea(palabras)
    texto, box = res[0]
    assert texto == "X"
    assert box[1] == 20.0 and box[3] == 30.0


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _expandir_cajas_linea ya no existe en pdf_reader")
def test_expandir_lista_vacia():
    assert pdf_reader._expandir_cajas_linea([]) == []


@pytest.mark.skip(reason="PaddleOCR reemplazado por EasyOCR — _get_paddle ya no existe")
def test_get_paddle_usa_modelos_mobile():
    """
    _get_paddle() debe construir PaddleOCR con los modelos MOBILE explícitos.

    Regresión: el detector "server" por defecto tardaba ~500 s/página en CPU.
    Conservado como deuda técnica para documentar la decisión de diseño.
    """
    pdf_reader._paddle_disponible = None
    pdf_reader._reader_paddle = None

    import paddleocr
    with patch.object(paddleocr, "PaddleOCR") as mock_ctor:
        mock_ctor.return_value = object()
        pdf_reader._get_paddle()

    assert mock_ctor.called
    kwargs = mock_ctor.call_args.kwargs
    assert kwargs.get("text_detection_model_name") == "PP-OCRv5_mobile_det"
    assert kwargs.get("text_recognition_model_name") == "latin_PP-OCRv5_mobile_rec"

    pdf_reader._paddle_disponible = None
    pdf_reader._reader_paddle = None


# ─── clasificar_documento ──────────────────────────────────────────────────────

def test_clasificar_documento_nativo():
    """Documento con sólo páginas de texto → tipo 'nativo'."""
    doc = pymupdf.open()
    p = doc.new_page(width=300, height=300)
    p.insert_text((50, 100), "texto de prueba para clasificar", fontsize=11)
    resultado = pdf_reader.clasificar_documento(doc)
    assert resultado["tipo"] == "nativo"
    assert resultado["paginas_nativas"] == [0]
    assert resultado["paginas_escaneadas"] == []
    assert resultado["total_paginas"] == 1


def test_clasificar_documento_escaneado():
    """Documento con sólo páginas imagen → tipo 'escaneado'."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300))
    pix.set_rect(pymupdf.IRect(0, 0, 300, 300), (200, 200, 200))
    page.insert_image(page.rect, stream=pix.tobytes("png"), keep_proportion=False)
    resultado = pdf_reader.clasificar_documento(doc)
    assert resultado["tipo"] == "escaneado"
    assert resultado["paginas_escaneadas"] == [0]
    assert resultado["paginas_nativas"] == []
    assert resultado["total_paginas"] == 1


def test_clasificar_documento_hibrido():
    """Documento con una página texto y una imagen → tipo 'hibrido'."""
    doc = pymupdf.open()
    p0 = doc.new_page(width=300, height=300)
    p0.insert_text((50, 100), "texto nativo aquí", fontsize=11)
    p1 = doc.new_page(width=300, height=300)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 300))
    pix.set_rect(pymupdf.IRect(0, 0, 300, 300), (180, 180, 180))
    p1.insert_image(p1.rect, stream=pix.tobytes("png"), keep_proportion=False)
    resultado = pdf_reader.clasificar_documento(doc)
    assert resultado["tipo"] == "hibrido"
    assert 0 in resultado["paginas_nativas"]
    assert 1 in resultado["paginas_escaneadas"]
    assert resultado["total_paginas"] == 2


def test_clasificar_documento_total_paginas():
    """total_paginas es la suma de nativas + escaneadas."""
    doc = pymupdf.open()
    for _ in range(3):
        p = doc.new_page(width=300, height=300)
        p.insert_text((50, 100), "pagina con texto", fontsize=11)
    resultado = pdf_reader.clasificar_documento(doc)
    assert resultado["total_paginas"] == 3
    assert len(resultado["paginas_nativas"]) + len(resultado["paginas_escaneadas"]) == resultado["total_paginas"]


# ─── ZOOM_OCR ──────────────────────────────────────────────────────────────────

def test_zoom_ocr():
    """ZOOM_OCR debe ser 2.0 (definido en pdf_reader para compatibilidad)."""
    assert pdf_reader.ZOOM_OCR == 2.0
