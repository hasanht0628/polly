"""Classification eval case registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

EVALS_DIR = Path(__file__).resolve().parent.parent
CLASSIFICATION_DIR = EVALS_DIR / "classification"
PROJECT_ROOT = EVALS_DIR.parent
CASES_PATH = CLASSIFICATION_DIR / "cases.yaml"
MANIFEST_PATH = CLASSIFICATION_DIR / "manifest.yaml"


@dataclass(frozen=True)
class ClassificationEvalCase:
    slug: str
    ocr_fixture_path: Path
    client_id: str
    expected_product_type: str
    evidence_phrases: list[str]
    pdf_path: Path | None = None
    classification_golden_path: Path | None = None


def _repo_path(rel: str | Path) -> Path:
    """Resolve a repo-relative path; normalize Windows separators from YAML."""
    return PROJECT_ROOT / Path(str(rel).replace("\\", "/"))


def _case_from_item(item: dict) -> ClassificationEvalCase:
    ocr_key = "ocr_fixture" if "ocr_fixture" in item else "ocr_golden_path"
    ocr_fixture = _repo_path(item[ocr_key])
    pdf_path = (
        _repo_path(item["pdf_path"])
        if item.get("pdf_path")
        else (_repo_path(item["pdf"]) if item.get("pdf") else None)
    )
    golden_path = (
        _repo_path(item["classification_golden_path"])
        if item.get("classification_golden_path")
        else None
    )
    return ClassificationEvalCase(
        slug=str(item["slug"]),
        ocr_fixture_path=ocr_fixture,
        client_id=str(item.get("client_id", "acme")),
        expected_product_type=str(item["expected_product_type"]),
        evidence_phrases=list(item.get("evidence_phrases") or []),
        pdf_path=pdf_path,
        classification_golden_path=golden_path,
    )


def load_classification_cases() -> list[ClassificationEvalCase]:
    if CASES_PATH.is_file():
        raw = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8")) or {}
        cases = [_case_from_item(item) for item in raw.get("cases", [])]
        if cases:
            return cases

    if MANIFEST_PATH.is_file():
        raw = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
        return [_case_from_item(item) for item in raw.get("cases", [])]

    return []


CLASSIFICATION_CASES = load_classification_cases()
