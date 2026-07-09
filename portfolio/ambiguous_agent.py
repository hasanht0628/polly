"""Tool-using agent for ambiguous / missing officer-code cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from classification.client_codes import (
    ClientCodeRow,
    ResolveResult,
    resolve_officer_code,
)
from classification.schemas import ProductClassification, ProductType
from classification.taxonomy import ACCOUNT_TYPE_LIST
from documents.profiles.product_classification import classify_document_text
from documents.text import load_document_text
from portfolio.dat_parser import DatCase
from portfolio.pdf_locator import PdfLocateResult, find_account_pdfs, list_pdfs
from pydantic import BaseModel, Field
from pydantic_ai import NativeOutput, RunContext

from agents.config import make_agent
from agents.extract_utils import EXTRACT_MODEL_SETTINGS


class AmbiguousClassificationOutput(BaseModel):
    archetype: str = "other"
    confidence: str = "low"
    needs_review: bool = True
    evidence_quotes: list[str] = Field(default_factory=list)
    pdf_paths_used: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@dataclass
class PortfolioAgentDeps:
    case: DatCase
    docs_root: Path
    code_rows: list[ClientCodeRow]
    resolve: ResolveResult
    client_id: str = "portfolio"
    use_cache: bool = True
    tool_trace: list[str] = field(default_factory=list)
    last_locate: PdfLocateResult | None = None
    last_classification: ProductClassification | None = None


SYSTEM_PROMPT = f"""\
You classify a debt-collection account when the officer code mapping is missing or ambiguous.

Allowed archetypes: {ACCOUNT_TYPE_LIST}

Use tools to:
1. Optionally re-check officer-code candidates.
2. Find the account folder and list PDFs.
3. Read PDF text (OCR) for one or more documents.
4. Call classify_archetype once you have useful document text.

Prefer a document that looks like a statement, contract, or deficiency notice over a blank cover sheet.
If no useful PDF text is available, return archetype=other with needs_review=true.
"""

portfolio_agent = make_agent(
    output_type=NativeOutput(AmbiguousClassificationOutput),
    system_prompt=SYSTEM_PROMPT,
    deps_type=PortfolioAgentDeps,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=2,
)


@portfolio_agent.tool
def resolve_officer_code_tool(ctx: RunContext[PortfolioAgentDeps]) -> dict:
    """Re-read officer-code table candidates for this case."""
    result = resolve_officer_code(ctx.deps.case.officer_code, ctx.deps.code_rows)
    ctx.deps.tool_trace.append(f"resolve_officer_code:{result.status.value}")
    return {
        "officer_code": result.officer_code,
        "status": result.status.value,
        "candidates": [c.value for c in result.candidates],
        "product_codes": result.product_codes,
        "evidence": result.evidence,
    }


@portfolio_agent.tool
def find_account_folder(ctx: RunContext[PortfolioAgentDeps]) -> dict:
    """Locate the account folder and PDFs for this case id."""
    locate = find_account_pdfs(ctx.deps.docs_root, ctx.deps.case.case_id)
    ctx.deps.last_locate = locate
    ctx.deps.tool_trace.append(f"find_account_folder:{locate.status}")
    return {
        "status": locate.status,
        "account_folder": str(locate.account_folder) if locate.account_folder else None,
        "pdf_paths": [str(p) for p in locate.pdf_paths],
        "matched_names": locate.matched_names,
        "evidence": locate.evidence,
    }


@portfolio_agent.tool
def list_account_pdfs(ctx: RunContext[PortfolioAgentDeps], folder: str | None = None) -> dict:
    """List PDFs under a folder (defaults to last matched account folder)."""
    target: Path | None
    if folder:
        target = Path(folder)
    elif ctx.deps.last_locate and ctx.deps.last_locate.account_folder:
        target = ctx.deps.last_locate.account_folder
    else:
        locate = find_account_pdfs(ctx.deps.docs_root, ctx.deps.case.case_id)
        ctx.deps.last_locate = locate
        target = locate.account_folder

    if target is None:
        ctx.deps.tool_trace.append("list_pdfs:no_folder")
        return {"pdf_paths": [], "error": "No account folder available"}

    pdfs = list_pdfs(target)
    ctx.deps.tool_trace.append(f"list_pdfs:{len(pdfs)}")
    return {"folder": str(target), "pdf_paths": [str(p) for p in pdfs]}


@portfolio_agent.tool
async def read_pdf_text(ctx: RunContext[PortfolioAgentDeps], pdf_path: str) -> dict:
    """OCR (or cache-read) text from one PDF."""
    path = Path(pdf_path)
    ctx.deps.tool_trace.append(f"read_pdf_text:{path.name}")
    if not path.exists():
        return {"pdf_path": pdf_path, "error": "file not found", "text": ""}
    document = await load_document_text(path, use_cache=ctx.deps.use_cache)
    text = document.text[:8000]
    return {
        "pdf_path": str(path),
        "text_preview": text[:2000],
        "text": text,
        "char_count": len(document.text),
    }


@portfolio_agent.tool
async def classify_archetype(
    ctx: RunContext[PortfolioAgentDeps],
    document_text: str,
    pdf_path: str | None = None,
) -> dict:
    """Classify document text into a firm archetype."""
    case = ctx.deps.case
    extra = (
        f"case_id={case.case_id}\n"
        f"officer_code={case.officer_code}\n"
        f"product_code_candidates={ctx.deps.resolve.product_codes}\n"
        f"archetype_candidates={[c.value for c in ctx.deps.resolve.candidates]}\n"
        f"plaintiff={case.plaintiff}\n"
        f"notes={'; '.join(case.notes)}"
    )
    ctx.deps.tool_trace.append(f"classify_archetype:{pdf_path or 'text'}")
    classification = await classify_document_text(
        document_text,
        client_id=ctx.deps.client_id,
        extra_context=extra,
    )
    ctx.deps.last_classification = classification
    return {
        "archetype": classification.product_type.value,
        "confidence": classification.confidence,
        "needs_review": classification.needs_review,
        "evidence_quotes": classification.evidence_quotes,
        "alternative_types": [t.value for t in classification.alternative_types],
    }


def _normalize_archetype(raw: str) -> ProductType:
    cleaned = raw.lower().replace(" ", "_").replace("-", "_")
    try:
        value = ProductType(cleaned)
    except ValueError:
        return ProductType.other
    if value == ProductType.unknown:
        return ProductType.other
    return value


async def run_ambiguous_classification(
    *,
    case: DatCase,
    docs_root: Path,
    code_rows: list[ClientCodeRow],
    resolve: ResolveResult,
    client_id: str = "portfolio",
    use_cache: bool = True,
) -> tuple[AmbiguousClassificationOutput, list[str], ProductClassification | None, PdfLocateResult | None]:
    deps = PortfolioAgentDeps(
        case=case,
        docs_root=docs_root,
        code_rows=code_rows,
        resolve=resolve,
        client_id=client_id,
        use_cache=use_cache,
    )
    prompt = (
        f"Classify case {case.case_id}.\n"
        f"Officer code: {case.officer_code}\n"
        f"Resolve status: {resolve.status.value}\n"
        f"Product codes: {resolve.product_codes}\n"
        f"Archetype candidates: {[c.value for c in resolve.candidates]}\n"
        f"Plaintiff: {case.plaintiff}\n"
        f"Debt amount: {case.debt_amount}\n"
        f"Case notes: {case.notes}\n"
        f"Docs root: {docs_root}\n"
        "Use tools as needed, then return the final structured classification."
    )
    result = await portfolio_agent.run(prompt, deps=deps)
    output = result.output
    output.archetype = _normalize_archetype(output.archetype).value
    return output, deps.tool_trace, deps.last_classification, deps.last_locate
