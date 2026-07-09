"""Shared helpers for eval runner CLIs."""

from __future__ import annotations

import argparse


def add_snapshot_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--snapshot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write regression snapshots under evals/runs/ (default: on)",
    )
    parser.add_argument(
        "--snapshot-label",
        default=None,
        help="Optional run folder name (default: UTC timestamp)",
    )


def _report_failed(report) -> bool:
    if report.failures:
        return True
    return any(
        not result.value
        for case in report.cases
        for result in case.assertions.values()
    )


def print_failure_summary(report) -> None:
    """Print per-case failure reasons from evaluator assertions."""
    failures: list[tuple[str, list[str]]] = []

    for failure in report.failures:
        failures.append((failure.name, [failure.error_message]))

    for case in report.cases:
        reasons: list[str] = []
        for name, result in case.assertions.items():
            if result.value:
                continue
            reason = getattr(result, "reason", None)
            if reason:
                reasons.append(f"{name}: {reason}")
            else:
                reasons.append(f"{name}: check failed")
        if reasons:
            failures.append((case.name, reasons))

    if not failures:
        return

    print("\nFailure details:")
    for case_name, reasons in failures:
        print(f"  {case_name}:")
        for reason in reasons:
            print(f"    - {reason}")
