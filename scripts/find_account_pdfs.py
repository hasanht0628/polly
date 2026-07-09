#!/usr/bin/env python3
"""Find account PDF folders for a case id under a docs root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portfolio.pdf_locator import find_account_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs_root", type=Path)
    parser.add_argument("case_id")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = find_account_pdfs(args.docs_root, args.case_id)
    payload = result.model_dump(mode="json")
    print(json.dumps(payload, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
