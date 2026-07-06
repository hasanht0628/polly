#!/usr/bin/env python3
"""Compare two eval regression snapshot runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.snapshots import RUNS_DIR, compare_run_dirs, load_manifest


def _resolve_run(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        return candidate.resolve()

    # suite/latest or suite -> latest run for suite
    normalized = path.strip("/")
    if normalized.endswith("/latest") or normalized.endswith("\\latest"):
        normalized = normalized.rsplit("/", 1)[0].rsplit("\\", 1)[0]
    if "/" not in normalized and "\\" not in normalized:
        latest_file = RUNS_DIR / normalized / "latest.txt"
        if latest_file.is_file():
            rel = latest_file.read_text(encoding="utf-8").strip()
            return (RUNS_DIR.parent / rel).resolve()

    # runs/suite/timestamp or suite/timestamp
    parts = Path(normalized)
    if len(parts.parts) >= 2:
        run_candidate = RUNS_DIR / parts
        if run_candidate.is_dir():
            return run_candidate.resolve()
        run_candidate = RUNS_DIR.parent / parts
        if run_candidate.is_dir():
            return run_candidate.resolve()

    raise FileNotFoundError(f"Run not found: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare eval regression snapshots")
    parser.add_argument("baseline", help="Baseline run dir, or suite name for latest")
    parser.add_argument("current", help="Current run dir, or suite name for latest")
    args = parser.parse_args()

    baseline = _resolve_run(args.baseline)
    current = _resolve_run(args.current)
    suite = load_manifest(baseline).get("suite")
    print(compare_run_dirs(baseline, current, suite=suite), end="")


if __name__ == "__main__":
    main()
