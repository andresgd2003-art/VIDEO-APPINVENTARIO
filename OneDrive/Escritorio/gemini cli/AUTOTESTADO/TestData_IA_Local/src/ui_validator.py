import ctypes
import json
import logging
import os
import queue
import sys
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata
from tkinter import filedialog, messagebox

# Prevenir 'RuntimeError: Already borrowed' del tokenizer de HuggingFace en modo multihilo
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Modo OFFLINE de HuggingFace: usa los modelos ya descargados en caché y NO intenta
# contactar a la red. Sin esto, en equipos sin internet/DNS la carga de GLiNER lanza
# "[Errno 11001] getaddrinfo failed". setdefault permite forzar online con la env var.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Declarar proceso DPI-aware ANTES de que Tkinter cree cualquier ventana.
# Sin esto, Windows escala la ventana internamente y las coordenadas del canvas
# quedan en píxeles lógicos mientras PhotoImage opera en píxeles físicos,
# produciendo desalineación visible entre los recuadros dibujados y el texto.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI aware v1
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import customtkinter as ctk
import pymupdf
from PIL import Image, ImageTk

import pdf_reader

# detector, mapper y audit se importan de forma lazy en los métodos que los necesitan
# para evitar que la UI se trabe si presidio/gliner no están instalados
_detector = None
_mapper = None
_audit = None
_qr = None

def _get_qr():
    global _qr
    if _qr is None:
        import qr_detector as _q
        _qr = _q
    return _qr

def _get_detector():
    global _detector
    if _detector is None:
        import detector as _d
        _detector = _d
    return _detector

def _get_mapper():
    global _mapper
    if _mapper is None:
        import mapper as _m
        _mapper = _m
    return _mapper

def _get_audit():
    global _audit
    if _audit is None:
        import audit as _a
        _audit = _a
    return _audit

try:
    from sanitizer import sanitize_page
    TIENE_SANITIZER = True
except ImportError:
    TIENE_SANITIZER = False

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
ctk.deactivate_automatic_dpi_awareness()

ZOOM = 1.25

# Normalización de alias GLiNER → tipo canónico Presidio/MX.
# Previene filas duplicadas en el acta cuando ambos detectores reconocen el mismo dato
# con spans de distinta longitud (el overlap resolver no los elimina si no se solapan).
_ALIAS_TIPOS: dict[str, str] = {
    "Diagnóstico": "MX_DIAGNOSTICO",
}

COLORES_ENTIDAD: dict[str, str] = {
    # ── Identidad de la persona (nombre + datos de nacimiento/identidad básica) ──
    "PERSON":         "#e67e22",
    "Persona":        "#e67e22",
    "MX_NOMBRE":      "#e67e22",
    "Menor":          "#e67e22",
    "MX_LUGAR_NAC":   "#e67e22",
    "MX_FECHA_NAC":   "#e67e22",
    "MX_EDAD":        "#e67e22",
    "MX_SEXO":        "#e67e22",
    "MX_NACIONALIDAD":"#e67e22",
    # ── Identificadores oficiales ──────────────────────────────────────────────
    "MX_CURP":        "#c0392b",
    "MX_RFC_PF":      "#c0392b",
    "MX_RFC_PM":      "#c0392b",
    "MX_INE":         "#c0392b",
    "MX_INE_FOLIO":   "#c0392b",
    "MX_IDCIF":       "#c0392b",
    "MX_CRIP":        "#c0392b",
    "MX_PASAPORTE":   "#c0392b",
    "MX_NSS":         "#c0392b",
    # ── Contacto y domicilio ───────────────────────────────────────────────────
    "MX_TEL":         "#2980b9",
    "MX_EMAIL":       "#2980b9",
    "MX_CP":          "#2980b9",
    "MX_DOMICILIO":   "#2980b9",
    "MX_COLONIA":     "#2980b9",
    "MX_ENTIDAD_REGISTRO": "#2980b9",
    "LOCATION":       "#2980b9",
    # ── Patrimonial / financiero ───────────────────────────────────────────────
    "MX_CLABE":       "#8e44ad",
    "MX_TARJETA":     "#8e44ad",
    "MX_CUENTA":      "#8e44ad",
    "MX_MONTO":       "#8e44ad",
    # ── Vehículo / tránsito ────────────────────────────────────────────────────
    "MX_PLACA":       "#1a5276",
    "MX_VIN":         "#1a5276",
    # ── Académico / laboral ────────────────────────────────────────────────────
    "MX_ESCOLAR":     "#b9770e",
    # ── Datos sensibles (cada categoría con color propio) ──────────────────────
    "MX_DIAGNOSTICO": "#e74c3c",   # Salud
    "Diagnóstico":    "#e74c3c",   # Salud (GLiNER) — mismo concepto, mismo color
    "MX_ORIGEN_ETNICO": "#a93226", # Origen étnico/racial
    "MX_RELIGION":    "#7d3c98",   # Creencias religiosas
    "MX_OPINION_POLITICA": "#16a085",  # Opinión política / afiliación
    "MX_PREFERENCIA_SEXUAL": "#d81b60",# Preferencia sexual
    "MX_BIOMETRICO":  "#d35400",   # Datos biométricos
    # ── Elementos visuales (firma, QR y códigos de barra) ──────────────────────
    "MX_FIRMA":       "#34495e",
    "MX_QR":          "#34495e",
    # ── Servidores públicos (informativo — NO se testan) ───────────────────────
    "Juez":           "#7f8c8d",
    "Secretario":     "#7f8c8d",
    # ── Marcado manual / otro ──────────────────────────────────────────────────
    "MANUAL":         "#95a5a6",
}
COLOR_DEFAULT = "#d4ac0d"
COLOR_DESELECCIONADO = "#aaaaaa"
COLOR_MANUAL = "#8e44ad"

# ── Sistema de diseño "Institucional Moderno" ────────────────────────────────
FONT_FAMILY = "Segoe UI Variable"

COL_APP_BG      = "#F8FAFC"   # Slate 50  — fondo de la aplicación
COL_PANEL       = "#FFFFFF"   # Blanco    — panel derecho / tarjetas
COL_HEADER      = "#0F172A"   # Slate 900 — encabezado superior
COL_CANVAS      = "#E2E8F0"   # Slate 200 — fondo del visor PDF
COL_TEXT        = "#1E293B"   # Slate 800 — texto principal
COL_TEXT2       = "#64748B"   # Slate 500 — texto secundario
COL_BORDER      = "#CBD5E1"   # Slate 300 — bordes
COL_BORDER_SOFT = "#E2E8F0"   # Slate 200 — separadores suaves
COL_CARD_SOFT   = "#F1F5F9"   # Slate 100 — tarjetas/hover suaves

# Estilos de botón (se expanden con ** en las llamadas a CTkButton)
BTN_PRIMARY = dict(
    fg_color="#0369A1", hover_color="#0284C7", text_color="#FFFFFF", corner_radius=8,
)
BTN_SECONDARY = dict(
    fg_color="#FFFFFF", hover_color=COL_CARD_SOFT, text_color="#334155",
    border_width=1, border_color=COL_BORDER, corner_radius=8,
)
BTN_GRAY = dict(
    fg_color="#64748B", hover_color="#475569", text_color="#FFFFFF", corner_radius=8,
    border_width=0
)
BTN_DANGER = dict(
    fg_color="#B91C1C", hover_color="#991B1B", text_color="#FFFFFF", corner_radius=8,
)

# Opciones del selector de tipo de dato en modo manual (label → entity_type)
OPCIONES_TIPO_MANUAL: dict[str, str] = {
    "Nombre / Persona":   "PERSON",
    "CURP":               "MX_CURP",
    "RFC":                "MX_RFC_PF",
    "NSS / IMSS":         "MX_NSS",
    "INE / Credencial":   "MX_INE",
    "Pasaporte":          "MX_PASAPORTE",
    "Domicilio":          "MX_DOMICILIO",
    "Teléfono":           "MX_TEL",
    "Correo electrónico": "MX_EMAIL",
    "Diagnóstico / Salud":"MX_DIAGNOSTICO",
    "Origen Étnico":      "MX_ORIGEN_ETNICO",
    "Religión":           "MX_RELIGION",
    "Opinión Política":   "MX_OPINION_POLITICA",
    "Preferencia Sexual": "MX_PREFERENCIA_SEXUAL",
    "Biométrico":         "MX_BIOMETRICO",
    "Dato escolar":       "MX_ESCOLAR",
    "Firma":              "MX_FIRMA",
    "Código QR":          "MX_QR",
    "Bancario / CLABE":   "MX_CLABE",
    "Otro dato personal": "MANUAL",
    "Personalizado...":   "CUSTOM",
}
_LABEL_A_ET: dict[str, str] = OPCIONES_TIPO_MANUAL  # alias legible en el código
_ET_A_LABEL: dict[str, str] = {v: k for k, v in OPCIONES_TIPO_MANUAL.items()}


class ValidadorPDFApp(ctk.CTk):

    _ZOOM_MIN  = 0.5
    _ZOOM_MAX  = 4.0
    _ZOOM_PASO = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.title("ANONIMA — Validador de Datos Personales en PDF")
        self.geometry("1280x800")

        self._doc: pymupdf.Document | None = None
        self._ruta_pdf: str = ""
        self._pagina_actual: int = 0
        self._analizador = None
        self._resultados_por_pagina: dict[int, list[dict]] = {}
        self._rects_manuales: list[dict] = []
        self._tipo_manual: str = "MANUAL"  # entity_type activo en modo marcado manual
        self._lista_descarte: list[str] = []  # textos que el usuario quiere ignorar
        self._foto: ImageTk.PhotoImage | None = None
        self._img_base: Image.Image | None = None
        self._cola: queue.Queue = queue.Queue()
        self._modo_manual: bool = False
        self._drag_inicio: tuple[int, int] | None = None
        self._id_rect_temporal: int | None = None
        self._error_modelo: str | None = None  # se llena si build_analyzer falla
        self._zoom: float = ZOOM           # zoom dinámico del preview (reemplaza constante ZOOM)
        self._modelo_carga_seg: int = 0    # contador de segundos esperando al modelo
        self._analisis_en_curso: bool = False # Evita crasheos bloqueando navegación durante análisis

        # ── Estado de resize interactivo ──────────────────────────────────
        # Permite agrandar/reducir un recuadro arrastrando sus esquinas.
        self._resize_target: dict | None = None       # entidad/rm siendo redimensionado
        self._resize_corner: str | None = None        # 'tl','tr','bl','br'
        self._resize_rect_idx: int | None = None      # índice del rect dentro de entidad["rects"]
        self._resize_es_manual: bool = False          # True→rm, False→entidad automática

        self._construir_ui()

        threading.Thread(target=self._hilo_init_analizador, daemon=True).start()
        self.after(200, self._monitorear_cola_init)
        self.after(1000, self._pulso_carga_modelo)

    # ------------------------------------------------------------------ UI

    # ------------------------------------------------------------------ helpers UI
    @staticmethod
    def _seccion(parent, titulo: str) -> None:
        """Encabezado de sección con línea divisoria (estilo Institucional Moderno)."""
        ctk.CTkLabel(
            parent, text=titulo.upper(),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COL_TEXT2,
        ).pack(pady=(15, 2), padx=20, anchor="w")
        ctk.CTkFrame(parent, height=1, fg_color=COL_BORDER_SOFT).pack(fill="x", padx=20, pady=(0, 8))

    def _construir_ui(self) -> None:
        self.configure(fg_color=COL_APP_BG)
        self.grid_rowconfigure(0, weight=0)   # encabezado
        self.grid_rowconfigure(1, weight=1)   # cuerpo
        self.grid_columnconfigure(0, weight=1)

        # ── Encabezado superior (full width, Slate 900) ──────────────────
        header = ctk.CTkFrame(self, height=50, fg_color=COL_HEADER, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header, text="ANONIMA — Validador de Datos Personales",
            font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
            text_color="#FFFFFF",
        ).pack(side="left", padx=20)

        # ── Cuerpo: visor (izq.) + controles (der.) ──────────────────────
        body = ctk.CTkFrame(self, fg_color=COL_APP_BG, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)              # visor expande
        body.grid_columnconfigure(1, weight=0, minsize=400) # panel fijo 400px

        # ── Panel izquierdo: canvas PDF ──────────────────────────────────
        marco_canvas = ctk.CTkFrame(body, fg_color=COL_CANVAS, corner_radius=0)
        marco_canvas.grid(row=0, column=0, sticky="nsew")
        marco_canvas.grid_rowconfigure(0, weight=1)
        marco_canvas.grid_columnconfigure(0, weight=1)
        marco_canvas.grid_rowconfigure(1, weight=0)
        marco_canvas.grid_rowconfigure(2, weight=0)

        self._canvas = tk.Canvas(marco_canvas, bg=COL_CANVAS, highlightthickness=0, bd=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        barra_v = ctk.CTkScrollbar(marco_canvas, command=self._canvas.yview)
        barra_v.grid(row=0, column=1, sticky="ns")
        barra_h = ctk.CTkScrollbar(marco_canvas, orientation="horizontal", command=self._canvas.xview)
        barra_h.grid(row=1, column=0, sticky="ew")
        self._canvas.configure(yscrollcommand=barra_v.set, xscrollcommand=barra_h.set)

        self._canvas.bind("<MouseWheel>",      self._on_scroll)
        self._canvas.bind("<Button-4>",        lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>",        lambda e: self._canvas.yview_scroll(1,  "units"))
        self._canvas.bind("<ButtonPress-1>",   self._on_canvas_press)
        self._canvas.bind("<B1-Motion>",       self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self._canvas.bind("<Control-MouseWheel>", self._on_ctrl_scroll)
        self._canvas.bind("<Motion>",          self._on_canvas_motion)

        # ── Atajos de teclado ──
        self.bind("+", self._on_key_zoom_in)
        self.bind("-", self._on_key_zoom_out)
        self.bind("<KP_Add>", self._on_key_zoom_in)
        self.bind("<KP_Subtract>", self._on_key_zoom_out)
        self.bind("<Left>", self._on_key_nav_prev)
        self.bind("<Right>", self._on_key_nav_sig)
        self.bind("<Up>", self._on_key_scroll_up)
        self.bind("<Down>", self._on_key_scroll_down)

        # ── Barra de zoom (inferior izquierda del canvas, tarjeta blanca) ─
        barra_zoom = ctk.CTkFrame(
            marco_canvas, fg_color=COL_PANEL, corner_radius=8,
            border_width=1, border_color=COL_BORDER,
        )
        barra_zoom.grid(row=2, column=0, sticky="w", padx=12, pady=8)

        ctk.CTkButton(
            barra_zoom, text="🔍−", width=40, height=28,
            command=self._zoom_out,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13), **BTN_SECONDARY,
        ).pack(side="left", padx=(6, 2), pady=4)

        self._lbl_zoom = ctk.CTkLabel(
            barra_zoom, text=f"{int(ZOOM * 100)}%",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COL_TEXT, width=48,
        )
        self._lbl_zoom.pack(side="left", padx=2)

        ctk.CTkButton(
            barra_zoom, text="🔍+", width=40, height=28,
            command=self._zoom_in,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13), **BTN_SECONDARY,
        ).pack(side="left", padx=(2, 6), pady=4)

        # ── Panel derecho: controles (ancho fijo 400px, blanco) ──────────
        derecho = ctk.CTkScrollableFrame(body, width=400, fg_color=COL_PANEL, corner_radius=0)
        derecho.grid(row=0, column=1, sticky="nsew")

        # ── Sección: Archivo ──
        self._seccion(derecho, "Archivo")

        self._etiqueta_archivo = ctk.CTkLabel(
            derecho, text="Sin archivo cargado",
            wraplength=340, justify="left",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13), text_color=COL_TEXT,
        )
        self._etiqueta_archivo.pack(pady=(0, 8), padx=20, fill="x")

        self._btn_cargar = ctk.CTkButton(
            derecho, text="  Cargar PDF",
            command=self._on_click_cargar, state="normal",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"), height=38,
            **BTN_SECONDARY,
        )
        self._btn_cargar.pack(pady=(0, 6), padx=20, fill="x")

        # Navegación de páginas
        nav = ctk.CTkFrame(derecho, fg_color=COL_CARD_SOFT, corner_radius=8)
        nav.pack(pady=6, padx=20, fill="x")
        self._btn_prev = ctk.CTkButton(
            nav, text="‹", width=36, height=30,
            command=lambda: self._navegar(-1), state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16), **BTN_SECONDARY,
        )
        self._btn_prev.pack(side="left", padx=(6, 2), pady=6)
        self._etiqueta_pagina = ctk.CTkLabel(
            nav, text="Página — de —",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13), text_color=COL_TEXT,
        )
        self._etiqueta_pagina.pack(side="left", expand=True)
        self._btn_sig = ctk.CTkButton(
            nav, text="›", width=36, height=30,
            command=lambda: self._navegar(1), state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16), **BTN_SECONDARY,
        )
        self._btn_sig.pack(side="right", padx=(2, 6), pady=6)

        # ── Sección: Análisis ──
        self._seccion(derecho, "Análisis")

        self._btn_analizar_todo = ctk.CTkButton(
            derecho, text="  Analizar todas las páginas",
            command=self._on_click_analizar_todo, state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"), height=38,
            **BTN_PRIMARY,
        )
        self._btn_analizar_todo.pack(pady=(0, 6), padx=20, fill="x")

        self._barra_progreso = ctk.CTkProgressBar(
            derecho, progress_color="#0369A1", fg_color=COL_CARD_SOFT,
        )
        # Se empaca dinámicamente

        self._etiqueta_estado = ctk.CTkLabel(
            derecho, text="  Cargando modelo NLP…",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COL_TEXT2,
            anchor="w",
        )
        self._etiqueta_estado.pack(pady=(0, 4), padx=20, fill="x")

        # ── Sección: Marcado manual ──
        self._seccion(derecho, "Marcado manual")

        ctk.CTkLabel(
            derecho,
            text="Arrastra sobre el PDF para marcar\ntexto que el sistema no detectó",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COL_TEXT2, justify="left",
        ).pack(pady=(0, 6), padx=20, anchor="w")

        self._btn_modo_manual = ctk.CTkButton(
            derecho, text="  Activar marcado manual",
            command=self._toggle_modo_manual, state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14), height=36,
            **BTN_GRAY,
        )
        self._btn_modo_manual.pack(pady=(0, 6), padx=20, fill="x")

        # ── Selector de tipo de dato (visible solo en modo manual) ──
        self._frame_tipo_manual = ctk.CTkFrame(derecho, fg_color="transparent")
        self._frame_tipo_manual.pack(pady=(0, 4), padx=20, fill="x")

        ctk.CTkLabel(
            self._frame_tipo_manual,
            text="Tipo de dato a marcar:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COL_TEXT,
        ).pack(anchor="w")

        self._combo_tipo_manual = ctk.CTkComboBox(
            self._frame_tipo_manual,
            values=list(OPCIONES_TIPO_MANUAL.keys()),
            command=self._on_tipo_manual_cambio,
            state="readonly",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=30, corner_radius=8,
            fg_color=COL_APP_BG, border_color=COL_BORDER, text_color=COL_TEXT,
            button_color="#0369A1", button_hover_color="#0284C7",
        )
        self._combo_tipo_manual.set("Otro dato personal")
        self._combo_tipo_manual.pack(fill="x", pady=(2, 0))

        self._lbl_color_manual = ctk.CTkLabel(
            self._frame_tipo_manual,
            text="  ■  Otro dato personal",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_MANUAL
        )
        self._lbl_color_manual.pack(anchor="w", pady=(2, 0))

        # Campos personalizados (ocultos por defecto)
        self._frame_custom = ctk.CTkFrame(self._frame_tipo_manual, fg_color="transparent")
        
        self._entry_tipo_custom = ctk.CTkEntry(
            self._frame_custom, placeholder_text="Tipo de dato (ej. Matrícula Consular)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11), height=28
        )
        self._entry_tipo_custom.pack(fill="x", pady=(4, 2))
        
        self._entry_fundamento_custom = ctk.CTkEntry(
            self._frame_custom, placeholder_text="Fundamento Legal (ej. Art. 116 LGTAIP)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11), height=28
        )
        self._entry_fundamento_custom.pack(fill="x", pady=(2, 2))

        self._entry_motivacion_custom = ctk.CTkEntry(
            self._frame_custom, placeholder_text="Motivación (ej. Identifica a una persona)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11), height=28
        )
        self._entry_motivacion_custom.pack(fill="x", pady=(0, 0))

        self._frame_tipo_manual.pack_forget()  # oculto hasta activar modo manual

        self._btn_deshacer_manual = ctk.CTkButton(
            derecho, text="  ↩  Deshacer último marcado",
            command=self._on_click_deshacer_manual, state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13), height=32,
            **BTN_SECONDARY,
        )
        self._btn_deshacer_manual.pack(pady=(0, 4), padx=20, fill="x")

        ctk.CTkLabel(
            derecho,
            text="Clic sobre un recuadro para activar/desactivar",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COL_TEXT2,
        ).pack(pady=(0, 4), padx=20, anchor="w")

        # ── Sección: Redacción ──
        self._seccion(derecho, "Redacción")

        self._btn_aplicar_todo = ctk.CTkButton(
            derecho, text="  Redactar todo el documento",
            command=self._on_click_aplicar_todo, state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"), height=38,
            **BTN_DANGER,
        )
        self._btn_aplicar_todo.pack(pady=(0, 6), padx=20, fill="x")

        self._btn_guardar_sin_redactar = ctk.CTkButton(
            derecho, text="  Guardar sin redactar",
            command=self._on_click_guardar_sin_redactar, state="disabled",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13), height=32,
            **BTN_SECONDARY,
        )
        self._btn_guardar_sin_redactar.pack(pady=(0, 6), padx=20, fill="x")

        # ── Sección: Lista de Descarte ──
        self._seccion(derecho, "Lista de Descarte")
        ctk.CTkLabel(
            derecho,
            text="Palabras o nombres que NO deben censurarse\n(uno por línea):",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COL_TEXT2, justify="left",
        ).pack(pady=(0, 4), padx=20, anchor="w")
        self._txt_descarte = ctk.CTkTextbox(
            derecho, height=80, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COL_APP_BG, border_color=COL_BORDER, border_width=1,
            text_color=COL_TEXT, corner_radius=8,
        )
        self._txt_descarte.pack(pady=(0, 4), padx=20, fill="x")
        self._txt_descarte.bind("<KeyRelease>", self._on_descarte_cambio)

        # ── Sección: Leyenda ──
        self._seccion(derecho, "Leyenda de colores")
        self._construir_leyenda(derecho)

    def _construir_leyenda(self, parent) -> None:
        leyenda = [
            ("#e67e22", "Identidad (nombre, nacimiento, edad, sexo, nacionalidad)"),
            ("#c0392b", "Identificadores (CURP, RFC, INE, Pasaporte, NSS, CRIP)"),
            ("#2980b9", "Contacto y domicilio (Tel, Email, CP, calle, colonia)"),
            ("#8e44ad", "Patrimonial (CLABE, tarjeta, cuenta, monto)"),
            ("#1a5276", "Vehículo (placa, VIN)"),
            ("#b9770e", "Escolar (matrícula, institución, carrera)"),
            ("#e74c3c", "Salud / diagnóstico"),
            ("#a93226", "Origen étnico"),
            ("#7d3c98", "Religión"),
            ("#16a085", "Opinión política / afiliación"),
            ("#d81b60", "Preferencia sexual"),
            ("#d35400", "Biométrico"),
            ("#34495e", "Visual (firma, QR, código de barras)"),
            ("#7f8c8d", "Servidor público (no se testa)"),
            ("#95a5a6", "Marcado manual"),
        ]
        marco = ctk.CTkFrame(
            parent, fg_color=COL_APP_BG, corner_radius=10,
            border_width=1, border_color=COL_BORDER_SOFT,
        )
        marco.pack(pady=(0, 16), padx=20, fill="x")
        for color, etiqueta in leyenda:
            fila = ctk.CTkFrame(marco, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(
                fila, text="  ", width=18, height=14,
                fg_color=color, corner_radius=3,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(
                fila, text=etiqueta,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COL_TEXT,
            ).pack(side="left")

    # ------------------------------------------------------------------ INICIALIZACIÓN

    def _hilo_init_analizador(self) -> None:
        try:
            analizador = _get_detector().build_analyzer()
            self._cola.put(("analizador_listo", analizador))
        except Exception as exc:
            self._cola.put(("error_analizador", str(exc)))

    def _pulso_carga_modelo(self) -> None:
        """Pulsa cada segundo mientras el modelo no ha cargado, actualizando la etiqueta."""
        if self._analizador is not None or self._error_modelo is not None:
            return  # ya cargó o falló — detener pulso
        self._modelo_carga_seg += 1
        spinner = ["⏳", "⌛"][self._modelo_carga_seg % 2]
        self._etiqueta_estado.configure(
            text=f"{spinner} Cargando modelo NLP… ({self._modelo_carga_seg}s)\n"
                 "(La primera vez puede tardar 2-3 min descargando GLiNER)"
        )
        self.after(1000, self._pulso_carga_modelo)

    def _monitorear_cola_init(self) -> None:
        try:
            mensaje = self._cola.get_nowait()
            etiqueta = mensaje[0]
            if etiqueta == "analizador_listo":
                self._analizador = mensaje[1]
                self._modelo_carga_seg = 0
                self._etiqueta_estado.configure(text="✅ Modelo listo — Sin analizar")
                self._btn_cargar.configure(state="normal")
            elif etiqueta == "error_analizador":
                self._error_modelo = mensaje[1]
                self._etiqueta_estado.configure(
                    text=f"⚠ Error al cargar modelo NLP — {mensaje[1][:80]}"
                )
                messagebox.showerror(
                    "Error al cargar modelo",
                    f"No se pudo inicializar el analizador NLP:\n\n{mensaje[1]}\n\n"
                    "Verifique la instalación y reinicie la aplicación.",
                )
            else:
                # Mensaje de otro origen (no debería llegar aquí durante init)
                self._cola.put(mensaje)  # devolver para que lo lea el monitor correcto
                self.after(200, self._monitorear_cola_init)
        except queue.Empty:
            self.after(200, self._monitorear_cola_init)

    # ------------------------------------------------------------------ CARGA DE PDF

    def _on_click_cargar(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar PDF",
            filetypes=[("Archivos PDF", "*.pdf")],
        )
        if ruta:
            self._cargar_pdf(ruta)

    def _cargar_pdf(self, ruta: str) -> None:
        try:
            self._doc = pdf_reader.open_pdf(ruta)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{exc}")
            return

        self._ruta_pdf = ruta
        self._pagina_actual = 0
        self._resultados_por_pagina = {}
        self._rects_manuales = []
        self._tipo_manual = "MANUAL"
        self._combo_tipo_manual.set("Otro dato personal")
        self._lbl_color_manual.configure(text="  ■  Otro dato personal", text_color=COLOR_MANUAL)
        self._etiqueta_archivo.configure(text=os.path.basename(ruta))

        # Clasificar documento y mostrar tipo antes de analizar
        info_doc = pdf_reader.clasificar_documento(self._doc)
        tipo = info_doc["tipo"]
        n = info_doc["total_paginas"]
        ne = len(info_doc["paginas_escaneadas"])
        if tipo == "nativo":
            estado_inicial = f"Documento nativo — {n} pág{'s' if n > 1 else ''}."
        elif tipo == "escaneado":
            estado_inicial = f"Documento escaneado — {n} pág{'s' if n > 1 else ''} (OCR activo)."
        else:
            estado_inicial = f"Documento híbrido — {n - ne} nativa{'s' if n - ne > 1 else ''} + {ne} escaneada{'s' if ne > 1 else ''} (OCR activo)."
        self._etiqueta_estado.configure(text=estado_inicial)
        self._btn_analizar_todo.configure(state="normal")
        self._btn_guardar_sin_redactar.configure(state="normal")
        self._btn_modo_manual.configure(state="normal")
        self._btn_aplicar_todo.configure(state="disabled")
        self._actualizar_nav()
        self._renderizar_pagina(0)

    # ------------------------------------------------------------------ RENDERIZADO

    def _renderizar_pagina(self, indice_pagina: int) -> None:
        if self._doc is None:
            return
        pagina = self._doc[indice_pagina]
        mat = pymupdf.Matrix(self._zoom, self._zoom)
        pix = pagina.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._img_base = img
        self._mostrar_imagen(img)

    def _mostrar_imagen(self, img: Image.Image) -> None:
        self._foto = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._foto)
        self._canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def _redibujar_entidades(self) -> None:
        """Redibuja la página actual mostrando la imagen base limpia y
        superpone los recuadros de entidades como items del canvas."""
        if self._img_base is None:
            return

        # 1. Mostrar imagen base sin modificar
        self._mostrar_imagen(self._img_base)

        # 2. Borrar recuadros anteriores (por si quedaron huérfanos)
        self._canvas.delete("entity_rects")

        _z = self._zoom
        _PAD_LEFT  = 1.0 * _z
        _PAD_RIGHT = 1.0 * _z
        _PAD_Y     = 1.5 * _z

        def _dibujar_rect(rect, color_hex: str, seleccionado: bool) -> None:
            x0 = rect.x0 * _z - _PAD_LEFT
            y0 = rect.y0 * _z - _PAD_Y
            x1 = rect.x1 * _z + _PAD_RIGHT
            y1 = rect.y1 * _z + _PAD_Y
            ancho = 2 if seleccionado else 1
            self._canvas.create_rectangle(
                x0, y0, x1, y1,
                outline=color_hex,
                width=ancho,
                tags="entity_rects",
            )
            # Handles de esquina (pequeños cuadrados sólidos) solo en recuadros activos
            if seleccionado:
                h = max(4, int(4 * _z / 1.25))  # tamaño del handle escalado
                for hx, hy in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
                    self._canvas.create_rectangle(
                        hx - h, hy - h, hx + h, hy + h,
                        fill=color_hex, outline="white", width=1,
                        tags="entity_rects",
                    )

        entidades = self._resultados_por_pagina.get(self._pagina_actual, [])
        for entidad in entidades:
            if self._en_lista_descarte(entidad.get("text", "")):
                continue
            # Soporte per-rect: "seleccionados" es una lista de bools, uno por rect
            seleccionados = entidad.get("seleccionados", [True] * len(entidad["rects"]))
            color_activo = COLORES_ENTIDAD.get(entidad["entity_type"], COLOR_DEFAULT)
            for i, rect in enumerate(entidad["rects"]):
                sel = seleccionados[i] if i < len(seleccionados) else True
                color = color_activo if sel else COLOR_DESELECCIONADO
                _dibujar_rect(rect, color, sel)

        for rm in self._rects_manuales:
            if rm["pagina"] == self._pagina_actual:
                r = rm["rect"]
                seleccionado = rm.get("seleccionado", True)
                et = rm.get("entity_type", "MANUAL")
                color = COLORES_ENTIDAD.get(et, COLOR_DEFAULT) if seleccionado else COLOR_DESELECCIONADO
                _dibujar_rect(r, color, seleccionado)

    # ------------------------------------------------------------------ NAVEGACIÓN

    def _navegar(self, delta: int) -> None:
        if self._doc is None or self._analisis_en_curso:
            return
        destino = self._pagina_actual + delta
        if 0 <= destino < len(self._doc):
            self._pagina_actual = destino
            self._actualizar_nav()
            self._renderizar_pagina(self._pagina_actual)
            if self._pagina_actual in self._resultados_por_pagina:
                self._redibujar_entidades()
            else:
                self._etiqueta_estado.configure(text="Sin analizar")

    def _actualizar_nav(self) -> None:
        if self._doc is None:
            return
        total = len(self._doc)
        self._etiqueta_pagina.configure(text=f"Página {self._pagina_actual + 1} de {total}")
        self._btn_prev.configure(state="normal" if self._pagina_actual > 0 else "disabled")
        self._btn_sig.configure(state="normal" if self._pagina_actual < total - 1 else "disabled")

    # ------------------------------------------------------------------ SCROLL Y CLICK

    def _on_scroll(self, evento) -> None:
        self._canvas.yview_scroll(int(-1 * (evento.delta / 120)), "units")

    def _on_ctrl_scroll(self, evento) -> None:
        """Ctrl+rueda → zoom in/out del preview."""
        if evento.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    def _on_key_zoom_in(self, evento) -> None:
        if isinstance(evento.widget, (tk.Entry, tk.Text)): return
        self._zoom_in()

    def _on_key_zoom_out(self, evento) -> None:
        if isinstance(evento.widget, (tk.Entry, tk.Text)): return
        self._zoom_out()

    def _on_key_nav_prev(self, evento) -> None:
        if isinstance(evento.widget, (tk.Entry, tk.Text)): return
        self._navegar(-1)

    def _on_key_nav_sig(self, evento) -> None:
        if isinstance(evento.widget, (tk.Entry, tk.Text)): return
        self._navegar(1)

    def _on_key_scroll_up(self, evento) -> None:
        if isinstance(evento.widget, (tk.Entry, tk.Text)): return
        self._canvas.yview_scroll(-3, "units")

    def _on_key_scroll_down(self, evento) -> None:
        if isinstance(evento.widget, (tk.Entry, tk.Text)): return
        self._canvas.yview_scroll(3, "units")

    # ------------------------------------------------------------------ ZOOM

    def _zoom_in(self) -> None:
        if self._zoom < self._ZOOM_MAX:
            self._zoom = round(self._zoom + self._ZOOM_PASO, 2)
            self._actualizar_zoom()

    def _zoom_out(self) -> None:
        if self._zoom > self._ZOOM_MIN:
            self._zoom = round(self._zoom - self._ZOOM_PASO, 2)
            self._actualizar_zoom()

    def _actualizar_zoom(self) -> None:
        """Re-renderiza la página actual con el nuevo zoom y redibuja entidades."""
        self._lbl_zoom.configure(text=f"{int(self._zoom * 100)}%")
        if self._doc is not None:
            self._renderizar_pagina(self._pagina_actual)
            if self._pagina_actual in self._resultados_por_pagina:
                self._redibujar_entidades()

    def _coords_canvas_a_pdf(self, cx: int, cy: int) -> tuple[float, float]:
        """Convierte coordenadas del canvas (incluye scroll) a coordenadas del PDF."""
        x_pdf = self._canvas.canvasx(cx) / self._zoom
        y_pdf = self._canvas.canvasy(cy) / self._zoom
        return x_pdf, y_pdf

    def _on_canvas_press(self, evento) -> None:
        cx = self._canvas.canvasx(evento.x)
        cy = self._canvas.canvasy(evento.y)

        # ① Modo marcado manual → dibuja nuevo rect (comportamiento existente)
        if self._modo_manual:
            self._drag_inicio = (cx, cy)
            return

        # ② Detectar si el clic cae en zona de esquina → iniciar resize
        target, corner, idx, es_manual = self._detectar_esquina_resize(cx, cy)
        if target is not None:
            self._resize_target = target
            self._resize_corner = corner
            self._resize_rect_idx = idx
            self._resize_es_manual = es_manual
            return

        # ③ Clic interior → toggle select/deselect (comportamiento existente)
        self._toggle_entidad_en_click(evento)

    def _on_canvas_drag(self, evento) -> None:
        # Resize activo → actualizar en tiempo real
        if self._resize_target is not None:
            self._actualizar_resize(evento)
            return

        # Drag manual → rect temporal punteado (comportamiento existente)
        if not self._modo_manual or self._drag_inicio is None:
            return
        x0, y0 = self._drag_inicio
        x1 = self._canvas.canvasx(evento.x)
        y1 = self._canvas.canvasy(evento.y)
        if self._id_rect_temporal is not None:
            self._canvas.delete(self._id_rect_temporal)
        self._id_rect_temporal = self._canvas.create_rectangle(
            x0, y0, x1, y1, outline=COLOR_MANUAL, width=2, dash=(4, 4)
        )

    def _on_canvas_release(self, evento) -> None:
        # Finalizar resize
        if self._resize_target is not None:
            self._resize_target = None
            self._resize_corner = None
            self._resize_rect_idx = None
            self._resize_es_manual = False
            self._canvas.configure(cursor="")
            return

        # Finalizar drag manual (comportamiento existente)
        if not self._modo_manual or self._drag_inicio is None:
            return
        if self._id_rect_temporal is not None:
            self._canvas.delete(self._id_rect_temporal)
            self._id_rect_temporal = None

        x0c, y0c = self._drag_inicio
        x1c = self._canvas.canvasx(evento.x)
        y1c = self._canvas.canvasy(evento.y)
        self._drag_inicio = None

        # Asegurar que el rect tenga área mínima (evitar clics accidentales)
        if abs(x1c - x0c) < 5 or abs(y1c - y0c) < 5:
            return

        x0p, y0p = x0c / self._zoom, y0c / self._zoom
        x1p, y1p = x1c / self._zoom, y1c / self._zoom
        rect_pdf = pymupdf.Rect(min(x0p, x1p), min(y0p, y1p), max(x0p, x1p), max(y0p, y1p))

        nuevo_rect = {
            "rect":        rect_pdf,
            "pagina":      self._pagina_actual,
            "seleccionado": True,
            "entity_type": self._tipo_manual,  # tipo elegido en el combobox
        }

        if self._tipo_manual == "CUSTOM":
            custom_label = self._entry_tipo_custom.get().strip()
            custom_legal = self._entry_fundamento_custom.get().strip()
            custom_motivacion = self._entry_motivacion_custom.get().strip()
            if not custom_label or not custom_legal or not custom_motivacion:
                messagebox.showwarning("Faltan datos", "Para datos personalizados, debes ingresar el Tipo de Dato, el Fundamento Legal y la Motivación.")
                return
            nuevo_rect["custom_label"] = custom_label
            nuevo_rect["custom_legal"] = custom_legal
            nuevo_rect["custom_motivacion"] = custom_motivacion

        self._rects_manuales.append(nuevo_rect)
        self._btn_deshacer_manual.configure(state="normal")
        self._redibujar_entidades()

    def _toggle_entidad_en_click(self, evento) -> None:
        """Selecciona/deselecciona una entidad al hacer clic sobre ella."""
        x_pdf, y_pdf = self._coords_canvas_a_pdf(evento.x, evento.y)
        punto = pymupdf.Point(x_pdf, y_pdf)

        # Verificar rects manuales primero
        for rm in reversed(self._rects_manuales):
            if rm["pagina"] == self._pagina_actual and rm["rect"].contains(punto):
                rm["seleccionado"] = not rm["seleccionado"]
                self._redibujar_entidades()
                self._actualizar_estado_boton_aplicar()
                return

        # Verificar entidades automáticas
        entidades = self._resultados_por_pagina.get(self._pagina_actual, [])
        for entidad in reversed(entidades):
            seleccionados = entidad.get("seleccionados", [True] * len(entidad["rects"]))
            for i, rect in enumerate(entidad["rects"]):
                if rect.contains(punto):
                    # Toggle solo este rect individual, no toda la entidad
                    sel_actual = seleccionados[i] if i < len(seleccionados) else True
                    seleccionados[i] = not sel_actual
                    entidad["seleccionados"] = seleccionados
                    self._redibujar_entidades()
                    self._actualizar_estado_boton_aplicar()
                    return

    def _actualizar_estado_boton_aplicar(self) -> None:
        pass  # _btn_aplicar eliminado; _btn_aplicar_todo siempre disponible tras análisis

    # ------------------------------------------------------------------ RESIZE INTERACTIVO

    _RESIZE_TOL = 10  # píxeles de tolerancia para detectar zona de esquina

    def _detectar_esquina_resize(self, cx: float, cy: float):
        """Busca si (cx,cy) en coordenadas canvas está sobre la esquina de algún recuadro.

        Devuelve (target_dict, corner_str, rect_idx, es_manual) o (None, None, None, False).
        corner_str ∈ {'tl','tr','bl','br'}
        """
        import math
        tol = self._RESIZE_TOL
        _z  = self._zoom
        _pad_x = 1.0 * _z
        _pad_y = 1.5 * _z

        def _esquinas_canvas(r: pymupdf.Rect):
            """Devuelve las 4 esquinas del rect en coord canvas (ya con padding)."""
            x0 = r.x0 * _z - _pad_x
            y0 = r.y0 * _z - _pad_y
            x1 = r.x1 * _z + _pad_x
            y1 = r.y1 * _z + _pad_y
            return {"tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1)}

        def _encontrar_corner(esquinas):
            for nombre, (ex, ey) in esquinas.items():
                if math.hypot(cx - ex, cy - ey) <= tol:
                    return nombre
            return None

        # Buscar en manuales (prioridad igual que el toggle)
        for rm in reversed(self._rects_manuales):
            if rm["pagina"] != self._pagina_actual:
                continue
            corner = _encontrar_corner(_esquinas_canvas(rm["rect"]))
            if corner:
                return rm, corner, 0, True  # manuales tienen solo 1 rect

        # Buscar en entidades automáticas
        entidades = self._resultados_por_pagina.get(self._pagina_actual, [])
        for entidad in reversed(entidades):
            if self._en_lista_descarte(entidad.get("text", "")):
                continue
            seleccionados = entidad.get("seleccionados", [True] * len(entidad["rects"]))
            if not any(seleccionados):
                continue
            for idx, rect in enumerate(entidad["rects"]):
                corner = _encontrar_corner(_esquinas_canvas(rect))
                if corner:
                    return entidad, corner, idx, False

        return None, None, None, False

    def _actualizar_resize(self, evento) -> None:
        """Actualiza en tiempo real el rect siendo redimensionado."""
        cx = self._canvas.canvasx(evento.x)
        cy = self._canvas.canvasy(evento.y)
        xp = cx / self._zoom
        yp = cy / self._zoom

        corner = self._resize_corner
        idx    = self._resize_rect_idx
        es_manual = self._resize_es_manual
        target = self._resize_target

        # Obtener el rect original actual
        if es_manual:
            orig = target["rect"]
        else:
            orig = target["rects"][idx]

        # Calcular nuevo rect según la esquina arrastrada
        if corner == "tl":
            new = pymupdf.Rect(xp, yp, orig.x1, orig.y1)
        elif corner == "tr":
            new = pymupdf.Rect(orig.x0, yp, xp, orig.y1)
        elif corner == "bl":
            new = pymupdf.Rect(xp, orig.y0, orig.x1, yp)
        else:  # 'br'
            new = pymupdf.Rect(orig.x0, orig.y0, xp, yp)

        # Normalizar y validar mínimo 5×5 pts
        new = pymupdf.Rect(
            min(new.x0, new.x1), min(new.y0, new.y1),
            max(new.x0, new.x1), max(new.y0, new.y1)
        )
        if new.width < 5 or new.height < 5:
            return

        # Aplicar
        if es_manual:
            target["rect"] = new
        else:
            target["rects"][idx] = new

        self._redibujar_entidades()

    def _on_canvas_motion(self, evento) -> None:
        """Cambia el cursor cuando el puntero se acerca a una esquina redimensionable."""
        if self._modo_manual or self._resize_target is not None:
            return
        cx = self._canvas.canvasx(evento.x)
        cy = self._canvas.canvasy(evento.y)
        _, corner, _, _ = self._detectar_esquina_resize(cx, cy)
        if corner in ("tl", "br"):
            self._canvas.configure(cursor="size_nw_se")
        elif corner in ("tr", "bl"):
            self._canvas.configure(cursor="size_ne_sw")
        else:
            self._canvas.configure(cursor="")



    # ------------------------------------------------------------------ MODO MANUAL

    def _on_descarte_cambio(self, _evento=None) -> None:
        """Actualiza la lista de descarte desde el textbox y redibuja."""
        contenido = self._txt_descarte.get("1.0", "end")
        self._lista_descarte = [
            linea.strip().lower()
            for linea in contenido.splitlines()
            if linea.strip()
        ]
        # Si ya hay resultados analizados, redibujar con el nuevo filtro
        if self._resultados_por_pagina.get(self._pagina_actual):
            self._redibujar_entidades()

    @staticmethod
    def _normalizar(s: str) -> str:
        """Normaliza acentos para comparación robusta."""
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()

    def _en_lista_descarte(self, texto_entidad: str) -> bool:
        """Devuelve True si el texto de la entidad está en la lista de descarte."""
        if not self._lista_descarte or not texto_entidad:
            return False
        texto_norm = self._normalizar(texto_entidad)
        return any(self._normalizar(d) in texto_norm for d in self._lista_descarte)

    def _on_tipo_manual_cambio(self, label: str) -> None:
        """Actualiza el entity_type activo y la pastilla de color del selector."""
        self._tipo_manual = _LABEL_A_ET.get(label, "MANUAL")
        color = COLORES_ENTIDAD.get(self._tipo_manual, COLOR_DEFAULT)
        if self._tipo_manual == "CUSTOM":
            color = COLOR_MANUAL
        self._lbl_color_manual.configure(text=f"  ■  {label}", text_color=color)
        
        if self._tipo_manual == "CUSTOM":
            self._frame_custom.pack(fill="x", pady=(4,0))
        else:
            self._frame_custom.pack_forget()

    def _toggle_modo_manual(self) -> None:
        self._modo_manual = not self._modo_manual
        if self._modo_manual:
            # Activo: relleno azul primario para indicar el estado activo
            self._btn_modo_manual.configure(
                text="Desactivar marcado manual",
                fg_color="#0369A1", hover_color="#0284C7",
                text_color="#FFFFFF", border_width=0,
            )
            self._canvas.configure(cursor="crosshair")
            self._frame_tipo_manual.pack(pady=(0, 4), padx=20, fill="x",
                                         before=self._btn_deshacer_manual)
        else:
            # Inactivo: vuelve al estilo gris
            self._btn_modo_manual.configure(
                text="  Activar marcado manual", **BTN_GRAY,
            )
            self._canvas.configure(cursor="")
            self._frame_tipo_manual.pack_forget()

    def _on_click_deshacer_manual(self) -> None:
        """Elimina el último rect manual trazado en la página actual."""
        for i in range(len(self._rects_manuales) - 1, -1, -1):
            if self._rects_manuales[i]["pagina"] == self._pagina_actual:
                self._rects_manuales.pop(i)
                self._redibujar_entidades()
                self._actualizar_estado_boton_aplicar()
                # Deshabilitar botón si ya no quedan manuales en esta página
                manuales_pagina = [rm for rm in self._rects_manuales
                                   if rm["pagina"] == self._pagina_actual]
                if not manuales_pagina:
                    self._btn_deshacer_manual.configure(state="disabled")
                return

    # ------------------------------------------------------------------ ANÁLISIS


    def _on_click_analizar_todo(self) -> None:
        if self._doc is None:
            return
        if self._analizador is None:
            if self._error_modelo is not None:
                messagebox.showerror(
                    "Modelo no disponible",
                    f"El modelo NLP no cargó correctamente:\n\n{self._error_modelo}\n\n"
                    "Reinicie la aplicación para intentar de nuevo.",
                )
                return
            self._etiqueta_estado.configure(text="⏳ Cargando modelo NLP, por favor espere…")
            self.after(500, self._on_click_analizar_todo)  # reintentar cada 500 ms
            return
        self._bloquear_botones_analisis()
        self._barra_progreso.configure(mode="determinate")
        self._barra_progreso.set(0)
        self._barra_progreso.pack(pady=4, padx=8, fill="x")
        self._etiqueta_estado.configure(text="Analizando documento…")
        self._analisis_en_curso = True
        threading.Thread(target=self._hilo_analisis_lote, daemon=True).start()
        self.after(200, self._monitorear_cola_analisis)

    def _bloquear_botones_analisis(self) -> None:
        self._btn_analizar_todo.configure(state="disabled")
        self._btn_cargar.configure(state="disabled")
        self._btn_aplicar_todo.configure(state="disabled")

    def _hilo_analisis_pagina(self, indice: int) -> None:
        try:
            resultado = self._analizar_una_pagina(indice)
            self._cola.put(("pagina_ok", {indice: resultado}))
        except Exception as exc:
            logger.exception("Error analizando página %d", indice)
            self._cola.put(("pagina_error", str(exc)))

    def _hilo_analisis_lote(self) -> None:
        total = len(self._doc)
        resultados: dict[int, list[dict]] = {}
        errores: dict[int, str] = {}

        # ── Fase 1: extracción secuencial (PyMuPDF no es thread-safe) ──────────
        extracciones: dict[int, tuple] = {}  # indice → (texto, indice_espacial)
        for i in range(total):
            try:
                pagina = self._doc[i]
                if pdf_reader.es_pagina_escaneada(pagina):
                    self._cola.put(("status", f"Pág. {i + 1}/{total}: escaneada — OCR (puede tardar)…"))
                    self._cola.put(("ocr_inicio", None))
                else:
                    self._cola.put(("status", f"Pág. {i + 1}/{total}: extrayendo texto…"))
                palabras = pdf_reader.extract_words(pagina)
                idx_esp = pdf_reader.build_spatial_index(palabras, pagina)
                texto = " ".join(e["word"] for e in idx_esp)
                # QR: detección basada en imagen, en fase secuencial (PyMuPDF
                # no es thread-safe, necesita el objeto `pagina` aquí).
                try:
                    qr_ents = _get_qr().detectar_qr(pagina)
                except Exception:
                    logger.exception("Error detectando QR en página %d", i)
                    qr_ents = []
                extracciones[i] = (texto, idx_esp, qr_ents)
            except Exception as exc:
                logger.exception("Error extrayendo página %d", i)
                errores[i] = str(exc)
            self._cola.put(("progreso_lote", (i + 1) / total * 0.5))  # 0 % → 50 %

        # ── Fase 2: análisis NLP en paralelo (Presidio/GLiNER libera el GIL) ──
        completados = 0

        def _analizar_texto(indice: int) -> list[dict]:
            texto, idx_esp, qr_ents = extracciones[indice]
            presidio_crudo = _get_detector().analyze_page(self._analizador, texto)
            dicts_presidio = [
                {
                    # Normaliza alias GLiNER al tipo canónico para evitar filas
                    # duplicadas en el acta cuando GLiNER y Presidio detectan el mismo dato
                    "entity_type": _ALIAS_TIPOS.get(r.entity_type, r.entity_type),
                    "text":        texto[r.start:r.end],
                    "start":       r.start,
                    "end":         r.end,
                    "score":       r.score,
                }
                for r in presidio_crudo
            ]
            mapeado = _get_mapper().map_entities(idx_esp, dicts_presidio)
            mapeado += qr_ents
            mapeado = _get_mapper()._deduplicar(mapeado)
            for entidad in mapeado:
                entidad.setdefault("seleccionados", [True] * len(entidad["rects"]))
            return mapeado

        indices_validos = [i for i in range(total) if i in extracciones]
        # Inferencia NLP (GLiNER/Tokenizers) restringida a 1 hilo para evitar
        # "RuntimeError: Already borrowed" en el core the Rust de HuggingFace.
        max_workers = 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_analizar_texto, i): i for i in indices_validos}
            for future in as_completed(futures):
                i = futures[future]
                try:
                    resultados[i] = future.result()
                except Exception as exc:
                    logger.exception("Error analizando página %d", i)
                    errores[i] = str(exc)
                completados += 1
                prog = 0.5 + completados / total * 0.5  # 50 % → 100 %
                self._cola.put(("progreso_lote", prog))

        self._cola.put(("lote_ok", resultados, errores))

    def _analizar_una_pagina(self, indice: int) -> list[dict]:
        """Analiza una sola página (usado en modo manual/página individual)."""
        pagina = self._doc[indice]
        if pdf_reader.es_pagina_escaneada(pagina):
            self._cola.put(("status", f"Pág. {indice + 1}: escaneada — OCR (puede tardar)…"))
            self._cola.put(("ocr_inicio", None))
        palabras = pdf_reader.extract_words(pagina)
        indice_espacial = pdf_reader.build_spatial_index(palabras, pagina)
        texto = " ".join(e["word"] for e in indice_espacial)
        presidio_crudo = _get_detector().analyze_page(self._analizador, texto)
        dicts_presidio = [
            {
                "entity_type": _ALIAS_TIPOS.get(r.entity_type, r.entity_type),
                "text":        texto[r.start:r.end],
                "start":       r.start,
                "end":         r.end,
                "score":       r.score,
            }
            for r in presidio_crudo
        ]
        mapeado = _get_mapper().map_entities(indice_espacial, dicts_presidio)
        # Detección de QR (basada en imagen; sirve para nativo y escaneado)
        try:
            mapeado += _get_qr().detectar_qr(pagina)
        except Exception:
            logger.exception("Error detectando QR en página %d", indice)
        mapeado = _get_mapper()._deduplicar(mapeado)
        for entidad in mapeado:
            entidad.setdefault("seleccionados", [True] * len(entidad["rects"]))
        return mapeado

    def _monitorear_cola_analisis(self) -> None:
        # Drena todos los mensajes disponibles en la cola ahora mismo
        while True:
            try:
                mensaje = self._cola.get_nowait()
            except queue.Empty:
                # Cola vacía — reprogramar para el próximo ciclo
                self.after(200, self._monitorear_cola_analisis)
                return

            etiqueta = mensaje[0]

            if etiqueta == "status":
                self._etiqueta_estado.configure(text=mensaje[1])
                # Continúa drenando — puede haber más mensajes

            elif etiqueta == "ocr_inicio":
                self._barra_progreso.configure(mode="indeterminate")
                self._barra_progreso.start()
                # Continúa drenando

            elif etiqueta == "progreso_lote":
                self._barra_progreso.stop()
                self._barra_progreso.configure(mode="determinate")
                self._barra_progreso.set(mensaje[1])
                # Continúa drenando — puede haber más mensajes

            elif etiqueta == "pagina_ok":
                resultados_nuevos: dict = mensaje[1]
                self._resultados_por_pagina.update(resultados_nuevos)
                self._finalizar_analisis()
                return  # Terminal — no reprogramar

            elif etiqueta == "lote_ok":
                resultados_nuevos, errores = mensaje[1], mensaje[2]
                self._resultados_por_pagina.update(resultados_nuevos)
                self._finalizar_analisis(errores=errores)
                return  # Terminal — no reprogramar

            elif etiqueta == "pagina_error":
                self._barra_progreso.stop()
                self._barra_progreso.pack_forget()
                self._desbloquear_botones_analisis()
                self._etiqueta_estado.configure(text=f"Error: {mensaje[1]}")
                messagebox.showerror("Error de análisis", str(mensaje[1]))
                return  # Terminal — no reprogramar

    def _finalizar_analisis(self, errores: dict | None = None) -> None:
        try:
            self._barra_progreso.stop()
        except Exception:
            pass
        self._barra_progreso.pack_forget()
        self._analisis_en_curso = False
        self._desbloquear_botones_analisis()

        total_entidades = sum(
            len(v) for v in self._resultados_por_pagina.values()
        )
        paginas_analizadas = len(self._resultados_por_pagina)

        if errores:
            msg_error = "\n".join(f"  Pág {k+1}: {v}" for k, v in errores.items())
            self._etiqueta_estado.configure(
                text=f"{total_entidades} entidades en {paginas_analizadas} pág. ({len(errores)} errores)"
            )
            messagebox.showwarning("Errores parciales", f"Errores en algunas páginas:\n{msg_error}")
        else:
            n = len(self._resultados_por_pagina.get(self._pagina_actual, []))
            self._etiqueta_estado.configure(
                text=f"{total_entidades} entidades totales · {n} en esta página"
            )

        if self._pagina_actual in self._resultados_por_pagina:
            self._redibujar_entidades()
            self._actualizar_estado_boton_aplicar()

        if self._resultados_por_pagina:
            self._btn_aplicar_todo.configure(state="normal")

    def _desbloquear_botones_analisis(self) -> None:
        self._btn_analizar_todo.configure(state="normal")
        self._btn_cargar.configure(state="normal")

    # ------------------------------------------------------------------ REDACCIÓN


    def _on_click_aplicar_todo(self) -> None:
        if self._doc is None:
            return
        rects_por_pagina: dict[int, list] = {}
        for idx in self._resultados_por_pagina:
            rects = self._recopilar_rects_pagina(idx)
            if rects:
                rects_por_pagina[idx] = rects
        if not rects_por_pagina:
            messagebox.showinfo("Sin selección", "No hay entidades seleccionadas en ninguna página.")
            return
        todos_rects = [r for lista in rects_por_pagina.values() for r in lista]
        self._ejecutar_redaccion(todos_rects, list(rects_por_pagina.keys()))

    def _recopilar_rects_pagina(self, indice_pagina: int) -> list:
        rects: list = []
        entidades = self._resultados_por_pagina.get(indice_pagina, [])
        for entidad in entidades:
            seleccionados = entidad.get("seleccionados", [True] * len(entidad["rects"]))
            if not self._en_lista_descarte(entidad.get("text", "")):
                for i, rect in enumerate(entidad["rects"]):
                    if i < len(seleccionados) and seleccionados[i]:
                        rects.append(rect)
        for rm in self._rects_manuales:
            if rm["pagina"] == indice_pagina and rm.get("seleccionado", True):
                rects.append(rm["rect"])
        return rects

    def _ejecutar_redaccion(self, _rects_ignorados: list, paginas: list[int]) -> None:
        ruta_salida = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            title="Guardar documento redactado como...",
            initialfile=os.path.basename(self._ruta_pdf).replace(".pdf", "_redactado.pdf")
        )
        if not ruta_salida:
            return

        if TIENE_SANITIZER:
            try:
                # TRABAJAR SOBRE UNA COPIA EN MEMORIA PARA NO MODIFICAR EL ORIGINAL
                doc_copy = pymupdf.open("pdf", self._doc.tobytes())

                # 1. Recopilar información para el Acta de Justificación (Fase 4)
                info_reporte = []
                for idx in paginas:
                    entidades = self._resultados_por_pagina.get(idx, [])
                    for entidad in entidades:
                        seleccionados = entidad.get("seleccionados", [True] * len(entidad["rects"]))
                        if not self._en_lista_descarte(entidad.get("text", "")):
                            for i, rect in enumerate(entidad["rects"]):
                                if i < len(seleccionados) and seleccionados[i]:
                                    info_reporte.append({
                                        "entity_type": entidad["entity_type"],
                                        "pagina": idx,
                                        "y0": rect.y0
                                    })
                    for rm in self._rects_manuales:
                        if rm["pagina"] == idx and rm.get("seleccionado", True):
                            info_dict = {
                                "entity_type": rm.get("entity_type", "MANUAL"),
                                "pagina":      idx,
                                "y0":          rm["rect"].y0,
                                "manual":      True,
                            }
                            if info_dict["entity_type"] == "CUSTOM":
                                info_dict["custom_label"] = rm.get("custom_label")
                                info_dict["custom_legal"] = rm.get("custom_legal")
                                info_dict["custom_motivacion"] = rm.get("custom_motivacion")
                            info_reporte.append(info_dict)

                # 2. Sanitización física irreversible (Fase 3 - Art. 121 LGTAIP)
                for idx in paginas:
                    rects_pagina = self._recopilar_rects_pagina(idx)
                    if rects_pagina:
                        sanitize_page(doc_copy[idx], rects_pagina)
                
                # 3. Insertar Acta de Justificación Legal
                try:
                    import report_generator
                    nombre_archivo = os.path.basename(self._ruta_pdf)
                    report_generator.generate_justification_page(doc_copy, info_reporte, nombre_archivo)
                except ImportError:
                    logger.warning("No se pudo importar report_generator. Omitiendo acta.")
                except Exception as e:
                    logger.exception("Error al generar acta de justificación: %s", e)

                # Limpiar metadatos antes de guardar
                doc_copy.set_metadata({"producer": "", "creator": "", "author": "", "title": ""})
                try:
                    doc_copy.del_xml_metadata()
                except Exception:
                    pass

                # Double-pass: garbage=4 elimina físicamente los streams originales
                # del archivo para que no sean recuperables con herramientas forenses.
                buf = doc_copy.tobytes(garbage=4, deflate=True, clean=True, incremental=False)
                doc2 = pymupdf.open("pdf", buf)
                doc2.save(ruta_salida, garbage=4, deflate=True, clean=True, incremental=False)
                doc2.close()
                doc_copy.close()

                # Registro de auditoría
                try:
                    _get_audit().registrar_redaccion(
                        archivo_entrada=self._ruta_pdf,
                        archivo_salida=ruta_salida,
                        num_paginas=len(paginas),
                        info_reporte=info_reporte,
                    )
                except Exception:
                    logger.warning("No se pudo escribir el registro de auditoría.")

                messagebox.showinfo("Guardado", f"PDF redactado guardado en:\n{ruta_salida}")
                logger.info("PDF redactado guardado: %s", ruta_salida)
            except Exception as exc:
                logger.exception("Error al aplicar redacción")
                messagebox.showerror("Error", str(exc))
        else:
            self._guardar_coords_json(paginas)

    def _guardar_coords_json(self, paginas: list[int]) -> None:
        directorio_salida = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(directorio_salida, exist_ok=True)
        base = os.path.splitext(os.path.basename(self._ruta_pdf))[0]
        ruta_json = os.path.join(directorio_salida, f"coords_redaccion_{base}.json")

        serializable = []
        for idx in paginas:
            rects_pagina = self._recopilar_rects_pagina(idx)
            for r in rects_pagina:
                serializable.append({
                    "pagina": idx,
                    "x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1,
                })

        with open(ruta_json, "w", encoding="utf-8") as fh:
            json.dump(serializable, fh, ensure_ascii=False, indent=2)

        messagebox.showinfo(
            "Coordenadas guardadas",
            f"sanitizer.py no encontrado.\nCoordenadas guardadas en:\n{ruta_json}",
        )
        logger.info("Coordenadas de redacción guardadas: %s", ruta_json)

    def _on_click_guardar_sin_redactar(self) -> None:
        if self._doc is None:
            return
        destino = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar copia sin redactar",
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialfile=os.path.basename(self._ruta_pdf),
        )
        if destino:
            try:
                self._doc.save(destino)
                messagebox.showinfo("Guardado", f"Archivo guardado en:\n{destino}")
                logger.info("PDF guardado sin redactar: %s", destino)
            except Exception as exc:
                logger.exception("Error al guardar sin redactar")
                messagebox.showerror("Error", str(exc))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ValidadorPDFApp().mainloop()
