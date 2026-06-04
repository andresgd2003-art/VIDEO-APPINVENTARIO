"""
Smoke Testing — Hito Fase 1: LLM Auditor
=========================================
Verifica conectividad, fallback, latencia y parsing del modulo llm_auditor.
"""
import sys
import os
import time
import httpx
import pytest
from unittest.mock import patch

# Asegura que src/ este en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llm_auditor import check_ollama_health, audit_results, parse_llm_response

# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------
SAMPLE_RESULT = [
    {
        "entity_type": "MX_RFC_PF",
        "text": "GADA0307211L8",
        "start": 0,
        "end": 13,
        "score": 0.85,
    }
]


# ---------------------------------------------------------------------------
# 1. Conectividad
# ---------------------------------------------------------------------------
def test_conectividad_ollama():
    """Verifica que Ollama responde en localhost:11434."""
    result = check_ollama_health()
    if not result:
        pytest.skip("Ollama no disponible — se omite test de conectividad")
    assert result is True


# ---------------------------------------------------------------------------
# 2. Fallback cuando Ollama esta caido
# ---------------------------------------------------------------------------
def test_fallback_ollama_caido():
    """Cuando check_ollama_health retorna False, audit_results debe devolver
    los presidio_results originales sin modificacion (fallback activo)."""
    presidio_results = [
        {
            "entity_type": "MX_RFC_PF",
            "text": "GADA0307211L8",
            "start": 0,
            "end": 13,
            "score": 0.85,
        }
    ]

    with patch("llm_auditor.check_ollama_health", return_value=False):
        result = audit_results(
            text="GADA0307211L8 es un RFC de prueba",
            presidio_results=presidio_results,
        )

    assert result == presidio_results, (
        f"Se esperaba fallback con lista original, pero se obtuvo: {result}"
    )


# ---------------------------------------------------------------------------
# 3. Latencia base
# ---------------------------------------------------------------------------
def test_latencia_base():
    """Mide el tiempo de respuesta de Ollama con un prompt minimo.
    Acepta hasta 30 s (CPU puede ser lento)."""
    if not check_ollama_health():
        pytest.skip("Ollama no disponible — se omite test de latencia")

    start = time.time()
    try:
        with httpx.Client() as client:
            response = client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": "Hola",
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0),
            )
        elapsed = time.time() - start
        print(f"\n  [latencia] Ollama respondio en {elapsed:.2f}s")
        assert response.status_code == 200, f"Status inesperado: {response.status_code}"
        assert elapsed < 30.0, f"Latencia demasiado alta: {elapsed:.2f}s (limite 30s)"
    except httpx.TimeoutException as exc:
        elapsed = time.time() - start
        pytest.fail(f"Timeout despues de {elapsed:.2f}s: {exc}")


# ---------------------------------------------------------------------------
# 4. parse_llm_response — array valido
# ---------------------------------------------------------------------------
def test_parse_llm_response_array_valido():
    """Parsea correctamente un JSON array limpio."""
    raw = '[{"entity_type":"MX_CURP","text":"GADA030721HDGLZNA8","start":5,"end":23,"score":0.85}]'
    result = parse_llm_response(raw)
    assert result is not None, "Se esperaba lista, se obtuvo None"
    assert isinstance(result, list), f"Se esperaba list, se obtuvo {type(result)}"
    assert len(result) == 1, f"Se esperaba 1 elemento, se obtuvieron {len(result)}"
    item = result[0]
    assert item["entity_type"] == "MX_CURP"
    assert item["text"] == "GADA030721HDGLZNA8"
    assert item["start"] == 5
    assert item["end"] == 23
    assert item["score"] == 0.85


# ---------------------------------------------------------------------------
# 5. parse_llm_response — con fence markdown
# ---------------------------------------------------------------------------
def test_parse_llm_response_con_fence_markdown():
    """Parsea correctamente cuando el LLM envuelve el JSON en un fence markdown."""
    raw = '```json\n[{"entity_type":"MX_RFC_PF","text":"GADA0307211L8","start":0,"end":13,"score":0.85}]\n```'
    result = parse_llm_response(raw)
    assert result is not None, "Se esperaba lista, se obtuvo None"
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["entity_type"] == "MX_RFC_PF"
    assert result[0]["text"] == "GADA0307211L8"


# ---------------------------------------------------------------------------
# 6. parse_llm_response — texto vacio y None
# ---------------------------------------------------------------------------
def test_parse_llm_response_texto_vacio():
    """Texto vacio o None deben retornar None sin lanzar excepcion."""
    assert parse_llm_response("") is None, "Se esperaba None para string vacio"
    assert parse_llm_response(None) is None, "Se esperaba None para None"


# ---------------------------------------------------------------------------
# 7. parse_llm_response — JSON invalido
# ---------------------------------------------------------------------------
def test_parse_llm_response_json_invalido():
    """Texto sin JSON valido debe retornar None sin lanzar excepcion."""
    result = parse_llm_response("aqui no hay json valido")
    assert result is None, f"Se esperaba None para JSON invalido, se obtuvo: {result}"
