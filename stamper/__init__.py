"""
AETHER Stamper Agent Pipeline
Extracts normative assertions from source documents and produces verified capsules.
"""

from .dsl_parser import parse_dsl, is_dsl_document, classify_sentence
from .nas import build_nas_document, validate_nas_document, split_sentences
from .classifier import Classifier
from .pipeline import UniversalExtractor
from .kg_projection import nas_to_kg, verify_antipatterns
from .agent_stamper import AgentStamper

__version__ = "1.0.0"
__all__ = [
    "parse_dsl",
    "is_dsl_document",
    "classify_sentence",
    "build_nas_document",
    "validate_nas_document",
    "split_sentences",
    "Classifier",
    "UniversalExtractor",
    "nas_to_kg",
    "verify_antipatterns",
    "AgentStamper",
]
