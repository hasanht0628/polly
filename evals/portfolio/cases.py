"""Portfolio classification eval case registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

EVALS_DIR = Path(__file__).resolve().parent.parent
PORTFOLIO_DIR = EVALS_DIR / "portfolio"
PROJECT_ROOT = EVALS_DIR.parent
CASES_PATH = PORTFOLIO_DIR / "cases.yaml"


@dataclass(frozen=True)
class PortfolioEvalCase:
    slug: str
    case_id: str
    account_id: str
    resolve_path: str
    expected_source: str
    expected_archetype: str


@dataclass(frozen=True)
class PortfolioEvalConfig:
    dat_path: Path
    docs_root: Path
    codes_path: Path
    case_map_path: Path
    client_id: str
    cases: tuple[PortfolioEvalCase, ...]


def _load_config() -> PortfolioEvalConfig:
    if not CASES_PATH.is_file():
        raise FileNotFoundError(CASES_PATH)
    raw = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8")) or {}
    cases = tuple(
        PortfolioEvalCase(
            slug=str(item["slug"]),
            case_id=str(item["case_id"]),
            account_id=str(item["account_id"]),
            resolve_path=str(item["resolve_path"]),
            expected_source=str(item["expected_source"]),
            expected_archetype=str(item["expected_archetype"]),
        )
        for item in raw.get("cases") or []
    )
    return PortfolioEvalConfig(
        dat_path=PROJECT_ROOT / str(raw["dat_path"]),
        docs_root=PROJECT_ROOT / str(raw["docs_root"]),
        codes_path=PROJECT_ROOT / str(raw["codes_path"]),
        case_map_path=PROJECT_ROOT / str(raw["case_map_path"]),
        client_id=str(raw.get("client_id", "portfolio")),
        cases=cases,
    )


PORTFOLIO_EVAL = _load_config()
PORTFOLIO_CASES = PORTFOLIO_EVAL.cases
