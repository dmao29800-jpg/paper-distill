# engine/__init__.py
"""Paper Distill — Multi-discipline academic paper SFT data generation engine."""

__version__ = "2.0.0"

from .pdf_extractor import extract_pdf_text
from .api_client import DeepSeekClient
from .jsonl_parser import parse_jsonl_response
from .prompt_builder import PromptBuilder
from .checkpoint import Checkpoint
from .classifier import DisciplineClassifier
from .pipeline import Pipeline

__all__ = [
    "extract_pdf_text",
    "DeepSeekClient",
    "parse_jsonl_response",
    "PromptBuilder",
    "Checkpoint",
    "DisciplineClassifier",
    "Pipeline",
]
