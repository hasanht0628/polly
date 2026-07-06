#!/usr/bin/env python3
"""Bootstrap OCR goldens, extract goldens, and cases.yaml metadata for all eval cases."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from court.extract import extract_from_ocr_file
from court.pdf_text import load_document_text
from evals.cases import EVAL_CASES, EvalCase, FIXTURES_DIR

CASES_YAML = Path(__file__).resolve().parent / "cases.yaml"
OCR_GOLDENS = Path(__file__).resolve().parent / "ocr" / "goldens"
EXTRACT_GOLDENS = Path(__file__).resolve().parent / "extract" / "goldens"

_CASE_NUMBER = re.compile(r"Case No\.?:?\s*([^\s,]+)", re.IGNORECASE)
_RELATIVE_DEADLINE = re.compile(r"\(\d+\)\s*days?\s+prior", re.IGNORECASE)


def _derive_phrases(text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    if match := _CASE_NUMBER.search(text):
        phrases.append(match.group(1).strip())
    for label in ("Docket Sounding", "TRIAL", "Pre-trial Events", "VIA ZOOM"):
        if label.lower() in text.lower():
            phrases.append(label)
    if match := re.search(r"ID:\s*([\d\s]+)", text, re.IGNORECASE):
        phrases.append(re.sub(r"\s+", " ", match.group(1).strip()))
    if match := re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
        text,
        re.IGNORECASE,
    ):
        phrases.append(match.group(0))
    if _RELATIVE_DEADLINE.search(text):
        for line in text.splitlines():
            if _RELATIVE_DEADLINE.search(line):
                phrases.append(line.strip()[:120])
                break
    # party line heuristic
    for line in text.splitlines()[:20]:
        if " vs." in line.lower() or " v. " in line.lower():
            phrases.append(line.strip()[:80])
            break
    # dedupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for phrase in phrases:
        key = phrase.lower()
        if key not in seen and phrase:
            seen.add(key)
            unique.append(phrase)
    return tuple(unique)


def _derive_extract_checks(extraction_json: dict) -> dict[str, object]:
    checks: dict[str, object] = {
        "min_events": max(0, len(extraction_json.get("events", [])) - 1),
        "min_deadlines": max(0, len(extraction_json.get("deadlines", [])) - 1),
        "no_hallucinated_zoom_urls": True,
    }
    if case_number := extraction_json.get("case_number"):
        checks["case_number"] = case_number
    event_types = [
        e.get("event_type", "").lower()
        for e in extraction_json.get("events", [])
        if e.get("event_type")
    ]
    if event_types:
        checks["event_types"] = event_types[:2]
    deadline_phrases: list[str] = []
    for deadline in extraction_json.get("deadlines", [])[:5]:
        words = deadline.get("description", "").lower().split()
        if words:
            deadline_phrases.append(words[0])
    if deadline_phrases:
        checks["deadline_phrases"] = sorted(set(deadline_phrases))[:3]
    return checks


async def bootstrap_case(eval_case: EvalCase, *, skip_ocr: bool = False) -> dict:
    OCR_GOLDENS.mkdir(parents=True, exist_ok=True)
    EXTRACT_GOLDENS.mkdir(parents=True, exist_ok=True)

    if not skip_ocr and not eval_case.ocr_golden_path.is_file():
        document = await load_document_text(eval_case.pdf_path, use_cache=True)
        eval_case.ocr_golden_path.write_text(document.text, encoding="utf-8")
        print(f"OCR golden: {eval_case.ocr_golden_path}")
    elif eval_case.ocr_golden_path.is_file():
        print(f"OCR golden exists: {eval_case.ocr_golden_path}")
    else:
        raise FileNotFoundError(f"OCR golden missing: {eval_case.ocr_golden_path}")

    ocr_text = eval_case.ocr_golden_path.read_text(encoding="utf-8")
    phrases = _derive_phrases(ocr_text)

    extraction = await extract_from_ocr_file(eval_case.ocr_golden_path)
    extraction_dict = json.loads(extraction.model_dump_json())
    eval_case.extract_golden_path.write_text(
        json.dumps(extraction_dict, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Extract golden: {eval_case.extract_golden_path}")

    checks = _derive_extract_checks(extraction_dict)
    return {
        "slug": eval_case.slug,
        "pdf_path": str(eval_case.pdf_path.relative_to(PROJECT_ROOT)),
        "ocr_golden_path": str(eval_case.ocr_golden_path.relative_to(PROJECT_ROOT)),
        "extract_golden_path": str(eval_case.extract_golden_path.relative_to(PROJECT_ROOT)),
        "required_phrases": list(phrases),
        "extract_checks": checks,
    }


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap eval goldens")
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Skip OCR; use existing OCR goldens and only run extract + cases.yaml",
    )
    args = parser.parse_args()

    entries = []
    for eval_case in EVAL_CASES:
        entries.append(await bootstrap_case(eval_case, skip_ocr=args.extract_only))
    CASES_YAML.write_text(
        yaml.safe_dump({"cases": entries}, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Wrote {CASES_YAML}")


if __name__ == "__main__":
    asyncio.run(main())
