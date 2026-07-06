"""Convert loose LLM extract models into validated domain models."""

from __future__ import annotations

import re
from datetime import date as DateType, datetime, time as TimeType

from court.extract_models import (
    ExtractedCaseInfo,
    ExtractedDeadline,
    ExtractedEvent,
    ExtractedEvents,
    ExtractedDeadlines,
)
from court.schemas import (
    CaseExtraction,
    CourtEvent,
    DayType,
    Deadline,
    DeadlineKind,
    LocationType,
    OffsetDirection,
)

_TIME_IN_QUOTE = re.compile(
    r"\b(\d{1,2}:\d{2}\s*(?:A\.?M\.?|P\.?M\.?))\b",
    re.IGNORECASE,
)
_MONTH_DAY_YEAR = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})\b",
    re.IGNORECASE,
)
_MEETING_ID = re.compile(r"(?:ID|Meeting ID)[:\s]+([\d\s]+)", re.IGNORECASE)
_OFFSET_DAYS = re.compile(r"\((\d+)\)\s*days?|(\d+)\s*days?", re.IGNORECASE)


def _normalize_enum(value: str | None, allowed: set[str], default: str) -> str:
    if not value:
        return default
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in allowed else default


def _location_type(raw: ExtractedEvent) -> LocationType:
    quote = raw.source_quote.lower()
    normalized = _normalize_enum(
        raw.location_type,
        {"physical", "virtual", "unknown"},
        "unknown",
    )
    if normalized != "unknown":
        return LocationType(normalized)
    if "via zoom" in quote or "teams" in quote or raw.virtual_meeting_id:
        return LocationType.virtual
    if "courtroom" in quote or raw.location:
        return LocationType.physical
    return LocationType.unknown


def _meeting_id_from_quote(quote: str) -> str | None:
    match = _MEETING_ID.search(quote)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1).strip())


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _sanitize_meeting_id(raw_id: str | None, quote: str) -> str | None:
    from_quote = _meeting_id_from_quote(quote)
    if raw_id and raw_id.strip().lower().startswith(("http://", "https://")):
        raw_id = from_quote
    candidate = (raw_id or from_quote or "").strip() or None
    if not candidate:
        return None
    quote_digits = _digits(quote)
    if _digits(candidate) in quote_digits:
        return candidate
    return from_quote if from_quote else None


def _quote_mentions_time(quote: str) -> bool:
    return bool(_TIME_IN_QUOTE.search(quote))


def _date_from_quote(quote: str) -> DateType | None:
    match = _MONTH_DAY_YEAR.search(quote)
    if not match:
        return None
    month_name, day, year = match.group(1), int(match.group(2)), int(match.group(3))
    try:
        return datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y").date()
    except ValueError:
        return datetime.strptime(f"{month_name} {day} {year}", "%b %d %Y").date()


def _coerce_date(value: DateType | str | None) -> DateType | None:
    if value is None or value == "":
        return None
    if isinstance(value, DateType):
        return value
    text = str(value).strip()
    try:
        return DateType.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _sanitize_date(
    raw_date: DateType | str | None, quote: str
) -> tuple[DateType | None, bool]:
    parsed = _coerce_date(raw_date)
    if parsed and parsed.year >= 1900:
        return parsed, False
    recovered = _date_from_quote(quote)
    if recovered:
        return recovered, parsed is not None
    return None, True


def _sanitize_time(raw_time: str | None, quote: str) -> tuple[TimeType | None, bool]:
    if raw_time:
        cleaned = raw_time.split("-")[0].split("+")[0].strip()
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M:%S", "%H:%M"):
            try:
                token = cleaned.upper().replace(".", "")
                if fmt in ("%I:%M %p", "%I:%M%p"):
                    token = token.replace("AM", " AM").replace("PM", " PM").strip()
                return datetime.strptime(token, fmt).time(), False
            except ValueError:
                continue
    match = _TIME_IN_QUOTE.search(quote)
    if not match:
        return None, bool(raw_time)
    parsed = datetime.strptime(match.group(1).upper().replace(".", ""), "%I:%M %p")
    return parsed.time(), bool(raw_time)


def _looks_like_deadline(event: ExtractedEvent) -> bool:
    quote = event.source_quote.lower()
    return "days prior to" in quote or "days before" in quote


def normalize_event(raw: ExtractedEvent) -> CourtEvent | None:
    if _looks_like_deadline(raw):
        return None

    quote = raw.source_quote.strip()
    meeting_id = _sanitize_meeting_id(raw.virtual_meeting_id, quote)
    location_type = _location_type(raw)
    event_date, date_needs_review = _sanitize_date(raw.date, quote)
    event_time, time_needs_review = _sanitize_time(raw.time, quote)
    needs_review = date_needs_review or time_needs_review

    if not event_date and quote:
        needs_review = True
    if not event_time and _quote_mentions_time(quote):
        needs_review = True
    if raw.virtual_meeting_id and not meeting_id:
        needs_review = True
    if location_type == LocationType.virtual and not meeting_id:
        needs_review = True

    return CourtEvent(
        event_type=raw.event_type.strip() or "unknown",
        date=event_date,
        time=event_time,
        timezone="America/New_York" if event_date else None,
        location_type=location_type,
        location=raw.location,
        virtual_meeting_id=meeting_id,
        source_quote=quote,
        needs_review=needs_review,
    )


def _deadline_kind(raw: ExtractedDeadline) -> DeadlineKind:
    if _coerce_date(raw.due_date):
        return DeadlineKind.absolute
    normalized = _normalize_enum(raw.kind, {"absolute", "relative"}, "relative")
    if normalized == "absolute":
        return DeadlineKind.absolute
    return DeadlineKind.relative


def _deadline_direction(raw: ExtractedDeadline) -> OffsetDirection | None:
    quote = raw.source_quote.lower()
    normalized = _normalize_enum(raw.direction, {"before", "after"}, "")
    if normalized == "before":
        return OffsetDirection.before
    if normalized == "after":
        return OffsetDirection.after
    if "prior to" in quote or "before" in quote:
        return OffsetDirection.before
    if "after" in quote:
        return OffsetDirection.after
    return None


def _deadline_day_type(raw: ExtractedDeadline) -> DayType:
    if raw.day_type:
        normalized = _normalize_enum(
            raw.day_type,
            {"calendar", "business", "unknown"},
            "unknown",
        )
        if normalized in {"calendar", "business"}:
            return DayType(normalized)
    if re.search(r"\(\d+\)\s*days?|\b\d+\s*days?", raw.source_quote, re.IGNORECASE):
        return DayType.calendar
    return DayType.unknown


def _deadline_offset_days(raw: ExtractedDeadline) -> int | None:
    if raw.offset_days is not None:
        return raw.offset_days
    match = _OFFSET_DAYS.search(raw.source_quote)
    if match:
        return int(match.group(1) or match.group(2))
    if "prior to" in raw.source_quote.lower() and "days" not in raw.source_quote.lower():
        return 0
    return None


def _deadline_anchor(raw: ExtractedDeadline) -> str | None:
    if raw.anchor_event:
        return raw.anchor_event.strip()
    quote = raw.source_quote.lower()
    if "docket sounding" in quote:
        return "Docket Sounding"
    if "trial" in quote and "prior to" in quote:
        return "Trial"
    return None


def normalize_deadline(raw: ExtractedDeadline) -> Deadline | None:
    quote = raw.source_quote.strip()
    if not quote or not raw.description.strip():
        return None

    kind = _deadline_kind(raw)
    direction = _deadline_direction(raw)
    anchor = _deadline_anchor(raw)
    offset_days = _deadline_offset_days(raw)
    day_type = _deadline_day_type(raw)

    if kind == DeadlineKind.relative and not anchor and offset_days is None and not direction:
        return None

    needs_review = False
    if kind == DeadlineKind.relative and not anchor:
        needs_review = True
    if kind == DeadlineKind.relative and direction is None:
        needs_review = True

    return Deadline(
        description=raw.description.strip(),
        kind=kind,
        due_date= _coerce_date(raw.due_date),
    due_time=_sanitize_time(raw.due_time, quote)[0],
        anchor_event=anchor,
        offset_days=offset_days,
        direction=direction,
        day_type=day_type,
        source_quote=quote,
        needs_review=needs_review,
    )


def normalize_extraction(
    case: ExtractedCaseInfo,
    events: ExtractedEvents,
    deadlines: ExtractedDeadlines,
    *,
    page_count: int,
) -> CaseExtraction:
    normalized_events = [
        event
        for raw in events.events
        if (event := normalize_event(raw)) is not None
    ]
    normalized_deadlines = [
        deadline
        for raw in deadlines.deadlines
        if (deadline := normalize_deadline(raw)) is not None
    ]
    notes = [*events.extraction_notes, *deadlines.extraction_notes]

    if not any([case.case_caption, case.case_number, case.court]):
        notes.append("Case header fields missing or incomplete.")

    return CaseExtraction(
        case_caption=case.case_caption,
        case_number=case.case_number,
        court=case.court,
        events=normalized_events,
        deadlines=normalized_deadlines,
        extraction_notes=notes,
        page_count=page_count,
    )
