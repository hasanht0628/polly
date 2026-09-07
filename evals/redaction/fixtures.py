"""Build synthetic redaction fixtures (fake PII, safe to commit)."""

from __future__ import annotations

from pathlib import Path

import fitz

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Fake PII for tests only — not real people.
SYNTHETIC_NAME = "Jane Q. Public"
SYNTHETIC_SSN = "123-45-6789"
SYNTHETIC_ADDRESS = "742 Evergreen Terrace, Springfield, IL 62704"

SYNTHETIC_BODY = f"""Consumer Information Form

Name: {SYNTHETIC_NAME}
SSN: {SYNTHETIC_SSN}
Address: {SYNTHETIC_ADDRESS}

Account reference: ACCT-0000
"""


def synthetic_pdf_path() -> Path:
    return FIXTURES_DIR / "synthetic_consumer.pdf"


def synthetic_ocr_path() -> Path:
    return synthetic_pdf_path().with_name("synthetic_consumer.ocr.txt")


def ensure_synthetic_fixtures() -> Path:
    """Create text-layer PDF + OCR sidecar if missing; return PDF path."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = synthetic_pdf_path()
    ocr_path = synthetic_ocr_path()

    if not pdf_path.is_file():
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        # insert_text keeps a searchable text layer for page.search_for
        y = 72
        for line in SYNTHETIC_BODY.strip().splitlines():
            page.insert_text((72, y), line, fontsize=12, fontname="helv")
            y += 18
        doc.save(pdf_path)
        doc.close()

    ocr_text = f"--- Page 1 ---\n{SYNTHETIC_BODY.strip()}\n"
    if not ocr_path.is_file() or ocr_path.read_text(encoding="utf-8") != ocr_text:
        ocr_path.write_text(ocr_text, encoding="utf-8")

    return pdf_path
