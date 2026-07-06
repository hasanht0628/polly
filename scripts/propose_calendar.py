#!/usr/bin/env python3
"""Map court extraction goldens to schedulable calendar output (no LLM)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from court.schemas import CaseExtraction
from documents.profiles.registry import extract_document
from workflows.court_calendar.map_extraction import map_extraction_to_review_package
from workflows.court_calendar.run import format_scheduling_output


async def main() -> None:
    parser = argparse.ArgumentParser(description="Propose schedulable calendar events from a court PDF")
    parser.add_argument("pdf", type=Path, help="Court PDF path")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--from-golden",
        type=Path,
        help="Use extract golden JSON instead of live extract",
    )
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"File not found: {pdf_path}")

    if args.from_golden:
        extraction = CaseExtraction.model_validate_json(
            args.from_golden.read_text(encoding="utf-8")
        )
    else:
        result = await extract_document(
            pdf_path,
            profile="court_calendar",
            use_cache=not args.refresh_ocr,
        )
        extraction = result.data

    package = map_extraction_to_review_package(extraction, pdf_path=pdf_path)
    print(format_scheduling_output(package, pretty=args.pretty))


if __name__ == "__main__":
    asyncio.run(main())
