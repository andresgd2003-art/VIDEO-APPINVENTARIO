# Fase 1 — Auditoria Normativa y Diccionario de Datos Sensibles

**Proyecto:** ANONIMA
**Fecha:** 2026-05-14 (revalidada contra PDFs oficiales DOF 2025)
**Estado:** COMPLETADA Y VALIDADA

## 1. Marco Legal Aplicable

El sanitizador opera bajo dos leyes federales mexicanas complementarias:

### 1.1 LGTAIP — Ley General de Transparencia y Acceso a la Informacion Publica
- **Vigente:** Nueva Ley DOF 20-03-2025 (abroga la LGTAIP DOF 04-05-2015 y sus reformas)
- **Articulo 115:** define *informacion confidencial* como aquella que contiene datos personales concernientes a persona fisica identificada o identificable. Tambien clasifica como confidencial los secretos bancario, fiduciario, industrial, comercial, fiscal, bursatil y postal de personas particulares.
- ⚠ **Nota:** en la ley abrogada (2015) este contenido estaba en el Art. 116. En la ley vigente el Art. 116 trata fideicomisos.

### 1.2 LGPDPPSO — Ley General de Proteccion de Datos Personales en Posesion de Sujetos Obligados
- **Vigente:** Nueva Ley DOF 20-03-2025, ultima reforma DOF 14-11-2025
- **Art. 3-IX:** *dato personal* — cualquier informacion concerniente a persona identificada o identificable.
- **Art. 3-X:** *dato personal sensible* — origen racial o etnico, salud, genetica, religion, opiniones politicas, preferencia sexual.
- **Art. 3-XIII:** *disociacion* — procedimiento que impide asociacion al titular. **Fundamento juridico-tecnico del sanitizador.**
- **Art. 7 + Art. 15 ultimo parrafo:** consentimiento expreso y por escrito para tratamiento de sensibles (excepciones en Art. 16).
- ⚠ **Nota:** en la ley abrogada (2017) la disociacion era 3-XI y el consentimiento expreso para sensibles era el Art. 21; ahora el Art. 21 trata el contenido del aviso de privacidad.

## 2. Diccionario de Datos Sensibles

El mapeo completo dato → fundamento legal → regex de referencia esta en [`fundamentos_legales.json`](fundamentos_legales.json).

Categorias:
- **personal** (Art. 3-IX LGPDPPSO + Art. 115 LGTAIP): CURP, RFC, PERSON_NAME, domicilio, telefono, email, CLABE, INE, pasaporte, NSS, CP.
- **sensible** (Art. 3-X LGPDPPSO, requiere consentimiento expreso por escrito Art. 15): salud, biometrico, origen etnico, religion, preferencia sexual.

## 3. Hallazgos Clave

1. **Doble marco**: LGTAIP define *que* se protege frente al acceso publico; LGPDPPSO define *como* se trata el dato. Son complementarias.
2. **Identificadores no nombrados explicitamente**: CURP, RFC, INE, NSS, CLABE y pasaporte no aparecen textualmente en la ley, pero caen bajo la definicion amplia de dato personal (Art. 3-IX) y se refuerzan con criterios INAI + Art. 115.
3. **Disociacion como fundamento tecnico**: el Art. 3-XIII LGPDPPSO es la base juridica que habilita el sanitizador (eliminar el dato de forma que no pueda re-asociarse al titular).
4. **Sensibles requieren tratamiento reforzado**: salud, biometricos, origen etnico, religion y preferencia sexual exigen consentimiento expreso y por escrito (Art. 15 ultimo parrafo, excepciones en Art. 16).
5. **Reforma 2025**: las leyes vigentes son nuevas, expedidas tras la reforma constitucional de simplificacion organica (dic-2024) que extinguio al INAI. La sustancia conceptual de los conceptos clave se mantuvo, pero la numeracion cambio respecto a leyes abrogadas.

## 4. Implicaciones para Fases siguientes

- **Fase 2 (Stack):** Presidio + spaCy `es_core_news_md` cubren PERSON_NAME y domicilio (NER). Patrones regex deben implementarse como `PatternRecognizer` para CURP, RFC, INE, CLABE, NSS, telefono, CP, email.
- **Fase 3 (Modulos):** `detector.py` debe consumir el diccionario y poblar dinamicamente los recognizers de Presidio con el campo `regex_referencia`.
- **Orden de deteccion:** ejecutar primero los de mayor longitud/especificidad (CURP 18 → RFC → INE → CLABE → NSS) antes que los permisivos (telefono, CP) para evitar solapamientos. Ver `orden_deteccion_recomendado` en el JSON.
- **Validadores checksum requeridos:** CLABE (mod 10 ponderado [3,7,1]), NSS (Luhn), CURP (digito verificador). Reducen falsos positivos en regex permisivos.

## 5. Validacion y Fuentes

- Citas literales extraidas con `pdfplumber` directamente de los PDFs oficiales descargados de `diputados.gob.mx/LeyesBiblio/pdf/`:
  - `docs/LGTAIP.pdf` — DOF 20-03-2025
  - `docs/LGPDPPSO.pdf` — DOF 20-03-2025 con reforma 14-11-2025
- Scrubadub fue inspiracion arquitectonica (Detector → Filth → PostProcessor) pero su corpus regex es anglocentrico; solo el EmailDetector se reutilizo. CURP, RFC, CLABE, INE, NSS, telefono MX y CP se crearon desde cero contra catalogos RENAPO/SAT/CONSAR/INE.

## 6. Entregables Fase 1

- [x] `docs/fundamentos_legales.json` v2.0 — diccionario maquina-legible validado
- [x] `docs/FASE1_AUDITORIA_NORMATIVA.md` — este documento
- [x] `docs/LGTAIP.pdf` y `docs/LGPDPPSO.pdf` — fuentes oficiales
- [x] `docs/TRACKING.md` — bitacora de estado
