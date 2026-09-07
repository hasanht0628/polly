"""Locate detected PII spans as page rectangles (search_for + vision fallback)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import fitz
from pydantic_ai import NativeOutput
from pydantic_ai.messages import BinaryContent

from agents.config import make_ocr_agent
from agents.extract_utils import EXTRACT_MODEL_SETTINGS, RunMetrics
from documents.ocr import render_page_png
from redaction.schemas import (
    LocatedRedaction,
    NormalizedBox,
    PiiCandidate,
    VisionLocateOutput,
)

RECT_PAD_PT = 2.0

locate_agent = make_ocr_agent(
    output_type=NativeOutput(VisionLocateOutput),
    system_prompt=(
        "You locate known text strings on a document page image for redaction. "
        "Return normalized bounding boxes in [0,1] with origin at the top-left of the page. "
        "Only box the provided target strings; do not invent new entities."
    ),
    model_settings=EXTRACT_MODEL_SETTINGS,
    retries=2,
)


def _search_variants(text: str) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            variants.append(value)

    add(text)
    collapsed = re.sub(r"\s+", " ", text).strip()
    add(collapsed)
    add(re.sub(r"\s*\n\s*", " ", text))
    return variants


def _pad_rect(rect: fitz.Rect, page: fitz.Page, pad: float = RECT_PAD_PT) -> fitz.Rect:
    padded = fitz.Rect(
        rect.x0 - pad,
        rect.y0 - pad,
        rect.x1 + pad,
        rect.y1 + pad,
    )
    return padded & page.rect


def _rects_via_search(page: fitz.Page, text: str) -> list[fitz.Rect]:
    rects: list[fitz.Rect] = []
    for variant in _search_variants(text):
        hits = page.search_for(variant)
        if hits:
            rects.extend(hits)
            break
    if not rects and "\n" in text:
        line_rects: list[fitz.Rect] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            hits = page.search_for(line)
            if not hits:
                line_rects = []
                break
            line_rects.extend(hits)
        rects = line_rects
    return [_pad_rect(r, page) for r in rects]


def _norm_box_to_rect(box: NormalizedBox, page: fitz.Page) -> fitz.Rect:
    page_rect = page.rect
    x0 = page_rect.x0 + box.x0 * page_rect.width
    y0 = page_rect.y0 + box.y0 * page_rect.height
    x1 = page_rect.x0 + box.x1 * page_rect.width
    y1 = page_rect.y0 + box.y1 * page_rect.height
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return _pad_rect(fitz.Rect(x0, y0, x1, y1), page)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


async def _vision_locate(
    pdf_path: Path,
    page_index: int,
    targets: list[str],
    *,
    metrics: RunMetrics | None = None,
) -> dict[str, list[tuple[float, float, float, float]]]:
    if not targets:
        return {}

    png_bytes = render_page_png(pdf_path, page_index)
    target_list = json.dumps(targets, ensure_ascii=False)
    prompt = (
        "Locate each of these exact strings on the page image and return a bounding box "
        "for each one you can see. Coordinates must be normalized to [0,1] "
        "(x0,y0=top-left; x1,y1=bottom-right).\n\n"
        f"Target strings:\n{target_list}"
    )
    result = await locate_agent.run(
        [
            prompt,
            BinaryContent(data=png_bytes, media_type="image/png"),
        ]
    )
    if metrics is not None:
        metrics.incr_usage(result.usage)
        metrics.attempts += 1

    output: VisionLocateOutput = result.output
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        by_text: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
        for item in output.boxes:
            key = (item.text or "").strip()
            if not key:
                continue
            box = NormalizedBox(
                x0=_clamp01(item.box.x0),
                y0=_clamp01(item.box.y0),
                x1=_clamp01(item.box.x1),
                y1=_clamp01(item.box.y1),
            )
            rect = _norm_box_to_rect(box, page)
            by_text[key].append((rect.x0, rect.y0, rect.x1, rect.y1))

        resolved: dict[str, list[tuple[float, float, float, float]]] = {
            t: [] for t in targets
        }
        for target in targets:
            if target in by_text:
                resolved[target].extend(by_text[target])
                continue
            for key, rects in by_text.items():
                if key.lower() == target.lower() or key in target or target in key:
                    resolved[target].extend(rects)
        return resolved


async def locate_candidates(
    pdf_path: Path,
    candidates: list[PiiCandidate],
    *,
    metrics: RunMetrics | None = None,
) -> list[LocatedRedaction]:
    """Locate each candidate on its page; search first, vision for misses."""
    path = pdf_path.resolve()
    located: list[LocatedRedaction] = []
    if not candidates:
        return located

    by_page: dict[int, list[PiiCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_page[candidate.page].append(candidate)

    with fitz.open(path) as doc:
        for page_num, page_candidates in sorted(by_page.items()):
            page_index = page_num - 1
            if page_index < 0 or page_index >= doc.page_count:
                continue
            page = doc.load_page(page_index)
            missing: list[PiiCandidate] = []

            for candidate in page_candidates:
                rects = _rects_via_search(page, candidate.text)
                if rects:
                    for rect in rects:
                        located.append(
                            LocatedRedaction(
                                page=page_num,
                                entity_type=candidate.entity_type,
                                text=candidate.text,
                                confidence=candidate.confidence,
                                x0=rect.x0,
                                y0=rect.y0,
                                x1=rect.x1,
                                y1=rect.y1,
                                locate_method="search",
                            )
                        )
                else:
                    missing.append(candidate)

            if not missing:
                continue

            vision_map = await _vision_locate(
                path,
                page_index,
                [c.text for c in missing],
                metrics=metrics,
            )
            for candidate in missing:
                for coords in vision_map.get(candidate.text) or []:
                    located.append(
                        LocatedRedaction(
                            page=page_num,
                            entity_type=candidate.entity_type,
                            text=candidate.text,
                            confidence=candidate.confidence,
                            x0=coords[0],
                            y0=coords[1],
                            x1=coords[2],
                            y1=coords[3],
                            locate_method="vision",
                        )
                    )

    return located
