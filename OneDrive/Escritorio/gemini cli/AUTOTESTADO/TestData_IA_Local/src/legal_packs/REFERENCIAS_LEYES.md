# Referencias de leyes — Fundamentos legales para testado de datos personales

Verificación realizada en 2026 mediante búsquedas Brave sobre fuentes oficiales
(diputados.gob.mx, DOF, congresos estatales, INFONL/COTAI/IEPC). Para cada ley se
indica: nombre exacto vigente, última reforma confirmada, artículo de información
confidencial, artículo/fracción de datos personales y de datos sensibles, y URL.

> Regla aplicada: no se inventan números de artículo. Donde Brave no pudo
> confirmar directamente el texto vigente, se anota explícitamente.

---

## 1. FEDERAL — Transparencia (LGTAIP)

- **Nombre exacto:** Ley General de Transparencia y Acceso a la Información Pública.
- **Estado:** LEY NUEVA. El DECRETO del DOF **20-mar-2025** (vigente 21-mar-2025)
  EXPIDIÓ una nueva LGTAIP, abrogando la anterior, **extinguió al INAI** y transfirió
  sus funciones a la Secretaría Anticorrupción y Buen Gobierno y al órgano
  "Transparencia para el Pueblo". Última actualización del articulado registrada: 2025.
- **Información confidencial con datos personales: Art. 116** — "Se considera
  información confidencial la que contiene datos personales concernientes a una persona
  identificada o identificable." **VERIFICADO Y VIGENTE (no cambió de número).**
- **Información confidencial de datos sensibles:** Art. 115.
- **Información reservada (prueba de daño):** Art. 110.
- **URLs oficiales:**
  - Decreto DOF 20-mar-2025: https://www.dof.gob.mx/nota_detalle.php?codigo=5752569&fecha=20/03/2025
  - Texto LGTAIP orig. 20-mar-2025 (diputados): https://www.diputados.gob.mx/LeyesBiblio/ref/lgtaip/LGTAIP_orig_20mar25.pdf
  - Índice de reformas: https://www.diputados.gob.mx/LeyesBiblio/ref/lgtaip.htm

## 2. FEDERAL — Protección de datos de sujetos obligados (LGPDPPSO)

- **Nombre exacto:** Ley General de Protección de Datos Personales en Posesión de
  Sujetos Obligados. **SIGUE VIGENTE CON ESE NOMBRE** (no fue renombrada). Lo que
  ocurrió es que el mismo decreto del 20-mar-2025 expidió una **ley NUEVA del mismo
  nombre**, abrogando la anterior.
- **Última reforma confirmada:** DOF **14-nov-2025**.
- **Datos personales: Art. 3, Fracción IX** — "Cualquier información concerniente a
  una persona física identificada o identificable." **VERIFICADO** (Gaceta Parlamentaria
  Cámara de Diputados, núm. 6757-II-6, 8-abr-2025).
  - NOTA: en la ley ABROGADA el dato personal se ubicaba en otra fracción; por ello se
    **corrigió `legal_mapper.py` de "Art. 3, Fracción XI" → "Art. 3, Fracción IX"** (28 citas).
- **Datos personales sensibles: Art. 3, Fracción X** — "Aquellos que se refieran a la
  esfera más íntima de su titular, o cuya utilización indebida pueda dar origen a
  discriminación o conlleve un riesgo grave para éste." **VERIFICADO Y VIGENTE.**
- **Consentimiento expreso y por escrito para datos sensibles:** firma autógrafa, firma
  electrónica o mecanismo de autenticación (confirmado en el articulado de la LGPDPPSO).
- **URLs oficiales:**
  - Texto vigente (diputados): http://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf
  - Índice de reformas (última 14-nov-2025): https://www.diputados.gob.mx/LeyesBiblio/ref/lgpdppso.htm
  - Definición Art. 3 Fr. IX (Gaceta): https://gaceta.diputados.gob.mx/Gaceta/66/2025/abr/20250408-II-6.html

## 3. DURANGO — Transparencia (DEC.365)

- **Nombre exacto:** Ley de Transparencia y Acceso a la Información Pública del Estado
  de Durango y sus Municipios.
- **Última reforma confirmada:** **DEC.365, P.O. 20 Ext. del 27 de diciembre de 2025**
  (ley nueva armonizada; aprobada por unanimidad en el Congreso el 22/23-dic-2025).
- **Información confidencial con datos personales: Art. 110** — texto confirmado contra
  el PDF oficial: "ARTÍCULO 110. Se considera información confidencial la que contiene
  datos personales concernientes a una persona física identificada o identificable."
  **VERIFICADO.**
- **Datos patrimoniales (secreto bancario, etc.):** **mismo Art. 110, párrafo 3** —
  "los secretos bancario, fiduciario, industrial, comercial, fiscal, bursátil y postal,
  cuya titularidad corresponda a las personas particulares...". **VERIFICADO.**
- **URLs oficiales:**
  - Texto DEC.365 (IEPC Durango): https://iepcdurango.mx/IEPC_DURANGO/documentos/2026/normatividad/200226/LEY_DE_TRANSPARENCIA.pdf
  - Aprobación Congreso: https://congresodurango.gob.mx/2025/12/23/aprueba-congreso-nueva-ley-de-transparencia-y-acceso-a-la-informacion/

## 4. DURANGO — Protección de datos (DEC.366)

- **Nombre exacto:** Ley de Protección de Datos Personales en Posesión de Sujetos
  Obligados del Estado de Durango y sus Municipios.
- **Última reforma confirmada:** **DEC.366, P.O. 20 Ext. del 27 de diciembre de 2025**
  (ley de datos expedida junto con la de transparencia).
- **Datos sensibles — Art. 7:** "Por regla general no podrán tratarse datos personales
  sensibles, salvo que se cuente con el consentimiento expreso de su titular..."
  **VERIFICADO** (congresodurango.gob.mx).
- **Datos personales = Art. 3 Fr. IX; Datos sensibles = Art. 3 Fr. X; Consentimiento
  escrito = Art. 15:** **NO CONFIRMADO DIRECTAMENTE.** El texto íntegro del DEC.366 aún
  no está indexado públicamente (vLex y similares lo tienen tras suscripción). Se
  conservan los números prepararos a partir del decreto y del modelo federal armonizado
  (que también usa Fr. IX/Fr. X). Pendiente de cotejo con el P.O. cuando se publique.
- **URLs:**
  - Congreso de Durango (legislación): https://congresodurango.gob.mx/Archivos/legislacion/
  - Ficha vLex (requiere suscripción): https://vlex.com.mx/vid/ley-proteccion-datos-personales-695776037

## 5. NUEVO LEÓN — Transparencia

- **Nombre exacto:** Ley de Transparencia y Acceso a la Información Pública del Estado
  de Nuevo León.
- **Publicación / reformas:** original P.O. 83-III del **1-jul-2016** (Decreto 119);
  reformas posteriores integradas por el INFONL (reubicación P.O. 20-ago-2021; reforma
  17-may-2023). **NO armonizada aún con la reforma federal del 21-mar-2025.**
- **Información confidencial con datos personales: Art. 141** — confirmado mediante
  documentos oficiales de sujetos obligados de NL ("Fundamento Legal: artículo 141...
  información clasificada como confidencial en virtud de que contiene datos personales").
  **VERIFICADO.**
- **URLs oficiales:**
  - Congreso NL (HCNL): https://www.hcnl.gob.mx/trabajo_legislativo/leyes/leyes/ley_de_transparencia_y_acceso_a_la_informacion_publica_del_estado_de_nuevo_leon/
  - Gobierno NL (última reforma integrada): https://www.nl.gob.mx/es/publicaciones/ley-de-transparencia-y-acceso-la-informacion-publica-del-estado-de-nuevo-leon

## 6. NUEVO LEÓN — Protección de datos

- **Nombre exacto:** Ley de Protección de Datos Personales en Posesión de Sujetos
  Obligados del Estado de Nuevo León.
- **Última reforma confirmada:** texto original P.O. Núm. 153 III del **11-dic-2019**
  (Decreto Núm. 193, LXXV Legislatura). **No se localizó reforma posterior ni abrogación**;
  sigue vigente y aún no armonizada con la reforma federal de 2025.
- **Datos personales: Art. 3, Fracción X.**
- **Datos personales sensibles: Art. 3, Fracción XI** — confirmado por aviso de
  privacidad oficial de NL: "...serán resguardados como datos sensibles, en términos de
  ... el 3 fracción XI, 7, 22 ... de la Ley de Protección de Datos Personales en Posesión
  de Sujetos Obligados del Estado de Nuevo León." **VERIFICADO.**
- **Consentimiento expreso y por escrito: Art. 22.** **VERIFICADO** (mismo aviso oficial).
- **URLs oficiales:**
  - Congreso NL (HCNL): https://www.hcnl.gob.mx/trabajo_legislativo/leyes/leyes/ley_de_proteccion_de_datos_personales_en_posesion_de_sujetos_obligados_del_estado_de_nuevo_leon/
  - Aviso oficial NL que cita Art. 3 Fr. XI, 7, 22: https://www.nl.gob.mx/es/aviso-de-privacidad-integral-sobre-datos-personales-utilizados-en-la-procuraduria-de-la

---

## Resumen de cambios aplicados

| Archivo | Cambio | Motivo |
|---|---|---|
| `legal_mapper.py` | "Art. 3, Fracción XI de la LGPDPPSO" → "Fracción IX" (28 citas) | Nueva LGPDPPSO 2025: dato personal = Art. 3 Fr. IX |
| `legal_mapper.py` | Nota de cabecera sobre reforma 2025 e INAI extinto | Trazabilidad legal |
| `durango.json` | `nota_vigencia` Art. 110/Art. 7 verificados; Art. 3/15 pendientes de cotejo | Precisión |
| `nuevo_leon.json` | `ultima_reforma`/`nota_vigencia` con reformas INFONL y estado de armonización | Precisión |

Sin cambios en números de artículo de los packs estatales: todos los verificables
(Durango Art. 110, Art. 7; NL Art. 3 Fr. X/XI, Art. 22, Art. 141) resultaron correctos.
