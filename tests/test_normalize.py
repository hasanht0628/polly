from court.extract_models import ExtractedDeadline, ExtractedEvent
from court.normalize import normalize_deadline, normalize_event
from court.schemas import DayType, DeadlineKind, LocationType, OffsetDirection


def test_normalize_event_strips_hallucinated_zoom_url() -> None:
    quote = (
        "Docket Sounding will be held on December 8, 2026 at 8:30 A.M. "
        "VIA ZOOM (ID: 311 329 7498), Courtroom 3C."
    )
    event = normalize_event(
        ExtractedEvent(
            event_type="docket_sounding",
            date="2026-12-08",
            time="8:30 A.M.",
            location_type="virtual",
            virtual_meeting_id="https://zoom.us/j/3113297498?pwd=fake",
            source_quote=quote,
        )
    )
    assert event.virtual_meeting_id == "311 329 7498"
    assert event.location_type == LocationType.virtual
    assert event.needs_review is False


def test_normalize_deadline_fills_anchor_and_offset() -> None:
    quote = (
        "No later than thirty (30) days prior to the Docket Sounding, counsel shall "
        "file and exchange a list of witnesses."
    )
    deadline = normalize_deadline(
        ExtractedDeadline(
            description="Exchange expert and lay witness list",
            kind="relative",
            source_quote=quote,
        )
    )
    assert deadline is not None
    assert deadline.kind == DeadlineKind.relative
    assert deadline.anchor_event == "Docket Sounding"
    assert deadline.offset_days == 30
    assert deadline.direction == OffsetDirection.before
    assert deadline.day_type == DayType.calendar
