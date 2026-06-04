# -*- coding: utf-8 -*-
"""
Pruebas de palabras de contexto que FALTAN en los regex de detector.py.

Cada test reproduce una frase real de documentos mexicanos donde la entidad
debería detectarse pero el contexto aún no está registrado. Al pasar estos
tests se confirma que las palabras nuevas fueron agregadas correctamente.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
from detector import build_analyzer, analyze_page

@pytest.fixture(scope="module")
def analyzer():
    return build_analyzer()

def _tiene(res, tipo):
    return any(r.entity_type == tipo for r in res)

# ══════════════════════════════════════════════════════════════════════════════
# MX_NSS — contextos adicionales
# ══════════════════════════════════════════════════════════════════════════════

def test_nss_asegurado(analyzer):
    assert _tiene(analyze_page(analyzer, "Número de asegurado 11000520030 IMSS"), "MX_NSS")

def test_nss_derechohabiente(analyzer):
    assert _tiene(analyze_page(analyzer, "Derechohabiente número 11000520030 del IMSS"), "MX_NSS")

def test_nss_afiliacion_imss(analyzer):
    assert _tiene(analyze_page(analyzer, "Afiliación IMSS: 11000520030"), "MX_NSS")

# ══════════════════════════════════════════════════════════════════════════════
# MX_CUENTA — bancos y términos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_cuenta_bbva(analyzer):
    assert _tiene(analyze_page(analyzer, "Cuenta BBVA número 1234567890"), "MX_CUENTA")

def test_cuenta_citibanamex(analyzer):
    assert _tiene(analyze_page(analyzer, "Citibanamex cuenta 1234567890"), "MX_CUENTA")

def test_cuenta_banbajio(analyzer):
    assert _tiene(analyze_page(analyzer, "BanBajío 1234567890 nómina"), "MX_CUENTA")

def test_cuenta_banregio(analyzer):
    assert _tiene(analyze_page(analyzer, "Banregio cuenta 1234567890"), "MX_CUENTA")

def test_cuenta_spei(analyzer):
    assert _tiene(analyze_page(analyzer, "SPEI desde cuenta 1234567890"), "MX_CUENTA")

def test_cuenta_nomina(analyzer):
    assert _tiene(analyze_page(analyzer, "Cuenta de nómina 1234567890"), "MX_CUENTA")

def test_cuenta_domiciliacion(analyzer):
    assert _tiene(analyze_page(analyzer, "Domiciliación bancaria cuenta 1234567890"), "MX_CUENTA")

# ══════════════════════════════════════════════════════════════════════════════
# MX_INE_FOLIO — identificación oficial
# ══════════════════════════════════════════════════════════════════════════════

def test_ine_folio_identificacion_oficial(analyzer):
    assert _tiene(analyze_page(analyzer, "Identificación oficial folio 1234567890123"), "MX_INE_FOLIO")

def test_ine_folio_documento_identidad(analyzer):
    assert _tiene(analyze_page(analyzer, "Documento de identidad número 1234567890123"), "MX_INE_FOLIO")

# ══════════════════════════════════════════════════════════════════════════════
# MX_TEL — formas de referenciar teléfono
# ══════════════════════════════════════════════════════════════════════════════

def test_tel_comunicarse(analyzer):
    assert _tiene(analyze_page(analyzer, "Comuníquese al 5512345678 para atención"), "MX_TEL")

def test_tel_numero_directo(analyzer):
    assert _tiene(analyze_page(analyzer, "Número directo: 5512345678"), "MX_TEL")

def test_tel_marque(analyzer):
    assert _tiene(analyze_page(analyzer, "Marque al 5512345678 en horario de oficina"), "MX_TEL")

# ══════════════════════════════════════════════════════════════════════════════
# MX_CP — contextos de domicilio faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_cp_barrio(analyzer):
    assert _tiene(analyze_page(analyzer, "Barrio del Centro CP 06060"), "MX_CP")

def test_cp_sector(analyzer):
    assert _tiene(analyze_page(analyzer, "Sector Libertad 64810"), "MX_CP")

def test_cp_residencial(analyzer):
    assert _tiene(analyze_page(analyzer, "Residencial Las Brisas código postal 64850"), "MX_CP")

def test_cp_unidad_habitacional(analyzer):
    assert _tiene(analyze_page(analyzer, "Unidad habitacional CP 07760"), "MX_CP")

def test_cp_condominio(analyzer):
    assert _tiene(analyze_page(analyzer, "Condominio Las Flores 45050"), "MX_CP")

def test_cp_manzana(analyzer):
    assert _tiene(analyze_page(analyzer, "Manzana 5 Lote 2 CP 77500 Cancún"), "MX_CP")

def test_cp_privada(analyzer):
    assert _tiene(analyze_page(analyzer, "Privada del Roble número 12 CP 20010"), "MX_CP")

def test_cp_prolongacion(analyzer):
    assert _tiene(analyze_page(analyzer, "Prolongación Reforma 500 CP 11530"), "MX_CP")

# ══════════════════════════════════════════════════════════════════════════════
# MX_RELIGION — términos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_religion_templo(analyzer):
    assert _tiene(analyze_page(analyzer, "Asistente al templo de la Iglesia Evangélica"), "MX_RELIGION")

def test_religion_parroquia(analyzer):
    assert _tiene(analyze_page(analyzer, "Parroquia católica de San Juan Bautista"), "MX_RELIGION")

def test_religion_rito(analyzer):
    assert _tiene(analyze_page(analyzer, "Rito religioso practicado: Evangelista"), "MX_RELIGION")

def test_religion_ministro_culto(analyzer):
    assert _tiene(analyze_page(analyzer, "Ministro de culto de la Iglesia Adventista"), "MX_RELIGION")

# ══════════════════════════════════════════════════════════════════════════════
# MX_OPINION_POLITICA — términos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_politica_ideologia(analyzer):
    assert _tiene(analyze_page(analyzer, "Ideología política: Morena"), "MX_OPINION_POLITICA")

def test_politica_tendencia(analyzer):
    assert _tiene(analyze_page(analyzer, "Tendencia política de izquierda del PRD"), "MX_OPINION_POLITICA")

def test_politica_conviccion(analyzer):
    assert _tiene(analyze_page(analyzer, "Convicción política afín al PAN"), "MX_OPINION_POLITICA")

# ══════════════════════════════════════════════════════════════════════════════
# MX_BIOMETRICO — términos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_biometrico_dactilar(analyzer):
    assert _tiene(analyze_page(analyzer, "Impresión dactilar para verificar huella digital"), "MX_BIOMETRICO")

def test_biometrico_lector(analyzer):
    assert _tiene(analyze_page(analyzer, "Lector de huella dactilar para acceso"), "MX_BIOMETRICO")

def test_biometrico_enrolamiento(analyzer):
    assert _tiene(analyze_page(analyzer, "Enrolamiento biométrico de huella dactilar"), "MX_BIOMETRICO")

def test_biometrico_escaneo(analyzer):
    assert _tiene(analyze_page(analyzer, "Escaneo de iris para identificación biométrica"), "MX_BIOMETRICO")

# ══════════════════════════════════════════════════════════════════════════════
# MX_DIAGNOSTICO — términos médicos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_diagnostico_expediente_medico(analyzer):
    assert _tiene(analyze_page(analyzer, "Expediente médico: diabetes tipo 2 crónica"), "MX_DIAGNOSTICO")

def test_diagnostico_historial_clinico(analyzer):
    assert _tiene(analyze_page(analyzer, "Historial clínico con diagnóstico de asma bronquial"), "MX_DIAGNOSTICO")

def test_diagnostico_nota_medica(analyzer):
    assert _tiene(analyze_page(analyzer, "Nota médica: paciente con hipertensión arterial"), "MX_DIAGNOSTICO")

def test_diagnostico_internamiento(analyzer):
    assert _tiene(analyze_page(analyzer, "Internamiento por epilepsia refractaria"), "MX_DIAGNOSTICO")

def test_diagnostico_cirugia(analyzer):
    assert _tiene(analyze_page(analyzer, "Paciente post cirugía cardiopatía coronaria"), "MX_DIAGNOSTICO")

def test_diagnostico_discapacidad(analyzer):
    assert _tiene(analyze_page(analyzer, "Discapacidad motriz: artritis reumatoide severa"), "MX_DIAGNOSTICO")

def test_diagnostico_prescripcion(analyzer):
    assert _tiene(analyze_page(analyzer, "Prescripción médica para diabetes tipo 2"), "MX_DIAGNOSTICO")

# ══════════════════════════════════════════════════════════════════════════════
# MX_ORIGEN_ETNICO — términos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_origen_etnicidad(analyzer):
    assert _tiene(analyze_page(analyzer, "Etnicidad declarada: indígena nahua"), "MX_ORIGEN_ETNICO")

def test_origen_descendencia(analyzer):
    assert _tiene(analyze_page(analyzer, "Descendencia maya por línea materna"), "MX_ORIGEN_ETNICO")

def test_origen_pertenencia(analyzer):
    assert _tiene(analyze_page(analyzer, "Pertenencia a pueblo indígena zapoteca"), "MX_ORIGEN_ETNICO")

# ══════════════════════════════════════════════════════════════════════════════
# MX_PREFERENCIA_SEXUAL — términos faltantes
# ══════════════════════════════════════════════════════════════════════════════

def test_sexual_vida_intima(analyzer):
    assert _tiene(analyze_page(analyzer, "Vida íntima del declarante: homosexual"), "MX_PREFERENCIA_SEXUAL")

def test_sexual_conducta_sexual(analyzer):
    assert _tiene(analyze_page(analyzer, "Conducta sexual declarada en expediente: bisexual"), "MX_PREFERENCIA_SEXUAL")
