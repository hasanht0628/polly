"""Batch PII redaction workflow: path → visually redacted PDFs."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from agents.audit import AuditLog, WorkflowRun
from agents.extract_utils import RunMetrics, empty_usage, merge_usage, usage_summary
from documents.text import load_document_text
from redaction.apply import apply_redactions, to_entity_summary
from redaction.detect import detect_pii_in_document
from redaction.locate import locate_candidates
from redaction.paths import resolve_pdf_paths
from redaction.schemas import RedactionBatch, RedactionDocumentResult


async def redact_one_pdf(
    pdf_path: Path,
    *,
    use_cache: bool = True,
    out_dir: Path | None = None,
    audit: AuditLog | None = None,
    run: WorkflowRun | None = None,
) -> RedactionDocumentResult:
    """Detect → locate → apply for a single PDF. Soft-fails into result.error."""
    pdf_path = pdf_path.resolve()
    started = time.perf_counter()
    ocr_metrics = RunMetrics()
    detect_metrics = RunMetrics()
    locate_metrics = RunMetrics()

    try:
        if audit and run:
            audit.log_tool(run, "load_document_text", {"pdf_path": str(pdf_path)})
        doc = await load_document_text(
            pdf_path,
            use_cache=use_cache,
            metrics=ocr_metrics,
        )

        if audit and run:
            audit.log_tool(
                run,
                "detect_pii",
                {"pdf_path": str(pdf_path), "page_count": doc.page_count},
            )
        candidates = await detect_pii_in_document(
            doc.text,
            metrics=detect_metrics,
        )

        if audit and run:
            audit.log_tool(
                run,
                "locate_rects",
                {"candidate_count": len(candidates)},
            )
        located = await locate_candidates(
            pdf_path,
            candidates,
            metrics=locate_metrics,
        )

        if audit and run:
            audit.log_tool(
                run,
                "apply_redactions",
                {"located_count": len(located)},
            )
        output_path = apply_redactions(pdf_path, located, out_dir=out_dir)

        summaries = [to_entity_summary(item) for item in located]
        counts = Counter(s.entity_type.value for s in summaries)
        needs_review = any(s.confidence != "high" for s in summaries) or (
            len(candidates) > 0 and len(located) < len(candidates)
        )

        return RedactionDocumentResult(
            source_pdf_path=pdf_path,
            output_pdf_path=output_path,
            page_count=doc.page_count,
            entities=summaries,
            entity_counts=dict(counts),
            needs_review=needs_review,
            duration_s=time.perf_counter() - started,
            llm_usage=merge_usage(
                usage_summary(detect_metrics),
                usage_summary(locate_metrics),
            ),
            ocr_usage=usage_summary(ocr_metrics),
        )
    except Exception as exc:  # noqa: BLE001 — batch soft-fail
        return RedactionDocumentResult(
            source_pdf_path=pdf_path,
            error=str(exc),
            needs_review=True,
            duration_s=time.perf_counter() - started,
            llm_usage=merge_usage(
                usage_summary(detect_metrics),
                usage_summary(locate_metrics),
            ),
            ocr_usage=usage_summary(ocr_metrics) if ocr_metrics.attempts else empty_usage(),
        )


async def run_redaction(
    path: Path | list[Path],
    *,
    use_cache: bool = True,
    out_dir: Path | None = None,
    audit: AuditLog | None = None,
    run: WorkflowRun | None = None,
) -> RedactionBatch:
    audit = audit or AuditLog()
    owns_run = run is None

    try:
        pdfs = resolve_pdf_paths(path)
    except (FileNotFoundError, ValueError) as exc:
        if owns_run:
            run = audit.start_run("redaction", {"error": str(exc)})
            audit.complete_run(run, {"error": str(exc)})
        raise

    inputs = [p.resolve() for p in (path if isinstance(path, list) else [path])]
    if run is None:
        run = audit.start_run(
            "redaction",
            {
                "inputs": [str(p) for p in inputs],
                "pdf_count": len(pdfs),
                "out_dir": str(out_dir) if out_dir else None,
            },
        )

    documents: list[RedactionDocumentResult] = []
    for pdf in pdfs:
        result = await redact_one_pdf(
            pdf,
            use_cache=use_cache,
            out_dir=out_dir,
            audit=audit,
            run=run,
        )
        documents.append(result)

    summary = {
        "pdfs": len(documents),
        "succeeded": sum(1 for d in documents if d.error is None),
        "failed": sum(1 for d in documents if d.error is not None),
        "needs_review": sum(1 for d in documents if d.needs_review),
        "entities": sum(len(d.entities) for d in documents),
    }
    for key in ("name", "ssn", "address"):
        summary[f"entities_{key}"] = sum(
            d.entity_counts.get(key, 0) for d in documents
        )

    batch = RedactionBatch(
        inputs=inputs,
        documents=documents,
        summary=summary,
        run_id=run.run_id,
    )
    if owns_run:
        audit.log_tool(run, "assemble_batch", summary)
        audit.complete_run(run, json.loads(batch.model_dump_json()))
    return batch


def format_redaction_output(batch: RedactionBatch, *, pretty: bool = False) -> str:
    payload = json.loads(batch.model_dump_json())
    if pretty:
        return json.dumps(payload, indent=2)
    return json.dumps(payload)
