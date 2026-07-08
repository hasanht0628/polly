"""Offline eval tests — no Ollama required."""

from __future__ import annotations

from evals.court.cases import EVAL_CASES, load_eval_cases


def test_eval_cases_loaded() -> None:
    assert len(EVAL_CASES) == 3
    slugs = {case.slug for case in EVAL_CASES}
    assert slugs == {"case_1", "case_2", "doc_viewer"}


def test_ocr_goldens_exist_and_contain_phrases() -> None:
    for case in load_eval_cases():
        assert case.ocr_golden_path.is_file(), f"missing OCR golden: {case.slug}"
        text = case.ocr_golden_path.read_text(encoding="utf-8").lower()
        assert text.count("--- page ") >= 1, f"no page markers: {case.slug}"
        for phrase in case.required_phrases:
            assert phrase.lower() in text, f"{case.slug} missing phrase: {phrase!r}"


def test_extract_checks_defined() -> None:
    for case in load_eval_cases():
        checks = case.extract_checks
        assert checks.get("case_number"), f"{case.slug} missing case_number check"
        assert "min_events" in checks, f"{case.slug} missing min_events"


def test_phrase_matcher_ignores_whitespace_in_ids() -> None:
    from evals.evaluators import _phrase_present

    text = "Meeting ID: 4090526226"
    assert _phrase_present("409 052 6226", text)
    assert _phrase_present("26-SC-002955", "CASE NO. 26-SC-002955")
    assert _phrase_present("April 24, 2026", "PRETRIAL CONFERENCE on April 24 2026 at 10:00")
