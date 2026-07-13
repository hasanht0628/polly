"""Shared PDF OCR via olmocr2 (page render + vision model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
from pydantic_ai.messages import BinaryContent

from agents.config import make_ocr_agent
from agents.extract_utils import EXTRACT_MODEL_SETTINGS, RunMetrics

OCR_PROMPT = "Return all text on this page in reading order. Output plain text only."


@dataclass(frozen=True)
class DocumentText:
    text: str
    page_count: int


def ocr_cache_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.ocr.txt")


def _render_page_png(doc: fitz.Document, page_index: int) -> bytes:
    page = doc.load_page(page_index)
    pixmap = page.get_pixmap()
    return pixmap.tobytes("png")


async def _ocr_page(png_bytes: bytes, *, metrics: RunMetrics | None = None) -> str:
    ocr_agent = make_ocr_agent(model_settings=EXTRACT_MODEL_SETTINGS)
    result = await ocr_agent.run(
        [
            OCR_PROMPT,
            BinaryContent(data=png_bytes, media_type="image/png"),
        ]
    )
    if metrics is not None:
        metrics.incr_usage(result.usage)
        metrics.attempts += 1
    return str(result.output).strip()


async def _ocr_pdf(path: Path, *, metrics: RunMetrics | None = None) -> DocumentText:
    page_texts: list[str] = []
    with fitz.open(path) as doc:
        page_count = doc.page_count
        for page_index in range(page_count):
            png_bytes = _render_page_png(doc, page_index)
            page_text = await _ocr_page(png_bytes, metrics=metrics)
            page_texts.append(page_text)

    combined = "\n\n".join(
        f"--- Page {index + 1} ---\n{text}" for index, text in enumerate(page_texts)
    )
    return DocumentText(text=combined, page_count=page_count)


def _load_cached_text(path: Path, cache_path: Path) -> DocumentText | None:
    if not cache_path.is_file() or cache_path.stat().st_mtime < path.stat().st_mtime:
        return None
    text = cache_path.read_text(encoding="utf-8")
    page_count = text.count("--- Page ")
    return DocumentText(text=text, page_count=page_count or 1)


def _save_cached_text(cache_path: Path, document: DocumentText) -> None:
    cache_path.write_text(document.text, encoding="utf-8")


async def load_document_text(
    path: Path,
    *,
    use_cache: bool = True,
    metrics: RunMetrics | None = None,
) -> DocumentText:
    """Render every PDF page and OCR it with olmocr2. No native text extraction."""
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    cache_path = ocr_cache_path(path)
    if use_cache:
        cached = _load_cached_text(path, cache_path)
        if cached is not None:
            return cached

    document = await _ocr_pdf(path, metrics=metrics)
    if use_cache:
        _save_cached_text(cache_path, document)
    return document
