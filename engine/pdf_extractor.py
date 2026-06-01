"""PDF text extraction using pypdf."""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_PAPER_CHARS = 120_000
HEAD_CHARS = 80_000
TAIL_CHARS = 30_000


def extract_pdf_text(filepath: Path, max_chars: int = MAX_PAPER_CHARS) -> str:
    """
    Extract text from a PDF file.
    If text exceeds max_chars, truncate keeping head + tail.
    Returns empty string on failure.
    """
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(filepath))
        pages = []

        for page in reader.pages:
            text = page.extract_text()
            if text:
                text = re.sub(r"[ \t]{3,}", "  ", text)
                text = re.sub(r"\n{4,}", "\n\n\n", text)
                pages.append(text)

        full_text = "\n".join(pages)

        if not full_text.strip():
            logger.warning(f"PDF text extraction empty: {filepath.name}")
            return ""

        if len(full_text) > max_chars:
            logger.info(
                f"Paper text {len(full_text):,} chars exceeds {max_chars:,}, "
                f"truncating to head {HEAD_CHARS:,} + tail {TAIL_CHARS:,}"
            )
            full_text = (
                full_text[:HEAD_CHARS]
                + "\n\n... [truncated] ...\n\n"
                + full_text[-TAIL_CHARS:]
            )

        logger.debug(f"Extracted text: {len(full_text):,} chars from {filepath.name}")
        return full_text

    except Exception as e:
        logger.error(f"PDF parse failed: {filepath.name} — {e}")
        return ""
