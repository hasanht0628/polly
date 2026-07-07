from __future__ import annotations

import json
from pathlib import Path

from agents.audit import AuditLog, WorkflowRun
from classification.schemas import ClientTaxonomy, ProductClassification
from classification.taxonomy import merge_taxonomies
from court.pdf_text import ocr_cache_path
from documents.profiles.registry import extract_document
from documents.text import load_document_text
from knowledge.client_manuals.store import DEFAULT_ROOT, load_taxonomy, retrieve_manual_passages
from workflows.account_classification.map_classification import map_classification_to_package
from workflows.schemas import AccountClassificationPackage


def _load_client_taxonomy(client_id: str, *, root: Path = DEFAULT_ROOT) -> ClientTaxonomy | None:
    try:
        return load_taxonomy(client_id, root=root)
    except FileNotFoundError:
        return None


async def run_account_classification_from_pdf(
    client_id: str,
    pdf_path: Path,
    *,
    consumer_id: str | None = None,
    use_cache: bool = True,
    audit: AuditLog | None = None,
    run: WorkflowRun | None = None,
    knowledge_root: Path = DEFAULT_ROOT,
) -> AccountClassificationPackage:
    audit = audit or AuditLog()
    owns_run = run is None
    if run is None:
        run = audit.start_run(
            "account_classification",
            {
                "client_id": client_id,
                "consumer_id": consumer_id,
                "pdf_path": str(pdf_path),
            },
        )

    pdf_path = pdf_path.resolve()
    audit.log_tool(
        run,
        "load_document_text",
        {"pdf_path": str(pdf_path), "use_cache": use_cache},
    )
    document = await load_document_text(pdf_path, use_cache=use_cache)

    audit.log_tool(run, "load_taxonomy", {"client_id": client_id})
    client_taxonomy = _load_client_taxonomy(client_id, root=knowledge_root)
    taxonomy = merge_taxonomies(client_taxonomy)
    taxonomy.client_id = client_id

    audit.log_tool(
        run,
        "retrieve_manual_passages",
        {"client_id": client_id, "query_chars": min(len(document.text), 4000)},
    )
    passages = retrieve_manual_passages(
        client_id,
        document.text[:4000],
        root=knowledge_root,
    )

    audit.log_tool(
        run,
        "extract_document",
        {"pdf_path": str(pdf_path), "profile": "product_classification"},
    )
    result = await extract_document(
        pdf_path,
        profile="product_classification",
        use_cache=use_cache,
        context={
            "client_id": client_id,
            "taxonomy": taxonomy,
            "manual_passages": passages,
        },
    )
    classification: ProductClassification = result.data

    audit.log_tool(
        run,
        "map_classification",
        {
            "account_type": classification.product_type.value,
            "needs_review": classification.needs_review,
        },
    )
    package = map_classification_to_package(
        classification,
        pdf_path=pdf_path,
        consumer_id=consumer_id,
        ocr_cache_path=ocr_cache_path(pdf_path),
        run_id=run.run_id,
    )

    if owns_run:
        audit.complete_run(run, json.loads(package.model_dump_json()))
    return package


def format_classification_output(
    package: AccountClassificationPackage,
    *,
    pretty: bool = False,
) -> str:
    indent = 2 if pretty else None
    return package.model_dump_json(indent=indent)
