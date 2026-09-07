"""Shared document ingest / extract helpers.

Import concrete modules directly (``documents.text``, ``documents.profiles.registry``)
to avoid eager circular imports through package ``__init__`` re-exports.
"""

from __future__ import annotations

from documents.schemas import DocumentTextResult, ExtractResult

__all__ = ["DocumentTextResult", "ExtractResult"]
