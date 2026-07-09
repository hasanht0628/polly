"""Shared helpers for structured LLM extraction passes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai.usage import RunUsage

EXTRACT_MODEL_SETTINGS = {"temperature": 0}

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass
class RunMetrics:
    usage: RunUsage = field(default_factory=RunUsage)
    attempts: int = 0


async def run_with_retries(
    agent,
    prompt: str,
    *,
    attempts: int = 2,
    is_empty,
    metrics: RunMetrics | None = None,
) -> OutputT:
    usage = RunUsage()
    last: OutputT | None = None
    attempt_count = 0
    for attempt_count in range(1, attempts + 1):
        result = await agent.run(prompt)
        usage.incr(result.usage)
        last = result.output
        if not is_empty(last):
            if metrics is not None:
                metrics.usage = usage
                metrics.attempts = attempt_count
            return last
    assert last is not None
    if metrics is not None:
        metrics.usage = usage
        metrics.attempts = attempt_count
    return last
