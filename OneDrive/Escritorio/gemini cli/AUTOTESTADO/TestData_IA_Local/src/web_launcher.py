"""
ANONIMA Web Launcher
Flujo:
  1. Usuario sube PDF en :7080  (password: LUISMIGUEL)
  2. PDF se carga automáticamente en la app tkinter (via after() polling)
  3. La página web muestra la interfaz VNC embebida + instrucciones
  4. Usuario revisa entidades y hace click en "Redactar" dentro de la app
  5. El click en "Redactar" intercepta el guardado → escribe a /tmp/anonima_output/
  6. La página web detecta que el resultado está listo y muestra el botón de descarga
"""

import json
import logging
import os
import queue
import threading
import uuid
from pathlib import Path

import pymupdf

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

UPLOAD_DIR = Path("/tmp/anonima_uploads")
OUTPUT_DIR = Path("/tmp/anonima_output")
STATUS_DIR = Path("/tmp/anonima_status")
for d in (UPLOAD_DIR, OUTPUT_DIR, STATUS_DIR):
    d.mkdir(exist_ok=True)

WEB_PASSWORD = "LUISMIGUEL"
WEB_PORT     = 7080
VNC_URL      = "http://148.230.82.14:6080/vnc.html?autoconnect=true&resize=scale"

job_queue: queue.Queue = queue.Queue()


def _write_status(job_id: str, status: str) -> None:
    (STATUS_DIR / f"{job_id}.json").write_text(json.dumps({"status": status}))


def _read_status(job_id: str) -> dict:
    f = STATUS_DIR / f"{job_id}.json"
    return json.loads(f.read_text()) if f.exists() else {"status": "not_found"}


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML_INDEX = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ANONIMA — Subir documento</title>
  <style>
    *{box-sizing:border-box}
    body{font-family:Arial,sans-serif;max-width:560px;margin:60px auto;padding:0 20px;color:#222}
    h1{color:#1a5276;font-size:1.4rem;margin-bottom:4px}
    p.sub{color:#555;font-size:.9rem;margin-top:0}
    label{font-weight:bold;display:block;margin-top:18px}
    input[type=password],input[type=file]{width:100%;padding:8px;margin-top:4px;border:1px solid #ccc;border-radius:4px}
    button{margin-top:22px;width:100%;padding:11px;background:#1a5276;color:#fff;border:none;border-radius:4px;font-size:1rem;cursor:pointer}
    button:hover{background:#154360}
    .err{color:#c0392b;margin-top:12px;font-weight:bold}
    .note{font-size:.82rem;color:#777;margin-top:6px}
  </style>
</head>
<body>
  <h1>⬛ ANONIMA</h1>
  <p class="sub">Validador de datos personales — LGTAIP</p>
  {% if error %}<p class="err">{{ error }}</p>{% endif %}
  <form method="post" enctype="multipart/form-data">
    <label>Documento PDF (máx. 50 MB)</label>
    <input type="file" name="file" accept=".pdf" required autofocus>
    <p class="note">El documento se cargará en la app. Podrás revisar las entidades detectadas antes de redactar.</p>
    <button type="submit">Subir documento →</button>
  </form>
</body>
</html>"""

HTML_APP = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ANONIMA — Revisión</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:Arial,sans-serif;background:#f0f4f8;color:#222}
    .topbar{background:#1a5276;color:#fff;padding:10px 20px;display:flex;align-items:center;gap:12px}
    .topbar h1{font-size:1.1rem;font-weight:bold}
    .badge{font-size:.78rem;background:#154360;padding:3px 10px;border-radius:12px}
    .instructions{background:#fff;border-left:4px solid #1a5276;margin:14px 16px 0;padding:10px 14px;font-size:.88rem;line-height:1.6}
    .instructions b{color:#1a5276}
    #vnc-wrap{margin:14px 16px;border:2px solid #ccc;border-radius:6px;overflow:hidden;background:#000}
    iframe{display:block;width:100%;height:580px;border:none}
    #status-bar{margin:10px 16px 16px;padding:10px 14px;border-radius:6px;font-size:.88rem;text-align:center}
    .waiting{background:#fef9e7;border:1px solid #f0c040;color:#7d6608}
    .ready{background:#eafaf1;border:1px solid #27ae60;color:#1e8449}
    .error{background:#fdedec;border:1px solid #e74c3c;color:#922b21}
    a.btn{display:inline-block;margin-top:8px;padding:9px 28px;background:#1e8449;color:#fff;text-decoration:none;border-radius:4px;font-size:.95rem}
    .spinner{display:inline-block;width:14px;height:14px;border:3px solid #ccc;border-top-color:#7d6608;border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:6px}
    @keyframes spin{to{transform:rotate(360deg)}}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>⬛ ANONIMA — Testado de Datos Personales</h1>
    <span class="badge">Sesión activa</span>
  </div>

  <div class="instructions">
    <b>Cómo usar:</b><br>
    1. Espera a que el documento cargue en la app (puede tomar 1-2 min la primera vez).<br>
    2. Haz clic en <b>«Analizar todo»</b> si el análisis no inicia automáticamente.<br>
    3. Revisa las entidades detectadas y desmarca las que <b>no</b> quieras redactar.<br>
    4. Haz clic en <b>«Redactar todo el documento»</b> — el PDF redactado aparecerá aquí abajo.
  </div>

  <div id="vnc-wrap">
    <iframe src="{{ vnc_url }}" allowfullscreen></iframe>
  </div>

  <div id="status-bar" class="waiting">
    <span class="spinner"></span>
    <span id="status-text">Esperando que hagas clic en «Redactar todo el documento» en la app…</span>
  </div>

  <script>
    const jobId = "{{ job_id }}";
    function poll() {
      fetch('/api/status/' + jobId)
        .then(r => r.json())
        .then(data => {
          const bar = document.getElementById('status-bar');
          const txt = document.getElementById('status-text');
          if (data.status === 'ready') {
            window.location.href = '/done/' + jobId;
          } else if (data.status === 'cancelled') {
            bar.className = 'error';
            txt.innerHTML = '⏱️ Sesión expirada por inactividad. <a href="/">Subir otro documento</a>';
          } else if (data.status && data.status.startsWith('error')) {
            bar.className = 'error';
            txt.textContent = '❌ ' + data.status;
          } else {
            setTimeout(poll, 3000);
          }
        })
        .catch(() => setTimeout(poll, 5000));
    }
    setTimeout(poll, 3000);
  </script>
</body>
</html>"""


# ── Flask ─────────────────────────────────────────────────────────────────────
from flask import (Flask, abort, jsonify, redirect, render_template_string,
                   request, send_file, url_for)
from werkzeug.utils import secure_filename

flask_app = Flask(__name__)
flask_app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


@flask_app.route("/", methods=["GET", "POST"])
def index():
    error = None
    if request.method == "POST":
        if "file" not in request.files or request.files["file"].filename == "":
            error = "No se seleccionó ningún archivo."
        else:
            f = request.files["file"]
            if not f.filename.lower().endswith(".pdf"):
                error = "Solo se aceptan archivos PDF."
            else:
                job_id = str(uuid.uuid4())
                pdf_path = UPLOAD_DIR / f"{job_id}.pdf"
                f.save(str(pdf_path))
                _write_status(job_id, "loading")
                job_queue.put((job_id, str(pdf_path)))
                return redirect(url_for("app_page", job_id=job_id))
    return render_template_string(HTML_INDEX, error=error)


@flask_app.route("/app/<job_id>")
def app_page(job_id: str):
    if not (STATUS_DIR / f"{job_id}.json").exists():
        abort(404)
    return render_template_string(HTML_APP, job_id=job_id, vnc_url=VNC_URL)


@flask_app.route("/api/status/<job_id>")
def api_status(job_id: str):
    return jsonify(_read_status(job_id))


HTML_DONE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ANONIMA — Descarga lista</title>
  <style>
    *{box-sizing:border-box}
    body{font-family:Arial,sans-serif;max-width:520px;margin:80px auto;padding:0 20px;color:#222;text-align:center}
    h1{color:#1a5276;font-size:1.4rem}
    .ok{font-size:3.5rem;margin:20px 0}
    p{color:#555;font-size:.95rem;margin:8px 0}
    a.btn{display:inline-block;margin-top:24px;padding:13px 36px;background:#1e8449;color:#fff;text-decoration:none;border-radius:5px;font-size:1.05rem;font-weight:bold}
    a.btn:hover{background:#196f3d}
    a.nuevo{display:block;margin-top:18px;font-size:.88rem;color:#1a5276}
  </style>
</head>
<body>
  <div class="ok">✅</div>
  <h1>¡Redacción completada!</h1>
  <p>El documento ha sido procesado.<br>Los datos personales han sido redactados conforme a la LGTAIP.</p>
  <a class="btn" href="/download/{{ job_id }}">⬇ Descargar PDF redactado</a>
  <a class="nuevo" href="/">← Procesar otro documento</a>
</body>
</html>"""


@flask_app.route("/done/<job_id>")
def done_page(job_id: str):
    if not (STATUS_DIR / f"{job_id}.json").exists():
        abort(404)
    return render_template_string(HTML_DONE, job_id=job_id)


@flask_app.route("/download/<job_id>")
def download(job_id: str):
    out = OUTPUT_DIR / f"{job_id}_redactado.pdf"
    if not out.exists():
        abort(404)
    response = send_file(str(out), as_attachment=True,
                         download_name="documento_redactado.pdf",
                         mimetype="application/pdf")
    try:
        (UPLOAD_DIR / f"{job_id}.pdf").unlink(missing_ok=True)
        (STATUS_DIR / f"{job_id}.json").unlink(missing_ok=True)
    except Exception:
        pass
    threading.Timer(10, lambda: out.unlink(missing_ok=True)).start()
    return response


# ── Monkey-patch de ValidadorPDFApp ──────────────────────────────────────────
from ui_validator import ValidadorPDFApp

_original_init                = ValidadorPDFApp.__init__
_original_ejecutar            = ValidadorPDFApp._ejecutar_redaccion
_original_guardar_sin_redactar= ValidadorPDFApp._on_click_guardar_sin_redactar


def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self._web_job_queue   = job_queue
    self._web_processing  = False
    self._web_current_job = None
    self._web_output_path = None
    self.after(500, self._check_web_jobs)


def _check_web_jobs(self):
    try:
        job_id, pdf_path = self._web_job_queue.get_nowait()
    except queue.Empty:
        self.after(500, self._check_web_jobs)
        return
    # Si hay un job previo (analizado pero sin redactar), abandonarlo: el nuevo
    # upload tiene prioridad. Marca el anterior como cancelado para que su
    # frontend deje de polling.
    if self._web_current_job and self._web_current_job != job_id:
        _write_status(self._web_current_job, "cancelled")
    self._web_processing  = True
    self._web_current_job = job_id
    self._web_output_path = str(OUTPUT_DIR / f"{job_id}_redactado.pdf")
    _write_status(job_id, "loading")
    try:
        self._cargar_pdf(pdf_path)
    except Exception as exc:
        logging.getLogger(__name__).exception("Error cargando PDF")
        _write_status(job_id, f"error: no se pudo abrir el PDF ({exc})")
        self._web_processing  = False
        self._web_current_job = None
        self._web_output_path = None
        self.after(500, self._check_web_jobs)
        return
    self.after(300, self._auto_wait_analyzer)
    self.after(500, self._check_web_jobs)


def _auto_wait_analyzer(self):
    """Espera al analizador y lanza el análisis automáticamente."""
    if self._analizador is None and self._error_modelo is None:
        self.after(500, self._auto_wait_analyzer)
        return
    if self._error_modelo is not None:
        _write_status(self._web_current_job, f"error: modelo no disponible ({self._error_modelo})")
        self._web_processing  = False
        self._web_current_job = None
        self._web_output_path = None
        return
    _write_status(self._web_current_job, "analyzing")
    self._on_click_analizar_todo()
    self.after(1000, self._auto_monitor_analysis)


def _auto_monitor_analysis(self):
    """Espera a que el análisis termine y luego deja control al usuario."""
    import time
    if self._analisis_en_curso:
        self.after(1000, self._auto_monitor_analysis)
        return
    # Análisis completo — el usuario ahora revisa y hace click en Redactar
    _write_status(self._web_current_job, "waiting_user")
    self._web_waiting_since = time.time()
    # Polling para trigger automático via archivo (usado en tests o modo headless)
    self.after(500, lambda: self._check_auto_trigger())

# Timeout: si el usuario no hace click en Redactar dentro de este lapso, cancelar.
WAITING_USER_TIMEOUT = 300  # 5 minutos

def _check_auto_trigger(self):
    import os, time
    if not self._web_current_job:
        return
    trigger = f"/tmp/anonima_trigger_{self._web_current_job}"
    if os.path.exists(trigger):
        os.unlink(trigger)
        self._btn_aplicar_todo.invoke()
        return
    if _read_status(self._web_current_job).get("status") != "waiting_user":
        return
    # Timeout: si lleva demasiado en waiting_user, liberar sesión
    if time.time() - getattr(self, "_web_waiting_since", time.time()) > WAITING_USER_TIMEOUT:
        _write_status(self._web_current_job, "cancelled")
        self._web_processing  = False
        self._web_current_job = None
        self._web_output_path = None
        return
    self.after(500, lambda: self._check_auto_trigger())


def _patched_ejecutar_redaccion(self, _rects_ignorados, paginas):
    """Intercepta el botón Redactar: si hay job web activo, guarda sin diálogo."""
    if self._web_current_job and self._web_processing:
        self._web_save_and_notify(paginas)
    else:
        _original_ejecutar(self, _rects_ignorados, paginas)


def _patched_guardar_sin_redactar(self):
    """Intercepta 'Guardar sin redactar': si hay job web, guarda el original a OUTPUT_DIR."""
    if self._web_current_job and self._web_processing and self._doc is not None:
        try:
            self._doc.save(self._web_output_path)
            _write_status(self._web_current_job, "ready")
            logging.getLogger(__name__).info("Job %s → ready (sin redactar): %s",
                                             self._web_current_job, self._web_output_path)
        except Exception as exc:
            logging.getLogger(__name__).exception("Error guardando sin redactar")
            _write_status(self._web_current_job, f"error: {exc}")
        finally:
            self._web_processing  = False
            self._web_current_job = None
            self._web_output_path = None
    else:
        _original_guardar_sin_redactar(self)


def _web_save_and_notify(self, paginas):
    """Guarda el PDF redactado en OUTPUT_DIR (con acta de justificación) y notifica al frontend."""
    import os as _os
    from sanitizer import sanitize_page
    try:
        doc_copy = pymupdf.open("pdf", self._doc.tobytes())

        # 1. Recopilar info para el Acta de Justificación
        info_reporte = []
        for idx in paginas:
            for entidad in self._resultados_por_pagina.get(idx, []):
                seleccionados = entidad.get("seleccionados", [True] * len(entidad["rects"]))
                if not self._en_lista_descarte(entidad.get("text", "")):
                    for i, rect in enumerate(entidad["rects"]):
                        if i < len(seleccionados) and seleccionados[i]:
                            info_reporte.append({
                                "entity_type": entidad["entity_type"],
                                "pagina": idx,
                                "y0": rect.y0,
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
                        info_dict["custom_label"]     = rm.get("custom_label")
                        info_dict["custom_legal"]     = rm.get("custom_legal")
                        info_dict["custom_motivacion"]= rm.get("custom_motivacion")
                    info_reporte.append(info_dict)

        # 2. Sanitización física irreversible
        for idx in paginas:
            rects_pagina = self._recopilar_rects_pagina(idx)
            if rects_pagina:
                sanitize_page(doc_copy[idx], rects_pagina)

        # 3. Insertar Acta de Justificación Legal
        try:
            import report_generator
            nombre_archivo = _os.path.basename(self._ruta_pdf)
            report_generator.generate_justification_page(doc_copy, info_reporte, nombre_archivo)
        except ImportError:
            logging.getLogger(__name__).warning("report_generator no disponible — acta omitida")
        except Exception:
            logging.getLogger(__name__).exception("Error al generar acta de justificación")

        # 4. Limpiar metadatos
        doc_copy.set_metadata({"producer": "", "creator": "", "author": "", "title": ""})
        try:
            doc_copy.del_xml_metadata()
        except Exception:
            pass

        # 5. Double-pass garbage=4 para eliminar streams originales
        buf = doc_copy.tobytes(garbage=4, deflate=True, clean=True, incremental=False)
        doc2 = pymupdf.open("pdf", buf)
        doc2.save(self._web_output_path, garbage=4, deflate=True, clean=True, incremental=False)
        doc2.close()
        doc_copy.close()

        # 6. Auditoría
        try:
            import audit
            audit.registrar_redaccion(
                archivo_entrada=self._ruta_pdf,
                archivo_salida=self._web_output_path,
                num_paginas=len(paginas),
                info_reporte=info_reporte,
            )
        except Exception:
            logging.getLogger(__name__).warning("No se pudo escribir auditoría")

        _write_status(self._web_current_job, "ready")
        logging.getLogger(__name__).info("Job %s → ready: %s",
                                         self._web_current_job, self._web_output_path)
    except Exception as exc:
        logging.getLogger(__name__).exception("Error en web_save_and_notify")
        _write_status(self._web_current_job, f"error: {exc}")
    finally:
        self._web_processing  = False
        self._web_current_job = None
        self._web_output_path = None


ValidadorPDFApp._check_auto_trigger       = _check_auto_trigger
ValidadorPDFApp.__init__                 = _patched_init
ValidadorPDFApp._check_web_jobs          = _check_web_jobs
ValidadorPDFApp._auto_wait_analyzer      = _auto_wait_analyzer
ValidadorPDFApp._auto_monitor_analysis   = _auto_monitor_analysis
ValidadorPDFApp._ejecutar_redaccion      = _patched_ejecutar_redaccion
ValidadorPDFApp._on_click_guardar_sin_redactar = _patched_guardar_sin_redactar
ValidadorPDFApp._web_save_and_notify     = _web_save_and_notify


# ── Arranque ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(
        target=lambda: flask_app.run(
            host="0.0.0.0", port=WEB_PORT,
            debug=False, use_reloader=False
        ),
        daemon=True,
        name="flask-sidecar",
    ).start()
    logging.getLogger(__name__).info("Flask sidecar en :%d", WEB_PORT)
    ValidadorPDFApp().mainloop()
