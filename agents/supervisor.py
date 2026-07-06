"""Court workflow supervisor — deterministic single-run pipeline."""

from __future__ import annotations

from pathlib import Path

from workflows.court_calendar.run import (
    format_scheduling_output,
    run_court_workflow_from_email,
    run_court_workflow_from_pdf,
)
from workflows.schemas import ReviewPackage


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


__all__ = [
    "format_scheduling_output",
    "run_court_workflow",
    "run_court_workflow_from_email",
    "run_court_workflow_from_pdf",
]
