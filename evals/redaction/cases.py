"""Redaction eval case registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from evals.redaction.fixtures import (
    SYNTHETIC_ADDRESS,
    SYNTHETIC_NAME,
    SYNTHETIC_SSN,
    ensure_synthetic_fixtures,
    synthetic_pdf_path,
)

EVALS_DIR = Path(__file__).resolve().parent.parent
REDACTION_DIR = EVALS_DIR / "redaction"
PROJECT_ROOT = EVALS_DIR.parent
CASES_PATH = REDACTION_DIR / "cases.yaml"


@dataclass(frozen=True)
class RedactionEvalCase:
    slug: str
    pdf_path: Path
    forbidden_phrases: list[str]
    min_entities: int
    expected_entity_types: list[str]


def _repo_path(rel: str | Path) -> Path:
    return PROJECT_ROOT / Path(str(rel).replace("\\", "/"))


def _case_from_item(item: dict) -> RedactionEvalCase:
    return RedactionEvalCase(
        slug=str(item["slug"]),
        pdf_path=_repo_path(item["pdf_path"]),
        forbidden_phrases=list(item.get("forbidden_phrases") or []),
        min_entities=int(item.get("min_entities", 1)),
        expected_entity_types=list(item.get("expected_entity_types") or []),
    )


def load_redaction_cases() -> list[RedactionEvalCase]:
    ensure_synthetic_fixtures()
    if CASES_PATH.is_file():
        raw = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8")) or {}
        return [_case_from_item(item) for item in raw.get("cases", [])]
    # Fallback if YAML missing
    return [
        RedactionEvalCase(
            slug="synthetic_consumer",
            pdf_path=synthetic_pdf_path(),
            forbidden_phrases=[SYNTHETIC_NAME, SYNTHETIC_SSN, "742 Evergreen"],
            min_entities=3,
            expected_entity_types=["name", "ssn", "address"],
        )
    ]


REDACTION_CASES = load_redaction_cases()
