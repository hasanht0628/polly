"""Shared PDF → text ingest."""

from __future__ import annotations

from pathlib import Path

from documents.ocr import DocumentText, load_document_text as _load_document_text
from documents.schemas import DocumentTextResult


async def load_document_text(
    path: Path,
    *,
    use_cache: bool = True,
) -> DocumentTextResult:
    path = path.resolve()
    document: DocumentText = await _load_document_text(path, use_cache=use_cache)
    return DocumentTextResult(
        text=document.text,
        page_count=document.page_count,
        source_path=path,
    )
