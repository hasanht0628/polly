"""Schemas for PII detection, location, and batch redaction results."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class PiiEntityType(str, Enum):
    name = "name"
    ssn = "ssn"
    address = "address"


class PiiCandidate(BaseModel):
    entity_type: PiiEntityType
    text: str
    confidence: str = "medium"
    page: int = 1


class DetectedEntities(BaseModel):
    """LLM structured output for one page of OCR text."""

    entities: list[PiiCandidate] = Field(default_factory=list)


class NormalizedBox(BaseModel):
    """Page-relative box in [0, 1] coordinates (origin top-left)."""

    x0: float
    y0: float
    x1: float
    y1: float


class VisionLocatedItem(BaseModel):
    text: str
    box: NormalizedBox


class VisionLocateOutput(BaseModel):
    boxes: list[VisionLocatedItem] = Field(default_factory=list)


class LocatedRedaction(BaseModel):
    page: int
    entity_type: PiiEntityType
    text: str
    confidence: str
    x0: float
    y0: float
    x1: float
    y1: float
    locate_method: str = "search"


class RedactionEntitySummary(BaseModel):
    """Audit-safe entity record (no full SSN)."""

    entity_type: PiiEntityType
    page: int
    confidence: str
    locate_method: str
    ssn_last4: str | None = None
    text_preview: str | None = None


class RedactionDocumentResult(BaseModel):
    source_pdf_path: Path
    output_pdf_path: Path | None = None
    page_count: int = 0
    entities: list[RedactionEntitySummary] = Field(default_factory=list)
    entity_counts: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    needs_review: bool = False
    duration_s: float = 0.0
    llm_usage: dict[str, int | float] = Field(default_factory=dict)
    ocr_usage: dict[str, int | float] = Field(default_factory=dict)


class RedactionBatch(BaseModel):
    inputs: list[Path] = Field(default_factory=list)
    documents: list[RedactionDocumentResult] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    run_id: str | None = None
