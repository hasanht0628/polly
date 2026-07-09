"""Portfolio classification workflow: .dat → officer-code resolve → optional LLM."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from agents.audit import AuditLog, WorkflowRun
from classification.client_codes import (
    DEFAULT_CODES_PATH,
    ResolveStatus,
    load_client_code_table,
    resolve_officer_code,
)
from classification.schemas import ProductType
from portfolio.ambiguous_agent import run_ambiguous_classification
from portfolio.dat_parser import DatCase, parse_dat_file
from portfolio.pdf_locator import find_account_pdfs
from workflows.schemas import (
    ClassificationSource,
    PortfolioAccountResult,
    PortfolioClassificationBatch,
)


def parse_dat(dat_path: Path) -> list[DatCase]:
    return parse_dat_file(dat_path)


def resolve_codes(
    cases: list[DatCase],
    *,
    codes_path: Path | None = None,
):
    rows = load_client_code_table(codes_path)
    return rows, [(case, resolve_officer_code(case.officer_code, rows)) for case in cases]


def _from_unique(
    case: DatCase,
    *,
    archetype: ProductType,
    product_codes: list[str],
    evidence: list[str],
) -> PortfolioAccountResult:
    return PortfolioAccountResult(
        case_id=case.case_id,
        archetype=archetype,
        source=ClassificationSource.client_code,
        officer_code=case.officer_code,
        product_codes_considered=product_codes,
        confidence="high",
        needs_review=False,
        evidence=evidence,
        plaintiff=case.plaintiff,
        debt_amount=case.debt_amount,
        notes=list(case.notes),
    )


async def _from_ambiguous(
    case: DatCase,
    *,
    docs_root: Path | None,
    code_rows,
    resolve,
    client_id: str,
    use_cache: bool,
) -> PortfolioAccountResult:
    if docs_root is None:
        return PortfolioAccountResult(
            case_id=case.case_id,
            archetype=ProductType.other,
            source=ClassificationSource.unresolved,
            officer_code=case.officer_code,
            product_codes_considered=list(resolve.product_codes),
            confidence="low",
            needs_review=True,
            evidence=list(resolve.evidence)
            + ["docs_root not provided; cannot run PDF/LLM fallback"],
            plaintiff=case.plaintiff,
            debt_amount=case.debt_amount,
            notes=list(case.notes),
        )

    output, tool_trace, last_classification, last_locate = await run_ambiguous_classification(
        case=case,
        docs_root=docs_root,
        code_rows=code_rows,
        resolve=resolve,
        client_id=client_id,
        use_cache=use_cache,
    )

    try:
        archetype = ProductType(output.archetype)
    except ValueError:
        archetype = ProductType.other

    pdf_paths = []
    account_folder = None
    if last_locate is not None:
        pdf_paths = list(last_locate.pdf_paths)
        account_folder = last_locate.account_folder
    elif output.pdf_paths_used:
        pdf_paths = [Path(p) for p in output.pdf_paths_used]

    evidence = list(output.evidence_quotes) or list(resolve.evidence)
    if last_classification is not None:
        evidence = list(last_classification.evidence_quotes) or evidence

    return PortfolioAccountResult(
        case_id=case.case_id,
        account_folder=account_folder,
        archetype=archetype,
        source=ClassificationSource.llm,
        officer_code=case.officer_code,
        product_codes_considered=list(resolve.product_codes),
        confidence=output.confidence if output.confidence in {"high", "medium", "low"} else "low",
        needs_review=bool(output.needs_review) or archetype == ProductType.other,
        evidence=evidence,
        pdf_paths=pdf_paths,
        tool_trace=tool_trace,
        plaintiff=case.plaintiff,
        debt_amount=case.debt_amount,
        notes=list(case.notes),
    )


def assemble_batch(
    *,
    dat_path: Path,
    docs_root: Path | None,
    codes_path: Path | None,
    accounts: list[PortfolioAccountResult],
    run_id: str | None = None,
) -> PortfolioClassificationBatch:
    counts = Counter(a.source.value for a in accounts)
    counts["total"] = len(accounts)
    counts["needs_review"] = sum(1 for a in accounts if a.needs_review)
    return PortfolioClassificationBatch(
        dat_path=dat_path.resolve(),
        docs_root=docs_root.resolve() if docs_root else None,
        codes_path=codes_path.resolve() if codes_path else None,
        accounts=accounts,
        summary=dict(counts),
        run_id=run_id,
    )


async def run_portfolio_classification(
    dat_path: Path,
    *,
    docs_root: Path | None = None,
    codes_path: Path | None = None,
    client_id: str = "portfolio",
    use_cache: bool = True,
    audit: AuditLog | None = None,
    run: WorkflowRun | None = None,
) -> PortfolioClassificationBatch:
    dat_path = Path(dat_path)
    codes_path = Path(codes_path) if codes_path else DEFAULT_CODES_PATH
    docs_root = Path(docs_root) if docs_root else None

    audit = audit or AuditLog()
    owns_run = run is None
    if run is None:
        run = audit.start_run(
            "portfolio_classification",
            {
                "dat_path": str(dat_path),
                "docs_root": str(docs_root) if docs_root else None,
                "codes_path": str(codes_path),
            },
        )

    try:
        audit.log_tool(run, "parse_dat", {"dat_path": str(dat_path)})
        cases = parse_dat(dat_path)

        audit.log_tool(run, "resolve_codes", {"codes_path": str(codes_path), "cases": len(cases)})
        code_rows, resolved = resolve_codes(cases, codes_path=codes_path)

        accounts: list[PortfolioAccountResult] = []
        for case, resolve in resolved:
            if resolve.status == ResolveStatus.unique and resolve.archetype is not None:
                accounts.append(
                    _from_unique(
                        case,
                        archetype=resolve.archetype,
                        product_codes=list(resolve.product_codes),
                        evidence=list(resolve.evidence),
                    )
                )
                continue

            # Optional: still attempt locate for audit even when docs missing handled inside.
            if docs_root is not None:
                locate = find_account_pdfs(docs_root, case.case_id)
                audit.log_tool(
                    run,
                    "locate_pdfs",
                    {
                        "case_id": case.case_id,
                        "status": locate.status,
                        "pdf_count": len(locate.pdf_paths),
                    },
                )

            audit.log_tool(
                run,
                "ambiguous_classify",
                {
                    "case_id": case.case_id,
                    "resolve_status": resolve.status.value,
                    "officer_code": case.officer_code,
                },
            )
            accounts.append(
                await _from_ambiguous(
                    case,
                    docs_root=docs_root,
                    code_rows=code_rows,
                    resolve=resolve,
                    client_id=client_id,
                    use_cache=use_cache,
                )
            )

        batch = assemble_batch(
            dat_path=dat_path,
            docs_root=docs_root,
            codes_path=codes_path,
            accounts=accounts,
            run_id=run.run_id,
        )
        audit.log_tool(run, "assemble_batch", batch.summary)
        if owns_run:
            audit.complete_run(run, batch.summary, status="completed")
        return batch
    except Exception as exc:
        if owns_run:
            audit.complete_run(run, {"error": str(exc)}, status="failed")
        raise


def format_portfolio_output(batch: PortfolioClassificationBatch, *, pretty: bool = False) -> str:
    payload = batch.model_dump(mode="json")
    if pretty:
        return json.dumps(payload, indent=2)
    return json.dumps(payload)
