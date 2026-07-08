"""Shared helpers for structured LLM extraction passes."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

EXTRACT_MODEL_SETTINGS = {"temperature": 0}

OutputT = TypeVar("OutputT", bound=BaseModel)


async def run_with_retries(
    agent,
    prompt: str,
    *,
    attempts: int = 2,
    is_empty,
) -> OutputT:
    last: OutputT | None = None
    for _ in range(attempts):
        result = await agent.run(prompt)
        last = result.output
        if not is_empty(last):
            return last
    assert last is not None
    return last
