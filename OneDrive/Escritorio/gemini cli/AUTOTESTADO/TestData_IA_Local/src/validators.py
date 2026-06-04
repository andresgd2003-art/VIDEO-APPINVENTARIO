"""
Validadores de identificadores oficiales mexicanos (checksums).

Cada función devuelve True solo si la cadena cumple el algoritmo oficial de
dígito verificador. Permite descartar falsos positivos del regex (cualquier
18 dígitos que parezca CLABE pero no lo sea, cualquier 16 dígitos que parezca
tarjeta pero falle Luhn, etc.).
"""
import re

# ── CURP ──────────────────────────────────────────────────────────────────────
# Diccionario oficial RENAPO para cálculo del dígito verificador
_CURP_VALORES: dict[str, int] = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16,
    "H": 17, "I": 18, "J": 19, "K": 20, "L": 21, "M": 22, "N": 23,
    "Ñ": 24, "O": 25, "P": 26, "Q": 27, "R": 28, "S": 29,
    "T": 30, "U": 31, "V": 32, "W": 33, "X": 34, "Y": 35, "Z": 36,
}

_RE_CURP = re.compile(r"^[A-ZÑ]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$")


def curp_valido(curp: str) -> bool:
    """True si el dígito verificador del CURP coincide con el calculado."""
    if not curp or len(curp) != 18:
        return False
    curp = curp.upper()
    if not _RE_CURP.match(curp):
        return False
    try:
        suma = sum(_CURP_VALORES[c] * (18 - i) for i, c in enumerate(curp[:17]))
    except KeyError:
        return False
    digito = (10 - (suma % 10)) % 10
    return str(digito) == curp[17]


# ── RFC ───────────────────────────────────────────────────────────────────────
# Diccionario oficial SAT (Anexo 19) para dígito verificador del RFC.
# Importante: A=10 (NO 11). Ñ=36, &=37 según práctica común; espacio=0 (pad PM).
_RFC_VALORES: dict[str, int] = {
    " ": 0, "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15,
    "G": 16, "H": 17, "I": 18, "J": 19, "K": 20, "L": 21, "M": 22, "N": 23,
    "O": 24, "P": 25, "Q": 26, "R": 27, "S": 28, "T": 29, "U": 30, "V": 31,
    "W": 32, "X": 33, "Y": 34, "Z": 35, "Ñ": 36, "&": 37,
}

_RE_RFC_PF = re.compile(r"^[A-ZÑ&]{4}\d{6}[A-Z0-9]{2}[A-Z0-9]$")
_RE_RFC_PM = re.compile(r"^[A-ZÑ&]{3}\d{6}[A-Z0-9]{2}[A-Z0-9]$")


def rfc_valido(rfc: str) -> bool:
    """
    True si el dígito verificador del RFC (último char) coincide.

    Algoritmo oficial SAT: se pondera cada carácter por su posición desde 13
    hasta abajo (el primero pesa 13 para PF de 13 chars, 12 para PM de 12),
    se suman, se calcula (11 - suma%11), donde 10→'A' y 11→'0'.
    """
    if not rfc:
        return False
    rfc = rfc.upper()
    if _RE_RFC_PF.match(rfc):
        chars = rfc  # ya tiene 13 caracteres
    elif _RE_RFC_PM.match(rfc):
        chars = " " + rfc  # pad a 13 para alinear pesos
    else:
        return False
    try:
        suma = sum(_RFC_VALORES[c] * (13 - i) for i, c in enumerate(chars[:12]))
    except KeyError:
        return False
    resto = suma % 11
    digito_calc = 11 - resto
    if digito_calc == 11:
        esperado = "0"
    elif digito_calc == 10:
        esperado = "A"
    else:
        esperado = str(digito_calc)
    return esperado == chars[12]


# ── CLABE ─────────────────────────────────────────────────────────────────────
# Algoritmo mod-10 ponderado con pesos [3, 7, 1] cíclicos
_CLABE_PESOS = (3, 7, 1)


def clabe_valida(clabe: str) -> bool:
    """True si el dígito verificador (18º) de la CLABE coincide."""
    if not clabe or len(clabe) != 18 or not clabe.isdigit():
        return False
    suma = sum((int(d) * _CLABE_PESOS[i % 3]) % 10 for i, d in enumerate(clabe[:17]))
    digito = (10 - (suma % 10)) % 10
    return str(digito) == clabe[17]


# ── Luhn (Tarjeta bancaria) ───────────────────────────────────────────────────

def luhn_valido(numero: str) -> bool:
    """True si los dígitos del número (cualquier longitud par válida) pasan Luhn."""
    digitos = [int(c) for c in numero if c.isdigit()]
    if len(digitos) < 13 or len(digitos) > 19:
        return False
    suma = 0
    # Recorremos de derecha a izquierda, duplicando los pares (desde el segundo)
    for i, d in enumerate(reversed(digitos)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        suma += d
    return suma % 10 == 0


def tarjeta_valida(tarjeta: str) -> bool:
    """Wrapper semántico: tarjeta bancaria pasa Luhn y tiene 13-19 dígitos."""
    return luhn_valido(tarjeta)

# ── INE (Clave de Elector) ────────────────────────────────────────────────────
_RE_INE_ESTRUCTURA = re.compile(
    r"^[A-ZÑ]{6}"             # 1-6: Letras
    r"(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])"  # 7-12: Fecha Nac. YYMMDD
    r"(0[1-9]|[12]\d|3[0-3])" # 13-14: Entidad Federativa (01-32, a veces 33 para extranjero)
    r"[HM]"                   # 15: Sexo (H o M)
    r"[A-Z0-9]{3}$"           # 16-18: Homoclave
)

def ine_valido(ine: str) -> bool:
    """
    Verifica la estructura y semántica de los 18 caracteres de la Clave de Elector del INE.
    Aunque no tiene un checksum público estandarizado, sus componentes internos 
    (fecha y estado) deben ser semánticamente válidos.
    """
    if not ine or len(ine) != 18:
        return False
    
    ine = ine.upper()
    
    # 1. Validación de patrón estricto (fecha, entidad, sexo)
    match = _RE_INE_ESTRUCTURA.match(ine)
    if not match:
        return False
        
    # 2. Validación de día según el mes
    yy, mm, dd, estado = match.groups()
    mes = int(mm)
    dia = int(dd)
    
    if mes in (4, 6, 9, 11) and dia > 30:
        return False
    if mes == 2 and dia > 29:
        return False
            
    return True
