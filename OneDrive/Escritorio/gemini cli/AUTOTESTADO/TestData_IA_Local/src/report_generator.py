import pymupdf
import datetime
from legal_mapper import get_legal_justification, get_active_estado, load_state_pack

# CSS del acta (compartida por todas las páginas para que el estilo y los anchos
# de columna sean idénticos al paginar manualmente y repetir el encabezado).
_ACTA_CSS = """
        body {
            font-family: 'Times New Roman', Georgia, 'DejaVu Serif', serif;
            font-size: 8pt;
            line-height: 1.3;
            color: #1a1a1a;
            margin: 30px 35px 25px 35px;
        }
        .header {
            text-align: center;
            margin-bottom: 12px;
            padding-bottom: 6px;
            border-bottom: 1.5px solid #1a1a1a;
        }
        .header h1 {
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 13pt;
            font-weight: bold;
            margin: 0 0 3px 0;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: #000000;
        }
        .header h2 {
            font-family: 'Times New Roman', 'Georgia', serif;
            font-size: 9pt;
            font-weight: normal;
            margin: 0;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: #444444;
        }
        .meta-table {
            width: 100%;
            margin: 8px 0;
            border-collapse: collapse;
        }
        .meta-table td {
            padding: 2px 6px;
            font-size: 8pt;
            vertical-align: top;
            border: none;
        }
        .meta-label {
            font-weight: bold;
            width: 150px;
            color: #1a1a1a;
        }
        .meta-value {
            color: #333333;
        }
        h3 {
            font-size: 8.5pt;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #000000;
            margin: 12px 0 4px 0;
            padding-bottom: 2px;
            border-bottom: 0.5px solid #333333;
        }
        .fundamento {
            font-size: 8pt;
            text-align: justify;
            margin: 4px 0 8px 0;
            text-indent: 20px;
        }
        .tabla-clasif {
            width: 100%;
            border-collapse: collapse;
            margin: 4px 0 10px 0;
            font-size: 7pt;
        }
        .tabla-clasif th {
            background-color: #2c2c2c;
            color: #ffffff;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            padding: 3px 3px;
            text-align: left;
            font-size: 6.5pt;
            border: 0.5px solid #1a1a1a;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        .tabla-clasif td {
            padding: 2px 3px;
            border: 0.5px solid #999999;
            vertical-align: top;
            color: #1a1a1a;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        .tabla-clasif tr {
            page-break-inside: avoid;
            break-inside: avoid;
        }
        .tabla-clasif tr:nth-child(even) td {
            background-color: #f5f5f5;
        }
        .col-num { width: 18px; text-align: center; }
        .col-ubic { width: 55px; }
        .col-desc { width: 120px; font-weight: bold; }
        .col-fund { width: 150px; font-size: 6.5pt; }
        .col-motiv { width: 133px; font-size: 6.5pt; font-style: italic; }
        .fund-label {
            font-weight: bold;
            color: #000000;
            text-transform: uppercase;
            font-size: 6pt;
            letter-spacing: 0.2px;
        }
        .fund-sep {
            display: block;
            margin-top: 3px;
        }
        .resolutivo {
            font-size: 8pt;
            text-align: justify;
            margin: 4px 0;
            text-indent: 20px;
        }
        .firma-container {
            margin-top: 35px;
            text-align: center;
        }
        .firma-linea {
            display: inline-block;
            width: 240px;
            border-top: 0.5px solid #1a1a1a;
            padding-top: 4px;
            font-size: 7.5pt;
            font-weight: bold;
            color: #1a1a1a;
        }
        .firma-cargo {
            font-size: 7pt;
            font-weight: normal;
            color: #555555;
            margin-top: 1px;
        }
        .nota {
            margin-top: 15px;
            padding-top: 4px;
            border-top: 0.5px solid #cccccc;
            font-size: 6.5pt;
            color: #777777;
            font-style: italic;
        }
        .thead-tr th { }
"""

_ACTA_THEAD = """
            <thead>
                <tr>
                    <th class="col-num">No.</th>
                    <th class="col-desc">Dato Testado</th>
                    <th class="col-ubic">Ubicaciones</th>
                    <th class="col-fund">Fundamento Legal</th>
                    <th class="col-motiv">Motivaci&oacute;n / Prueba de Da&ntilde;o</th>
                </tr>
            </thead>
"""

def _acta_tabla(filas_html: str) -> str:
    """Tabla de clasificación con encabezado + las filas indicadas."""
    return (
        '<table class="tabla-clasif">' + _ACTA_THEAD +
        "<tbody>" + filas_html + "</tbody></table>"
    )

def _estimar_renglon(y0: float) -> int:
    """Estima el renglón basado en la coordenada Y. Asume tamaño de renglón de 12-15 pts."""
    return max(1, int(y0 / 15))

def _formato_fundamento(legal_info: dict) -> str:
    """Devuelve el HTML de la celda de fundamento legal.

    Si hay capa estatal, separa el marco general y el estatal en líneas
    etiquetadas para que se lea organizado en vez de un bloque corrido.
    """
    federal = legal_info.get("fundamento_federal")
    estatal = legal_info.get("fundamento_estatal")
    if federal and estatal:
        return (
            f'<span class="fund-label">Marco general:</span> {federal}'
            f'<span class="fund-sep"></span>'
            f'<span class="fund-label">Marco estatal:</span> {estatal}'
        )
    return legal_info.get("fundamento", "")

def generate_justification_page(doc: pymupdf.Document, info_reporte: list[dict], filename: str, estado=None) -> None:
    """
    Inserta una o más páginas al inicio del documento PDF que sirven como
    Acta del Comité de Transparencia (Cuadro de Clasificación), justificando
    legalmente las entidades testadas.

    Estilo: Institucional sobrio — tipografía serif, monocromático, sin colores.
    """
    if not info_reporte:
        return

    if estado is None:
        estado = get_active_estado()

    # Agrupar por TIPO DE DATO: una fila por entity_type con todas las ubicaciones
    from collections import OrderedDict
    tipos: dict[str, dict] = OrderedDict()
    for item in info_reporte:
        et = item["entity_type"]
        custom_l = item.get("custom_label")
        custom_leg = item.get("custom_legal")
        custom_mot = item.get("custom_motivacion")

        # Agrupar por entity_type, o por custom_label si es CUSTOM
        key = f"CUSTOM_{custom_l}" if et == "CUSTOM" else et

        renglon = _estimar_renglon(item["y0"])
        pag = item["pagina"] + 1
        fue_manual = bool(item.get("manual", False))
        if key not in tipos:
            tipos[key] = {
                "entity_type": et,
                "custom_label": custom_l,
                "custom_legal": custom_leg,
                "custom_motivacion": custom_mot,
                "ubicaciones": [],
                "manual": False
            }
        tipos[key]["ubicaciones"].append(f"p.{pag} r.{renglon}")
        tipos[key]["manual"] = tipos[key]["manual"] or fue_manual

    filas = []
    num = 0
    for key, info in tipos.items():
        num += 1
        entity_type = info["entity_type"]
        legal_info = get_legal_justification(entity_type, info["custom_label"], info["custom_legal"], info["custom_motivacion"], estado=estado)
        # Deduplicar y ordenar ubicaciones
        ubics = sorted(set(info["ubicaciones"]))
        ubic_str = ", ".join(ubics)
        origen = " <i>(manual)</i>" if info["manual"] else ""

        filas.append(f"""
        <tr>
            <td class="col-num">{num}</td>
            <td class="col-desc">{legal_info['descripcion']}{origen}</td>
            <td class="col-ubic">{ubic_str}</td>
            <td class="col-fund">{_formato_fundamento(legal_info)}</td>
            <td class="col-motiv">{legal_info['motivacion']}</td>
        </tr>
        """)

    fecha = datetime.datetime.now().strftime('%d de %B de %Y').replace(
        'January', 'enero').replace('February', 'febrero').replace('March', 'marzo'
        ).replace('April', 'abril').replace('May', 'mayo').replace('June', 'junio'
        ).replace('July', 'julio').replace('August', 'agosto').replace('September', 'septiembre'
        ).replace('October', 'octubre').replace('November', 'noviembre').replace('December', 'diciembre')

    # Marco legal aplicable: federal + (si hay) pack estatal
    import html as _html_mod
    marco_legal = "Ley General (LGTAIP / LGPDPPSO)"
    if estado:
        pack = load_state_pack(estado)
        if pack and pack.get("ley", {}).get("nombre"):
            marco_legal += " + " + pack["ley"]["nombre"]
    marco_legal = _html_mod.escape(marco_legal)

    # ── Tamaño de hoja (igual al documento original) ──────────────────────────
    if len(doc) > 0:
        w = doc[0].rect.width
        h = doc[0].rect.height
    else:
        w, h = 612, 792  # Carta por defecto

    # ── Secciones del acta como bloques independientes ────────────────────────
    preambulo = f"""
        <div class="header">
            <h1>Acta del Comit&eacute; de Transparencia</h1>
            <h2>Resoluci&oacute;n de Clasificaci&oacute;n &mdash; Versi&oacute;n P&uacute;blica</h2>
        </div>
        <table class="meta-table">
            <tr><td class="meta-label">Fecha de elaboraci&oacute;n:</td><td class="meta-value">{fecha}</td></tr>
            <tr><td class="meta-label">Documento original:</td><td class="meta-value"><i>{filename}</i></td></tr>
            <tr><td class="meta-label">&Aacute;rea clasificadora:</td><td class="meta-value">Generado por ANONIMA &mdash; Sistema de Testado Automatizado</td></tr>
            <tr><td class="meta-label">Total de datos testados:</td><td class="meta-value">{num}</td></tr>
            <tr><td class="meta-label">Marco legal aplicable:</td><td class="meta-value">{marco_legal}</td></tr>
        </table>
        <h3>I. Fundamentaci&oacute;n y Motivaci&oacute;n Legal</h3>
        <p class="fundamento">
            Con fundamento en los art&iacute;culos 107, 110, 116 y 120 de la
            <b>Ley General de Transparencia y Acceso a la Informaci&oacute;n P&uacute;blica</b>
            (LGTAIP), as&iacute; como en el Art&iacute;culo 3 de la
            <b>Ley General de Protecci&oacute;n de Datos Personales en Posesi&oacute;n
            de Sujetos Obligados</b> (LGPDPPSO), se aprueba la clasificaci&oacute;n
            de la informaci&oacute;n testada en el documento que se adjunta, conforme
            al cuadro de clasificaci&oacute;n que a continuaci&oacute;n se detalla.
        </p>
        <h3>II. Cuadro de Clasificaci&oacute;n</h3>
    """

    cierre = """
        <h3>III. Resolutivo</h3>
        <p class="resolutivo">
            El Comit&eacute; de Transparencia <b>confirma</b> la clasificaci&oacute;n
            de los datos personales se&ntilde;alados en el cuadro anterior, avala la
            prueba de da&ntilde;o (en su caso) y aprueba la presente
            <b>Versi&oacute;n P&uacute;blica</b> mediante testado irreversible conforme
            al Art&iacute;culo 121 de la LGTAIP.
        </p>
        <div class="firma-container">
            <div class="firma-linea">
                Firma del Comit&eacute; de Transparencia
                <div class="firma-cargo">Responsable de la clasificaci&oacute;n</div>
            </div>
        </div>
        <p class="nota">
            Documento generado autom&aacute;ticamente por ANONIMA. La clasificaci&oacute;n
            fue realizada mediante an&aacute;lisis automatizado de datos personales con
            tecnolog&iacute;a de procesamiento de lenguaje natural (Presidio/GLiNER).
            El responsable deber&aacute; verificar y validar el contenido antes de su
            formalizaci&oacute;n.
        </p>
    """

    def _wrap(inner: str) -> str:
        return f"<html><head><style>{_ACTA_CSS}</style></head><body>{inner}</body></html>"

    def _to_pdf(inner: str):
        hd = pymupdf.open("html", _wrap(inner).encode("utf-8"))
        hd.layout(width=w, height=h, fontsize=11)
        return pymupdf.open("pdf", hd.convert_to_pdf())

    def _medir(inner: str):
        """Altura (pt) que ocuparía el bloque, medida con el motor Story."""
        try:
            story = pymupdf.Story(html=_wrap(inner), em=11)
            _, filled = story.place(pymupdf.Rect(0, 0, w, 1_000_000))
            return filled.height
        except Exception:
            return None

    # ── Estimación de alturas para empacar filas por página ──────────────────
    usable_h = h - 30 - 25          # márgenes verticales del body
    cap = usable_h - 10             # margen de seguridad
    h_pre = _medir(preambulo) or 0.0
    h_head = _medir(_acta_tabla("")) or 0.0
    h_close = _medir(cierre) or 0.0
    alturas = []
    for r in filas:
        m = _medir(_acta_tabla(r))
        alturas.append((m - h_head) if m else 42.0)

    # ── Repartir filas en páginas (con verificación de render por página) ─────
    acta_doc = pymupdf.open()
    n = len(filas)
    i = 0
    pagina_idx = 0
    cierre_insertado = False
    while i < n:
        disponible = cap - (h_pre if pagina_idx == 0 else 0.0) - h_head
        # estimación inicial de cuántas filas caben
        cnt, acc = 0, 0.0
        while i + cnt < n:
            ah = alturas[i + cnt]
            if cnt > 0 and acc + ah > disponible:
                break
            acc += ah
            cnt += 1
        cnt = max(cnt, 1)

        es_ultima_de_filas = (i + cnt >= n)
        # Si es la última tanda de filas, intentar incluir el cierre en la misma página
        pg = None
        if es_ultima_de_filas:
            inner_full = (preambulo if pagina_idx == 0 else "") + _acta_tabla("".join(filas[i:i + cnt])) + cierre
            cand = _to_pdf(inner_full)
            if cand.page_count == 1:
                pg = cand
                cierre_insertado = True
            else:
                cand.close()

        # Render normal (solo filas) con retroceso si se desborda a 2+ páginas
        if pg is None:
            while True:
                inner = (preambulo if pagina_idx == 0 else "") + _acta_tabla("".join(filas[i:i + cnt]))
                pg = _to_pdf(inner)
                if pg.page_count == 1 or cnt == 1:
                    break
                pg.close()
                cnt -= 1

        acta_doc.insert_pdf(pg)
        i += cnt
        pagina_idx += 1

    # Cierre en página propia si no cupo con la última tanda de filas
    if not cierre_insertado:
        acta_doc.insert_pdf(_to_pdf(cierre))

    acta_pages_count = len(acta_doc)
    doc.insert_pdf(acta_doc)

    # Pie de página (paginación) en las páginas del acta recién insertadas
    start_page = len(doc) - acta_pages_count
    for pno in range(start_page, len(doc)):
        p = doc[pno]
        p.insert_text(
            (p.rect.width / 2 - 80, p.rect.height - 25),
            f"Acta de Clasificacion — Pag. {pno - start_page + 1} de {acta_pages_count}",
            fontname="helv",
            fontsize=7.5,
            color=(0.45, 0.45, 0.45)
        )
    return
