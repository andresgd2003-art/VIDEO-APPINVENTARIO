"""Tests de checksums oficiales: CURP, RFC, CLABE, Luhn."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from validators import curp_valido, rfc_valido, clabe_valida, luhn_valido, tarjeta_valida


# ── CURP ──────────────────────────────────────────────────────────────────────

def _curp_check_digit(base17: str) -> str:
    """Calcula el dígito verificador oficial de una CURP de 17 chars."""
    from validators import _CURP_VALORES
    suma = sum(_CURP_VALORES[c] * (18 - i) for i, c in enumerate(base17))
    return str((10 - (suma % 10)) % 10)


class TestCurp:
    # Generamos CURPs con check digit correcto para no depender de datos reales
    BASES_17 = [
        "BADD110313HCMLNS0",
        "PERA800101HDFRZN0",
        "HEGA850315MDFRNN0",
    ]

    def _curp_valida(self, base17):
        return base17 + _curp_check_digit(base17)

    def test_curps_validos(self):
        for base in self.BASES_17:
            curp = self._curp_valida(base)
            assert curp_valido(curp), f"Debía ser válido: {curp}"

    def test_curps_invalidos_digito_alterado(self):
        for base in self.BASES_17:
            correcto = _curp_check_digit(base)
            alterado = str((int(correcto) + 1) % 10)
            curp_malo = base + alterado
            assert not curp_valido(curp_malo), f"No debía ser válido: {curp_malo}"

    def test_curp_longitud_incorrecta(self):
        assert not curp_valido("")
        assert not curp_valido("BADD110313HCMLNS0")     # 17
        assert not curp_valido("BADD110313HCMLNS091")   # 19

    def test_curp_formato_invalido(self):
        assert not curp_valido("12345678901234567X")    # comienza con dígitos
        assert not curp_valido("BADD11A313HCMLNS09")    # letra en posición de dígito

    def test_curp_acepta_minusculas(self):
        curp = self._curp_valida(self.BASES_17[0])
        assert curp_valido(curp.lower())


# ── RFC ───────────────────────────────────────────────────────────────────────

def _rfc_check_digit(base12: str) -> str:
    """Calcula el dígito verificador del RFC (PF) dado los primeros 12 chars."""
    from validators import _RFC_VALORES
    suma = sum(_RFC_VALORES[c] * (13 - i) for i, c in enumerate(base12))
    d = 11 - (suma % 11)
    if d == 11: return "0"
    if d == 10: return "A"
    return str(d)


class TestRfc:
    # RFC real del CSF público (Andrés Gallegos Díaz, generado por SAT)
    RFC_REAL_VALIDO = "GADA0307211L8"

    BASES_12_PF = ["GADA0307211L", "GOMC900514AB", "PERA800101AB"]

    def test_rfc_real_csf_valido(self):
        assert rfc_valido(self.RFC_REAL_VALIDO)

    def test_rfc_generados_validos(self):
        for base in self.BASES_12_PF:
            rfc = base + _rfc_check_digit(base)
            assert rfc_valido(rfc), f"Debía ser válido: {rfc}"

    def test_rfc_pf_estructuralmente_invalido(self):
        # RFC con check digit cambiado
        for base in self.BASES_12_PF:
            correcto = _rfc_check_digit(base)
            alterado = "0" if correcto != "0" else "1"
            rfc_malo = base + alterado
            assert not rfc_valido(rfc_malo), f"No debía ser válido: {rfc_malo}"

    def test_rfc_longitud_invalida(self):
        assert not rfc_valido("")
        assert not rfc_valido("ABC")
        assert not rfc_valido("ABCD800101AB")  # solo 12 (PF debería ser 13)

    def test_rfc_caracteres_invalidos(self):
        assert not rfc_valido("AB#D800101A0A")

    def test_rfc_acepta_minusculas(self):
        assert rfc_valido(self.RFC_REAL_VALIDO.lower())


# ── CLABE ─────────────────────────────────────────────────────────────────────

class TestClabe:
    # CLABEs de prueba — calculadas con el algoritmo oficial mod-10 [3,7,1]
    # CLABE BBVA Bancomer: 012180001234567892 (placeholder)
    def test_clabe_calcula_digito(self):
        # Construyo una CLABE válida programáticamente para no depender de datos reales
        pesos = [3, 7, 1] * 6
        base = "01218000123456789"  # 17 dígitos
        suma = sum((int(d) * pesos[i]) % 10 for i, d in enumerate(base))
        check = (10 - (suma % 10)) % 10
        clabe_ok = base + str(check)
        assert clabe_valida(clabe_ok)

    def test_clabe_digito_alterado(self):
        # Misma CLABE pero con dígito verificador cambiado
        base = "012180001234567890"
        # Si '0' es el check válido, '9' no lo es (y viceversa)
        assert not (clabe_valida(base[:-1] + "0") and clabe_valida(base[:-1] + "9"))

    def test_clabe_longitud_invalida(self):
        assert not clabe_valida("")
        assert not clabe_valida("12345")
        assert not clabe_valida("0" * 17)
        assert not clabe_valida("0" * 19)

    def test_clabe_con_letras(self):
        assert not clabe_valida("01218000123456789A")


# ── Luhn / Tarjeta ────────────────────────────────────────────────────────────

class TestLuhn:
    # Números Luhn-válidos famosos de testing (no reales)
    VISA_TEST = "4111111111111111"          # 16 dígitos
    MASTERCARD_TEST = "5555555555554444"
    AMEX_TEST = "378282246310005"           # 15 dígitos

    def test_luhn_validos(self):
        for n in [self.VISA_TEST, self.MASTERCARD_TEST, self.AMEX_TEST]:
            assert luhn_valido(n), f"Debía ser Luhn-válido: {n}"

    def test_luhn_invalidos(self):
        # Mismo número con último dígito cambiado
        for n in [self.VISA_TEST, self.MASTERCARD_TEST]:
            invalido = n[:-1] + str((int(n[-1]) + 1) % 10)
            assert not luhn_valido(invalido), f"No debía pasar Luhn: {invalido}"

    def test_luhn_longitud_fuera_rango(self):
        assert not luhn_valido("123456789012")          # 12 dígitos (< 13)
        assert not luhn_valido("12345678901234567890")  # 20 dígitos (> 19)

    def test_luhn_ignora_espacios_y_guiones(self):
        assert luhn_valido("4111 1111 1111 1111")
        assert luhn_valido("4111-1111-1111-1111")

    def test_tarjeta_alias(self):
        assert tarjeta_valida(self.VISA_TEST)
        assert not tarjeta_valida("4111111111111112")  # falla Luhn (último dígito alterado)
