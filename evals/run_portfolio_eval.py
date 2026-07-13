#!/usr/bin/env python3
"""Run portfolio classification evals on sample.dat + synthetic_test codes."""

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

from pydantic import BaseModel
from pydantic_evals import Case, Dataset

from agents.config import active_model_names
from agents.extract_utils import empty_usage, merge_usage
from evals.evaluators import PortfolioChecksPass
from evals.portfolio.cases import PORTFOLIO_CASES, PORTFOLIO_EVAL, PortfolioEvalCase
from evals.runner_utils import _report_failed, add_snapshot_args, print_failure_summary
from evals.snapshots import SnapshotWriter, assertion_summary
from workflows.portfolio_classification.run import run_portfolio_classification
from workflows.schemas import PortfolioAccountResult, PortfolioClassificationBatch

# Populated by the batch task; per-case tasks look up results by case_id.
_BATCH_BY_CASE: dict[str, PortfolioAccountResult] = {}
_BATCH_SUMMARY: dict[str, int] = {}
_CASE_METRICS: dict[str, dict[str, object]] = {}
_BATCH_DURATION_S = 0.0


class PortfolioInput(BaseModel):
    case_id: str
    slug: str


def _metrics_for_account(account: PortfolioAccountResult) -> dict[str, object]:
    llm = dict(account.llm_usage or empty_usage())
    ocr = dict(account.ocr_usage or empty_usage())
    return {
        "duration_s": float(account.duration_s),
        "source": account.source.value,
        "llm_usage": llm,
        "ocr_usage": ocr,
        "total_usage": merge_usage(llm, ocr),
    }


async def _run_batch(
    eval_cases: list[PortfolioEvalCase],
    *,
    use_cache: bool,
) -> None:
    import time

    global _BATCH_DURATION_S
    case_ids = {c.case_id for c in eval_cases}
    needs_llm = any(c.expected_source == "llm" for c in eval_cases)
    docs_root = PORTFOLIO_EVAL.docs_root if needs_llm else None

    started = time.perf_counter()
    batch: PortfolioClassificationBatch = await run_portfolio_classification(
        PORTFOLIO_EVAL.dat_path,
        docs_root=docs_root,
        codes_path=PORTFOLIO_EVAL.codes_path,
        client_id=PORTFOLIO_EVAL.client_id,
        use_cache=use_cache,
        case_map_path=PORTFOLIO_EVAL.case_map_path,
        case_ids=case_ids,
    )
    _BATCH_DURATION_S = time.perf_counter() - started
    _BATCH_SUMMARY.clear()
    _BATCH_SUMMARY.update(batch.summary)
    _BATCH_BY_CASE.clear()
    _CASE_METRICS.clear()
    slug_by_case = {c.case_id: c.slug for c in eval_cases}
    for account in batch.accounts:
        _BATCH_BY_CASE[account.case_id] = account
        slug = slug_by_case.get(account.case_id, account.case_id)
        _CASE_METRICS[slug] = _metrics_for_account(account)


async def portfolio_task(inputs: PortfolioInput) -> PortfolioAccountResult:
    result = _BATCH_BY_CASE.get(inputs.case_id)
    if result is None:
        raise KeyError(f"No portfolio result for case_id={inputs.case_id}")
    return result


def _aggregate_usage() -> dict[str, object]:
    totals = {
        "duration_s": 0.0,
        "llm": empty_usage(),
        "ocr": empty_usage(),
        "total": empty_usage(),
    }
    for metrics in _CASE_METRICS.values():
        totals["duration_s"] = float(totals["duration_s"]) + float(metrics.get("duration_s", 0))
        totals["llm"] = merge_usage(totals["llm"], metrics.get("llm_usage", {}))  # type: ignore[arg-type]
        totals["ocr"] = merge_usage(totals["ocr"], metrics.get("ocr_usage", {}))  # type: ignore[arg-type]
        totals["total"] = merge_usage(totals["total"], metrics.get("total_usage", {}))  # type: ignore[arg-type]
    return totals


def _save_portfolio_snapshots(report, *, writer: SnapshotWriter) -> None:
    models = active_model_names()
    usage_totals = _aggregate_usage()
    writer.write_json(
        "_batch",
        "summary.json",
        {
            "summary": _BATCH_SUMMARY,
            "dat_path": str(PORTFOLIO_EVAL.dat_path.relative_to(PROJECT_ROOT)),
            "docs_root": str(PORTFOLIO_EVAL.docs_root.relative_to(PROJECT_ROOT)),
            "codes_path": str(PORTFOLIO_EVAL.codes_path.relative_to(PROJECT_ROOT)),
            "models": models,
            "batch_duration_s": _BATCH_DURATION_S,
            "usage_totals": usage_totals,
        },
    )
    for case in report.cases:
        passed = all(a.value for a in case.assertions.values()) if case.assertions else True
        metrics = _CASE_METRICS.get(case.name, {})
        writer.write_json(case.name, "account.json", case.output)
        writer.write_json(
            case.name,
            "meta.json",
            {
                "inputs": case.inputs.model_dump(mode="json"),
                "portfolio_checks": case.metadata.get("portfolio_checks")
                if case.metadata
                else {},
                "assertions": assertion_summary(case.assertions),
                "task_duration_s": metrics.get("duration_s", case.task_duration),
                "source": metrics.get("source"),
                "llm_usage": metrics.get("llm_usage", empty_usage()),
                "ocr_usage": metrics.get("ocr_usage", empty_usage()),
                "total_usage": metrics.get("total_usage", empty_usage()),
                "models": models,
            },
        )
        writer.record_case(
            case.name,
            passed=passed,
            files=["account.json", "meta.json"],
        )
    for failure in report.failures:
        writer.record_case(
            failure.name,
            passed=False,
            files=[],
            meta={"error": failure.error_message},
        )


def _print_path_summary(report) -> None:
    print("\nPath summary:")
    print(f"{'case':<12} {'path':<10} {'source':<12} {'archetype':<20} {'status':<6}")
    print("-" * 66)
    for case in report.cases:
        passed = all(a.value for a in case.assertions.values()) if case.assertions else True
        status = "PASS" if passed else "FAIL"
        checks = case.metadata.get("portfolio_checks", {}) if case.metadata else {}
        source = getattr(case.output, "source", None)
        source_s = source.value if hasattr(source, "value") else str(source)
        archetype = getattr(case.output, "archetype", None)
        archetype_s = archetype.value if hasattr(archetype, "value") else str(archetype)
        print(
            f"{case.name:<12} {str(checks.get('resolve_path', '')):<10} "
            f"{source_s:<12} {archetype_s:<20} {status:<6}"
        )
    if _BATCH_SUMMARY:
        print(
            f"\nBatch summary: client_code={_BATCH_SUMMARY.get('client_code', 0)}, "
            f"llm={_BATCH_SUMMARY.get('llm', 0)}, "
            f"unresolved={_BATCH_SUMMARY.get('unresolved', 0)}, "
            f"total={_BATCH_SUMMARY.get('total', 0)}"
        )


def _print_usage_summary(report) -> None:
    if not report.cases:
        return
    models = active_model_names()
    print("\nUsage summary:")
    print(
        f"provider={models['provider']}  chat={models['chat_model']}  "
        f"ocr={models['ocr_model']}"
    )
    print(
        f"{'case':<12} {'src':<12} {'time_s':>7} {'llm_in':>8} {'llm_out':>8} "
        f"{'ocr_in':>8} {'ocr_out':>8} {'total':>8}"
    )
    print("-" * 84)

    totals = {
        "duration_s": 0.0,
        "llm_in": 0,
        "llm_out": 0,
        "ocr_in": 0,
        "ocr_out": 0,
        "total": 0,
    }
    for case in report.cases:
        metrics = _CASE_METRICS.get(case.name, {})
        llm = metrics.get("llm_usage", empty_usage())
        ocr = metrics.get("ocr_usage", empty_usage())
        duration = float(metrics.get("duration_s", 0))
        llm_in = int(llm.get("input_tokens", 0))
        llm_out = int(llm.get("output_tokens", 0))
        ocr_in = int(ocr.get("input_tokens", 0))
        ocr_out = int(ocr.get("output_tokens", 0))
        total = llm_in + llm_out + ocr_in + ocr_out
        source = str(metrics.get("source", ""))
        print(
            f"{case.name:<12} {source:<12} {duration:>7.1f} "
            f"{llm_in:>8} {llm_out:>8} {ocr_in:>8} {ocr_out:>8} {total:>8}"
        )
        totals["duration_s"] += duration
        totals["llm_in"] += llm_in
        totals["llm_out"] += llm_out
        totals["ocr_in"] += ocr_in
        totals["ocr_out"] += ocr_out
        totals["total"] += total

    print("-" * 84)
    print(
        f"{'TOTAL':<12} {'':<12} {totals['duration_s']:>7.1f} "
        f"{totals['llm_in']:>8} {totals['llm_out']:>8} "
        f"{totals['ocr_in']:>8} {totals['ocr_out']:>8} {totals['total']:>8}"
    )
    print(f"Wall-clock batch: {_BATCH_DURATION_S:.1f}s")
    case_count = len(report.cases)
    if case_count:
        print(
            f"Averages: {totals['duration_s'] / case_count:.1f}s/case, "
            f"{totals['total'] / case_count:.0f} tokens/case"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run portfolio classification evals (client-code + LLM paths)"
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        metavar="SLUG",
        help="Run only these case slugs (repeatable), e.g. SL-24001",
    )
    parser.add_argument(
        "--unique-only",
        action="store_true",
        help="Only run unique client-code cases (offline, no Ollama)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore OCR sidecars for LLM-path PDF reads",
    )
    add_snapshot_args(parser)
    args = parser.parse_args()

    eval_cases = list(PORTFOLIO_CASES)
    if args.unique_only:
        eval_cases = [c for c in eval_cases if c.expected_source == "client_code"]
    if args.cases:
        selected = set(args.cases)
        eval_cases = [c for c in eval_cases if c.slug in selected]
        if not eval_cases:
            raise SystemExit(f"No matching cases for: {', '.join(args.cases)}")

    await _run_batch(eval_cases, use_cache=not args.no_cache)

    cases = [
        Case(
            name=eval_case.slug,
            inputs=PortfolioInput(case_id=eval_case.case_id, slug=eval_case.slug),
            metadata={
                "portfolio_checks": {
                    "expected_source": eval_case.expected_source,
                    "expected_archetype": eval_case.expected_archetype,
                    "resolve_path": eval_case.resolve_path,
                    "account_id": eval_case.account_id,
                },
            },
            evaluators=[PortfolioChecksPass()],
        )
        for eval_case in eval_cases
    ]
    dataset = Dataset(name="portfolio_classification", cases=cases, evaluators=[])
    report = await dataset.evaluate(portfolio_task)
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
    _print_path_summary(report)
    _print_usage_summary(report)
    if args.snapshot:
        writer = SnapshotWriter.create("portfolio", label=args.snapshot_label)
        _save_portfolio_snapshots(report, writer=writer)
        run_dir = writer.finalize()
        print(f"\nSnapshot: {run_dir}")
    if _report_failed(report):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
