"""Persist and retrieve client manual knowledge (taxonomy + chunks)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from classification.schemas import ClientTaxonomy
from documents.profiles.registry import extract_document
from documents.text import load_document_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "knowledge" / "client_manuals"


@dataclass(frozen=True)
class ManualChunk:
    section: str
    text: str


def _client_dir(root: Path, client_id: str) -> Path:
    return root / client_id


def _chunk_manual(text: str, *, max_chars: int = 1500) -> list[ManualChunk]:
    sections = re.split(r"\n(?=[A-Z][A-Z0-9 /\-]{4,}\n)", text)
    chunks: list[ManualChunk] = []
    for index, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        title = section.splitlines()[0][:80]
        for offset in range(0, len(section), max_chars):
            chunk_text = section[offset : offset + max_chars]
            label = title if offset == 0 else f"{title} (part {offset // max_chars + 1})"
            chunks.append(ManualChunk(section=label, text=chunk_text))
    if not chunks and text.strip():
        for offset in range(0, len(text), max_chars):
            chunks.append(
                ManualChunk(
                    section=f"Section {offset // max_chars + 1}",
                    text=text[offset : offset + max_chars],
                )
            )
    return chunks


async def ingest_client_manual(
    client_id: str,
    pdf_path: Path,
    *,
    root: Path = DEFAULT_ROOT,
    use_cache: bool = True,
) -> ClientTaxonomy:
    pdf_path = pdf_path.resolve()
    result = await extract_document(
        pdf_path,
        profile="client_manual_taxonomy",
        use_cache=use_cache,
        context={"client_id": client_id},
    )
    taxonomy: ClientTaxonomy = result.data
    taxonomy.client_id = client_id

    document = await load_document_text(pdf_path, use_cache=use_cache)
    chunks = _chunk_manual(document.text)

    client_dir = _client_dir(root, client_id)
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "taxonomy.json").write_text(
        taxonomy.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (client_dir / "chunks.json").write_text(
        json.dumps([{"section": c.section, "text": c.text} for c in chunks], indent=2)
        + "\n",
        encoding="utf-8",
    )
    return taxonomy


def load_taxonomy(client_id: str, *, root: Path = DEFAULT_ROOT) -> ClientTaxonomy:
    path = _client_dir(root, client_id) / "taxonomy.json"
    if not path.is_file():
        raise FileNotFoundError(f"No taxonomy for client {client_id!r} at {path}")
    return ClientTaxonomy.model_validate_json(path.read_text(encoding="utf-8"))


def load_chunks(client_id: str, *, root: Path = DEFAULT_ROOT) -> list[ManualChunk]:
    path = _client_dir(root, client_id) / "chunks.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ManualChunk(section=item["section"], text=item["text"]) for item in data]


def retrieve_manual_passages(
    client_id: str,
    query: str,
    *,
    top_k: int = 3,
    root: Path = DEFAULT_ROOT,
) -> list[str]:
    chunks = load_chunks(client_id, root=root)
    if not chunks:
        return []

    query_tokens = {t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query) if len(t) > 2}

    def score(chunk: ManualChunk) -> int:
        text_tokens = {t.lower() for t in re.findall(r"[a-zA-Z0-9]+", chunk.text) if len(t) > 2}
        return len(query_tokens & text_tokens)

    ranked = sorted(chunks, key=score, reverse=True)
    selected = [c for c in ranked if score(c) > 0][:top_k]
    if not selected:
        selected = ranked[:top_k]
    return [f"[{c.section}]\n{c.text}" for c in selected]
