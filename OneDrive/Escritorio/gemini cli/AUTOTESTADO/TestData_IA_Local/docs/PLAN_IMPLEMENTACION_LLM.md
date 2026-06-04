# Plan de Implementación y Testing del Modelo LLM (Auditor Inteligente)

Este documento describe la hoja de ruta estructurada en fases para la integración, estabilización y pruebas de estrés del modelo `Llama 3.2` como capa de auditoría en la arquitectura híbrida de **ANONIMA**.

---

## FASE 1: Validación Estructural (Smoke Testing Local)
**Objetivo:** Confirmar que la infraestructura local puede soportar la inferencia del LLM sin fugas de memoria y que la API interna se comunica correctamente con el binario de Ollama.

**Pasos de Implementación:**
1. Instalación de Ollama Daemon.
2. Descarga del checkpoint `llama3.2` vía CLI.
3. Configuración del timeout y retries en la librería `httpx` de Python (`src/llm_auditor.py`).

**Tests (Pruebas a ejecutar):**
- [ ] **Test de Conectividad:** Hacer ping al endpoint `http://localhost:11434/api/generate` para verificar que el servicio está levantado.
- [ ] **Test de Fallback (Resiliencia):** Apagar deliberadamente Ollama y ejecutar el sistema. Comprobar que ANONIMA redirige el análisis de vuelta a `Presidio` puro sin lanzar errores fatales (`Exception Handling`).
- [ ] **Test de Latencia Base:** Enviar un prompt mínimo (ej. "Hola") y verificar que la latencia (TTFT - *Time To First Token*) no exceda los 5 segundos.

---

## FASE 2: Calibración Lingüística y de Rol (Zero-Shot Prompting)
**Objetivo:** Asegurar que el LLM entienda su rol estricto como Auditor Jurídico de Transparencia (INAI) y que solo devuelva listas JSON estandarizadas sin añadir comentarios conversacionales ("Claro, aquí tienes la respuesta...").

**Pasos de Implementación:**
1. Ajuste del `System Prompt` en `llm_auditor.py` imponiendo reglas estrictas de salida.
2. Configurar `temperature=0.0` para garantizar respuestas deterministas y eliminar la creatividad matemática del modelo.

**Tests (Pruebas a ejecutar):**
- [ ] **Test de Alucinación:** Pasar un documento vacío o sin datos confidenciales y asegurar que el LLM devuelva estrictamente un JSON vacío `[]`.
- [ ] **Test de Formato Json:** Pasar 5 textos de prueba simulados y pasar la salida del LLM por `json.loads()`. La prueba falla si el LLM inyecta texto fuera de la estructura de array.

---

## FASE 3: Refinamiento de Falsos Positivos (Edge Cases de la Fase 1)
**Objetivo:** Utilizar la inteligencia de contexto del LLM para resolver los errores históricos de Presidio.

**Pasos de Implementación:**
1. Intercepción del array `presidio_results` antes del renderizado en UI.
2. Inyección del array como contexto para el prompt del LLM.

**Tests (Pruebas a ejecutar):**
- [ ] **Test de Separación de Prefijos:** Pasar la frase `"Clave: JURX990312"`. Verificar que el LLM rectifica las coordenadas de Presidio y solo censura `JURX990312`, ignorando la palabra `"Clave:"`.
- [ ] **Test de Servidores Públicos:** Pasar un documento con la firma del `"Presidente Municipal Andrés Silva"`. Comprobar que el LLM dictamina `IS_PUBLIC_SERVANT: TRUE` y desactiva el recuadro de censura, manteniéndolo visible en la versión pública.

---

## FASE 4: Pruebas End-to-End (E2E) con la GUI Multi-Página
**Objetivo:** Integrar el LLM en el flujo asíncrono de la interfaz gráfica sin afectar la experiencia de usuario (UX).

**Pasos de Implementación:**
1. Actualización del botón `Analizar Página` para cambiar a estado "Analizando (Auditor IA)...".
2. Manejo de concurrencia: asegurar que la GUI no se congele durante los ~3-10 segundos que el LLM toma en validar una página densa.

**Tests (Pruebas a ejecutar):**
- [ ] **Test de Congelamiento de UI:** Hacer scroll y usar el Paneo (arrastre de mouse) sobre el PDF *mientras* el LLM está auditando en segundo plano. La app debe seguir siendo responsiva.
- [ ] **Test Multi-Página:** Analizar la página 1 y luego saltar rápidamente a la página 2 y pedir otro análisis. Comprobar que los resultados del LLM se almacenan en el diccionario correcto (`pages_data`) sin mezclar entidades de distintas hojas.
- [ ] **Test de Renderizado de Carátula:** Dar clic en "Aplicar y Guardar" tras el filtro LLM y verificar que los fundamentos legales inyectados en la Carátula de Justificación (Página 0) correspondan *exactamente* a lo dictaminado por la IA.
