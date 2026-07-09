"""Model configuration for pydantic-ai agents (Ollama local, optional OpenAI)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


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
        provider=OllamaProvider(base_url=base_url),
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
