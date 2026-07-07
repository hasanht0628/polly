"""Offline classification fixture checks — no Ollama required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from classification.schemas import ClientTaxonomy, ProductClassification, ProductType
from classification.taxonomy import DEFAULT_ACCOUNT_TYPES, baseline_taxonomy, merge_taxonomies
from workflows.account_classification.map_classification import map_classification_to_package

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANUALS = PROJECT_ROOT / "fixtures/classification/manuals"
CONSUMER = PROJECT_ROOT / "fixtures/classification/consumer"

ACCOUNT_TYPES = {
    ProductType.credit_card,
    ProductType.personal_loan,
    ProductType.auto_loan,
    ProductType.student_loan,
    ProductType.mortgage,
    ProductType.heloc,
    ProductType.medical_bill,
    ProductType.bnpl,
    ProductType.telecom,
}


def test_product_type_enum_has_nine_account_types() -> None:
    assert len(ACCOUNT_TYPES) == 9
    assert ProductType.unknown not in ACCOUNT_TYPES


def test_baseline_taxonomy_covers_all_account_types() -> None:
    taxonomy = baseline_taxonomy()
    types = {rule.product_type for rule in taxonomy.product_types}
    assert types == ACCOUNT_TYPES


def test_merge_taxonomies_uses_client_keywords() -> None:
    client = ClientTaxonomy.model_validate_json(
        (MANUALS / "acme_taxonomy.json").read_text(encoding="utf-8")
    )
    merged = merge_taxonomies(client)
    credit_card = next(
        rule for rule in merged.product_types if rule.product_type == ProductType.credit_card
    )
    assert "Capital One" in credit_card.issuer_patterns
    assert len(merged.product_types) == len(DEFAULT_ACCOUNT_TYPES)


def test_merge_taxonomies_without_client_uses_baseline() -> None:
    merged = merge_taxonomies(None)
    assert len(merged.product_types) == len(DEFAULT_ACCOUNT_TYPES)


def test_manual_taxonomy_golden_valid() -> None:
    taxonomy = ClientTaxonomy.model_validate_json(
        (MANUALS / "acme_taxonomy.json").read_text(encoding="utf-8")
    )
    assert len(taxonomy.product_types) >= 9


@pytest.mark.parametrize(
    "golden_file,expected_type",
    [
        ("credit_card_classification.json", ProductType.credit_card),
        ("personal_loan_classification.json", ProductType.personal_loan),
        ("auto_loan_classification.json", ProductType.auto_loan),
        ("student_loan_classification.json", ProductType.student_loan),
        ("mortgage_classification.json", ProductType.mortgage),
        ("heloc_classification.json", ProductType.heloc),
        ("medical_bill_classification.json", ProductType.medical_bill),
        ("bnpl_classification.json", ProductType.bnpl),
        ("telecom_classification.json", ProductType.telecom),
    ],
)
def test_consumer_golden_classification(golden_file: str, expected_type: ProductType) -> None:
    golden = json.loads((CONSUMER / golden_file).read_text())
    result = ProductClassification.model_validate(golden)
    assert result.product_type == expected_type
    assert result.evidence_quotes


def test_map_classification_package_flags_low_confidence() -> None:
    classification = ProductClassification(
        client_id="acme",
        product_type=ProductType.credit_card,
        confidence="medium",
        evidence_quotes=["Credit Card Account"],
        needs_review=True,
    )
    package = map_classification_to_package(
        classification,
        pdf_path=CONSUMER / "credit_card_statement.txt",
        consumer_id="C-1",
    )
    assert package.needs_review
    assert package.account_type == ProductType.credit_card
    assert package.consumer_id == "C-1"
    assert any("confidence" in reason.lower() for reason in package.review_reasons)


def test_consumer_statement_mentions_credit_card() -> None:
    text = (CONSUMER / "credit_card_statement.txt").read_text(encoding="utf-8").lower()
    assert "credit card" in text
    assert "minimum payment" in text
