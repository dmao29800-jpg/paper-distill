"""Main pipeline orchestrating PDF extraction, API calls, and output."""

import time
import json
import logging
from pathlib import Path
from datetime import timedelta
from typing import Optional

from .pdf_extractor import extract_pdf_text
from .api_client import DeepSeekClient
from .jsonl_parser import parse_jsonl_response
from .prompt_builder import PromptBuilder
from .checkpoint import Checkpoint

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"input", "output", "doc_id", "type"}

# Sentinel value meaning "auto-detect per paper"
AUTO = "auto"


class Pipeline:
    """Orchestrates the full paper → JSONL pipeline.

    Supports:
    - Fixed discipline: all papers use the same preset
    - Auto-detect (discipline="auto"): classifies each paper individually
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        api_client: DeepSeekClient,
        prompt_builder: PromptBuilder,
        discipline: str = "auto",
        model: str = "deepseek-chat",
        concurrency: int = 1,
        limit: int = 0,
        classifier: Optional[object] = None,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.api_client = api_client
        self.prompt_builder = prompt_builder
        self.discipline = discipline
        self.model = model
        self.concurrency = concurrency
        self.limit = limit
        self.classifier = classifier

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = Checkpoint(self.output_dir / "progress.json")

        # Track per-discipline stats
        self._discipline_counts: dict[str, int] = {}

    def run(self) -> dict:
        """Run the pipeline. Returns summary stats dict."""
        pdf_files = sorted(
            f for f in self.input_dir.iterdir()
            if f.suffix.lower() == ".pdf" and not f.name.startswith("~")
        )

        if not pdf_files:
            logger.error(f"No PDF files found in {self.input_dir}")
            return {"total": 0, "success": 0, "failed": 0, "total_samples": 0}

        # Filter already-done
        pending = [f for f in pdf_files if not self.checkpoint.is_done(f.name)]
        skipped = len(pdf_files) - len(pending)
        if skipped:
            logger.info(f"Skipping {skipped} already-completed papers")

        if self.limit > 0 and len(pending) > self.limit:
            logger.info(f"Limiting to {self.limit}/{len(pending)} pending papers")
            pending = pending[:self.limit]

        if not pending:
            logger.info("All papers already processed!")
            return self.checkpoint.stats

        logger.info(f"Processing {len(pending)} papers "
                    f"(discipline={self.discipline}, model={self.model}, "
                    f"concurrency={self.concurrency})")

        total_start = time.time()

        if self.concurrency == 1:
            for pdf_path in pending:
                self._process_one(pdf_path)
        else:
            self._process_concurrent(pending)

        total_duration = time.time() - total_start
        stats = self.checkpoint.stats
        stats["elapsed"] = str(timedelta(seconds=int(total_duration)))
        return stats

    def _process_one(self, pdf_path: Path):
        """Process a single paper sequentially."""
        result = process_single(
            pdf_path, self.output_dir, self.prompt_builder,
            self.api_client, self.discipline, self.model, self.classifier,
        )
        self._record_result(result)

    def _process_concurrent(self, pending: list[Path]):
        """Process papers with thread pool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(
                    process_single, pdf_path, self.output_dir,
                    self.prompt_builder, self.api_client,
                    self.discipline, self.model, self.classifier,
                ): pdf_path
                for pdf_path in pending
            }
            for future in as_completed(futures):
                result = future.result()
                self._record_result(result)

    def _record_result(self, result: dict):
        """Save checkpoint and track discipline stats.
        Multi-discipline papers count for ALL detected disciplines."""
        self.checkpoint.mark(
            result["filename"], result["status"],
            result["sample_count"], result["duration"], result["error"],
        )
        self.checkpoint.save()

        # Multi-discipline: count ALL detected disciplines
        disc_details = result.get("discipline_details", [])
        if disc_details:
            for key, _, _ in disc_details:
                self._discipline_counts[key] = self._discipline_counts.get(key, 0) + 1
        else:
            disc = result.get("discipline", "unknown")
            self._discipline_counts[disc] = self._discipline_counts.get(disc, 0) + 1


def process_single(
    pdf_path: Path,
    output_dir: Path,
    prompt_builder: PromptBuilder,
    api_client: DeepSeekClient,
    discipline: str,
    model: str,
    classifier: Optional[object] = None,
) -> dict:
    """Process a single paper. Supports auto-discipline detection.

    Args:
        discipline: Preset name, or "auto" to classify from text.
        classifier: Required if discipline="auto".
    """
    filename = pdf_path.name
    # Derive paper title from filename: "title_author.pdf" → "title"
    stem = pdf_path.stem
    parts = stem.rsplit("_", 1)
    paper_title = parts[0] if len(parts) > 1 else stem
    out_path = output_dir / (pdf_path.stem + ".txt")
    start = time.time()

    result = {
        "filename": filename,
        "status": "pending",
        "sample_count": 0,
        "invalid_lines": 0,
        "total_lines": 0,
        "duration": 0,
        "error": "",
        "discipline": discipline,
    }

    log = logger.getChild(filename)

    # Step 1: Extract text
    log.info(f"[{filename}] Extracting PDF text...")
    paper_text = extract_pdf_text(pdf_path)
    if not paper_text:
        result["status"] = "failed"
        result["error"] = "PDF text extraction empty"
        log.error(f"[{filename}] {result['error']}")
        return result

    # Step 1.5: Auto-detect discipline(s) if requested
    actual_discipline = discipline
    disc_details: list[tuple[str, str, float]] = []  # (key, name, score)

    if discipline == AUTO and classifier is not None:
        disc_list = classifier.classify_multi(paper_text)
        disc_details = disc_list
        primary_key, primary_name, primary_score = disc_list[0]
        actual_discipline = primary_key
        result["discipline"] = primary_key
        result["discipline_details"] = disc_list

        # Logging
        if len(disc_list) == 1 and primary_key == "generic":
            log.info(f"[{filename}] Auto-detected: generic (score={primary_score:.0f})")
        elif len(disc_list) == 1:
            log.info(
                f"[{filename}] Auto-detected: {primary_name} "
                f"(key={primary_key}, score={primary_score:.0f})"
            )
        else:
            extras = " + ".join(f"{n}({s:.0f})" for _, n, s in disc_list[1:])
            log.info(
                f"[{filename}] Auto-detected: {primary_name}(主,{primary_score:.0f}) "
                f"+ {extras}"
            )

    elif discipline == AUTO:
        # No classifier available, fall back to generic
        actual_discipline = "generic"
        result["discipline"] = "generic"
        disc_details = [("generic", "学术研究", 0.0)]
        result["discipline_details"] = disc_details
        log.warning(f"[{filename}] No classifier, using 'generic'")

    else:
        # Fixed discipline mode
        actual_discipline = discipline
        result["discipline"] = discipline
        cfg = prompt_builder._config.get(discipline, {})
        disc_name = cfg.get("domain", discipline)
        disc_details = [(discipline, disc_name, 0.0)]
        result["discipline_details"] = disc_details

    # Step 2: Build prompt (pass list for multi-discipline, str otherwise)
    if len(disc_details) > 1:
        prompt_disc = [d[0] for d in disc_details]
    else:
        prompt_disc = actual_discipline

    full_prompt = prompt_builder.build(
        discipline=prompt_disc,
        paper_filename=filename,
        paper_title=paper_title,
        paper_text=paper_text,
    )

    # Step 3: Call API
    disc_label = "+".join(d[0] for d in disc_details) if disc_details else actual_discipline
    log.info(f"[{filename}] Calling {model} (discipline={disc_label})...")
    response = api_client.chat(full_prompt, model=model)
    if response is None:
        result["status"] = "failed"
        result["error"] = "API call failed"
        log.error(f"[{filename}] {result['error']}")
        return result

    # Step 4: Parse JSONL
    valid, invalid, total = parse_jsonl_response(response)
    result["sample_count"] = len(valid)
    result["invalid_lines"] = invalid
    result["total_lines"] = total

    if not valid:
        result["status"] = "failed"
        result["error"] = f"No valid samples (total: {total}, invalid: {invalid})"
        log.error(f"[{filename}] {result['error']}")
        debug = output_dir / f"{pdf_path.stem}_debug_raw.txt"
        debug.write_text(response, encoding="utf-8")
        log.info(f"  Raw response saved: {debug.name}")
        return result

    # Step 5: Save with discipline header
    disc_details_final = result.get("discipline_details", [])
    if disc_details_final:
        if len(disc_details_final) == 1 and disc_details_final[0][0] == "generic":
            header = "# 学科归属：学术研究"
        else:
            parts = [f"{disc_details_final[0][1]}（主）"]
            for _, name, _ in disc_details_final[1:]:
                parts.append(name)
            header = "# 学科归属：" + "、".join(parts)
    else:
        header = "# 学科归属：学术研究"

    jsonl_body = "\n".join(json.dumps(s, ensure_ascii=False) for s in valid)
    out_path.write_text(header + "\n" + jsonl_body, encoding="utf-8")
    duration = time.time() - start
    result["duration"] = round(duration, 1)
    result["status"] = "success"

    log.info(
        f"[{filename}] Done! {len(valid)} samples, "
        f"{invalid} invalid, {duration:.1f}s"
    )
    return result
