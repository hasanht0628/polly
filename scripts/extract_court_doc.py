#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from court.extract import extract_from_pdf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract structured case data from a court PDF via olmocr2 + LLM."
    )
    parser.add_argument("pdf", type=Path, help="Path to the court PDF")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "--refresh-ocr",
        action="store_true",
        help="Re-run olmocr2 OCR even if a cached .ocr.txt file exists",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"File not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    try:
        extraction = asyncio.run(
            extract_from_pdf(args.pdf, use_cache=not args.refresh_ocr)
        )
    except Exception as exc:
        print(f"Extraction failed: {exc}", file=sys.stderr)
        sys.exit(1)

    indent = 2 if args.pretty else None
    print(extraction.model_dump_json(indent=indent))


if __name__ == "__main__":
    main()
