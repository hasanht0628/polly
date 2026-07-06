from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DocumentTextResult(BaseModel):
    text: str
    page_count: int
    source_path: Path


class ExtractResult(BaseModel):
    profile_id: str
    data: Any
    source_path: Path | None = None
    extraction_notes: list[str] = Field(default_factory=list)
