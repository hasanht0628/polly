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
