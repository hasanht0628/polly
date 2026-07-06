import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

# Load .env from project root (parent of tutorials/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def make_agent(**kwargs) -> Agent:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model_name = os.environ["OLLAMA_MODEL"]
    model = OllamaModel(
        model_name,
        provider=OllamaProvider(base_url=base_url),
    )
    return Agent(model, **kwargs)


def make_ocr_agent(**kwargs) -> Agent:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model_name = os.environ["OLLAMA_MODEL_OCR"]
    model = OllamaModel(
        model_name,
        provider=OllamaProvider(base_url=base_url),
    )
    return Agent(model, **kwargs)