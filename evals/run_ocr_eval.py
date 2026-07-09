#!/usr/bin/env python3
"""Run OCR evals against all fixture PDFs."""

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

from documents.ocr import load_document_text
from evals.court.cases import EVAL_CASES
from evals.evaluators import RequiredPhrasesPresent
from evals.runner_utils import _report_failed, add_snapshot_args, print_failure_summary
from evals.snapshots import SnapshotWriter, assertion_summary


class OcrInput(BaseModel):
    pdf_path: Path


async def ocr_task(inputs: OcrInput, *, use_cache: bool) -> str:
    document = await load_document_text(inputs.pdf_path, use_cache=use_cache)
    return document.text


def build_ocr_dataset() -> Dataset[OcrInput, str, dict]:
    cases = [
        Case(
            name=eval_case.slug,
            inputs=OcrInput(pdf_path=eval_case.pdf_path),
            metadata={
                "required_phrases": list(eval_case.required_phrases),
            },
            evaluators=[RequiredPhrasesPresent()],
        )
        for eval_case in EVAL_CASES
    ]
    return Dataset(name="court_ocr", cases=cases, evaluators=[])


def _save_ocr_snapshots(
    report,
    *,
    writer: SnapshotWriter,
    use_cache: bool,
) -> None:
    for case in report.cases:
        passed = all(a.value for a in case.assertions.values()) if case.assertions else True
        writer.write_text(case.name, "ocr.txt", case.output)
        writer.write_json(
            case.name,
            "meta.json",
            {
                "inputs": case.inputs.model_dump(mode="json"),
                "assertions": assertion_summary(case.assertions),
                "task_duration_s": case.task_duration,
                "use_cache": use_cache,
            },
        )
        writer.record_case(
            case.name,
            passed=passed,
            files=["ocr.txt", "meta.json"],
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

    parser = argparse.ArgumentParser(description="Run OCR evals against fixture PDFs")
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use sidecar .ocr.txt cache next to PDFs (fast, skips live olmocr2)",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        metavar="SLUG",
        help="Run only these case slugs (repeatable)",
    )
    add_snapshot_args(parser)
    args = parser.parse_args()

    eval_cases = EVAL_CASES
    if args.cases:
        selected = set(args.cases)
        eval_cases = [c for c in EVAL_CASES if c.slug in selected]
        if not eval_cases:
            raise SystemExit(f"No matching cases for: {', '.join(args.cases)}")

    async def task(inputs: OcrInput) -> str:
        return await ocr_task(inputs, use_cache=args.use_cache)

    cases = [
        Case(
            name=eval_case.slug,
            inputs=OcrInput(pdf_path=eval_case.pdf_path),
            metadata={
                "required_phrases": list(eval_case.required_phrases),
            },
            evaluators=[RequiredPhrasesPresent()],
        )
        for eval_case in eval_cases
    ]
    dataset = Dataset(name="court_ocr", cases=cases, evaluators=[])
    report = await dataset.evaluate(task)
    report.print(
        include_input=True,
        include_output=False,
        include_durations=True,
        include_reasons=True,
    )
    print_failure_summary(report)
    if args.snapshot:
        writer = SnapshotWriter.create(
            "ocr",
            label=args.snapshot_label,
            extra={"use_cache": args.use_cache},
        )
        _save_ocr_snapshots(report, writer=writer, use_cache=args.use_cache)
        run_dir = writer.finalize()
        print(f"\nSnapshot: {run_dir}")
    if _report_failed(report):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
