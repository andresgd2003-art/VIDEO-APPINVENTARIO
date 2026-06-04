"""
Genera tests/fixtures/documento_prueba_integral.pdf
PDF de prueba con ~38 tipos de entidad para la herramienta ANONIMA.
Requiere: pymupdf (fitz)
Opcional: opencv-python (cv2) para QR real
"""

import os
import sys

try:
    import fitz  # pymupdf
except ImportError:
    print("ERROR: pymupdf no está instalado. Ejecuta: pip install pymupdf")
    sys.exit(1)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "documento_prueba_integral.pdf")
MARGIN = 72
LINE_HEIGHT = 14
FONT = "helv"
FONT_SIZE = 10
FONT_SIZE_TITLE = 13
FONT_SIZE_SECTION = 11


def add_text_block(page, lines, x, y, size=FONT_SIZE, bold=False):
    font = "hebo" if bold else FONT
    for line in lines:
        page.insert_text((x, y), line, fontname=font, fontsize=size, color=(0, 0, 0))
        y += LINE_HEIGHT
    return y


def separator(page, x, y, width=460):
    page.draw_line((x, y), (x + width, y), color=(0, 0, 0), width=0.5)
    return y + 6


def try_insert_qr(page, x, y):
    """Genera QR con cv2 e inserta en la página.  Sin error si cv2 no está."""
    try:
        import cv2
        import numpy as np
        import tempfile

        qr_text = "CURP:GADA030721HDGLZNA8 RFC:GADA0307211L8"
        encoder = cv2.QRCodeEncoder.create()
        # encode() devuelve la imagen QR como ndarray 2D directamente (NO tupla)
        qr_image = encoder.encode(qr_text)
        if qr_image is None or not hasattr(qr_image, "shape") or len(qr_image.shape) < 2:
            raise ValueError("QRCodeEncoder.encode() no devolvió imagen válida")

        # Escalar a 100x100 con NEAREST para que los módulos queden nítidos
        qr_resized = cv2.resize(qr_image, (100, 100), interpolation=cv2.INTER_NEAREST)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        cv2.imwrite(tmp_path, qr_resized)

        rect = fitz.Rect(x, y, x + 100, y + 100)
        page.insert_image(rect, filename=tmp_path)
        os.unlink(tmp_path)
        return y + 110, True

    except Exception as e:
        # Placeholder visible con etiqueta clara
        rect = fitz.Rect(x, y, x + 100, y + 100)
        page.draw_rect(rect, color=(0.3, 0.3, 0.3), width=1.5)
        page.insert_text((x + 5, y + 45), "QR CODE", fontname=FONT, fontsize=8, color=(0.3, 0.3, 0.3))
        page.insert_text((x + 5, y + 58), "CURP+RFC", fontname=FONT, fontsize=7, color=(0.5, 0.5, 0.5))
        return y + 110, False


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — Identificadores y contacto
# ═══════════════════════════════════════════════════════════════════════════════
doc = fitz.open()
page1 = doc.new_page(width=612, height=792)
x = MARGIN
y = MARGIN

y = add_text_block(page1, ["EXPEDIENTE DE IDENTIFICACION PERSONAL"], x, y, size=FONT_SIZE_TITLE, bold=True)
y = separator(page1, x, y)
y += 4

# ── Identificadores (regex-based) ────────────────────────────────────────────
lines_id = [
    "Titular:              ANDRES GALLEGOS DIAZ",
    "CURP:                 GADA030721HDGLZNA8",
    "RFC:                  GADA0307211L8",
    # NSS: 11 dígitos + contexto "NSS:"
    "NSS:                  11000520030",
    # INE clave elector: [A-Z]{6} + YYMMDD + EE(entidad) + H/M + 3 alphanum = 18
    # GALLEG(6) + 030721(6) + 10(Durango) + H(1) + 001(3) = 18 → ine_valido=True
    "INE Clave Elector:    GALLEG03072110H001",
    # Pasaporte: [A-Z]? + 8-9 dígitos → G + 8 dígitos = 9 chars
    "Pasaporte:            G12345678",
    # idCIF: regex idCIF\s*:\s*\d{9,13} → 11 dígitos
    "idCIF:                10212345678",
]
y = add_text_block(page1, lines_id, x, y)
y += 4

lines_personal = [
    "Fecha de Nacimiento: 21/07/2003    Edad: 21 anos    SEXO: MASCULINO",
    "Telefono:            618-123-4567",
    "Correo electronico:  andres.gallegos@gmail.com",
]
y = add_text_block(page1, lines_personal, x, y)
y += 10

# ── Domicilio ─────────────────────────────────────────────────────────────────
y = add_text_block(page1, ["DOMICILIO PARTICULAR"], x, y, size=FONT_SIZE_SECTION, bold=True)
y = separator(page1, x, y)
y += 4

lines_dom = [
    "Vialidad:             Cto. Amanecer            Numero exterior: 348",
    "Fraccionamiento:      Brisas Diamante",
    "Municipio:            Victoria de Durango       Estado: Durango    C.P.: 34235",
    # MX_ENTIDAD_REGISTRO: "Entidad de registro: DURANGO"
    "Entidad de registro:  DURANGO",
    # MX_LUGAR_NAC: LUGAR DE NACIMIENTO ... DATOS
    "LUGAR DE NACIMIENTO DURANGO DURANGO MEXICO DATOS DEL REGISTRADO",
    # MX_NACIONALIDAD: NACIONALIDAD MEXICANA (sin dos puntos)
    "NACIONALIDAD MEXICANA",
]
y = add_text_block(page1, lines_dom, x, y)
y += 20

# QR (opcional con cv2)
qr_x = page1.rect.width - MARGIN - 110
qr_y_start = MARGIN + 10
_, qr_ok = try_insert_qr(page1, qr_x, qr_y_start)
status = "QR real" if qr_ok else "QR placeholder"
page1.insert_text((qr_x, qr_y_start - 12), status, fontname=FONT, fontsize=7, color=(0.4, 0.4, 0.4))

page1.insert_text((x, 792 - 36), "Documento ANONIMA  |  Pag. 1 de 3", fontname=FONT, fontsize=8, color=(0.4, 0.4, 0.4))


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — Datos patrimoniales y acta de nacimiento
# ═══════════════════════════════════════════════════════════════════════════════
page2 = doc.new_page(width=612, height=792)
x = MARGIN
y = MARGIN

y = add_text_block(page2, ["DATOS PATRIMONIALES / FINANCIEROS"], x, y, size=FONT_SIZE_TITLE, bold=True)
y = separator(page2, x, y)
y += 4

lines_fin = [
    # CLABE: 18 dígitos con verificador correcto (014200012345678900)
    "CLABE Interbancaria:  014200012345678900",
    # Tarjeta: 4 grupos de 4 dígitos Luhn-válida
    "Numero de tarjeta:    4111 1111 1111 1111",
    # Cuenta bancaria: exactamente 10 dígitos + contexto "cuenta"
    "Numero de cuenta bancaria:  0012345678",
    "Monto:                $15,340.00",
    "Placa vehicular:      DGO-1234-B",
    "VIN / NIV:            1HGBH41JXMN109186",
    # RFC PM: exactamente 3 letras ASCII [A-ZÑ&]{3} + YYMMDD + 3 alphanum
    # CAF900901IB8 verificado con algoritmo SAT → rfc_valido=True
    "Empresa:  CAF DURANGO S.A. DE C.V.    RFC: CAF900901IB8",
]
y = add_text_block(page2, lines_fin, x, y)
y += 20

y = add_text_block(page2, ["DATOS DE ACTA DE NACIMIENTO"], x, y, size=FONT_SIZE_SECTION, bold=True)
y = separator(page2, x, y)
y += 4

lines_acta = [
    # CRIP: regex (?i)CRIP\s*:?\s*[A-Z0-9]{12,16}
    "CRIP:                 10DGO03072100000027",
    "Registrado:           ANDRES GALLEGOS DIAZ",
    "Madre:                EVA GALLEGOS DIAZ",
    "Lugar de nacimiento:  Durango, Durango, Mexico",
    "Fecha de nacimiento:  21/07/2003",
    "SEXO: MASCULINO",
]
y = add_text_block(page2, lines_acta, x, y)

page2.insert_text((x, 792 - 36), "Documento ANONIMA  |  Pag. 2 de 3", fontname=FONT, fontsize=8, color=(0.4, 0.4, 0.4))


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3 — Datos sensibles y partes procesales
# ═══════════════════════════════════════════════════════════════════════════════
page3 = doc.new_page(width=612, height=792)
x = MARGIN
y = MARGIN

y = add_text_block(page3, ["DATOS PERSONALES SENSIBLES"], x, y, size=FONT_SIZE_TITLE, bold=True)
y = separator(page3, x, y)
y += 4

lines_sens = [
    "Diagnostico medico:",
    "  Paciente con diagnostico de hipertension arterial esencial, en tratamiento.",
    "",
    "Origen etnico:",
    "  Perteneciente a la comunidad indigena Tepehuan del norte.",
    "",
    "Religion:",
    "  Practicante de la fe cristiana protestante, congregacion local.",
    "",
    "Afiliacion politica:",
    "  Militante activo del Partido Revolucionario Institucional desde 2018.",
    "",
    "Orientacion sexual:",
    "  Orientacion sexual declarada en expediente clinico: homosexual.",
    "",
    "Biometrico:",
    "  Sistema de autenticacion biometrica por reconocimiento de huella dactilar.",
]
y = add_text_block(page3, lines_sens, x, y)
y += 14

y = add_text_block(page3, ["PARTES PROCESALES"], x, y, size=FONT_SIZE_SECTION, bold=True)
y = separator(page3, x, y)
y += 4

lines_proc = [
    # IMPUTADO en MAYUSCULAS activa persona_header_judicial
    "IMPUTADO: ANDRES GALLEGOS DIAZ",
    "Victima:              Eva Gallegos Diaz",
    "Menor de edad:        Pepe Garcia Lopez (nombre ficticio de menor)",
    # Juez/Secretario: texto natural para que GLiNER los reconozca como roles legales
    "El Juez Roberto Rubio Cantu presidio la audiencia del dia de hoy.",
    "La Secretaria Maria Fernandez Torres certifico las actuaciones judiciales.",
    "Lugar de los hechos:  Durango, Durango",
    "Fecha de los hechos:  21/07/2024",
]
y = add_text_block(page3, lines_proc, x, y)

page3.insert_text((x, 792 - 36), "Documento ANONIMA  |  Pag. 3 de 3", fontname=FONT, fontsize=8, color=(0.4, 0.4, 0.4))


# ─── Guardar ──────────────────────────────────────────────────────────────────
doc.save(OUTPUT_PATH)
doc.close()

size_bytes = os.path.getsize(OUTPUT_PATH)
verify_doc = fitz.open(OUTPUT_PATH)
num_pages = len(verify_doc)
verify_doc.close()

print(f"PDF generado: {OUTPUT_PATH}")
print(f"Paginas:      {num_pages}")
print(f"Tamano:       {size_bytes:,} bytes ({size_bytes / 1024:.1f} KB)")
print("RESULTADO: OK" if num_pages >= 3 and size_bytes >= 10_000 else "RESULTADO: FALLO")
