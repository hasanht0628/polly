from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from classification.schemas import ManualCitation, ProductClassification, ProductType
from court.schemas import CaseExtraction
from pydantic import BaseModel, Field


class EventKind(str, Enum):
    hearing = "hearing"
    deadline = "deadline"
    trial_period = "trial_period"


class IntakeEmail(BaseModel):
    sender: str | None = None
    subject: str | None = None
    received_at: datetime | None = None
    body_text: str = ""
    pdf_urls: list[str] = Field(default_factory=list)
    attachment_paths: list[Path] = Field(default_factory=list)
    documents_section: str | None = None


class SchedulableEvent(BaseModel):
    title: str
    start: datetime
    end: datetime
    timezone: str = "America/New_York"
    location: str | None = None
    virtual_meeting_id: str | None = None
    description: str = ""
    event_kind: EventKind = EventKind.hearing
    needs_review: bool = False
    source_quote: str = ""


class FlaggedItem(BaseModel):
    title: str
    reason: str
    source_quote: str = ""
    kind: str = "deadline"


class ReviewPackage(BaseModel):
    case_number: str | None = None
    case_caption: str | None = None
    court: str | None = None
    schedulable_events: list[SchedulableEvent] = Field(default_factory=list)
    flagged_items: list[FlaggedItem] = Field(default_factory=list)
    extraction: CaseExtraction | None = None
    source_pdf_path: Path | None = None
    email_subject: str | None = None
    email_sender: str | None = None
    run_id: str | None = None


class AccountClassificationPackage(BaseModel):
    client_id: str
    consumer_id: str | None = None
    account_type: ProductType
    confidence: str
    needs_review: bool
    review_reasons: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    manual_citations: list[ManualCitation] = Field(default_factory=list)
    alternative_types: list[ProductType] = Field(default_factory=list)
    classification: ProductClassification
    source_pdf_path: Path
    ocr_cache_path: Path | None = None
    run_id: str | None = None


class ClassificationSource(str, Enum):
    client_code = "client_code"
    llm = "llm"
    unresolved = "unresolved"


class PortfolioAccountResult(BaseModel):
    case_id: str
    account_folder: Path | None = None
    archetype: ProductType = ProductType.unknown
    source: ClassificationSource = ClassificationSource.unresolved
    officer_code: str = ""
    product_codes_considered: list[str] = Field(default_factory=list)
    confidence: str = "low"
    needs_review: bool = True
    evidence: list[str] = Field(default_factory=list)
    pdf_paths: list[Path] = Field(default_factory=list)
    tool_trace: list[str] = Field(default_factory=list)
    plaintiff: str = ""
    debt_amount: str = ""
    notes: list[str] = Field(default_factory=list)


class PortfolioClassificationBatch(BaseModel):
    dat_path: Path
    docs_root: Path | None = None
    codes_path: Path | None = None
    accounts: list[PortfolioAccountResult] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    run_id: str | None = None
