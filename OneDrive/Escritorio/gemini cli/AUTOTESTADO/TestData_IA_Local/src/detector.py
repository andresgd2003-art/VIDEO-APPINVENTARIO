import os
import re

# Modo OFFLINE de HuggingFace: GLiNER/transformers usan la caché local en vez de
# contactar la red. Evita "[Errno 11001] getaddrinfo failed" en equipos sin
# internet/DNS. Debe fijarse ANTES de importar gliner/transformers/huggingface_hub.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_analyzer.nlp_engine.ner_model_configuration import NerModelConfiguration

from validators import curp_valido, rfc_valido, clabe_valida, tarjeta_valida, ine_valido

# ── Constante de confusiones OCR comunes ──────────────────────────────────────
# EasyOCR/Tesseract confunden estos caracteres en documentos escaneados:
#   O ↔ 0,  I ↔ 1 ↔ l,  S ↔ 5,  B ↔ 8
_OCR_DIGIT_CHARS = 'OI'  # Caracteres que el OCR pone donde debería haber dígitos


def _normalizar_ocr_digitos(texto: str, posiciones_digito: list[int]) -> str:
    """
    Corrige confusiones OCR (O→0, I→1) en posiciones que DEBEN ser dígitos.
    Funciona para CURP, RFC, INE y cualquier identificador con estructura fija.
    """
    if not texto:
        return texto
    chars = list(texto.upper())
    for pos in posiciones_digito:
        if pos >= len(chars):
            continue
        if chars[pos] == 'O':
            chars[pos] = '0'
        elif chars[pos] in ('I', 'l'):
            chars[pos] = '1'
    return ''.join(chars)


def _normalizar_curp_ocr(texto: str) -> str:
    """Normaliza CURP de OCR: posiciones 4-9 (fecha) y 17 (verificador) son dígitos."""
    if not texto or len(texto) != 18:
        return texto
    return _normalizar_ocr_digitos(texto, [4, 5, 6, 7, 8, 9, 17])


def _normalizar_rfc_pf_ocr(texto: str) -> str:
    """Normaliza RFC persona física de OCR: posiciones 4-9 (fecha) son dígitos."""
    if not texto or len(texto) != 13:
        return texto
    return _normalizar_ocr_digitos(texto, [4, 5, 6, 7, 8, 9])


def _normalizar_rfc_pm_ocr(texto: str) -> str:
    """Normaliza RFC persona moral de OCR: posiciones 3-8 (fecha) son dígitos."""
    if not texto or len(texto) != 12:
        return texto
    return _normalizar_ocr_digitos(texto, [3, 4, 5, 6, 7, 8])


def _normalizar_ine_ocr(texto: str) -> str:
    """Normaliza clave de elector INE de OCR: posiciones 6-13 (números) y 15-17 son dígitos."""
    if not texto or len(texto) != 18:
        return texto
    return _normalizar_ocr_digitos(texto, [6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17])

# "Etiqueta: " al inicio de un campo estructurado (CSF/INE). Se recorta para que
# el recuadro tape solo el VALOR (ej. "Nombre de Vialidad: AMANECER" → "AMANECER").
# El límite de 60 chars cubre etiquetas largas ("Nombre del Municipio o
# Demarcación Territorial:") sin comerse texto si no es realmente una etiqueta.
_RE_ETIQUETA_VALOR = re.compile(r'^[^:]{1,60}:\s*')

_RE_CONTIENE_DIGITO = re.compile(r'\d')
_RE_CONTIENE_HASH   = re.compile(r'#')
_RE_RANGO_ANIO      = re.compile(r'^\d{4}-\d{4}$')

# Prefijo "LABEL:" al inicio del span — se recorta antes de validar
# Cubre todas las etiquetas comunes en documentos legales/identidad mexicanos
_ETIQUETAS_LABEL = (
    r"TITULAR|CONTRIBUYENTE|SOLICITANTE|PACIENTE|INTERESADO|INTERESADA"
    r"|PROMOVENTE|CAUSANTE|DEUDOR|DEUDORA|ACREEDOR|ACREEDORA"
    r"|TRABAJADOR|TRABAJADORA|ASEGURADO|ASEGURADA|BENEFICIARIO|BENEFICIARIA"
    r"|IMPUTADO|IMPUTADA|ACUSADO|ACUSADA|SENTENCIADO|SENTENCIADA"
    r"|V[Ií]CTIMA|OFENDIDO|OFENDIDA|AGRAVIADO|AGRAVIADA"
    r"|TESTIGO|DENUNCIANTE|QUEJOSO|QUEJOSA"
    r"|ACTOR|ACTORA|DEMANDADO|DEMANDADA|TERCERO\s+INTERESADO"
    r"|CONTRIBUYENTE|NOMBRE\s*\(S\)|NOMBRE|APELLIDO\s+PATERNO|APELLIDO\s+MATERNO"
    r"|PRIMER\s+APELLIDO|SEGUNDO\s+APELLIDO"
    r"|RAZ[Oó]N\s+SOCIAL|RFC|CURP|NSS|CLABE|IDCIF"
    r"|DOMICILIO|DIRECCI[Oó]N|CALLE|COLONIA|MUNICIPIO|ESTADO|C\.?P\.?"
    r"|TEL[Eé]FONO|TEL\.?|CELULAR|CORREO|EMAIL|E-MAIL"
    r"|FECHA\s+DE\s+NACIMIENTO|FECHA|EDAD|SEXO|G[Eé]NERO|NACIONALIDAD|OCUPACI[Oó]N"
    r"|R[Eé]GIMEN(?:\s+FISCAL)?|ACTIVIDAD|ESTADO\s+CIVIL"
    r"|EXPEDIENTE|CARPETA|FOLIO|N[Uú]MERO|REGISTRO"
    r"|TIPO\s+DE\s+\w+|DELITO|DEMARCACI[Oó]N\s+TERRITORIAL"
    r"|MARCA|SUBMARCA|MODELO|COLOR|PLACAS?|VIN|NIV"
    r"|REPRESENTANTE\s+LEGAL|APODERADO|MENOR\s+DE\s+EDAD|MENOR"
)
_RE_LABEL_PREFIX = re.compile(
    rf"^(?:(?:{_ETIQUETAS_LABEL})\s*:\s+)+",
    re.IGNORECASE,
)
# Prefijos narrativos sin ":" — se recortan del span MX_NOMBRE en _filtrar_falsos_positivos
_RE_NARRATIVA_PREFIX = re.compile(
    r"^(?:de\s+nombres?\s+|conocido\s+como\s+|conocida\s+como\s+|"
    r"identificado\s+como\s+|identificada\s+como\s+|"
    r"llamado\s+|llamada\s+|denominado\s+|denominada\s+|"
    r"a\s+nombre\s+de\s+|expedido\s+a\s+|emitido\s+a\s+|girado\s+a\s+|"
    # Etiqueta INE: "NOMBRE" (opcionalmente con "SEXO H" intercalado por el layout)
    r"NOMBRE\s+(?:SEXO\s*[HM]?\s+)?|"
    r"(?:el|la)\s+(?:C\.\s+|ciudadano\s+|ciudadana\s+|se[ñn]or\s+|se[ñn]ora\s+|sr\.\s+|sra\.\s+|lic\.\s+))",
    re.IGNORECASE,
)

# Roles legales genéricos que NO son nombres propios
_RE_ROLES_LEGALES = re.compile(
    r'^(?:el\s+|la\s+|los\s+|las\s+|al\s+|del\s+|un\s+|una\s+)?'
    r'(?:demandado|demandada|acusado|acusada|v[ií]ctima|imputado|imputada|'
    r'testigo|agraviado|agraviada|quejoso|quejosa|denunciante|ofendido|ofendida|'
    r'actor|actora|parte\s+actora|parte\s+demandada|reo|rea|'
    r'sentenciado|sentenciada|inculpado|inculpada|procesado|procesada|'
    r'apelante|recurrente|peticionario|peticionaria)s?$',
    re.IGNORECASE,
)

# Contexto que indica que una fecha es de nacimiento (100 chars antes del span)
# NOTA: NO incluir "emisión/operaciones/estado" — esas son fechas administrativas
# (emisión del documento, inicio de operaciones, cambio de estado en el padrón),
# NO fechas de nacimiento. Incluirlas marcaba esas fechas como MX_FECHA_NAC
# (falso positivo visto en la Constancia de Situación Fiscal).
_RE_CONTEXTO_NACIMIENTO = re.compile(
    r'nac(?:ido|ida|imiento|i[oó])|fecha\s+de\s+nac|d\.?o\.?b|'
    r'a[ñn]os?\s+de\s+edad|edad\s*:|born|cumple',
    re.IGNORECASE,
)

# ── Contexto obligatorio para identificadores numéricos ambiguos ───────────────
# Sin estas palabras en ±40 chars del span, el patrón se descarta (folio/expediente,
# no NSS / cuenta / folio INE).

_RE_CTX_NSS = re.compile(
    r'\b(?:NSS|N\.S\.S\.|n[uú]mero\s+de\s+seguridad\s+social|seguridad\s+social|IMSS|'
    r'asegurado|derechohabiente|afiliaci[oó]n)\b',
    re.IGNORECASE,
)
_RE_CTX_CUENTA = re.compile(
    r'\b(?:cuenta(?:\s+bancaria|\s+de\s+n[oó]mina|\s+de\s+ahorros?)?'
    r'|n[uú]m\.?\s+de\s+cuenta|cta\.?|no\.?\s+cuenta'
    r'|banco|bancomer|banamex|citibanamex|santander|hsbc|banorte|scotiabank'
    r'|inbursa|azteca|BBVA|banbaj[ií]o|banregio|multiva|afirme'
    r'|d[eé]posito|transferencia|cheques?|ahorros?'
    r'|SPEI|domiciliaci[oó]n|n[oó]mina)\b',
    re.IGNORECASE,
)
_RE_CTX_INE_FOLIO = re.compile(
    r'\b(?:folio|INE|IFE|credencial\s+(?:de\s+elector|para\s+votar)|elector|'
    r'identificaci[oó]n\s+oficial|documento\s+de\s+identidad)\b',
    re.IGNORECASE,
)
_RE_CTX_TEL = re.compile(
    r'\b(?:tel[eé]fono|tel\.?|cel(?:ular)?\.?|m[oó]vil|whatsapp|whats\b|wa\b|'
    r'lada|contacto|llamar|extensi[oó]n|ext\.?|fax|'
    r'comun[ií]c(?:ar|ate|arse)|marque|n[uú]mero\s+directo)\b'
    r'|\+\s*52\b',
    re.IGNORECASE,
)
# Contexto institucional: teléfonos públicos del SAT / dependencias que NO son
# datos personales (aparecen como boilerplate en el pie de la CSF y similares).
_RE_CTX_TEL_INSTITUCIONAL = re.compile(
    r'\b(?:MarcaSAT|SAT\s+m[oó]vil|atenci[oó]n\s+telef[oó]nica|denuncia|'
    r'sat\.gob|gob\.mx|desde\s+el\s+extranjero|desde\s+M[eé]xico|'
    r'cualquier\s+parte\s+del\s+pa[ií]s)\b',
    re.IGNORECASE,
)
_RE_CTX_CP = re.compile(
    r'\b(?:c\.?\s*p\.?|c[oó]digo\s+postal|cp\b)\b'
    r'|\b(?:colonia|col\.?|fracc(?:ionamiento)?|circuito|cto\.?|delegaci[oó]n|municipio|'
    r'localidad|alcald[ií]a|calle|avenida|av\.?|boulevard|blvd\.?'
    r'|barrio|sector|residencial|unidad\s+habitacional|condominio'
    r'|manzana|privada|prolongaci[oó]n|prol\.?|supermanzana)\b',
    re.IGNORECASE,
)
_RE_CTX_DOMICILIO = re.compile(
    r'\b(?:'
    # Tipos de vialidad
    r'calle|avenida|av\.?|boulevard|blvd\.?|calzada|calz\.?|carretera|camino|'
    r'cerrada|privada|circuito|cto\.?|fraccionamiento|fracc\.?|retorno|andador|'
    r'pasaje|paseo|anillo|ronda|prolongaci[oó]n|prol\.?|transversal|viaducto|'
    # Tipos de asentamiento
    r'colonia|col\.?|condominio|unidad\s+habitacional|u\.?\s*h\.?|residencial|'
    r'barrio|bo\.?|ejido|rancher[ií]a|pueblo|sector|supermanzana|'
    r'conjunto\s+habitacional|villa|'
    # Elementos numerados
    r'manzana|mza\.?|lote|lt\.?|interior|int\.?|n[uú]mero|n[uú]m\.?|'
    r'piso|planta|departamento|depto\.?|apto\.?|apartamento|casa|esquina|esq\.?|'
    # Frases de ubicación comunes en documentos oficiales
    r'con\s+domicilio|domicilio\s+en|domicilio\s+particular|domicilio\s+fiscal|'
    r'ubicado\s+en|ubicada\s+en|sito\s+en|sita\s+en|'
    r'c[oó]digo\s+postal|c\.?\s*p\.?'
    r')\b',
    re.IGNORECASE,
)
_RE_CTX_LUGAR_NAC = re.compile(
    r'\b(?:'
    r'lugar\s+de\s+nacimiento|lugar\s+de\s+origen|lugar\s+natal|'
    r'naci[oó]\s+en|nacido\s+en|nacida\s+en|nativo\s+de|nativa\s+de|'
    r'originario\s+de|originaria\s+de|procedente\s+de|procedencia|'
    r'estado\s+de\s+nacimiento|municipio\s+de\s+nacimiento|localidad\s+natal|'
    r'registro\s+civil|acta\s+de\s+nacimiento|sede\s+de\s+registro|'
    r'tierra\s+natal|origen\s+geogr[aá]fico'
    r')\b',
    re.IGNORECASE,
)
_RE_CTX_NACIONALIDAD = re.compile(
    r'\b(?:'
    r'nacionalidad|de\s+nacionalidad|nacionalidad\s+de|con\s+nacionalidad|'
    r'ciudadano\s+de|ciudadana\s+de|s[uú]bdito\s+de|naturalizado|naturalizada|'
    r'procedencia\s+nacional|extranjero|extranjera|extranjer[ií]a|'
    r'pasaporte|visa|residencia\s+permanente|residencia\s+temporal|'
    r'tenencia\s+de\s+la\s+nacionalidad|doble\s+nacionalidad'
    r')\b',
    re.IGNORECASE,
)

# ── Contextos para Datos Personales Sensibles ──────────────────────────────────
_RE_CTX_ORIGEN_ETNICO = re.compile(
    r'\b(?:origen|etnia|etnicidad|raza|grupo|comunidad|pueblo|lengua|habla|nativ[oa]|'
    r'ascendencia|descendencia|pertenencia|ind[ií]gena|'
    r'de\s+origen|perteneciente\s+a|miembro\s+de|integrante\s+de|descendiente\s+de|'
    r'pueblos\s+originarios|comunidades\s+ind[ií]genas|autoidentificaci[oó]n|'
    r'lengua\s+materna|idioma\s+materno|costumbres|tradiciones|cultura\s+ind[ií]gena|'
    r'diversidad\s+[eé]tnica|comunidades\s+ancestrales)\b',
    re.IGNORECASE,
)
_RE_CTX_RELIGION = re.compile(
    r'\b(?:religi[oó]n|creencia|culto|fe|iglesia|bautismo|practicante|congregaci[oó]n|dogma|'
    r'rito|parroquia|templo|devoto|devota|feligr[eé]s|ministro\s+de\s+culto|'
    r'de\s+religi[oó]n|confesi[oó]n\s+religiosa|afiliaci[oó]n\s+religiosa|'
    r'profesi[oó]n\s+de\s+fe|credo|sinagoga|mezquita|monasterio|convento|'
    r'orden\s+religiosa|sacerdote|sacerdotisa|di[aá]cono|rabino|im[aá]n|'
    r'ap[oó]stata|conversi[oó]n|bautizado|bautizada|confirmado|confirmada)\b',
    re.IGNORECASE,
)
_RE_CTX_OPINION_POLITICA = re.compile(
    r'\b(?:afiliaci[oó]n|partido|pol[ií]tica|voto|simpatizante|militante|eleccion(?:es)?|candidat[oa]|campa[ñn]a|'
    r'afiliado\s+a|militante\s+de|simpatizante\s+de|votante\s+de|'
    r'ideolog[ií]a|tendencia\s+pol[ií]tica|filiaci[oó]n\s+pol[ií]tica|'
    r'coalici[oó]n|precandidatur[ao]|candidatur[ao]|disidente\s+pol[ií]tic[oa]|'
    r'preso\s+pol[ií]tic[oa]|exiliado\s+pol[ií]tic[oa]|persecuci[oó]n\s+pol[ií]tica|'
    r'conservador|progresista|revolucionari[oa]|populista|libertari[oa])\b',
    re.IGNORECASE,
)
_RE_CTX_PREFERENCIA_SEXUAL = re.compile(
    r'\b(?:preferencia|orientaci[oó]n|sexual|g[eé]nero|identidad|sexo|'
    r'vida\s+[ií]ntima|conducta\s+sexual|'
    r'orientaci[oó]n\s+sexual|identidad\s+de\s+g[eé]nero|expresi[oó]n\s+de\s+g[eé]nero|'
    r'vida\s+afectiva|uni[oó]n\s+civil|matrimonio\s+igualitario|'
    r'familia\s+homoparental|comunidad\s+lgbtq|colectivo\s+lgbt|derechos\s+lgbt|'
    r'transfobia|homofobia|discriminaci[oó]n\s+por\s+orientaci[oó]n|'
    r'cambio\s+de\s+nombre|cambio\s+de\s+sexo|rectificaci[oó]n\s+de\s+acta|'
    r'reasignaci[oó]n\s+de\s+sexo|reconocimiento\s+legal\s+de\s+g[eé]nero)\b',
    re.IGNORECASE,
)
_RE_CTX_BIOMETRICO = re.compile(
    r'\b(?:autenticaci[oó]n|registro|identificaci[oó]n|biometr[ií]a|captura|verificaci[oó]n|sistema|'
    r'dactilar|lector|enrolamiento|escaneo|sensor|'
    r'datos\s+biom[eé]tricos|informaci[oó]n\s+biom[eé]trica|plantilla\s+biom[eé]trica|'
    r'patr[oó]n\s+dactilar|crestas\s+dactilares|geometr[ií]a\s+palmar|'
    r'reconocimiento\s+de\s+voz|verificaci[oó]n\s+de\s+voz|'
    r'perfil\s+gen[eé]tico|an[aá]lisis\s+gen[eé]tico|huella\s+gen[eé]tica|'
    r'base\s+de\s+datos\s+biom[eé]trica|algoritmo\s+biom[eé]trico|'
    r'comparaci[oó]n\s+biom[eé]trica|fusi[oó]n\s+biom[eé]trica)\b',
    re.IGNORECASE,
)
_RE_CTX_DIAGNOSTICO = re.compile(
    r'\b(?:paciente|diagn[oó]stico|enfermedad|s[ií]ntoma|padecimiento|tratamiento|cl[ií]nica|'
    r'hospital|m[eé]dico|salud|consulta|urgencia|condici[oó]n|'
    r'expediente\s+m[eé]dico|historial\s+cl[ií]nico|historia\s+cl[ií]nica|'
    r'nota\s+m[eé]dica|prescripci[oó]n|internamiento|cirug[ií]a|'
    r'discapacidad|incapacidad\s+m[eé]dica|rehabilitaci[oó]n|'
    r'diagn[oó]stico\s+de|portador\s+de|portadora\s+de|'
    r'infectado\s+de|infectada\s+de|contagiado\s+de|contagiada\s+de|'
    r'aquejado\s+de|aquejada\s+de|afectado\s+de|afectada\s+de|'
    r'antecedentes\s+m[eé]dicos|antecedentes\s+patol[oó]gicos|'
    r'cuadro\s+cl[ií]nico|cuadro\s+sinto|pron[oó]stico|secuela|'
    r'comorbilidad|certificado\s+m[eé]dico|informe\s+m[eé]dico)\b',
    re.IGNORECASE,
)


def _tiene_contexto(texto: str, inicio: int, fin: int, regex: re.Pattern, radio: int = 40) -> bool:
    """True si `regex` aparece en los ±radio chars alrededor del span."""
    ventana_ini = max(0, inicio - radio)
    ventana_fin = min(len(texto), fin + radio)
    return bool(regex.search(texto[ventana_ini:ventana_fin]))

# Títulos que preceden a servidores públicos — NO deben redactarse
_TITULOS_SERVIDOR = re.compile(
    r'(?:Licenciado|Licenciada|Lic\.'
    r'|Oficial|Agente\s+de\s+(?:Fuerza\s+Civil|Polic[i\xed]a)|Agente|Inspector'
    r'|Juez|Jueza|Magistrado|Magistrada'
    r'|Secretari[ao]\s+de\s+(?:Gesti[o\xf3]n|Acuerdos|Gobernaci[o\xf3]n|Estado|Seguridad)'
    r'|Secretari[ao]\s+T[e\xe9]cnico|Secretari[ao]\s+(?:General|Ejecutivo|Ejecutiva)'
    r'|Secretar[i\xed]a\s+de\s+(?:Gobernaci[o\xf3]n|Estado|Seguridad|Salud|Educaci[o\xf3]n)'
    r'|Notari[ao]\s+P[u\xfa]blico'
    r'|Ciudadano\s+Juez|C\.\s+Juez'
    r'|Fiscal|Subprocurador|Procurador|Diputado|Diputada|Senador|Senadora'
    r'|Subsecretari[ao]|Delegad[ao]\s+(?:Federal|Estatal|Municipal)'
    r'|Director\s+(?:General|de\s+\w+)|Subdirector)',
    re.IGNORECASE,
)
# Aplica al contexto previo — busca el título en cualquier posición del contexto,
# no solo al final (cubre casos como "Oficial de la Policía Municipal de San Pedro, NOMBRE")
_RE_TITULO_PREVIO = re.compile(
    r'(?:Licenciado|Licenciada|Lic\.'
    r'|Oficial|Agente\s+de\s+(?:Fuerza\s+Civil|Polic[i\xed]a)|Agente|Inspector'
    r'|Juez|Jueza|Magistrado|Magistrada'
    r'|Secretari[ao]\s+de\s+(?:Gesti[o\xf3]n|Acuerdos|Gobernaci[o\xf3]n|Estado|Seguridad)'
    r'|Secretari[ao]\s+T[e\xe9]cnico|Secretari[ao]\s+(?:General|Ejecutivo|Ejecutiva)'
    r'|Secretar[i\xed]a\s+de\s+(?:Gobernaci[o\xf3]n|Estado|Seguridad|Salud|Educaci[o\xf3]n)'
    r'|Notari[ao]\s+P[u\xfa]blico'
    r'|Ciudadano\s+Juez|C\.\s+Juez'
    r'|Fiscal|Subprocurador|Procurador|Diputado|Diputada|Senador|Senadora'
    r'|Subsecretari[ao]|Delegad[ao]\s+(?:Federal|Estatal|Municipal)'
    r'|Director\s+(?:General|de\s+\w+)|Subdirector)',
    re.IGNORECASE,
)

# Patrones que indican que la entidad detectada NO es un nombre propio real
# Se aplican sobre el texto completo del span (case-insensitive, bytes ASCII)
_RE_ETIQUETAS_CAMPO = re.compile(
    # CÉDULA: mayúscula É = \xc9, minúscula é = \xe9, o simple E/e
    r'c[\xc9\xe9eE]?[dD][uU][lL][aA]'
    r'|folio|fecha|nombre|apellido'
    r'|domicilio|direcci[\xf3\xd3o]n'
    r'|municipio|estado|pa[\xeds\xeds]'
    r'|sexo|g[\xe9\xc9e]nero|nacionalidad'
    r'|ocupaci[\xf3\xd3o]n|rfc\b|curp\b|nss\b|clabe\b'
    r'|experiencia\s+laboral|datos\s+personales'
    r'|educaci[\xf3\xd3o]n|habilidades|referencias'
    r'|NL\s+[Tt]ecnico|t[\xe9\xc9e]cnico'
    # Régimen fiscal / tipo de empleo (aparece en CSF, nóminas)
    r'|asalariado|asalariada|r[\xe9e]gimen|honorarios|arrendamiento'
    r'|actividad\s+empresarial|plataformas\s+tecnol'
    # Nombres de empresa / instituciones
    r'|farmacias|tiendas|grupo\s+\w+|corporativo|empresa|s\.a\.|s\.c\.|hospital'
    # Documentos y formatos
    r'|registro\s+federal|contribuyentes|denominaci[\xf3\xd3o]n|raz[\xf3\xd3o]n\s+social'
    r'|valida\s+tu\s+informaci[\xf3\xd3o]n|situaci[\xf3\xd3o]n\s+fiscal|identificaci[\xf3\xd3o]n'
    # Meses del año (span que incluye un mes probablemente es fecha/empleo, no nombre)
    r'|enero|febrero|marzo|abril|mayo|junio|julio|agosto'
    r'|septiembre|octubre|noviembre|diciembre',
    re.IGNORECASE,
)

# PERSON con más de 6 palabras probablemente no es un nombre
_MAX_PALABRAS_NOMBRE = 6

# Modelo spaCy cacheado para análisis POS de spans PERSON.
# Se setea desde build_analyzer() para reutilizar el nlp ya cargado.
_nlp_pos = None


def _set_nlp_pos(nlp):
    """Registra la instancia de spaCy nlp para uso en _filtrar_falsos_positivos."""
    global _nlp_pos
    _nlp_pos = nlp


def _es_nombre_propio_por_pos(fragmento: str) -> bool:
    """
    Usa POS tags de spaCy para decidir si el span tiene estructura de nombre propio.

    Reglas:
    - Si NO hay tokens PROPN → no es un nombre.
    - Si la mayoría de tokens son NOUN/VERB/ADJ (no PROPN), tampoco.
    - Si solo hay 1-2 tokens y al menos uno es PROPN → aceptar (nombre corto).

    Devuelve True si el análisis POS NO descarta el span (default permisivo
    si spaCy no está disponible).
    """
    if _nlp_pos is None or not fragmento.strip():
        return True
    try:
        doc = _nlp_pos(fragmento)
    except Exception:
        return True
    tokens_alfa = [t for t in doc if t.is_alpha and len(t.text) > 1]
    if not tokens_alfa:
        return True
    propn = sum(1 for t in tokens_alfa if t.pos_ == "PROPN")
    noun_o_verb = sum(1 for t in tokens_alfa if t.pos_ in ("NOUN", "VERB"))
    # Sin ningún PROPN → no es un nombre propio
    if propn == 0:
        return False
    # Si hay más NOUN/VERB que PROPN → más narrativa que nombre
    if noun_o_verb > propn:
        return False
    return True


def _filtrar_falsos_positivos(resultados: list, texto: str) -> list:
    """
    Descarta entidades PERSON cuyo texto no corresponde a un nombre propio real.
    Reglas:
    - Contiene dígitos o '#' → dirección
    - Coincide con etiqueta de campo (CÉDULA, FOLIO, EXPERIENCIA LABORAL, etc.)
    - Más de 6 palabras → encabezado de sección, no un nombre
    """
    limpios = []
    for r in resultados:
        fragmento = texto[r.start:r.end].strip()

        # ── MX_NOMBRE (campos CSF "Nombre/Apellido: VALOR") ──
        # Recorta el prefijo de etiqueta para que el recuadro tape solo el valor.
        if r.entity_type == "MX_NOMBRE":
            # 1. Prefijo tipo "LABEL: " (Titular:, Víctima:, etc.)
            m_lbl = _RE_LABEL_PREFIX.match(fragmento)
            if m_lbl:
                try:
                    r.start = r.start + len(m_lbl.group(0))
                except Exception:
                    pass
                fragmento = texto[r.start:r.end]
            # 2. Prefijos narrativos sin ":" ("de nombre X", "el ciudadano X", etc.)
            if not m_lbl:
                m_nar = _RE_NARRATIVA_PREFIX.match(fragmento)
                if m_nar:
                    try:
                        r.start = r.start + len(m_nar.group(0))
                    except Exception:
                        pass
                    fragmento = texto[r.start:r.end]
            if fragmento.strip():
                limpios.append(r)
            continue

        # ── Campos estructurados: recortar "Etiqueta:" para tapar solo el valor ──
        if r.entity_type in ("MX_DOMICILIO", "MX_COLONIA", "MX_IDCIF", "MX_ENTIDAD_REGISTRO"):
            m_ev = _RE_ETIQUETA_VALOR.match(texto[r.start:r.end])
            if m_ev:
                try:
                    r.start = r.start + m_ev.end()
                except Exception:
                    pass
                fragmento = texto[r.start:r.end].strip()

        # ── Validación de checksum oficial ──
        # Descarta identificadores que cumplen el regex pero NO el dígito verificador.
        if r.entity_type == "MX_CURP":
            # Pre-normalizar confusiones OCR (O↔0, I↔1) antes de validar checksum
            curp_normalizado = _normalizar_curp_ocr(fragmento)
            if not curp_valido(curp_normalizado):
                continue
        elif r.entity_type in ("MX_RFC_PF", "MX_RFC_PM"):
            # Pre-normalizar confusiones OCR en posiciones de fecha
            if r.entity_type == "MX_RFC_PF":
                rfc_normalizado = _normalizar_rfc_pf_ocr(fragmento)
            else:
                rfc_normalizado = _normalizar_rfc_pm_ocr(fragmento)
            if not rfc_valido(rfc_normalizado):
                continue
        elif r.entity_type == "MX_CLABE":
            if not clabe_valida(fragmento):
                continue
        elif r.entity_type == "MX_INE":
            ine_normalizado = _normalizar_ine_ocr(fragmento)
            if not ine_valido(ine_normalizado):
                continue
        elif r.entity_type == "MX_TARJETA":
            if not tarjeta_valida(fragmento):
                continue

        # ── Contexto obligatorio para identificadores ambiguos por longitud ──
        # MX_NSS (\d{11}) sin contexto "NSS/IMSS/seguridad social" → casi siempre folio
        if r.entity_type == "MX_NSS":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_NSS):
                continue
        # MX_CUENTA (\d{10}) sin contexto bancario → folio/expediente/tel sin formato
        elif r.entity_type == "MX_CUENTA":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_CUENTA):
                continue
        # MX_INE_FOLIO (\d{13} genérico) sin contexto INE/folio → otro número largo
        elif r.entity_type == "MX_INE_FOLIO":
            # El patrón con lookbehind contextual (folio_pasaporte/licencia) ya filtra;
            # solo aplicamos contexto al patrón genérico de 13 dígitos puros.
            if fragmento.isdigit() and len(fragmento) == 13:
                if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_INE_FOLIO):
                    continue

        if r.entity_type == "MX_TEL":
            # Rango de año (2020-2023)
            if _RE_RANGO_ANIO.match(fragmento):
                continue
            # Teléfono institucional público (SAT, dependencias) → no es dato personal
            if _tiene_contexto(texto, r.start, r.end, _RE_CTX_TEL_INSTITUCIONAL, radio=70):
                continue
            # Número embebido dentro de un token mayor sin espacios
            antes = texto[r.start - 1] if r.start > 0 else " "
            despues = texto[r.end] if r.end < len(texto) else " "
            if antes not in " \t\n(+-" or despues not in " \t\n),.:;|":
                continue
            # Contexto telefónico: prefijo +52, o palabra "tel/cel/etc" en ±40 chars
            digitos = re.sub(r'\D', '', fragmento)
            tiene_prefijo_52 = fragmento.lstrip().startswith("+52") or fragmento.lstrip().startswith("52 ")
            if not (tiene_prefijo_52 or len(digitos) == 10
                    or _tiene_contexto(texto, r.start, r.end, _RE_CTX_TEL)):
                continue
            limpios.append(r)
            continue

        # MX_CP: requiere contexto postal o de domicilio
        if r.entity_type == "MX_CP":
            # Si trae prefijo "C.P." en el propio span → válido sin más
            if re.match(r'^\s*C\.?\s*P\.?\b', fragmento, re.IGNORECASE):
                pass
            elif not _tiene_contexto(texto, r.start, r.end, _RE_CTX_CP, radio=60):
                continue

        # Contexto para domicilio: el patrón natural ya es bastante restrictivo,
        # pero el contexto adicional reduce falsos positivos en listas sin número.
        if r.entity_type == "MX_DOMICILIO":
            # Patrones CSF (campos estructurados) se aceptan siempre.
            # El patrón libre "Calle X Núm Y" solo requiere contexto si NO incluye número.
            fragmento_dom = texto[r.start:r.end]
            tiene_numero = bool(re.search(r'\d', fragmento_dom))
            if not tiene_numero:
                if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_DOMICILIO, radio=80):
                    continue

        # Contexto para lugar de nacimiento: amplía detección en lenguaje narrativo
        if r.entity_type == "MX_LUGAR_NAC":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_LUGAR_NAC, radio=80):
                continue

        # Contexto para nacionalidad: rechaza "MEXICANA" sin indicador de nacionalidad
        if r.entity_type == "MX_NACIONALIDAD":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_NACIONALIDAD, radio=60):
                continue

        # Filtros de contexto para Datos Sensibles (evita falsos positivos como "PAN" o "Católico" sin contexto)
        if r.entity_type == "MX_ORIGEN_ETNICO":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_ORIGEN_ETNICO, radio=60):
                continue
        elif r.entity_type == "MX_RELIGION":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_RELIGION, radio=60):
                continue
        elif r.entity_type == "MX_OPINION_POLITICA":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_OPINION_POLITICA, radio=60):
                continue
        elif r.entity_type == "MX_PREFERENCIA_SEXUAL":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_PREFERENCIA_SEXUAL, radio=60):
                continue
        elif r.entity_type == "MX_BIOMETRICO":
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_BIOMETRICO, radio=80):
                continue
        elif r.entity_type in ("MX_DIAGNOSTICO", "Diagnóstico"):
            if not _tiene_contexto(texto, r.start, r.end, _RE_CTX_DIAGNOSTICO, radio=80):
                continue

        # Juez / Secretario detectados por GLiNER: son servidores públicos por definición
        if r.entity_type in ("Juez", "Secretario"):
            continue

        # Filtro de servidor público para PERSON / Persona
        if r.entity_type in ("PERSON", "Persona"):
            contexto_previo  = texto[max(0, r.start - 80):r.start]
            contexto_despues = texto[r.end:r.end + 80]
            es_servidor = (
                _RE_TITULO_PREVIO.search(contexto_previo)       # título antes
                or _TITULOS_SERVIDOR.match(fragmento)            # título dentro
                or _TITULOS_SERVIDOR.search(contexto_despues)   # título después
            )
            if es_servidor:
                continue

        # Filtros comunes a PERSON y Persona (GLiNER)
        if r.entity_type in ("PERSON", "Persona"):
            # Si el span empieza con "LABEL:" (IMPUTADO:, VICTIMA:, etc.) recortar el prefijo
            m_lbl = _RE_LABEL_PREFIX.match(fragmento)
            if m_lbl:
                offset = len(m_lbl.group(0))
                try:
                    r.start = r.start + offset
                except Exception:
                    pass
                fragmento = texto[r.start:r.end]
            # Contiene dígitos o # → dirección, no nombre
            if _RE_CONTIENE_DIGITO.search(fragmento) or _RE_CONTIENE_HASH.search(fragmento):
                continue
            # Patrón "Label: Valor" con ":" en medio (no al inicio) → descartar
            if ":" in fragmento:
                continue
            # Etiqueta de campo / título de sección / ocupación
            if _RE_ETIQUETAS_CAMPO.search(fragmento):
                continue
            # Demasiadas palabras para ser un nombre
            if len(fragmento.split()) > _MAX_PALABRAS_NOMBRE:
                continue
            # Rol legal genérico ("el demandado", "la víctima", etc.)
            if _RE_ROLES_LEGALES.match(fragmento.strip()):
                continue
            # POS tags de spaCy: span sin PROPN o dominado por NOUN/VERB no es un nombre
            if not _es_nombre_propio_por_pos(fragmento):
                continue

        # Menor: descartar palabras sueltas comunes sin mayúscula (GLiNER hallucina)
        if r.entity_type == "Menor":
            palabras = fragmento.split()
            tiene_mayuscula = any(w[0].isupper() for w in palabras if w)
            if len(palabras) < 2 and not tiene_mayuscula:
                continue

        if r.entity_type == "MX_FECHA_NAC":
            # Solo es fecha de nacimiento si hay contexto explícito en los 50 chars previos
            contexto = texto[max(0, r.start - 50):r.start]
            if not _RE_CONTEXTO_NACIMIENTO.search(contexto):
                continue

        # Correos institucionales de gobierno no son datos personales
        if r.entity_type == "MX_EMAIL":
            if fragmento.lower().endswith(".gob.mx") or fragmento.lower().endswith(".gob.mx>"):
                continue

        if r.entity_type == "LOCATION":
            if "custodia" in fragmento.lower():
                continue

        limpios.append(r)
    return limpios


import threading as _threading
_analyzer_lock = _threading.Lock()
_analyzer_singleton: "AnalyzerEngine | None" = None


def build_analyzer() -> AnalyzerEngine:
    """Construye (o devuelve el singleton cacheado) del AnalyzerEngine.

    GLiNER/PyTorch no es seguro para inicialización concurrente: dos llamadas
    simultáneas desde distintos hilos (e.g. test fixture + UI background thread)
    causan un race condition en torch.nn.Embedding.__init__ y terminan en
    segfault. El lock garantiza inicialización única; llamadas posteriores
    devuelven el singleton ya construido sin volver a cargar los modelos.
    """
    global _analyzer_singleton
    if _analyzer_singleton is not None:
        return _analyzer_singleton
    with _analyzer_lock:
        if _analyzer_singleton is not None:  # double-checked
            return _analyzer_singleton
        _analyzer_singleton = _build_analyzer_impl()
    return _analyzer_singleton


def _build_analyzer_impl() -> AnalyzerEngine:
    import os
    import spacy
    import gliner_spacy
    from presidio_analyzer.nlp_engine import SpacyNlpEngine
    
    ner_mapping = NerModelConfiguration(
        labels_to_ignore=["O"],
        model_to_presidio_entity_mapping={
            "PER": "PERSON", "LOC": "LOCATION", "ORG": "ORGANIZATION",
            "Persona": "Persona", "Juez": "Juez", "Secretario": "Secretario", 
            "Diagnóstico": "Diagnóstico", "Menor": "Menor"
        }
    )

    class LoadedSpacyNlpEngine(SpacyNlpEngine):
        def __init__(self, loaded_spacy_model):
            super().__init__(ner_model_configuration=ner_mapping)
            self.nlp = {"es": loaded_spacy_model}
            
        def get_supported_entities(self):
            base_entities = super().get_supported_entities()
            return base_entities + ["Persona", "Juez", "Secretario", "Diagnóstico", "Menor"]

    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../models/es_core_news_custom"))
    nlp = spacy.load(model_path)

    # Registrar el modelo para análisis POS de spans PERSON en _filtrar_falsos_positivos
    _set_nlp_pos(nlp)

    gliner_labels = ["Persona", "Juez", "Secretario", "Diagnóstico", "Menor"]
    nlp.add_pipe("gliner_spacy", config={"gliner_model": "urchade/gliner_multi-v2.1", "labels": gliner_labels})
    
    loaded_nlp_engine = LoadedSpacyNlpEngine(loaded_spacy_model=nlp)
    analyzer = AnalyzerEngine(nlp_engine=loaded_nlp_engine, supported_languages=["es"])

    recognizers = [
        PatternRecognizer(
            supported_entity="MX_CURP",
            patterns=[Pattern(
                name="curp_pattern",
                # Posiciones 14-16: consonantes según norma, pero se relaja a [A-Z]
                # para admitir CURPs simulados/no estándar (ej. posición con vocal)
                regex=r"[A-Z][AEIOUX][A-Z]{2}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[HM](?:AS|B[CS]|C[CLMSH]|D[FG]|G[TR]|HG|JC|M[CNS]|N[ETL]|OC|PL|Q[TR]|S[PLR]|T[CSL]|VZ|YN|ZS|NE)[A-Z]{3}[A-Z\d]\d",
                score=0.85,
            ),
            Pattern(
                name="curp_ocr_tolerant",
                # OCR-tolerante: permite O/0/I/1 confusión en posiciones numéricas
                # EasyOCR/Tesseract confunden estos caracteres en IDs escaneadas
                regex=r"[A-Z][AEIOUX][A-Z]{2}[OI0-9]{2}[OI0-9]{2}[OI0-9]{2}[HM][A-Z]{2}[A-Z]{3}[A-Z0-9][OI0-9]",
                score=0.70,
            )],
            supported_language="es",
            context=["curp", "clave", "registro", "población", "identificación"],
        ),
        PatternRecognizer(
            supported_entity="MX_RFC_PF",
            patterns=[
                Pattern(
                    name="rfc_pf_pattern",
                    regex=r"\b[A-ZÑ&]{4}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[A-Z\d]{2}[A\d]\b",
                    score=0.85,
                ),
                Pattern(
                    name="rfc_pf_ocr_tolerant",
                    # OCR-tolerante: posiciones 4-9 son fecha, permiten O/0/I/1
                    regex=r"[A-ZÑ&]{4}[OI0-9]{6}[A-Z\d]{2}[A\d]",
                    score=0.65,
                ),
            ],
            supported_language="es",
            context=["rfc", "registro", "contribuyentes", "fiscal", "sat"],
        ),
        PatternRecognizer(
            supported_entity="MX_RFC_PM",
            patterns=[
                Pattern(
                    name="rfc_pm_pattern",
                    regex=r"[A-ZÑ&]{3}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[A-Z\d]{2}[A\d]",
                    score=0.85,
                ),
                Pattern(
                    name="rfc_pm_ocr_tolerant",
                    regex=r"[A-ZÑ&]{3}[OI0-9]{6}[A-Z\d]{2}[A\d]",
                    score=0.65,
                ),
            ],
            supported_language="es",
            context=["rfc", "registro", "contribuyentes", "fiscal", "sat"],
        ),
        PatternRecognizer(
            supported_entity="MX_INE",
            patterns=[
                Pattern(
                    name="ine_pattern",
                    regex=r"[A-Z]{6}\d{8}[A-Z\d]\d{3}",
                    score=0.85,
                ),
                Pattern(
                    name="ine_ocr_tolerant",
                    # OCR-tolerante: posiciones 6-13 son dígitos, permiten O/0/I/1
                    regex=r"[A-Z]{6}[OI0-9]{8}[A-Z0-9OI][OI0-9]{3}",
                    score=0.70,
                ),
            ],
            supported_language="es",
            context=["elector", "clave", "ine", "ife", "credencial", "votar"],
        ),
        PatternRecognizer(
            supported_entity="MX_CLABE",
            patterns=[Pattern(
                name="clabe_pattern",
                regex=r"\b\d{18}\b",
                score=0.75,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_NSS",
            patterns=[Pattern(
                name="nss_pattern",
                regex=r"\b\d{11}\b",
                score=0.65,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_CUENTA",
            patterns=[Pattern(
                name="cuenta_pattern",
                regex=r"\b\d{10}\b",
                score=0.5,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_PLACA",
            patterns=[Pattern(
                name="placa_pattern",
                # Formatos de placa México:
                # Automóvil federal: ABC-1234-A | anterior: ABC-12-34
                # Moto NL / estados: 99-XYZ-1, XX-NNN-N
                # Genérico alfanumérico con guiones
                regex=(
                    # Automóvil federal antiguo: ABC-12-34
                    r"\b[A-Z]{3}-\d{2}-\d{2}\b"
                    # Automóvil federal nuevo: ABC-1234-A
                    r"|\b[A-Z]{3}-\d{3,4}-[A-Z]\b"
                    # Moto/estado con formato dígitos-letras-dígito: 99-XYZ-1
                    r"|\b\d{2,3}-[A-Z]{2,4}-\d{1,2}\b"
                    # Moto con 3 letras + 5 dígitos (no 4, para no confundir con modelos)
                    r"|\b[A-Z]{3}-\d{5}\b"
                ),
                score=0.85,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_VIN",
            patterns=[Pattern(
                name="vin_pattern",
                # VIN: 17 caracteres alfanuméricos (excluye I, O, Q)
                regex=r"\b[A-HJ-NPR-Z0-9]{17}\b",
                score=0.85,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_TARJETA",
            patterns=[Pattern(
                name="tarjeta_pattern",
                # Tarjeta bancaria: 16 dígitos en grupos de 4
                regex=r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
                score=0.9,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_MONTO",
            patterns=[
                Pattern(
                    name="monto_pattern",
                    # Montos con signo de pesos: $3,500.00 / $845,000.00
                    regex=r"\$[\d,]+(?:\.\d{2})?",
                    score=0.7,
                ),
                Pattern(
                    name="monto_letra_pattern",
                    # Montos en texto: Doscientos cuarenta y cinco mil pesos 00/100 M.N. o moneda nacional
                    regex=r"(?i)\b(?:(?:un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|diecis[eé]is|diecisiete|dieciocho|diecinueve|veinte|veinti[uú]n|veintiuno|veintid[oó]s|veintitr[eé]s|veinticuatro|veinticinco|veintis[eé]is|veintisiete|veintiocho|veintinueve|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|doscientos|trescientos|cuatrocientos|quinientos|seiscientos|setecientos|ochocientos|novecientos|mil|mill[oó]n|millones|y)\s+)+pesos\s+\d{2}/100\s+(?:M\.?N\.?|moneda\s+nacional)(?!\w)",
                    score=0.7,
                )
            ],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_FECHA_NAC",
            patterns=[
                Pattern(
                    name="fecha_nac_pattern",
                    regex=(
                        r"\b\d{1,2}\s+de\s+"
                        r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
                        r"septiembre|octubre|noviembre|diciembre)"
                        r"\s+de\s+\d{4}\b"
                    ),
                    score=0.8,
                ),
                Pattern(
                    name="fecha_nac_numeric",
                    # Formato INE: dd/mm/yyyy
                    regex=r"\b\d{2}/\d{2}/\d{4}\b",
                    score=0.6,
                ),
                Pattern(
                    name="fecha_nac_acta",
                    # Formato acta: "2003 JULIO 21" o "JULIO 21 2003"
                    regex=(
                        r"\b\d{4}\s+"
                        r"(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|"
                        r"SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)"
                        r"\s+\d{1,2}\b"
                    ),
                    score=0.7,
                ),
            ],
            supported_language="es",
            context=["nacimiento", "nació", "nacido", "nacida", "fecha", "born"],
        ),
        PatternRecognizer(
            supported_entity="MX_EDAD",
            patterns=[
                Pattern(
                    name="edad_pattern",
                    # "27 años de edad" / "de 27 años de edad"
                    regex=r"\b\d{1,3}\s+a[ñn]os\s+de\s+edad\b",
                    score=0.75,
                ),
                Pattern(
                    name="edad_acta_pattern",
                    # Formato acta de nacimiento: "EDAD 32" o "EDAD: 25"
                    regex=r"(?i)EDAD\s*:?\s*\d{1,3}(?=\s|$)",
                    score=0.80,
                ),
            ],
            supported_language="es",
            context=["edad", "años", "madre", "padre", "padres", "nacimiento"],
        ),
        PatternRecognizer(
            supported_entity="MX_INE_FOLIO",
            patterns=[Pattern(
                name="ine_folio_pattern",
                # Folio INE: 13 dígitos (diferente al código de credencial de 6+8+1+3)
                regex=r"(?<!\d)\d{13}(?!\d)",
                score=0.7,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_TEL",
            patterns=[Pattern(
                name="tel_pattern",
                regex=r"(?:\+?52[\s\-]?(?:1[\s\-]?)?)?(?:\(?\d{2,3}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{4}\b",
                score=0.6,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_CP",
            patterns=[Pattern(
                name="cp_pattern",
                # CPs válidos de México: 01000–99999
                # Lookbehind negativo: no capturar si está precedido por "placa",
                # "número", "folio", "carpeta", "expediente", "serie"
                regex=r"(?<!placa\s)(?<!número\s)(?<!numero\s)(?<!folio\s)(?<!serie\s)(?<!carpeta\s)(?<!\d)(?:C\.?P\.?\s*)?(?:0[1-9]\d{3}|[1-9]\d{4})(?!\d)",
                score=0.5,
            )],
            supported_language="es",
        ),
        PatternRecognizer(
            supported_entity="MX_EMAIL",
            patterns=[Pattern(
                name="email_pattern",
                regex=r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
                score=0.85,
            )],
            supported_language="es",
        ),
    ]

    # Domicilio: lenguaje natural ("Calle X número Y") + formato campos CSF/INE
    recognizers.append(PatternRecognizer(
        supported_entity="MX_DOMICILIO",
        patterns=[
            Pattern(
                name="domicilio_calle_natural",
                regex=(
                    r"(?:Calle|Avenida|Av\.?|Boulevard|Blvd\.?|Calzada|Calz\.?"
                    r"|Carretera|Camino|Cerrada|Privada|Circuito|Cto\.?"
                    r"|Fraccionamiento|Fracc\.?|Retorno|Andador)"
                    r"(?:\s+[\wÀ-ɏ]+){1,8}"
                    r"\s+(?:n[u\xfa]mero|num\.?|No\.?|#)\s*\d+"
                    r"(?:[,\s]+(?:interior|int\.?|depto\.?|piso|departamento|apto\.?)\s*\d+)?"
                    r"(?:[,\s]+[Pp]lanta\s+[Bb]aja)?"
                ),
                score=0.85,
            ),
            # Formato INE / credencial: número DESNUDO sin la palabra "número".
            # "CTO AMANECER 348 FRACC BRISAS DIAMANTE" — tipo de vialidad + nombre +
            # número + asentamiento (FRACC/COL...). El nombre del asentamiento se acota
            # a SOLO LETRAS para detenerse en el CP siguiente y no tragarse otros campos.
            Pattern(
                name="domicilio_ine_credencial",
                regex=(
                    r"(?i)(?:Cto\.?|Calle|Av\.?|Avenida|Blvd\.?|Boulevard|Calz\.?|Calzada"
                    r"|Priv\.?|Privada|Cerrada|Circuito|And\.?|Andador|Retorno"
                    r"|Carr\.?|Carretera|Camino|Prol\.?|Prolongaci[oó]n)"
                    r"(?:\s+[A-Za-zÀ-ÿ]+){1,5}\s+\d{1,5}"
                    r"\s+(?:Fracc\.?|Fraccionamiento|Col\.?|Colonia|U\.?\s*H\.?"
                    r"|Unidad\s+Habitacional|Residencial|Barrio|Ejido)"
                    r"(?:\s+[A-Za-zÀ-ÿ]{2,}){1,4}"
                ),
                score=0.85,
            ),
            # Domicilio precedido por la etiqueta "DOMICILIO" (INE sin FRACC/COL).
            # Tipo de vialidad + nombre (letras) + número desnudo. Acotado a letras
            # para no desbordarse hacia el CP / clave de elector siguientes.
            Pattern(
                name="domicilio_etiqueta_ine",
                regex=(
                    r"(?i)DOMICILIO\s+"
                    r"(?:Cto\.?|Calle|Av\.?|Avenida|Blvd\.?|Boulevard|Calz\.?|Calzada"
                    r"|Priv\.?|Privada|Cerrada|Circuito|And\.?|Andador|Retorno|Carr\.?|Camino)"
                    r"(?:\s+[A-Za-zÀ-ÿ]+){1,6}\s+\d{1,5}"
                ),
                score=0.82,
            ),
            # Formato CSF / formularios estructurados
            Pattern(
                name="csf_vialidad",
                regex=r"Nombre\s+de\s+Vialidad\s*:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ɏ\s]{1,60}?(?=\s+N[u\xfa]mero|\s*$|\s*\n)",
                score=0.9,
            ),
            Pattern(
                name="csf_numero_ext",
                regex=r"N[u\xfa]mero\s+Exterior\s*:\s+\d+",
                score=0.85,
            ),
            Pattern(
                name="csf_numero_int",
                regex=r"N[u\xfa]mero\s+Interior\s*:\s+\d+",
                score=0.85,
            ),
            Pattern(
                name="csf_localidad",
                regex=r"Nombre\s+de\s+la\s+Localidad\s*:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ɏ\s]{1,60}?(?=\s+(?:Nombre|N[uú]mero|Entre|Y\s+Calle|C\.?P\.?|C[oó]digo|RFC|CURP)|\s*$|\s*\n)",
                score=0.85,
            ),
            Pattern(
                name="csf_municipio",
                regex=r"Nombre\s+del\s+Municipio[^:]{0,40}:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ɏ\s]{1,60}?(?=\s+(?:Nombre|N[uú]mero|Entre|Y\s+Calle|C\.?P\.?|C[oó]digo|RFC|CURP)|\s*$|\s*\n)",
                score=0.85,
            ),
            Pattern(
                name="csf_entidad",
                regex=r"Nombre\s+de\s+la\s+Entidad\s+Federativa\s*:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ɏ\s]{1,60}?(?=\s+(?:Nombre|N[uú]mero|Entre|Y\s+Calle|C\.?P\.?|C[oó]digo|RFC|CURP)|\s*$|\s*\n)",
                score=0.85,
            ),
            Pattern(
                name="csf_lugar_emision",
                regex=r"(?-i:\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ,\n]{3,60}?)(?=\s+[Aa]\s+\d{1,2}\s+[Dd][Ee]\s+[A-ZÁÉÍÓÚÑ]+\s+[Dd][Ee]\s+\d{4})",
                score=0.9,
            ),
            Pattern(
                name="csf_entre_calle",
                # Valor en MAYÚSCULAS (nombres de calle en CSF: TALISTIPA, ANOCHECER);
                # exigir ≥2 mayúsculas por palabra evita tragarse "Página", "Actividades",
                # etc. (antes usaba [^\n\r]+ y, como el texto nativo no tiene saltos de
                # línea, se desbordaba hasta el pie de página).
                regex=r"(?:Entre\s+Calle|Y\s+Calle)\s*:\s*(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,4})",
                score=0.85,
            ),
        ],
        supported_language="es",
    ))

    # Entidad de registro (específico para formato CURP)
    ESTADOS_MEXICO = r"(?:AGUASCALIENTES|BAJA CALIFORNIA(?: SUR)?|CAMPECHE|CHIAPAS|CHIHUAHUA|CIUDAD DE M[EÉ]XICO|COAHUILA(?: DE ZARAGOZA)?|COLIMA|DURANGO|GUANAJUATO|GUERRERO|HIDALGO|JALISCO|M[EÉ]XICO|MICHOAC[AÁ]N(?: DE OCAMPO)?|MORELOS|NAYARIT|NUEVO LE[OÓ]N|OAXACA|PUEBLA|QUER[EÉ]TARO|QUINTANA ROO|SAN LUIS POTOS[IÍ]|SINALOA|SONORA|TABASCO|TAMAULIPAS|TLAXCALA|VERACRUZ(?: DE IGNACIO DE LA LLAVE)?|YUCAT[AÁ]N|ZACATECAS)"
    recognizers.append(PatternRecognizer(
        supported_entity="MX_ENTIDAD_REGISTRO",
        patterns=[
            Pattern(
                name="entidad_registro_curp",
                regex=rf"(?<=Entidad de registro: )\b{ESTADOS_MEXICO}\b",
                score=0.9,
            ),
            # Nota: el patrón genérico de estado se eliminó — un estado solo
            # no constituye dato personal per se (LGTAIP/LGPDPPSO).
        ],
        supported_language="es",
    ))

    # Colonia / Fraccionamiento / Sector — lenguaje natural + formato campos CSF
    recognizers.append(PatternRecognizer(
        supported_entity="MX_COLONIA",
        patterns=[
            Pattern(
                name="colonia_natural",
                regex=(
                    r"(?:Colonia|Col\.)\s+[\w\sÀ-ɏ]{2,50}"
                    r"(?=[,\.\n]|\s+\d{5}|\s*$)"
                ),
                score=0.8,
            ),
            Pattern(
                name="csf_colonia",
                regex=r"Nombre\s+de\s+la\s+Colonia\s*:\s+[A-ZÁÉÍÓÚÑ][\wÀ-ɏ\s]{1,60}?(?=\s+(?:Nombre|N[u\xfa]mero|Entre|Y\s+Calle)|\s*$|\s*\n)",
                score=0.9,
            ),
        ],
        supported_language="es",
    ))

    # Diagnóstico médico: condición + descriptores de gravedad/tipo
    recognizers.append(PatternRecognizer(
        supported_entity="MX_DIAGNOSTICO",
        patterns=[Pattern(
            name="diagnostico_pattern",
            regex=(
                r"\b(?:asma|diabetes|hipertensi[o\xf3]n|VIH|SIDA|c[a\xe1]ncer"
                r"|tuberculosis|insuficiencia\s+\w+"
                r"|epilepsia|cardiopat[i\xed]a|cirrosis"
                r"|esquizofrenia|depresi[o\xf3]n|ansiedad|trastorno\s+\w+"
                r"|hepatitis|leucemia|linfoma|fibromialgia|artritis"
                r"|Alzheimer|Parkinson|autismo|discapacidad\s+\w+)"
                r"\b(?:\s+(?:cr[o\xf3]nica|aguda|severa|grave|leve|moderada"
                r"|tipo\s+\d+|arterial|ventricular|renal|pulmonar|mental|mixta))*"
            ),
            score=0.8,
        )],
        supported_language="es",
    ))

    # Folio de pasaporte mexicano: letra + 8 dígitos (ej. G87654321)
    recognizers.append(PatternRecognizer(
        supported_entity="MX_INE_FOLIO",
        patterns=[
            Pattern(
                name="folio_licencia_conducir",
                # Licencias estatales: 2 letras + 6 dígitos (ej. NL987654)
                regex=r"(?i)(?<=licencia\s{0,30})\b[A-Z]{2}\d{6}\b|(?<=folio\s{0,10})\b[A-Z]{2}\d{6}\b",
                score=0.80,
            ),
        ],
        supported_language="es",
    ))

    # ── Datos Sensibles y Nuevos (LGPDPPSO) ───────────────────────────────────
    recognizers.append(PatternRecognizer(
        supported_entity="MX_ORIGEN_ETNICO",
        patterns=[Pattern(
            name="origen_etnico",
            regex=r"\b(?:ind[ií]gena|maya|n[aá]huatl|zapotec[oa]|mixtec[oa]|otom[ií]|tzeltal|pur[eé]pecha|afrodescendiente|mestiz[oa]|cauc[aá]sic[oa]|blanc[oa]|moren[oa])\b",
            score=0.8,
        )],
        supported_language="es",
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MX_RELIGION",
        patterns=[Pattern(
            name="religion",
            regex=(
                r"\b(?:cat[oó]lic[oa]|cristian[oa]|testigo\s+de\s+jehov[aá]|morm[oó]n"
                r"|jud[ií]o|evang[eé]lic[oa]|evangelista|ate[oa]|agn[oó]stic[oa]"
                r"|musulm[aá]n|protestante|adventista|bautista|pentecost[ae]s?"
                r"|menonita|judaico|jud[ií]a)\b"
            ),
            score=0.8,
        )],
        supported_language="es",
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MX_OPINION_POLITICA",
        patterns=[Pattern(
            name="opinion_politica",
            regex=r"\b(?:PAN|PRI|PRD|Morena|PVEM|PT|Movimiento\s+Ciudadano|Acci[oó]n\s+Nacional|Revolucionario\s+Institucional|Revoluci[oó]n\s+Democr[aá]tica)\b",
            score=0.8,
        )],
        supported_language="es",
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MX_PREFERENCIA_SEXUAL",
        patterns=[Pattern(
            name="preferencia_sexual",
            regex=r"\b(?:heterosexual|homosexual|gay|lesbiana|bisexual|transexual|transg[eé]nero|pansexual|queer|LGBTQ\+?)\b",
            score=0.8,
        )],
        supported_language="es",
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MX_BIOMETRICO",
        patterns=[Pattern(
            name="biometrico",
            regex=r"\b(?:huella(?:s)?\s+dactilar(?:es)?|iris|reconocimiento\s+facial|ADN|huella\s+digital)\b",
            score=0.8,
        )],
        supported_language="es",
    ))

    recognizers.append(PatternRecognizer(
        supported_entity="MX_PASAPORTE",
        patterns=[Pattern(
            name="pasaporte_mx",
            regex=r"\b[A-Z]?\d{8,9}\b",
            score=0.7,
        )],
        supported_language="es",
    ))

    # Nombres en cabeceras judiciales: "IMPUTADO: JUAN PÉREZ GARCÍA" / "VÍCTIMA: ANA TORRES"
    # GLiNER falla en este contexto (todo mayúsculas, rodeado de etiquetas legales).
    recognizers.append(PatternRecognizer(
        supported_entity="Persona",
        patterns=[
            Pattern(
                name="persona_header_judicial",
                regex=(
                    # Solo roles donde GLiNER falla en texto ALL-CAPS (IMPUTADO/ACUSADO headers)
                    r"(?:IMPUTADO|IMPUTADA|ACUSADO|ACUSADA|SENTENCIADO|SENTENCIADA)\s*:\s*"
                    r"(?:[A-ZÁÉÍÓÚÑ]{2,15}"
                    r"(?:\s+(?!V[IÍ]CTIMA\b|IMPUTAD[OA]\b|ACUSAD[OA]\b|SENTENCIAD[OA]\b"
                    r"|CARPETA\b|DELITO\b|EXPEDIENTE\b)"
                    r"[A-ZÁÉÍÓÚÑ]{2,15}){1,4})"
                ),
                score=0.88,
            ),
            Pattern(
                name="persona_firma_licenciado",
                regex=r"(?i)(?:licenciad[oa]\s+|lic\.\s+)([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,4})",
                score=0.90,
            ),
            Pattern(
                name="persona_firma_juez",
                regex=r"(?i)(?:juez\s+)([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,4})",
                score=0.90,
            ),
            Pattern(
                name="persona_firma_secretario",
                regex=r"(?i)(?:secretari[oa]\s+)([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,4})",
                score=0.90,
            )
        ],
        supported_language="es",
    ))

    # idCIF: identificador del documento en la Constancia de Situación Fiscal
    # (11 dígitos). Antes lo capturaba el patrón NSS pero se descartaba por falta
    # de contexto "NSS"; aquí se reconoce por su etiqueta propia "idCIF:".
    recognizers.append(PatternRecognizer(
        supported_entity="MX_IDCIF",
        patterns=[Pattern(
            name="idcif_pattern",
            regex=r"(?i)idCIF\s*:\s*\d{9,13}",
            score=0.9,
        )],
        supported_language="es",
    ))

    # Nombre y apellidos en formato de campos CSF ("Nombre (s): ANDRES",
    # "Primer Apellido: GALLEGOS", "Segundo Apellido: DIAZ") y el nombre completo
    # del encabezado ("ANDRES GALLEGOS DIAZ" antes de "Nombre, denominación...").
    # GLiNER es inconsistente en este layout etiqueta:valor todo-mayúsculas; estos
    # patrones lo hacen determinista. El prefijo de etiqueta se recorta luego en
    # _filtrar_falsos_positivos (las etiquetas están en _ETIQUETAS_LABEL), dejando
    # el recuadro sobre el valor y no sobre "Primer Apellido:".
    # Entidad propia MX_NOMBRE (no "Persona"): Presidio fusiona los spans que
    # comparten tipo, así que GLiNER (que devuelve el nombre contaminado con las
    # etiquetas vecinas, p.ej. "Nombre (s): ANDRES Primer Apellido") imponía su
    # span más largo. Con un tipo distinto, el span limpio del regex sobrevive;
    # los spans contaminados de GLiNER (tipo Persona) mueren en el filtro de
    # etiquetas. En _filtrar_falsos_positivos se recorta el prefijo "Etiqueta:".
    # Patrón reutilizable: nombre en MAYÚSCULAS (2-4 palabras).
    # (?!\s*:) evita tragarse la etiqueta del campo siguiente ("CURP:", "RFC:", etc.)
    _NOMBRE_CAPS = r"(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+(?![A-ZÁÉÍÓÚÑ]+\s*:)[A-ZÁÉÍÓÚÑ]{2,}){1,3})"

    recognizers.append(PatternRecognizer(
        supported_entity="MX_NOMBRE",
        patterns=[
            # (?-i:...) fuerza distinción de mayúsculas pese a que Presidio compila
            # los patrones con IGNORECASE global; sin esto el valor en MAYÚSCULAS
            # se "comía" la etiqueta siguiente en minúsculas ("ANDRES Primer Apellido").

            # ── Etiquetas CSF / SAT ───────────────────────────────────────────
            Pattern(
                name="csf_nombres",
                regex=r"Nombre\s*\(s\)\s*:\s+(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,3})",
                score=0.95,
            ),
            Pattern(
                name="csf_primer_apellido",
                regex=r"Primer\s+Apellido\s*:\s+(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,3})",
                score=0.95,
            ),
            Pattern(
                name="csf_segundo_apellido",
                regex=r"Segundo\s+Apellido\s*:\s+(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,3})",
                score=0.95,
            ),
            Pattern(
                name="csf_nombre_encabezado",
                regex=r"(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,3})(?=\s+Nombre,\s+denominaci)",
                score=0.95,
            ),

            # ── Etiquetas de identidad en documentos oficiales mexicanos ──────
            # Cubre: Titular, Nombre del X, Contribuyente, Víctima, Imputado,
            # Acusado, Testigo, Ofendido, Denunciante, Quejoso, Promovente, etc.
            Pattern(
                name="etiqueta_titular",
                regex=(
                    r"(?i)(?:"
                    # Con "Nombre del/de la X:"
                    r"Nombre(?:\s+(?:del?|de\s+la)\s+(?:titular|solicitante|contribuyente|"
                    r"paciente|deudor|deudora|acreedor|acreedora|interesado|interesada|"
                    r"promovente|menor|representado|representada|representante|causante|"
                    r"trabajador|trabajadora|empleado|empleada|asegurado|asegurada|"
                    r"beneficiario|beneficiaria|quejoso|quejosa|agraviado|agraviada|"
                    r"imputado|imputada|acusado|acusada|sentenciado|sentenciada|"
                    r"v[ií]ctima|ofendido|ofendida|denunciante|testigo|declarante|"
                    r"arrendador|arrendadora|arrendatario|arrendataria|"
                    r"actor|actora|demandado|demandada|apelante|recurrente|"
                    r"tercero|tercera|fiador|fiadora|avalista|endosante))?|"
                    # Etiquetas standalone directas
                    r"Titular|Contribuyente|Persona\s+f[ií]sica|Paciente|Solicitante|"
                    r"Deudor|Deudora|Acreedor|Acreedora|Interesado|Interesada|"
                    r"Promovente|Causante|"
                    r"V[ií]ctima|Ofendido|Ofendida|Agraviado|Agraviada|"
                    r"Imputado|Imputada|Acusado|Acusada|Sentenciado|Sentenciada|"
                    r"Testigo|Denunciante|Declarante|Quejoso|Quejosa|"
                    r"Actor|Actora|Demandado|Demandada|Apelante|Recurrente|"
                    r"Arrendador|Arrendadora|Arrendatario|Arrendataria|"
                    r"Fiador|Fiadora|Avalista|Endosante|"
                    r"Asegurado|Asegurada|Beneficiario|Beneficiaria|"
                    r"Trabajador|Trabajadora|Empleado|Empleada"
                    r")\s*:\s+" + _NOMBRE_CAPS
                ),
                score=0.92,
            ),

            # ── Nombre en actas / expedientes ("el C.", "el ciudadano", etc.) ─
            Pattern(
                name="ciudadano_nombre",
                regex=(
                    r"(?i)(?:el\s+C\.|la\s+C\.|el\s+ciudadano|la\s+ciudadana|"
                    r"el\s+se[ñn]or|la\s+se[ñn]ora|el\s+sr\.|la\s+sra\.|"
                    r"el\s+lic\.|la\s+lic\.|c\.\s+)"
                    + _NOMBRE_CAPS
                ),
                score=0.88,
            ),

            # ── Nombre en narrativa legal sin ":" ─────────────────────────────
            # "la víctima NOMBRE", "el imputado NOMBRE", "el testigo NOMBRE"
            # Precede directamente al nombre en mayúsculas sin dos puntos.
            Pattern(
                name="narrativa_legal",
                regex=(
                    r"(?i)(?:la\s+v[ií]ctima|el\s+v[ií]ctima|"
                    r"el\s+imputado|la\s+imputada|"
                    r"el\s+acusado|la\s+acusada|"
                    r"el\s+sentenciado|la\s+sentenciada|"
                    r"el\s+ofendido|la\s+ofendida|"
                    r"el\s+agraviado|la\s+agraviada|"
                    r"el\s+testigo|la\s+testigo|"
                    r"el\s+denunciante|la\s+denunciante|"
                    r"el\s+quejoso|la\s+quejosa|"
                    r"el\s+actor|la\s+actora|"
                    r"el\s+demandado|la\s+demandada|"
                    r"el\s+menor|la\s+menor)\s+"
                    + _NOMBRE_CAPS
                ),
                score=0.85,
            ),

            # ── Nombre precedido de "de nombre" / "identificado como" ─────────
            Pattern(
                name="de_nombre",
                regex=(
                    r"(?i)(?:de\s+nombre|de\s+nombres|conocido\s+como|conocida\s+como|"
                    r"identificado\s+como|identificada\s+como|llamado|llamada)\s+"
                    + _NOMBRE_CAPS
                ),
                score=0.87,
            ),

            # ── Nombre precedido de "A nombre de:" / "Expedido a:" ────────────
            Pattern(
                name="a_nombre_de",
                regex=(
                    r"(?i)(?:A\s+nombre\s+de|Expedido\s+a|Emitido\s+a|Girado\s+a)"
                    r"\s*:\s+" + _NOMBRE_CAPS
                ),
                score=0.90,
            ),

            # ── Nombre en credencial INE — determinista, NO depende de GLiNER ──
            # Layout: "NOMBRE [SEXO H] APELLIDO APELLIDO NOMBRES DOMICILIO".
            # La etiqueta NOMBRE + (opcional SEXO H que el OCR intercala) precede
            # al nombre en MAYÚSCULAS; se detiene antes de DOMICILIO/CURP/CLAVE.
            # El prefijo "NOMBRE [SEXO H]" se recorta en _filtrar_falsos_positivos
            # vía _RE_NARRATIVA_PREFIX.
            Pattern(
                name="nombre_credencial_ine",
                regex=(
                    r"(?i)NOMBRE\s+(?:SEXO\s*[HM]?\s+)?"
                    r"(?-i:[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,3})"
                    r"(?=\s+(?:DOMICILIO|CLAVE|CURP|FECHA|SECCI|VIGENCIA|$))"
                ),
                score=0.88,
            ),
        ],
        supported_language="es",
    ))

    # ── Datos de Acta de Nacimiento ────────────────────────────────────────────

    # CRIP: Clave de Registro de Identidad Personal (precursor del CURP para menores)
    recognizers.append(PatternRecognizer(
        supported_entity="MX_CRIP",
        patterns=[Pattern(
            name="crip_pattern",
            regex=r"(?i)(?:CRIP|C\.R\.I\.P\.?)\s*:?\s*[A-Z0-9]{12,16}",
            score=0.90,
        )],
        supported_language="es",
    ))

    # Lugar de nacimiento en formato acta
    recognizers.append(PatternRecognizer(
        supported_entity="MX_LUGAR_NAC",
        patterns=[
            Pattern(
                name="lugar_nac_acta",
                # "LUGAR DE NACIMIENTO DURANGO DURANGO DURANGO MEXICO"
                regex=r"(?i)LUGAR\s+DE\s+NACIMIENTO\s+[A-Z\u00C1\u00C9\u00CD\u00D3\u00DA\u00D1\s]{4,80}?(?=\s+(?:LOCALIDAD|PADRES|DATOS|NOMBRE))",
                score=0.85,
            ),
        ],
        supported_language="es",
    ))

    # Nacionalidad del titular o de los padres
    recognizers.append(PatternRecognizer(
        supported_entity="MX_NACIONALIDAD",
        patterns=[Pattern(
            name="nacionalidad_pattern",
            regex=r"(?i)NACIONALIDAD\s+(?:MEXICANA|EXTRANJERA|[A-Z\u00C1\u00C9\u00CD\u00D3\u00DA\u00D1]{4,20})",
            score=0.75,
        )],
        supported_language="es",
    ))

    # Sexo del registrado (en contexto de acta/INE)
    recognizers.append(PatternRecognizer(
        supported_entity="MX_SEXO",
        patterns=[Pattern(
            name="sexo_acta_pattern",
            regex=r"(?i)SEXO\s*:?\s*(?:MASCULINO|FEMENINO|HOMBRE|MUJER|[HM](?=\s|$))",
            score=0.80,
        )],
        supported_language="es",
    ))

    for recognizer in recognizers:
        analyzer.registry.add_recognizer(recognizer)

    # Nota: los estados de México (DURANGO, NUEVO LEÓN, etc.) no se registran como LOCATION
    # porque nombres de estado solos no son datos personales per LGPDPPSO.
    # El domicilio completo (calle + colonia + CP) sí lo es, pero se captura vía CP y contexto.

    # Permitir que Presidio procese las etiquetas de GLiNER a traves de spaCy
    gliner_recognizer = SpacyRecognizer(supported_language="es", supported_entities=["Persona", "Juez", "Secretario", "Diagnóstico", "Menor"])
    analyzer.registry.add_recognizer(gliner_recognizer)

    return analyzer


def analyze_page(analyzer: AnalyzerEngine, text: str) -> list:
    if not text or not text.strip():
        return []

    entidades_validas = [
        "MX_CURP", "MX_RFC_PF", "MX_RFC_PM", "MX_INE", "MX_INE_FOLIO", "MX_PASAPORTE",
        "MX_CLABE", "MX_NSS", "MX_CUENTA", "MX_PLACA", "MX_VIN", "MX_TARJETA", "MX_MONTO",
        "MX_TEL", "MX_CP", "MX_EMAIL", "MX_DOMICILIO", "MX_COLONIA", "MX_ENTIDAD_REGISTRO",
        "MX_FECHA_NAC", "MX_EDAD", "MX_DIAGNOSTICO", "MX_NOMBRE", "MX_IDCIF",
        "MX_CRIP", "MX_LUGAR_NAC", "MX_NACIONALIDAD", "MX_SEXO",
        "MX_ORIGEN_ETNICO", "MX_RELIGION", "MX_OPINION_POLITICA", "MX_PREFERENCIA_SEXUAL", "MX_BIOMETRICO",
        "PERSON", "Persona", "Juez", "Secretario", "Diagnóstico", "Menor", "LOCATION",
    ]
    resultados = analyzer.analyze(text=text, language="es", entities=entidades_validas)
    resultados = _filtrar_falsos_positivos(resultados, text)
    return _resolver_overlaps(resultados)


# Prioridad de entidad cuando dos spans se superponen (mayor índice = más prioritario)
_PRIORIDAD = {
    # Identificadores únicos de alta confianza
    "MX_CURP": 10, "MX_RFC_PF": 10, "MX_RFC_PM": 10,
    "MX_INE": 10, "MX_INE_FOLIO": 9,
    "MX_CLABE": 10, "MX_TARJETA": 10, "MX_VIN": 10,
    "MX_EMAIL": 10, "MX_IDCIF": 10,
    # GLiNER zero-shot (más específico que spaCy)
    "Persona": 11, "Juez": 11, "Secretario": 11, "Diagnóstico": 11, "Menor": 11,
    # Nombre por campos estructurados CSF (gana a la Persona contaminada de GLiNER)
    "MX_NOMBRE": 12,
    # spaCy NER
    "PERSON": 7, "LOCATION": 6,
    # Datos numéricos con contexto
    "MX_NSS": 8, "MX_PLACA": 8, "MX_FECHA_NAC": 8, "MX_EDAD": 7,
    "MX_MONTO": 7, "MX_CUENTA": 6,
    "MX_DOMICILIO": 8, "MX_COLONIA": 7, "MX_DIAGNOSTICO": 9, "MX_ENTIDAD_REGISTRO": 9,
    "MX_TEL": 5, "MX_CP": 4,
    # Datos de acta de nacimiento
    "MX_LUGAR_NAC": 9, "MX_CRIP": 9,
    "MX_NACIONALIDAD": 7, "MX_SEXO": 7,
    # Datos sensibles
    "MX_ORIGEN_ETNICO": 9, "MX_RELIGION": 8,
    "MX_OPINION_POLITICA": 8, "MX_PREFERENCIA_SEXUAL": 9,
    "MX_BIOMETRICO": 9, "MX_PASAPORTE": 10,
    # Visual / imagen (inyectado por qr_detector, no por analyze_page)
    "MX_QR": 11,
}


def _resolver_overlaps(resultados: list) -> list:
    """Elimina resultados de menor prioridad cuando sus spans se superponen."""
    ordenados = sorted(resultados, key=lambda r: _PRIORIDAD.get(r.entity_type, 0), reverse=True)
    spans_usados: list[tuple[int, int]] = []
    filtrados = []
    for r in ordenados:
        solapado = any(r.start < fin and r.end > ini for ini, fin in spans_usados)
        if not solapado:
            spans_usados.append((r.start, r.end))
            filtrados.append(r)
    return filtrados
