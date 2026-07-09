#!/usr/bin/env python3
"""Inspect a .dat file: record types, officer-code lengths, sample slices."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portfolio.dat_parser import (
    CASE_ID_SLICE,
    MISC_CODE_SLICE,
    OFFICER_CODE_SLICE,
    RECORD_TYPE_SLICE,
    parse_dat_file,
    parse_dat_line,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dat_path", type=Path)
    parser.add_argument("--limit", type=int, default=20, help="Sample lines to print")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    text = args.dat_path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    record_types = Counter()
    officer_lengths = Counter()
    samples = []

    for i, line in enumerate(lines):
        record_type, case_id, officer = parse_dat_line(line)
        record_types[record_type or "?"] += 1
        if officer:
            officer_lengths[len(officer)] += 1
        if i < args.limit:
            samples.append(
                {
                    "line_no": i + 1,
                    "record_type": record_type,
                    "case_id": case_id,
                    "officer_code": officer,
                    "misc_code": line[MISC_CODE_SLICE].strip() if len(line) > MISC_CODE_SLICE.start else "",
                    "officer_raw": repr(line[OFFICER_CODE_SLICE]) if len(line) > OFFICER_CODE_SLICE.start else "",
                    "prefix": repr(line[:70]),
                }
            )

    cases = parse_dat_file(args.dat_path)
    payload = {
        "path": str(args.dat_path),
        "line_count": len(lines),
        "case_count": len(cases),
        "record_types": dict(record_types),
        "officer_code_lengths": {str(k): v for k, v in sorted(officer_lengths.items())},
        "slices": {
            "record_type": [RECORD_TYPE_SLICE.start, RECORD_TYPE_SLICE.stop],
            "case_id": [CASE_ID_SLICE.start, CASE_ID_SLICE.stop],
            "officer_code": [OFFICER_CODE_SLICE.start, OFFICER_CODE_SLICE.stop],
            "misc_code": [MISC_CODE_SLICE.start, MISC_CODE_SLICE.stop],
        },
        "sample_cases": [
            {
                "case_id": c.case_id,
                "officer_code": c.officer_code,
                "misc_code": c.misc_code,
                "plaintiff": c.plaintiff,
                "debt_amount": c.debt_amount,
                "notes": c.notes,
                "record_types": c.record_types,
            }
            for c in cases[:10]
        ],
        "sample_lines": samples,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(f"path: {payload['path']}")
    print(f"lines: {payload['line_count']}  cases: {payload['case_count']}")
    print(f"record_types: {payload['record_types']}")
    print(f"officer_code_lengths: {payload['officer_code_lengths']}")
    print(f"slices: {payload['slices']}")
    print("\nSample cases:")
    for case in payload["sample_cases"]:
        print(
            f"  {case['case_id']} officer={case['officer_code']!r} "
            f"misc={case['misc_code']!r} records={case['record_types']}"
        )


if __name__ == "__main__":
    main()
