"""
Fase 2: Calibracion Linguistica y de Rol del LLM Auditor
Llama al LLM REAL via Ollama — no mocks.
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llm_auditor import audit_results, build_audit_prompt


# ---------------------------------------------------------------------------
# Helper: objeto que simula un RecognizerResult de Presidio
# ---------------------------------------------------------------------------
class FakeResult:
    def __init__(self, entity_type: str, start: int, end: int, score: float):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score


# ---------------------------------------------------------------------------
# Fixture: saltar tests si Ollama no esta disponible
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def skip_if_ollama_down():
    from llm_auditor import check_ollama_health
    if not check_ollama_health():
        pytest.skip("Ollama no disponible")


# ---------------------------------------------------------------------------
# Test 1: El LLM no debe inventar entidades cuando Presidio no detecto ninguna
# ---------------------------------------------------------------------------
def test_alucinacion_documento_sin_pii():
    text = "El cielo es azul. Los pajaros vuelan alto. El sol sale cada manana."
    result = audit_results(text, [])
    assert result == [], (
        f"El LLM alucinó entidades inexistentes: {result}"
    )


# ---------------------------------------------------------------------------
# Test 2: El output del LLM siempre debe ser JSON parseable con las claves correctas
# ---------------------------------------------------------------------------
def test_formato_json_obligatorio():
    text = "RFC: GADA0307211L8, CURP: GADA030721HDGLZNA8"
    presidio_results = [
        FakeResult("RFC",  5, 18, 0.85),
        FakeResult("CURP", 26, 44, 0.90),
    ]
    result = audit_results(text, presidio_results)

    assert isinstance(result, list), (
        f"Se esperaba lista, se obtuvo {type(result)}: {result}"
    )

    required_keys = {"entity_type", "text", "start", "end", "score"}
    for item in result:
        missing = required_keys - set(item.keys())
        assert not missing, f"Item {item} le faltan claves: {missing}"


# ---------------------------------------------------------------------------
# Test 3: build_audit_prompt debe contener los candidatos y la instruccion JSON
# ---------------------------------------------------------------------------
def test_build_prompt_contiene_candidatos():
    text = "Nombre: Juan Perez, RFC: PEPJ800101XX9"
    presidio_results = [
        FakeResult("PERSON", 8,  18, 0.92),
        FakeResult("RFC",   24, 38, 0.87),
    ]
    prompt = build_audit_prompt(text, presidio_results)

    assert "PERSON" in prompt, "El prompt no contiene el entity_type PERSON"
    assert "RFC" in prompt,    "El prompt no contiene el entity_type RFC"
    assert "JSON" in prompt,   "El prompt no contiene la instruccion de formato JSON"
    assert len(prompt) > 200,  f"El prompt parece demasiado corto: {len(prompt)} chars"


# ---------------------------------------------------------------------------
# Test 4: build_audit_prompt debe mencionar el rol juridico del auditor
# ---------------------------------------------------------------------------
def test_build_prompt_rol_juridico():
    prompt = build_audit_prompt("texto de prueba", [])

    terminos_juridicos = ["LGTAIP", "LGPDPPSO", "datos personales"]
    encontrado = any(t in prompt for t in terminos_juridicos)
    assert encontrado, (
        f"El prompt no menciona ningun termino juridico esperado "
        f"({terminos_juridicos}). Prompt actual:\n{prompt[:500]}"
    )


# ---------------------------------------------------------------------------
# Test 5: Con temperature=0 y seed=42, dos llamadas identicas deben dar el mismo resultado
# ---------------------------------------------------------------------------
def test_temperatura_cero_determinismo():
    text = "Mi nombre es Carlos Lopez y mi RFC es LOCR850312AB1."
    presidio_results = [
        FakeResult("PERSON", 14, 27, 0.91),
        FakeResult("RFC",   39, 52, 0.88),
    ]

    timeout_per_call = 60  # segundos

    t0 = time.time()
    result1 = audit_results(text, presidio_results)
    elapsed1 = time.time() - t0
    if elapsed1 > timeout_per_call:
        pytest.skip(f"Primera llamada tardó {elapsed1:.1f}s > {timeout_per_call}s")

    t0 = time.time()
    result2 = audit_results(text, presidio_results)
    elapsed2 = time.time() - t0
    if elapsed2 > timeout_per_call:
        pytest.skip(f"Segunda llamada tardó {elapsed2:.1f}s > {timeout_per_call}s")

    assert result1 == result2, (
        f"LLM no fue determinista con temperature=0.\n"
        f"Resultado 1: {result1}\n"
        f"Resultado 2: {result2}"
    )
