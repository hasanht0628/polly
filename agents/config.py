"""Model configuration for pydantic-ai agents (Ollama local, optional OpenAI)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Local CPU-only inference can take many minutes per call, well past the OpenAI
# client's default read timeout. A too-short timeout aborts the whole run (and,
# in batch mode, loses all prior work). Allow a generous, env-tunable timeout.
_DEFAULT_OLLAMA_TIMEOUT_S = 1200.0
_OLLAMA_HTTP_CLIENT: httpx.AsyncClient | None = None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _ollama_timeout_s() -> float:
    try:
        return float(os.environ.get("OLLAMA_TIMEOUT_S", _DEFAULT_OLLAMA_TIMEOUT_S))
    except (TypeError, ValueError):
        return _DEFAULT_OLLAMA_TIMEOUT_S


def _ollama_http_client() -> httpx.AsyncClient:
    """Shared httpx client with a long read timeout for slow local inference."""
    global _OLLAMA_HTTP_CLIENT
    if _OLLAMA_HTTP_CLIENT is None or _OLLAMA_HTTP_CLIENT.is_closed:
        timeout = httpx.Timeout(_ollama_timeout_s(), connect=30.0)
        _OLLAMA_HTTP_CLIENT = httpx.AsyncClient(timeout=timeout)
    return _OLLAMA_HTTP_CLIENT


def use_openai() -> bool:
    """Temporary switch: when true, all agents use OpenAI instead of Ollama."""
    return _truthy(os.environ.get("USE_OPENAI"))


def _openai_model(model_name: str) -> OpenAIChatModel:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("USE_OPENAI is enabled but OPENAI_API_KEY is not set")
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(api_key=api_key),
    )


def _ollama_model(model_name: str) -> OllamaModel:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    return OllamaModel(
        model_name,
        provider=OllamaProvider(base_url=base_url, http_client=_ollama_http_client()),
    )


def make_agent(**kwargs) -> Agent:
    if use_openai():
        model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        model = _openai_model(model_name)
    else:
        model_name = os.environ["OLLAMA_MODEL"]
        model = _ollama_model(model_name)
    return Agent(model, **kwargs)


def make_ocr_agent(**kwargs) -> Agent:
    if use_openai():
        model_name = os.environ.get("OPENAI_MODEL_OCR", "gpt-4o-mini")
        model = _openai_model(model_name)
    else:
        model_name = os.environ["OLLAMA_MODEL_OCR"]
        model = _ollama_model(model_name)
    return Agent(model, **kwargs)


def active_model_names() -> dict[str, str]:
    """Return the chat/OCR model names currently selected by USE_OPENAI."""
    if use_openai():
        return {
            "provider": "openai",
            "chat_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "ocr_model": os.environ.get("OPENAI_MODEL_OCR", "gpt-4o-mini"),
        }
    return {
        "provider": "ollama",
        "chat_model": os.environ.get("OLLAMA_MODEL", ""),
        "ocr_model": os.environ.get("OLLAMA_MODEL_OCR", ""),
    }
