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

from agents.config import make_agent
from agents.extract_utils import EXTRACT_MODEL_SETTINGS, RunMetrics, run_with_retries
from documents.schemas import ExtractResult
from documents.text import load_document_text

CLASSIFICATION_SYSTEM_PROMPT = """\
You classify consumer account documents into exactly one firm account archetype.

You MUST return structured output. Put your decision in the structured fields, not in prose:
- product_type: EXACTLY one value from the allowed list. Choose the best match; only use "unknown"
  when no archetype has any supporting evidence in the document.
- evidence_quotes: 1-3 verbatim snippets copied from the consumer document that justify product_type.
  If you can identify a type, evidence_quotes MUST NOT be empty.
- confidence: "high" only when the evidence is clear and unambiguous; otherwise "medium" or "low".
- extraction_notes: optional caveats ONLY. Never put your main answer or reasoning here instead of
  product_type / evidence_quotes.
- Set needs_review=true when confidence is not high, the type is unknown, or alternatives exist.
- List alternative_types when the document could plausibly match more than one archetype.
"""

CLASSIFICATION_PROMPT = f"""\
Classify this consumer document into exactly one account archetype using the taxonomy and manual passages.

Account types: {ACCOUNT_TYPE_LIST}

Disambiguation hints:
- lending_point vs fintech: use lending_point when LendingPoint is named as issuer/originator.
- auto_deficiency: any auto/vehicle-secured account that has gone bad. Signals include a vehicle
  or VIN as collateral, a motor-vehicle retail installment / purchase contract, dealer recourse,
  a charge-off, a returned/NSF down payment, or repossession/deficiency language. Repossession is
  ONE signal, not a requirement — "no repossession yet", "pre-recovery review", or a charged-off
  auto contract still classify as auto_deficiency, NOT other.
- retail_installments vs credit_card: retail/BNPL checkout plans and store financing → retail_installments; revolving card accounts → credit_card. A MOTOR-VEHICLE installment contract is auto_deficiency, not retail_installments.
- fintech vs retail_installments: online/marketplace personal loans → fintech; merchant installment contracts → retail_installments.
- student_loan: education debt, deferment, forbearance, federal/private student servicers.
- other: use ONLY when the document is clearly debt but fits none of the named archetypes.

How to answer:
1. Scan the document for keywords from each archetype in the taxonomy.
2. Pick the single archetype with the strongest keyword/context support and set product_type to it.
3. Copy 1-3 exact phrases from the document into evidence_quotes.

Example: a document containing "Credit Card Statement", "Minimum Payment", and "APR" should return
product_type="credit_card" with evidence_quotes=["Credit Card Statement", "Minimum Payment"].

Rules:
- If the case context provides `archetype_candidates`, an upstream officer-code lookup already
  narrowed this account to those archetypes. Choose the best-fitting candidate. Only pick a type
  outside that list (or "other") when the document clearly contradicts every candidate. Never
  return "other" when a listed candidate has any supporting evidence in the document — put the
  weaker candidate in alternative_types instead.
- Ignore any "SYNTHETIC / SAMPLE / FICTIONAL / not a real document" banners. Classify from the
  account content as if it were real; such banners are never a reason to return "other".
- Use only evidence from the consumer document for evidence_quotes.
- Cite which manual rules/sections support the classification in manual_citations.
- Set needs_review=true when confidence is not high or alternatives exist.
- List alternative_types when the document could plausibly match more than one archetype.
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


def _normalize_product_type(raw: str) -> ProductType:
    cleaned = raw.lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "personal_loan": ProductType.fintech,
        "auto_loan": ProductType.auto_deficiency,
        "bnpl": ProductType.retail_installments,
        "telecom": ProductType.other,
        "mortgage": ProductType.other,
        "heloc": ProductType.other,
        "medical_bill": ProductType.other,
    }
    if cleaned in aliases:
        return aliases[cleaned]
    try:
        return ProductType(cleaned)
    except ValueError:
        return ProductType.unknown


def _normalize_classification(
    client_id: str,
    raw: ExtractedProductClassification,
) -> ProductClassification:
    product_type = _normalize_product_type(raw.product_type)

    alternatives: list[ProductType] = []
    for alt in raw.alternative_types:
        normalized = _normalize_product_type(alt)
        if normalized != ProductType.unknown and normalized not in alternatives:
            alternatives.append(normalized)

    confidence = raw.confidence.lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    # Map unresolved unknown → other + review for firm-facing packages.
    if product_type == ProductType.unknown:
        product_type = ProductType.other
        needs_review = True
    else:
        needs_review = raw.needs_review or confidence != "high"

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
    extra_context: str = "",
    metrics: RunMetrics | None = None,
) -> tuple[ProductClassification, list[str]]:
    merged = merge_taxonomies(taxonomy)
    merged.client_id = client_id
    snippet = doc_text[:8000]
    prompt = (
        CLASSIFICATION_PROMPT
        + f"\n\n{_format_taxonomy_context(merged)}\n\nManual passages:\n{_format_passages(passages or [])}"
    )
    if extra_context:
        prompt += f"\n\nAdditional case context:\n{extra_context}"
    prompt += f"\n\nConsumer document:\n\n{snippet}"
    raw = await run_with_retries(
        classification_agent,
        prompt,
        is_empty=lambda data: data.product_type in {"unknown", "other"}
        and not data.evidence_quotes,
        metrics=metrics,
    )
    return _normalize_classification(client_id, raw), list(raw.extraction_notes)


async def classify_from_ocr_file(
    ocr_path: Path,
    *,
    client_id: str = "baseline",
    taxonomy: ClientTaxonomy | None = None,
    passages: list[str] | None = None,
    metrics: RunMetrics | None = None,
) -> ProductClassification:
    text = ocr_path.read_text(encoding="utf-8")
    classification, _ = await _classify_document_text(
        text,
        client_id=client_id,
        taxonomy=taxonomy,
        passages=passages,
        metrics=metrics,
    )
    return classification


async def classify_document_text(
    doc_text: str,
    *,
    client_id: str = "baseline",
    taxonomy: ClientTaxonomy | None = None,
    passages: list[str] | None = None,
    extra_context: str = "",
    metrics: RunMetrics | None = None,
) -> ProductClassification:
    classification, _ = await _classify_document_text(
        doc_text,
        client_id=client_id,
        taxonomy=taxonomy,
        passages=passages,
        extra_context=extra_context,
        metrics=metrics,
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
    extra_context = str(context.get("extra_context") or "")

    taxonomy = merge_taxonomies(raw_taxonomy)
    if raw_taxonomy is None:
        taxonomy.client_id = client_id

    document = await load_document_text(pdf_path, use_cache=use_cache)
    classification, notes = await _classify_document_text(
        document.text,
        client_id=client_id,
        taxonomy=raw_taxonomy,
        passages=passages,
        extra_context=extra_context,
    )
    return ExtractResult(
        profile_id="product_classification",
        data=classification,
        source_path=pdf_path,
        extraction_notes=notes,
    )
