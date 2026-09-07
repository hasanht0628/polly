"""Apply located redactions to a PDF with PyMuPDF permanent redaction."""

from __future__ import annotations

from pathlib import Path

import fitz

from redaction.paths import redacted_output_path
from redaction.schemas import LocatedRedaction, PiiEntityType, RedactionEntitySummary


def ssn_last4(text: str) -> str | None:
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 4:
        return digits[-4:]
    return None


def to_entity_summary(item: LocatedRedaction) -> RedactionEntitySummary:
    if item.entity_type == PiiEntityType.ssn:
        return RedactionEntitySummary(
            entity_type=item.entity_type,
            page=item.page,
            confidence=item.confidence,
            locate_method=item.locate_method,
            ssn_last4=ssn_last4(item.text),
            text_preview=None,
        )
    preview = item.text if len(item.text) <= 80 else item.text[:77] + "..."
    return RedactionEntitySummary(
        entity_type=item.entity_type,
        page=item.page,
        confidence=item.confidence,
        locate_method=item.locate_method,
        ssn_last4=None,
        text_preview=preview,
    )


def apply_redactions(
    source_pdf: Path,
    located: list[LocatedRedaction],
    *,
    out_dir: Path | None = None,
) -> Path:
    """Write a visually redacted PDF beside the source (or under out_dir)."""
    source_pdf = source_pdf.resolve()
    output = redacted_output_path(source_pdf, out_dir=out_dir)

    with fitz.open(source_pdf) as doc:
        by_page: dict[int, list[LocatedRedaction]] = {}
        for item in located:
            by_page.setdefault(item.page, []).append(item)

        for page_num, items in by_page.items():
            page_index = page_num - 1
            if page_index < 0 or page_index >= doc.page_count:
                continue
            page = doc.load_page(page_index)
            for item in items:
                rect = fitz.Rect(item.x0, item.y0, item.x1, item.y1) & page.rect
                if rect.is_empty or rect.get_area() <= 0:
                    continue
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()

        doc.save(output, garbage=4, deflate=True)

    return output
