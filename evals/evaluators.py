"""Custom pydantic-evals evaluators for court document pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluationReason

from court.schemas import CaseExtraction


def _compact_alnum(text: str) -> str:
    return re.sub(r"[\s,./\-:]+", "", text.lower())


def _phrase_present(phrase: str, text: str) -> bool:
    """Case-insensitive match; tolerate OCR spacing/punctuation drift."""
    lowered = phrase.lower()
    haystack = text.lower()
    if lowered in haystack:
        return True
    if sum(ch.isdigit() for ch in phrase) >= max(3, len(phrase) // 3):
        if _compact_alnum(phrase) in _compact_alnum(text):
            return True
    return False


@dataclass(repr=False)
class RequiredPhrasesPresent(Evaluator[str, str, dict]):
    """OCR output must contain every required phrase (case-insensitive)."""

    evaluation_name: str | None = field(default="required_phrases")

    def evaluate(self, ctx: EvaluatorContext[str, str, dict]) -> EvaluationReason:
        phrases: list[str] = ctx.metadata.get("required_phrases", [])
        if not phrases:
            return EvaluationReason(value=True)
        missing = [phrase for phrase in phrases if not _phrase_present(phrase, ctx.output)]
        if missing:
            return EvaluationReason(
                value=False,
                reason=f"missing phrases: {', '.join(missing)}",
            )
        return EvaluationReason(value=True)


@dataclass(repr=False)
class ExtractChecksPass(Evaluator[object, CaseExtraction, dict]):
    """Structured extraction must satisfy per-case checks from metadata."""

    evaluation_name: str | None = field(default="extract_checks")

    def evaluate(self, ctx: EvaluatorContext[object, CaseExtraction, dict]) -> EvaluationReason:
        checks: dict = ctx.metadata.get("extract_checks", {})
        if not checks:
            return EvaluationReason(value=True)
        output: CaseExtraction = ctx.output

        if expected_number := checks.get("case_number"):
            if output.case_number != expected_number:
                return EvaluationReason(
                    value=False,
                    reason=f"expected case_number {expected_number!r}, got {output.case_number!r}",
                )

        if min_events := checks.get("min_events"):
            if len(output.events) < int(min_events):
                return EvaluationReason(
                    value=False,
                    reason=f"expected at least {min_events} events, got {len(output.events)}",
                )

        if min_deadlines := checks.get("min_deadlines"):
            if len(output.deadlines) < int(min_deadlines):
                return EvaluationReason(
                    value=False,
                    reason=f"expected at least {min_deadlines} deadlines, got {len(output.deadlines)}",
                )

        if expected_types := checks.get("event_types"):
            actual = {event.event_type.lower().replace(" ", "_") for event in output.events}
            for event_type in expected_types:
                normalized = event_type.lower().replace(" ", "_")
                if not any(
                    normalized in actual_type or actual_type in normalized
                    for actual_type in actual
                ):
                    return EvaluationReason(
                        value=False,
                        reason=f"expected event_type {event_type!r}, got {sorted(actual)}",
                    )

        if deadline_phrases := checks.get("deadline_phrases"):
            blob = " ".join(d.description.lower() for d in output.deadlines)
            for phrase in deadline_phrases:
                if phrase.lower() not in blob:
                    return EvaluationReason(
                        value=False,
                        reason=f"missing deadline phrase: {phrase!r}",
                    )

        if checks.get("no_hallucinated_zoom_urls"):
            for event in output.events:
                if event.virtual_meeting_id and event.virtual_meeting_id.startswith(
                    ("http://", "https://")
                ):
                    return EvaluationReason(
                        value=False,
                        reason=(
                            "virtual_meeting_id looks like a URL, not an ID: "
                            f"{event.virtual_meeting_id!r}"
                        ),
                    )

        return EvaluationReason(value=True)


@dataclass(repr=False)
class ClassificationChecksPass(Evaluator[object, object, dict]):
    """Product classification must match expected account type and evidence."""

    evaluation_name: str | None = field(default="classification_checks")

    def evaluate(self, ctx: EvaluatorContext[object, object, dict]) -> EvaluationReason:
        checks: dict = ctx.metadata.get("classification_checks", {})
        if not checks:
            return EvaluationReason(value=True)

        output = ctx.output
        product_type = getattr(output, "product_type", None)
        actual = product_type.value if hasattr(product_type, "value") else str(product_type)

        expected = checks.get("expected_product_type")
        if expected and actual != expected:
            return EvaluationReason(
                value=False,
                reason=f"expected product_type {expected!r}, got {actual!r}",
            )

        quotes = getattr(output, "evidence_quotes", []) or []
        blob = " ".join(quotes).lower()
        for phrase in checks.get("evidence_phrases", []):
            if phrase.lower() not in blob:
                return EvaluationReason(
                    value=False,
                    reason=f"missing evidence phrase: {phrase!r}",
                )

        return EvaluationReason(value=True)
