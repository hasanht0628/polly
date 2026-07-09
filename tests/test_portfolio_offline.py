"""Offline portfolio workflow tests — no Ollama required."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from classification.client_codes import (
    ResolveStatus,
    load_client_code_table,
    resolve_officer_code,
)
from classification.schemas import ProductType
from portfolio.ambiguous_agent import AmbiguousClassificationOutput
from portfolio.dat_parser import account_folder_candidates, parse_dat_text
from portfolio.pdf_locator import find_account_pdfs
from workflows.portfolio_classification.run import run_portfolio_classification
from workflows.schemas import ClassificationSource

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _pad(s: str, width: int) -> str:
    return s[:width].ljust(width)


def _make_line(
    record_type: str,
    case_id: str,
    officer: str,
    misc: str = "XXXX",
    body: str = "",
) -> str:
    # record(2) + case(9) + pad(36) + officer(6) + pad(4) + misc(4) + rest
    prefix = (
        record_type
        + _pad(case_id, 9)
        + (" " * 36)
        + _pad(officer, 6)
        + (" " * 4)
        + _pad(misc, 4)
    )
    return prefix + body


def test_parse_dat_groups_records_and_trims_officer() -> None:
    # 01/09 body after misc: pad(6) + date(8) + pad(8 or 19) + payload
    note_body = (" " * 6) + "20240115" + (" " * 8) + "Called consumer; left VM"
    lines = [
        _make_line(
            "01",
            "493458439",
            "VIN02",
            "ABCD",
            (" " * 6) + "20240115" + (" " * 19) + "1234.56",
        ),
        _make_line("02", "493458439", "VIN02", "ABCD", "DOE/JANE" + " " * 20 + "123 MAIN ST"),
        _make_line("09", "493458439", "VIN02", "ABCD", note_body),
        _make_line("01", "111222333", "LP001 ", "ZZZZ", (" " * 6) + "20240201"),
    ]
    cases = parse_dat_text("\n".join(lines))
    assert len(cases) == 2
    first = cases[0]
    assert first.case_id == "493458439"
    assert first.officer_code == "VIN02"
    assert first.misc_code == "ABCD"
    assert first.record_types == ["01", "02", "09"]
    assert first.notes == ["Called consumer; left VM"]
    assert cases[1].officer_code == "LP001"


def test_officer_code_accepts_five_char() -> None:
    line = _make_line("01", "493458439", "CC100", "CARD")
    cases = parse_dat_text(line)
    assert cases[0].officer_code == "CC100"


def test_resolve_unique_and_ambiguous() -> None:
    rows = load_client_code_table(PROJECT_ROOT / "knowledge/client_codes/default.yaml")
    unique = resolve_officer_code("LP001", rows)
    assert unique.status == ResolveStatus.unique
    assert unique.archetype == ProductType.lending_point

    ambiguous = resolve_officer_code("VIN02", rows)
    assert ambiguous.status == ResolveStatus.ambiguous
    assert ProductType.fintech in ambiguous.candidates
    assert ProductType.auto_deficiency in ambiguous.candidates

    missing = resolve_officer_code("NOPE1", rows)
    assert missing.status == ResolveStatus.missing


def test_pdf_locator_finds_prefixed_account_folder(tmp_path: Path) -> None:
    case_id = "493458439"
    folder = tmp_path / "2026-04-20" / "PLMTDOCS_260420" / f"0{case_id}"
    folder.mkdir(parents=True)
    pdf = folder / "statement.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = find_account_pdfs(tmp_path, case_id)
    assert result.status == "found"
    assert result.account_folder == folder
    assert result.pdf_paths == [pdf]
    assert f"0{case_id}" in account_folder_candidates(case_id)


def test_portfolio_workflow_unique_short_circuit(tmp_path: Path) -> None:
    dat = tmp_path / "sample.dat"
    dat.write_text(_make_line("01", "111222333", "LP001", "LOAN") + "\n", encoding="utf-8")

    batch = asyncio.run(
        run_portfolio_classification(
            dat,
            docs_root=tmp_path / "docs",
            codes_path=PROJECT_ROOT / "knowledge/client_codes/default.yaml",
        )
    )
    assert len(batch.accounts) == 1
    account = batch.accounts[0]
    assert account.source == ClassificationSource.client_code
    assert account.archetype == ProductType.lending_point
    assert account.needs_review is False
    assert batch.summary["client_code"] == 1


def test_portfolio_workflow_ambiguous_uses_agent(tmp_path: Path) -> None:
    case_id = "493458439"
    dat = tmp_path / "sample.dat"
    dat.write_text(
        "\n".join(
            [
                _make_line("01", case_id, "VIN02", "MISC"),
                _make_line("09", case_id, "VIN02", "MISC", "Auto deficiency after repo"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    folder = docs / "PLMTDOCS_260420" / f"0{case_id}"
    folder.mkdir(parents=True)
    (folder / "notice.pdf").write_bytes(b"%PDF-1.4 fake")

    fake_output = AmbiguousClassificationOutput(
        archetype="auto_deficiency",
        confidence="medium",
        needs_review=True,
        evidence_quotes=["deficiency after repo"],
        pdf_paths_used=[str(folder / "notice.pdf")],
    )

    with patch(
        "workflows.portfolio_classification.run.run_ambiguous_classification",
        new_callable=AsyncMock,
        return_value=(fake_output, ["find_account_folder:found", "classify_archetype:notice.pdf"], None, None),
    ):
        batch = asyncio.run(
            run_portfolio_classification(
                dat,
                docs_root=docs,
                codes_path=PROJECT_ROOT / "knowledge/client_codes/default.yaml",
            )
        )

    assert len(batch.accounts) == 1
    account = batch.accounts[0]
    assert account.source == ClassificationSource.llm
    assert account.archetype == ProductType.auto_deficiency
    assert "find_account_folder:found" in account.tool_trace
