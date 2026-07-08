#!/usr/bin/env python3
"""Offline eval: map extract goldens to ReviewPackage scheduling output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from court.schemas import CaseExtraction
from evals.court.cases import EVAL_CASES
from evals.runner_utils import add_snapshot_args
from evals.snapshots import SnapshotWriter
from workflows.court_calendar.map_extraction import map_extraction_to_review_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Run proposal eval on extract goldens")
    add_snapshot_args(parser)
    args = parser.parse_args()

    failures: list[str] = []
    writer: SnapshotWriter | None = None
    if args.snapshot:
        writer = SnapshotWriter.create("proposal", label=args.snapshot_label)

    for case in EVAL_CASES:
        if not case.extract_golden_path.is_file():
            failures.append(f"{case.slug}: missing golden")
            continue
        extraction = CaseExtraction.model_validate_json(
            case.extract_golden_path.read_text(encoding="utf-8")
        )
        package = map_extraction_to_review_package(
            extraction,
            pdf_path=case.pdf_path,
        )
        passed = True
        if not package.case_number and extraction.case_number:
            failures.append(f"{case.slug}: case_number not mapped")
            passed = False
        if extraction.events and not package.schedulable_events and not package.flagged_items:
            failures.append(f"{case.slug}: no schedulable or flagged output")
            passed = False

        if writer:
            writer.write_json(case.slug, "review_package.json", package)
            writer.write_json(
                case.slug,
                "meta.json",
                {
                    "source_golden": str(case.extract_golden_path.relative_to(PROJECT_ROOT)),
                    "schedulable_count": len(package.schedulable_events),
                    "flagged_count": len(package.flagged_items),
                },
            )
            writer.record_case(
                case.slug,
                passed=passed,
                files=["review_package.json", "meta.json"],
            )

        print(
            f"{case.slug}: {len(package.schedulable_events)} schedulable, "
            f"{len(package.flagged_items)} flagged"
        )

    if writer:
        run_dir = writer.finalize()
        print(f"\nSnapshot: {run_dir}")

    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(f"  - {item}")
        sys.exit(1)
    print("\nAll proposal eval checks passed.")


if __name__ == "__main__":
    main()
