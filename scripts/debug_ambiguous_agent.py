#!/usr/bin/env python3
"""Instrumented single-case run of the ambiguous portfolio agent.

Runs fully offline against local Ollama. Shows, step by step, whether the model
actually calls tools, WHAT each tool returned, where time is spent, and the final
classification. Use it to debug the agentic PDF path on real portfolio data.

Examples
--------
# Synthetic fixtures (defaults):
python scripts/debug_ambiguous_agent.py --case-id 000880021

# Real data:
python scripts/debug_ambiguous_agent.py \
    --dat data/portfolio.dat \
    --docs data/docs_root \
    --codes knowledge/client_codes/default.yaml \
    --case-id 000123456

Tips
----
- Run with `python -u` (unbuffered) so you see each step live, e.g.
  `python -u scripts/debug_ambiguous_agent.py --case-id ...`
- `--no-cache` forces live OCR instead of reading .ocr.txt sidecars.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart

from agents.config import active_model_names
from classification.client_codes import load_client_code_table, resolve_officer_code
from portfolio.ambiguous_agent import PortfolioAgentDeps, portfolio_agent
from portfolio.case_aliases import load_folder_aliases
from portfolio.dat_parser import parse_dat_file
from portfolio.docs_root import prepare_docs_root


def _t(start: float) -> str:
    return f"[{time.perf_counter() - start:6.1f}s]"


def _clip(value: object, limit: int = 300) -> str:
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case-id", default="000880021", help="9-char case id from the .dat file")
    p.add_argument("--dat", type=Path, default=PROJECT_ROOT / "fixtures/portfolio/sample.dat")
    p.add_argument("--docs", type=Path, default=PROJECT_ROOT / "fixtures/portfolio")
    p.add_argument(
        "--codes", type=Path, default=PROJECT_ROOT / "knowledge/client_codes/synthetic_test.yaml"
    )
    p.add_argument(
        "--case-map",
        type=Path,
        default=PROJECT_ROOT / "fixtures/portfolio/case_id_map.yaml",
        help="Optional case_id -> account folder alias map",
    )
    p.add_argument("--client-id", default="portfolio")
    p.add_argument("--no-cache", action="store_true", help="Force live OCR (ignore .ocr.txt sidecars)")
    p.add_argument("--clip", type=int, default=300, help="Max chars printed per tool result")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()

    docs_root = prepare_docs_root(args.docs) if args.docs and args.docs.is_dir() else args.docs
    aliases_map = load_folder_aliases(args.case_map) if args.case_map.is_file() else {}
    code_rows = load_client_code_table(args.codes)
    cases = parse_dat_file(args.dat)
    case = next((c for c in cases if c.case_id == args.case_id), None)
    if case is None:
        available = ", ".join(c.case_id for c in cases[:20])
        raise SystemExit(f"case_id {args.case_id!r} not found in {args.dat}. First ids: {available}")
    resolve = resolve_officer_code(case.officer_code, code_rows)

    deps = PortfolioAgentDeps(
        case=case,
        docs_root=docs_root,
        code_rows=code_rows,
        resolve=resolve,
        client_id=args.client_id,
        use_cache=not args.no_cache,
        folder_aliases=list(aliases_map.get(case.case_id) or []),
    )

    prompt = (
        f"Classify case {case.case_id}.\n"
        f"Officer code: {case.officer_code}\n"
        f"Resolve status: {resolve.status.value}\n"
        f"Product codes (hints only): {resolve.product_codes}\n"
        f"Archetype candidates (hints only): {[c.value for c in resolve.candidates]}\n"
        f"Plaintiff: {case.plaintiff}\n"
        f"Docs root: {docs_root}\n"
        "\nStart by calling find_account_folder."
    )

    start = time.perf_counter()
    models = active_model_names()
    print(f"{_t(start)} models: chat={models['chat_model']} ocr={models['ocr_model']} provider={models['provider']}")
    print(f"{_t(start)} START case={case.case_id} officer={case.officer_code} resolve={resolve.status.value}")
    print(f"{_t(start)} aliases={deps.folder_aliases} use_cache={deps.use_cache}")

    async with portfolio_agent.iter(prompt, deps=deps) as run:
        async for node in run:
            if portfolio_agent.is_model_request_node(node):
                # A model request carries the results of tools executed just before it.
                request = getattr(node, "request", None)
                for part in getattr(request, "parts", []) or []:
                    if isinstance(part, ToolReturnPart):
                        print(f"{_t(start)}    <- {part.tool_name} returned: {_clip(part.content, args.clip)}")
                print(f"{_t(start)} -> model request")
            elif portfolio_agent.is_call_tools_node(node):
                for part in getattr(node.model_response, "parts", []) or []:
                    if isinstance(part, ToolCallPart):
                        print(f"{_t(start)}    model wants tool: {part.tool_name}({_clip(part.args, 160)})")
                    elif isinstance(part, TextPart) and part.content.strip():
                        print(f"{_t(start)}    model text: {_clip(part.content, 160)}")
            elif portfolio_agent.is_end_node(node):
                print(f"{_t(start)} END")

    result = run.result
    print("\n===== SUMMARY =====")
    print(f"tool_trace = {deps.tool_trace}")
    if deps.last_locate is not None:
        print(f"located folder = {deps.last_locate.account_folder}")
        print(f"located pdfs   = {[Path(p).name for p in deps.last_locate.pdf_paths]}")
    if deps.last_classification is not None:
        lc = deps.last_classification
        print(f"classify_archetype -> {lc.product_type.value} (conf={lc.confidence}) evidence={lc.evidence_quotes}")
    out = result.output
    print(f"final archetype = {out.archetype} (conf={out.confidence}, needs_review={out.needs_review})")
    print(f"final evidence  = {out.evidence_quotes}")
    usage = result.usage
    print(f"tokens = in:{usage.input_tokens} out:{usage.output_tokens} requests:{usage.requests}")
    print(f"wall   = {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
