"""JSONL response parser with validation."""

import json
import re
import logging

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"input", "output", "doc_id", "type"}


def parse_jsonl_response(text: str) -> tuple[list[dict], int, int]:
    """
    Parse AI response text into validated JSONL samples.
    Handles markdown code block wrapping automatically.
    Returns (valid_samples, invalid_count, total_lines).
    """
    if not text or not text.strip():
        return [], 0, 0

    cleaned = text.strip()

    # Strip markdown code block if present
    m = re.match(r"```(?:jsonl?|jsonl)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()

    valid = []
    invalid = 0
    total = 0

    for line in cleaned.split("\n"):
        line = line.strip()
        if not line:
            continue
        total += 1

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            logger.debug(f"  JSON parse fail: {line[:80]}...")
            continue

        missing = REQUIRED_FIELDS - set(obj.keys())
        if missing:
            invalid += 1
            logger.debug(f"  Missing fields {missing}: {str(obj)[:80]}...")
            continue

        if not all(obj.get(f) for f in REQUIRED_FIELDS):
            invalid += 1
            logger.debug(f"  Empty field: {str(obj)[:80]}...")
            continue

        valid.append(obj)

    return valid, invalid, total
