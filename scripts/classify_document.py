#!/usr/bin/env python3
"""Classify a consumer document using client manual knowledge."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from documents.profiles.registry import extract_document
from documents.text import load_document_text
from knowledge.client_manuals.store import load_taxonomy, retrieve_manual_passages


async def main() -> None:
    parser = argparse.ArgumentParser(description="Classify consumer document by product type")
    parser.add_argument("client_id", help="Client whose manual to use")
    parser.add_argument("pdf", type=Path, help="Consumer document PDF")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args()

    taxonomy = load_taxonomy(args.client_id)
    document = await load_document_text(args.pdf, use_cache=not args.refresh_ocr)
    passages = retrieve_manual_passages(args.client_id, document.text[:4000])

    result = await extract_document(
        args.pdf,
        profile="product_classification",
        use_cache=not args.refresh_ocr,
        context={
            "client_id": args.client_id,
            "taxonomy": taxonomy,
            "manual_passages": passages,
        },
    )
    indent = 2 if args.pretty else None
    print(result.data.model_dump_json(indent=indent))


if __name__ == "__main__":
    asyncio.run(main())
