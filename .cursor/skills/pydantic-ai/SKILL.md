---
name: pydantic-ai
description: >-
  Architecture and implementation guidance for Pydantic AI agents: toolsets,
  capabilities, hooks, message history, streaming, deps, structured output,
  deferred tools, and Ollama. Use when designing or building agents, choosing
  between tools vs multi-agent passes, adding MCP, chat persistence, HITL
  approval, or refactoring LLM layers in this repo.
---

# Pydantic AI — build advisor

Official docs: https://ai.pydantic.dev/

Read [reference.md](reference.md) when choosing between toolsets, capabilities, hooks, or chat patterns.

## Agent anatomy (mental model)

An `Agent` composes:

| Piece | Purpose |
|-------|---------|
| `model` | LLM provider + model name |
| `instructions` / `@agent.instructions` | Static + dynamic system guidance |
| `output_type` | Structured result (`NativeOutput`, `ToolOutput`, plain text) |
| `deps_type` + `RunContext` | Type-safe dependency injection into tools/instructions |
| `tools` / `@agent.tool` | Per-agent function tools |
| `toolsets` / `capabilities` | Reusable, composable tool + behavior bundles |
| `retries` / `model_settings` | Output retry budget and per-request settings |
| `message_history` | Multi-turn chat continuity |

Runs: `agent.run()` → `RunResult` with `.output`, `.new_messages()`, `.all_messages()`.

## Decision tree — what to use

### 1. Output shape

| Need | Use |
|------|-----|
| Fixed Pydantic schema from local model (Ollama) | `output_type=NativeOutput(Model)` — **Pollack default** |
| Model must call an output tool | `ToolOutput` / output tools |
| Free text (OCR, summaries) | No `output_type` or `str` |
| Multiple unrelated schemas in one doc | **Separate agents** (see `court/extract.py`), not one giant schema |

### 2. Reuse & composition

| Need | Use |
|------|-----|
| A few functions on one agent | `@agent.tool` / `@agent.tool_plain` |
| Shared tools across agents, test swaps | `FunctionToolset` |
| MCP, LangChain, external providers | Dedicated toolsets (`MCPToolset`, etc.) |
| Filter/rename/prefix tools per step | `FilteredToolset`, `RenamedToolset`, `PrefixTools`, `PreparedToolset` |
| Bundle tools + hooks + instructions + settings | `Capability(...)` or subclass `AbstractCapability` |
| Built-in behaviors (web search, thinking, compaction) | Native capabilities (`WebSearch`, `Thinking`, `Compaction`, …) |
| Hide tools until model needs them | `defer_loading=True` on capability/toolset |

**Rule of thumb:** tools on the agent for app-specific glue; toolsets for shared libraries; capabilities when behavior should ship as one unit.

### 3. Cross-cutting behavior (logging, approval, metrics)

| Need | Use |
|------|-----|
| App-level interceptors, one file | `Hooks()` + `@hooks.on.*` |
| Reusable packaged behavior (tools + hooks + settings) | `AbstractCapability` subclass |
| Approve dangerous tool calls | `requires_approval=True` on tool + `HandleDeferredToolCalls` or `@hooks.on.deferred_tool_calls` |
| Dynamic tool list per step | `@hooks.on.prepare_tools` or `PreparedToolset` |
| Retry with custom message | `ModelRetry` from hook or tool |
| Skip model call / tool / validation | `SkipModelRequest`, `SkipToolExecution`, `SkipToolValidation` |

**Rule of thumb:** `Hooks` for app wiring; `AbstractCapability` for libraries and deferred workflows.

### 4. Conversation & memory

| Need | Use |
|------|-----|
| Stateless extraction (Pollack court docs) | Single `run(prompt)` — no history |
| Multi-turn chat | `message_history=result.new_messages()` on next `run` |
| Persist to DB | `result.all_messages_json()` / load back as messages |
| History missing system prompt | `ReinjectSystemPrompt` capability |
| Long threads, token limits | `Compaction` capability |
| Correlate traces | `conversation_id` on runs (auto from history) |

### 5. Streaming & observability

| Need | Use |
|------|-----|
| Stream final text only | `run_stream()` + `stream_text()` |
| Full agent graph (tool calls after text) | `run_stream_events()` or `agent.iter()` |
| Custom UI / logging | `@hooks.on.event` or `ProcessEventStream` |
| Tests asserting message flow | `capture_run_messages` context manager |

### 6. Dependencies

| Need | Use |
|------|-----|
| DB, API clients, config in tools | `deps_type=MyDeps`, `agent.run(prompt, deps=...)` |
| Dynamic instructions from deps | `@agent.instructions` with `RunContext[MyDeps]` |
| Unit tests with fakes | Inject mock deps; swap toolsets at test time |

## Pollack conventions (this repo)

| Pattern | Canonical file |
|---------|----------------|
| Ollama agent factory | `agents/config.py` — `make_agent()`, `make_ocr_agent()` |
| Structured multi-pass extract | `court/extract.py` — module-level agents, `NativeOutput`, `_run_with_retries` |
| Vision OCR | `documents/ocr.py` — `BinaryContent` multimodal prompt |
| Document profiles | `documents/profiles/*.py` |

**Current architecture:** deterministic workflow supervisor (`agents/supervisor.py`), not an LLM routing loop. Prefer explicit pipelines over agentic tool-chaining unless requirements demand it.

**When extending Pollack:**

1. New extract schema → Pydantic model + `make_agent(output_type=NativeOutput(...))`.
2. New shared external capability → `FunctionToolset` or MCP capability, not copy-paste `@agent.tool`.
3. Audit / approval on calendar writes → `Hooks` or deferred tools, not ad-hoc middleware.
4. Interactive scheduling assistant → `message_history` + tools; keep extraction agents stateless.

## Anti-patterns

- One agent with 15 tools when a linear pipeline suffices
- Inline `Agent(...)` instead of shared factory
- Putting business normalization in hooks (belongs in Python after `result.output`)
- `run_stream()` when tools may run after text — use `run_stream_events()`
- Deferred capabilities without stable `id` (breaks history replay)
- Giant monolithic `output_type` when domains are independent

## Build-advice checklist

Before recommending a design, answer:

1. **Stateless or conversational?** → history yes/no
2. **Structured or free text?** → `NativeOutput` vs plain
3. **Who calls whom?** → pipeline vs tool loop vs deferred capabilities
4. **What is reused?** → toolset vs capability vs copy-paste
5. **What needs guardrails?** → approval, hooks, retries, `PrepareTools`
6. **Provider constraints?** → Ollama may lack native web search / deferred tools; plan fallbacks

## Version note

Repo pins `pydantic-ai>=0.2.0`. Capabilities, `Hooks`, and deferred loading are newer API surfaces — verify against installed version before suggesting APIs that may not exist on older installs.
