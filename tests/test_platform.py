from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.audit import AuditLog
from agents.registry import WorkflowName, tools_for
from classification.schemas import ClientTaxonomy, ProductType
from documents.profiles.registry import list_profiles
from knowledge.client_manuals.store import _chunk_manual, load_taxonomy, retrieve_manual_passages

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_extract_profiles_registered() -> None:
    profiles = list_profiles()
    assert "court_calendar" in profiles
    assert "client_manual_taxonomy" in profiles
    assert "product_classification" in profiles


def test_tool_registry_court_workflow() -> None:
    tools = tools_for(WorkflowName.court_doc_scheduling)
    assert "propose_calendar_items" in tools
    assert "create_calendar_events" not in tools


def test_audit_log_roundtrip(tmp_path: Path) -> None:
    audit = AuditLog(tmp_path / "test.db")
    run = audit.start_run("court_doc_scheduling", {"pdf": "x.pdf"})
    audit.log_tool(run, "extract_document", {"profile": "court_calendar"})
    audit.complete_run(run, {"ok": True})
    loaded = audit.get_run(run.run_id)
    assert loaded is not None
    assert loaded.status == "completed"
    assert len(loaded.tool_log) == 1


def test_manual_chunking() -> None:
    text = (PROJECT_ROOT / "fixtures/classification/manuals/acme_manual.txt").read_text()
    chunks = _chunk_manual(text)
    assert len(chunks) >= 1


def test_load_acme_taxonomy_golden() -> None:
    path = PROJECT_ROOT / "fixtures/classification/manuals/acme_taxonomy.json"
    taxonomy = ClientTaxonomy.model_validate_json(path.read_text(encoding="utf-8"))
    assert taxonomy.client_id == "acme"
    types = {rule.product_type for rule in taxonomy.product_types}
    assert ProductType.credit_card in types


def test_retrieve_manual_passages_prefers_credit_card(tmp_path: Path) -> None:
    client_dir = tmp_path / "acme"
    client_dir.mkdir()
    manual = (PROJECT_ROOT / "fixtures/classification/manuals/acme_manual.txt").read_text()
    chunks = _chunk_manual(manual)
    (client_dir / "chunks.json").write_text(
        json.dumps([{"section": c.section, "text": c.text} for c in chunks]),
        encoding="utf-8",
    )
    taxonomy = ClientTaxonomy.model_validate_json(
        (PROJECT_ROOT / "fixtures/classification/manuals/acme_taxonomy.json").read_text()
    )
    (client_dir / "taxonomy.json").write_text(taxonomy.model_dump_json(), encoding="utf-8")

    query = (PROJECT_ROOT / "fixtures/classification/consumer/credit_card_statement.txt").read_text()
    passages = retrieve_manual_passages("acme", query, root=tmp_path)
    assert passages
    assert "credit card" in passages[0].lower() or any("credit card" in p.lower() for p in passages)


def test_consumer_classification_golden_shape() -> None:
    path = PROJECT_ROOT / "fixtures/classification/consumer/credit_card_classification.json"
    data = json.loads(path.read_text())
    assert data["product_type"] == "credit_card"
    assert data["evidence_quotes"]
