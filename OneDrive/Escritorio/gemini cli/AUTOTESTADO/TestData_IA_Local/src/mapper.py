import re
import pymupdf


# Palabras a ignorar si spaCy las arrastra dentro del span de una entidad
PALABRAS_IGNORADAS = {
    # Títulos y tratamientos
    "licenciado", "licenciada", "lic", "juez", "jueza", "magistrado", "magistrada",
    "secretario", "secretaria", "dr", "dra", "ing", "arq", "mtro", "mtra",
    "sr", "sra", "señor", "señora",
    # Vocabulario de campos en formularios
    "cedula", "cédula", "idcif", "folio", "fecha", "número", "numero", "nom",
    "nombre", "val", "rfc", "curp", "nss", "clabe", "tel", "email", "correo",
    "registro", "federal", "contribuyentes", "contribuyente", "denominación",
    "denominacion", "razón", "razon", "social", "valida", "tu", "información",
    "informacion", "situación", "situacion", "fiscal", "identificación",
    "identificacion", "operaciones", "estatus", "padrón", "padron", "comercial",
    "datos", "domicilio", "registrado",
    # Geografía genérica (no datos personales)
    "calle", "colonia", "código", "codigo", "postal", "cp", "avenida", "ave",
    "boulevard", "blvd", "fraccionamiento", "fracc", "municipio", "estado",
    # Etiquetas de campo en CSF / formularios estructurados
    "vialidad", "exterior", "interior", "entre", "y", "localidad",
    "demarcación", "demarcacion", "territorial", "entidad", "federativa",
    "tipo", "del", "de", "la", "el", "los", "las", "o", "al", "a",
    # Términos legales comunes que spaCy confunde con nombres
    "primero", "segundo", "tercero", "cuarto", "quinto",
    "actor", "actora", "demandado", "demandada",
    "víctima", "victima", "imputado", "imputada", "acusado", "acusada",
    "sentenciado", "sentenciada", "ofendido", "ofendida", "quejoso", "quejosa",
    "c.", "c",
}

# Patrones que indican que un token NO es parte de un nombre de persona
_RE_SOLO_DIGITOS = re.compile(r'^\d+$')
_RE_CONTIENE_HASH = re.compile(r'#')
_RE_CONTIENE_ARROBA = re.compile(r'@')


def _es_token_valido_para_persona(palabra: str) -> bool:
    """Filtra tokens que no pueden ser parte de un nombre propio."""
    if _RE_SOLO_DIGITOS.match(palabra):
        return False
    if _RE_CONTIENE_HASH.search(palabra):
        return False
    if _RE_CONTIENE_ARROBA.search(palabra):
        return False
    return True


def _get(r, field):
    return r[field] if isinstance(r, dict) else getattr(r, field)


_TOLERANCIA_LINEA = 4.0  # puntos PDF — misma banda y para consolidar rects


def _consolidar_rects_por_linea(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """
    Agrupa los rectángulos de una misma línea horizontal en un único bounding box.

    Elimina los huecos entre palabras de entidades multi-token (ej. 'MIGUEL ÁNGEL
    CORTÉS RIVERA' → 4 rects separados → 1 rect sólido que cubre toda la frase).
    """
    if not rects:
        return rects
    lineas: dict[int, pymupdf.Rect] = {}
    for r in rects:
        key = round(r.y0 / _TOLERANCIA_LINEA)
        if key not in lineas:
            lineas[key] = pymupdf.Rect(r)
        else:
            e = lineas[key]
            lineas[key] = pymupdf.Rect(
                min(e.x0, r.x0), min(e.y0, r.y0),
                max(e.x1, r.x1), max(e.y1, r.y1),
            )
    return list(lineas.values())


def _deduplicar(mapeado: list[dict]) -> list[dict]:
    """Elimina entidades duplicadas por tipo y coordenadas de rectángulo."""
    vistos: set[tuple] = set()
    resultado = []
    for entidad in mapeado:
        # Clave: tipo + primer rect redondeado
        if entidad["rects"]:
            r = entidad["rects"][0]
            clave = (entidad["entity_type"], round(r.x0), round(r.y0), round(r.x1), round(r.y1))
        else:
            clave = (entidad["entity_type"], entidad["score"])
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(entidad)
    return resultado


_TIPOS_PERSONA    = {"PERSON", "Persona", "Juez", "Secretario", "Menor"}
_TIPOS_DOMICILIO  = {"MX_DOMICILIO", "MX_COLONIA", "MX_CP", "MX_ENTIDAD_REGISTRO"}
_TOLERANCIA_Y     = 4.0   # puntos PDF — misma línea si |y0_a - y0_b| < este valor
_TOLERANCIA_X     = 20.0  # puntos PDF — palabras adyacentes si gap_x < este valor
_TOLERANCIA_COL_X = 10.0  # puntos PDF — misma columna (formulario) si |x0_a - x0_b| < este valor
_TOLERANCIA_COL_Y = 30.0  # puntos PDF — líneas contiguas en columna si gap_y < este valor
_TOLERANCIA_DOMI_Y = 35.0  # puntos PDF — gap vertical máximo para fusión de domicilio


def _merge_adjacent_personas(mapeado: list[dict]) -> list[dict]:
    """
    Fusiona entidades de tipo PERSON/Persona contiguas en la misma línea.

    Cuando spaCy/GLiNER detecta 'ANDRES', 'GALLEGOS', 'DIAZ' por separado,
    esta función las une en una sola entidad 'ANDRES GALLEGOS DIAZ' con todos
    sus rects combinados, siempre que estén en la misma línea horizontal y
    el gap entre ellas sea inferior a _TOLERANCIA_X puntos PDF.
    """
    if not mapeado:
        return mapeado

    personas  = [e for e in mapeado if e["entity_type"] in _TIPOS_PERSONA]
    resto     = [e for e in mapeado if e["entity_type"] not in _TIPOS_PERSONA]

    if not personas:
        return mapeado

    # Ordenar por línea (y0 del primer rect) y luego por posición horizontal (x0)
    personas.sort(key=lambda e: (round(e["rects"][0].y0 / _TOLERANCIA_Y), e["rects"][0].x0))

    fusionadas: list[dict] = []
    actual = personas[0]

    for siguiente in personas[1:]:
        r_actual   = actual["rects"][-1]   # último rect del grupo actual
        r_siguiente = siguiente["rects"][0]  # primer rect del candidato

        misma_linea   = abs(r_actual.y0 - r_siguiente.y0) < _TOLERANCIA_Y
        misma_celda   = (r_actual == r_siguiente)  # ambas en la misma celda expandida
        # Formularios columna: mismo x0, línea siguiente inmediata (ej. Nombre/Apellido1/Apellido2)
        misma_columna = (abs(r_actual.x0 - r_siguiente.x0) < _TOLERANCIA_COL_X
                         and 0 < (r_siguiente.y0 - r_actual.y1) < _TOLERANCIA_COL_Y)
        gap_x         = r_siguiente.x0 - r_actual.x1
        en_linea      = misma_linea and (gap_x < _TOLERANCIA_X and gap_x > -_TOLERANCIA_X)
        puede_fusionar = en_linea or misma_celda or misma_columna

        if puede_fusionar and actual["entity_type"] == siguiente["entity_type"]:
            # Fusionar: combinar texto y rects
            texto_fusionado = (actual.get("text", "") + " " + siguiente.get("text", "")).strip()
            actual = {
                "entity_type": actual["entity_type"],
                "score":       max(actual["score"], siguiente["score"]),
                "text":        texto_fusionado,
                "rects":       actual["rects"] + siguiente["rects"],
            }
        else:
            fusionadas.append(actual)
            actual = siguiente

    fusionadas.append(actual)
    return fusionadas + resto


def _bounding_box(rects: list[pymupdf.Rect]) -> pymupdf.Rect:
    """Devuelve el bounding box mínimo que envuelve todos los rects."""
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return pymupdf.Rect(x0, y0, x1, y1)


def _merge_domicilio_multipieza(mapeado: list[dict]) -> list[dict]:
    """
    Fusiona entidades de domicilio (MX_DOMICILIO, MX_COLONIA, MX_CP,
    MX_ENTIDAD_REGISTRO) que estén en líneas contiguas y se traslapen
    horizontalmente — son piezas de un mismo bloque de dirección.

    Resultado: un único entity MX_DOMICILIO con un rect bounding-box que
    cubre todo el bloque, eliminando los huecos blancos entre las cajas.

    Conserva las piezas originales si están aisladas (otra dirección en
    otra parte de la página).
    """
    if not mapeado:
        return mapeado

    domicilio = [e for e in mapeado if e["entity_type"] in _TIPOS_DOMICILIO]
    resto     = [e for e in mapeado if e["entity_type"] not in _TIPOS_DOMICILIO]
    if len(domicilio) < 2:
        return mapeado

    # Ordenar por y0 del primer rect — orden de lectura vertical
    domicilio.sort(key=lambda e: e["rects"][0].y0)

    grupos: list[list[dict]] = [[domicilio[0]]]
    for ent in domicilio[1:]:
        grupo_actual = grupos[-1]
        bbox_actual  = _bounding_box([r for g in grupo_actual for r in g["rects"]])
        bbox_ent     = _bounding_box(ent["rects"])

        # Solape horizontal: comparten al menos algo de columna
        solapa_x = (bbox_ent.x0 < bbox_actual.x1 and bbox_ent.x1 > bbox_actual.x0)
        # Gap vertical: la nueva entidad arranca poco después de que termina el grupo
        gap_y = bbox_ent.y0 - bbox_actual.y1
        contiguo = -_TOLERANCIA_Y <= gap_y <= _TOLERANCIA_DOMI_Y

        if solapa_x and contiguo:
            grupo_actual.append(ent)
        else:
            grupos.append([ent])

    fusionadas: list[dict] = []
    for grupo in grupos:
        if len(grupo) == 1:
            fusionadas.append(grupo[0])
        else:
            todos_rects = [r for g in grupo for r in g["rects"]]
            bbox = _bounding_box(todos_rects)
            texto = " / ".join(g.get("text", "") for g in grupo if g.get("text"))
            fusionadas.append({
                "entity_type": "MX_DOMICILIO",
                "score":       max(g["score"] for g in grupo),
                "text":        texto,
                "rects":       [bbox],  # un solo rect que envuelve todo
            })

    return fusionadas + resto


def map_entities(indice_espacial: list[dict], resultados_analizador: list) -> list[dict]:
    """
    Traduce posiciones de carácter 1D a coordenadas espaciales 2D.

    Args:
        indice_espacial: Lista de dicts de pdf_reader.build_spatial_index()
        resultados_analizador: Lista de RecognizerResult o dicts de detector.analyze_page()

    Returns:
        Lista de entidades con entity_type, score y rects (deduplicadas).
    """
    mapeado = []

    for resultado in resultados_analizador:
        r_inicio = _get(resultado, "start")
        r_fin    = _get(resultado, "end")
        tipo     = _get(resultado, "entity_type")
        rects_encontrados = []

        for entrada in indice_espacial:
            if entrada["start_idx"] < r_fin and entrada["end_idx"] > r_inicio:
                palabra = entrada["word"]
                palabra_limpia = re.sub(r'[^\w]', '', palabra.lower())

                # Filtrar palabras ignoradas SOLO para nombres propios
                if tipo in ("PERSON", "Persona", "Juez", "Secretario", "Menor"):
                    if palabra_limpia in PALABRAS_IGNORADAS:
                        continue
                    if not _es_token_valido_para_persona(palabra):
                        continue

                word_char_rects = entrada.get("char_rects")
                if word_char_rects and len(word_char_rects) == len(palabra):
                    for j, char_rect in enumerate(word_char_rects):
                        char_idx = entrada["start_idx"] + j
                        if r_inicio <= char_idx < r_fin:
                            rects_encontrados.append(pymupdf.Rect(char_rect))
                else:
                    r = entrada["rect"]
                    rect_reducido = pymupdf.Rect(r.x0, r.y0, r.x1, r.y1)
                    rects_encontrados.append(rect_reducido)

        if rects_encontrados:
            if isinstance(resultado, dict):
                texto_entidad = resultado.get("text", "")
            elif hasattr(resultado, "text"):
                texto_entidad = resultado.text
            else:
                texto_entidad = " ".join(textos_encontrados) if "textos_encontrados" in locals() else " ".join(e["word"] for e in idx_esp) if "idx_esp" in locals() else "" # fallback
                
            mapeado.append({
                "entity_type": tipo,
                "score":       _get(resultado, "score"),
                "text":        texto_entidad,
                "rects":       _consolidar_rects_por_linea(rects_encontrados),
            })

    return _deduplicar(_merge_domicilio_multipieza(_merge_adjacent_personas(mapeado)))
