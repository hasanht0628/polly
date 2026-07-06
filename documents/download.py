"""Download PDFs to local storage."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx


class PdfStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def download(self, url: str, *, filename: str | None = None) -> Path:
        parsed = urlparse(url)
        name = filename or Path(parsed.path).name or "document.pdf"
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
        dest = self.root / name
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            dest.write_bytes(response.content)
        return dest

    def resolve_local(self, path: Path) -> Path:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
