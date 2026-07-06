from __future__ import annotations

from pathlib import Path
from typing import Any

from classification.extract_models import ExtractedProductClassification
from classification.schemas import (
    ClientTaxonomy,
    ManualCitation,
    ProductClassification,
    ProductType,
)
from pydantic_ai import NativeOutput

from court.extract import EXTRACT_MODEL_SETTINGS, EXTRACT_SYSTEM_PROMPT, _run_with_retries
from documents.schemas import ExtractResult
from documents.text import load_document_text
from tutorials.config import make_agent

CLASSIFICATION_PROMPT = """\
Classify this consumer document into exactly one product type using the client taxonomy and manual passages.

Product types: student_loan, credit_card, auto_loan, or unknown if none match.

Rules:
- Use only evidence from the consumer document for evidence_quotes.
- Cite which manual rules/sections support the classification in manual_citations.
- Set needs_review=true when confidence is not high or alternatives exist.
- List alternative_types when the document could plausibly match more than one product.
"""

classification_agent = make_agent(
    output_type=NativeOutput(ExtractedProductClassification),
    system_prompt=EXTRACT_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)


def _format_taxonomy_context(taxonomy: ClientTaxonomy) -> str:
    lines = [f"Client: {taxonomy.client_id}", "Product types:"]
    for rule in taxonomy.product_types:
        lines.append(
            f"- {rule.product_type.value}: {rule.definition}; keywords={rule.keywords}"
        )
    if taxonomy.rules:
        lines.append("Rules:")
        lines.extend(f"- {rule}" for rule in taxonomy.rules)
    return "\n".join(lines)


def _format_passages(passages: list[str]) -> str:
    if not passages:
        return "(no manual passages retrieved)"
    return "\n\n---\n\n".join(passages)


def _normalize_classification(
    client_id: str,
    raw: ExtractedProductClassification,
) -> ProductClassification:
    try:
        product_type = ProductType(raw.product_type.lower().replace(" ", "_"))
    except ValueError:
        product_type = ProductType.unknown

    alternatives: list[ProductType] = []
    for alt in raw.alternative_types:
        try:
            alternatives.append(ProductType(alt.lower().replace(" ", "_")))
        except ValueError:
            continue

    confidence = raw.confidence.lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    needs_review = raw.needs_review or confidence != "high" or product_type == ProductType.unknown

    return ProductClassification(
        client_id=client_id,
        product_type=product_type,
        confidence=confidence,
        evidence_quotes=raw.evidence_quotes,
        manual_citations=[
            ManualCitation(section=c.section, rule_text=c.rule_text)
            for c in raw.manual_citations
        ],
        needs_review=needs_review,
        alternative_types=alternatives,
    )


async def run_product_classification(
    pdf_path: Path,
    *,
    use_cache: bool = True,
    context: dict[str, Any] | None = None,
) -> ExtractResult:
    context = context or {}
    client_id = str(context.get("client_id", "unknown"))
    taxonomy: ClientTaxonomy | None = context.get("taxonomy")
    passages: list[str] = list(context.get("manual_passages") or [])

    document = await load_document_text(pdf_path, use_cache=use_cache)
    snippet = document.text[:8000]

    taxonomy_block = (
        _format_taxonomy_context(taxonomy) if taxonomy else "(no taxonomy provided)"
    )
    prompt = (
        CLASSIFICATION_PROMPT
        + f"\n\n{taxonomy_block}\n\nManual passages:\n{_format_passages(passages)}"
        + f"\n\nConsumer document:\n\n{snippet}"
    )

    raw = await _run_with_retries(
        classification_agent,
        prompt,
        is_empty=lambda data: data.product_type == "unknown" and not data.evidence_quotes,
    )
    classification = _normalize_classification(client_id, raw)
    return ExtractResult(
        profile_id="product_classification",
        data=classification,
        source_path=pdf_path,
        extraction_notes=list(raw.extraction_notes),
    )
