#!/usr/bin/env python3
"""Run portfolio classification over a .dat file (+ optional docs root)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from classification.client_codes import DEFAULT_CODES_PATH
from workflows.portfolio_classification.run import (
    format_portfolio_output,
    run_portfolio_classification,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", type=Path, required=True, help="Path to portfolio .dat file")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Root directory containing PLMTDOCS_*/account folders",
    )
    parser.add_argument(
        "--codes",
        type=Path,
        default=DEFAULT_CODES_PATH,
        help="YAML client-code mapping table",
    )
    parser.add_argument("--client-id", default="portfolio")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    batch = asyncio.run(
        run_portfolio_classification(
            args.dat,
            docs_root=args.docs_root,
            codes_path=args.codes,
            client_id=args.client_id,
            use_cache=not args.no_cache,
        )
    )
    print(format_portfolio_output(batch, pretty=args.pretty))


if __name__ == "__main__":
    main()
