#!/usr/bin/env python3
"""Run consumer PDF → account classification workflow."""

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

from agents.supervisor import format_classification_output, run_account_classification_workflow


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consumer PDF → AccountClassificationPackage JSON"
    )
    parser.add_argument("client_id", help="Client whose manual/taxonomy to use")
    parser.add_argument("pdf", type=Path, help="Consumer document PDF")
    parser.add_argument("--consumer-id", help="Optional consumer identifier for traceability")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, help="Write JSON to file")
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args()

    package = await run_account_classification_workflow(
        args.client_id,
        args.pdf,
        consumer_id=args.consumer_id,
        use_cache=not args.refresh_ocr,
    )
    text = format_classification_output(package, pretty=args.pretty)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
