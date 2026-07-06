"""Parse local .eml files for court document intake."""

from __future__ import annotations

import re
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path

from workflows.schemas import IntakeEmail

_PDF_URL = re.compile(r"https?://[^\s<>\"']+\.pdf(?:\?[^\s<>\"']*)?", re.IGNORECASE)
_DOCUMENTS_HEADER = re.compile(r"^documents\s*:?\s*$", re.IGNORECASE | re.MULTILINE)
_DISCLAIMER_MARKERS = (
    "confidentiality notice",
    "this email and any attachments",
    "privileged and confidential",
    "if you are not the intended recipient",
)


def _split_body_and_disclaimer(body: str) -> str:
    lowered = body.lower()
    cut = len(body)
    for marker in _DISCLAIMER_MARKERS:
        idx = lowered.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    return body[:cut].strip()


def _extract_documents_section(body: str) -> tuple[str, list[str]]:
    urls: list[str] = []
    documents_section: str | None = None

    match = _DOCUMENTS_HEADER.search(body)
    if match:
        start = match.end()
        tail = body[start:].strip()
        documents_section = tail.split("\n\n", 1)[0].strip()
        urls.extend(_PDF_URL.findall(documents_section))

    urls.extend(_PDF_URL.findall(body))
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return documents_section or "", unique_urls


def parse_eml(path: Path) -> IntakeEmail:
    raw = path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(raw)

    body_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_content()
                if isinstance(payload, str):
                    body_parts.append(payload)
    else:
        payload = message.get_content()
        if isinstance(payload, str):
            body_parts.append(payload)

    body = _split_body_and_disclaimer("\n".join(body_parts))
    documents_section, pdf_urls = _extract_documents_section(body)

    received = message.get("Date")
    received_at = None
    if received:
        try:
            from email.utils import parsedate_to_datetime

            received_at = parsedate_to_datetime(received)
        except (TypeError, ValueError):
            received_at = None

    return IntakeEmail(
        sender=message.get("From"),
        subject=message.get("Subject"),
        received_at=received_at,
        body_text=body,
        pdf_urls=pdf_urls,
        documents_section=documents_section or None,
    )


def parse_email_text(text: str, *, subject: str | None = None, sender: str | None = None) -> IntakeEmail:
    body = _split_body_and_disclaimer(text)
    documents_section, pdf_urls = _extract_documents_section(body)
    return IntakeEmail(
        sender=sender,
        subject=subject,
        received_at=datetime.now(),
        body_text=body,
        pdf_urls=pdf_urls,
        documents_section=documents_section or None,
    )
