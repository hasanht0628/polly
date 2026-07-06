from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import NativeOutput

from court.extract_models import (
    ExtractedCaseInfo,
    ExtractedDeadlines,
    ExtractedEvents,
)
from court.normalize import normalize_extraction
from court.pdf_text import load_document_text
from court.schemas import CaseExtraction
from tutorials.config import make_agent

EXTRACT_MODEL_SETTINGS = {"temperature": 0}

EXTRACT_SYSTEM_PROMPT = """\
You extract structured case information from court documents for a law firm calendar workflow.

Rules:
- Output only information explicitly stated in the document.
- Include source_quote for every event and deadline (verbatim supporting text).
- Distinguish scheduled events from filing/compliance deadlines.
- For relative deadlines, capture anchor_event, offset_days, direction, and day_type as written.
- Do not calculate resulting due dates.
- Never invent dates, times, locations, or meeting IDs.
"""

case_agent = make_agent(
    output_type=NativeOutput(ExtractedCaseInfo),
    system_prompt=EXTRACT_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)

events_agent = make_agent(
    output_type=NativeOutput(ExtractedEvents),
    system_prompt=EXTRACT_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)

deadlines_agent = make_agent(
    output_type=NativeOutput(ExtractedDeadlines),
    system_prompt=EXTRACT_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)

CASE_PROMPT = (
    "Extract the case caption (parties), case number, and court name from the document header."
)

EVENTS_PROMPT = (
    "Extract scheduled calendar events only: trial dates or trial periods, docket sounding, "
    "hearings, and mediations. "
    "Set location_type to virtual when the document says VIA ZOOM; physical for in-person courtrooms. "
    "Put the Zoom meeting ID exactly as written (e.g. '311 329 7498') in virtual_meeting_id. "
    "Do not construct URLs. Do not include filing deadlines."
)

DEADLINES_PROMPT = (
    "Extract filing and compliance deadlines from Pre-trial Events and similar sections. "
    "Include relative deadlines exactly as written. "
    "Set kind=relative with anchor_event, offset_days, direction=before, day_type=calendar when applicable. "
    "Do not include trial dates, docket sounding dates, or other scheduled hearings."
)


def _select_pages(document_text: str, pages: list[int]) -> str:
    sections: list[str] = []
    for page in pages:
        marker = f"--- Page {page} ---"
        start = document_text.find(marker)
        if start == -1:
            continue
        start += len(marker)
        next_marker = document_text.find("\n--- Page ", start)
        chunk = document_text[start:next_marker if next_marker != -1 else None].strip()
        if chunk:
            sections.append(f"{marker}\n{chunk}")
    return "\n\n".join(sections) if sections else document_text


OutputT = TypeVar("OutputT", bound=BaseModel)


async def _run_with_retries(
    agent,
    prompt: str,
    *,
    attempts: int = 2,
    is_empty,
) -> OutputT:
    last: OutputT | None = None
    for _ in range(attempts):
        result = await agent.run(prompt)
        last = result.output
        if not is_empty(last):
            return last
    assert last is not None
    return last


async def extract_from_document_text(
    doc_text: str, *, page_count: int
) -> CaseExtraction:
    case_info = await _run_with_retries(
        case_agent,
        CASE_PROMPT + f"\n\nCourt document (page 1):\n\n{_select_pages(doc_text, [1])}",
        is_empty=lambda info: not any(
            [info.case_caption, info.case_number, info.court]
        ),
    )
    events = await _run_with_retries(
        events_agent,
        EVENTS_PROMPT + f"\n\nCourt document (pages 1-2):\n\n{_select_pages(doc_text, [1, 2])}",
        is_empty=lambda data: len(data.events) == 0,
    )
    deadlines = await _run_with_retries(
        deadlines_agent,
        DEADLINES_PROMPT + f"\n\nCourt document (pages 1-2):\n\n{_select_pages(doc_text, [1, 2])}",
        is_empty=lambda data: len(data.deadlines) == 0,
    )
    return normalize_extraction(
        case_info,
        events,
        deadlines,
        page_count=page_count,
    )


async def extract_from_ocr_file(path: Path) -> CaseExtraction:
    path = path.resolve()
    text = path.read_text(encoding="utf-8")
    page_count = text.count("--- Page ") or 1
    return await extract_from_document_text(text, page_count=page_count)


async def extract_from_pdf(path: Path, *, use_cache: bool = True) -> CaseExtraction:
    document = await load_document_text(path, use_cache=use_cache)
    return await extract_from_document_text(
        document.text, page_count=document.page_count
    )
