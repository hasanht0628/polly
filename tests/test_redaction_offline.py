"""Offline redaction checks — no Ollama required."""

from __future__ import annotations

import asyncio
from pathlib import Path

import fitz
import pytest

from evals.redaction.fixtures import (
    SYNTHETIC_ADDRESS,
    SYNTHETIC_NAME,
    SYNTHETIC_SSN,
    ensure_synthetic_fixtures,
)
from redaction.apply import apply_redactions, ssn_last4, to_entity_summary
from redaction.locate import locate_candidates
from redaction.paths import is_redacted_pdf, redacted_output_path, resolve_pdf_paths
from redaction.schemas import LocatedRedaction, PiiCandidate, PiiEntityType


def test_resolve_pdf_paths_skips_redacted(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    redacted = tmp_path / "doc.redacted.pdf"
    src.write_bytes(b"%PDF-1.4")
    redacted.write_bytes(b"%PDF-1.4")
    found = resolve_pdf_paths(tmp_path)
    assert found == [src.resolve()]
    assert is_redacted_pdf(redacted)


def test_redacted_output_path() -> None:
    src = Path("/tmp/sample.pdf")
    assert redacted_output_path(src).name == "sample.redacted.pdf"


def test_ssn_last4() -> None:
    assert ssn_last4("123-45-6789") == "6789"
    assert ssn_last4("xx") is None


def test_entity_summary_masks_ssn() -> None:
    item = LocatedRedaction(
        page=1,
        entity_type=PiiEntityType.ssn,
        text="123-45-6789",
        confidence="high",
        x0=0,
        y0=0,
        x1=10,
        y1=10,
        locate_method="search",
    )
    summary = to_entity_summary(item)
    assert summary.ssn_last4 == "6789"
    assert summary.text_preview is None


def test_locate_and_apply_removes_text_layer_pii(tmp_path: Path) -> None:
    pdf_path = ensure_synthetic_fixtures()
    # Copy into tmp so we don't leave a .redacted.pdf next to the committed fixture
    work = tmp_path / "synthetic_consumer.pdf"
    work.write_bytes(pdf_path.read_bytes())

    candidates = [
        PiiCandidate(entity_type=PiiEntityType.name, text=SYNTHETIC_NAME, page=1),
        PiiCandidate(entity_type=PiiEntityType.ssn, text=SYNTHETIC_SSN, page=1),
        PiiCandidate(entity_type=PiiEntityType.address, text=SYNTHETIC_ADDRESS, page=1),
    ]

    located = asyncio.run(locate_candidates(work, candidates))
    assert len(located) >= 3
    assert all(item.locate_method == "search" for item in located)

    out = apply_redactions(work, located, out_dir=tmp_path)
    assert out.is_file()

    with fitz.open(out) as doc:
        text = doc.load_page(0).get_text()
    assert SYNTHETIC_NAME not in text
    assert SYNTHETIC_SSN not in text
    assert "742 Evergreen" not in text


@pytest.mark.parametrize(
    "phrase",
    [SYNTHETIC_NAME, SYNTHETIC_SSN, "742 Evergreen"],
)
def test_synthetic_fixture_contains_pii(phrase: str) -> None:
    pdf_path = ensure_synthetic_fixtures()
    with fitz.open(pdf_path) as doc:
        text = doc.load_page(0).get_text()
    assert phrase in text
