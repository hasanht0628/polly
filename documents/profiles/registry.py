from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from documents.profiles import court_calendar
from documents.schemas import ExtractResult

ProfileRunner = Callable[..., Awaitable[ExtractResult]]

_REGISTRY: dict[str, ProfileRunner] = {}


def register_profile(profile_id: str, runner: ProfileRunner) -> None:
    _REGISTRY[profile_id] = runner


def list_profiles() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


async def extract_document(
    pdf_path: Path,
    profile: str,
    *,
    use_cache: bool = True,
    context: dict[str, Any] | None = None,
) -> ExtractResult:
    if profile not in _REGISTRY:
        known = ", ".join(list_profiles()) or "(none)"
        raise ValueError(f"Unknown extract profile {profile!r}. Known: {known}")
    return await _REGISTRY[profile](
        pdf_path.resolve(),
        use_cache=use_cache,
        context=context or {},
    )


def _register_defaults() -> None:
    register_profile("court_calendar", court_calendar.run_court_calendar)
    from documents.profiles import client_manual_taxonomy, product_classification

    register_profile(
        "client_manual_taxonomy",
        client_manual_taxonomy.run_client_manual_taxonomy,
    )
    register_profile(
        "product_classification",
        product_classification.run_product_classification,
    )


_register_defaults()
