import pytesseract
from PIL import Image
import cv2
import os

# Configuración de ruta para Windows (donde se suele instalar Tesseract con winget)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Define the custom configuration for Tesseract based on the official guidelines
# psm 3: Fully automatic page segmentation, but no OSD (default)
# oem 1: Neural nets LSTM engine only
# tessdata_best should be installed in the system
TESSDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "tessdata"))
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
CUSTOM_CONFIG = r'--oem 1 --psm 3'

def extract_text_from_image(image, lang='eng+spa'):
    """
    Toma una imagen preprocesada (matriz numpy de OpenCV) y devuelve el texto extraído.
    También devuelve los metadatos de confianza (confidence) para evaluación.
    """
    # Convertir la imagen de OpenCV (numpy) a un formato PIL, ya que pytesseract 
    # trabaja muy bien con PIL internamente y evita problemas de color/canales.
    # Como el preprocesamiento ya la dejó en binarizado (escala de grises simple), 
    # se puede pasar directamente o convertir a RGB.
    if len(image.shape) == 2:
        img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        img_rgb = image
        
    pil_img = Image.fromarray(img_rgb)
    
    # Extraer el texto simple
    text = pytesseract.image_to_string(pil_img, lang=lang, config=CUSTOM_CONFIG)
    
    # Extraer datos detallados para el 'Confidence Thresholding' (Human-in-the-loop)
    data = pytesseract.image_to_data(pil_img, lang=lang, config=CUSTOM_CONFIG, output_type=pytesseract.Output.DICT)
    
    # Calcular la confianza media excluyendo espacios vacíos (donde conf es -1)
    confidences = [int(conf) for conf in data['conf'] if int(conf) != -1]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        'text': text.strip(),
        'confidence': avg_confidence,
        'detailed_data': data
    }

import easyocr

# Singleton EasyOCR reader (heavy init, reuse across calls)
_easyocr_reader = None

def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(['es', 'en'], gpu=False)
    return _easyocr_reader

def extract_words_from_image(image, lang='spa', min_conf=30, width_ths=0.0):
    """
    Toma una imagen preprocesada y devuelve una lista de diccionarios con las palabras
    y sus bounding boxes usando EasyOCR (deep learning CRAFT+CRNN).
    Mucho más robusto que Tesseract para documentos con marcas de agua, fondos complejos
    y texto pequeño (INE, actas, pasaportes).

    width_ths controla la fusión horizontal de cajas de EasyOCR:
    - 0.0 (default): no fusiona — bboxes individuales por palabra (ruta de página).
    - 0.5: fusiona cajas cercanas — evita fragmentar tokens largos como CURP o
      la clave de elector en credenciales (ruta de imagen embebida / INE).
    """
    if len(image.shape) == 2:
        img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        img_rgb = image

    reader = _get_easyocr_reader()
    results = reader.readtext(img_rgb, detail=1, paragraph=False, width_ths=width_ths)

    words = []
    for idx, (bbox, text, conf) in enumerate(results):
        text = text.strip()
        conf_scaled = conf * 100.0

        if text and conf_scaled > min_conf:
            # bbox es [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            x0 = int(min(x_coords))
            y0 = int(min(y_coords))
            x1 = int(max(x_coords))
            y1 = int(max(y_coords))
            words.append({
                'text': text,
                'bbox': [x0, y0, x1, y1],
                'conf': conf_scaled,
                'block_no': idx,
                'word_no': 0
            })
    return words

def needs_manual_review(ocr_result, threshold=50):
    """
    Determina si el documento debe enviarse a la cola de revisión manual.
    Basado en la métrica de confianza promedio.
    """
    return ocr_result['confidence'] < threshold

