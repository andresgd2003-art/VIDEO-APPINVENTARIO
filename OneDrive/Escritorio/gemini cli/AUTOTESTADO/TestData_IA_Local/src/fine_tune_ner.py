import spacy
from spacy.training.example import Example
import random
import os
import sys

def build_training_data():
    raw_data = [
        # Formato de nombre suelto (CV/CURP)
        ("ANDRES GALLEGOS DIAZ", "ANDRES GALLEGOS DIAZ", "PERSON"),
        ("ANDRÉS GALLEGOS DÍAZ Ingeniero Mecatrónico", "ANDRÉS GALLEGOS DÍAZ", "PERSON"),
        ("JUAN CARLOS PEREZ GOMEZ", "JUAN CARLOS PEREZ GOMEZ", "PERSON"),
        
        # Bloques masivos de la CURP extraídos directamente de PyMuPDF
        ("Clave: GADA030721HDGLZNA8 Nombre ANDRES GALLEGOS DIAZ Entidad de registro: DURANGO", "ANDRES GALLEGOS DIAZ", "PERSON"),
        ("110005200301774 ANDRES GALLEGOS DIAZ PRESENTE Ciudad de México", "ANDRES GALLEGOS DIAZ", "PERSON"),
        
        # Ocurrencias con arrastre que debemos cortar
        ("ANDRES GALLEGOS DIAZ PRESENTE Ciudad de México", "ANDRES GALLEGOS DIAZ", "PERSON"),
        ("ANDRES GALLEGOS DIAZ Entidad de registro", "ANDRES GALLEGOS DIAZ", "PERSON"),
        ("Nombre ANDRES GALLEGOS DIAZ", "ANDRES GALLEGOS DIAZ", "PERSON"),
        ("DIAZ Entidad de registro:", "DIAZ", "PERSON"),
        ("DIAZ PRESENTE", "DIAZ", "PERSON"),
        
        # Falsos positivos a anular completamente (O - Outside)
        ("PRESENTE", None, None),
        ("Entidad de registro:", None, None),
        ("Ciudad de México, a 21 de mayo de 2025", None, None),
        ("Clave:", None, None),
        ("Clave: GADA030721HDGLZNA8", None, None),
        ("Nombre", None, None),
        ("Entidad", None, None),
        ("registro:", None, None),
        ("de", None, None),
        ("la", None, None),
        ("el", None, None),
        ("en", None, None),
        
        # Reconocer localidades
        ("Entidad de registro: DURANGO", "DURANGO", "LOC"),
        ("DURANGO", "DURANGO", "LOC"),
        
        # Falsos positivos del CV que debemos anular
        ("Claude Code", None, None),
        ("Claude Sonnet", None, None),
        ("May 2026", None, None),
        ("Técnico", None, None),
        ("Lógica de programación", None, None),
        
        # Falsos positivos de la CURP y excepciones legales
        ("CURP Certificada", None, None),
        ("Registro Civil", None, None),
        ("El derecho a la identidad está consagrado en nuestra Constitución.", None, None),
        ("Secretaría de Gobernación", None, None),
        ("ROSA ICELA RODRÍGUEZ VELÁZQUEZ", None, None), # Excepción servidor público
    ]
    
    train_data = []
    for text, entity_text, label in raw_data:
        if entity_text is None:
            train_data.append((text, {"entities": []}))
        else:
            # Encontrar la ocurrencia (asumimos 1 por frase en estos ejemplos aislados)
            start = text.find(entity_text)
            if start != -1:
                end = start + len(entity_text)
                train_data.append((text, {"entities": [(start, end, label)]}))
            
    return train_data

def fine_tune():
    print("Iniciando script de Fine-Tuning de Redes Neuronales...")
    print("Cargando pesos base del modelo es_core_news_md...")
    try:
        nlp = spacy.load("es_core_news_md")
    except OSError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "es_core_news_md"])
        nlp = spacy.load("es_core_news_md")

    ner = nlp.get_pipe("ner")
    
    train_data = build_training_data()
    
    examples = []
    for text, annotations in train_data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)
        examples.append(example)
        
    print("Congelando capas convolucionales base...")
    pipe_exceptions = ["ner"]
    unaffected_pipes = [pipe for pipe in nlp.pipe_names if pipe not in pipe_exceptions]
    
    print("Entrenando capa NER (Backpropagation) - 60 Epochs...")
    with nlp.disable_pipes(*unaffected_pipes):
        optimizer = nlp.resume_training()
        for epoch in range(60):
            random.shuffle(examples)
            losses = {}
            # Reducimos el dropout para que memorice mejor estos edge cases
            nlp.update(examples, sgd=optimizer, drop=0.2, losses=losses)
            if (epoch+1) % 10 == 0:
                print(f"Epoch {epoch+1} Loss: {losses['ner']:.4f}")
                
    # Guardar modelo en carpeta local
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../models/es_core_news_custom"))
    os.makedirs(output_dir, exist_ok=True)
    nlp.to_disk(output_dir)
    print(f"\nModelo reentrenado exitosamente. Guardado en:\n{output_dir}")

if __name__ == "__main__":
    fine_tune()
