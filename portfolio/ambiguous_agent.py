"""Tool-using agent for ambiguous / missing officer-code cases."""

from __future__ import annotations

import time
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
from pydantic_ai import ModelRetry, RunContext, ToolOutput

from agents.config import make_agent
from agents.extract_utils import EXTRACT_MODEL_SETTINGS, RunMetrics, empty_usage, usage_summary


# Max characters of PDF text handed back to the tool-using model per document.
# Small enough to fit a local model's context window alongside the running tool
# history, large enough to capture the classifying header of a statement/contract.
PDF_TEXT_LIMIT = 3000


class AmbiguousClassificationOutput(BaseModel):
    archetype: str = "other"
    confidence: str = "low"
    needs_review: bool = True
    evidence_quotes: list[str] = Field(default_factory=list)
    pdf_paths_used: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@dataclass
class AmbiguousRunMetrics:
    duration_s: float = 0.0
    agent_usage: dict[str, int | float] = field(default_factory=empty_usage)
    classify_usage: dict[str, int | float] = field(default_factory=empty_usage)
    ocr_usage: dict[str, int | float] = field(default_factory=empty_usage)

    def llm_usage(self) -> dict[str, int | float]:
        from agents.extract_utils import merge_usage

        return merge_usage(self.agent_usage, self.classify_usage)


@dataclass
class PortfolioAgentDeps:
    case: DatCase
    docs_root: Path
    code_rows: list[ClientCodeRow]
    resolve: ResolveResult
    client_id: str = "portfolio"
    use_cache: bool = True
    folder_aliases: list[str] = field(default_factory=list)
    tool_trace: list[str] = field(default_factory=list)
    last_locate: PdfLocateResult | None = None
    last_classification: ProductClassification | None = None
    classify_metrics: RunMetrics = field(default_factory=RunMetrics)
    ocr_metrics: RunMetrics = field(default_factory=RunMetrics)


SYSTEM_PROMPT = f"""\
You classify a debt-collection account when the officer code mapping is missing or ambiguous.

Allowed archetypes: {ACCOUNT_TYPE_LIST}

CRITICAL RULES:
- You MUST use tools before returning a final answer. Do not guess from plaintiff/notes alone.
- Officer-code candidates are hints only; they are ambiguous/missing by design. PDF evidence wins.
- If you have not called find_account_folder and read_pdf_text at least once, you are not done.
- Only return archetype=other after tools show no useful PDF text.

Required tool sequence (keep it short — each step is expensive):
1. find_account_folder — returns the account folder AND its pdf_paths. Do NOT call
   list_account_pdfs afterwards; you already have the paths.
2. read_pdf_text — read ONE promising PDF (prefer statement / contract / deficiency /
   account report over cover sheets). Only read a second PDF if the first has no useful text.
3. classify_archetype — pass the text returned by read_pdf_text (and its pdf_path).
4. Call final_result using classify_archetype's archetype/confidence. Put the PDF paths you
   read into pdf_paths_used and short document quotes into evidence_quotes.

Do not call the same tool twice with the same arguments. If read_pdf_text returns empty text
for every PDF, submit final_result with archetype=other and needs_review=true.
"""

# NOTE: ToolOutput (not NativeOutput) is required for the agentic PDF path.
# Ollama's OpenAI-compatible endpoint locks output to a JSON schema when NativeOutput
# is used, which prevents the model from emitting any tool calls (it just returns the
# final schema immediately). Delivering the result via a `final_result` tool keeps the
# model in function-calling mode so it can locate + read PDFs before answering.
portfolio_agent = make_agent(
    output_type=ToolOutput(
        AmbiguousClassificationOutput,
        name="final_result",
        description=(
            "Submit the final classification. Only call this AFTER you have read PDF "
            "text with read_pdf_text and classified it with classify_archetype."
        ),
    ),
    system_prompt=SYSTEM_PROMPT,
    deps_type=PortfolioAgentDeps,
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=3,
)


@portfolio_agent.output_validator
def require_pdf_tools(
    ctx: RunContext[PortfolioAgentDeps],
    output: AmbiguousClassificationOutput,
) -> AmbiguousClassificationOutput:
    """Reject a final answer that skipped the required locate+read tool sequence.

    Only enforced when documents are actually available; if the folder has no
    readable PDFs the agent is allowed to fall back to archetype=other.
    """
    trace = ctx.deps.tool_trace
    has_folder = any(t.startswith("find_account_folder:") for t in trace)
    has_read = any(t.startswith("read_pdf_text:") for t in trace)
    if has_read:
        return output
    if not has_folder:
        raise ModelRetry(
            "Call find_account_folder first to locate this account's PDFs, then "
            "read_pdf_text on a useful document, then classify_archetype."
        )
    # Folder was located; only accept skipping read if it genuinely had no PDFs.
    located_pdfs = bool(ctx.deps.last_locate and ctx.deps.last_locate.pdf_paths)
    if located_pdfs:
        raise ModelRetry(
            "You found the account folder but never called read_pdf_text. Read at "
            "least one PDF, then classify_archetype, before submitting final_result."
        )
    return output


@portfolio_agent.tool
def resolve_officer_code_tool(
    ctx: RunContext[PortfolioAgentDeps],
    officer_code: str | None = None,
) -> dict:
    """Re-read officer-code table candidates for this case.

    Call with no arguments; `officer_code` is optional and ignored (the case's
    code is already bound) but accepted so the call does not fail if included.
    """
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
def find_account_folder(
    ctx: RunContext[PortfolioAgentDeps],
    case_id: str | None = None,
    docs_root: str | None = None,
) -> dict:
    """Locate the account folder and its PDFs for this case.

    Call with no arguments. `case_id`/`docs_root` are optional and ignored — the
    correct values are already bound to this run — but they are accepted so the
    call does not fail if you include them.
    """
    locate = find_account_pdfs(
        ctx.deps.docs_root,
        ctx.deps.case.case_id,
        extra_names=ctx.deps.folder_aliases,
    )
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
        locate = find_account_pdfs(
            ctx.deps.docs_root,
            ctx.deps.case.case_id,
            extra_names=ctx.deps.folder_aliases,
        )
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
    document = await load_document_text(
        path,
        use_cache=ctx.deps.use_cache,
        metrics=ctx.deps.ocr_metrics,
    )
    # Keep the payload small: local CPU models run with a modest context window,
    # so returning the whole document (plus a duplicate preview) overflows it and
    # makes every subsequent step slower. A leading slice is enough to classify.
    text = document.text[:PDF_TEXT_LIMIT]
    return {
        "pdf_path": str(path),
        "text": text,
        "char_count": len(document.text),
        "truncated": len(document.text) > PDF_TEXT_LIMIT,
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
        metrics=ctx.deps.classify_metrics,
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
    folder_aliases: list[str] | None = None,
) -> tuple[
    AmbiguousClassificationOutput,
    list[str],
    ProductClassification | None,
    PdfLocateResult | None,
    AmbiguousRunMetrics,
]:
    deps = PortfolioAgentDeps(
        case=case,
        docs_root=docs_root,
        code_rows=code_rows,
        resolve=resolve,
        client_id=client_id,
        use_cache=use_cache,
        folder_aliases=list(folder_aliases or []),
    )
    prompt = (
        f"Classify case {case.case_id}.\n"
        f"Officer code: {case.officer_code}\n"
        f"Resolve status: {resolve.status.value}\n"
        f"Product codes (hints only): {resolve.product_codes}\n"
        f"Archetype candidates (hints only): {[c.value for c in resolve.candidates]}\n"
        f"Plaintiff: {case.plaintiff}\n"
        f"Debt amount: {case.debt_amount}\n"
        f"Case notes (collector notes; not sufficient alone): {case.notes}\n"
        f"Docs root: {docs_root}\n"
        "\n"
        "Start now by calling find_account_folder, then read_pdf_text on a useful PDF, "
        "then classify_archetype. Do not return a final answer until those tools have run."
    )
    started = time.perf_counter()
    result = await portfolio_agent.run(prompt, deps=deps)
    duration_s = time.perf_counter() - started
    output = result.output
    output.archetype = _normalize_archetype(output.archetype).value

    agent_metrics = RunMetrics(usage=result.usage, attempts=1)
    run_metrics = AmbiguousRunMetrics(
        duration_s=duration_s,
        agent_usage=usage_summary(agent_metrics),
        classify_usage=usage_summary(deps.classify_metrics),
        ocr_usage=usage_summary(deps.ocr_metrics),
    )
    return (
        output,
        deps.tool_trace,
        deps.last_classification,
        deps.last_locate,
        run_metrics,
    )
