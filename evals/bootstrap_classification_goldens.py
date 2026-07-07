#!/usr/bin/env python3
"""Bootstrap classification OCR goldens, classification goldens, and cases.yaml."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import fitz
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from classification.schemas import ClientTaxonomy, ProductClassification
from classification.taxonomy import merge_taxonomies
from documents.profiles.product_classification import classify_from_ocr_file
from documents.text import load_document_text
from knowledge.client_manuals.store import retrieve_manual_passages

EVALS_DIR = Path(__file__).resolve().parent
CLASSIFICATION_DIR = EVALS_DIR / "classification"
MANIFEST_PATH = CLASSIFICATION_DIR / "manifest.yaml"
CASES_PATH = CLASSIFICATION_DIR / "cases.yaml"
OCR_GOLDENS = CLASSIFICATION_DIR / "goldens"
CLASSIFICATION_GOLDENS = CLASSIFICATION_DIR / "goldens"
CLIENT_ID = "acme"


def _pdf_to_page_text(pdf_path: Path) -> str:
    """Format embedded PDF text like OCR sidecars (--- Page N --- blocks)."""
    doc = fitz.open(pdf_path)
    sections: list[str] = []
    for index, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        sections.append(f"--- Page {index} ---\n{text}")
    return "\n\n".join(sections) + "\n"


async def _ocr_pdf_text(pdf_path: Path, *, use_ocr: bool) -> str:
    if use_ocr:
        document = await load_document_text(pdf_path, use_cache=True)
        return document.text
    return _pdf_to_page_text(pdf_path)


def _load_manifest() -> list[dict]:
    raw = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    return list(raw.get("cases", []))


def _load_taxonomy() -> ClientTaxonomy:
    path = PROJECT_ROOT / "fixtures/classification/manuals/acme_taxonomy.json"
    client = (
        ClientTaxonomy.model_validate_json(path.read_text(encoding="utf-8"))
        if path.is_file()
        else None
    )
    taxonomy = merge_taxonomies(client)
    taxonomy.client_id = CLIENT_ID
    return taxonomy


async def bootstrap_case(entry: dict, *, use_ocr: bool, write_classification: bool) -> dict:
    OCR_GOLDENS.mkdir(parents=True, exist_ok=True)
    slug = str(entry["slug"])
    pdf_path = PROJECT_ROOT / str(entry["pdf"])
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    ocr_golden = OCR_GOLDENS / f"{slug}.ocr.txt"
    if not ocr_golden.is_file() or use_ocr:
        ocr_golden.write_text(await _ocr_pdf_text(pdf_path, use_ocr=use_ocr), encoding="utf-8")
        print(f"OCR golden: {ocr_golden}")
    else:
        print(f"OCR golden exists: {ocr_golden}")

    classification_golden = CLASSIFICATION_GOLDENS / f"{slug}.json"
    ocr_text = ocr_golden.read_text(encoding="utf-8")
    taxonomy = _load_taxonomy()
    passages = retrieve_manual_passages(
        CLIENT_ID,
        ocr_text[:4000],
        root=PROJECT_ROOT / "knowledge/client_manuals",
    )

    if write_classification:
        classification: ProductClassification = await classify_from_ocr_file(
            ocr_golden,
            client_id=CLIENT_ID,
            taxonomy=taxonomy,
            passages=passages,
        )
        classification_golden.write_text(
            classification.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Classification golden: {classification_golden}")
    elif classification_golden.is_file():
        print(f"Classification golden exists: {classification_golden}")

    evidence_phrases = list(entry.get("evidence_phrases") or [])
    if not evidence_phrases and classification_golden.is_file():
        golden = json.loads(classification_golden.read_text(encoding="utf-8"))
        evidence_phrases = list(golden.get("evidence_quotes") or [])[:3]

    return {
        "slug": slug,
        "pdf_path": str(Path(entry["pdf"]).as_posix()),
        "ocr_fixture": str(ocr_golden.relative_to(PROJECT_ROOT).as_posix()),
        "classification_golden_path": str(
            classification_golden.relative_to(PROJECT_ROOT).as_posix()
        ),
        "client_id": CLIENT_ID,
        "expected_product_type": str(entry["expected_product_type"]),
        "evidence_phrases": evidence_phrases,
    }


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap classification eval goldens")
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Run live olmocr2 OCR instead of embedded PDF text (slow)",
    )
    parser.add_argument(
        "--skip-classify",
        action="store_true",
        help="Only write OCR goldens; do not run classification LLM",
    )
    args = parser.parse_args()

    entries = []
    for item in _load_manifest():
        entries.append(
            await bootstrap_case(
                item,
                use_ocr=args.ocr,
                write_classification=not args.skip_classify,
            )
        )

    CASES_PATH.write_text(
        yaml.safe_dump({"cases": entries}, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Wrote {CASES_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
