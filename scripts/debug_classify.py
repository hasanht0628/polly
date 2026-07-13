#!/usr/bin/env python3
"""Isolated single-call test of the archetype classifier (offline, local Ollama).

This is the fast way to debug *accuracy* ("why did it pick the wrong archetype?")
without the full ~11 min agentic loop: it feeds one document's text straight to
classify_document_text and prints the result. Point it at a cached .ocr.txt file
or a PDF (which will be OCR'd, honoring the .ocr.txt cache).

Examples
--------
# Classify a cached OCR sidecar, biasing toward the officer-code candidates:
python -u scripts/debug_classify.py \
    --ocr data/docs_root/ACME/ACME_statement.ocr.txt \
    --candidates auto_deficiency,fintech

# Classify a PDF directly (runs OCR if no sidecar exists):
python -u scripts/debug_classify.py --pdf data/docs_root/ACME/ACME_statement.pdf
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from agents.config import active_model_names
from agents.extract_utils import RunMetrics
from documents.profiles.product_classification import classify_document_text
from documents.text import load_document_text


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--ocr", type=Path, help="Path to a .ocr.txt / plain-text document")
    src.add_argument("--pdf", type=Path, help="Path to a PDF (OCR'd, honoring the .ocr.txt cache)")
    p.add_argument("--client-id", default="portfolio")
    p.add_argument(
        "--candidates",
        default="",
        help="Comma-separated archetype_candidates to bias the classifier, e.g. auto_deficiency,fintech",
    )
    p.add_argument("--officer-code", default="")
    p.add_argument("--plaintiff", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--no-cache", action="store_true", help="Force live OCR for --pdf")
    return p.parse_args()


def _build_extra(args: argparse.Namespace) -> str:
    lines: list[str] = []
    if args.officer_code:
        lines.append(f"officer_code={args.officer_code}")
    if args.candidates:
        cand = [c.strip() for c in args.candidates.split(",") if c.strip()]
        lines.append(f"archetype_candidates={cand}")
    if args.plaintiff:
        lines.append(f"plaintiff={args.plaintiff}")
    if args.notes:
        lines.append(f"notes={args.notes}")
    return "\n".join(lines)


async def main() -> None:
    args = _parse_args()

    if args.ocr is not None:
        if not args.ocr.is_file():
            raise SystemExit(f"OCR file not found: {args.ocr}")
        text = args.ocr.read_text(encoding="utf-8")
        label = args.ocr.name
    else:
        if not args.pdf.is_file():
            raise SystemExit(f"PDF not found: {args.pdf}")
        doc = await load_document_text(args.pdf, use_cache=not args.no_cache)
        text = doc.text
        label = args.pdf.name

    extra = _build_extra(args)
    models = active_model_names()
    print(f"models: chat={models['chat_model']} provider={models['provider']}")
    print(f"=== classifying {label} ({len(text)} chars) client={args.client_id} ===")
    if extra:
        print(f"context:\n{extra}")

    metrics = RunMetrics()
    start = time.perf_counter()
    result = await classify_document_text(
        text, client_id=args.client_id, extra_context=extra, metrics=metrics
    )
    dt = time.perf_counter() - start

    print(f"\n[{dt:.1f}s] product_type = {result.product_type.value}")
    print(f"         confidence   = {result.confidence}  needs_review={result.needs_review}")
    print(f"         alternatives = {[t.value for t in result.alternative_types]}")
    print(f"         evidence     = {result.evidence_quotes}")
    print(f"         tokens in:{metrics.usage.input_tokens} out:{metrics.usage.output_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
