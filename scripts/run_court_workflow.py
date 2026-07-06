#!/usr/bin/env python3
"""Run court doc → scheduling output workflow."""

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

from agents.supervisor import format_scheduling_output, run_court_workflow


async def main() -> None:
    parser = argparse.ArgumentParser(description="Court doc → ReviewPackage JSON")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pdf", type=Path, help="Path to court PDF")
    group.add_argument("--email", type=Path, help="Path to .eml file")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, help="Write JSON to file")
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args()

    package = await run_court_workflow(
        pdf_path=args.pdf,
        email_path=args.email,
        use_cache=not args.refresh_ocr,
    )
    text = format_scheduling_output(package, pretty=args.pretty)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
