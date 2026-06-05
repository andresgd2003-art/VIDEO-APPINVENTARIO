# ── MARCO FEDERAL VIGENTE (verificado 2026, fuentes oficiales) ──────────────
# Reforma estructural de transparencia: el DECRETO publicado en el DOF el
# 20-mar-2025 (vigente 21-mar-2025) EXPIDIÓ tres leyes NUEVAS, abrogando las
# anteriores del mismo nombre, y extinguió al INAI (funciones transferidas a la
# Secretaría Anticorrupción y Buen Gobierno y al órgano "Transparencia para el
# Pueblo"). Las siglas se conservan:
#   • LGTAIP  = Ley General de Transparencia y Acceso a la Información Pública
#               (nueva, orig. DOF 20-mar-2025). Art. 116 = información
#               confidencial con datos personales (VIGENTE, sin cambio de número).
#               Art. 115 = información confidencial de datos sensibles; Art. 110
#               = información reservada (prueba de daño).
#   • LGPDPPSO = Ley General de Protección de Datos Personales en Posesión de
#               Sujetos Obligados (nueva, orig. DOF 20-mar-2025; última reforma
#               DOF 14-nov-2025). Art. 3, Fr. IX = "Datos personales"; Art. 3,
#               Fr. X = "Datos personales sensibles". (En la ley ABROGADA el dato
#               personal estaba en otra fracción; por eso se actualizó a Fr. IX.)
# Detalle y URLs oficiales en: legal_packs/REFERENCIAS_LEYES.md
LEGAL_MAPPING = {
    # ── PERSONAS / IDENTIDADES ──────────────────────────────────────────────
    "PERSON": {
        "descripcion": "Nombre de persona física",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Constituye dato personal que hace identificable a una persona física. "
            "Su divulgación afecta directamente la privacidad del titular (Art. 6 Const.)."
        ),
    },
    "Persona": {
        "descripcion": "Nombre de persona física",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato personal de identificación directa. Testado para proteger la "
            "identidad de la persona física involucrada en el documento."
        ),
    },
    "Menor": {
        "descripcion": "Identidad de persona menor de edad",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3 de la LGPDPPSO; "
            "Arts. 1 y 57 de la Ley General de los Derechos de Niñas, Niños y Adolescentes (LGDNNA)"
        ),
        "motivacion": (
            "Información estrictamente confidencial para proteger el interés superior del menor. "
            "La LGDNNA prohíbe exponer la identidad de menores de edad en documentos públicos."
        ),
    },

    # ── IDENTIFICADORES OFICIALES MEXICANOS ─────────────────────────────────
    "MX_CURP": {
        "descripcion": "Clave Única de Registro de Población (CURP)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Acuerdo por el que se establece el RENAPO (DOF 1990); "
            "Ley General de Población, Art. 85 Bis"
        ),
        "motivacion": (
            "La CURP es un identificador único por persona física emitido por el RENAPO. "
            "Su exposición permite la identificación inequívoca del titular y puede facilitar "
            "suplantación de identidad."
        ),
    },
    "MX_RFC_PF": {
        "descripcion": "Registro Federal de Contribuyentes (Persona Física)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Código Fiscal de la Federación (CFF), Art. 27"
        ),
        "motivacion": (
            "El RFC es un dato fiscal asignado por el SAT a cada contribuyente persona física. "
            "El CFF lo protege como información tributaria confidencial; "
            "su divulgación permite correlacionar la situación fiscal del titular."
        ),
    },
    "MX_INE": {
        "descripcion": "Clave de Elector (Credencial INE)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Ley General de Instituciones y Procedimientos Electorales (LEGIPE), Art. 9"
        ),
        "motivacion": (
            "La clave de elector es un identificador único de la lista nominal emitido por el INE. "
            "La LEGIPE establece la confidencialidad del Padrón Electoral y sus datos derivados."
        ),
    },
    "MX_INE_FOLIO": {
        "descripcion": "Folio de Identificación (Credencial INE)",
        "fundamento": (
            "Art. 116 de la LGTAIP; "
            "Ley General de Instituciones y Procedimientos Electorales (LEGIPE), Art. 9"
        ),
        "motivacion": (
            "Folio de identificación oficial emitido por el INE. "
            "Dato de identificación personal protegido por la LEGIPE como parte del Padrón Electoral."
        ),
    },
    "MX_NSS": {
        "descripcion": "Número de Seguridad Social (NSS/IMSS)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Ley del Seguro Social, Art. 15, Fracción I"
        ),
        "motivacion": (
            "El NSS es asignado individualmente por el IMSS a cada trabajador. "
            "La Ley del Seguro Social obliga a tratar los datos de asegurados con estricta confidencialidad; "
            "su revelación puede exponer historial laboral y de salud del titular."
        ),
    },
    "MX_ESCOLAR": {
        "descripcion": "Dato escolar (matrícula, institución educativa, carrera o programa)",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "La matrícula, institución educativa, carrera o programa que cursa el titular "
            "constituye un dato personal de carácter académico. Asociado al nombre, identifica "
            "de forma individual al titular, revela su trayectoria escolar y puede facilitar "
            "su identificación, perfilamiento o el acceso a sistemas y trámites del titular."
        ),
    },

    # ── CONTACTO ─────────────────────────────────────────────────────────────
    "MX_EMAIL": {
        "descripcion": "Correo electrónico particular",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato personal de contacto directo. Identificado como correo privado "
            "(no institucional *.gob.mx). Su exposición facilita acoso y suplantación."
        ),
    },
    "MX_TEL": {
        "descripcion": "Número telefónico",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato personal de contacto de la persona física. "
            "Permite localización directa del titular."
        ),
    },

    # ── DOMICILIO / UBICACIÓN ─────────────────────────────────────────────────
    "MX_DOMICILIO": {
        "descripcion": "Domicilio particular (calle, número, localidad)",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato de ubicación que revela la residencia habitual de una persona física. "
            "Su divulgación expone al titular a riesgos de seguridad personal."
        ),
    },
    "MX_COLONIA": {
        "descripcion": "Colonia o asentamiento (parte de domicilio)",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato ligado a la ubicación y domicilio particular. "
            "Combinado con otros datos identifica inequívocamente la residencia del titular."
        ),
    },
    "MX_CP": {
        "descripcion": "Código Postal (parte de domicilio)",
        "fundamento": "Art. 116 de la LGTAIP",
        "motivacion": (
            "Componente del domicilio particular. En contexto de un documento con otros datos "
            "del titular, contribuye a la identificación de su residencia."
        ),
    },
    "LOCATION": {
        "descripcion": "Referencia geográfica asociada al titular",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Ubicación geográfica que, en el contexto del documento, permite identificar "
            "o ubicar a la persona física titular. Protegida bajo el principio de minimización "
            "del Art. 16 LGPDPPSO: si su divulgación contribuye a la identificación del titular, "
            "debe testarse aunque de forma aislada no constituya dato personal."
        ),
    },
    "MX_ENTIDAD_REGISTRO": {
        "descripcion": "Entidad de Registro de Nacimiento",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato biográfico que revela el lugar de nacimiento o registro civil del titular. "
            "Permite perfilamiento de origen de la persona física."
        ),
    },

    # ── BIOGRÁFICOS ───────────────────────────────────────────────────────────
    "MX_FECHA_NAC": {
        "descripcion": "Fecha de nacimiento",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato biográfico que, en combinación con el nombre, permite la identificación "
            "precisa de la persona física y su perfilamiento demográfico."
        ),
    },
    "MX_EDAD": {
        "descripcion": "Edad de la persona",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": "Dato personal biográfico de carácter identificador.",
    },

    # ── PATRIMONIALES ─────────────────────────────────────────────────────────
    "MX_CLABE": {
        "descripcion": "CLABE Interbancaria",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Ley de Instituciones de Crédito, Art. 117 (secreto bancario)"
        ),
        "motivacion": (
            "Dato financiero de carácter estrictamente confidencial protegido por el secreto bancario. "
            "Su divulgación expone la cuenta del titular a fraude y acceso no autorizado."
        ),
    },
    "MX_TARJETA": {
        "descripcion": "Número de tarjeta bancaria",
        "fundamento": (
            "Art. 116 de la LGTAIP; "
            "Ley de Instituciones de Crédito, Art. 117 (secreto bancario)"
        ),
        "motivacion": (
            "Dato financiero protegido por secreto bancario. "
            "Su exposición facilita fraude y uso no autorizado del instrumento de pago."
        ),
    },
    "MX_CUENTA": {
        "descripcion": "Número de cuenta bancaria",
        "fundamento": (
            "Art. 116 de la LGTAIP; "
            "Ley de Instituciones de Crédito, Art. 117 (secreto bancario)"
        ),
        "motivacion": (
            "Dato financiero protegido por secreto bancario. "
            "Su revelación puede dar acceso no autorizado a los fondos del titular."
        ),
    },
    "MX_MONTO": {
        "descripcion": "Monto o cantidad económica",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato patrimonial de la persona física. "
            "Su revelación vulnera la esfera económica y privada del titular."
        ),
    },
    "MX_PLACA": {
        "descripcion": "Placa vehicular",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato patrimonial que identifica un bien mueble registrado a nombre de una persona física. "
            "Permite rastrear movimientos y ubicación habitual del titular."
        ),
    },
    "MX_VIN": {
        "descripcion": "Número de Identificación Vehicular (VIN/NIV)",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Identificador único del vehículo registrado a nombre del titular. "
            "Dato patrimonial confidencial."
        ),
    },

    # ── DATOS SENSIBLES (Art. 3 Fracción X LGPDPPSO) ───────────────────────
    "MX_ORIGEN_ETNICO": {
        "descripcion": "Origen racial o étnico",
        "fundamento": "Art. 3, Fracción X de la LGPDPPSO; Art. 115 de la LGTAIP",
        "motivacion": (
            "Dato personal sensible que revela el origen de una persona. "
            "Su uso indebido puede dar origen a discriminación o riesgo grave."
        ),
    },
    "MX_RELIGION": {
        "descripcion": "Creencias religiosas, filosóficas o morales",
        "fundamento": "Art. 3, Fracción X de la LGPDPPSO; Art. 115 de la LGTAIP",
        "motivacion": (
            "Dato personal sensible que pertenece a la esfera más íntima del titular. "
            "Requiere protección reforzada para evitar discriminación."
        ),
    },
    "MX_OPINION_POLITICA": {
        "descripcion": "Opiniones políticas / Afiliación",
        "fundamento": "Art. 3, Fracción X de la LGPDPPSO; Art. 115 de la LGTAIP",
        "motivacion": (
            "Dato personal sensible. Revelarlo puede vulnerar la privacidad "
            "ideológica y política de la persona física."
        ),
    },
    "MX_PREFERENCIA_SEXUAL": {
        "descripcion": "Preferencia u orientación sexual",
        "fundamento": "Art. 3, Fracción X de la LGPDPPSO; Art. 115 de la LGTAIP",
        "motivacion": (
            "Dato personal de la esfera más íntima del titular. Su tratamiento "
            "sin consentimiento expreso representa un riesgo grave de discriminación."
        ),
    },
    "MX_BIOMETRICO": {
        "descripcion": "Datos biométricos (huella, iris, reconocimiento facial)",
        "fundamento": "Art. 3, Fracción X de la LGPDPPSO (interpretación analógica y lineamientos INAI)",
        "motivacion": (
            "Dato personal que permite la identificación unívoca del titular "
            "mediante características físicas irreparables. Se considera de alta sensibilidad."
        ),
    },
    "MX_PASAPORTE": {
        "descripcion": "Número de Pasaporte",
        "fundamento": "Art. 115 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Identificador oficial emitido por la SRE que permite la identificación unívoca "
            "del titular y sus movimientos internacionales."
        ),
    },
    "MX_DIAGNOSTICO": {
        "descripcion": "Diagnóstico médico / Condición de salud",
        "fundamento": (
            "Art. 3, Fracción X de la LGPDPPSO (datos personales sensibles); "
            "Art. 115 de la LGTAIP"
        ),
        "motivacion": (
            "Dato personal sensible concerniente al estado de salud físico o mental del titular. "
            "La LGPDPPSO otorga protección reforzada a los datos sensibles: su divulgación "
            "conlleva riesgo grave de discriminación y afecta la dignidad del titular."
        ),
    },
    "Diagnóstico": {
        "descripcion": "Diagnóstico médico / Condición de salud",
        "fundamento": (
            "Art. 3, Fracción X de la LGPDPPSO (datos personales sensibles); "
            "Art. 115 de la LGTAIP"
        ),
        "motivacion": (
            "Dato personal sensible de salud. Su revelación puede ocasionar discriminación "
            "laboral, social o de seguros. Protección reforzada bajo LGPDPPSO."
        ),
    },

    # ── RESERVADOS (Art. 110 LGTAIP) ──────────────────────────────────────────
    "RESERVADO_SEGURIDAD": {
        "descripcion": "Información de seguridad institucional / nacional",
        "fundamento": "Art. 110 de la LGTAIP",
        "motivacion": (
            "Prueba de Daño: su divulgación representa un riesgo real y demostrable "
            "de perjuicio a la seguridad y procesos operativos institucionales."
        ),
    },

    # ── MANUAL / GENÉRICO ─────────────────────────────────────────────────────
    "MANUAL": {
        "descripcion": "Dato clasificado manualmente por el responsable",
        "fundamento": "Arts. 110 y 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Dato testado por revisión manual del oficial de privacidad o del "
            "responsable del tratamiento conforme a su criterio de clasificación."
        ),
    },
    "UNKNOWN": {
        "descripcion": "Dato personal diverso",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Información concerniente a una persona física identificada o identificable "
            "que no corresponde a una categoría específica listada."
        ),
    },

    # ── DATOS DE ACTA DE NACIMIENTO ──────────────────────────────────────────
    "MX_CRIP": {
        "descripcion": "Clave de Registro de Identidad Personal (CRIP)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Ley General de Población, Art. 85 Bis; "
            "Código Civil Federal, Arts. 55 y 389"
        ),
        "motivacion": (
            "La CRIP es el identificador único asignado al acta de nacimiento por el Registro Civil, "
            "precursor del CURP para menores. Permite la identificación unívoca del registrado "
            "y está vinculada a sus datos de filiación. Su exposición facilita la suplantación "
            "de identidad y el acceso indebido a registros civiles."
        ),
    },
    "MX_LUGAR_NAC": {
        "descripcion": "Lugar de nacimiento (localidad, municipio, entidad, país)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Código Civil Federal, Arts. 55 y 58 (contenido del acta de nacimiento)"
        ),
        "motivacion": (
            "Dato biográfico del acta de nacimiento que revela el origen geográfico del titular. "
            "Combinado con nombre y fecha de nacimiento, permite la identificación precisa "
            "de la persona y su perfilamiento. El Art. 58 del CCF establece que el acta debe "
            "contener el lugar de nacimiento, lo que lo convierte en dato personal de identificación."
        ),
    },
    "MX_NACIONALIDAD": {
        "descripcion": "Nacionalidad del titular o de sus padres",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Código Civil Federal, Art. 58, Fracción IV"
        ),
        "motivacion": (
            "Dato personal de identificación que revela el origen nacional del titular "
            "o de sus ascendientes. El Art. 58 del CCF lo establece como contenido "
            "obligatorio del acta de nacimiento. Su divulgación puede dar lugar a "
            "perfilamiento o discriminación por origen nacional."
        ),
    },
    "MX_SEXO": {
        "descripcion": "Sexo del registrado",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Código Civil Federal, Art. 58, Fracción II"
        ),
        "motivacion": (
            "Dato personal biográfico consignado en el acta de nacimiento conforme al Art. 58 "
            "del CCF. Su tratamiento requiere el consentimiento del titular; combinado con "
            "otros datos del acta, contribuye a la identificación inequívoca de la persona."
        ),
    },

    # ── ELEMENTOS VISUALES (MARCADO MANUAL) ──────────────────────────────────
    "MX_FIRMA": {
        "descripcion": "Firma autógrafa o digital",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción X de la LGPDPPSO (datos personales sensibles); "
            "Lineamientos del INAI en materia de datos biométricos"
        ),
        "motivacion": (
            "La firma autógrafa constituye un dato biométrico de comportamiento que permite "
            "la identificación unívoca del titular. Los lineamientos del INAI clasifican la firma "
            "como dato biométrico; su exposición facilita la falsificación documental "
            "y la suplantación de identidad."
        ),
    },
    "MX_QR": {
        "descripcion": "Código QR con datos personales codificados",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO"
        ),
        "motivacion": (
            "Los códigos QR en documentos oficiales (INE, CSF, actas) codifican datos personales "
            "del titular (CURP, RFC, nombre, domicilio) en formato legible por máquina. "
            "Su divulgación equivale a exponer todos los datos contenidos en el código, "
            "facilitando la extracción masiva automatizada de información personal."
        ),
    },

    # ── IDENTIFICADORES ADICIONALES ──────────────────────────────────────────
    "MX_NOMBRE": {
        "descripcion": "Nombre completo de persona física (campo estructurado)",
        "fundamento": "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO",
        "motivacion": (
            "Nombre de persona física extraído de campos estructurados de documentos oficiales "
            "(CSF, INE, actas). Dato personal de identificación directa."
        ),
    },
    "MX_IDCIF": {
        "descripcion": "Identificador de Cédula de Identificación Fiscal (idCIF)",
        "fundamento": (
            "Art. 116 de la LGTAIP; Art. 3, Fracción IX de la LGPDPPSO; "
            "Código Fiscal de la Federación (CFF), Art. 27"
        ),
        "motivacion": (
            "Identificador único de la Constancia de Situación Fiscal emitida por el SAT. "
            "Permite verificar la identidad fiscal del contribuyente y acceder a su información tributaria."
        ),
    },
    "MX_RFC_PM": {
        "descripcion": "Registro Federal de Contribuyentes (Persona Moral)",
        "fundamento": (
            "Art. 116 de la LGTAIP; "
            "Código Fiscal de la Federación (CFF), Art. 27"
        ),
        "motivacion": (
            "El RFC de persona moral identifica a una entidad jurídica ante el SAT. "
            "Aunque las personas morales no tienen datos personales per se, "
            "el RFC puede vincular a sus representantes legales como personas físicas."
        ),
    },
}


import json
import os

# ── Capa estatal modular ───────────────────────────────────────────────────
# El fundamento federal (LEGAL_MAPPING) se conserva intacto. Por configuración
# se le concatena el fundamento de la ley estatal correspondiente, sin alterar
# la maqueta del acta. Cada estado vive en src/legal_packs/<estado>.json.

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKS_DIR = os.path.join(_SRC_DIR, "legal_packs")
_CONFIG_PATH = os.path.join(_SRC_DIR, "legal_config.json")

# Tipos clasificados como datos personales SENSIBLES (Art. 3 frac. sensibles).
# El resto se considera dato personal "personal". Las leyes estatales citan
# fracciones distintas para cada categoría.
SENSIBLE_TYPES = {
    "MX_ORIGEN_ETNICO", "MX_RELIGION", "MX_OPINION_POLITICA",
    "MX_PREFERENCIA_SEXUAL", "MX_BIOMETRICO", "MX_DIAGNOSTICO",
    "Diagnóstico", "MX_FIRMA",
    # MX_SEXO puede indicar identidad de género (dato sensible bajo Art. 3 frac. X)
    "MX_SEXO",
    # MX_QR puede contener datos sensibles (firma digital = biométrico); capa estatal
    # más protectora si lo clasifica como sensible
    "MX_QR",
}

# Datos PATRIMONIALES / financieros: además del fundamento de dato personal,
# las leyes de transparencia los protegen vía secreto bancario, fiscal y bursátil
# (información confidencial). Reciben una cita estatal reforzada cuando el pack
# define la categoría "patrimonial" (si no, cae a "personal").
PATRIMONIAL_TYPES = {
    "MX_CLABE", "MX_TARJETA", "MX_CUENTA", "MX_MONTO", "MX_PLACA", "MX_VIN",
}

# cache: {estado: (mtime_float, pack_dict)}
_pack_cache: dict = {}


def _categoria(entity_type: str) -> str:
    if entity_type in SENSIBLE_TYPES:
        return "sensible"
    if entity_type in PATRIMONIAL_TYPES:
        return "patrimonial"
    return "personal"


def get_active_estado() -> str | None:
    """Lee la jurisdicción activa de legal_config.json. None si no hay config."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh).get("estado_activo") or None
    except (FileNotFoundError, ValueError, OSError):
        return None


def load_state_pack(estado: str | None) -> dict | None:
    """Carga (con cache invalidado por mtime) el pack legal del estado."""
    if not estado:
        return None
    path = os.path.join(_PACKS_DIR, f"{estado}.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    cached = _pack_cache.get(estado)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            pack = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        pack = None
    _pack_cache[estado] = (mtime, pack)
    return pack


def _fundamento_estatal(pack: dict, entity_type: str) -> str | None:
    por_tipo = pack.get("fundamento_por_tipo") or {}
    if entity_type in por_tipo:
        return por_tipo[entity_type]
    por_cat = pack.get("fundamento_por_categoria") or {}
    # patrimonial cae a "personal" si el pack no define esa categoría
    return por_cat.get(_categoria(entity_type)) or por_cat.get("personal")


def get_legal_justification(
    entity_type: str,
    custom_label: str = None,
    custom_legal: str = None,
    custom_motivacion: str = None,
    estado: str = None,
) -> dict:
    if entity_type == "CUSTOM" and custom_label and custom_legal and custom_motivacion:
        return {
            "type": custom_label,
            "descripcion": custom_label,
            "legal": custom_legal,
            "fundamento": custom_legal,
            "motivacion": custom_motivacion
        }

    base = LEGAL_MAPPING.get(entity_type)
    # Tipos desconocidos conservan el fallback genérico federal sin capa estatal
    # (preserva la identidad de LEGAL_MAPPING["UNKNOWN"] que esperan los tests).
    if base is None:
        return LEGAL_MAPPING["UNKNOWN"]

    if estado is None:
        estado = get_active_estado()
    pack = load_state_pack(estado)
    if not pack:
        return base

    estatal = _fundamento_estatal(pack, entity_type)
    if not estatal:
        return base

    merged = dict(base)
    # Partes separadas para que el acta pueda presentarlas de forma organizada
    # (etiquetadas en líneas distintas). El campo "fundamento" combinado se
    # conserva para compatibilidad con el resto del código y los tests.
    merged["fundamento_federal"] = base["fundamento"]
    merged["fundamento_estatal"] = estatal
    merged["fundamento"] = f"{base['fundamento']} — Marco estatal aplicable: {estatal}"
    return merged
