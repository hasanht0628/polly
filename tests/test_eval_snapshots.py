from __future__ import annotations

import json
from pathlib import Path

from court.schemas import CaseExtraction
from evals.snapshots import SnapshotWriter, compare_run_dirs


def test_snapshot_writer_creates_manifest_and_files(tmp_path: Path) -> None:
    writer = SnapshotWriter.create("proposal", runs_root=tmp_path, label="test_run")
    writer.write_json("case_1", "review_package.json", {"ok": True})
    writer.record_case("case_1", passed=True, files=["review_package.json"])
    run_dir = writer.finalize(runs_root=tmp_path)

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["suite"] == "proposal"
    assert manifest["cases"]["case_1"]["passed"] is True
    assert (run_dir / "case_1" / "review_package.json").is_file()
    assert (tmp_path / "proposal" / "latest.txt").is_file()


def test_compare_extract_snapshots_detects_case_number_change(tmp_path: Path) -> None:
    base = SnapshotWriter.create("extract", runs_root=tmp_path, label="base")
    curr = SnapshotWriter.create("extract", runs_root=tmp_path, label="curr")

    extraction_a = CaseExtraction(case_number="26-CC-001299")
    extraction_b = CaseExtraction(case_number="26-CC-999999")
    base.write_json("case_1", "extraction.json", extraction_a)
    curr.write_json("case_1", "extraction.json", extraction_b)
    base.record_case("case_1", passed=True, files=["extraction.json"])
    curr.record_case("case_1", passed=True, files=["extraction.json"])
    base_dir = base.finalize(runs_root=tmp_path)
    curr_dir = curr.finalize(runs_root=tmp_path)

    diff = compare_run_dirs(base_dir, curr_dir, suite="extract")
    assert "case_number" in diff
