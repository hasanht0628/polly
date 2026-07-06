from __future__ import annotations

from pathlib import Path
from typing import Any

from court.extract import extract_from_pdf
from court.schemas import CaseExtraction
from documents.schemas import ExtractResult


async def run_court_calendar(
    pdf_path: Path,
    *,
    use_cache: bool = True,
    context: dict[str, Any] | None = None,
) -> ExtractResult:
    del context
    extraction: CaseExtraction = await extract_from_pdf(pdf_path, use_cache=use_cache)
    return ExtractResult(
        profile_id="court_calendar",
        data=extraction,
        source_path=pdf_path.resolve(),
        extraction_notes=list(extraction.extraction_notes),
    )
