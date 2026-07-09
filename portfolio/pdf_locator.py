"""Locate account PDF folders under a docs root."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from portfolio.dat_parser import account_folder_candidates

PLMTDOCS_RE = re.compile(r"^PLMTDOCS_\d{6}$", re.IGNORECASE)


class PdfLocateResult(BaseModel):
    case_id: str
    status: str  # found | not_found | ambiguous
    account_folder: Path | None = None
    pdf_paths: list[Path] = Field(default_factory=list)
    matched_names: list[str] = Field(default_factory=list)
    search_pattern: str = ""
    evidence: list[str] = Field(default_factory=list)


def _is_plmtdocs_dir(path: Path) -> bool:
    return path.is_dir() and bool(PLMTDOCS_RE.match(path.name))


def _collect_pdfs(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*.pdf") if p.is_file())


def find_account_folders(docs_root: Path, case_id: str) -> list[Path]:
    """Return directories under docs_root whose names match the case/account id rule."""
    docs_root = docs_root.resolve()
    wanted = set(account_folder_candidates(case_id))
    matches: list[Path] = []

    for path in docs_root.rglob("*"):
        if not path.is_dir():
            continue
        if path.name not in wanted:
            continue
        matches.append(path)

    # Prefer folders under a PLMTDOCS_* parent when multiple matches exist.
    plmt = [p for p in matches if any(_is_plmtdocs_dir(parent) for parent in p.parents)]
    if plmt:
        return sorted(plmt)
    return sorted(matches)


def find_account_pdfs(docs_root: Path, case_id: str) -> PdfLocateResult:
    docs_root = Path(docs_root)
    case_id = case_id.strip()
    pattern = f"folder in {account_folder_candidates(case_id)!r} under {docs_root}"
    folders = find_account_folders(docs_root, case_id)

    if not folders:
        return PdfLocateResult(
            case_id=case_id,
            status="not_found",
            search_pattern=pattern,
            evidence=[f"No account folder matching case_id={case_id}"],
        )

    if len(folders) > 1:
        # If multiple folders share the same leaf name, prefer the one with PDFs.
        with_pdfs = [f for f in folders if _collect_pdfs(f)]
        chosen = with_pdfs[0] if len(with_pdfs) == 1 else folders[0]
        if len(with_pdfs) > 1 or (not with_pdfs and len(folders) > 1):
            pdfs = _collect_pdfs(chosen)
            return PdfLocateResult(
                case_id=case_id,
                status="ambiguous",
                account_folder=chosen,
                pdf_paths=pdfs,
                matched_names=[p.name for p in folders],
                search_pattern=pattern,
                evidence=[
                    f"Multiple folders matched: {[str(p) for p in folders]}; using {chosen}"
                ],
            )
        folders = [chosen]

    folder = folders[0]
    pdfs = _collect_pdfs(folder)
    return PdfLocateResult(
        case_id=case_id,
        status="found",
        account_folder=folder,
        pdf_paths=pdfs,
        matched_names=[folder.name],
        search_pattern=pattern,
        evidence=[f"Matched account folder {folder}"],
    )


def list_pdfs(folder: Path) -> list[Path]:
    return _collect_pdfs(Path(folder))
