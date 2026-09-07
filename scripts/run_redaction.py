#!/usr/bin/env python3
"""Run PII redaction workflow → visually redacted PDFs + JSON manifest."""

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

from agents.supervisor import format_redaction_output, run_redaction_workflow


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Redact name/SSN/address from PDF(s) or a folder of PDFs"
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="+",
        help="PDF file(s) and/or folder(s) containing PDFs",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write redacted PDFs here (default: beside each source)",
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, help="Write batch JSON manifest to file")
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args()

    paths = args.path if len(args.path) > 1 else args.path[0]
    batch = await run_redaction_workflow(
        paths,
        use_cache=not args.refresh_ocr,
        out_dir=args.out_dir,
    )
    text = format_redaction_output(batch, pretty=args.pretty)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
