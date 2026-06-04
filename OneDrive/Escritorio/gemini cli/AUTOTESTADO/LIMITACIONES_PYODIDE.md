# Investigación: ¿Es posible ejecutar ANONIMA 100% en GitHub Pages usando PyScript/Pyodide?

Tras realizar una investigación profunda a través de la web sobre el ecosistema actual de **WebAssembly (WASM), Pyodide y PyScript**, la respuesta corta es: **Teóricamente sí se puede correr Python estático en GitHub Pages, pero para este proyecto en particular (OCR + IA), es inviable e inestable en producción.**

A continuación, presento los hallazgos y limitaciones técnicas específicas para las librerías que utiliza nuestro sistema de testado:

## 1. El entorno: Pyodide y PyScript
Hoy en día, herramientas como **PyScript** o **Pyodide** permiten compilar el intérprete de Python a WebAssembly (WASM). Esto significa que el código Python se descarga y se ejecuta *directamente en el navegador del usuario* (Chrome, Edge, Firefox) sin necesidad de un servidor backend. Como GitHub Pages es un host estático, funciona perfectamente para servir estos archivos a la máquina del cliente.

### ¿Dónde funciona muy bien?
Scripts pequeños de análisis de datos con librerías estándar: `numpy`, `pandas`, o `matplotlib`. 

## 2. Los Bloqueos Técnicos para ANONIMA

El proyecto actual no es un script ligero. Utiliza redes neuronales profundas (Deep Learning) y librerías precompiladas en C++ que chocan frontalmente con las limitaciones de los navegadores actuales.

### A. El problema de PaddleOCR (Binarios C++ y Aceleración de Hardware)
- PaddleOCR requiere el framework **PaddlePaddle**. Este framework depende estrictamente de librerías nativas del sistema operativo (C++, MKL de Intel, OpenBLAS) para cálculos matriciales ultrarrápidos.
- Compilar PaddlePaddle a WebAssembly para que corra dentro de Pyodide es una tarea hercúlea que hoy en día no cuenta con soporte oficial robusto.
- Si lograras compilarlo, PaddleOCR perdería el acceso a la aceleración por hardware nativo (instrucciones AVX de la CPU o tarjetas gráficas). En nuestras pruebas, el OCR nativo pasaba de tardar 20 segundos a más de 8 minutos al perder optimizaciones. En un navegador a través de WebAssembly, **el tiempo de espera por página se volvería inaceptable**.

### B. El problema de GLiNER / Presidio (Tamaño de Modelos y Memoria RAM)
- El modelo GLiNER (o los modelos de HuggingFace/Transformers) requiere cargar cientos de megabytes de pesos neuronales a la memoria RAM.
- **Tiempos de Carga (Cold Start):** Como GitHub Pages solo sirve archivos estáticos, el navegador de cada usuario tendría que descargar todo el entorno Python (aprox. 20-30MB) + PyMuPDF (15MB) + los modelos OCR y NLP (200MB a 1GB) **cada vez que entra a la página o la recarga**. Esto consume un ancho de banda masivo y tarda minutos solo en cargar la página inicial.
- **Límite de RAM del Navegador:** Los navegadores imponen límites estrictos a la memoria que una pestaña de WebAssembly puede usar (típicamente entre 2GB y 4GB). Cargar PyMuPDF, modelos de IA y procesar un PDF escaneado pesado saturaría la pestaña provocando el famoso error `"Aw, Snap!"` (Página bloqueada por falta de memoria).

### C. El problema de PyMuPDF y el OCR Híbrido
- Investigando la documentación reciente de `PyMuPDF`, sí tienen soporte para **Pyodide** (tienen un archivo `.whl` compilado para Emscripten).
- Sin embargo, para la extracción de texto en imágenes y redacción forense (garbage=4), el rendimiento decae, y dependemos estrictamente del módulo externo OCR. PyMuPDF delega el OCR localmente a Tesseract o similar, lo que rompe de nuevo el ecosistema cerrado del navegador.

## 3. Veredicto y Conclusión

Aunque usar GitHub Pages + Pyodide suena ideal porque el hosting es gratuito y no requiere mantenimiento de servidores:

> **Intentar empaquetar PaddleOCR y Modelos Transformer en el navegador mediante Pyodide para GitHub Pages resultará en una aplicación que tarda minutos en abrir, que congela la pestaña del usuario y que probablemente fallará por falta de memoria RAM.**

### La única alternativa real de arquitectura "Serverless"
Si el objetivo es evitar pagar por un servidor backend (Backend 24/7), existe un punto intermedio: **Hugging Face Spaces**. 

Hugging Face te regala un contenedor gratuito (con CPU de 16GB de RAM) diseñado explícitamente para hospedar modelos de Machine Learning (como GLiNER y PaddleOCR) subiendo directamente tu código allí. Esto permite tener la aplicación como una página web accesible mundialmente, delegando el procesamiento pesado a un servidor real, sin costo.

---

## 4. Plan de Acción: Alojamiento Directo en Hugging Face Spaces (con Gradio/Streamlit)

Para transformar nuestra app (basada en `customtkinter`) a la web usando Spaces, podemos subir nuestros archivos y modelos directamente al repositorio integrado de Hugging Face. El plan de 5 pasos es:

### Paso 1: Crear una Interfaz Web en un archivo separado
Dado que `customtkinter` no funciona en la web, debemos crear un script independiente llamado `app.py`. Este archivo utilizará **Gradio** (la librería estándar y más recomendada por Hugging Face) o **Streamlit** para la interfaz web.
- El archivo `app.py` **importará tu código original** (ej. `from src.pdf_reader import ...`, `from src.detector import ...`).
- Creará una interfaz donde el usuario pueda subir un archivo PDF, elegir configuraciones, y presionar un botón "Analizar".
- La lógica subyacente seguirá siendo exactamente la misma. El escritorio usará `ui_validator.py` y la web usará `app.py`.

### Paso 2: Crear el archivo `requirements.txt`
Hugging Face necesita saber qué librerías instalar en su servidor antes de arrancar. 
Crearemos un archivo `requirements.txt` en la raíz del repositorio de Hugging Face con:
```txt
gradio==4.0.0
PyMuPDF==1.24.2
paddlepaddle==3.3.1
paddleocr==3.5.0
gliner==0.1.12
# (y las demás dependencias de nuestro proyecto actual)
```

### Paso 3: Configurar el Espacio en Hugging Face
1. Crear una cuenta gratuita en [Hugging Face](https://huggingface.co).
2. Ir a **"Create new Space"** (Crear nuevo espacio).
3. Elegir un nombre (ej. `anonima-validador`).
4. En **"Space SDK"**, seleccionar **Gradio** (recomendado) o **Streamlit**.
5. En **"Space Hardware"**, seleccionar la opción gratuita **"CPU basic (16GB RAM, 2 vCPU)"**, que es suficiente para nuestra arquitectura.

### Paso 4: Subir el código a Hugging Face
Existen dos formas de subir tu código directamente al repositorio de Hugging Face:
- **Subida Manual (Fácil):** Desde la interfaz web del Space recién creado en Hugging Face, ve a la pestaña "Files" y haz clic en "Add file -> Upload files" para arrastrar y soltar tu archivo `app.py`, `requirements.txt` y la carpeta `src`.
- **Git Push Directo (Avanzado):** Hugging Face te proporciona un comando para clonar el repositorio de tu Space a tu computadora local (`git clone https://huggingface.co/spaces/tu-usuario/anonima-validador`). Copias tus archivos allí y luego haces `git push` directo a sus servidores.

### Paso 5: Despliegue y Limitaciones de la Versión Gratuita
Al terminar la sincronización, Hugging Face instalará las librerías, descargará los modelos (como GLiNER) la primera vez, y lanzará la web de Gradio. 
**A tener en cuenta en el Tier Gratuito:**
- **Sleep Mode (Modo de reposo):** Si la web no recibe visitas por 48 horas, el servidor se "duerme" para ahorrar recursos. El siguiente visitante que entre tendrá que esperar unos 2 o 3 minutos a que el servidor "despierte" e instale todo de nuevo. Las visitas posteriores serán instantáneas.
- **Sin Aceleración GPU:** PaddleOCR usará CPU. Seguirá funcionando bastante bien (como ya logramos optimizarlo), pero no tendrá la velocidad ultra-rápida de una tarjeta gráfica de miles de dólares.

**Conclusión:** Esta estrategia permite mantener el código nativo de escritorio intacto, reciclando toda la lógica de validación e IA para la web, ofreciendo una experiencia profesional y gratuita mediante Hugging Face Spaces.
