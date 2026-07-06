"""Eval case registry for the three fixture PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
CASES_YAML = EVALS_DIR / "cases.yaml"


@dataclass(frozen=True)
class EvalCase:
    slug: str
    pdf_path: Path
    ocr_golden_path: Path
    extract_golden_path: Path
    required_phrases: tuple[str, ...]
    extract_checks: dict[str, object]


def _case_from_dict(entry: dict) -> EvalCase:
    return EvalCase(
        slug=entry["slug"],
        pdf_path=PROJECT_ROOT / entry["pdf_path"],
        ocr_golden_path=PROJECT_ROOT / entry["ocr_golden_path"],
        extract_golden_path=PROJECT_ROOT / entry["extract_golden_path"],
        required_phrases=tuple(entry.get("required_phrases", [])),
        extract_checks=entry.get("extract_checks", {}),
    )


def _default_cases() -> tuple[EvalCase, ...]:
    return (
        EvalCase(
            slug="case_1",
            pdf_path=FIXTURES_DIR / "case 1.pdf",
            ocr_golden_path=EVALS_DIR / "ocr" / "goldens" / "case_1.ocr.txt",
            extract_golden_path=EVALS_DIR / "extract" / "goldens" / "case_1.json",
            required_phrases=(
                "26-CC-001299",
                "Capital One",
                "Anthony A Gomes",
                "Docket Sounding",
                "December 15, 2027",
                "thirty (30) days prior to the Docket Sounding",
                "311 329 7498",
            ),
            extract_checks={
                "case_number": "26-CC-001299",
                "min_events": 2,
                "min_deadlines": 3,
                "event_types": ["docket_sounding", "trial_period"],
                "deadline_phrases": ["exchange", "discovery", "mediation"],
            },
        ),
        EvalCase(
            slug="case_2",
            pdf_path=FIXTURES_DIR / "case 2.pdf",
            ocr_golden_path=EVALS_DIR / "ocr" / "goldens" / "case_2.ocr.txt",
            extract_golden_path=EVALS_DIR / "extract" / "goldens" / "case_2.json",
            required_phrases=(),
            extract_checks={},
        ),
        EvalCase(
            slug="doc_viewer",
            pdf_path=FIXTURES_DIR / "DocViewer.pdf",
            ocr_golden_path=EVALS_DIR / "ocr" / "goldens" / "doc_viewer.ocr.txt",
            extract_golden_path=EVALS_DIR / "extract" / "goldens" / "doc_viewer.json",
            required_phrases=(),
            extract_checks={},
        ),
    )


def load_eval_cases() -> tuple[EvalCase, ...]:
    if CASES_YAML.is_file():
        data = yaml.safe_load(CASES_YAML.read_text(encoding="utf-8"))
        return tuple(_case_from_dict(entry) for entry in data["cases"])
    return _default_cases()


EVAL_CASES = load_eval_cases()
