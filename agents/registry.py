from __future__ import annotations

from enum import Enum


class WorkflowName(str, Enum):
    court_doc_scheduling = "court_doc_scheduling"
    product_classification = "product_classification"
    account_classification = "account_classification"
    portfolio_classification = "portfolio_classification"


TOOL_SETS: dict[WorkflowName, tuple[str, ...]] = {
    WorkflowName.court_doc_scheduling: (
        "parse_court_email",
        "download_document",
        "load_document_text",
        "extract_document",
        "propose_calendar_items",
        "format_scheduling_output",
    ),
    WorkflowName.product_classification: (
        "load_document_text",
        "ingest_client_manual",
        "retrieve_manual_passages",
        "extract_document",
    ),
    WorkflowName.account_classification: (
        "load_document_text",
        "load_taxonomy",
        "retrieve_manual_passages",
        "extract_document",
        "map_classification",
        "format_classification_output",
    ),
    WorkflowName.portfolio_classification: (
        "parse_dat",
        "resolve_codes",
        "locate_pdfs",
        "ambiguous_classify",
        "assemble_batch",
        "format_portfolio_output",
    ),
}


def tools_for(workflow: WorkflowName) -> tuple[str, ...]:
    return TOOL_SETS[workflow]
