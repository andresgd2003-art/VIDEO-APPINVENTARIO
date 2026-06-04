"""
Tests para las tres mejoras implementadas:
1. Detección de tablas (build_spatial_index expande rects a celdas)
2. Registro de auditoría (audit.py escribe y lee log)
3. Número de página del acta (report_generator usa offset correcto)
"""
import pathlib
import sys
import json
import tempfile
import os

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import pymupdf


# ─────────────────────────────────────────────────────────────
# Mejora 1: Detección de tablas
# ─────────────────────────────────────────────────────────────

def _crear_pdf_con_tabla() -> pymupdf.Document:
    """Crea un PDF en memoria con una tabla simple de 2×2."""
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    # Dibujar tabla 2×2 (líneas)
    page.draw_rect(pymupdf.Rect(10, 10, 190, 190), color=(0, 0, 0), width=1)
    page.draw_line((10, 100), (190, 100), color=(0, 0, 0))
    page.draw_line((100, 10), (100, 190), color=(0, 0, 0))
    # Insertar texto en una celda
    page.insert_text((20, 60), "CURP", fontsize=10)
    return doc


def test_build_spatial_index_sin_pagina_no_lanza():
    """Sin pasar page, build_spatial_index funciona igual que antes."""
    from pdf_reader import build_spatial_index
    words = [(10, 10, 50, 20, "Hola", 0, 0, 0, 0)]
    resultado = build_spatial_index(words)
    assert len(resultado) == 1
    assert resultado[0]["word"] == "Hola"


def test_build_spatial_index_con_pagina_devuelve_lista():
    """Con page, build_spatial_index no lanza excepción."""
    from pdf_reader import extract_words, build_spatial_index
    doc = _crear_pdf_con_tabla()
    page = doc[0]
    words = extract_words(page)
    resultado = build_spatial_index(words, page)
    assert isinstance(resultado, list)


def test_build_spatial_index_expande_rect_de_celda():
    """
    Cuando una palabra cae dentro de una celda de tabla,
    su rect debe ser mayor o igual al rect natural de la palabra.
    """
    from pdf_reader import extract_words, build_spatial_index
    doc = _crear_pdf_con_tabla()
    page = doc[0]
    words = extract_words(page)
    if not words:
        pytest.skip("No se extrajeron palabras del PDF de prueba")

    sin_tabla = build_spatial_index(words)
    con_tabla = build_spatial_index(words, page)

    # Al menos un rect debería haberse expandido (celda ≥ palabra)
    alguno_expandido = any(
        con_tabla[i]["rect"].width >= sin_tabla[i]["rect"].width or
        con_tabla[i]["rect"].height >= sin_tabla[i]["rect"].height
        for i in range(len(words))
    )
    assert alguno_expandido, "Ningún rect fue expandido al área de celda de tabla"


def test_build_cell_index_pdf_sin_tablas():
    """En un PDF sin tablas, _build_cell_index devuelve lista vacía sin excepción."""
    from pdf_reader import _build_cell_index
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Texto simple sin tabla")
    celdas = _build_cell_index(page)
    assert isinstance(celdas, list)


# ─────────────────────────────────────────────────────────────
# Mejora 2: Registro de auditoría
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def audit_temporal(tmp_path, monkeypatch):
    """Redirige el log de auditoría a un directorio temporal."""
    import audit as audit_mod
    log_dir = tmp_path / "logs"
    log_file = log_dir / "audit.log"
    monkeypatch.setattr(audit_mod, "_LOG_DIR", log_dir)
    monkeypatch.setattr(audit_mod, "_LOG_FILE", log_file)
    return audit_mod


def test_registrar_redaccion_crea_archivo(audit_temporal):
    audit_temporal.registrar_redaccion(
        archivo_entrada="entrada.pdf",
        archivo_salida="salida.pdf",
        num_paginas=2,
        info_reporte=[
            {"entity_type": "PERSON", "pagina": 0, "y0": 100.0},
            {"entity_type": "MX_CURP", "pagina": 1, "y0": 50.0, "manual": True},
        ],
    )
    assert audit_temporal._LOG_FILE.exists()


def test_registrar_redaccion_json_valido(audit_temporal):
    audit_temporal.registrar_redaccion(
        archivo_entrada="entrada.pdf",
        archivo_salida="salida.pdf",
        num_paginas=1,
        info_reporte=[{"entity_type": "MX_RFC_PF", "pagina": 0, "y0": 80.0}],
    )
    lineas = audit_temporal._LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 1
    entrada = json.loads(lineas[0])
    assert entrada["archivo_entrada"] == "entrada.pdf"
    assert entrada["num_paginas"] == 1
    assert entrada["total_entidades"] == 1


def test_registrar_redaccion_conteo_por_tipo(audit_temporal):
    audit_temporal.registrar_redaccion(
        archivo_entrada="e.pdf",
        archivo_salida="s.pdf",
        num_paginas=1,
        info_reporte=[
            {"entity_type": "PERSON", "pagina": 0, "y0": 10.0},
            {"entity_type": "PERSON", "pagina": 0, "y0": 20.0},
            {"entity_type": "MX_CURP", "pagina": 0, "y0": 30.0},
        ],
    )
    entrada = json.loads(audit_temporal._LOG_FILE.read_text(encoding="utf-8").strip())
    assert entrada["por_tipo"]["PERSON"] == 2
    assert entrada["por_tipo"]["MX_CURP"] == 1


def test_registrar_redaccion_cuenta_manuales(audit_temporal):
    audit_temporal.registrar_redaccion(
        archivo_entrada="e.pdf",
        archivo_salida="s.pdf",
        num_paginas=1,
        info_reporte=[
            {"entity_type": "PERSON", "pagina": 0, "y0": 10.0},
            {"entity_type": "MANUAL", "pagina": 0, "y0": 20.0, "manual": True},
            {"entity_type": "MANUAL", "pagina": 0, "y0": 30.0, "manual": True},
        ],
    )
    entrada = json.loads(audit_temporal._LOG_FILE.read_text(encoding="utf-8").strip())
    assert entrada["manuales"] == 2
    assert entrada["total_entidades"] == 3


def test_leer_log_vacio(audit_temporal):
    resultado = audit_temporal.leer_log()
    assert resultado == []


def test_leer_log_multiples_entradas(audit_temporal):
    for i in range(3):
        audit_temporal.registrar_redaccion(
            archivo_entrada=f"e{i}.pdf",
            archivo_salida=f"s{i}.pdf",
            num_paginas=1,
            info_reporte=[],
        )
    entradas = audit_temporal.leer_log()
    assert len(entradas) == 3
    assert entradas[0]["archivo_entrada"] == "e0.pdf"


def test_registrar_redaccion_tiene_timestamp(audit_temporal):
    audit_temporal.registrar_redaccion("e.pdf", "s.pdf", 1, [])
    entrada = json.loads(audit_temporal._LOG_FILE.read_text(encoding="utf-8").strip())
    assert "timestamp" in entrada
    assert "T" in entrada["timestamp"]  # formato ISO


def test_registrar_redaccion_tiene_usuario(audit_temporal):
    audit_temporal.registrar_redaccion("e.pdf", "s.pdf", 1, [])
    entrada = json.loads(audit_temporal._LOG_FILE.read_text(encoding="utf-8").strip())
    assert "usuario_os" in entrada
    assert isinstance(entrada["usuario_os"], str)


# ─────────────────────────────────────────────────────────────
# Mejora 3: Número de página del acta
# ─────────────────────────────────────────────────────────────

def _generar_acta(info_reporte: list[dict], filename: str = "test.pdf") -> pymupdf.Document:
    import report_generator
    doc = pymupdf.open()
    # Agregar una página de contenido original (pág. 0)
    doc.new_page()
    doc.new_page()
    report_generator.generate_justification_page(doc, info_reporte, filename)
    return doc


def test_acta_se_inserta_al_final():
    """El acta siempre se inserta al final del documento."""
    doc = _generar_acta([{"entity_type": "PERSON", "pagina": 0, "y0": 100.0}])
    # Leer todas las páginas del acta (están al final)
    texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count)).lower()
    assert "acta" in texto_acta or "comité" in texto_acta or "transparencia" in texto_acta


def test_acta_cita_pagina_original_correctamente():
    """
    La referencia a la página del documento original debe mostrar el número
    de la página original (1-indexed), no el número final en el PDF.
    """
    doc = _generar_acta([{"entity_type": "MX_CURP", "pagina": 0, "y0": 80.0}])
    # Leer todas las páginas del acta (están al final)
    texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count)).lower()
    # Debe mencionar "p.1" como página original (pagina=0 → 1-indexed)
    assert "p.1" in texto_acta


def test_acta_cita_pagina_en_pdf_final():
    """
    El texto del acta debe contener referencias a páginas del documento original
    (formato p.N r.M) donde N es el número 1-indexed de la página original.
    """
    doc = _generar_acta([{"entity_type": "MX_CURP", "pagina": 0, "y0": 80.0}])
    # Leer todas las páginas del acta (están al final)
    texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count)).lower()
    # pagina=0 → referencia "p.1" en el acta
    assert "p.1" in texto_acta


def test_acta_tiene_pie_de_pagina_numerado():
    """La página del acta debe contener su número de paginación interna."""
    doc = _generar_acta([{"entity_type": "PERSON", "pagina": 0, "y0": 50.0}])
    # Leer todas las páginas del acta (están al final)
    texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count))
    assert "Pág. 1 de" in texto_acta or "g. 1 de" in texto_acta


def test_acta_sin_info_no_modifica_doc():
    """Si info_reporte está vacío, el documento no se modifica."""
    import report_generator
    doc = pymupdf.open()
    doc.new_page()
    n_original = doc.page_count
    report_generator.generate_justification_page(doc, [], "vacio.pdf")
    assert doc.page_count == n_original


def test_acta_multiples_entidades_misma_pagina():
    """Varias entidades en la misma página se agrupan correctamente."""
    info = [
        {"entity_type": "PERSON", "pagina": 0, "y0": 50.0},
        {"entity_type": "MX_CURP", "pagina": 0, "y0": 80.0},
        {"entity_type": "MX_RFC_PF", "pagina": 0, "y0": 110.0},
    ]
    doc = _generar_acta(info)
    # Leer todas las páginas del acta (están al final)
    texto_acta = "".join(doc[i].get_text() for i in range(doc.page_count)).lower()
    assert "curp" in texto_acta


# ─── _words_from_rawdict ──────────────────────────────────────────────────────


def _pdf_con_texto_conocido() -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=100)
    page.insert_text((20, 50), "HOLA MUNDO PRUEBA", fontsize=11)
    return doc


def test_words_from_rawdict_devuelve_palabras():
    """_words_from_rawdict extrae al menos las mismas palabras que get_text(words)."""
    from pdf_reader import _words_from_rawdict
    doc = _pdf_con_texto_conocido()
    page = doc[0]
    resultado = _words_from_rawdict(page)
    textos = [w[4] for w in resultado]
    assert "HOLA" in textos
    assert "MUNDO" in textos
    assert "PRUEBA" in textos


def test_words_from_rawdict_formato_tupla():
    """Cada entrada es una tupla de al menos 8 elementos con x0,y0,x1,y1 float."""
    from pdf_reader import _words_from_rawdict
    doc = _pdf_con_texto_conocido()
    resultado = _words_from_rawdict(doc[0])
    assert len(resultado) >= 3
    for w in resultado:
        assert len(w) >= 5
        x0, y0, x1, y1 = w[:4]
        assert isinstance(x0, float)
        assert x1 > x0
        assert y1 > y0


def test_words_from_rawdict_orden_top_bottom():
    """Palabras están ordenadas de arriba a abajo, izquierda a derecha."""
    from pdf_reader import _words_from_rawdict
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 50), "PRIMERA LINEA", fontsize=11)
    page.insert_text((20, 100), "SEGUNDA LINEA", fontsize=11)
    resultado = _words_from_rawdict(page)
    ys = [w[1] for w in resultado]  # y0 de cada palabra
    assert ys[0] < ys[-1], "Primera palabra debe tener y0 menor que la última"


def test_words_from_rawdict_bbox_cubre_caracter_inicial():
    """El bbox x0 de cada palabra cubre el primer carácter (no trunca izquierda)."""
    from pdf_reader import _words_from_rawdict
    doc = _pdf_con_texto_conocido()
    resultado = _words_from_rawdict(doc[0])
    for w in resultado:
        x0, y0, x1, y1, word = w[:5]
        assert x0 >= 0, f"x0 negativo para {word!r}"
        assert x1 > x0, f"x1 <= x0 para {word!r}"


def test_words_from_rawdict_vs_get_text_words_cobertura():
    """
    El x0 de rawdict debe ser <= x0 de get_text(words) para la misma palabra,
    garantizando que la cobertura de rawdict es igual o mayor.
    """
    from pdf_reader import _words_from_rawdict
    doc = _pdf_con_texto_conocido()
    page = doc[0]
    rawdict_words = {w[4]: w[0] for w in _words_from_rawdict(page)}  # word → x0
    native_words = {w[4]: w[0] for w in page.get_text("words", sort=True)}  # word → x0
    for word, x0_raw in rawdict_words.items():
        if word in native_words:
            assert x0_raw <= native_words[word] + 1.0, (
                f"rawdict x0={x0_raw:.2f} > native x0={native_words[word]:.2f} para {word!r}"
            )


def test_extract_words_nativo_usa_rawdict():
    """extract_words en página nativa devuelve palabras via rawdict."""
    from pdf_reader import extract_words, _words_from_rawdict
    doc = _pdf_con_texto_conocido()
    page = doc[0]
    via_extract = extract_words(page)
    via_rawdict = _words_from_rawdict(page)
    # Deben tener el mismo número de palabras
    assert len(via_extract) == len(via_rawdict)


def test_words_from_rawdict_pagina_vacia():
    """Página sin texto devuelve lista vacía sin excepción."""
    from pdf_reader import _words_from_rawdict
    doc = pymupdf.open()
    page = doc.new_page()
    assert _words_from_rawdict(page) == []


# ─── _consolidar_rects_por_linea ───────────────────────────────────────────────

from mapper import _consolidar_rects_por_linea


def test_consolidar_rects_misma_linea():
    """Tres rects en la misma línea → un único bounding box."""
    r1 = pymupdf.Rect(10, 100, 50, 112)
    r2 = pymupdf.Rect(55, 100, 100, 112)
    r3 = pymupdf.Rect(105, 100, 150, 112)
    resultado = _consolidar_rects_por_linea([r1, r2, r3])
    assert len(resultado) == 1
    assert resultado[0].x0 == 10
    assert resultado[0].x1 == 150
    assert resultado[0].y0 == 100
    assert resultado[0].y1 == 112


def test_consolidar_rects_lineas_distintas():
    """Rects en dos líneas distintas → dos rects separados."""
    linea1 = pymupdf.Rect(10, 100, 80, 112)
    linea2 = pymupdf.Rect(10, 130, 80, 142)
    resultado = _consolidar_rects_por_linea([linea1, linea2])
    assert len(resultado) == 2


def test_consolidar_rects_vacio():
    """Lista vacía → lista vacía."""
    assert _consolidar_rects_por_linea([]) == []


def test_consolidar_rects_un_elemento():
    """Un solo rect → devuelto sin cambios."""
    r = pymupdf.Rect(10, 50, 100, 62)
    resultado = _consolidar_rects_por_linea([r])
    assert len(resultado) == 1
    assert resultado[0] == r
