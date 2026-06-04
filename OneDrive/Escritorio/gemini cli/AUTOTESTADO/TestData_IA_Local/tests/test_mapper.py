import pytest
import pymupdf
import sys
import os

# Ensure src is in path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from mapper import map_entities

class DummyResult:
    def __init__(self, entity_type, start, end, score):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score

def test_map_entities_single_word():
    # Texto: "Hola mundo cruel" (0-4, 5-10, 11-16)
    spatial_index = [
        {"word": "Hola", "start_idx": 0, "end_idx": 4, "rect": pymupdf.Rect(0,0,10,10)},
        {"word": "mundo", "start_idx": 5, "end_idx": 10, "rect": pymupdf.Rect(15,0,25,10)},
        {"word": "cruel", "start_idx": 11, "end_idx": 16, "rect": pymupdf.Rect(30,0,40,10)}
    ]
    # Entidad: "mundo"
    results = [DummyResult("TEST", 5, 10, 0.9)]
    
    mapped = map_entities(spatial_index, results)
    
    assert len(mapped) == 1
    assert mapped[0]["entity_type"] == "TEST"
    assert mapped[0]["score"] == 0.9
    assert len(mapped[0]["rects"]) == 1
    assert mapped[0]["rects"][0] == pymupdf.Rect(15,0,25,10)

def test_map_entities_repeated_word():
    # Texto: "Juan y Juan son Juan" (0-4, 5-6, 7-11, 12-15, 16-20)
    spatial_index = [
        {"word": "Juan", "start_idx": 0, "end_idx": 4, "rect": pymupdf.Rect(0,0,10,10)},
        {"word": "y", "start_idx": 5, "end_idx": 6, "rect": pymupdf.Rect(15,0,25,10)},
        {"word": "Juan", "start_idx": 7, "end_idx": 11, "rect": pymupdf.Rect(30,0,40,10)},
        {"word": "son", "start_idx": 12, "end_idx": 15, "rect": pymupdf.Rect(45,0,55,10)},
        {"word": "Juan", "start_idx": 16, "end_idx": 20, "rect": pymupdf.Rect(60,0,70,10)}
    ]
    # Entidad: SEGUNDO "Juan"
    results = [DummyResult("PERSON", 7, 11, 0.85)]
    
    mapped = map_entities(spatial_index, results)
    
    assert len(mapped) == 1
    assert len(mapped[0]["rects"]) == 1
    assert mapped[0]["rects"][0] == pymupdf.Rect(30,0,40,10)

def test_map_entities_multi_word():
    # Texto: "Juan Carlos Lopez" (0-4, 5-11, 12-17)
    spatial_index = [
        {"word": "Juan", "start_idx": 0, "end_idx": 4, "rect": pymupdf.Rect(0,0,10,10)},
        {"word": "Carlos", "start_idx": 5, "end_idx": 11, "rect": pymupdf.Rect(15,0,25,10)},
        {"word": "Lopez", "start_idx": 12, "end_idx": 17, "rect": pymupdf.Rect(30,0,40,10)}
    ]
    # Entidad: "Juan Carlos Lopez"
    results = [DummyResult("PERSON", 0, 17, 0.99)]
    
    mapped = map_entities(spatial_index, results)
    
    assert len(mapped) == 1
    # _consolidar_rects_por_linea fusiona las 3 palabras de la misma línea en 1 rect
    assert len(mapped[0]["rects"]) == 1
    assert mapped[0]["rects"][0] == pymupdf.Rect(0, 0, 40, 10)

def test_map_entities_no_overlap():
    # Texto: "Hola" (0-4)
    spatial_index = [
        {"word": "Hola", "start_idx": 0, "end_idx": 4, "rect": pymupdf.Rect(0,0,10,10)}
    ]
    # Entidad fuera de rango
    results = [DummyResult("TEST", 10, 15, 0.5)]
    
    mapped = map_entities(spatial_index, results)
    
    assert len(mapped) == 0
