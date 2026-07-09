"""Officer-code → product-code → archetype mapping store."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from classification.schemas import ProductType

DEFAULT_CODES_PATH = (
    Path(__file__).resolve().parent.parent / "knowledge" / "client_codes" / "default.yaml"
)


class ResolveStatus(str, Enum):
    unique = "unique"
    ambiguous = "ambiguous"
    missing = "missing"


class ClientCodeRow(BaseModel):
    officer_code: str
    portfolio: str = ""
    legal_name: str = ""
    product_code: str
    product_description: str = ""
    archetype: ProductType | None = None


class ResolveResult(BaseModel):
    officer_code: str
    status: ResolveStatus
    archetype: ProductType | None = None
    candidates: list[ProductType] = Field(default_factory=list)
    product_codes: list[str] = Field(default_factory=list)
    rows: list[ClientCodeRow] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


def _normalize_officer_code(code: str) -> str:
    return code.strip().upper()


def _normalize_product_code(code: str) -> str:
    return code.strip().upper()


def _parse_archetype(value: str | None) -> ProductType | None:
    if value is None:
        return None
    raw = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if not raw or raw in {"??", "undetermined", "unknown", "none", "null"}:
        return None
    try:
        return ProductType(raw)
    except ValueError:
        return None


def load_client_code_table(path: Path | None = None) -> list[ClientCodeRow]:
    path = path or DEFAULT_CODES_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"Client code table must be a YAML list: {path}")

    rows: list[ClientCodeRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        officer = _normalize_officer_code(str(item.get("officer_code", "")))
        product = _normalize_product_code(str(item.get("product_code", "")))
        if not officer or not product:
            continue
        rows.append(
            ClientCodeRow(
                officer_code=officer,
                portfolio=str(item.get("portfolio") or item.get("portfoliio_description") or ""),
                legal_name=str(item.get("legal_name") or item.get("legal_name_for_suit") or ""),
                product_code=product,
                product_description=str(item.get("product_description") or ""),
                archetype=_parse_archetype(item.get("archetype")),
            )
        )
    return rows


def resolve_officer_code(
    officer_code: str,
    rows: list[ClientCodeRow] | None = None,
    *,
    table_path: Path | None = None,
) -> ResolveResult:
    code = _normalize_officer_code(officer_code)
    table = rows if rows is not None else load_client_code_table(table_path)
    matches = [row for row in table if row.officer_code == code]

    if not matches:
        return ResolveResult(
            officer_code=code,
            status=ResolveStatus.missing,
            evidence=[f"No client-code rows for officer_code={code}"],
        )

    product_codes = sorted({row.product_code for row in matches})
    archetypes = sorted(
        {row.archetype for row in matches if row.archetype is not None},
        key=lambda a: a.value,
    )
    undetermined = [row for row in matches if row.archetype is None]

    evidence = [
        f"{row.officer_code}/{row.product_code} → "
        f"{row.archetype.value if row.archetype else 'undetermined'}"
        f" ({row.product_description or row.portfolio or 'no description'})"
        for row in matches
    ]

    if undetermined or len(archetypes) != 1:
        return ResolveResult(
            officer_code=code,
            status=ResolveStatus.ambiguous,
            candidates=list(archetypes),
            product_codes=product_codes,
            rows=matches,
            evidence=evidence,
        )

    return ResolveResult(
        officer_code=code,
        status=ResolveStatus.unique,
        archetype=archetypes[0],
        candidates=list(archetypes),
        product_codes=product_codes,
        rows=matches,
        evidence=evidence,
    )
