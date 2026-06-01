#!/usr/bin/env python3
"""
Paper Distill CLI — Multi-discipline paper SFT data generation tool.
Default mode: auto-detect each paper's discipline.

Usage:
    paper-distill -i ./papers -o ./out                     # auto-detect
    paper-distill -i ./papers -o ./out -d civil_engineering # fixed discipline
    paper-distill -i ./papers -o ./out -c 3 -n 100          # concurrent + limit
    paper-distill --list-disciplines                        # list presets
    paper-distill -i ./papers --dry-run --classify           # preview classification
"""

import os
import sys
import argparse
import logging
import textwrap
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from engine.api_client import DeepSeekClient, DEFAULT_MODEL
from engine.prompt_builder import PromptBuilder
from engine.classifier import DisciplineClassifier
from engine.pipeline import Pipeline, AUTO


def setup_logging(output_dir: Path) -> logging.Logger:
    """Setup dual console + file logging with UTF-8 support."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    output_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    log_file = output_dir / f"process_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger = logging.getLogger("paper_distill")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Log file: {log_file}")
    return logger


def print_stats(stats: dict, api_client: DeepSeekClient,
                pipeline: Pipeline, logger: logging.Logger):
    """Print final processing statistics."""
    elapsed = stats.get("elapsed", "N/A")
    total = stats["total"]
    success = stats["success"]
    failed = stats["failed"]
    samples = stats["total_samples"]
    duration = stats.get("total_duration", 0)

    logger.info(f"\n{'='*60}")
    logger.info(f"📊 Processing Complete!")
    logger.info(f"{'='*60}")
    logger.info(f"  Total: {total} | Success: {success} | Failed: {failed}")
    logger.info(f"  Total samples: {samples}")
    logger.info(f"  Total time: {elapsed}")
    if duration > 0 and success > 0:
        logger.info(f"  Avg per paper: {duration / success:.1f}s")
    logger.info(f"  Est. API cost: ¥{api_client.total_cost:.4f}")

    # Discipline distribution (when using auto-detect)
    disc_counts = pipeline._discipline_counts
    if disc_counts:
        logger.info(f"\n  📚 Discipline Distribution:")
        for disc, count in sorted(disc_counts.items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 30)
            logger.info(f"     {disc:25s} {count:3d}  {bar}")

    # Failures
    failures = pipeline.checkpoint.failed_files()
    if failures:
        logger.info(f"\n  ❌ Failed ({len(failures)}):")
        for name, err in failures:
            logger.info(f"     - {name}: {err}")


def main():
    parser = argparse.ArgumentParser(
        prog="paper-distill",
        description="Multi-discipline paper SFT training data generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              paper-distill -i ./papers -o ./out                       # auto-detect (default)
              paper-distill -i ./papers -o ./out -d civil_engineering   # fixed discipline
              paper-distill -i ./papers -o ./out -c 5 -n 100            # concurrent + limit
              paper-distill -i ./papers --dry-run --classify             # preview classification
              paper-distill --list-disciplines                          # list all presets
        """),
    )
    parser.add_argument("-i", "--input", help="PDF input directory")
    parser.add_argument("-o", "--output", help="Output directory")
    parser.add_argument(
        "-d", "--discipline", default="auto",
        help="Discipline preset. Use 'auto' for per-paper detection (default), "
             "or specify a preset name (e.g. civil_engineering, materials_science)")
    parser.add_argument(
        "-c", "--concurrency", type=int, default=1,
        help="Concurrent workers (default: 1, recommended: 3-5)")
    parser.add_argument(
        "-n", "--limit", type=int, default=0,
        help="Max papers to process (0=all)")
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--api-key", default=None,
        help="DeepSeek API key (or set DEEPSEEK_API_KEY env var)")
    parser.add_argument(
        "--config", default=None,
        help="Path to custom disciplines.yaml")
    parser.add_argument(
        "--list-disciplines", action="store_true",
        help="List all available discipline presets and exit")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List PDFs without processing")
    parser.add_argument(
        "--classify", action="store_true",
        help="Show auto-detected discipline for each paper (use with --dry-run)")
    args = parser.parse_args()

    # --- Config path resolution ---
    config_path = None
    if args.config:
        config_path = Path(args.config)
    else:
        default_config = _SCRIPT_DIR / "configs" / "disciplines.yaml"
        if default_config.exists():
            config_path = default_config

    # --- Prompt builder ---
    builder = PromptBuilder(config_path)

    # --- Classifier (for auto mode) ---
    classifier = None
    if args.discipline == "auto":
        classifier = DisciplineClassifier(config_path)
        if not classifier.names:
            logger = logging.getLogger("paper_distill")
            logger.warning("No disciplines loaded for auto-detection, falling back to 'generic'")

    # --- List disciplines ---
    if args.list_disciplines:
        print(f"\n{'='*50}")
        print(f"Available Discipline Presets ({len(classifier.names) if classifier else len(builder.disciplines)} total)")
        print(f"{'='*50}")
        names = classifier.names if classifier else builder.disciplines
        for name in sorted(names):
            print(f"  - {name}")
        print(f"\nDefault mode: auto-detect (no need to specify -d)")
        print(f"Manual mode:  paper-distill -i ./pdfs -o ./out -d <preset>")
        return

    # --- Validate args ---
    if not args.input or not args.output:
        parser.error("--input and --output are required (unless --list-disciplines)")

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.exists():
        sys.exit(f"Input directory not found: {input_dir}")

    # --- Logging ---
    logger = setup_logging(output_dir)
    logger.info(f"Input:  {input_dir}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Discipline: {args.discipline}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Concurrency: {args.concurrency}")

    # --- Dry run (optionally with classification preview) ---
    pdfs = sorted(f for f in input_dir.iterdir()
                  if f.suffix.lower() == ".pdf" and not f.name.startswith("~"))

    if args.classify and classifier and pdfs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Classifying {min(len(pdfs), args.limit or len(pdfs))} papers...")
        logger.info(f"{'='*60}")
        limit = args.limit if args.limit > 0 else len(pdfs)
        for pdf_path in pdfs[:limit]:
            disc_list = classifier.classify_multi_from_pdf(pdf_path)
            if len(disc_list) == 1:
                key, name, score = disc_list[0]
                bar = "█" * min(int(score), 40)
                logger.info(
                    f"  {pdf_path.name:40s} → {name:20s} "
                    f"(score: {score:4.0f}) {bar}"
                )
            else:
                primary = disc_list[0]
                extras = " + ".join(f"{n}({s:.0f})" for _, n, s in disc_list[1:])
                bar = "█" * min(int(primary[2]), 40)
                logger.info(
                    f"  {pdf_path.name:40s} → {primary[1]}(主,{primary[2]:.0f}) "
                    f"+ {extras} {bar}"
                )
        return

    if args.dry_run:
        logger.info(f"\nFound {len(pdfs)} PDFs:")
        for i, f in enumerate(pdfs, 1):
            logger.info(f"  {i:3d}. {f.name}")
        return

    # --- API client ---
    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("Set DEEPSEEK_API_KEY environment variable or use --api-key")
    api_client = DeepSeekClient(api_key)

    # --- Pipeline ---
    pipeline = Pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        api_client=api_client,
        prompt_builder=builder,
        discipline=args.discipline,
        model=args.model,
        concurrency=args.concurrency,
        limit=args.limit,
        classifier=classifier,
    )

    try:
        stats = pipeline.run()
        print_stats(stats, api_client, pipeline, logger)
    except KeyboardInterrupt:
        logger.info("\n⏸️  Interrupted. Progress saved — resume with same command.")
        sys.exit(130)


if __name__ == "__main__":
    main()
