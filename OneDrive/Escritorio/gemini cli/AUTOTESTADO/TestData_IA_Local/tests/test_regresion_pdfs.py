"""
Suite de regresión sobre PDFs reales del proyecto.

Para cada PDF conocido, ejecuta el pipeline completo (extract_words → analyze
→ map_entities) UNA sola vez por módulo y verifica:

- True positives: identificadores que SÍ deben detectarse (RFC del CSF, CURP, etc.)
- True negatives: textos que NO deben redactarse (correos .gob.mx, servidores públicos,
  expedientes que parecen folios).

El propósito es detectar regresiones cuando se modifica el detector: si un cambio
hace que un dato real deje de detectarse, falla aquí.

Cada PDF se procesa una sola vez gracias a `scope="module"` en el fixture.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import pymupdf

import pdf_reader
from detector import build_analyzer, analyze_page
from mapper import map_entities


# ── Ubicación de los PDFs ──────────────────────────────────────────────────────

_RAIZ_PDFS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

PDFS = {
    "csf":            os.path.join(_RAIZ_PDFS, "csf.pdf"),
    "curp":           os.path.join(_RAIZ_PDFS, "curp.pdf"),
    "ilovepdf":       os.path.join(_RAIZ_PDFS, "ilovepdf_merged.pdf"),
    "sentencia_nl":   os.path.join(_RAIZ_PDFS, "Sentencia de Prueba NL.pdf"),
    "sentencia_robo": os.path.join(_RAIZ_PDFS, "Sentencia Penal Robo NL.pdf"),
}


@pytest.fixture(scope="session")
def analizador():
    return build_analyzer()


def _ejecutar_pipeline(ruta: str, analizador):
    """Devuelve (texto_completo, lista_entidades_mapeadas, info_doc)."""
    doc = pymupdf.open(ruta)
    texto_global = ""
    entidades_globales: list[dict] = []
    for page in doc:
        palabras = pdf_reader.extract_words(page)
        idx_esp  = pdf_reader.build_spatial_index(palabras, page)
        texto    = " ".join(e["word"] for e in idx_esp)
        presidio = analyze_page(analizador, texto)
        dicts    = [
            {"entity_type": r.entity_type, "text": texto[r.start:r.end],
             "start": r.start, "end": r.end, "score": r.score}
            for r in presidio
        ]
        ents = map_entities(idx_esp, dicts)
        entidades_globales.extend(ents)
        texto_global += " " + texto
    doc.close()
    return texto_global, entidades_globales


def _crear_fixture_pdf(clave: str):
    """Factory para construir fixtures perezosos por PDF (uno por módulo)."""
    def _fixture(analizador):
        ruta = PDFS[clave]
        if not os.path.exists(ruta):
            pytest.skip(f"PDF no disponible: {ruta}")
        return _ejecutar_pipeline(ruta, analizador)
    return _fixture


# Fixtures por PDF — uno se invoca por test pero el pipeline corre una sola vez
fix_csf            = pytest.fixture(scope="module")(_crear_fixture_pdf("csf"))
fix_curp           = pytest.fixture(scope="module")(_crear_fixture_pdf("curp"))
fix_sentencia_robo = pytest.fixture(scope="module")(_crear_fixture_pdf("sentencia_robo"))
fix_sentencia_nl   = pytest.fixture(scope="module")(_crear_fixture_pdf("sentencia_nl"))


# ── Helpers de aserción ────────────────────────────────────────────────────────

def _tipos(entidades):
    return {e["entity_type"] for e in entidades}


def _textos_de_tipo(entidades, tipo):
    return [e.get("text", "") for e in entidades if e["entity_type"] == tipo]


def _aparece_en_alguno(entidades, fragmento_buscado: str) -> bool:
    """True si algún texto de entidad contiene `fragmento_buscado` (case-insensitive)."""
    f = fragmento_buscado.lower()
    return any(f in (e.get("text") or "").lower() for e in entidades)


# ── csf.pdf — Constancia de Situación Fiscal SAT (Andrés Gallegos Díaz) ────────

class TestCsf:
    def test_detecta_rfc(self, fix_csf):
        _, entidades = fix_csf
        rfcs = _textos_de_tipo(entidades, "MX_RFC_PF")
        assert any("GADA0307211L8" in t for t in rfcs), \
            f"RFC GADA0307211L8 no detectado. RFCs detectados: {rfcs}"

    def test_detecta_curp(self, fix_csf):
        _, entidades = fix_csf
        curps = _textos_de_tipo(entidades, "MX_CURP")
        assert any("GADA030721HDGLZNA8" in t for t in curps), \
            f"CURP del CSF no detectada. CURPs: {curps}"

    def test_detecta_nombre_andres(self, fix_csf):
        _, entidades = fix_csf
        # Aparece el nombre del titular en alguna forma. En la CSF los campos
        # estructurados ("Nombre (s):", "Primer Apellido:") se detectan como
        # MX_NOMBRE; GLiNER/spaCy los daría como PERSON/Persona en texto corrido.
        nombres = [t for e in entidades
                   for t in [e.get("text", "")]
                   if e["entity_type"] in ("PERSON", "Persona", "MX_NOMBRE")]
        assert any("ANDRES" in t.upper() or "GALLEGOS" in t.upper() for t in nombres), \
            f"Nombre del titular no detectado. PERSON/Persona/MX_NOMBRE: {nombres}"

    def test_no_detecta_correo_sat_gob_mx(self, fix_csf):
        """denuncias@sat.gob.mx es correo institucional — no debe redactarse."""
        _, entidades = fix_csf
        emails = _textos_de_tipo(entidades, "MX_EMAIL")
        assert not any("sat.gob.mx" in (t or "").lower() for t in emails), \
            f"Correo gob.mx fue redactado: {emails}"

    def test_detecta_apellidos_completos(self, fix_csf):
        """Ambos apellidos (GALLEGOS y DIAZ) deben detectarse, no solo el nombre."""
        _, entidades = fix_csf
        nombres = [t.upper() for e in entidades
                   for t in [e.get("text", "")]
                   if e["entity_type"] in ("PERSON", "Persona", "MX_NOMBRE")]
        assert any("GALLEGOS" in t for t in nombres), \
            f"Primer apellido GALLEGOS no detectado: {nombres}"
        assert any("DIAZ" in t for t in nombres), \
            f"Segundo apellido DIAZ no detectado: {nombres}"

    def test_detecta_idcif(self, fix_csf):
        """El idCIF (identificador del documento) debe detectarse."""
        _, entidades = fix_csf
        assert _aparece_en_alguno(entidades, "20090149720"), \
            "idCIF 20090149720 no detectado"

    def test_no_redacta_telefonos_publicos_sat(self, fix_csf):
        """Los teléfonos públicos del SAT del pie no son datos personales."""
        _, entidades = fix_csf
        tels = _textos_de_tipo(entidades, "MX_TEL")
        assert not any("8852" in (t or "") for t in tels), \
            f"Teléfono público del SAT fue redactado: {tels}"

    def test_no_marca_fechas_administrativas_como_nacimiento(self, fix_csf):
        """Fechas de emisión / inicio de operaciones NO son fecha de nacimiento."""
        _, entidades = fix_csf
        fechas = _textos_de_tipo(entidades, "MX_FECHA_NAC")
        assert not any("2025" in (t or "") or "2020" in (t or "") for t in fechas), \
            f"Fecha administrativa marcada como nacimiento: {fechas}"


# ── curp.pdf — CURP impresa de prueba ──────────────────────────────────────────

class TestCurp:
    def test_detecta_curp(self, fix_curp):
        _, entidades = fix_curp
        curps = _textos_de_tipo(entidades, "MX_CURP")
        assert len(curps) >= 1, f"Se esperaba al menos 1 CURP. Detectados: {curps}"

    def test_curp_pasa_checksum(self, fix_curp):
        """La CURP detectada debe pasar el checksum oficial (no es un falso match)."""
        from validators import curp_valido
        _, entidades = fix_curp
        for t in _textos_de_tipo(entidades, "MX_CURP"):
            if t:
                assert curp_valido(t.strip()), f"CURP detectada falla checksum: {t!r}"


# ── Sentencia Penal Robo NL — múltiples identificadores ───────────────────────

class TestSentenciaRobo:
    def test_detecta_variedad_de_tipos(self, fix_sentencia_robo):
        """
        Sentencia Penal NL debe detectar al menos 5 tipos distintos de PII —
        no especificamos cuáles porque la CURP/RFC del documento son sintéticas
        y son rechazadas por checksum (comportamiento correcto). Lo importante es
        que el resto del pipeline siga capturando una variedad de identificadores.
        """
        _, entidades = fix_sentencia_robo
        tipos = _tipos(entidades)
        # Tipos esperados (subset razonable que debe estar presente)
        esperados_relevantes = {
            "MX_CP", "MX_DOMICILIO", "MX_TEL", "MX_PLACA", "MX_VIN",
            "MX_MONTO", "MX_EDAD", "MX_FECHA_NAC", "MX_EMAIL",
            "PERSON", "Persona",
        }
        encontrados = tipos & esperados_relevantes
        assert len(encontrados) >= 5, (
            f"Esperaba al menos 5 tipos relevantes detectados. "
            f"Encontrados: {encontrados}. Todos los tipos: {tipos}"
        )

    def test_detecta_personas(self, fix_sentencia_robo):
        _, entidades = fix_sentencia_robo
        tipos = _tipos(entidades)
        assert ("PERSON" in tipos) or ("Persona" in tipos), \
            f"Esperaba al menos un PERSON/Persona. Tipos: {tipos}"

    def test_servidores_publicos_no_detectados(self, fix_sentencia_robo):
        """Jueces, secretarios, agentes y oficiales NO deben aparecer como PERSON."""
        _, entidades = fix_sentencia_robo
        personas = _textos_de_tipo(entidades, "PERSON") + _textos_de_tipo(entidades, "Persona")
        # Frases conocidas que NO deben aparecer (servidores públicos del documento)
        BLACKLIST = ["Gerardo Macias", "Roberto Dominguez", "Karla Patricia Romero"]
        for nombre in BLACKLIST:
            for p in personas:
                if nombre.lower() in (p or "").lower():
                    pytest.fail(
                        f"Servidor público '{nombre}' fue marcado como dato personal: {p!r}"
                    )


# ── Sentencia de Prueba NL ─────────────────────────────────────────────────────

class TestSentenciaNl:
    def test_pipeline_no_falla(self, fix_sentencia_nl):
        """Smoke test: el pipeline completo termina sin excepciones."""
        texto, entidades = fix_sentencia_nl
        assert len(texto) > 100  # documento real, no vacío
        assert isinstance(entidades, list)

    def test_detecta_entidades_minimas(self, fix_sentencia_nl):
        _, entidades = fix_sentencia_nl
        assert len(entidades) >= 5, f"Demasiadas pocas entidades: {len(entidades)}"


# ── Falsos positivos globales ──────────────────────────────────────────────────

class TestFalsosPositivosGlobales:
    """Casos compartidos: ningún PDF debe detectar estos como datos personales."""

    @pytest.mark.parametrize("fix_name", ["fix_csf", "fix_sentencia_robo"])
    def test_no_estados_como_location(self, fix_name, request):
        """DURANGO, NUEVO LEON, etc. solos no son datos personales."""
        _, entidades = request.getfixturevalue(fix_name)
        locations = _textos_de_tipo(entidades, "LOCATION")
        ESTADOS_PUROS = {"durango", "nuevo leon", "nuevo león", "jalisco", "ciudad de mexico"}
        for loc in locations:
            if (loc or "").lower().strip() in ESTADOS_PUROS:
                pytest.fail(f"Estado puro marcado como LOCATION: {loc!r}")
