# -*- coding: utf-8 -*-
"""
Tests de detección integral sobre tests/fixtures/documento_prueba_integral.pdf.

Verifica que la herramienta ANONIMA detecta automáticamente todos los tipos
de entidad que deben redactarse en documentos oficiales mexicanos.

Nota sobre Juez / Secretario: son servidores públicos en ejercicio de sus
funciones; la LGTAIP no requiere redactar sus datos en documentos públicos.
El pipeline los filtra intencionalmente en _filtrar_falsos_positivos línea 430.
Por lo tanto NO están en la lista de entidades esperadas.
"""
import os
import sys
import pytest
import pymupdf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pdf_reader
import detector
import mapper
import qr_detector

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "documento_prueba_integral.pdf")

# ── Tipos de entidad esperados (todos los que la herramienta debe detectar) ──
# Se dividen en HARD (regex-based, deben detectarse siempre) y
# SOFT (NLP-based, dependientes del modelo — marcar xfail si fallan)

TIPOS_HARD = {
    # Identificadores oficiales
    "MX_CURP", "MX_RFC_PF", "MX_RFC_PM", "MX_INE", "MX_NSS",
    "MX_PASAPORTE", "MX_IDCIF", "MX_CRIP",
    # Contacto
    "MX_EMAIL", "MX_TEL",
    # Financiero / patrimonial
    "MX_CLABE", "MX_TARJETA", "MX_CUENTA", "MX_MONTO",
    "MX_PLACA", "MX_VIN",
    # Biográficos / temporales
    "MX_FECHA_NAC", "MX_EDAD", "MX_SEXO", "MX_LUGAR_NAC", "MX_NACIONALIDAD",
    # Domicilio
    "MX_CP", "MX_DOMICILIO",
    # Datos sensibles (regex con contexto)
    "MX_DIAGNOSTICO", "MX_ORIGEN_ETNICO", "MX_RELIGION",
    "MX_OPINION_POLITICA", "MX_PREFERENCIA_SEXUAL", "MX_BIOMETRICO",
    # Visual / imagen
    "MX_QR",
}

TIPOS_SOFT = {
    # NLP / GLiNER — detectados en la mayoría de ejecuciones pero pueden variar
    "Persona",   # nombre de persona física (GLiNER zero-shot)
    "Menor",     # nombre de menor de edad (GLiNER zero-shot)
    "Diagnóstico",  # diagnóstico (GLiNER, alternativo a MX_DIAGNOSTICO)
}


@pytest.fixture(scope="module")
def resultados(tmp_path_factory):
    """Ejecuta el pipeline completo sobre el documento integral una sola vez."""
    if not os.path.exists(FIXTURE):
        pytest.skip(f"Fixture no encontrada: {FIXTURE}")

    analizador = detector._analyzer_singleton or detector.build_analyzer()
    doc = pymupdf.open(FIXTURE)
    todos: dict[str, list[str]] = {}

    for i in range(doc.page_count):
        page = doc[i]
        palabras = pdf_reader.extract_words(page)
        idx = pdf_reader.build_spatial_index(palabras, page)
        texto = " ".join(e["word"] for e in idx)

        presidio = detector.analyze_page(analizador, texto)
        dicts_p = [
            {
                "entity_type": r.entity_type,
                "text":        texto[r.start:r.end],
                "start":       r.start,
                "end":         r.end,
                "score":       r.score,
            }
            for r in presidio
        ]
        mapeado = mapper.map_entities(idx, dicts_p)
        qr_ents = qr_detector.detectar_qr(page)

        for ent in mapeado + qr_ents:
            todos.setdefault(ent["entity_type"], []).append(ent["text"][:60])

    doc.close()
    return todos


# ── Tests individuales por tipo (hard — deben pasar siempre) ─────────────────

@pytest.mark.parametrize("tipo", sorted(TIPOS_HARD))
def test_tipo_hard_detectado(resultados, tipo):
    """Cada tipo de entidad hard debe aparecer al menos una vez."""
    assert tipo in resultados, (
        f"Entidad '{tipo}' NO detectada en documento_prueba_integral.pdf.\n"
        f"Tipos detectados: {sorted(resultados.keys())}"
    )


# ── Tests individuales por tipo (soft — xfail si el modelo no lo retorna) ────

@pytest.mark.parametrize("tipo", sorted(TIPOS_SOFT))
@pytest.mark.xfail(strict=False, reason="Entidad NLP/GLiNER: su detección depende del modelo")
def test_tipo_soft_detectado(resultados, tipo):
    assert tipo in resultados


# ── Test de cobertura global ──────────────────────────────────────────────────

def test_cobertura_minima(resultados):
    """Al menos 30 tipos distintos deben ser detectados (umbral de regresión)."""
    assert len(resultados) >= 30, (
        f"Solo se detectaron {len(resultados)} tipos. "
        f"Detectados: {sorted(resultados.keys())}"
    )


def test_qr_decodifica_contenido(resultados):
    """El QR debe contener CURP o RFC del titular."""
    assert "MX_QR" in resultados, "MX_QR no detectado"
    textos_qr = " ".join(resultados["MX_QR"]).upper()
    assert "CURP" in textos_qr or "RFC" in textos_qr or "GADA" in textos_qr, (
        f"QR detectado pero no contiene CURP/RFC esperado: {resultados['MX_QR']}"
    )


def test_curp_valor_correcto(resultados):
    """La CURP detectada debe ser la real del titular."""
    assert "MX_CURP" in resultados
    curps = " ".join(resultados["MX_CURP"])
    assert "GADA030721HDGLZNA8" in curps


def test_rfc_pf_valor_correcto(resultados):
    assert "MX_RFC_PF" in resultados
    rfcs = " ".join(resultados["MX_RFC_PF"])
    assert "GADA0307211L8" in rfcs


def test_clabe_valor_correcto(resultados):
    """La CLABE detectada debe ser la del documento (18 dígitos, checksum válido)."""
    assert "MX_CLABE" in resultados
    clabes = " ".join(resultados["MX_CLABE"])
    assert "014200012345678900" in clabes


def test_juez_secretario_no_detectados(resultados):
    """Juez y Secretario son servidores públicos → no deben redactarse (filtro intencional)."""
    assert "Juez" not in resultados, (
        "El tipo 'Juez' no debe aparecer: servidores públicos son filtrados por diseño"
    )
    assert "Secretario" not in resultados, (
        "El tipo 'Secretario' no debe aparecer: servidores públicos son filtrados por diseño"
    )
