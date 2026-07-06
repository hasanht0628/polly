#!/usr/bin/env python3
"""Ingest a client manual PDF into taxonomy + chunk index."""

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

from knowledge.client_manuals.store import ingest_client_manual


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest client manual for classification")
    parser.add_argument("client_id", help="Client identifier")
    parser.add_argument("pdf", type=Path, help="Client manual PDF")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args()

    taxonomy = await ingest_client_manual(
        args.client_id,
        args.pdf,
        use_cache=not args.refresh_ocr,
    )
    indent = 2 if args.pretty else None
    print(taxonomy.model_dump_json(indent=indent))


if __name__ == "__main__":
    asyncio.run(main())
