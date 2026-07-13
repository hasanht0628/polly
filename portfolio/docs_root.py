"""Prepare portfolio docs roots by extracting PLMTDOCS zip archives."""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

PLMTDOCS_ZIP_RE = re.compile(r"^PLMTDOCS_\d{6}\.zip$", re.IGNORECASE)


def _is_plmtdocs_zip(path: Path) -> bool:
    return path.is_file() and bool(PLMTDOCS_ZIP_RE.match(path.name))


def _target_dir(zip_path: Path) -> Path:
    return zip_path.with_suffix("")


def _should_extract(zip_path: Path, target_dir: Path) -> bool:
    if not target_dir.is_dir():
        return True
    try:
        return zip_path.stat().st_mtime > target_dir.stat().st_mtime
    except OSError:
        return True


def _extract_plmtdocs_zip(zip_path: Path, target_dir: Path) -> None:
    """Extract zip to sibling folder PLMTDOCS_YYMMDD/."""
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        children = [
            p
            for p in tmp_path.iterdir()
            if p.name not in {"__MACOSX"} and not p.name.startswith(".")
        ]
        if len(children) == 1 and children[0].is_dir():
            inner = children[0]
            if inner.name.upper() == target_dir.name.upper():
                content_root = inner
            else:
                content_root = tmp_path
        else:
            content_root = tmp_path

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(content_root, target_dir)


def prepare_docs_root(docs_root: Path) -> Path:
    """Extract PLMTDOCS_YYMMDD.zip archives under docs_root, then return docs_root.

    Each zip is extracted to a sibling directory with the same stem
    (e.g. PLMTDOCS_250708.zip → PLMTDOCS_250708/). Skips extraction when
    the target folder exists and is newer than the zip.
    """
    docs_root = docs_root.resolve()
    if not docs_root.is_dir():
        raise FileNotFoundError(docs_root)

    for zip_path in sorted(docs_root.rglob("*.zip")):
        if not _is_plmtdocs_zip(zip_path):
            continue
        target = _target_dir(zip_path)
        if _should_extract(zip_path, target):
            _extract_plmtdocs_zip(zip_path, target)

    return docs_root
