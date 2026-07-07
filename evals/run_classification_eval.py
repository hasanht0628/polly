#!/usr/bin/env python3
"""Run classification evals using golden OCR text fixtures (no live OCR)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from pydantic import BaseModel
from pydantic_evals import Case, Dataset

from classification.schemas import ClientTaxonomy, ProductClassification
from classification.taxonomy import merge_taxonomies
from documents.profiles.product_classification import classify_from_ocr_file
from evals.classification.cases import CLASSIFICATION_CASES
from evals.evaluators import ClassificationChecksPass
from evals.runner_utils import _report_failed, add_snapshot_args
from evals.snapshots import SnapshotWriter, assertion_summary
from knowledge.client_manuals.store import retrieve_manual_passages


class ClassificationInput(BaseModel):
    ocr_fixture_path: Path
    client_id: str


def _load_taxonomy(client_id: str) -> ClientTaxonomy | None:
    path = PROJECT_ROOT / "fixtures/classification/manuals/acme_taxonomy.json"
    if client_id != "acme" or not path.is_file():
        return None
    return ClientTaxonomy.model_validate_json(path.read_text(encoding="utf-8"))


async def classification_task(inputs: ClassificationInput) -> ProductClassification:
    text = inputs.ocr_fixture_path.read_text(encoding="utf-8")
    taxonomy = merge_taxonomies(_load_taxonomy(inputs.client_id))
    taxonomy.client_id = inputs.client_id
    passages = retrieve_manual_passages(
        inputs.client_id,
        text[:4000],
        root=PROJECT_ROOT / "knowledge/client_manuals",
    )
    return await classify_from_ocr_file(
        inputs.ocr_fixture_path,
        client_id=inputs.client_id,
        taxonomy=taxonomy,
        passages=passages,
    )


def build_classification_dataset() -> Dataset[ClassificationInput, ProductClassification, dict]:
    cases = [
        Case(
            name=eval_case.slug,
            inputs=ClassificationInput(
                ocr_fixture_path=eval_case.ocr_fixture_path,
                client_id=eval_case.client_id,
            ),
            metadata={
                "classification_checks": {
                    "expected_product_type": eval_case.expected_product_type,
                    "evidence_phrases": eval_case.evidence_phrases,
                },
            },
            evaluators=[ClassificationChecksPass()],
        )
        for eval_case in CLASSIFICATION_CASES
    ]
    return Dataset(name="account_classification", cases=cases, evaluators=[])


def _save_classification_snapshots(report, *, writer: SnapshotWriter) -> None:
    for case in report.cases:
        passed = all(a.value for a in case.assertions.values()) if case.assertions else True
        writer.write_json(case.name, "classification.json", case.output)
        writer.write_json(
            case.name,
            "meta.json",
            {
                "inputs": case.inputs.model_dump(mode="json"),
                "classification_checks": case.metadata.get("classification_checks")
                if case.metadata
                else {},
                "assertions": assertion_summary(case.assertions),
                "task_duration_s": case.task_duration,
            },
        )
        writer.record_case(
            case.name,
            passed=passed,
            files=["classification.json", "meta.json"],
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
        description="Run account classification evals on golden OCR text"
    )
    add_snapshot_args(parser)
    args = parser.parse_args()

    dataset = build_classification_dataset()
    report = await dataset.evaluate(classification_task)
    try:
        report.print(include_input=False, include_output=False, include_durations=True)
    except UnicodeEncodeError:
        print("Evaluation complete (summary table skipped on this console encoding).")
        for case in report.cases:
            passed = all(a.value for a in case.assertions.values()) if case.assertions else True
            status = "PASS" if passed else "FAIL"
            print(f"  {case.name}: {status} ({case.task_duration:.1f}s)")
        for failure in report.failures:
            print(f"  {failure.name}: ERROR {failure.error_message}")
    if args.snapshot:
        writer = SnapshotWriter.create("classification", label=args.snapshot_label)
        _save_classification_snapshots(report, writer=writer)
        run_dir = writer.finalize()
        print(f"\nSnapshot: {run_dir}")
    if _report_failed(report):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
