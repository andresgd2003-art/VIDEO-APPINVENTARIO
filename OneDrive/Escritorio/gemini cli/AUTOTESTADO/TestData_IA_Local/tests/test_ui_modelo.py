"""
Tests de comportamiento UI: carga de modelo NLP, estado de botones,
retry automático y flujo de análisis — sin abrir ventana real.

Estrategia: stub class que replica sólo la lógica de cola/threading de
ValidadorPDFApp sin heredar de CTk, evitando crashes de pymupdf en re-import.
"""
import sys
import os
import queue
import threading
import unittest.mock as mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
import detector  # importado una sola vez


# ── Stub con la lógica de carga de modelo extraída de ValidadorPDFApp ────────

class _AppStub:
    """
    Stub mínimo que replica los métodos de cola/modelo de ValidadorPDFApp
    sin depender de Tkinter/CTk. Permite probar la lógica de negocio pura.
    """

    def __init__(self):
        self._cola: queue.Queue = queue.Queue()
        self._analizador = None
        self._doc = None
        self._tipos_descartados: set = set()
        self._after_calls: list = []          # (ms, func) en vez de Tk.after
        self._estado_texto: str = ""          # en vez de CTkLabel
        self._btn_analizar_disabled: bool = False
        self._hilo_lote_iniciado: bool = False

    # ── Replicas exactas de los métodos de ValidadorPDFApp ────────────────

    def _hilo_init_analizador(self) -> None:
        try:
            analizador = detector.build_analyzer()
            self._cola.put(("analizador_listo", analizador))
        except Exception as exc:
            self._cola.put(("error_analizador", str(exc)))

    def _monitorear_cola_init(self) -> None:
        try:
            etiqueta, carga = self._cola.get_nowait()
            if etiqueta == "analizador_listo":
                self._analizador = carga
                self._estado_texto = "Sin analizar"
            elif etiqueta == "error_analizador":
                self._estado_texto = f"Error al cargar modelo: {carga}"
        except queue.Empty:
            self.after(200, self._monitorear_cola_init)

    def _on_click_analizar_todo(self) -> None:
        if self._doc is None:
            return
        if self._analizador is None:
            self._estado_texto = "⏳ Cargando modelo NLP, por favor espere…"
            self.after(500, self._on_click_analizar_todo)
            return
        self._btn_analizar_disabled = True
        self._estado_texto = "Analizando documento…"
        self._hilo_lote_iniciado = True

    def after(self, ms: int, func=None, *args):
        """Simula Tk.after: acumula callbacks sin ejecutarlas."""
        if func:
            self._after_calls.append((ms, func))
        return len(self._after_calls)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_analizador_inicia_en_none():
    """_analizador debe ser None al construir — carga en hilo separado."""
    app = _AppStub()
    assert app._analizador is None


def test_hilo_init_pone_analizador_en_cola():
    """_hilo_init_analizador pone ('analizador_listo', obj) en la cola."""
    app = _AppStub()
    fake = object()
    with mock.patch.object(detector, "build_analyzer", return_value=fake):
        app._hilo_init_analizador()
    msg = app._cola.get_nowait()
    assert msg == ("analizador_listo", fake)


def test_hilo_init_pone_error_en_cola_si_falla():
    """Si build_analyzer lanza, llega ('error_analizador', msg) a la cola."""
    app = _AppStub()
    with mock.patch.object(detector, "build_analyzer", side_effect=RuntimeError("sin GPU")):
        app._hilo_init_analizador()
    msg = app._cola.get_nowait()
    assert msg[0] == "error_analizador"
    assert "sin GPU" in msg[1]


def test_monitorear_cola_asigna_analizador():
    """_monitorear_cola_init asigna _analizador cuando llega analizador_listo."""
    app = _AppStub()
    fake = object()
    app._cola.put(("analizador_listo", fake))
    app._monitorear_cola_init()
    assert app._analizador is fake


def test_monitorear_cola_reintenta_si_vacia():
    """Cola vacía → registra after(200, ...) para reintentar."""
    app = _AppStub()
    app._monitorear_cola_init()
    assert len(app._after_calls) == 1
    assert app._after_calls[0][0] == 200


def test_monitorear_cola_muestra_error():
    """Si llega error_analizador, el estado refleja el mensaje de error."""
    app = _AppStub()
    app._cola.put(("error_analizador", "modelo no encontrado"))
    app._monitorear_cola_init()
    assert "Error" in app._estado_texto or "modelo no encontrado" in app._estado_texto


def test_analizar_sin_modelo_programa_reintento():
    """
    Click antes de que cargue el modelo → mensaje de espera + after(500).
    Reproduce el bug original: la UI se quedaba bloqueada sin reintentar.
    """
    app = _AppStub()
    app._doc = mock.MagicMock()
    app._analizador = None

    app._on_click_analizar_todo()

    assert "espere" in app._estado_texto.lower() or "cargando" in app._estado_texto.lower()
    retries_500 = [c for c in app._after_calls if c[0] == 500]
    assert len(retries_500) >= 1, "Debe programar reintento en 500ms"


def test_analizar_sin_doc_no_hace_nada():
    """Sin documento cargado, _on_click_analizar_todo no modifica el estado."""
    app = _AppStub()
    app._doc = None
    app._analizador = object()

    estado_inicial = app._estado_texto
    app._on_click_analizar_todo()

    assert app._estado_texto == estado_inicial
    assert len(app._after_calls) == 0


def test_analizar_con_modelo_listo_lanza_analisis():
    """Con doc y analizador, debe marcar botón como disabled y lanzar análisis."""
    app = _AppStub()
    app._doc = mock.MagicMock()
    app._analizador = object()

    app._on_click_analizar_todo()

    assert app._btn_analizar_disabled is True
    assert app._hilo_lote_iniciado is True
    assert "Analizando" in app._estado_texto


def test_retry_loop_termina_cuando_modelo_carga():
    """
    Simula: click → None → retry programado → modelo llega → análisis sin más retries.
    """
    app = _AppStub()
    app._doc = mock.MagicMock()
    app._analizador = None

    # Primer click — modelo aún no listo
    app._on_click_analizar_todo()
    assert len([c for c in app._after_calls if c[0] == 500]) == 1

    # Simular que el modelo cargó
    app._analizador = object()
    app._after_calls.clear()

    # Ejecutar el retry que se había programado
    app._on_click_analizar_todo()

    # No debe haber nuevos retries de 500ms — el análisis debe proceder
    nuevos_500 = [c for c in app._after_calls if c[0] == 500]
    assert len(nuevos_500) == 0, "Con modelo listo no debe haber más retries"
    assert app._hilo_lote_iniciado is True


def test_multiples_retries_hasta_modelo():
    """
    El loop puede reintentar N veces hasta que el modelo esté disponible.
    Cada intento fallido debe registrar exactamente 1 after(500).
    """
    app = _AppStub()
    app._doc = mock.MagicMock()
    app._analizador = None

    for intento in range(1, 4):
        app._after_calls.clear()
        app._on_click_analizar_todo()
        assert len([c for c in app._after_calls if c[0] == 500]) == 1, \
            f"Intento {intento}: debe haber exactly 1 retry programado"


def test_carga_modelo_en_hilo_separado_no_bloquea():
    """
    _hilo_init_analizador debe ejecutarse en un thread y completar en <5s.
    Verifica que la carga del modelo no bloquea el hilo principal.
    """
    app = _AppStub()
    fake = object()
    completado = threading.Event()

    def _hilo():
        with mock.patch.object(detector, "build_analyzer", return_value=fake):
            app._hilo_init_analizador()
        completado.set()

    t = threading.Thread(target=_hilo, daemon=True)
    t.start()
    resultado = completado.wait(timeout=5.0)

    assert resultado, "El hilo de carga no completó en 5 segundos"
    msg = app._cola.get_nowait()
    assert msg[0] == "analizador_listo"
