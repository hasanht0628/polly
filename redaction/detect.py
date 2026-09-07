"""LLM detection of name / SSN / address spans in OCR text."""

from __future__ import annotations

import re

from pydantic_ai import NativeOutput

from agents.config import make_agent
from agents.extract_utils import EXTRACT_MODEL_SETTINGS, RunMetrics, run_with_retries
from redaction.schemas import DetectedEntities, PiiCandidate, PiiEntityType

DETECT_SYSTEM_PROMPT = """\
You extract personally identifiable information (PII) from document OCR text for redaction.

Entity types (only these three):
- name: natural-person names (debtors, consumers, plaintiffs as people). Do NOT treat
  court names, company names, law firm names, or judge titles alone as name.
- ssn: Social Security Numbers in any common format (XXX-XX-XXXX, spaces, or 9 digits).
- address: physical mailing / street addresses (street line, city/state/ZIP). Multi-line
  addresses may be returned as one entity with newlines preserved as in the OCR, or as
  the longest contiguous address block.

Rules:
- Copy text spans VERBATIM from the document (same spelling, punctuation, line breaks).
- Prefer recall over precision: if unsure whether something is PII of these types, include it.
- confidence: "high" when clear; "medium" when plausible; "low" when uncertain.
- Do not invent text that is not present.
- If none found, return an empty entities list.
"""

detect_agent = make_agent(
    output_type=NativeOutput(DetectedEntities),
    system_prompt=DETECT_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)

DETECT_PROMPT = """\
Extract every name, SSN, and address from this page of OCR text.

Return structured entities only. Each entity.text must be copied verbatim from the text.

OCR page text:

{page_text}
"""

_PAGE_MARKER = re.compile(r"^--- Page (\d+) ---$", re.MULTILINE)


def split_ocr_pages(document_text: str) -> list[tuple[int, str]]:
    """Split cached OCR text into (1-based page number, page body) pairs."""
    matches = list(_PAGE_MARKER.finditer(document_text))
    if not matches:
        return [(1, document_text.strip())]

    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        page_num = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(document_text)
        body = document_text[start:end].strip()
        pages.append((page_num, body))
    return pages


def _is_empty(detected: DetectedEntities) -> bool:
    return False  # empty list is a valid answer; do not retry solely for emptiness


def _normalize_candidates(
    detected: DetectedEntities,
    *,
    page: int,
) -> list[PiiCandidate]:
    out: list[PiiCandidate] = []
    for entity in detected.entities:
        text = (entity.text or "").strip()
        if not text:
            continue
        entity_type = entity.entity_type
        if not isinstance(entity_type, PiiEntityType):
            try:
                entity_type = PiiEntityType(str(entity_type).lower())
            except ValueError:
                continue
        confidence = (entity.confidence or "medium").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        out.append(
            PiiCandidate(
                entity_type=entity_type,
                text=text,
                confidence=confidence,
                page=page,
            )
        )
    return out


async def detect_pii_on_page(
    page_text: str,
    *,
    page: int = 1,
    metrics: RunMetrics | None = None,
) -> list[PiiCandidate]:
    """Run the detect agent on one page of OCR text."""
    if not page_text.strip():
        return []
    prompt = DETECT_PROMPT.format(page_text=page_text)
    detected = await run_with_retries(
        detect_agent,
        prompt,
        attempts=2,
        is_empty=_is_empty,
        metrics=metrics,
    )
    return _normalize_candidates(detected, page=page)


async def detect_pii_in_document(
    document_text: str,
    *,
    metrics: RunMetrics | None = None,
) -> list[PiiCandidate]:
    """Detect PII on each OCR page and return combined candidates."""
    candidates: list[PiiCandidate] = []
    for page, page_text in split_ocr_pages(document_text):
        page_metrics = RunMetrics() if metrics is not None else None
        page_hits = await detect_pii_on_page(
            page_text,
            page=page,
            metrics=page_metrics,
        )
        if metrics is not None and page_metrics is not None:
            metrics.incr_usage(page_metrics.usage)
            metrics.attempts += page_metrics.attempts
        candidates.extend(page_hits)
    return candidates
