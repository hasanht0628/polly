"""Offline classification fixture checks — no Ollama required."""

from __future__ import annotations

import json
from pathlib import Path

from classification.schemas import ClientTaxonomy, ProductClassification, ProductType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANUALS = PROJECT_ROOT / "fixtures/classification/manuals"
CONSUMER = PROJECT_ROOT / "fixtures/classification/consumer"


def test_manual_taxonomy_golden_valid() -> None:
    taxonomy = ClientTaxonomy.model_validate_json(
        (MANUALS / "acme_taxonomy.json").read_text(encoding="utf-8")
    )
    assert len(taxonomy.product_types) >= 3


def test_consumer_golden_classification() -> None:
    golden = json.loads((CONSUMER / "credit_card_classification.json").read_text())
    result = ProductClassification.model_validate(golden)
    assert result.product_type == ProductType.credit_card
    assert not result.needs_review


def test_consumer_statement_mentions_credit_card() -> None:
    text = (CONSUMER / "credit_card_statement.txt").read_text(encoding="utf-8").lower()
    assert "credit card" in text
    assert "minimum payment" in text
