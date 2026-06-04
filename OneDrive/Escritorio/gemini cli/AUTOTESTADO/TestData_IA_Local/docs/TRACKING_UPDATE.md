## ESTADO ACTUAL (2026-06-04 — Renombrado a ANONIMA + Sincronización Web)

### Sesión 2026-06-04 — Rebrand STINGTEST → ANONIMA y sync de algoritmos web

**Cambios aplicados:**

- **Rebrand completo:** Toda referencia a `STINGTEST` reemplazada por `ANONIMA` en los 21 archivos donde aparecía (`.py`, `.md`, `.txt`).
- **Tipografía mejorada:**
  - Escritorio (`ui_validator.py`): `FONT_FAMILY` cambiado de `"Segoe UI"` a `"Segoe UI Variable"` (más moderna en Windows 10/11); encabezado principal usa `"Georgia"` tamaño 20.
  - Acta PDF (`report_generator.py`): `h1` del encabezado aumentado a 13pt, letter-spacing 3px; `h2` más sutil (letter-spacing 1.5px, color #444).
- **Carpeta renombrada:** `stingtest-web/` → `anonima-web/`.
- **Sincronización web ← escritorio:** Los módulos `detector.py`, `pdf_reader.py`, `legal_mapper.py`, `report_generator.py`, `legal_config.json` y `legal_packs/` copiados byte a byte desde `TestData_IA_Local/src/` a `anonima-web/TestData_IA_Local/src/`.
- **Suite de deploy creada:** `anonima-web/tests/test_deploy.py` (22 tests con marca `@pytest.mark.deploy`) cubre: estructura del Space HF, sintaxis de `app.py`, branding, presencia de módulos core, sincronización byte a byte con escritorio, y generación correcta del acta.

**Tests:**
- `anonima-web/tests/test_deploy.py` — 22 tests de deploy, todos parametrizados.
- `anonima-web/pytest.ini` y `anonima-web/tests/conftest.py` replicando el patrón del escritorio.

---

## ESTADO ANTERIOR (2026-05-22 — Rollback a Tesseract por Incompatibilidad OneDNN de PaddleX)

### Sesión 2026-05-22 (Antigravity) — Fix de Crash en PaddleOCR / PaddleX en Windows

**Síntoma reportado por el usuario:** "Errores parciales en algunas páginas: Pág 1: PaddleOCR.predict() got an unexpected keyword argument 'cls'".

**Diagnóstico:** 
- El agente anterior restauró el uso de PaddleOCR (versión 3.5.0), asumiendo que al inhabilitar explícitamente `FLAGS_use_mkldnn` (`os.environ['FLAGS_use_mkldnn'] = '0'`) se resolvería el colapso del framework.
- Sin embargo, la versión actual instalada de `paddlepaddle` (3.3.1) en arquitectura Windows tiene un bug profundo de implementación en `onednn_instruction.cc` ( `ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]` ) que hace colapsar el pipeline de PaddleX independientemente de la flag de entorno de MKLDNN.
- Adicionalmente, `PaddleOCR 3.5.0` ha deprecado el método `.ocr()` clásico con el kwarg `cls=True` en favor de `predict()`, cambiando totalmente la firma y la estructura de retorno.

**Fix aplicado:**
- Se dio reversa a la integración inestable de PaddleOCR en `src/ocr_engine.py`.
- Se restauró la integración madura de **Tesseract OCR**.
- Dado que Tesseract puede sufrir problemas de delimitación (`\b`) con marcas de agua oscuras en documentos escaneados (INE), los validadores Regex en `src/detector.py` ya se encontraban previamente flexibilizados para tolerar uniones de palabras por fallos de Tesseract (ej. omitir los boundaries `\b` y validar `[A-Z\d]` en género).
- Se añadió un test unitario (`tests/test_ui_error_handling.py`) para verificar que las caídas de OCR sean capturadas graciosamente y enviadas a la cola de `errores_procesamiento` de la UI (sin colgar la ventana con Excepciones nativas).

**Tests:**
- La suite de UI (`test_ui_error_handling.py`) pasa correctamente.
- La extracción por Tesseract para documentos escaneados opera como el motor estándar actual de ANONIMA.
