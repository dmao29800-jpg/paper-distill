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

    def _score_text(self, text: str) -> dict[str, float]:
        """Score all non-generic disciplines against text. Returns {key: score}."""
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
        return scores

    def classify(self, text: str) -> tuple[str, str, float]:
        """
        Classify paper text into a single discipline.

        Args:
            text: Paper full text (only first SCAN_CHARS are scanned).

        Returns:
            (discipline_key, domain_name, confidence_score)
            e.g. ("civil_engineering", "土木工程", 18.0)
        """
        if not self._disciplines:
            return ("generic", "学术研究", 0.0)

        scores = self._score_text(text)
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

    def classify_multi(self, text: str) -> list[tuple[str, str, float]]:
        """
        Classify paper text into 1-3 disciplines for multi-label output.

        Algorithm:
          1. Score all disciplines via keyword matching.
          2. Sort by score descending.
          3. Always keep the top-scoring discipline.
          4. Additionally keep any discipline whose score >= CONFIDENCE_THRESHOLD
             AND score >= 50% of the top score. Cap at 3 total.
          5. If top score < CONFIDENCE_THRESHOLD, fall back to generic.

        Returns:
            List of (discipline_key, domain_name, confidence_score).
            First element is always primary. Sorted by score descending.
            Falls back to [("generic", "学术研究", 0.0)] if no match.
        """
        if not self._disciplines:
            return [("generic", "学术研究", 0.0)]

        scores = self._score_text(text)
        if not scores:
            return [("generic", "学术研究", 0.0)]

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_key, top_score = ranked[0]

        # Fallback if top is below threshold
        if top_score < CONFIDENCE_THRESHOLD:
            logger.info(
                f"ClassifyMulti: best='{top_key}' score={top_score:.0f} "
                f"< threshold={CONFIDENCE_THRESHOLD}, falling back to 'generic'"
            )
            return [("generic", "学术研究", 0.0)]

        # Always include the top discipline
        result = [(top_key, self._disciplines[top_key]["domain"], top_score)]

        # Include secondary disciplines: score >= threshold AND >= 50% of top
        min_score = top_score * 0.5
        for key, score in ranked[1:]:
            if len(result) >= 3:
                break
            if score >= CONFIDENCE_THRESHOLD and score >= min_score:
                result.append((key, self._disciplines[key]["domain"], score))

        if len(result) == 1:
            logger.info(
                f"ClassifyMulti: → '{top_key}' "
                f"({self._disciplines[top_key]['domain']}) score={top_score:.0f}"
            )
        else:
            extras = ", ".join(f"{k}({s:.0f})" for k, _, s in result[1:])
            logger.info(
                f"ClassifyMulti: → '{top_key}'({top_score:.0f}) + {extras}"
            )

        return result

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
        scores = self._score_text(text)
        entries = [
            (name, self._disciplines[name]["domain"], score)
            for name, score in scores.items()
        ]
        entries.sort(key=lambda x: x[2], reverse=True)
        return entries[:n]

    def classify_multi_from_pdf(self, pdf_path: Path) -> list[tuple[str, str, float]]:
        """
        Classify a PDF file into 1-3 disciplines.

        Returns:
            List of (discipline_key, domain_name, confidence_score).
        """
        from .pdf_extractor import extract_pdf_text

        text = extract_pdf_text(pdf_path, max_chars=SCAN_CHARS)
        if not text:
            logger.warning(f"ClassifyMulti: empty text for {pdf_path.name}, using generic")
            return [("generic", "学术研究", 0.0)]

        return self.classify_multi(text)
