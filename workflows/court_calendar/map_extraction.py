from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from court.schemas import CaseExtraction, CourtEvent, Deadline, DeadlineKind, LocationType
from workflows.schemas import EventKind, FlaggedItem, ReviewPackage, SchedulableEvent


def _event_title(caption: str | None, event_type: str) -> str:
    label = event_type.replace("_", " ").title()
    if caption:
        return f"{label} - {caption}"
    return label


def _location_label(event: CourtEvent) -> str | None:
    if event.location_type == LocationType.virtual:
        return "VIA ZOOM"
    return event.location


def _build_description(
    extraction: CaseExtraction,
    event: CourtEvent | Deadline,
    *,
    pdf_path: Path | None,
) -> str:
    parts: list[str] = []
    if extraction.case_number:
        parts.append(f"Case: {extraction.case_number}")
    if extraction.court:
        parts.append(f"Court: {extraction.court}")
    if pdf_path:
        parts.append(f"Source PDF: {pdf_path}")
    parts.append(f"Quote: {event.source_quote}")
    return "\n".join(parts)


def _event_kind(event_type: str) -> EventKind:
    normalized = event_type.lower().replace(" ", "_")
    if "trial" in normalized:
        return EventKind.trial_period
    return EventKind.hearing


def _court_event_to_schedulable(
    extraction: CaseExtraction,
    event: CourtEvent,
    *,
    pdf_path: Path | None,
) -> SchedulableEvent | FlaggedItem | None:
    if event.needs_review:
        return FlaggedItem(
            title=_event_title(extraction.case_caption, event.event_type),
            reason="Event flagged needs_review during extraction",
            source_quote=event.source_quote,
            kind="event",
        )
    if not event.date:
        return FlaggedItem(
            title=_event_title(extraction.case_caption, event.event_type),
            reason="Missing explicit event date",
            source_quote=event.source_quote,
            kind="event",
        )

    tz = event.timezone or "America/New_York"
    start_time = event.time or datetime.min.time().replace(hour=9, minute=0)
    start = datetime.combine(event.date, start_time)
    end = start + timedelta(hours=1)

    return SchedulableEvent(
        title=_event_title(extraction.case_caption, event.event_type),
        start=start,
        end=end,
        timezone=tz,
        location=_location_label(event),
        virtual_meeting_id=event.virtual_meeting_id,
        description=_build_description(extraction, event, pdf_path=pdf_path),
        event_kind=_event_kind(event.event_type),
        needs_review=False,
        source_quote=event.source_quote,
    )


def _deadline_to_flagged(extraction: CaseExtraction, deadline: Deadline) -> FlaggedItem:
    if deadline.kind == DeadlineKind.relative:
        anchor = deadline.anchor_event or "anchor event"
        offset = deadline.offset_days
        direction = deadline.direction.value if deadline.direction else "before"
        reason = f"Relative deadline: {offset} days {direction} {anchor}" if offset else f"Relative deadline anchored to {anchor}"
    elif deadline.due_date:
        reason = f"Absolute deadline on {deadline.due_date.isoformat()}"
    else:
        reason = "Deadline without computable date"

    return FlaggedItem(
        title=f"Deadline: {deadline.description}",
        reason=reason,
        source_quote=deadline.source_quote,
        kind="deadline",
    )


def map_extraction_to_review_package(
    extraction: CaseExtraction,
    *,
    pdf_path: Path | None = None,
    email_subject: str | None = None,
    email_sender: str | None = None,
    run_id: str | None = None,
) -> ReviewPackage:
    schedulable: list[SchedulableEvent] = []
    flagged: list[FlaggedItem] = []

    for event in extraction.events:
        mapped = _court_event_to_schedulable(extraction, event, pdf_path=pdf_path)
        if isinstance(mapped, SchedulableEvent):
            schedulable.append(mapped)
        elif mapped:
            flagged.append(mapped)

    for deadline in extraction.deadlines:
        if deadline.needs_review or deadline.kind == DeadlineKind.relative or not deadline.due_date:
            flagged.append(_deadline_to_flagged(extraction, deadline))
        elif deadline.due_date:
            start_time = deadline.due_time or datetime.min.time().replace(hour=17, minute=0)
            start = datetime.combine(deadline.due_date, start_time)
            schedulable.append(
                SchedulableEvent(
                    title=f"Deadline: {deadline.description}",
                    start=start,
                    end=start + timedelta(hours=1),
                    timezone="America/New_York",
                    description=_build_description(extraction, deadline, pdf_path=pdf_path),
                    event_kind=EventKind.deadline,
                    needs_review=False,
                    source_quote=deadline.source_quote,
                )
            )
        else:
            flagged.append(_deadline_to_flagged(extraction, deadline))

    return ReviewPackage(
        case_number=extraction.case_number,
        case_caption=extraction.case_caption,
        court=extraction.court,
        schedulable_events=schedulable,
        flagged_items=flagged,
        extraction=extraction,
        source_pdf_path=pdf_path,
        email_subject=email_subject,
        email_sender=email_sender,
        run_id=run_id,
    )
