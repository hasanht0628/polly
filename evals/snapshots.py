"""Write and compare regression snapshots from eval runs."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
RUNS_DIR = EVALS_DIR / "runs"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=EVALS_DIR.parent,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


@dataclass
class SnapshotWriter:
    suite: str
    run_dir: Path
    manifest: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        suite: str,
        *,
        runs_root: Path = RUNS_DIR,
        label: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SnapshotWriter:
        name = label or _utc_timestamp()
        run_dir = runs_root / suite / name
        run_dir.mkdir(parents=True, exist_ok=False)
        writer = cls(
            suite=suite,
            run_dir=run_dir,
            manifest={
                "suite": suite,
                "timestamp": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "git_sha": _git_sha(),
                **(extra or {}),
                "cases": {},
            },
        )
        return writer

    def write_text(self, case_slug: str, filename: str, content: str) -> Path:
        case_dir = self._case_dir(case_slug)
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, case_slug: str, filename: str, data: Any) -> Path:
        case_dir = self._case_dir(case_slug)
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / filename
        if hasattr(data, "model_dump"):
            text = data.model_dump_json(indent=2)
        else:
            text = json.dumps(data, indent=2, default=str)
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def record_case(
        self,
        case_slug: str,
        *,
        passed: bool,
        files: list[str],
        meta: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {"passed": passed, "files": files}
        if meta:
            entry["meta"] = meta
        self.manifest["cases"][case_slug] = entry

    def finalize(self, *, runs_root: Path = RUNS_DIR) -> Path:
        manifest_path = self.run_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(self.manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        latest_path = runs_root / self.suite / "latest.txt"
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        rel = self.run_dir.relative_to(runs_root.parent)
        latest_path.write_text(str(rel) + "\n", encoding="utf-8")
        return self.run_dir

    def _case_dir(self, case_slug: str) -> Path:
        return self.run_dir / case_slug


def assertion_summary(assertions: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, result in assertions.items():
        value = getattr(result, "value", result)
        reason = getattr(result, "reason", None)
        summary[name] = {"passed": bool(value), "reason": reason}
    return summary


def load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"No manifest.json in {run_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def compare_run_dirs(baseline: Path, current: Path, *, suite: str | None = None) -> str:
    """Return a human-readable diff summary between two snapshot runs."""
    base_manifest = load_manifest(baseline)
    curr_manifest = load_manifest(current)
    lines = [
        f"Baseline: {baseline}",
        f"Current:  {current}",
        f"Suite:    {base_manifest.get('suite')} vs {curr_manifest.get('suite')}",
        "",
    ]

    all_cases = sorted(
        set(base_manifest.get("cases", {})) | set(curr_manifest.get("cases", {}))
    )
    for case_slug in all_cases:
        lines.append(f"## {case_slug}")
        base_case = base_manifest.get("cases", {}).get(case_slug)
        curr_case = curr_manifest.get("cases", {}).get(case_slug)
        if not base_case:
            lines.append("  (new in current)")
            continue
        if not curr_case:
            lines.append("  (missing in current)")
            continue

        base_pass = base_case.get("passed")
        curr_pass = curr_case.get("passed")
        if base_pass != curr_pass:
            lines.append(f"  pass status: {base_pass} -> {curr_pass}")

        if suite == "extract" or (baseline / case_slug / "extraction.json").is_file():
            base_json = baseline / case_slug / "extraction.json"
            curr_json = current / case_slug / "extraction.json"
            if base_json.is_file() and curr_json.is_file():
                lines.extend(_diff_extract_json(base_json, curr_json, prefix="  "))
        elif suite == "proposal" or (baseline / case_slug / "review_package.json").is_file():
            base_json = baseline / case_slug / "review_package.json"
            curr_json = current / case_slug / "review_package.json"
            if base_json.is_file() and curr_json.is_file():
                lines.extend(_diff_proposal_json(base_json, curr_json, prefix="  "))
        elif (baseline / case_slug / "ocr.txt").is_file():
            base_text = (baseline / case_slug / "ocr.txt").read_text(encoding="utf-8")
            curr_text = (current / case_slug / "ocr.txt").read_text(encoding="utf-8")
            if base_text != curr_text:
                lines.append(f"  ocr.txt: changed ({len(base_text)} -> {len(curr_text)} chars)")
            else:
                lines.append("  (ocr.txt unchanged)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _diff_extract_json(base_path: Path, curr_path: Path, *, prefix: str = "") -> list[str]:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    curr = json.loads(curr_path.read_text(encoding="utf-8"))
    lines: list[str] = []

    for key in ("case_number", "case_caption", "court"):
        if base.get(key) != curr.get(key):
            lines.append(f"{prefix}{key}: {base.get(key)!r} -> {curr.get(key)!r}")

    base_events = base.get("events") or []
    curr_events = curr.get("events") or []
    if len(base_events) != len(curr_events):
        lines.append(f"{prefix}events count: {len(base_events)} -> {len(curr_events)}")

    for index, (be, ce) in enumerate(zip(base_events, curr_events, strict=False)):
        for field in ("event_type", "date", "time", "virtual_meeting_id"):
            if be.get(field) != ce.get(field):
                lines.append(
                    f"{prefix}events[{index}].{field}: {be.get(field)!r} -> {ce.get(field)!r}"
                )

    base_deadlines = base.get("deadlines") or []
    curr_deadlines = curr.get("deadlines") or []
    if len(base_deadlines) != len(curr_deadlines):
        lines.append(
            f"{prefix}deadlines count: {len(base_deadlines)} -> {len(curr_deadlines)}"
        )

    if not lines:
        lines.append(f"{prefix}(extraction.json unchanged on key fields)")
    return lines


def _diff_proposal_json(base_path: Path, curr_path: Path, *, prefix: str = "") -> list[str]:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    curr = json.loads(curr_path.read_text(encoding="utf-8"))
    lines: list[str] = []

    for key in ("case_number", "case_caption", "court"):
        if base.get(key) != curr.get(key):
            lines.append(f"{prefix}{key}: {base.get(key)!r} -> {curr.get(key)!r}")

    base_sched = base.get("schedulable_events") or []
    curr_sched = curr.get("schedulable_events") or []
    if len(base_sched) != len(curr_sched):
        lines.append(
            f"{prefix}schedulable_events count: {len(base_sched)} -> {len(curr_sched)}"
        )
    for index, (be, ce) in enumerate(zip(base_sched, curr_sched, strict=False)):
        for field in ("title", "start_at", "event_type", "location"):
            if be.get(field) != ce.get(field):
                lines.append(
                    f"{prefix}schedulable_events[{index}].{field}: "
                    f"{be.get(field)!r} -> {ce.get(field)!r}"
                )

    base_flagged = base.get("flagged_items") or []
    curr_flagged = curr.get("flagged_items") or []
    if len(base_flagged) != len(curr_flagged):
        lines.append(
            f"{prefix}flagged_items count: {len(base_flagged)} -> {len(curr_flagged)}"
        )

    if not lines:
        lines.append(f"{prefix}(review_package.json unchanged on key fields)")
    return lines
