#!/usr/bin/env python3
"""Run extract evals using golden OCR text (no live OCR)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from pydantic import BaseModel
from pydantic_evals import Case, Dataset

from court.extract import extract_from_ocr_file
from court.schemas import CaseExtraction
from evals.court.cases import EVAL_CASES
from evals.evaluators import ExtractChecksPass
from evals.runner_utils import _report_failed, add_snapshot_args, print_failure_summary
from evals.snapshots import SnapshotWriter, assertion_summary


class ExtractInput(BaseModel):
    ocr_golden_path: Path


async def extract_task(inputs: ExtractInput) -> CaseExtraction:
    return await extract_from_ocr_file(inputs.ocr_golden_path)


def build_extract_dataset() -> Dataset[ExtractInput, CaseExtraction, dict]:
    cases = [
        Case(
            name=eval_case.slug,
            inputs=ExtractInput(ocr_golden_path=eval_case.ocr_golden_path),
            metadata={
                "extract_checks": {
                    **eval_case.extract_checks,
                    "no_hallucinated_zoom_urls": True,
                },
            },
            evaluators=[ExtractChecksPass()],
        )
        for eval_case in EVAL_CASES
    ]
    return Dataset(name="court_extract", cases=cases, evaluators=[])


def _save_extract_snapshots(report, *, writer: SnapshotWriter) -> None:
    for case in report.cases:
        passed = all(a.value for a in case.assertions.values()) if case.assertions else True
        writer.write_json(case.name, "extraction.json", case.output)
        writer.write_json(
            case.name,
            "meta.json",
            {
                "inputs": case.inputs.model_dump(mode="json"),
                "extract_checks": case.metadata.get("extract_checks") if case.metadata else {},
                "assertions": assertion_summary(case.assertions),
                "task_duration_s": case.task_duration,
            },
        )
        writer.record_case(
            case.name,
            passed=passed,
            files=["extraction.json", "meta.json"],
        )
    for failure in report.failures:
        writer.record_case(
            failure.name,
            passed=False,
            files=[],
            meta={"error": failure.error_message},
        )


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run extract evals on golden OCR text")
    add_snapshot_args(parser)
    args = parser.parse_args()

    dataset = build_extract_dataset()
    report = await dataset.evaluate(extract_task)
    report.print(
        include_input=False,
        include_output=False,
        include_durations=True,
        include_reasons=True,
    )
    print_failure_summary(report)
    if args.snapshot:
        writer = SnapshotWriter.create("extract", label=args.snapshot_label)
        _save_extract_snapshots(report, writer=writer)
        run_dir = writer.finalize()
        print(f"\nSnapshot: {run_dir}")
    if _report_failed(report):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
