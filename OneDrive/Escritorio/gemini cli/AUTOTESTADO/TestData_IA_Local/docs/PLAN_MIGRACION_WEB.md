# Investigación y Plan de Migración a Aplicación Web

El objetivo de este documento es trazar una estrategia técnica para transformar el actual sistema de testado de datos personales (una aplicación de escritorio nativa en Python con `customtkinter`) en una aplicación web, partiendo de su alojamiento en GitHub.

**Regla de Oro:** El proyecto original de escritorio debe mantenerse intacto. La migración web será un *spin-off* o una rama paralela (backend/frontend) para garantizar cero regresiones en el sistema actual.

---

## 1. Investigación Técnica y Limitaciones

### 1.1. El mito de "Subirlo a GitHub" (GitHub Pages)
GitHub ofrece un servicio llamado **GitHub Pages**, que permite alojar páginas web de forma gratuita directamente desde un repositorio. Sin embargo, GitHub Pages es exclusivamente para **páginas estáticas** (HTML, CSS, JavaScript nativo o frameworks como React/Vue/Angular). 
**Limitación:** GitHub Pages **no puede ejecutar código Python**, ni alojar un servidor backend, ni correr modelos de Inteligencia Artificial como GLiNER o PaddleOCR.

### 1.2. Requisitos de la Aplicación Actual
El sistema actual es muy "pesado" en términos computacionales porque:
- Utiliza **PaddleOCR** (requiere procesamiento intensivo para analizar imágenes).
- Utiliza **GLiNER / Presidio / Transformers** (modelos de Machine Learning de Procesamiento de Lenguaje Natural).
- Utiliza **PyMuPDF** para la manipulación y renderizado avanzado de archivos PDF.

Dado esto, el código Python *debe* correr en un servidor (Backend) o en un entorno en la nube especializado.

### 1.3. Alternativas Viables para la Versión Web

Existen tres caminos principales para convertir esta herramienta en una web app:

| Opción | Arquitectura | Alojamiento | Complejidad | Costo estimado |
| :--- | :--- | :--- | :--- | :--- |
| **Opción A: Streamlit / Gradio** | Framework web de Python. Convierte scripts en web apps automáticamente. | **Hugging Face Spaces** o **Render**. (Extrae el código directo de GitHub). | **Baja**. Se reutiliza el 90% del código backend actual. | Gratis (capa básica) / Muy bajo. |
| **Opción B: Backend API + Frontend Separado** | **Backend:** FastAPI/Flask (Python).<br>**Frontend:** React / Vue / HTML. | Frontend en **GitHub Pages/Vercel**.<br>Backend en **AWS / Google Cloud / Render**. | **Alta**. Requiere programar la interfaz web desde cero y crear una API REST. | Medio/Alto (el backend procesa PDFs e IA, requiere RAM/CPU). |
| **Opción C: WebAssembly (PyScript)** | Python corriendo directamente en el navegador del usuario. | Todo en **GitHub Pages**. | **Muy Alta / Experimental**. Librerías pesadas como GLiNER o PaddleOCR no son 100% compatibles con el navegador hoy en día. | Gratis. |

**Recomendación:** La **Opción B** es la más escalable y profesional, pero la **Opción A (Streamlit en Hugging Face Spaces)** es la más rápida para tener un prototipo funcional sin destruir la lógica actual y de forma muy económica. A continuación trazamos el plan para la **Opción B** (Arquitectura Profesional), adaptada a buenas prácticas.

---

## 2. Plan de Acción Paso a Paso (Arquitectura Desacoplada)

Para preservar el proyecto original, el desarrollo web constará de dos partes: una Interfaz de Usuario Web (Frontend) y un Motor de Procesamiento (Backend).

### Fase 1: Preparación y Prácticas Seguras (Semana 1)
1. **Separación de Lógica e Interfaz:**
   - Aislar completamente la lógica de `src/detector.py`, `src/sanitizer.py`, y `src/report_generator.py` de cualquier dependencia gráfica (`tkinter`, `customtkinter`, `messagebox`).
   - El proyecto original ya está bastante modularizado, lo cual facilita este paso.
2. **Creación de Repositorios Independientes (o Monorepo estructurado):**
   - En GitHub, se creará un directorio `backend/` (código Python) y un directorio `frontend/` (código Web), paralelos al `desktop_app/` (actual).
3. **Dockerización:**
   - Crear un archivo `Dockerfile` para empaquetar el backend de Python junto con sus modelos OCR y NLP. Esto asegura que funcionará en cualquier nube exactamente igual que en la computadora local.

### Fase 2: Desarrollo del Backend Web (Semana 2)
1. **Creación de API con FastAPI:**
   - Envolver el pipeline actual en endpoints web.
   - Endpoint `POST /upload`: Recibe un documento PDF, lo procesa asíncronamente (con GLiNER y PaddleOCR) y devuelve un archivo JSON con las entidades y coordenadas detectadas.
   - Endpoint `POST /redact`: Recibe el PDF, el JSON validado (con las correcciones del usuario) y devuelve el PDF testado junto con el Acta generada.
2. **Gestión de Memoria y Almacenamiento Temporal:**
   - La nube no mantiene estados como un programa de escritorio. Los PDFs subidos deben guardarse temporalmente (por ejemplo, en Amazon S3 o en memoria efímera local) y borrarse inmediatamente tras ser procesados (por seguridad y cumplimiento de la LGTAIP).

### Fase 3: Desarrollo del Frontend Web (Semana 3)
1. **Framework Moderno:**
   - Usar React.js o Vue.js (alojados en Vercel, Netlify o GitHub Pages).
2. **Visor de PDF en el Navegador:**
   - Integrar una librería como `pdf.js` para renderizar el documento en la pantalla del usuario.
3. **Visor de Cajas y Marcado Manual:**
   - Implementar un lienzo (Canvas) HTML5 sobrepuesto al visor PDF para dibujar dinámicamente las cajas rojas de las entidades detectadas por la API, permitiendo al usuario eliminarlas o dibujar nuevas (replicando lo que hoy hace el canvas interactivo de Tkinter).

### Fase 4: Despliegue en la Nube (Semana 4)
1. **Despliegue del Frontend:**
   - Conectar la carpeta web a **GitHub Pages** (o Vercel). Cada vez que se haga un *push* a GitHub, la página web se actualizará.
2. **Despliegue del Backend:**
   - Subir el contenedor Docker a un servicio Cloud como **Google Cloud Run**, **AWS App Runner** o **Render**. Estos servicios pueden soportar los requerimientos de RAM necesarios para PaddleOCR y GLiNER.
3. **Seguridad y Cifrado (HTTPS):**
   - Configurar certificados SSL (HTTPS). Los documentos legales no pueden viajar en texto plano.

---

## 3. Prácticas de Seguridad y Estabilidad (Manteniendo el proyecto original intacto)

1. **Gestión de Ramas (Branching en Git):**
   - Nunca trabajar la migración en la rama `main` original. Crear una rama llamada `feature/web-migration` o alojar la versión web en repositorios complementarios (ej. `anonima-api` y `anonima-web`).
2. **Abstracción Total de la UI:**
   - El código central (`pdf_reader`, `detector`, `mapper`) debe ser una librería pura (Core). El cliente de escritorio importa este Core, y la API web importa este mismo Core. Si hay un bug en el OCR y se arregla en el Core, se arreglará automáticamente tanto para el escritorio como para la web.
3. **Privacidad de los Modelos Creados:**
   - No subir archivos de modelos muy pesados (.bin, .pt) directamente a GitHub. En su lugar, el `Dockerfile` del backend debe descargarlos durante la construcción desde repositorios oficiales de Hugging Face.
4. **Borrado Forense de Datos Web:**
   - A diferencia de un entorno local cerrado, en web el servidor toca documentos de terceros. El código backend deberá usar el módulo `tempfile` de Python y scripts de limpieza (*garbage collection*) que purguen cualquier rastro de PDF procesado de la memoria RAM y del disco del servidor inmediatamente tras devolver la descarga al usuario.
