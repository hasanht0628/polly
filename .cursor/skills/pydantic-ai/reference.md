# Pydantic AI reference (for build decisions)

Docs index: https://ai.pydantic.dev/

## Tools

### `@agent.tool` vs `@agent.tool_plain`

- `@agent.tool` — first arg is `RunContext[Deps]`; deps injected, not in JSON schema
- `@agent.tool_plain` — no context; all args visible to model
- `retries=N` on tool for `ModelRetry` recovery
- `requires_approval=True` → deferred tool call; resolve via handler or hook
- `sequential=True` — serialize parallel tool calls of same tool

### FunctionToolset

```python
from pydantic_ai import Agent, FunctionToolset, RunContext

weather = FunctionToolset(instructions="Use for forecasts only.")

@weather.tool
async def temperature(ctx: RunContext[MyDeps], city: str) -> float: ...

agent = Agent(model, toolsets=[weather])
```

- `tools=[fn, ...]` or `@toolset.tool` decorators
- `instructions=` bundled with toolset (avoids duplicating on every agent)
- `defer_loading=True` — hide tools until `load_capability` or tool search

### Toolset composition

| Class | Role |
|-------|------|
| `CombinedToolset([a, b])` | Merge toolsets |
| `FilteredToolset` | Include/exclude by name |
| `RenamedToolset` | Rename tools for model |
| `PreparedToolset` / `.prepared(fn)` | Mutate `ToolDefinition` list per step (no add/rename) |
| `ExternalToolset` | Tools executed outside agent (client-side) |
| `MCPToolset` | MCP server tools |
| `WrapperToolset` | Custom `AbstractToolset` subclass |

Capability equivalents: `PrepareTools`, `PrefixTools`, `SetToolMetadata`, `IncludeToolReturnSchemas`, `HandleDeferredToolCalls`.

## Capabilities

Capabilities bundle instructions, toolsets, tools, model settings, native tools, and lifecycle hooks. Pass via `Agent(..., capabilities=[...])`.

### Convenience: `Capability`

```python
from pydantic_ai.capabilities import Capability

support = Capability(
    id="refunds",
    description="Process refund lookups and status checks.",
    instructions="...",
    defer_loading=True,  # catalog entry only until loaded
)

@support.tool
async def refund_status(ctx: RunContext, order_id: str) -> str: ...
```

### `AbstractCapability` — when to subclass

Use when you need: dynamic description, per-run model settings, native tools, wrapper toolsets, or complex hook logic.

Key methods: `get_instructions`, `get_model_settings`, `get_toolset`, `get_native_tools`, `before_model_request`, `after_model_request`, `prepare_tools`, `handle_deferred_tool_calls`.

### Deferred (on-demand) capabilities

- Model sees a **catalog** of capability ids + descriptions
- Calls `load_capability` to activate tools/instructions/hooks for that bundle
- Requires stable explicit `id` for history replay across runs/providers
- `ctx.loaded_capability_ids`, `ctx.available_capability_ids` on `RunContext`

Use when: many optional workflows (support bot with refunds + billing + security), MCP servers, skill files.

### Built-in capabilities (common)

| Capability | Purpose |
|------------|---------|
| `Hooks` | Decorator-based lifecycle hooks |
| `Thinking` | Extended reasoning (provider-native) |
| `Compaction` | Summarize/prune long history |
| `WebSearch` / `WebFetch` | Native or fallback web access |
| `MCP` | MCP server integration |
| `ToolSearch` | Discover deferred tools |
| `ProcessHistory` | History processor wrapper |
| `ProcessEventStream` | Stream event forwarding |
| `ReinjectSystemPrompt` | Fix missing system prompt in history |
| `HandleDeferredToolCalls` | Inline approval/deferred resolution |

## Hooks

`Hooks` capability — preferred for app-level concerns.

```python
from pydantic_ai.capabilities import Hooks

hooks = Hooks()

@hooks.on.before_model_request
async def log(ctx, request_context):
    return request_context

@hooks.on.before_tool_execute(tools=["delete_file"])
async def audit(ctx, *, call, tool_def, args):
    return args

agent = Agent(model, capabilities=[hooks])
```

### Hook phases (simplified)

| Phase | Examples | Notes |
|-------|----------|-------|
| Run | `before_run`, `after_run`, `run` (wrap) | Once per run |
| Node | `before_node_run`, `node_run` | Per graph step |
| Model | `before_model_request`, `model_request` (wrap) | Per LLM call; `SkipModelRequest` to short-circuit |
| Tool validate | `before_tool_validate`, `tool_validate` | JSON → Pydantic args |
| Tool execute | `before_tool_execute`, `tool_execute` | Actual function call |
| Output | `before_output_validate`, `before_output_process` | Structured output path only |
| Prepare | `prepare_tools`, `prepare_output_tools` | Dynamic tool visibility |
| Deferred | `deferred_tool_calls` | Approve/deny external tool calls |
| Stream | `event`, `run_event_stream` | Streaming observability |

Ordering: `before_*` forward, `after_*` reverse, `wrap_*` nested middleware.

`ModelRetry` from hooks triggers same retry machinery as tools/output validators.

### Hooks vs AbstractCapability

| Hooks | AbstractCapability |
|-------|-------------------|
| Logging, metrics, one-off guards | Reusable library / multi-agent shared behavior |
| No packaged state | Tools + settings + hooks together |
| Single-file scripts | Deferred workflows, MCP bundles |

## Message history & chat

### Continuing a conversation

```python
r1 = await agent.run("Tell me about the case.")
r2 = await agent.run("What deadlines?", message_history=r1.new_messages())
```

- `new_messages()` — only this run (usual choice for next turn)
- `all_messages()` — full thread including prior runs
- `*_json()` variants for persistence
- With non-empty `message_history`, agent does **not** regenerate system prompt — use `ReinjectSystemPrompt` if your store dropped it

### IDs

- `run_id` — unique per run (tracing)
- `conversation_id` — stable across turns; pass `conversation_id="new"` to fork

### History processors

- `ProcessHistory` capability or agent-level history processors
- `Compaction` for long threads

## Structured output

| Mode | When |
|------|------|
| `NativeOutput(Model)` | Provider returns JSON matching schema (Pollack + Ollama) |
| Output tools | Model explicitly calls output tool |
| Plain text | OCR, narration |

Agent-level `retries=N` applies to output validation failures.

## Streaming

| API | Behavior |
|-----|----------|
| `run_stream()` | Streams first final output; may stop early if tools follow |
| `run_stream_events()` | Full event graph |
| `agent.iter()` | Manual step control |
| `event_stream_handler` on `run()` | Runs graph to completion with events |

For agents that call tools after emitting text, prefer `run_stream_events()` or `iter()`.

## Dependency injection

```python
@dataclass
class Deps:
    db: Database
    user_id: str

agent = Agent(model, deps_type=Deps)

@agent.tool
async def lookup(ctx: RunContext[Deps], query: str) -> str:
    return await ctx.deps.db.fetch(query, ctx.deps.user_id)

result = await agent.run("...", deps=Deps(db, "u1"))
```

`@agent.instructions` functions also receive `RunContext[Deps]`.

Static `instructions=` are cache-friendly; dynamic instructions re-evaluate each run.

## Deferred tools & human-in-the-loop

1. Mark tool `requires_approval=True` or use external execution
2. Run produces `DeferredToolRequests`
3. Resolve via:
   - `HandleDeferredToolCalls(handler)` capability
   - `@hooks.on.deferred_tool_calls`
   - Or resume later with `DeferredToolResults`

## MCP integration

- `MCP` capability — URL, client, or `FastMCP` server
- `MCPToolset` for lower-level control
- Often combined with `defer_loading=True` to avoid huge tool lists in prompt

## Testing patterns

- Swap `FunctionToolset` implementations per test
- Inject fake `deps`
- `capture_run_messages` to assert prompts/tools
- `TestModel` / model overrides for offline agent tests (see pydantic-ai testing docs)

## Pollack → Pydantic AI evolution map

| Today | If requirements grow |
|-------|---------------------|
| 3 extract agents, no tools | Keep — good for deterministic legal extraction |
| `agents/registry.py` documents tools | Wire as `FunctionToolset` when supervisor becomes agentic |
| SQLite audit log | `Hooks.after_run` or `after_tool_execute` for structured telemetry |
| Stateless CLI scripts | Add `message_history` only for interactive assistant UX |
| Ollama only | Add capabilities with fallbacks when switching providers |

## Official doc links

- Agent: https://ai.pydantic.dev/agent/
- Tools: https://ai.pydantic.dev/tools/
- Toolsets: https://ai.pydantic.dev/toolsets/
- Capabilities: https://ai.pydantic.dev/capabilities/
- Hooks: https://ai.pydantic.dev/hooks/
- Messages: https://ai.pydantic.dev/message-history/
- Deferred tools: https://ai.pydantic.dev/deferred-tools/
- Dependencies: https://ai.pydantic.dev/dependencies/
- Output: https://ai.pydantic.dev/output/
