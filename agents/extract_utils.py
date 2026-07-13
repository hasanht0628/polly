"""Shared helpers for structured LLM extraction passes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_ai.usage import RunUsage

EXTRACT_MODEL_SETTINGS = {"temperature": 0}

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass
class RunMetrics:
    usage: RunUsage = field(default_factory=RunUsage)
    attempts: int = 0

    def incr_usage(self, other: RunUsage) -> None:
        self.usage.incr(other)

    def as_dict(self) -> dict[str, int | float]:
        return usage_summary(self)


def usage_summary(metrics: RunMetrics) -> dict[str, int | float]:
    usage = metrics.usage
    return {
        "attempts": metrics.attempts,
        "requests": usage.requests,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


def empty_usage() -> dict[str, int | float]:
    return {
        "attempts": 0,
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def merge_usage(*parts: dict[str, Any]) -> dict[str, int | float]:
    merged = empty_usage()
    for part in parts:
        if not part:
            continue
        for key in ("attempts", "requests", "input_tokens", "output_tokens", "total_tokens"):
            merged[key] = int(merged[key]) + int(part.get(key, 0))
    return merged


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
