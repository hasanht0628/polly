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
from classification.taxonomy import ACCOUNT_TYPE_LIST, merge_taxonomies
from pydantic_ai import NativeOutput

from court.extract import EXTRACT_MODEL_SETTINGS, _run_with_retries
from documents.schemas import ExtractResult
from documents.text import load_document_text
from tutorials.config import make_agent

CLASSIFICATION_SYSTEM_PROMPT = """\
You classify consumer account documents into exactly one account type for a collections workflow.

You MUST return structured output. Put your decision in the structured fields, not in prose:
- product_type: EXACTLY one value from the allowed list. Choose the best match; only use "unknown"
  when no account type has any supporting evidence in the document.
- evidence_quotes: 1-3 verbatim snippets copied from the consumer document that justify product_type.
  If you can identify a type, evidence_quotes MUST NOT be empty.
- confidence: "high" only when the evidence is clear and unambiguous; otherwise "medium" or "low".
- extraction_notes: optional caveats ONLY. Never put your main answer or reasoning here instead of
  product_type / evidence_quotes.
- Set needs_review=true when confidence is not high, the type is unknown, or alternatives exist.
- List alternative_types when the document could plausibly match more than one account type.
"""

CLASSIFICATION_PROMPT = f"""\
Classify this consumer document into exactly one account type using the taxonomy and manual passages.

Account types: {ACCOUNT_TYPE_LIST}

Disambiguation hints:
- personal_loan vs auto_loan: auto loans mention VIN, vehicle collateral, or motor vehicle.
- mortgage vs heloc: mortgages are first-lien home loans with escrow/principal; HELOCs are revolving lines secured by home equity with draw periods.
- medical_bill vs credit_card: medical bills reference providers, hospitals, patients, or CPT codes.
- bnpl vs credit_card: BNPL mentions merchant checkout installments (Affirm, Klarna, pay in 4).
- telecom vs credit_card: telecom bills reference wireless plans, carriers, data, or minutes.

How to answer:
1. Scan the document for keywords from each account type in the taxonomy.
2. Pick the single account type with the strongest keyword/context support and set product_type to it.
3. Copy 1-3 exact phrases from the document into evidence_quotes.

Example: a document containing "Credit Card Statement", "Minimum Payment", and "APR" should return
product_type="credit_card" with evidence_quotes=["Credit Card Statement", "Minimum Payment"].

Rules:
- Use only evidence from the consumer document for evidence_quotes.
- Cite which manual rules/sections support the classification in manual_citations.
- Set needs_review=true when confidence is not high or alternatives exist.
- List alternative_types when the document could plausibly match more than one account type.
"""

classification_agent = make_agent(
    output_type=NativeOutput(ExtractedProductClassification),
    system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)


def _format_taxonomy_context(taxonomy: ClientTaxonomy) -> str:
    lines = [f"Client: {taxonomy.client_id}", "Account types:"]
    for rule in taxonomy.product_types:
        lines.append(
            f"- {rule.product_type.value}: {rule.definition}; keywords={rule.keywords}"
        )
    if taxonomy.rules:
        lines.append("Rules:")
        lines.extend(f"- {rule}" for rule in taxonomy.rules)
    return "\n".join(lines)


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


def _format_passages(passages: list[str]) -> str:
    if not passages:
        return "(no manual passages retrieved)"
    return "\n\n---\n\n".join(passages)


async def _classify_document_text(
    doc_text: str,
    *,
    client_id: str,
    taxonomy: ClientTaxonomy | None = None,
    passages: list[str] | None = None,
) -> tuple[ProductClassification, list[str]]:
    merged = merge_taxonomies(taxonomy)
    merged.client_id = client_id
    snippet = doc_text[:8000]
    prompt = (
        CLASSIFICATION_PROMPT
        + f"\n\n{_format_taxonomy_context(merged)}\n\nManual passages:\n{_format_passages(passages or [])}"
        + f"\n\nConsumer document:\n\n{snippet}"
    )
    raw = await _run_with_retries(
        classification_agent,
        prompt,
        is_empty=lambda data: data.product_type == "unknown" and not data.evidence_quotes,
    )
    return _normalize_classification(client_id, raw), list(raw.extraction_notes)


async def classify_from_ocr_file(
    ocr_path: Path,
    *,
    client_id: str = "baseline",
    taxonomy: ClientTaxonomy | None = None,
    passages: list[str] | None = None,
) -> ProductClassification:
    text = ocr_path.read_text(encoding="utf-8")
    classification, _ = await _classify_document_text(
        text,
        client_id=client_id,
        taxonomy=taxonomy,
        passages=passages,
    )
    return classification


async def run_product_classification(
    pdf_path: Path,
    *,
    use_cache: bool = True,
    context: dict[str, Any] | None = None,
) -> ExtractResult:
    context = context or {}
    client_id = str(context.get("client_id", "unknown"))
    raw_taxonomy: ClientTaxonomy | None = context.get("taxonomy")
    passages: list[str] = list(context.get("manual_passages") or [])

    taxonomy = merge_taxonomies(raw_taxonomy)
    if raw_taxonomy is None:
        taxonomy.client_id = client_id

    document = await load_document_text(pdf_path, use_cache=use_cache)
    classification, notes = await _classify_document_text(
        document.text,
        client_id=client_id,
        taxonomy=raw_taxonomy,
        passages=passages,
    )
    return ExtractResult(
        profile_id="product_classification",
        data=classification,
        source_path=pdf_path,
        extraction_notes=notes,
    )
