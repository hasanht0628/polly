"""Workflow supervisors — deterministic single-run pipelines."""

from __future__ import annotations

from pathlib import Path

from workflows.account_classification.run import (
    format_classification_output,
    run_account_classification_from_pdf,
)
from workflows.court_calendar.run import (
    format_scheduling_output,
    run_court_workflow_from_email,
    run_court_workflow_from_pdf,
)
from workflows.schemas import AccountClassificationPackage, ReviewPackage


async def run_court_workflow(
    *,
    pdf_path: Path | None = None,
    email_path: Path | None = None,
    use_cache: bool = True,
) -> ReviewPackage:
    if pdf_path is not None:
        return await run_court_workflow_from_pdf(pdf_path, use_cache=use_cache)
    if email_path is not None:
        return await run_court_workflow_from_email(email_path, use_cache=use_cache)
    raise ValueError("Provide pdf_path or email_path")


async def run_account_classification_workflow(
    client_id: str,
    pdf_path: Path,
    *,
    consumer_id: str | None = None,
    use_cache: bool = True,
) -> AccountClassificationPackage:
    return await run_account_classification_from_pdf(
        client_id,
        pdf_path,
        consumer_id=consumer_id,
        use_cache=use_cache,
    )


__all__ = [
    "format_classification_output",
    "format_scheduling_output",
    "run_account_classification_from_pdf",
    "run_account_classification_workflow",
    "run_court_workflow",
    "run_court_workflow_from_email",
    "run_court_workflow_from_pdf",
]
