"""Loose schemas for LLM structured output. Normalized to court.schemas before return."""

from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel, Field


class ExtractedCaseInfo(BaseModel):
    case_caption: str | None = None
    case_number: str | None = None
    court: str | None = None


class ExtractedEvent(BaseModel):
    event_type: str = Field(
        default="unknown",
        description="trial, docket_sounding, hearing, mediation, or similar.",
    )
    date: DateType | str | None = None
    time: str | None = None
    location_type: str | None = Field(
        default=None,
        description="physical, virtual, or unknown.",
    )
    location: str | None = None
    virtual_meeting_id: str | None = Field(
        default=None,
        description="Video meeting ID as written in the document, not a constructed URL.",
    )
    source_quote: str = ""


class ExtractedEvents(BaseModel):
    events: list[ExtractedEvent] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)


class ExtractedDeadline(BaseModel):
    description: str
    kind: str | None = Field(
        default=None,
        description="absolute or relative.",
    )
    due_date: DateType | str | None = None
    due_time: str | None = None
    anchor_event: str | None = None
    offset_days: int | None = None
    direction: str | None = Field(
        default=None,
        description="before or after.",
    )
    day_type: str | None = Field(
        default=None,
        description="calendar, business, or unknown.",
    )
    source_quote: str = ""


class ExtractedDeadlines(BaseModel):
    deadlines: list[ExtractedDeadline] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)
