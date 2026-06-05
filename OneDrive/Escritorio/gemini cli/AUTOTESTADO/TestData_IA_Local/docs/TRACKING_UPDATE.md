## ESTADO ACTUAL (2026-06-05 — Endurecimiento contra documento adversarial + sincronización de listas)

### Sesión 2026-06-05 — Prueba de máxima dificultad, fusión MX_ESCOLAR y validación de contexto

Sesión enfocada en robustez: pruebas con documentos reales (curp.pdf, CENEVAL EGEL.pdf) y un PDF adversarial generado a propósito, más la unificación del modelo de datos escolares y la validación exhaustiva del contexto.

---

#### 1. Documentos reales: curp.pdf y CENEVAL EGEL.pdf

- **curp.pdf** (nativo): detecta CURP, nombre, entidad de registro y el domicilio/colonia/CP del pie de SEGOB. La firmante (servidora pública) NO se testa, por diseño.
- **CENEVAL EGEL.pdf** (texto VECTORIAL, 0 texto nativo, solo un logo de 0.3%): **bug encontrado y corregido** — `_ocr_jpeg_embebidos` hacía OCR solo del logo diminuto y perdía todo el contenido. Fix: si las imágenes embebidas son diminutas (<12% máx, <15% total), cae a OCR de página completa que rasteriza y lee el texto vectorial. Tras el fix detecta nombre, folio y **matrícula** correctamente.

#### 2. Fusión de matrícula en MX_ESCOLAR (dato escolar unificado)

- A petición del usuario, `MX_MATRICULA` se **fusionó en `MX_ESCOLAR`**: un solo tipo de dato escolar que cubre **matrícula + institución educativa + carrera/programa**, sincronizado en las **4 listas** (detección `entidades_validas`/`_PRIORIDAD`, color `COLORES_ENTIDAD`, marcado manual `OPCIONES_TIPO_MANUAL`, acta `legal_mapper`).
- Patrón de institución excluye entidades de gobierno (`Instituto Nacional Electoral/de Migración`); carrera/programa por etiqueta.

#### 3. Auditoría de sincronización de las 4 listas (con agente)

- Un agente auditor verificó que cada tipo de dato aparezca consistente en las 4 listas (detección/color/manual/acta). Resultado: matrícula/escolar faltaban en marcado manual → corregido. Juez/Secretario sin acta propia es intencional (se descartan antes de generarla).

#### 4. Enriquecimiento y validación de contexto (con agentes + Brave MCP)

- Un agente añadió términos de contexto (additivos sobre `_RE_CTX_*` y `_ETIQUETAS_LABEL`) basados en fuentes oficiales: **SEPOMEX/INEGI** (vialidades/asentamientos), **NOM-004-SSA3** (expediente clínico), **LGPDPPSO/LFPDPPP** (datos sensibles: creencias, afiliación sindical, origen racial), y **roles judiciales/notariales** (apelante, albacea, cesionario, fiador, arrendatario…).
- El mismo agente **validó cada término con un script generador** de 455 frases en 6-9 variantes tipográficas (MAYÚSCULAS, minúsculas, Title Case, con/sin acentos, espacios extra, saltos de línea, con/sin dos puntos): **455/455 detectadas**. No hubo que ajustar regex — ya eran tolerantes (acentos opcionales `[oó]`, `\s+` cubre saltos de línea, `re.IGNORECASE`).

#### 5. Prueba de MÁXIMA DIFICULTAD (PDF adversarial)

Se generó `PRUEBA_BRUTAL_ANONIMA.pdf` (4 páginas) con datos de **checksum válido**, formatos mezclados, Title Case vs MAYÚSCULAS, acentos/sin acentos, saltos de línea entre etiqueta y valor, servidores públicos (NO testar) y trampas de falso positivo. Reveló y se corrigieron **6 bugs**:

- **Falso positivo grave (`institucion_edu`):** "Universidad como concepto general…" se testaba porque **Presidio compila todos los patrones con IGNORECASE global**, así que `[A-Z]` casaba minúsculas. Fix: `(?-i:[A-ZÁÉÍÓÚÑ])` fuerza mayúscula REAL en la primera letra del nombre.
- **Fusión de instituciones contiguas:** "Instituto Tecnológico de Durango Escuela Secundaria…" en un solo span → lookahead negativo de cabeceras (Universidad/Escuela/Instituto…) para no encadenar otra institución.
- **Servidor público no filtrado:** "La Secretaria NOMBRE certificó" (secretaria de acuerdos judicial, sin calificador) se testaba → se añadió `Secretari[ao]` suelto a `_TITULOS_SERVIDOR`/`_RE_TITULO_PREVIO`.
- **Autoridad no filtrada:** "Secretaría de Relaciones Exteriores" se testaba → se ampliaron los ministerios (Relaciones Exteriores, Hacienda, Marina, Defensa, Bienestar, Economía…).
- **Prefijos sin recortar:** "Nombre del solicitante: X", "A nombre de: X" dejaban el prefijo en el recuadro. Causa: el prefijo narrativo `NOMBRE\s+` recortaba solo "Nombre " y, al casar, el fallback no corría. Fix: trims **en secuencia** (label → narrativo → `_RE_LABEL_COLON` genérico que recorta cualquier etiqueta terminada en ":"). Además `_RE_NARRATIVA_PREFIX` admite ":" opcional ("A nombre de:").
- **Overmatch de nombre:** "GUADALUPE SANTOS RIVERA Fin" tragaba "Fin" → se ampliaron las palabras-límite `_STOP_NOMBRE` (Fin, Otra, Domicilio, Institución, Matrícula…).

**Resultado del PDF brutal:** 54 entidades correctas, 0 falsos positivos en las trampas, servidores públicos protegidos. Procesado end-to-end en el VPS vía Flask.

#### 6. Documentación (con agente)

- Un agente documentó la sesión 2026-06-04 completa en este archivo (rebrand, despliegue VPS, regresión OCR INE, mejoras de detección, sincronización, contexto), en UTF-8 con acentos correctos.

**Tests:** 117 passed, 1 xfailed, 2 xpassed tras todos los cambios. Sin regresiones. Commits clave de la sesión: `37dbf45` (fusión escolar + Title-Case + Paciente), `7693979` (contexto + tracking), `5a39ac6` (endurecimiento adversarial).

---

## ESTADO ANTERIOR (2026-06-04 — Rebrand ANONIMA + Fix regresión OCR INE + Detección enriquecida)

### Sesión 2026-06-04 — Rebrand, despliegue VPS, fix crítico de OCR de INE y mejoras de detección

Sesión amplia que abarca el renombrado del producto, la corrección de una regresión crítica de coordenadas en el OCR de la INE, mejoras de calidad de OCR, y una ronda extensa de mejoras en la detección y el enriquecimiento de contexto legal. A continuación se documenta por temas.

---

#### 1. Rebranding STINGTEST → ANONIMA

- **Rebrand completo:** Toda referencia a `STINGTEST` reemplazada por `ANONIMA` en los 21 archivos donde aparecía (`.py`, `.md`, `.txt`).
- **`web_launcher.py` (VPS):** Títulos HTML (`ANONIMA — Subir documento / Revisión / Descarga lista`), header `⬛ ANONIMA — Testado de Datos Personales` y rutas temporales `/tmp/stingtest_{uploads,output,status,trigger}` → `/tmp/anonima_*`.
- **Tipografía mejorada:**
  - Escritorio (`ui_validator.py`): `FONT_FAMILY` cambiado de `"Segoe UI"` a `"Segoe UI Variable"` (más moderna en Windows 10/11); encabezado principal usa `"Georgia"` tamaño 20.
  - Acta PDF (`report_generator.py`): `h1` del encabezado aumentado a 13pt, letter-spacing 3px; `h2` más sutil (letter-spacing 1.5px, color #444).
- **Carpeta renombrada:** `stingtest-web/` → `anonima-web/`.
- **Sincronización web ← escritorio:** Los módulos `detector.py`, `pdf_reader.py`, `legal_mapper.py`, `report_generator.py`, `legal_config.json` y `legal_packs/` copiados byte a byte desde `TestData_IA_Local/src/` a `anonima-web/TestData_IA_Local/src/`.
- **Suite de deploy creada:** `anonima-web/tests/test_deploy.py` (22 tests con marca `@pytest.mark.deploy`): estructura del Space, sintaxis de `app.py`, branding, presencia de módulos core, sincronización byte a byte con escritorio, y generación correcta del acta. Acompañada de `anonima-web/pytest.ini` y `anonima-web/tests/conftest.py`.

#### 2. Despliegue real: VPS, NO Hugging Face

- El despliegue productivo de ANONIMA es el **VPS `148.230.82.14`**, sirviendo el stack **Flask + tkinter + noVNC en el puerto `7080`** mediante `web_launcher.py`. **No es un Space de Hugging Face** (los artefactos `app.py`/estructura HF de `anonima-web/` son material de empaquetado heredado, no el destino real). El flujo de trabajo del VPS usa las rutas `/tmp/anonima_{uploads,output,status,trigger}`.

#### 3. Regresión crítica de coordenadas en OCR de INE (causa raíz y fix)

- **Síntoma:** Las cajas de tachado de la INE caían en el lugar equivocado (sobre la página completa, no sobre la credencial).
- **Causa raíz (PyMuPDF):** `_ocr_jpeg_embebidos` llamaba a `get_image_info()` **sin `xrefs=True`**, por lo que el diccionario nunca contenía la clave `xref` → la búsqueda de xref fallaba siempre → el código caía al *fallback* del bbox de página completa.
- **Diagnóstico:** Realizado con un **equipo de agentes orquestados** + revisión de **documentación oficial de PyMuPDF/EasyOCR** (búsqueda Brave/docs oficiales).
- **Fix:** Reescritura de `_ocr_jpeg_embebidos` para usar `page.get_image_rects(xref, transform=True)` + `page.get_pixmap(clip=img_rect)`: rasteriza directamente la región de cada imagen en el espacio de la página, **inmune a rotación/flip**, con mapeo de coordenadas trivial.
- **Resultado:** La INE detecta 8 entidades (nombre, domicilio, CURP, clave de elector, fecha de nacimiento, sexo, CP, MRZ), todas con coordenadas correctas.

#### 4. Calidad de OCR (EasyOCR)

- La ruta de imagen embebida **binarizaba** con `adaptiveThreshold` antes de EasyOCR, pero EasyOCR (CRAFT+CRNN) necesita textura: **la binarización lo degrada**. Se reemplazó por **grayscale + denoise + CLAHE**.
- `ocr_engine.extract_words_from_image`: el parámetro **`width_ths` ahora es parametrizable**; la ruta INE usa `0.5` para no fragmentar CURP/clave de elector.
- Ruta OCR de imagen JPEG embebida previa (`dd0291d`): cuando las imágenes embebidas cubren <85% de la página cada una, extrae los JPEG y corre EasyOCR por imagen (con fallback a render de página completa si no hay imágenes).

#### 5. Mejoras de detección

- **Nombres tras etiquetas legales:** nuevos patrones en `MX_NOMBRE` para `Titular/Contribuyente/Solicitante/Interesado/Causante/Deudor/Trabajador/Asegurado/Beneficiario`, etiquetas judiciales (`Víctima/Ofendido/Imputado/Acusado/Testigo/Denunciante/Quejoso/Actor/Demandado/Arrendador/Fiador/Avalista`) y `Registrado/Madre/Padre/cónyuge`. Patrones `ciudadano_nombre` (`el C. NOMBRE`), `a_nombre_de`, `de_nombre`/`identificado como`/`conocido como`, y `narrativa_legal` para menciones sin dos puntos (`la víctima NOMBRE`).
  - `_NOMBRE_VAL` captura nombres en **Title-Case O MAYÚSCULAS** tras etiqueta (ej. `Víctima: Eva Gallegos Diaz`), de forma **determinista** (no depende de GLiNER).
  - `_NOMBRE_CAPS` con lookahead negativo `(?![A-Z]+\s*:)` y `_RE_NARRATIVA_PREFIX` para recortar el prefijo del span en `_filtrar_falsos_positivos`.
- **Nombre INE determinista:** patrón `nombre_credencial_ine` anclado en la etiqueta `NOMBRE` (tolerante a `SEXO H` intercalado por OCR), se detiene antes de `DOMICILIO/CURP/CLAVE`. Elimina la dependencia de GLiNER zero-shot, que variaba entre local y VPS (el nombre fallaba en el VPS).
- **Domicilio INE (número desnudo):** patrones `domicilio_ine_credencial` + `domicilio_etiqueta_ine` para formato sin keyword `número` (ej. `CTO AMANECER 348 FRACC BRISAS DIAMANTE`), acotado a letras para no invadir CP/clave.
- **`MX_ESCOLAR`:** se **fusionó `MX_MATRICULA` en `MX_ESCOLAR`** (un solo tipo de dato escolar que cubre matrícula, institución y carrera). Patrones de institución + carrera que **excluyen entidades de gobierno** (`Instituto Nacional X`). (`MX_MATRICULA` se introdujo primero como entidad propia con lookbehind sobre `Matrícula` y justificación legal Art. 116 LGTAIP, luego fusionado.)
- **Filtros de falsos positivos:** `_RE_NO_NOMBRE` filtra sustantivos comunes mal etiquetados como nombres (`Paciente`, etc.); guarda contra `MX_NACIONALIDAD` genérica (`en el caso de sustentantes de nacionalidad extranjera`).
- **Fallback OCR para texto vectorial (CENEVAL):** `_ocr_jpeg_embebidos` ahora cae a OCR de página completa cuando las imágenes embebidas son diminutas (<12% máx, <15% total) — p.ej. los certificados CENEVAL son texto vectorial con sólo un pequeño logo; antes sólo se OCRaba el logo y se perdía todo el texto.

#### 6. Sincronización de las 4 listas

- Tras introducir `MX_ESCOLAR`/matrícula, se **auditó con agente** la coherencia de las **4 listas** del sistema: detección (`detector.py`), color (`ui_validator.py`), marcado manual y acta (`report_generator.py`/`legal_mapper.py`). Confirmado por auditoría que el tipo aparece consistente en las cuatro.

#### 7. Enriquecimiento de contexto legal

Se ampliaron los diccionarios de contexto de `detector.py`, probados con **variantes tipográficas verificadas por agente**:

- **Domicilio (`_RE_CTX_DOMICILIO`, SEPOMEX/INEGI):** 40+ keywords — vialidades (`Fracc.`, `Cto.`, `Andador`…), asentamientos (`Colonia`, `Ejido`, `U.H.`, `Residencial`…), elementos numerados (`Mza.`, `Lt.`, `Int.`, `Depto`…) y frases `con domicilio en / ubicado en`; filtra spans sin número ni contexto postal.
- **Lugar de nacimiento (`_RE_CTX_LUGAR_NAC`, nuevo):** `nació en`, `originario/a de`, `acta de nacimiento`, `registro civil`, `estado/municipio de nacimiento`.
- **Nacionalidad (`_RE_CTX_NACIONALIDAD`, nuevo):** `de nacionalidad`, `ciudadano de`, `naturalizado/a`, `extranjería`, `doble nacionalidad`.
- **Datos sensibles (LGPDPPSO):** ampliación de `_RE_CTX_ORIGEN_ETNICO` (pueblos originarios, lengua materna), `_RE_CTX_RELIGION` (sinagoga, mezquita, rabino, imán), `_RE_CTX_OPINION_POLITICA` (ideología, disidente/preso político), `_RE_CTX_PREFERENCIA_SEXUAL` (identidad de género, unión civil, transfobia), `_RE_CTX_BIOMETRICO` (plantilla, perfil genético, reconocimiento de voz) y `_RE_CTX_DIAGNOSTICO` (NOM-004 salud: `diagnóstico de`, `portador/a de`, `cuadro clínico`, `comorbilidad`).

#### Otros fixes

- **Corrupción de encoding en el acta:** corregido el pie de página `Pág. X de Y` y reescrito todo `report_generator.py` con UTF-8 correcto en comentarios y docstrings.

**Tests:**
- Suites pasando sin regresiones a lo largo de la sesión: 39/39 integrales en las mejoras de detección; 94 tests tras el fix de coordenadas INE; 47 tras el ajuste de cajas verticales; 64 tras `MX_MATRICULA`; 57 tras la fusión `MX_ESCOLAR`.
- Validación en VPS: 10/10 casos víctima/imputado; INE con 8 entidades y coordenadas correctas.
- `anonima-web/tests/test_deploy.py` — 22 tests de deploy parametrizados.

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
