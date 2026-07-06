from __future__ import annotations

import json
from pathlib import Path

import pytest

from court.schemas import CaseExtraction
from workflows.court_calendar.map_extraction import map_extraction_to_review_package
from workflows.intake.email_parser import parse_email_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = PROJECT_ROOT / "evals/extract/goldens/case_1.json"


def test_map_extraction_produces_schedulable_events() -> None:
    extraction = CaseExtraction.model_validate_json(GOLDEN.read_text(encoding="utf-8"))
    package = map_extraction_to_review_package(
        extraction,
        pdf_path=PROJECT_ROOT / "fixtures/case 1.pdf",
    )
    assert package.case_number == "26-CC-001299"
    assert len(package.schedulable_events) >= 2
    titles = " ".join(event.title.lower() for event in package.schedulable_events)
    assert "docket sounding" in titles
    assert package.schedulable_events[0].virtual_meeting_id == "311 329 7498" or any(
        e.virtual_meeting_id == "311 329 7498" for e in package.schedulable_events
    )


def test_relative_deadlines_go_to_flagged() -> None:
    extraction = CaseExtraction.model_validate_json(GOLDEN.read_text(encoding="utf-8"))
    package = map_extraction_to_review_package(extraction)
    assert any(item.kind == "deadline" for item in package.flagged_items)


def test_email_parser_finds_documents_pdf_url() -> None:
    body = """
Court Notice

Documents:
https://courts.example.com/files/notice.pdf

CONFIDENTIALITY NOTICE
This email is privileged.
"""
    email = parse_email_text(body, subject="Scheduling Order", sender="clerk@courts.gov")
    assert email.pdf_urls == ["https://courts.example.com/files/notice.pdf"]
    assert email.documents_section is not None
    assert "confidentiality notice" not in email.body_text.lower()
