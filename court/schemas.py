from __future__ import annotations

from datetime import date as DateType, time as TimeType
from enum import Enum

from pydantic import BaseModel, Field


class LocationType(str, Enum):
    physical = "physical"
    virtual = "virtual"
    unknown = "unknown"


class DeadlineKind(str, Enum):
    absolute = "absolute"
    relative = "relative"


class OffsetDirection(str, Enum):
    before = "before"
    after = "after"


class DayType(str, Enum):
    calendar = "calendar"
    business = "business"
    unknown = "unknown"


class CourtEvent(BaseModel):
    """A calendar occurrence such as a trial, hearing, or docket sounding."""

    event_type: str = Field(
        description="Type of event, e.g. trial, docket_sounding, hearing, mediation.",
    )
    date: DateType | None = Field(
        default=None,
        description="Explicit date from the document.",
    )
    time: TimeType | None = Field(
        default=None,
        description="Explicit time from the document.",
    )
    timezone: str | None = Field(
        default=None,
        description="IANA timezone when known or inferred for the court.",
    )
    location_type: LocationType = Field(
        default=LocationType.unknown,
        description="Whether the event is physical, virtual, or unknown.",
    )
    location: str | None = Field(
        default=None,
        description="Address, courtroom, or venue when physical or hybrid.",
    )
    virtual_meeting_id: str | None = Field(
        default=None,
        description="Video meeting ID as stated in the document.",
    )
    source_quote: str = Field(
        description="Verbatim sentence or paragraph from the document supporting this event.",
    )
    needs_review: bool = Field(
        default=False,
        description="True when extraction is incomplete or uncertain.",
    )


class Deadline(BaseModel):
    """A filing or compliance deadline. Relative deadlines are not computed here."""

    description: str = Field(
        description="What must be done, e.g. Exchange expert witness list.",
    )
    kind: DeadlineKind = Field(description="absolute or relative deadline.")
    due_date: DateType | None = Field(
        default=None,
        description="Explicit due date for absolute deadlines only.",
    )
    due_time: TimeType | None = Field(
        default=None,
        description="Explicit due time for absolute deadlines, if stated.",
    )
    anchor_event: str | None = Field(
        default=None,
        description="Anchor event label for relative deadlines, as written in the doc.",
    )
    offset_days: int | None = Field(
        default=None,
        description="Number of days before or after the anchor event.",
    )
    direction: OffsetDirection | None = Field(
        default=None,
        description="Whether the deadline is before or after the anchor event.",
    )
    day_type: DayType = Field(
        default=DayType.unknown,
        description="Calendar days, business days, or unknown.",
    )
    source_quote: str = Field(
        description="Verbatim sentence or paragraph from the document supporting this deadline.",
    )
    needs_review: bool = Field(
        default=False,
        description="True when the deadline is incomplete or ambiguous.",
    )


class CaseExtraction(BaseModel):
    """Structured extraction from a court document."""

    case_caption: str | None = Field(
        default=None,
        description="Case caption or style, e.g. Smith v. Jones.",
    )
    case_number: str | None = Field(
        default=None,
        description="Docket, index, or case number.",
    )
    court: str | None = Field(
        default=None,
        description="Court name or division.",
    )
    events: list[CourtEvent] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Ambiguities or conflicts flagged during extraction.",
    )
    page_count: int = Field(
        default=0,
        description="Number of PDF pages OCR'd.",
    )
