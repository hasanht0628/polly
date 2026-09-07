"""Resolve file / files / folder inputs to PDF paths for redaction."""

from __future__ import annotations

from pathlib import Path


def is_redacted_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf" and path.stem.endswith(".redacted")


def resolve_pdf_paths(path: Path | list[Path]) -> list[Path]:
    """Expand a path, list of paths, or directory into PDF files to redact.

    Skips ``*.redacted.pdf`` outputs so re-running a folder is safe.
    """
    if isinstance(path, list):
        paths = path
    else:
        paths = [path]

    found: list[Path] = []
    seen: set[Path] = set()

    for raw in paths:
        candidate = raw.expanduser().resolve()
        if candidate.is_dir():
            for pdf in sorted(candidate.rglob("*.pdf")):
                if is_redacted_pdf(pdf):
                    continue
                resolved = pdf.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(resolved)
            continue

        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        if candidate.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF: {candidate}")
        if is_redacted_pdf(candidate):
            continue
        if candidate not in seen:
            seen.add(candidate)
            found.append(candidate)

    return found


def redacted_output_path(source: Path, *, out_dir: Path | None = None) -> Path:
    name = f"{source.stem}.redacted.pdf"
    if out_dir is None:
        return source.with_name(name)
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / name
