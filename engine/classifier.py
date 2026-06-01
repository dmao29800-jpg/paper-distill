"""
Auto-classifier: detect paper discipline from text content using keyword scoring.

Scoring: high-weight keyword match = +3 pts, medium-weight = +1 pt.
Returns the discipline with the highest score above a confidence threshold.
Falls back to 'generic' if no discipline scores above threshold.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum score to accept a discipline match
CONFIDENCE_THRESHOLD = 5
# How many chars from the paper to scan (head of paper: abstract + intro)
SCAN_CHARS = 30_000


class DisciplineClassifier:
    """Classify papers into disciplines using keyword matching."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: Path to disciplines.yaml.
                         If None, uses bundled config.
        """
        self._disciplines: dict[str, dict] = {}
        if config_path and config_path.exists():
            self._load_config(config_path)

    @property
    def names(self) -> list[str]:
        """List known discipline names (excluding generic)."""
        return [k for k in self._disciplines.keys() if k != "generic"]

    def _load_config(self, config_path: Path):
        """Load discipline keyword lists from YAML config."""
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw = data.get("disciplines", {})
        for name, cfg in raw.items():
            kw = cfg.get("keywords", {})
            self._disciplines[name] = {
                "domain": cfg.get("domain", name),
                "high": [k.lower() for k in kw.get("high", [])],
                "medium": [k.lower() for k in kw.get("medium", [])],
            }

        logger.info(f"Classifier loaded: {len(self._disciplines)} disciplines")

    def classify(self, text: str) -> tuple[str, str, float]:
        """
        Classify paper text into a discipline.

        Args:
            text: Paper full text (only first SCAN_CHARS are scanned).

        Returns:
            (discipline_key, domain_name, confidence_score)
            e.g. ("civil_engineering", "土木工程", 18.0)
        """
        if not self._disciplines:
            return ("generic", "学术研究", 0.0)

        scan = text[:SCAN_CHARS].lower()
        scores: dict[str, float] = {}

        for name, disc in self._disciplines.items():
            if name == "generic":
                continue
            score = 0.0
            for kw in disc["high"]:
                if kw in scan:
                    score += 3.0
            for kw in disc["medium"]:
                if kw in scan:
                    score += 1.0
            scores[name] = score

        if not scores:
            return ("generic", "学术研究", 0.0)

        best = max(scores, key=scores.get)
        best_score = scores[best]

        if best_score < CONFIDENCE_THRESHOLD:
            logger.info(
                f"Classify: best='{best}' score={best_score:.0f} < threshold={CONFIDENCE_THRESHOLD}, "
                f"falling back to 'generic'"
            )
            return ("generic", "学术研究", best_score)

        domain = self._disciplines[best]["domain"]
        logger.info(
            f"Classify: → '{best}' ({domain}) score={best_score:.0f}"
        )
        return (best, domain, best_score)

    def classify_from_pdf(self, pdf_path: Path) -> tuple[str, str, float]:
        """
        Classify a PDF file by extracting text first, then scoring keywords.

        Returns:
            (discipline_key, domain_name, confidence_score)
        """
        from .pdf_extractor import extract_pdf_text

        text = extract_pdf_text(pdf_path, max_chars=SCAN_CHARS)
        if not text:
            logger.warning(f"Classify: empty text for {pdf_path.name}, using generic")
            return ("generic", "学术研究", 0.0)

        return self.classify(text)

    def top_candidates(self, text: str, n: int = 5) -> list[tuple[str, str, float]]:
        """Return top-N discipline candidates with scores."""
        scan = text[:SCAN_CHARS].lower()
        entries = []

        for name, disc in self._disciplines.items():
            if name == "generic":
                continue
            score = 0.0
            for kw in disc["high"]:
                if kw in scan:
                    score += 3.0
            for kw in disc["medium"]:
                if kw in scan:
                    score += 1.0
            entries.append((name, disc["domain"], score))

        entries.sort(key=lambda x: x[2], reverse=True)
        return entries[:n]
