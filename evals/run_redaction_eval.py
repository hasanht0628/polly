#!/usr/bin/env python3
"""Run redaction evals on synthetic text-layer PDF (needs Ollama for detect)."""

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

from agents.config import active_model_names
from evals.evaluators import RedactionChecksPass
from evals.redaction.cases import REDACTION_CASES
from evals.redaction.fixtures import ensure_synthetic_fixtures
from evals.runner_utils import _report_failed, add_snapshot_args, print_failure_summary
from evals.snapshots import SnapshotWriter, assertion_summary
from redaction.schemas import RedactionDocumentResult
from workflows.redaction.run import redact_one_pdf


class RedactionInput(BaseModel):
    pdf_path: Path


CASE_METRICS: dict[str, dict[str, int | float]] = {}


async def redaction_task(inputs: RedactionInput) -> RedactionDocumentResult:
    result = await redact_one_pdf(inputs.pdf_path, use_cache=True)
    CASE_METRICS[inputs.pdf_path.stem] = {
        **result.llm_usage,
        "ocr_total_tokens": result.ocr_usage.get("total_tokens", 0),
        "duration_s": result.duration_s,
    }
    return result


def build_redaction_dataset() -> Dataset[RedactionInput, RedactionDocumentResult, dict]:
    ensure_synthetic_fixtures()
    cases = [
        Case(
            name=eval_case.slug,
            inputs=RedactionInput(pdf_path=eval_case.pdf_path),
            metadata={
                "redaction_checks": {
                    "forbidden_phrases": eval_case.forbidden_phrases,
                    "min_entities": eval_case.min_entities,
                    "expected_entity_types": eval_case.expected_entity_types,
                },
            },
            evaluators=[RedactionChecksPass()],
        )
        for eval_case in REDACTION_CASES
    ]
    return Dataset(name="redaction", cases=cases, evaluators=[])


def _save_redaction_snapshots(report, *, writer: SnapshotWriter) -> None:
    for case in report.cases:
        passed = all(a.value for a in case.assertions.values()) if case.assertions else True
        writer.write_json(case.name, "document.json", case.output)
        writer.write_json(
            case.name,
            "meta.json",
            {
                "inputs": case.inputs.model_dump(mode="json"),
                "redaction_checks": case.metadata.get("redaction_checks")
                if case.metadata
                else {},
                "assertions": assertion_summary(case.assertions),
                "task_duration_s": case.task_duration,
                "llm_usage": CASE_METRICS.get(case.name, {}),
                "models": active_model_names(),
            },
        )
        writer.record_case(
            case.name,
            passed=passed,
            files=["document.json", "meta.json"],
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

    parser = argparse.ArgumentParser(
        description="Run PII redaction evals on synthetic consumer PDF"
    )
    add_snapshot_args(parser)
    args = parser.parse_args()

    dataset = build_redaction_dataset()
    report = await dataset.evaluate(redaction_task)
    try:
        report.print(
            include_input=False,
            include_output=False,
            include_durations=True,
            include_reasons=True,
        )
    except UnicodeEncodeError:
        print("Evaluation complete (summary table skipped on this console encoding).")
        for case in report.cases:
            passed = all(a.value for a in case.assertions.values()) if case.assertions else True
            status = "PASS" if passed else "FAIL"
            print(f"  {case.name}: {status} ({case.task_duration:.1f}s)")
        for failure in report.failures:
            print(f"  {failure.name}: ERROR {failure.error_message}")
    print_failure_summary(report)
    if args.snapshot:
        writer = SnapshotWriter.create("redaction", label=args.snapshot_label)
        _save_redaction_snapshots(report, writer=writer)
        run_dir = writer.finalize()
        print(f"\nSnapshot: {run_dir}")
    if _report_failed(report):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
