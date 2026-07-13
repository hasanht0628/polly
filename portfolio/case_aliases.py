"""Load case_id → account folder name aliases for synthetic portfolio fixtures."""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASE_MAP = PROJECT_ROOT / "fixtures/portfolio/case_id_map.yaml"


def load_folder_aliases(case_map_path: Path | None = None) -> dict[str, list[str]]:
    """Return ``{case_id: [account_id, ...]}`` from a case_id_map.yaml file."""
    path = Path(case_map_path) if case_map_path else DEFAULT_CASE_MAP
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases: dict[str, list[str]] = {}
    for entry in raw.get("accounts") or []:
        case_id = str(entry.get("case_id") or "").strip()
        account_id = str(entry.get("account_id") or "").strip()
        if not case_id or not account_id:
            continue
        aliases.setdefault(case_id, [])
        if account_id not in aliases[case_id]:
            aliases[case_id].append(account_id)
    return aliases
