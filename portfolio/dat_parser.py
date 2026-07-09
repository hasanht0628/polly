"""Fixed-width .dat parser for portfolio case records.

Slice constants are centralized here so Phase-0 offset tweaks stay localized.
Offsets below are derived from the firm layout description and synthetic fixtures;
re-run ``scripts/inspect_dat.py`` against a real file to confirm before production use.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

# Layout: record_type(2) + case_id(9) + pad(36) + officer(6) + pad(4) + misc_code(4) + ...
RECORD_TYPE_SLICE = slice(0, 2)
CASE_ID_SLICE = slice(2, 11)
OFFICER_CODE_SLICE = slice(47, 53)
MISC_CODE_SLICE = slice(57, 61)

# 01 account / financial fields (approximate; refine with inspect_dat on real files)
DATE_SLICE = slice(67, 75)
DEBT_AMOUNT_SLICE = slice(94, 110)
PLAINTIFF_SLICE = slice(200, 260)

# 02 consumer fields (approximate)
CONSUMER_NAME_SLICE = slice(67, 110)
ADDRESS_SLICE = slice(110, 160)
CITY_STATE_SLICE = slice(164, 200)
ZIP_SLICE = slice(215, 224)
PHONE_SLICE = slice(228, 242)
SSN_SLICE = slice(256, 267)
DOB_SLICE = slice(281, 291)

# 09 notes: after misc(61) + pad(6) + date(8) + pad(8)
NOTES_DATE_SLICE = slice(67, 75)
NOTES_SLICE = slice(83, None)


class DatConsumer(BaseModel):
    name: str = ""
    address: str = ""
    city_state: str = ""
    zip_code: str = ""
    phone: str = ""
    # Stored for downstream use; never write raw SSN into audit logs.
    ssn: str = ""
    date_of_birth: str = ""


class DatCase(BaseModel):
    case_id: str
    officer_code: str = ""
    misc_code: str = ""
    plaintiff: str = ""
    debt_amount: str = ""
    account_date: str = ""
    notes: list[str] = Field(default_factory=list)
    consumer: DatConsumer = Field(default_factory=DatConsumer)
    record_types: list[str] = Field(default_factory=list)
    raw_lines: list[str] = Field(default_factory=list)


def _field(line: str, sl: slice) -> str:
    if len(line) <= sl.start:
        return ""
    return line[sl].strip()


def _parse_01(line: str, case: DatCase) -> None:
    case.officer_code = _field(line, OFFICER_CODE_SLICE) or case.officer_code
    case.misc_code = _field(line, MISC_CODE_SLICE) or case.misc_code
    case.account_date = _field(line, DATE_SLICE) or case.account_date
    case.debt_amount = _field(line, DEBT_AMOUNT_SLICE) or case.debt_amount
    case.plaintiff = _field(line, PLAINTIFF_SLICE) or case.plaintiff


def _parse_02(line: str, case: DatCase) -> None:
    # Officer code also appears on 02 lines; prefer 01 but fill if missing.
    case.officer_code = case.officer_code or _field(line, OFFICER_CODE_SLICE)
    case.misc_code = case.misc_code or _field(line, MISC_CODE_SLICE)
    consumer = case.consumer
    consumer.name = _field(line, CONSUMER_NAME_SLICE) or consumer.name
    consumer.address = _field(line, ADDRESS_SLICE) or consumer.address
    consumer.city_state = _field(line, CITY_STATE_SLICE) or consumer.city_state
    consumer.zip_code = _field(line, ZIP_SLICE) or consumer.zip_code
    consumer.phone = _field(line, PHONE_SLICE) or consumer.phone
    consumer.ssn = _field(line, SSN_SLICE) or consumer.ssn
    consumer.date_of_birth = _field(line, DOB_SLICE) or consumer.date_of_birth


def _parse_09(line: str, case: DatCase) -> None:
    case.officer_code = case.officer_code or _field(line, OFFICER_CODE_SLICE)
    note = _field(line, NOTES_SLICE)
    if note:
        case.notes.append(note)


def parse_dat_line(line: str) -> tuple[str, str, str]:
    """Return (record_type, case_id, officer_code) for a single line."""
    raw = line.rstrip("\n\r")
    record_type = _field(raw, RECORD_TYPE_SLICE)
    case_id = _field(raw, CASE_ID_SLICE)
    officer_code = _field(raw, OFFICER_CODE_SLICE)
    return record_type, case_id, officer_code


def parse_dat_text(text: str) -> list[DatCase]:
    grouped: dict[str, DatCase] = {}
    order: list[str] = []

    for line in text.splitlines():
        if not line.strip():
            continue
        record_type, case_id, _officer = parse_dat_line(line)
        if not case_id:
            continue
        if case_id not in grouped:
            grouped[case_id] = DatCase(case_id=case_id)
            order.append(case_id)
        case = grouped[case_id]
        case.raw_lines.append(line.rstrip("\n\r"))
        if record_type and record_type not in case.record_types:
            case.record_types.append(record_type)
        if record_type == "01":
            _parse_01(line, case)
        elif record_type == "02":
            _parse_02(line, case)
        elif record_type == "09":
            _parse_09(line, case)
        else:
            # Unknown record types: still capture officer if present.
            case.officer_code = case.officer_code or _field(line, OFFICER_CODE_SLICE)

    return [grouped[cid] for cid in order]


def parse_dat_file(path: Path) -> list[DatCase]:
    return parse_dat_text(path.read_text(encoding="utf-8", errors="replace"))


def account_folder_candidates(case_id: str) -> list[str]:
    """Folder names that may correspond to a .dat case id.

    Firm convention: account folder has one extra leading character vs case id.
    Also accept an exact match.
    """
    case_id = case_id.strip()
    candidates = [case_id]
    # Common pattern: leading digit prefix on the folder (e.g. case 493458439 → 0493458439)
    for prefix in "0123456789":
        candidates.append(f"{prefix}{case_id}")
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for name in candidates:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out
