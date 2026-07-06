from __future__ import annotations

from pathlib import Path
from typing import Any

from classification.extract_models import ExtractedClientTaxonomy
from classification.schemas import ClientTaxonomy, FieldDefinition, ProductType, ProductTypeRule
from pydantic_ai import NativeOutput

from court.extract import EXTRACT_MODEL_SETTINGS, EXTRACT_SYSTEM_PROMPT, _run_with_retries
from documents.schemas import ExtractResult
from documents.text import load_document_text
from tutorials.config import make_agent

TAXONOMY_PROMPT = """\
Extract the client's product type taxonomy and classification rules from this client manual.

Include each product type (student loan, credit card, auto loan, etc.) with:
- definition as written or summarized from the manual
- keywords and issuer patterns that identify that product
- example document descriptions if present

Also extract field definitions and data classification labels the client uses.
Output only what is explicitly stated or clearly implied in the manual.
"""

taxonomy_agent = make_agent(
    output_type=NativeOutput(ExtractedClientTaxonomy),
    system_prompt=EXTRACT_SYSTEM_PROMPT,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)


def _normalize_taxonomy(
    client_id: str,
    raw: ExtractedClientTaxonomy,
    *,
    source_path: Path,
) -> ClientTaxonomy:
    product_types: list[ProductTypeRule] = []
    for item in raw.product_types:
        try:
            ptype = ProductType(item.product_type.lower().replace(" ", "_"))
        except ValueError:
            ptype = ProductType.unknown
        if ptype == ProductType.unknown:
            continue
        product_types.append(
            ProductTypeRule(
                product_type=ptype,
                definition=item.definition or "",
                keywords=item.keywords,
                issuer_patterns=item.issuer_patterns,
                example_descriptions=item.example_descriptions,
            )
        )
    return ClientTaxonomy(
        client_id=client_id,
        product_types=product_types,
        field_definitions=[
            FieldDefinition(
                name=f.name,
                description=f.description,
                data_classification=f.data_classification,
            )
            for f in raw.field_definitions
        ],
        rules=raw.rules,
        source_manual_path=str(source_path),
    )


async def run_client_manual_taxonomy(
    pdf_path: Path,
    *,
    use_cache: bool = True,
    context: dict[str, Any] | None = None,
) -> ExtractResult:
    context = context or {}
    client_id = str(context.get("client_id", pdf_path.stem))
    document = await load_document_text(pdf_path, use_cache=use_cache)
    snippet = document.text[:12000]
    raw = await _run_with_retries(
        taxonomy_agent,
        TAXONOMY_PROMPT + f"\n\nClient manual:\n\n{snippet}",
        is_empty=lambda data: len(data.product_types) == 0 and len(data.rules) == 0,
    )
    taxonomy = _normalize_taxonomy(client_id, raw, source_path=pdf_path)
    return ExtractResult(
        profile_id="client_manual_taxonomy",
        data=taxonomy,
        source_path=pdf_path,
        extraction_notes=list(raw.extraction_notes),
    )
