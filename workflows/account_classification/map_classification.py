from __future__ import annotations

from pathlib import Path

from classification.schemas import ProductClassification, ProductType
from workflows.schemas import AccountClassificationPackage


def _review_reasons(classification: ProductClassification) -> list[str]:
    reasons: list[str] = []
    if classification.product_type in {ProductType.unknown, ProductType.other} and not classification.evidence_quotes:
        reasons.append("Account type could not be determined from the document")
    elif classification.product_type == ProductType.unknown:
        reasons.append("Account type could not be determined from the document")
    if classification.confidence != "high":
        reasons.append(f"Classification confidence is {classification.confidence}")
    if classification.alternative_types:
        alts = ", ".join(t.value for t in classification.alternative_types)
        reasons.append(f"Alternative account types considered: {alts}")
    if classification.needs_review and not reasons:
        reasons.append("Classifier flagged this document for human review")
    return reasons


def map_classification_to_package(
    classification: ProductClassification,
    *,
    pdf_path: Path,
    consumer_id: str | None = None,
    ocr_cache_path: Path | None = None,
    run_id: str | None = None,
) -> AccountClassificationPackage:
    reasons = _review_reasons(classification)
    needs_review = classification.needs_review or bool(reasons)

    return AccountClassificationPackage(
        client_id=classification.client_id,
        consumer_id=consumer_id,
        account_type=classification.product_type,
        confidence=classification.confidence,
        needs_review=needs_review,
        review_reasons=reasons,
        evidence_quotes=list(classification.evidence_quotes),
        manual_citations=list(classification.manual_citations),
        alternative_types=list(classification.alternative_types),
        classification=classification,
        source_pdf_path=pdf_path.resolve(),
        ocr_cache_path=ocr_cache_path,
        run_id=run_id,
    )
