from __future__ import annotations

import json
from pathlib import Path

from agents.audit import AuditLog, WorkflowRun
from court.schemas import CaseExtraction
from documents.download import PdfStore
from documents.profiles.registry import extract_document
from workflows.court_calendar.map_extraction import map_extraction_to_review_package
from workflows.intake.email_parser import parse_eml
from workflows.schemas import IntakeEmail, ReviewPackage


def _build_package(
    pdf_path: Path,
    extraction: CaseExtraction,
    *,
    email: IntakeEmail | None,
    run_id: str | None,
) -> ReviewPackage:
    return map_extraction_to_review_package(
        extraction,
        pdf_path=pdf_path.resolve(),
        email_subject=email.subject if email else None,
        email_sender=email.sender if email else None,
        run_id=run_id,
    )


async def run_court_workflow_from_pdf(
    pdf_path: Path,
    *,
    use_cache: bool = True,
    audit: AuditLog | None = None,
    run: WorkflowRun | None = None,
    email: IntakeEmail | None = None,
) -> ReviewPackage:
    audit = audit or AuditLog()
    owns_run = run is None
    if run is None:
        run = audit.start_run(
            "court_doc_scheduling",
            {"pdf_path": str(pdf_path), "email_subject": email.subject if email else None},
        )

    pdf_path = pdf_path.resolve()
    audit.log_tool(run, "extract_document", {"pdf_path": str(pdf_path), "profile": "court_calendar"})

    result = await extract_document(
        pdf_path,
        profile="court_calendar",
        use_cache=use_cache,
    )
    extraction: CaseExtraction = result.data

    package = _build_package(pdf_path, extraction, email=email, run_id=run.run_id)
    audit.log_tool(run, "propose_calendar_items", {"event_count": len(package.schedulable_events)})

    if owns_run:
        audit.complete_run(run, json.loads(package.model_dump_json()))
    return package


async def run_court_workflow_from_email(
    eml_path: Path,
    *,
    use_cache: bool = True,
    audit: AuditLog | None = None,
    pdf_store: PdfStore | None = None,
) -> ReviewPackage:
    audit = audit or AuditLog()
    pdf_store = pdf_store or PdfStore(Path("data/downloads"))

    email = parse_eml(eml_path)
    run = audit.start_run(
        "court_doc_scheduling",
        {"eml_path": str(eml_path), "pdf_urls": email.pdf_urls},
    )
    audit.log_tool(run, "parse_court_email", {"pdf_url_count": len(email.pdf_urls)})

    if email.pdf_urls:
        pdf_path = await pdf_store.download(email.pdf_urls[0])
        audit.log_tool(run, "download_document", {"url": email.pdf_urls[0], "path": str(pdf_path)})
    elif email.attachment_paths:
        pdf_path = pdf_store.resolve_local(email.attachment_paths[0])
    else:
        audit.complete_run(run, {"error": "no pdf found"}, status="failed")
        raise ValueError("No PDF URL or attachment found in email")

    package = await run_court_workflow_from_pdf(
        pdf_path,
        use_cache=use_cache,
        audit=audit,
        run=run,
        email=email,
    )
    audit.complete_run(run, json.loads(package.model_dump_json()))
    return package


def format_scheduling_output(package: ReviewPackage, *, pretty: bool = False) -> str:
    indent = 2 if pretty else None
    return package.model_dump_json(indent=indent)
