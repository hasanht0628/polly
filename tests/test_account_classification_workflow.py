from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agents.audit import AuditLog
from agents.registry import WorkflowName, tools_for
from classification.schemas import ManualCitation, ProductClassification, ProductType
from workflows.account_classification.run import run_account_classification_from_pdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent


async def _run_workflow(tmp_path: Path):
    pdf_path = PROJECT_ROOT / "fixtures/classification/consumer/credit_card_statement.txt"
    classification = ProductClassification(
        client_id="acme",
        product_type=ProductType.credit_card,
        confidence="high",
        evidence_quotes=["Credit Card Account ending in 4321"],
        manual_citations=[
            ManualCitation(section="CREDIT CARD", rule_text="Keywords: credit card")
        ],
        needs_review=False,
    )
    audit = AuditLog(tmp_path / "workflow.db")

    with (
        patch(
            "workflows.account_classification.run.load_document_text",
            new_callable=AsyncMock,
            return_value=type(
                "Doc",
                (),
                {"text": "Credit Card Account ending in 4321\nMinimum Payment Due"},
            )(),
        ),
        patch(
            "workflows.account_classification.run.extract_document",
            new_callable=AsyncMock,
            return_value=type(
                "Result",
                (),
                {"data": classification, "extraction_notes": []},
            )(),
        ),
    ):
        return await run_account_classification_from_pdf(
            "acme",
            pdf_path,
            consumer_id="C-99",
            use_cache=False,
            audit=audit,
            knowledge_root=tmp_path / "knowledge",
        )


def test_account_classification_workflow_wiring(tmp_path: Path) -> None:
    package = asyncio.run(_run_workflow(tmp_path))

    assert package.account_type == ProductType.credit_card
    assert package.consumer_id == "C-99"
    assert package.client_id == "acme"
    assert not package.needs_review

    audit = AuditLog(tmp_path / "workflow.db")
    loaded = audit.get_run(package.run_id)
    assert loaded is not None
    assert loaded.workflow_type == "account_classification"
    tool_names = [entry["tool"] for entry in loaded.tool_log]
    assert tool_names == [
        "load_document_text",
        "load_taxonomy",
        "retrieve_manual_passages",
        "extract_document",
        "map_classification",
    ]


def test_tool_registry_account_classification_workflow() -> None:
    tools = tools_for(WorkflowName.account_classification)
    assert "map_classification" in tools
    assert "format_classification_output" in tools
